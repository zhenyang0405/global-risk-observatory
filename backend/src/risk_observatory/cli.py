"""CLI subcommands invoked via `make ingest|brief|seed`."""

from __future__ import annotations

import asyncio
import sys

from .ingestion.extractor import ingest_text_once


def _usage() -> int:
    print("usage: python -m risk_observatory.cli <ingest|brief|seed> [args...]", file=sys.stderr)
    return 2


def main() -> int:
    if len(sys.argv) < 2:
        return _usage()

    cmd = sys.argv[1]

    if cmd == "ingest":
        text = sys.argv[2] if len(sys.argv) > 2 else None
        if not text:
            print("provide TEXT='...'", file=sys.stderr)
            return 2
        asyncio.run(ingest_text_once(text))
        return 0

    if cmd == "brief":
        from .reasoning.loop import run_once

        asyncio.run(run_once())
        return 0

    if cmd == "seed":
        from .scripts_runtime import seed_demo

        asyncio.run(seed_demo())
        return 0

    return _usage()


if __name__ == "__main__":
    raise SystemExit(main())
