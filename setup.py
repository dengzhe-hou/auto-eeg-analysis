"""Bundle the repository resources without maintaining a second source copy."""
from pathlib import Path
import runpy
import shutil

from setuptools import setup
from setuptools.command.build_py import build_py

ROOT = Path(__file__).parent


def resource_files():
    return (ROOT / "packaging" / "RESOURCE_FILES.txt").read_text(encoding="utf-8").splitlines()


class BuildResources(build_py):
    def run(self):
        super().run()
        destination = Path(self.build_lib) / "auto_eeg_analysis" / "resources"
        for name in resource_files():
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        version = runpy.run_path(str(ROOT / "src/auto_eeg_analysis/__init__.py"))
        (destination / "tools/env/ARCHIVE_VERSION").write_text(
            f"{version['SOURCE_COMMIT']} {version['SOURCE_DATE']}\n", encoding="utf-8", newline="\n")

    def get_outputs(self, include_bytecode=1):
        return super().get_outputs(include_bytecode) + [
            str(Path(self.build_lib) / "auto_eeg_analysis" / "resources" / name)
            for name in resource_files()
        ]


setup(cmdclass={"build_py": BuildResources})
