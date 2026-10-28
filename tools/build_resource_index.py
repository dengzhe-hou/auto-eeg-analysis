"""Build a short discovery index; procedure details remain in the source files."""

from pathlib import Path
import re
import sys


def build_index(root: Path) -> str:
    lines = ['# AEA resources', '', 'Read AGENT_GUIDE.md. Skill NAME is at skills/NAME/SKILL.md; read its procedure before implementing it. Descriptions below are routing summaries.', '', 'Skills:']
    for path in sorted(root.glob('skills/*/SKILL.md')):
        description = re.search(r'^description:\s*(.*)$', path.read_text(encoding='utf-8-sig'), re.M)[1].strip().strip('"')
        short = description if len(description) <= 72 else description[:69].rsplit(' ', 1)[0] + '...'
        lines.append(f'- {path.parent.name}: {short}')
    lines += ['', 'Recipes: NAME is at recipes/NAME/RECIPE.md.']
    lines += [f'- {path.parent.name}' for path in sorted(root.glob('recipes/*/RECIPE.md')) if path.parent.name != '_template']
    lines += ['Recipe template: recipes/_template/RECIPE.md']
    rendered = '\n'.join(lines) + '\n'
    assert len(rendered) <= 3000, 'Index must fit the observed 3000-character prefix reads'
    return rendered


if __name__ == '__main__':
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    (root / 'RESOURCE_INDEX.md').write_text(build_index(root), encoding='utf-8')
