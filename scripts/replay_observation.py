"""Verify received JEV answers and physical outcomes offline; never add new samples."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import httpx
from recover_observation import equivalent, physical_equivalent, prefix_responses

from jev_vla_sim.config import Config
from jev_vla_sim.policy import JevPolicy
from jev_vla_sim.recording import make_run, source_fingerprint, write_json
from jev_vla_sim.runner import run_episode
from robojev_ui.reports import EVALUABLE, outcome_category


class OfflineClient:
    """No network transport exists. Request drift or trace exhaustion fails verification."""

    def __init__(self, entries):
        self.entries, self.position = entries, 0

    def post(self, url, *, json, headers):
        if self.position >= len(self.entries):
            raise RuntimeError("Offline trace exhausted; no network fallback")
        entry = self.entries[self.position]
        if not physical_equivalent(entry["request"], json):
            raise RuntimeError(f"Offline request/state mismatch at stage {self.position}")
        self.position += 1
        return httpx.Response(entry["status"], json=entry["response"])


def replay_slot(data, job, slot, output):
    from jev_vla_sim.mujoco_backend import MujocoBackend

    original = slot["result"]
    episode = data / slot["episode"]
    profile = slot.get("observation_profile", "legacy")
    key = slot["task"] + ("-full_geometry" if profile == "full_geometry" else "")
    cfg = Config(**job["configs"][key])
    client = OfflineClient(prefix_responses(episode))
    backend = MujocoBackend(cfg)
    run = make_run(output / str(slot["id"]), cfg.to_dict(), {"offline_verification": True})
    try:
        if job["assets"] != backend.asset_manifest:
            raise RuntimeError("Offline replay assets differ")
        # Same episode ID is needed to verify the frozen request/state sequence.
        result = run_episode(backend, JevPolicy(cfg, client=client, api_key="offline-no-transport"),
                             cfg, run, "jev", slot["seed"], False)
        fields = ("success", "end_reason", "decisions", "executed", "rejected", "simulation_time_s",
                  "tracking_timeouts", "final_measurements")
        mismatches = [k for k in fields if not equivalent(original.get(k), result.get(k))]
        if client.position != len(client.entries):
            mismatches.append("unconsumed_responses")
        # Check every executed physical transition, including the final one.
        def transitions(path):
            return [r["next_state"] for r in map(json.loads, path.read_text().splitlines())
                    if r.get("event") == "execution"]
        if not physical_equivalent(transitions(episode / "steps.jsonl"),
                          transitions(run / result["episode_id"] / "steps.jsonl")):
            mismatches.append("physical_states")
        return {"slot": slot["id"], "task": slot["task"], "observation_profile": profile, "seed": slot["seed"],
                "verified": not mismatches, "mismatches": mismatches, "network_requests": 0,
                "stages": client.position, "numeric_tolerance": 1e-9,
                "derived_mesh_distance_features": "original observations replayed; physical poses independently verified",
                "trace_sha256": hashlib.sha256((episode / "steps.jsonl").read_bytes()).hexdigest(),
                "success": result["success"], "end_reason": result["end_reason"]}
    finally:
        backend.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("job", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    job = json.loads(args.job.read_text())
    if job["source_sha256"] != source_fingerprint():
        raise RuntimeError("Use frozen source for replay")
    data = args.job.resolve().parent.parent
    args.output.mkdir(parents=True, exist_ok=True)
    records = []
    for slot in job["slots"]:
        if slot["status"] != "completed" or outcome_category(slot["result"]) not in EVALUABLE:
            continue
        item = replay_slot(data, job, slot, args.output)
        records.append(item)
        print(json.dumps(item), flush=True)
        write_json(args.output / "replay.json", {"job_id": job["id"], "records": records,
                                                "network_requests": 0, "independent_new_trials": 0})
    if any(not r["verified"] for r in records):
        raise SystemExit("Offline verification mismatch; do not publish unverified results")


if __name__ == "__main__":
    main()
