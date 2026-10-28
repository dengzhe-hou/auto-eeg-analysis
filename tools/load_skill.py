"""Load selected AEA procedures for clients without native skill loading.

The caller chooses the skill and section from the public task. Add the returned
packet to the initial user message, rather than a truncatable tool observation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


def read_section(text: str, heading: str) -> str:
    lines = text.splitlines(keepends=True)
    start = None
    fence = None
    for i, line in enumerate(lines):
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            if fence is None:
                fence = marker[1]
            elif marker[1][0] == fence[0] and len(marker[1]) >= len(fence):
                fence = None
            continue
        match = re.match(r"^(#{1,6}) (.*?)\s*$", line)
        if fence is not None or not match:
            continue
        if start is None and match[2] == heading:
            start, level = i, len(match[1])
        elif start is not None and len(match[1]) <= level:
            return "".join(lines[start:i]).strip()
    if start is None:
        raise ValueError(f"Section not found: {heading}")
    return "".join(lines[start:]).strip()


def _reference_paths(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(
        r"\]\((references/[^\s)#]+\.md)(?:#[^\s)]*)?\)", text)))


def _selected_procedure(root: Path, skill: str, text: str, section: str):
    """Follow the entrypoint's explicit references, extracting only one section."""
    try:
        selected = read_section(text, section)
    except ValueError:
        selected = None
    references = _reference_paths(selected if selected is not None else text)
    if selected is not None and not references:
        return f"skills/{skill}/SKILL.md", selected

    matches = []
    for reference in references:
        source = f"skills/{skill}/{reference}"
        body = (root / source).read_text(encoding="utf-8-sig")
        try:
            matches.append((source, read_section(body, section)))
        except ValueError:
            continue
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(f"Ambiguous section: {section}; select a distinct heading")
    if selected is not None:
        return f"skills/{skill}/SKILL.md", selected
    raise ValueError(f"Section not found in {skill} or its linked references: {section}")


def load_skill_packet(root: Path, skill: str, *, section=None, references=()):
    path = f"skills/{skill}/SKILL.md"
    text = (root / path).read_text(encoding="utf-8-sig")
    parts = [_selected_procedure(root, skill, text, section)] if section else [(path, text)]
    for reference in references:
        source = f"skills/{skill}/{reference}"
        parts.append((source, (root / source).read_text(encoding="utf-8-sig")))
    packet = "\n\n".join(f"AEA procedure: {source}\n\n{body}" for source, body in parts)
    receipt = {
        "skill": skill,
        "section": section,
        "sources": [{"path": source, "characters": len(body)} for source, body in parts],
        "packet_characters": len(packet),
        "scope": "Procedure delivery is distinct from following it or passing validation.",
    }
    return packet, receipt


def check_packet_in_request(native_request: dict, packet: str) -> dict:
    """Check the full packet in the actual provider-format message payload."""
    for index, message in enumerate(native_request["messages"]):
        content = message["content"]
        text = content if isinstance(content, str) else "\n".join(
            block.get("text", "") for block in content if block.get("type") == "text")
        if packet and packet in text:
            return {"message_index": index, "packet_characters": len(packet),
                    "complete_packet_present": True}
    raise ValueError("Selected AEA procedure is absent or truncated in the model request")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill")
    parser.add_argument("--section")
    parser.add_argument("--reference", action="append", default=[])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    packet, receipt = load_skill_packet(args.root, args.skill, section=args.section,
                                        references=args.reference)
    if args.receipt:
        args.receipt.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(packet)


if __name__ == "__main__":
    main()
