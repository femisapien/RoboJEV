"""Continue interrupted JEV requests without resampling any received model answer.

Private journals contain requests/responses; never publish the run directory.
The existing simulator and prompts stay frozen. This is an opt-in experiment driver.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import time
from pathlib import Path

import httpx

from jev_vla_sim.config import Config
from jev_vla_sim.policy import JevPolicy
from jev_vla_sim.recording import make_run, source_fingerprint, write_json
from jev_vla_sim.runner import run_episode
from robojev_ui.credentials import Credentials
from robojev_ui.reports import outcome_category, summary

TRANSIENT = {429, 500, 502, 503, 504, 529}


class ServiceBlocked(RuntimeError):
    """Billing/authentication needs operator action; never score it as robot failure."""

    def __init__(self, status):
        self.status = status
        super().__init__(f"API blocked by HTTP {status}; keep trial unresolved")


def equivalent(a, b):
    """Preserve discrete fields exactly; allow 1e-9 physics roundoff in continuous values."""
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(equivalent(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(equivalent(x, y) for x, y in zip(a, b))
    if type(a) is float and type(b) is float:
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
    return type(a) is type(b) and a == b


def physical_equivalent(a, b):
    """Verify poses/joints/actions; replay recorded derived mesh-distance features.

    MuJoCo mesh distance queries can jump at floating-point degeneracies even
    when every underlying physical coordinate agrees to machine precision.
    This exception applies only to replay, never to newly queried observations.
    """
    def without_derived(value):
        value = copy.deepcopy(value)
        def walk(v):
            if isinstance(v, dict):
                if "spatial_geometry" in v and v["spatial_geometry"] is not None:
                    v["spatial_geometry"].pop("current_signed_distances", None)
                for item in v.values():
                    walk(item)
            elif isinstance(v, list):
                for item in v:
                    walk(item)
        walk(value)
        return value
    return equivalent(without_derived(a), without_derived(b))


def prefix_responses(episode):
    entries = []
    for line in (episode / "steps.jsonl").read_text(encoding="utf-8").splitlines():
        exchange = json.loads(line).get("exchange", {})
        for stage in ("intent", "motor"):
            record = exchange.get(stage, {})
            if "response" in record:
                entries.append({"request": record["request"], "response": record["response"], "status": 200})
    return entries


class PersistentClient:
    """Replay received answers exactly, then retry one unchanged HTTP request."""

    def __init__(self, entries, journal, audit, client=None, sleep=time.sleep, limit=20, pending=None):
        self.entries = entries
        self.position = 0
        self.journal, self.audit = journal, audit
        self.client = client or httpx.Client(timeout=60, follow_redirects=False)
        self.sleep, self.limit = sleep, limit
        self.pending = pending
        self.network_requests = self.transport_failures = self.http_failures = 0

    def post(self, url, *, json, headers):
        if self.position < len(self.entries):
            record = self.entries[self.position]
            if not physical_equivalent(record["request"], json):
                raise RuntimeError(f"Frozen request mismatch at cached stage {self.position}")
            json.clear()
            json.update(copy.deepcopy(record["request"]))
            self.position += 1
            return (httpx.Response(record["status"], content=bytes.fromhex(record["content_hex"]))
                    if "content_hex" in record else httpx.Response(record["status"], json=record["response"]))
        if self.pending is not None:
            if not physical_equivalent(self.pending, json):
                raise RuntimeError("Interrupted request physical state mismatch")
            json.clear()
            json.update(copy.deepcopy(self.pending))
            self.pending = None
        for attempt in range(self.limit):
            self.network_requests += 1
            try:
                response = self.client.post(url, json=json, headers=headers)
                if response.status_code in {401, 402, 403}:
                    import json as codec
                    self.audit.write(codec.dumps({"request_number": self.network_requests,
                                                  "error_type": f"HTTP_{response.status_code}",
                                                  "physics_paused": True, "operator_action_required": True}) + "\n")
                    self.audit.flush()
                    raise ServiceBlocked(response.status_code)
                if response.status_code not in TRANSIENT:
                    # Persist received answers BEFORE policy validation. Never retry an invalid answer.
                    record = {"request": json, "status": response.status_code,
                              "content_hex": response.content.hex()}
                    import json as codec
                    self.journal.write(codec.dumps(record, allow_nan=False) + "\n")
                    self.journal.flush()
                    return response
                self.http_failures += 1
                kind = f"HTTP_{response.status_code}"
            except httpx.TransportError as exc:
                self.transport_failures += 1
                kind = type(exc).__name__
            import json as codec
            self.audit.write(codec.dumps({"request_number": self.network_requests, "attempt": attempt + 1,
                                          "error_type": kind, "physics_paused": True}) + "\n")
            self.audit.flush()
            if attempt + 1 < self.limit:
                self.sleep(min(5 * (attempt + 1), 30))
        # This is not a policy failure or a physical outcome. Driver retains the private journal.
        raise RuntimeError("API unavailable after bounded recovery attempts; keep slot unresolved")

    def close(self):
        self.client.close()


def recover(root, data, original_job, slot, output):
    from jev_vla_sim.mujoco_backend import MujocoBackend

    episode = data / slot["episode"]
    entries = prefix_responses(episode)
    original_count = len(entries)
    last = json.loads((episode / "steps.jsonl").read_text().splitlines()[-1]).get("exchange", {})
    pending = next((last[k]["request"] for k in ("intent", "motor")
                    if k in last and "request" in last[k] and "response" not in last[k]), None)
    folder = output / f"slot-{slot['id']}"
    folder.mkdir(parents=True, exist_ok=True)
    journal_path = folder / "received.jsonl"
    if journal_path.exists():
        entries += [json.loads(line) for line in journal_path.read_text().splitlines() if line.strip()]
    if len(entries) > original_count:
        pending = None
    profile = slot.get("observation_profile", "legacy")
    config_key = slot["task"] + ("-full_geometry" if profile == "full_geometry" else "")
    cfg = Config(**original_job["configs"][config_key])
    key, _ = Credentials(root, data / "private-config").resolve()
    if not key:
        raise RuntimeError("No configured API key")
    with journal_path.open("a", encoding="utf-8") as journal, (folder / "transport.jsonl").open("a") as audit:
        client = PersistentClient(entries, journal, audit, pending=pending)
        backend = MujocoBackend(cfg)
        backend.capture_state = True
        run = make_run(folder, cfg.to_dict(), {"capture_video_state": True, "resume_received_answers": True})
        metadata = json.loads((run / "metadata.json").read_text())
        if original_job["assets"] != backend.asset_manifest:
            raise RuntimeError("Assets changed")
        metadata.update(assets=backend.asset_manifest, renderer={"selected": "none"})
        write_json(run / "metadata.json", metadata)
        try:
            result = run_episode(backend, JevPolicy(cfg, client=client, api_key=key), cfg, run, "jev", slot["seed"], False)
            if client.position != len(entries):
                raise RuntimeError("Previously received answer prefix was not fully consumed")
            return {"result": result, "episode": str((run / result["episode_id"]).relative_to(data)),
                    "recovery": {"cached_stages": len(entries), "network_requests": client.network_requests,
                                 "transport_failures": client.transport_failures, "http_failures": client.http_failures,
                                 "original_episode": slot["episode"], "prefix_verified": True,
                                 "numeric_tolerance": 1e-9}}
        finally:
            backend.close()
            client.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("job", type=Path)
    p.add_argument("--output", type=Path, required=True, help="Directory within original campaign data root")
    p.add_argument("--slots", nargs="*")
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    job = json.loads(args.job.read_text())
    if job["source_sha256"] != source_fingerprint():
        raise RuntimeError("Use original frozen simulator/policy source")
    data = args.job.resolve().parent.parent
    output = args.output.resolve()
    if not output.is_relative_to(data):
        raise ValueError("Recovery output must be inside original data root")
    output.mkdir(parents=True, exist_ok=True)
    merged = json.loads(json.dumps(job))
    for slot in merged["slots"]:
        if args.slots is not None and slot["id"] not in args.slots:
            continue
        if slot["status"] != "completed" or outcome_category(slot["result"]) != "infrastructure_error":
            continue
        saved = output / f"recovered-{slot['id']}.json"
        if saved.exists():
            recovered = json.loads(saved.read_text())
        else:
            print(json.dumps({"recovering_slot": slot["id"], "task": slot["task"], "profile": slot["observation_profile"]}), flush=True)
            recovered = recover(root, data, job, slot, output)
            write_json(saved, recovered)
        slot.update(recovered)
        write_json(output / "job.json", merged)
        write_json(output / "summary.json", summary(merged))
        print(json.dumps({"slot": slot["id"], "end_reason": recovered["result"]["end_reason"], "recovery": recovered["recovery"]}), flush=True)
    write_json(output / "job.json", merged)
    write_json(output / "summary.json", summary(merged))


if __name__ == "__main__":
    main()
