"""Record the actual Slurm process-tree CPU and memory limits before API calls."""
import json
import os
from pathlib import Path


def main():
    requested_cpus = int(os.environ['SLURM_CPUS_PER_TASK'])
    requested_bytes = int(os.environ['SLURM_MEM_PER_NODE']) * 1024 ** 2
    relative = next(line.split(':', 2)[2] for line in Path('/proc/self/cgroup').read_text().splitlines()
                    if line.startswith('0::'))
    cgroup = Path('/sys/fs/cgroup') / relative.lstrip('/')
    memory_controls = []
    for parent in [cgroup, *cgroup.parents]:
        if not parent.is_relative_to('/sys/fs/cgroup'):
            break
        control = parent / 'memory.max'
        if control.exists():
            value = control.read_text().strip()
            memory_controls.append({'path': str(control), 'value': value})
    limits = [int(row['value']) for row in memory_controls if row['value'] != 'max']
    affinity = sorted(os.sched_getaffinity(0))
    value = {'job_id': os.environ['SLURM_JOB_ID'], 'cgroup': str(cgroup),
             'requested_cpus': requested_cpus, 'affinity': affinity,
             'requested_memory_bytes': requested_bytes,
             'effective_memory_max': min(limits) if limits else None,
             'memory_controls': memory_controls,
             'cpuset_effective': (cgroup / 'cpuset.cpus.effective').read_text().strip(),
             'cpu_max': (cgroup / 'cpu.max').read_text().strip()}
    value['passed'] = (len(affinity) <= requested_cpus and bool(limits)
                       and min(limits) <= requested_bytes)
    target = Path(__file__).resolve().parent / 'logs' / ('allocation-' + value['job_id'] + '.json')
    target.write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps(value), flush=True)
    if not value['passed']:
        raise SystemExit('Requested process-tree CPU/memory limits are not effective; no model call allowed')


if __name__ == '__main__':
    main()
