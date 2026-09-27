import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


def test_billing_circuit_breaker_preserves_prior_success_and_validation_failure(tmp_path, monkeypatch):
    scripts = Path(__file__).parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("resilient_driver", scripts / "evaluate_resilient_observation.py")
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    slots = []
    for i in range(4):
        result = {"task": "obstacle_pick_place", "policy": "jev", "seed": i//2,
                  "success": i == 0, "end_reason": "success" if i == 0 else "policy_error",
                  "failure": {"detail": "invalid TypeSafe choice response; no action executed"}}
        slots.append({"id": str(i), "task": "obstacle_pick_place", "policy": "jev", "seed": i//2,
                      "observation_profile": "legacy" if i % 2 == 0 else "full_geometry",
                      "status": "completed" if i < 2 else "pending", "result": result if i < 2 else None,
                      "transport": {}, "episode": str(i)})
    job = {"id": "test", "slots": slots, "source_sha256": "test", "spec": {
        "comparison": "observation", "tasks": ["obstacle_pick_place"], "seed": 0, "count": 2}}
    original = copy.deepcopy(slots[:2])
    calls = []
    def blocked(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=3)
    monkeypatch.setattr(driver.subprocess, "run", blocked)
    path = tmp_path / "job.json"
    path.write_text(json.dumps(job))
    driver.run_pending(path, job, scripts.parent, workers=1)
    assert job["slots"][:2] == original
    assert len(calls) == 1 and calls[0][-1] == "2"
    assert job["status"] == "blocked_service"
    assert all(s["status"] == "blocked" for s in job["slots"][2:])
