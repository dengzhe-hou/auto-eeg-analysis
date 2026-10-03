# REPRO_RECEIPT — eegbci-resting

> Historical receipt. The date, commit, environment, results, hashes, and original
> commands below are retained from the 2026-06-19 analysis. The recorded commit
> `07c582ffcc3d984a147a693fc29be15edafc3c56` remains in the private history archive;
> it is not reachable from the clean public repository. It records the repository
> HEAD at the time, but does not contain this validation script or its results;
> those files were committed subsequently in `672db5d`. See the current release
> instructions at the end of this receipt.

> Generated: 2026-06-19 11:43

## AEA version
- Commit: `07c582ffcc3d984a147a693fc29be15edafc3c56`

## Environment (introspected)
- Python: 3.11.15  ·  OS: Linux 6.12.0-124.55.3.el10_1.x86_64
- MNE-Python: 1.12.1  ·  mne-icalabel: 0.9.0  ·  pycrostates: 0.6.1
- antropy: 0.2.2  ·  specparam: 2.0.0rc7  ·  scikit-learn: 1.8.0
- NumPy: 2.4.6  ·  SciPy: 1.17.1

## RNG seeds
| Stage | Seed |
|-------|------|
| ICA | 42 |
| ModKMeans | 42 |
| cluster | 42 |

## Claims
- C1 EC>EO posterior alpha: t=3.60 p=0.0019, spatial cluster p=0.0002 (N=20)
- C2 EO>EC complexity: LZC p=4.2e-5 dz=1.18, PE p=2.0e-7
- C3 microstates K=4: GEV=0.66, duration median=103ms

## File hashes (SHA256 prefix)
| File | Hash |
|------|------|
| `figure-stage/F1_resting_validation.png` | `903d0244f7254526` |
| `tools/validation/resting_results.json` | `da3240a3349de860` |

## Original reproduction commands (historical)
```bash
git clone https://github.com/dengzhe-hou/auto-eeg-analysis
git checkout 07c582ffcc3d984a147a693fc29be15edafc3c56
conda env create -f environment.yml && conda activate aeais
pip install -r requirements-optional.txt   # complexity/specparam/microstate extras
bash tools/env/check_env.sh
python tools/validation/validate_resting_recipes.py --subjects 20
```

## Run from the public v0.3.2 release

The public release retains the validation script and recorded result JSON. The
command below uses the same dataset, subjects, and scientific configuration as
the original command. This analysis was not rerun for the public release; the
results above remain the historical results, not a new v0.3.2 run. Review the
recorded environment above when comparing a new run with those results.

```bash
git clone https://github.com/dengzhe-hou/auto-eeg-analysis
cd auto-eeg-analysis
git checkout v0.3.2
conda env create -f environment.yml && conda activate aeais
pip install -r requirements-optional.txt
bash tools/env/check_env.sh
python tools/validation/validate_resting_recipes.py --subjects 20 --out projects/eegbci-resting/reproduction/resting_results.json
```

The new run writes its results and figure under `projects/eegbci-resting/reproduction/`,
leaving the committed historical outputs intact.
