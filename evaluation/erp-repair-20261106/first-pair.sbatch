#!/bin/bash
#SBATCH --job-name=aea-r2-first-pair
#SBATCH --partition=batch
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:05:00
#SBATCH --output=/home/hou/Research/auto-eeg-analysis/review-stage/aea-erp-repair-20261106/logs/first-pair-%j.out
#SBATCH --error=/home/hou/Research/auto-eeg-analysis/review-stage/aea-erp-repair-20261106/logs/first-pair-%j.err
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
stage=/home/hou/Research/auto-eeg-analysis/review-stage/aea-erp-repair-20261106
cd "$stage"
curl --connect-timeout 5 --max-time 15 -fsS https://api.ipify.org > "$stage/launch/worker01-egress-$SLURM_JOB_ID.txt"
srun --cpu-bind=threads /home/hou/miniconda3/bin/python -B -u "$stage/verify_allocation.py"
srun --cpu-bind=threads /home/hou/miniconda3/bin/python -B -c "import runpy; runpy.run_path('$stage/launch/run_first_pair.py', run_name='__mp_main__'); print('SPAWN_IMPORT_ONLY_PASSED')"
srun --cpu-bind=threads /home/hou/miniconda3/bin/python -B -u "$stage/launch/run_first_pair.py"
