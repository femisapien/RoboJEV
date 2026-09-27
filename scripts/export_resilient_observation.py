"""Export aggregate paired statistics only after every slot has an evaluable outcome."""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

from jev_vla_sim.recording import write_json
from robojev_ui.reports import EVALUABLE, outcome_category, summary


def transport_audit(job_path, job):
    """Read private journals, returning only counts and never request/response content."""
    statuses, errors = Counter(), Counter()
    for slot in job["slots"]:
        folder = job_path.parent / "trials" / slot["id"]
        for line in (folder / "received.jsonl").read_text().splitlines():
            statuses[str(json.loads(line)["status"])] += 1
        for line in (folder / "transport.jsonl").read_text().splitlines():
            kind = json.loads(line)["error_type"]
            if kind.startswith("HTTP_"):
                statuses[kind.removeprefix("HTTP_")] += 1
            else:
                errors[kind] += 1
    attempts = sum(statuses.values()) + sum(errors.values())
    if attempts != sum(s["transport"]["network_requests"] for s in job["slots"]):
        raise ValueError("Private transport audit does not reconcile with recorded request totals")
    return {"http_status_counts": dict(statuses), "transport_error_types": dict(errors),
            "account_block_attempts": sum(statuses[s] for s in ("401", "402", "403")),
            "transient_http_attempts": sum(statuses[str(s)] for s in (429, 500, 502, 503, 504, 529)),
            "network_requests": attempts}


def export(job, replay, audit=None):
    if len(job["slots"]) != 40 or any(s["status"] != "completed" for s in job["slots"]):
        raise ValueError("Require all 40 prespecified slots")
    if any(outcome_category(s["result"]) not in EVALUABLE for s in job["slots"]):
        raise ValueError("Unresolved infrastructure outcome; do not publish a completed comparison")
    if replay["job_id"] != job["id"]:
        raise ValueError("Replay campaign mismatch")
    checks = {r["slot"]: r for r in replay["records"]}
    if set(checks) != {s["id"] for s in job["slots"]}:
        raise ValueError("Missing offline verification")
    if any(not r["verified"] or r["network_requests"] for r in checks.values()):
        raise ValueError("Offline verification did not pass without network access")
    report = summary(job)
    for item in report["paired_comparisons"]:
        b, c = item["full_only_success"], item["legacy_only_success"]
        n = b + c
        item["exact_mcnemar_two_sided_p"] = min(1., 2 * sum(math.comb(n, k) for k in range(min(b, c)+1)) / 2**n) if n else 1.
        item["success_difference_pp"] = 100 * (b-c) / item["expected_pairs"]
    report.update(campaign="transport-resilient-observation-20260927", date="2026-09-27", job_id=job["id"],
                  transport_protocol=job["transport_protocol"], independent_trials=40, offline_independent_new_trials=0,
                  offline_verified=sum(r["verified"] for r in checks.values()), offline_expected=40,
                  offline_network_requests=sum(r["network_requests"] for r in checks.values()),
                  network_requests=sum(s["transport"]["network_requests"] for s in job["slots"]),
                  recovered_transport_errors=sum(s["transport"]["transport_failures"] for s in job["slots"]),
                  recorded_http_errors=sum(s["transport"]["http_retries"] for s in job["slots"]),
                  unresolved_transport_slots=0)
    if audit is not None:
        if audit["network_requests"] != report["network_requests"]:
            raise ValueError("Transport audit request count mismatch")
        report["transport_audit"] = audit
    report["denominators"] = "10 prespecified seeds per task and input. Transport retries pause physics at the same request. Physical and response-validation failures stay in the denominator. Offline replay adds no independent samples."
    report["interpretation"] = "Legacy remains the default. Full geometry is a simulator-only comparison. Ten paired seeds per task provide an exploratory estimate; report exact paired tests and do not assume improvement."
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("job", type=Path)
    p.add_argument("replay", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    job = json.loads(args.job.read_text())
    report = export(job, json.loads(args.replay.read_text()), transport_audit(args.job, job))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, report)


if __name__ == "__main__":
    main()
