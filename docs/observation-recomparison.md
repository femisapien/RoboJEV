# Spatial-input comparison with recoverable API transport

The September 27 campaign repeats the single-gate and staggered-double-gate tasks with seeds 0–9 under both `legacy` and `full_geometry` (40 slots, 20 paired scenes). It is separate from the September 23 comparison and the five-task 100-episode evaluation. Legacy remains the normal default; full geometry is privileged simulator information used only for this comparison.

Completed results: single gate 3/10 legacy versus 2/10 full geometry; staggered double gate 0/10 for both. All 40 traces passed offline verification without network requests. There were 113 recovered transport errors and 38 pre-recharge HTTP 402 account blocks; no unresolved slot remains. See the [final report](observation-evaluation.md) for paired statistics, all failure boundaries and six original-trajectory videos. The result does not demonstrate a success-rate improvement.

## Fixed experimental conditions

Both profiles use the same seeds, scene generator, physics, controller, task prompts, model version, action size, and decision limits. Profile order alternates by seed. Two workers process independent pairs; each pair runs its profiles sequentially. Numerical threads are fixed to one. No prompt or controller tuning is performed using the new outcomes. Every received model answer is retained, including invalid answers. Collisions, decision-budget exhaustion, and model-response validation failures remain failures; they are never rerun to obtain a better outcome.

## Separate transport from task outcomes

The final campaign uses `scripts/evaluate_resilient_observation.py`, with the resilient HTTP client in `scripts/recover_observation.py`, from its very first request. No simulator state is reconstructed between API attempts. Exploratory attempts with the old transport and cross-environment continuation are archived separately and are not pooled with this campaign. Those attempts exposed state-reconstruction mismatches; they were not accepted as equivalent trials.

Replay preserves the originally observed mesh-distance features. During verification, a MuJoCo mesh-distance query changed from 0.109045 m to zero despite underlying pose differences of about 1e-15. These derived distances are therefore excluded from recomputation equality; robot/body/joint poses, obstacles, actions, and other state fields remain checked. This is a limitation of distance-feature reproducibility, not evidence of additional physical motion. New decisions still receive the measurements from their actual running simulator.

At an unanswered stage, physics is paused while the same request is retried. Successful HTTP responses are journaled privately before policy validation; malformed or invalid answers are not resampled. Each request allows at most 20 transport/service attempts with bounded backoff. If the service remains unavailable, the slot stays unresolved and its journal remains available for a later continuation. Authentication errors are not treated as recoverable network outages.

HTTP 401/402/403 stops the campaign and leaves unfinished slots unresolved. After the operator restores service, `--resume JOB_ID/job.json` preserves every evaluable success/failure, replays received answers for interrupted slots under physical-state checks, and continues only unanswered requests. It must stop on state divergence; it cannot silently restart a seed to obtain a new trajectory.

Both profiles allow 60 seconds per HTTP attempt. Those transport settings do not change the task, prompt, action, or physical time budget. Actual HTTP requests and transport failures are recorded separately. A request interrupted before the client receives a response may still have incurred provider-side processing or cost.

## Offline verification is not another experiment

`scripts/replay_observation.py` uses a client with no network transport. It reconstructs each physical state, returns its saved JEV answer, reruns policy validation and physics, and checks the terminal result and every recorded physical transition. Discrete physical values must match exactly; continuous values allow `1e-9` absolute/relative floating-point tolerance. Response-validation failures remain validation failures. All replay checks use the frozen simulator/policy source and verified robot assets. Numerical thread settings must be consistent with the captured trajectory. Replay divergence must be reported rather than counted as a passing verification.

Replaying one trace many times does not add independent evidence. The sample size remains 10 paired seeds per task. The main comparison counts successes among all 10 slots per profile once transport is resolved, retaining response-validation failures. A purely physical subset may be described separately but cannot replace that denominator. Report paired discordant outcomes and uncertainty, including a negative or inconclusive result; the purpose is to test whether full geometry helps, not to force a positive conclusion.

## Reproduction

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python scripts/evaluate_resilient_observation.py --workers 2 --data runs/observation-recomparison
# After restoring account credits/connectivity, if the campaign was blocked:
python scripts/evaluate_resilient_observation.py --resume runs/observation-recomparison/JOB_ID/job.json
python scripts/replay_observation.py runs/observation-recomparison/JOB_ID/job.json \
  --output runs/observation-recomparison/offline
python scripts/export_resilient_observation.py runs/observation-recomparison/JOB_ID/job.json \
  runs/observation-recomparison/offline/replay.json --output artifacts/observation-recomparison/report.json
```

Keep raw request/response journals and full run directories private. Publish aggregate counts, failure boundaries, provenance hashes, and selected original-trajectory recordings only after the campaign and verification finish. The existing page layout and five-task results remain unchanged.
