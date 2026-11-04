# AEA ERP paired-validation public freeze

This commit freezes the approved plan and resources on 2026-11-05 before the first formal session. The user explicitly authorized public freezing and formal execution. It contains no formal-run results.

The approved design remains 24 requests, two resource conditions and three
repetitions (144 formal sessions), using Haiku 5.5 and the original 12 USD cap.
The four completed access pilots are separate. Current estimated spend is
0.1624612 USD, leaving 11.8375388 USD under the original ceiling; the existing
formal cost forecast is 5.20488 USD. These are usage estimates, not invoices.

The primary endpoint is unchanged. Single-subject answers use the approved
0.1 microvolt amplitude tolerance; group answers use the approved direction,
t-test significance and cluster significance comparisons. Group mean amplitude
agreement remains in the complete-contract secondary endpoint. The approved
processing details and both arms' settings remain unchanged.

The resource version remains aea-erp-r1-20261101. It includes tools/validation
and tools/benchmark inherited from r3, including reference-computation scripts;
the proposal to remove these has not been adopted. Their use is recorded from
execution traces. Formal reference outputs and answer values are excluded from
this candidate and are not given to agents. The candidate does not imply that
the treatment isolates the skill format independently of its software content.

The full original EXPERIMENT_PLAN.md and draft protocol are retained for
chronology. This document records execution of their approved defaults without
adopting the four proposed design/publication changes in DECISIONS.json. The user authorized an independent GitHub freeze branch on 2026-11-05. No DOI is claimed.

The candidate includes the plan, the 24 requests and their public contracts,
the 144-session proposed schedule, selected procedure packets, the original r1
resource ZIP, grader and analysis code, and execution parameters. Raw EEG,
private reference outputs, model credentials and account configuration are not
included. Original local paths in source identify the historical environment;
they are not an assurance of portable execution.

Implementation corrections before formal launch stop admission after a shared
infrastructure failure, retain the first failure record, keep session runtime
files under the study, and verify effective Slurm process-tree CPU/memory limits.
These do not change scientific inputs, endpoints or scoring.

The original session ceilings remain 1200 seconds, 2 CPUs, 8 GiB for individual
requests and 16 GiB for group requests, identical in both arms. Scheduler wall
limits are 65 minutes per individual shard and 45 minutes per group shard,
with at most two individual and two group workers. There are three individual
shards and two group shards; all 144 assignments remain. Times use 1.5 times
the slowest completed pilot of each kind across each shard's assignments, plus
startup/grading allowance. GPU allocation is zero. Queue time is additional.

Worker-specific outbound IP mappings have not been verified; no claim of four
independent IPs is made. Existing provider and permission settings are retained.
