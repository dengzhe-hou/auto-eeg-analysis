"""Check complete procedures survive request formatting; reject partial delivery."""
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from load_skill import load_skill_packet, check_packet_in_request, read_section


def entropy_packet():
    return load_skill_packet(ROOT, 'eeg-complexity',
        section='Sample & Approximate entropy (SampEn / ApEn)',
        references=['references/sample-entropy.md'])


@pytest.mark.parametrize('blocks', [True, False])
def test_full_packet_visible_in_native_message(blocks):
    packet, receipt = entropy_packet()
    text = 'Task description\n\n' + packet
    content = [{'type': 'text', 'text': text}] if blocks else text
    result = check_packet_in_request({'messages': [{'role': 'user', 'content': content}]}, packet)
    assert result['complete_packet_present']
    assert result['packet_characters'] == receipt['packet_characters']
    # Both the skill's computation section and its companion procedure are included.
    assert len(receipt['sources']) == 2
    assert receipt['sources'][0]['characters'] > 0
    assert receipt['sources'][1]['characters'] > 0


@pytest.mark.parametrize('characters', [0, 160, 3000])
def test_prefix_read_cannot_pass_as_complete_delivery(characters):
    packet, _ = entropy_packet()
    assert len(packet) > characters
    with pytest.raises(ValueError, match='absent or truncated'):
        check_packet_in_request({'messages': [{'role': 'user', 'content': packet[:characters]}]}, packet)


def test_missing_resource_fails_before_request():
    with pytest.raises(FileNotFoundError):
        load_skill_packet(ROOT, 'eeg-complexity', references=['references/absent.md'])


def test_section_loads_procedure_instead_of_router_or_entire_reference():
    packet, receipt = load_skill_packet(ROOT, 'eeg-spectral', section='Phase B — PSD computation')
    assert "def welch_parameters" in packet
    assert '## Phase C' not in packet
    assert receipt['sources'][0]['path'].endswith('/references/procedure.md')


def test_entrypoint_does_not_eagerly_load_references():
    packet, receipt = load_skill_packet(ROOT, 'eeg-spectral')
    assert len(receipt['sources']) == 1
    assert receipt['sources'][0]['path'].endswith('/SKILL.md')
    assert 'def welch_parameters' not in packet


def test_section_ignores_heading_inside_code_fence():
    text = '```python\n## Example\n```\n## Example\nactual\n## Next\n'
    assert read_section(text, 'Example') == '## Example\nactual'


def test_missing_section_fails_clearly():
    with pytest.raises(ValueError, match='Section not found'):
        load_skill_packet(ROOT, 'eeg-spectral', section='No such operation')
