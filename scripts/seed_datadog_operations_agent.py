from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "app" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from core.catalog_seed import seed_datadog_operations_analyst  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed only the Datadog Operations Analyst template.")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    status, version = seed_datadog_operations_analyst(apply=args.apply)
    print(f"Datadog Operations Analyst: {status} (version {version})")

if __name__ == "__main__":
    main()
