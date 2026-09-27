# Observation input ablation

The normal RoboJEV input is the legacy structured state. It is the default in the CLI, configuration files and local console. The full-geometry input is an opt-in simulator-only ablation because complete link geometry and signed distances are difficult to obtain from a physical robot.

The September 27, 2026 campaign is complete: all 40 fixed slots have evaluable outcomes and all 40 traces passed offline verification with zero network requests. See the [paired results, failure evidence and six original-trial videos](observation-evaluation.md). No success-rate improvement was observed. The [September 23 experiment](observation-evaluation-20260923.md) is a separate archive and is not pooled with these results.

Run the paired campaign from a configured Linux checkout. The [recovery protocol](observation-recomparison.md) freezes physics during transport retries and preserves every received answer:

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python scripts/evaluate_resilient_observation.py --workers 2 --data runs/observation-comparison
# After restoring an interrupted service, resume the same campaign:
python scripts/evaluate_resilient_observation.py --resume runs/observation-comparison/JOB_ID/job.json
python scripts/replay_observation.py runs/observation-comparison/JOB_ID/job.json \
  --output runs/observation-comparison/offline
python scripts/export_resilient_observation.py runs/observation-comparison/JOB_ID/job.json \
  runs/observation-comparison/offline/replay.json --output artifacts/observation-comparison/report.json
python scripts/analyze_observation.py runs/observation-comparison/JOB_ID/job.json \
  --output artifacts/observation-comparison --render
```

The campaign has 40 fixed slots: the existing single gate and the staggered double gate, each with seeds 0–9 under both `legacy` and `full_geometry` observations. Each seed receives both profiles in alternating order. The physics configuration, task layout, action interface, failure boundaries and JEV model are shared. Every evaluable success or failure is retained. Unanswered requests are resumed from the same state under physical checks; interrupted seeds are not rerolled to obtain a different trajectory. The console's comparison preset configures these paired scenes; use the script above for this campaign's same-request transport recovery.

`full_geometry` adds all robot collision parts, conservative part OBBs, joint and body poses, explicit gate geometry, and signed distances computed from MuJoCo collision geometry. It does not provide candidate-action collision predictions or select an action. The public report includes payload size; cached-prefix timings after resumption are not presented as pure inference latency or total task cost. Raw exchanges, credentials and token usage remain private.

Reports include same-seed pairs, failure boundaries, last actions, rejection runs, contact reconstruction, and up to eight natural demonstration videos. Missing success or failure outcomes are recorded as unavailable; no trial is replaced to manufacture a video.

Transport and HTTP service errors remain separate from physical task failures and model-response validation errors. The final comparison cannot be published as complete until all 40 prespecified slots have evaluable outcomes and pass offline verification. The denominator is always ten slots per task/profile, including every response-validation failure. HTTP 401/402/403 requires service restoration and is audited separately from transient HTTP or transport retries. Offline replay adds no independent samples. Ten pairs per task do not establish general superiority or equivalence.

The generic analyzer chooses the lowest-seed task failure, then a response-validation failure, then another error. The final report explicitly uses the lowest-seed collision for its failure videos to illustrate measured contact boundaries; all budget failures remain in the tables and evidence. Success videos use the lowest successful seed. The video manifest records this selection and the source hashes. A missing success is stated as unavailable, without borrowing a video from an older campaign.
