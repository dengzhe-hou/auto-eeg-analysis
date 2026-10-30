# Public-data validation

This example uses [PhysioNet EEG Motor Movement/Imagery Dataset
1.0.0](https://physionet.org/content/eegmmidb/1.0.0/), participants S001–S005,
runs 04, 08 and 12. These runs contain imagined left and right fist movements.
The fifteen EDF files total **38,581,920 bytes**. No raw participant data are
included in this contribution. PhysioNet distributes them under the Open Data
Commons Attribution License v1.0. Cite Schalk (2009), DOI
[10.13026/C28G6P](https://doi.org/10.13026/C28G6P), and the source references in
`../citation.bib`.

## Reproduce

Run from the AEA repository root, using the project environment with
scikit-learn installed. The following commands download only the selected
files and evaluate the fixed configuration.

```bash
python recipes/motor-imagery-csp/analysis/download.py /path/to/eegbci
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLBACKEND=Agg \
  python recipes/motor-imagery-csp/analysis/run.py \
  --data /path/to/eegbci --output /path/to/new-results
```

Use a new output directory for an independent replay. Existing participant
records in an output directory are reused to resume an interrupted execution.
The program saves predictions, fold identities, scores, acquisition details,
the exact configuration and software versions. Generated figures are saved
alongside these results. The figures from the recorded execution are stored
in `../reference_figures/`.

The tested environment used Python 3.12.0, MNE 1.13.2, NumPy 2.2.6, SciPy
1.17.0, scikit-learn 1.8.0, pandas 2.3.3 and Matplotlib 3.11.2 on Linux x86-64.
BLAS and OpenMP were restricted to one thread. No GPU was used. The initial
analysis took 3.31 seconds after data download and environment setup. A CPU
with 2 GB available memory is sufficient for this bounded example; allow
additional storage for the Python environment. Dataset files remain below
40 MB.

## Recorded results, 2026-10-30

All 225 task events were retained, with no annotated or incomplete epochs
dropped. Each of the 15 runs contains 15 trials. Every test fold uses one
entire run, while the other two runs provide 30 training trials.

| Participant | Run 04 | Run 08 | Run 12 | Mean |
|---|---:|---:|---:|---:|
| S001 | 0.785714 | 0.473214 | 0.616071 | 0.625000 |
| S002 | 0.651786 | 0.526786 | 0.732143 | 0.636905 |
| S003 | 0.598214 | 0.491071 | 0.517857 | 0.535714 |
| S004 | 0.508929 | 0.401786 | 0.339286 | 0.416667 |
| S005 | 0.642857 | 0.732143 | 0.723214 | 0.699405 |

Values are held-out-run balanced accuracies. The mean of participant means
is **0.582738**, with sample standard deviation **0.109684**. The 0.5 chance
reference is descriptive. No p-value, population-level above-chance claim or
clinical interpretation is asserted. S004 and every below-chance run remain
in the results. Subject selection, model settings and preprocessing were not
changed after observing scores.

The largest discrepancy between the CSP features and independently computed
log mean-square projections was **5.28e-16**. Independent execution inside the
data-dependent regression test reproduced every event identity, count,
prediction and probability, with maximum probability difference **0.0**.
The stated 1e-6 absolute probability tolerance allows small library and BLAS
differences; exact predicted labels and counts are still required. It is a
regression tolerance for this configuration, not a scientific effect threshold.

## Tests actually run

The focused synthetic test confirms that the arrays supplied to every CSP fit
contain exactly the training runs and exclude the held-out run. It passed.
The full project suite was then run with the public-data directory set:

```bash
AEA_EEGBCI_MOTOR_IMAGERY=/path/to/eegbci \
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLBACKEND=Agg \
  python -m pytest tools/tests/ recipes/ -q -ra
```

**339 passed, 42 skipped, 2 warnings**, in 84.72 seconds. All three new recipe
tests passed, including the actual public EDF replay. Existing skips concern
unavailable MATLAB/EEGLAB integrations, the MNE sample and ERP CORE datasets,
and optional packages for unrelated analyses. They are not evidence that those
paths passed. Existing warnings concern a short synthetic signal in
`test_tfr_api` and the F-test tail argument in `test_group_compare_api`.

## Interpretation and remaining work

This is a complete numerical example of the declared offline CSP/LDA analysis,
with preserved low scores and all fold records. It is intentionally labelled
**experimental**, because independent methodological review has not occurred
and physiological specificity has not been established. No ICA, manual artifact
screening or channel repair was performed. The code follows a bounded published
CSP workflow, with the explicit deviations described in the recipe. It does
not claim execution of every generic AEA preprocessing or reporting stage.

The five-participant subset cannot establish generalization to new people,
clinical populations or online acquisition. It also cannot separate cortical
information from residual muscle or eye signals. A future inferential or
artifact-cleaned study requires a separately declared design and corresponding
validation rather than tuning this example until its scores improve.

Prepared by Haoyang Su, Fudan University and Shanghai Innovation Institute.
OpenAI Codex assisted with implementation, execution and reporting.
