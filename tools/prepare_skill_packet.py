"""Prepare selected procedures for complete delivery in an initial model message."""
import argparse
import json
from pathlib import Path
from load_skill import load_skill_packet, check_packet_in_request


def prepare_packet(root, selections):
    packets = []
    receipts = []
    for selection in selections:
        packet, receipt = load_skill_packet(Path(root), **selection)
        packets.append(packet)
        receipts.append(receipt)
    if not packets:
        raise ValueError("Select a relevant skill procedure before preparing a packet")
    header = (
        "AEA preloaded procedures and executable templates\n\n"
        "Use these selected procedures for the supplied approved task. Scientific "
        "settings come from that task and its approved plan, not an example. "
        "Record procedures/helpers actually used and any explicit adaptations. "
        "Complete input delivery is distinct from correct execution. Run the "
        "public artifact self-check before final delivery; external numerical "
        "verification remains separate.\n\n")
    packet = header + "\n\n".join(packets)
    return packet, {"selections": receipts, "packet_characters": len(packet),
                    "execution_condition": "preloaded_procedures",
                    "scope": "Delivery receipt, not proof of adoption or accuracy."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("selection_file", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    packet, receipt = prepare_packet(args.root, json.loads(args.selection_file.read_text()))
    args.output.write_text(packet, encoding="utf-8")
    args.receipt.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
