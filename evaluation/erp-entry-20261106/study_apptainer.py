"""Cluster launch adapter; the published CodeAct execution loop is unchanged."""
import json
import os
from pathlib import Path
import signal
import subprocess
import time

from brainbench.codeact import engine

IMAGE = Path('/home/hou/Research/CogEEGBench/scratchpad/codeact_brainbench_timing_20261014/container/codeact.sif')


def stop_kernel(runtime_dir):
    """Also called by the case parent after the official hard deadline."""
    pid_file = Path(runtime_dir) / 'apptainer.pid'
    if pid_file.exists():
        info = json.loads(pid_file.read_text())
        pid = info['launcher_pid']
        target = info.get('kernel_pid', pid)
        try:
            os.kill(target, signal.SIGTERM)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + 3
        while session_processes(pid) and time.monotonic() < deadline:
            time.sleep(0.05)
        for remaining in session_processes(pid):
            try:
                os.kill(remaining, signal.SIGKILL)
            except ProcessLookupError:
                pass
        pid_file.unlink()


def descendants(pid):
    found, pending = [], [pid]
    while pending:
        current = pending.pop()
        proc = Path(f'/proc/{current}')
        if not proc.exists():
            continue
        found.append(current)
        pending.extend(int(x) for x in (proc / f'task/{current}/children').read_text().split())
    return found


def session_processes(session_id):
    """Apptainer's detached squashfuse helper stays in the launcher's session."""
    pids=[]
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            fields=(proc/'stat').read_text().rsplit(')',1)[1].split()
        except (FileNotFoundError, ProcessLookupError):
            continue
        if int(fields[3]) == session_id and fields[0] != 'Z':
            pids.append(int(proc.name))
    return pids


class ApptainerKernel(engine.DockerKernel):
    def execute(self, code, timeout_sec):
        started = time.monotonic()
        entry = {'code':code, 'started_at_unix':time.time()}
        try:
            observation = super().execute(code, timeout_sec=timeout_sec)
            entry['observation'] = observation
            return observation
        except Exception as exc:
            entry['error'] = {'type':type(exc).__name__, 'message':str(exc)}
            raise
        finally:
            entry['elapsed_seconds'] = time.monotonic()-started
            destination = os.environ.get('CODEACT_EXECUTION_TRACE')
            if destination:
                with Path(destination).open('a') as stream:
                    stream.write(json.dumps(entry, ensure_ascii=False)+'\n')

    def __enter__(self):
        connection_file = self.context.runtime_dir / 'connection.json'
        engine.write_connection_file(str(connection_file),
            ip=str(self.context.runtime_dir / 'kernel'), transport='ipc',
            key=os.urandom(32).hex().encode('ascii'))
        command = [
            '/usr/bin/apptainer', 'exec', '--containall', '--no-home',
            '--no-mount', 'hostfs,cwd,bind-paths', '--net', '--network', 'none',
            '--cleanenv', '--pwd', '/workspace',
            '--bind', f'{self.context.host_workspace}:/workspace:rw',
            '--bind', f'{self.context.runtime_dir}:{self.context.runtime_dir}:rw',
        ]
        for source, destination in self.context.input_mounts.items():
            command += ['--bind', f'{source}:{destination}:ro']
        for name, value in dict(HOME='/tmp', MPLCONFIGDIR='/tmp/matplotlib',
            MPLBACKEND='Agg', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1',
            MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1', BLIS_NUM_THREADS='1',
            NUMBA_CACHE_DIR='/tmp/numba-cache',
            PYTHONDONTWRITEBYTECODE='1').items():
            command += ['--env', f'{name}={value}']
        command += [str(IMAGE), 'python', '-m', 'ipykernel_launcher', '-f', str(connection_file)]
        self.context.audit['container_command'] = command
        self.log = (self.context.runtime_dir / 'apptainer.log').open('w')
        self.payload = subprocess.Popen(command, stdout=self.log, stderr=subprocess.STDOUT,
                                        start_new_session=True, cwd='/tmp')
        pid_file=self.context.runtime_dir / 'apptainer.pid'
        pid_file.write_text(json.dumps({'launcher_pid':self.payload.pid}))
        try:
            self.client = engine.BlockingKernelClient(connection_file=str(connection_file))
            # This client has no KernelManager. Early heartbeat silence is not
            # process death; retain the original 30s kernel_info readiness cap.
            async def process_alive():
                return self.payload.poll() is None
            self.client._async_is_alive = process_alive
            self.client.load_connection_file()
            self.client.start_channels()
            self.client.wait_for_ready(timeout=30)
            worker = Path('/proc/self/cgroup').read_text().strip().split('::', 1)[1]
            pids=set(descendants(self.payload.pid)) | set(session_processes(self.payload.pid))
            groups = {str(pid): Path(f'/proc/{pid}/cgroup').read_text().strip().split('::', 1)[1]
                      for pid in pids}
            kernels = [int(pid) for pid in groups
                       if Path(f'/proc/{pid}/exe').resolve().name.startswith('python')
                       and b'ipykernel_launcher' in Path(f'/proc/{pid}/cmdline').read_bytes()]
            if len(kernels) != 1:
                raise engine.SandboxSetupError(f'Expected one actual ipykernel PID, found {kernels}')
            self.kernel_pid = kernels[0]
            pid_file.write_text(json.dumps({'launcher_pid':self.payload.pid,
                                           'kernel_pid':self.kernel_pid}))
            contained = bool(groups) and worker != '/' and all(
                group == worker or group.startswith(worker.rstrip('/') + '/')
                for group in groups.values())
            self.context.audit.update({
                'backend': 'apptainer', 'image': str(IMAGE), 'network': 'none',
                'resource_accounting': {'worker_cgroup': worker,
                    'container_process_cgroups': groups, 'kernel_in_worker_cgroup': contained,
                    'kernel_host_pid': self.kernel_pid,
                    'slurm_job_id': os.environ.get('SLURM_JOB_ID'),
                    'limits': 'Slurm allocation; not the Docker 4CPU/8G sub-cgroup'},
            })
            if os.environ.get('SLURM_JOB_ID') and not contained:
                raise engine.SandboxSetupError('Apptainer processes outside Slurm worker cgroup')
            self.started = True
            return self
        except Exception as exc:
            self.log.flush()
            detail = (self.context.runtime_dir / 'apptainer.log').read_text()
            self.context.audit['container_error_log'] = detail
            self.context.audit['launcher_returncode_at_failure'] = self.payload.poll()
            self.context.audit['ipc_entries_at_failure'] = [p.name for p in self.context.runtime_dir.iterdir()]
            self._remove_container()
            raise engine.SandboxSetupError(f'Apptainer startup failed: {exc}; {detail}') from exc

    def _docker(self, command, *, check=True):
        # The inherited execute() uses this only to interrupt a timed-out cell.
        if command[1:4] != ['kill', '--signal', 'SIGINT']:
            raise ValueError(f'Unexpected Docker operation in Apptainer adapter: {command[:4]}')
        os.kill(self.kernel_pid, signal.SIGINT)
        return subprocess.CompletedProcess(command, 0, '', '')

    def _remove_container(self):
        stop_kernel(self.context.runtime_dir)
        if hasattr(self, 'payload'):
            self.payload.wait(timeout=5)
        if hasattr(self, 'log'):
            self.log.close()
        self.started = False
