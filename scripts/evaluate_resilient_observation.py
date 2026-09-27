"""Paired comparison with transport recovery from the FIRST request, not a reroll."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from recover_observation import PersistentClient, ServiceBlocked

from jev_vla_sim.config import Config
from jev_vla_sim.policy import JevPolicy
from jev_vla_sim.recording import make_run, source_fingerprint, write_json
from jev_vla_sim.runner import run_episode
from robojev_ui.credentials import Credentials
from robojev_ui.models import Experiment
from robojev_ui.reports import EVALUABLE, outcome_category, summary


def save_job(path, job):
    temporary = path.with_suffix(".tmp")
    write_json(temporary, job)
    temporary.replace(path)


def trial(job_path, slot_id):
    from jev_vla_sim.mujoco_backend import MujocoBackend

    root = Path(__file__).resolve().parents[1]
    job = json.loads(job_path.read_text())
    if source_fingerprint() != job["source_sha256"]:
        raise RuntimeError("Source changed during experiment")
    slot = job["slots"][slot_id]
    folder = job_path.parent / "trials" / str(slot_id)
    folder.mkdir(parents=True, exist_ok=True)
    cfg = Config(**job["configs"][Experiment.config_key(slot["task"], slot["observation_profile"])])
    backend = MujocoBackend(cfg)
    backend.capture_state = True
    key, _ = Credentials(root, folder / "private").resolve()
    if not key or backend.asset_manifest != job["assets"]:
        raise RuntimeError("Missing key or assets changed")
    run = make_run(folder, cfg.to_dict(), {"capture_video_state": True, "transport_resilient": True})
    metadata = json.loads((run / "metadata.json").read_text())
    metadata.update(assets=backend.asset_manifest, renderer={"selected": "none"},
                    numeric_threads={k: os.environ.get(k) for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS")})
    write_json(run / "metadata.json", metadata)
    try:
        received_path, audit_path = folder / "received.jsonl", folder / "transport.jsonl"
        previous = [json.loads(line) for line in received_path.read_text().splitlines()] if received_path.exists() else []
        previous_errors = [json.loads(line) for line in audit_path.read_text().splitlines()] if audit_path.exists() else []
        # HTTP service rejections are not model answers. Previously received 200s, including
        # invalid answers, must be consumed in their original order without another API call.
        entries = [r for r in previous if r["status"] == 200]
        prior_requests = len(previous) + len(previous_errors)
        with received_path.open("a") as journal, audit_path.open("a") as audit:
            client = PersistentClient(entries, journal, audit)
            try:
                result = run_episode(backend, JevPolicy(cfg, client=client, api_key=key), cfg, run, "jev", slot["seed"], False)
                if client.position != len(entries):
                    raise RuntimeError("Cached prefix not fully consumed; preserve original outcome")
                result["api_requests"] = prior_requests + client.network_requests
                write_json(run / result["episode_id"] / "result.json", result)
                transport = {"network_requests": result["api_requests"],
                             "transport_failures": client.transport_failures + sum(not e["error_type"].startswith("HTTP_") for e in previous_errors),
                             "http_retries": client.http_failures + sum(e["error_type"].startswith("HTTP_") for e in previous_errors)
                                 + sum(r["status"] != 200 for r in previous),
                             "physics_paused_during_retries": True, "cached_stages_on_resume": len(entries)}
                write_json(folder / "completed.json", {"result": result, "transport": transport,
                           "episode": str((run / result["episode_id"]).relative_to(job_path.parent.parent))})
            finally:
                client.close()
    finally:
        backend.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, default=Path("runs/resilient-observation"))
    p.add_argument("--workers", type=int, choices=(1, 2), default=2)
    p.add_argument("--trial", type=Path)
    p.add_argument("--slot", type=int)
    p.add_argument("--resume", type=Path, help="Existing job.json; retain all evaluable outcomes and received answers")
    args = p.parse_args()
    if args.trial:
        try:
            trial(args.trial, args.slot)
        except ServiceBlocked as exc:
            print(json.dumps({"blocked_http_status": exc.status}), flush=True)
            raise SystemExit(3) from None
        return
    root = Path(__file__).resolve().parents[1]
    if args.resume:
        job_path = args.resume.resolve()
        job = json.loads(job_path.read_text())
        if job["source_sha256"] != source_fingerprint():
            raise RuntimeError("Source changed; do not resume frozen campaign")
        folder = job_path.parent
        job["status"] = "running"
        save_job(job_path, job)
        run_pending(job_path, job, root, args.workers)
        return
    spec = Experiment(name="Transport-resilient paired observation comparison", mode="batch", policy="jev",
                      comparison="observation", seed=0, count=10, tasks=["obstacle_pick_place", "double_gate_pick_place"],
                      workers=args.workers, capture=True, defer_render=True)
    folder = args.data.resolve() / uuid.uuid4().hex
    folder.mkdir(parents=True)
    job = {"id": folder.name, "created": datetime.now(timezone.utc).isoformat(), "status": "running",
           "spec": spec.model_dump(), "configs": {k: v.to_dict() if hasattr(v, "to_dict") else v
                for k, v in spec.configurations().items()}, "source_sha256": source_fingerprint(),
           "assets": json.loads((root / "assets/panda/manifest.json").read_text()),
           "transport_protocol": {"timeout_s": 60, "attempt_limit": 20, "backoff_s": "5,10,...,30",
                                  "restart_completed_or_invalid_answer": False},
           "slots": [{"id": str(i), "task": t, "policy": policy, "seed": seed, "observation_profile": profile,
                      "status": "pending", "result": None, "attempt": 1, "video_status": "pending"}
                     for i, (t, policy, seed, profile) in enumerate(spec.trial_slots())]}
    job_path = folder / "job.json"
    for name, cfg in job["configs"].items():
        write_json(folder / f"{name}.json", cfg)
    save_job(job_path, job)
    print(json.dumps({"job_id": job["id"], "slots": len(job["slots"])}), flush=True)
    run_pending(job_path, job, root, args.workers)


def run_pending(job_path, job, root, workers):
    folder = job_path.parent
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", PYTHONUNBUFFERED="1")
    blocked = threading.Event()
    def execute(slot_id):
        slot = job["slots"][slot_id]
        if slot.get("result") and outcome_category(slot["result"]) in EVALUABLE:
            return slot_id, 0, {k: slot[k] for k in ("result", "transport", "episode")}
        if blocked.is_set():
            return slot_id, 3, None
        out = folder / "trials" / str(slot_id)
        out.mkdir(parents=True, exist_ok=True)
        with (out / "process.log").open("a") as log:
            proc = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--trial", str(job_path),
                                   "--slot", str(slot_id)], cwd=root, env=env, stdout=log, stderr=log)
        if proc.returncode == 3:
            blocked.set()
        result_path = out / "completed.json"
        return slot_id, proc.returncode, json.loads(result_path.read_text()) if result_path.exists() else None
    # A pair shares one worker, so both profile orders remain as specified.
    def pair(ids):
        return [execute(i) for i in ids]
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        pending = {pool.submit(pair, range(i, i + 2)): i for i in range(0, len(job["slots"]), 2)}
        for future in concurrent.futures.as_completed(pending):
            for i, code, completed in future.result():
                slot = job["slots"][i]
                if completed is not None and code == 0:
                    slot.update(completed, status="completed")
                else:
                    slot.update(status="blocked" if code == 3 else "unresolved", exit_code=code)
                print(json.dumps({"slot": i, "status": slot["status"], "end_reason": (slot.get("result") or {}).get("end_reason")}), flush=True)
            save_job(job_path, job)
            write_json(folder / "summary.json", summary(job))
    job["status"] = ("completed" if all(s["status"] == "completed" for s in job["slots"])
                     else "blocked_service" if blocked.is_set() else "unresolved")
    save_job(job_path, job)
    write_json(folder / "summary.json", summary(job))


if __name__ == "__main__":
    main()
