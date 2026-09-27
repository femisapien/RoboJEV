"""Recovery must never resample received answers or substitute a different state."""
import importlib.util
import io
import json
from pathlib import Path

import httpx
import pytest

SPEC = importlib.util.spec_from_file_location("recovery", Path(__file__).parents[1] / "scripts/recover_observation.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_received_invalid_answer_is_preserved_and_not_retried():
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(200, content=b"not-json")

    journal = io.StringIO()
    c = module.PersistentClient([], journal, io.StringIO(), client=httpx.Client(transport=httpx.MockTransport(respond)))
    first = c.post("https://example.test", json={"state": 1}, headers={})
    assert first.content == b"not-json" and len(calls) == 1
    cached = module.PersistentClient([json.loads(journal.getvalue())], io.StringIO(), io.StringIO(),
                                     client=httpx.Client(transport=httpx.MockTransport(respond)))
    assert cached.post("https://example.test", json={"state": 1}, headers={}).content == first.content
    assert len(calls) == 1


def test_transport_retries_same_body_and_retains_prefix():
    bodies, delays = [], []

    def respond(request):
        bodies.append(request.content)
        if len(bodies) == 1:
            raise httpx.ReadError("synthetic disconnect")
        return httpx.Response(200, json={"answer": "new"})

    entries = [{"request": {"state": 0}, "response": {"answer": "saved"}, "status": 200}]
    c = module.PersistentClient(entries, io.StringIO(), io.StringIO(),
                                client=httpx.Client(transport=httpx.MockTransport(respond)), sleep=delays.append)
    assert c.post("https://example.test", json={"state": 0}, headers={}).json() == {"answer": "saved"}
    assert not bodies
    assert c.post("https://example.test", json={"state": 1}, headers={}).json() == {"answer": "new"}
    assert len(bodies) == 2 and bodies[0] == bodies[1] and delays == [5]


def test_recovery_rejects_state_drift_and_tolerates_only_float_roundoff():
    assert module.equivalent({"x": 1.0}, {"x": 1.0 + 1e-12})
    assert not module.equivalent({"x": 1.0}, {"x": 1.001})
    assert not module.equivalent({"choice": "positive"}, {"choice": "zero"})
    c = module.PersistentClient([{"request": {"seed": 1}}], io.StringIO(), io.StringIO())
    with pytest.raises(RuntimeError, match="mismatch"):
        c.post("https://example.test", json={"seed": 2}, headers={})
    c.close()


def test_exhausted_transport_remains_unresolved():
    def fail(request):
        raise httpx.ConnectError("synthetic outage")

    c = module.PersistentClient([], io.StringIO(), io.StringIO(),
                                client=httpx.Client(transport=httpx.MockTransport(fail)), sleep=lambda _: None, limit=2)
    with pytest.raises(RuntimeError, match="unresolved"):
        c.post("https://example.test", json={}, headers={})
    assert c.network_requests == c.transport_failures == 2


def test_mesh_distance_replay_exception_never_ignores_robot_pose():
    a = {"state": {"robot": {"position": [0.1]}, "spatial_geometry": {"current_signed_distances": [0.109]}}}
    b = {"state": {"robot": {"position": [0.1]}, "spatial_geometry": {"current_signed_distances": [0.0]}}}
    assert module.physical_equivalent(a, b)
    b["state"]["robot"]["position"] = [0.2]
    assert not module.physical_equivalent(a, b)
    assert a["state"]["spatial_geometry"]["current_signed_distances"] == [0.109]


@pytest.mark.parametrize("status", [401, 402, 403])
def test_account_failures_stop_without_retry_or_scoring(status):
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(status, json={"detail": "synthetic account error"})
    journal, audit = io.StringIO(), io.StringIO()
    c = module.PersistentClient([], journal, audit,
                                client=httpx.Client(transport=httpx.MockTransport(respond)))
    with pytest.raises(module.ServiceBlocked) as failure:
        c.post("https://example.test", json={}, headers={})
    assert failure.value.status == status and len(calls) == 1
    assert journal.getvalue() == "" and json.loads(audit.getvalue())["operator_action_required"]
