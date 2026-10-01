from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from .config import default_config_path, load_config
from .google_calendar import authorize
from .service import run_forever, run_once
from .transport import discover


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Synchronize weather and Google Calendar with a ZMK display")
    parser.add_argument("--config", type=Path, default=default_config_path())
    parser.add_argument("--verbose", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("discover", help="list nearby Bluetooth devices")
    commands.add_parser("auth-google", help="authorize read-only Google Calendar access")
    once = commands.add_parser("once", help="fetch and send one update")
    once.add_argument("--dry-run", action="store_true", help="fetch and encode data without Bluetooth")
    commands.add_parser("run", help="run the synchronization service")
    return parser


def main() -> None:
    args = _parser().parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.command == "discover":
        for address, name in asyncio.run(discover()):
            print(f"{address}\t{name}")
        return

    config = load_config(args.config)
    if args.command == "auth-google":
        authorize(config.calendar)
    elif args.command == "once":
        packet = asyncio.run(run_once(config, dry_run=args.dry_run))
        if args.dry_run:
            print(packet.hex())
    elif args.command == "run":
        asyncio.run(run_forever(config))
