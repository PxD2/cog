#!/usr/bin/env python3
"""Publish the Alexandria 3D sets and hero pictures to GitHub (PxD2/cog), where the web and VR Hall load them.

    python publish_sets.py              # sets\\great_hall.glb, sets\\presidents_hall.glb -> cog/sets/ ; rotunda.jpg, theater.jpg -> cog/alexandria/img/
    python publish_sets.py --dry-run

Only the web sets go up (baked light, a few MB each). The Unreal sets (*_ue.glb) and .blend files stay on base1.
"""
from __future__ import annotations

import argparse, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cog_absorber as A        # noqa: E402

SETS = HERE / "sets"
MAP = {"great_hall.glb": "sets/great_hall.glb", "presidents_hall.glb": "sets/presidents_hall.glb",
       "rotunda.jpg": "alexandria/img/rotunda.jpg", "theater.jpg": "alexandria/img/theater.jpg"}
LIMIT = 50 * 1024 * 1024          # GitHub warns at 50 MB and rejects 100 MB


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--repo", default=A.REPO)
    a = ap.parse_args(argv)
    files = {}
    for name, dest in MAP.items():
        p = SETS / name
        if not p.exists():
            print(f"  missing {p} (skipped)")
            continue
        if p.stat().st_size > LIMIT:
            print(f"  {name} is {p.stat().st_size / 1e6:.0f} MB — over 50 MB, rebuild with --res 1024 (skipped)")
            continue
        files[dest] = p.read_bytes()
        print(f"  {name} -> {dest} ({p.stat().st_size / 1e6:.1f} MB)")
    if not files:
        print("Nothing to publish.")
        return 1
    if a.dry_run:
        return 0
    store = A.GitHubStore(a.repo)
    if not store.token:
        print("No GitHub sign-in found.")
        return 2
    store.refresh()
    sha = store.commit(files, f"Alexandria 3D sets: {', '.join(sorted(files))}")
    print(f"Published {len(files)} file(s) · commit {sha[:7]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
