"""Generate the Brindlecove synthetic data estate.

    python -m generator                 # seed 42, writes data/raw/
    python -m generator --seed 7 --out /tmp/raw --scale 0.25

Same seed -> same data. Every module gets its own RNG stream, so changing
one source system never reshuffles the others.
"""
from __future__ import annotations

import argparse
import importlib
import shutil
import time
from pathlib import Path

from .world import build_world

MODULES = ["brix", "crm", "billing", "support", "telemetry", "email", "wiki", "documents", "meetings", "integrations",
           "chat", "voice", "imaging", "pim", "legacy_office", "datalake", "ops", "marketing", "finance_extra"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="data/raw")
    ap.add_argument("--scale", type=float, default=1.0, help="customer-count multiplier")
    ap.add_argument("--only", nargs="*", help="render only these modules")
    ap.add_argument("--golden", default="data/GOLDEN_FACTS.yaml")
    args = ap.parse_args(argv)

    out = Path(args.out)
    t0 = time.time()
    world = build_world(args.seed, args.scale)
    print(f"world: {len(world.customers)} customers, {len(world.invoices)} invoices, {len(world.people)} staff ({time.time() - t0:.1f}s)")
    if not args.only and out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    for name in args.only or MODULES:
        t = time.time()
        mod = importlib.import_module(f".sources.{name}", __package__)
        mod.render(world, out, args.seed)
        print(f"  {name:<13} {time.time() - t:5.1f}s")
    from .util import normalize_office_files
    normalize_office_files(out)
    if not args.only:
        from .golden import write_golden
        write_golden(world, out, Path(args.golden))
        print(f"golden facts -> {args.golden}")
    print(f"done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
