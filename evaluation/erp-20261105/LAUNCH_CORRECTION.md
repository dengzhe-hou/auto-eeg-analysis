# Runtime-path correction before the first model request

The initial formal submission stopped on a shared infrastructure error on
2026-11-05. Two assigned group sessions failed before any model request or
execute action: `erp_P3b_group / without_aea / rep3` and
`erp_N400_group / with_aea / rep1`. Both recorded zero API attempts and zero cost.
Other workers honored the shared admission stop. No scientific delivery was
produced and no failed scientific answer was replaced.

The run directory had been moved from system temporary storage into the deep
session directory. Jupyter's IPC socket address then failed with `File name too
long`. The correction uses short, unique directories under this study's `rt/`
directory. First-attempt directories, logs and the original admission-stop
record are retained on the server. A direct IPC bind checks the corrected path
before the controlled retry.

Only runtime path handling changed relative to freeze commit 95a24a6. Inputs,
requests, resource version, prompts, reference outputs, primary and secondary
endpoints, tolerances, model parameters, assignment order and budget are unchanged.
The original 144 logical assignments are retained; infrastructure attempts are
reported separately. This commit records the implementation correction before
any paid model request in the formal study.
