#!/bin/bash
#SBATCH --job-name=aea-erp-single
#SBATCH --partition=batch
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=01:05:00
#SBATCH --array=0-2%2
#SBATCH --output=/home/hou/Research/auto-eeg-analysis/review-stage/aea-erp-validation-20261101/logs/formal-single-%A_%a.out
#SBATCH --error=/home/hou/Research/auto-eeg-analysis/review-stage/aea-erp-validation-20261101/logs/formal-single-%A_%a.err
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
cd /home/hou/Research/auto-eeg-analysis
/home/hou/miniconda3/bin/python -B -u /home/hou/Research/auto-eeg-analysis/review-stage/aea-erp-validation-20261101/verify_allocation.py
/home/hou/miniconda3/bin/python -B -u /home/hou/Research/auto-eeg-analysis/review-stage/aea-erp-validation-20261101/controller.py --phase formal --kind single_subject --shards 3 --shard "$SLURM_ARRAY_TASK_ID"
