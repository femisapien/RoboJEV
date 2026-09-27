import copy
import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("resilient_export", Path(__file__).parents[1] / "scripts/export_resilient_observation.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def campaign():
    tasks = ["obstacle_pick_place", "double_gate_pick_place"]
    slots = []
    for task in tasks:
        for seed in range(10):
            for profile in ("legacy", "full_geometry"):
                win = profile == "full_geometry"
                slots.append({"id": str(len(slots)), "task": task, "policy": "jev", "seed": seed,
                              "observation_profile": profile, "status": "completed",
                              "transport": {"network_requests": 2, "transport_failures": 0, "http_retries": 0},
                              "result": {"task": task, "policy": "jev", "seed": seed, "success": win,
                                         "end_reason": "success" if win else "policy_error",
                                         "failure": {"detail": "invalid TypeSafe choice response; no action executed"}}})
    job = {"id": "test", "source_sha256": "test", "transport_protocol": {}, "slots": slots,
           "spec": {"comparison": "observation", "tasks": tasks, "seed": 0, "count": 10}}
    replay = {"job_id": "test", "records": [{"slot": s["id"], "verified": True, "network_requests": 0} for s in slots]}
    return job, replay


def test_response_validation_failures_stay_in_paired_denominator():
    job, replay = campaign()
    result = module.export(job, replay)
    assert all(g["completed"] == 10 and g["evaluable"] == 10 for g in result["groups"])
    assert result["paired_comparisons"][0]["exact_mcnemar_two_sided_p"] == 2 / 1024
    assert result["independent_trials"] == 40 and result["offline_independent_new_trials"] == 0


def test_transport_missing_and_bad_replay_cannot_be_published_as_complete():
    job, replay = campaign()
    broken = copy.deepcopy(job)
    broken["slots"][0]["result"]["failure"]["detail"] = "TypeSafe transport error; no action executed"
    with pytest.raises(ValueError, match="infrastructure"):
        module.export(broken, replay)
    replay["records"][0]["verified"] = False
    with pytest.raises(ValueError, match="verification"):
        module.export(job, replay)
    replay["records"].pop()
    with pytest.raises(ValueError, match="Missing"):
        module.export(job, replay)


def test_transport_audit_separates_account_blocks_and_reconciles_attempts(tmp_path):
    folder = tmp_path / "trials" / "0"
    folder.mkdir(parents=True)
    (folder / "received.jsonl").write_text('\n'.join(json.dumps({"status": s}) for s in (402, 200)))
    (folder / "transport.jsonl").write_text('\n'.join(json.dumps({"error_type": s})
                                                    for s in ("ConnectError", "HTTP_503", "HTTP_402")))
    job = {"slots": [{"id": "0", "transport": {"network_requests": 5}}]}
    result = module.transport_audit(tmp_path / "job.json", job)
    assert result["account_block_attempts"] == 2
    assert result["transient_http_attempts"] == 1
    assert result["transport_error_types"] == {"ConnectError": 1}
    assert result["http_status_counts"] == {"402": 2, "200": 1, "503": 1}
    job["slots"][0]["transport"]["network_requests"] = 4
    with pytest.raises(ValueError, match="reconcile"):
        module.transport_audit(tmp_path / "job.json", job)
