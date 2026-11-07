"""Exercise the installed wheel against its source resource list."""
import argparse
from importlib import metadata
import json
from pathlib import Path
import subprocess
import sys
import tomllib

from auto_eeg_analysis import __version__
from auto_eeg_analysis.cli import resource_root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    output = args.out.resolve()
    output.mkdir()
    config = tomllib.loads((source / 'pyproject.toml').read_text())
    assert metadata.version('auto-eeg-analysis') == __version__ == config['project']['version']
    names = (source / 'packaging/RESOURCE_FILES.txt').read_text().splitlines()
    installed = resource_root()
    assert sorted(p.relative_to(installed).as_posix() for p in installed.rglob('*')
                  if p.is_file() and '__pycache__' not in p.parts) == names
    assert all((installed / name).read_bytes() == (source / name).read_bytes() for name in names)
    launcher = Path(sys.executable).with_name('aea-eeg')
    subprocess.run([str(launcher), '--version'], check=True)
    project = output / 'project with spaces'
    command = [str(launcher), 'init', str(project), '--agent', 'both']
    subprocess.run(command, check=True)
    assert not list(project.rglob('__pycache__'))
    assert all((project / name).read_bytes() == (source / name).read_bytes() for name in names)
    skill_names = sorted(p.parent.name for p in (source / 'skills').glob('*/SKILL.md'))
    for agent in ('.agents', '.claude'):
        directory = project / agent / 'skills'
        assert sorted(p.name for p in directory.iterdir()) == skill_names
        assert all((directory / name).resolve() == (project / 'skills' / name).resolve() for name in skill_names)
    marker = project / 'keep-user-file.txt'
    marker.write_text('keep this file\n')
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 2
    assert marker.read_text() == 'keep this file\n'
    assert all((project / name).read_bytes() == (source / name).read_bytes() for name in names)
    print(json.dumps({'passed': True, 'version': __version__, 'resource_files': len(names), 'skills': len(skill_names), 'clients_checked': ['codex', 'claude'], 'model_calls': 0}, indent=2))


if __name__ == '__main__':
    main()
