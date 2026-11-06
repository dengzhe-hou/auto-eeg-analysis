"""Inventory supported analysis outputs without assuming every study has ERPs."""
from pathlib import Path


STAGE_DIRECTORIES = {name: f'{name}-stage' for name in (
    'bids', 'preprocess', 'ica', 'epoch', 'erp', 'tfr', 'spectral', 'connectivity',
    'complexity', 'microstate', 'source', 'decoding', 'behavior', 'qc', 'stats', 'figure')}


def collect_stage_inputs(run_dir, *, planned_stages, required_sources):
    """Use stage/source declarations from the approved plan and execution ledger.

    required_sources maps each planned stage to its actual relative file paths or
    patterns. It need not use one particular summary filename or a cluster test.
    Presence is an input-availability check, not evidence computations passed.
    """
    root = Path(run_dir)
    planned = set(planned_stages)
    if planned - STAGE_DIRECTORIES.keys():
        raise ValueError(f'Unknown analysis stages: {sorted(planned - STAGE_DIRECTORIES.keys())}')
    if set(required_sources) != planned or any(not paths for paths in required_sources.values()):
        raise ValueError('Declare actual required sources for every planned stage only')
    result = {}
    for stage, directory in STAGE_DIRECTORIES.items():
        folder = root / directory
        files = sorted(p for p in folder.rglob('*') if p.is_file()) if folder.exists() else []
        item = dict(planned=stage in planned, directory_present=folder.is_dir(),
                    file_count=len(files), total_bytes=sum(p.stat().st_size for p in files),
                    files=[str(p.relative_to(root)) for p in files])
        if stage not in planned:
            item.update(status='not_applicable', required_matches={}, missing=[])
        else:
            matches = {pattern: sorted(str(p.relative_to(root)) for p in root.glob(pattern) if p.is_file())
                       for pattern in required_sources[stage]}
            missing = [pattern for pattern, found in matches.items() if not found]
            item.update(status='unavailable' if missing else 'available',
                        required_matches=matches, missing=missing)
        result[stage] = item
    return result


def require_planned_inputs(inventory):
    """Stop on planned-but-missing inputs; never invent an unplanned stage."""
    missing = {stage: item['missing'] for stage, item in inventory.items()
               if item['planned'] and item['status'] == 'unavailable'}
    if missing:
        raise ValueError(f'Planned stage inputs are unavailable: {missing}')
