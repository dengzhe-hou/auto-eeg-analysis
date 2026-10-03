"""Download one ERP CORE component (BIDS) from the local manifest's OSF URLs.

The MMN dataset shipped with a manifest (`erpcore_manifest.csv`) listing OSF download URLs
+ md5 for ALL 7 components (ERN, LRP, MMN, N170, N2pc, N400, P3). This fetches the shared
top-level files + the first N subjects of a chosen component into a BIDS directory, so the
same cross-tool benchmark harness can run on a second component.

  python tools/benchmark/download_erpcore_component.py --component P3 --n 20
"""
from __future__ import annotations
import argparse, hashlib, sys
from pathlib import Path
import pandas as pd
import requests

MANIFEST = Path.home() / "mne_data" / "MNE-erpcoremmn2021-data" / "erpcore_manifest.csv"


def md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--component", required=True)
    ap.add_argument("--n", type=int, default=20, help="number of subjects")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    comp = args.component
    out = Path(args.out or (Path.home() / "mne_data" / f"erpcore-{comp}"))
    out.mkdir(parents=True, exist_ok=True)

    d = pd.read_csv(MANIFEST)
    d = d[d["component"] == comp].copy()
    prefix = f"erpcore/{comp}/"
    d["rel"] = d["local_path"].str.replace(prefix, "", regex=False)

    keep_subs = {f"sub-{i:03d}" for i in range(1, args.n + 1)}
    def wanted(rel):
        if "/sub-" not in ("/" + rel):
            return "/sub-" not in rel and not rel.startswith("sub-")  # top-level
        return any(rel.startswith(s + "/") for s in keep_subs)
    rows = [r for _, r in d.iterrows() if ("sub-" not in r["rel"]) or r["rel"].split("/")[0] in keep_subs]

    sess = requests.Session()
    ok = skip = fail = 0
    for r in rows:
        dst = out / r["rel"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        want_md5 = str(r.get("hash", "")).replace("md5:", "")
        if dst.exists() and want_md5 and md5(dst) == want_md5:
            skip += 1; continue
        try:
            with sess.get(r["url"], stream=True, timeout=120, allow_redirects=True) as resp:
                resp.raise_for_status()
                with open(dst, "wb") as f:
                    for chunk in resp.iter_content(1 << 20):
                        f.write(chunk)
            if want_md5 and md5(dst) != want_md5:
                print(f"  MD5 MISMATCH {r['rel']}", flush=True); fail += 1
            else:
                ok += 1
                if dst.suffix in (".set", ".fdt"):
                    print(f"  {r['rel']}  ({dst.stat().st_size//1024} KB)", flush=True)
        except Exception as e:
            print(f"  FAIL {r['rel']}: {type(e).__name__}: {str(e)[:60]}", flush=True); fail += 1
    print(f"\n{comp}: downloaded {ok}, skipped {skip}, failed {fail} -> {out}", flush=True)
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
