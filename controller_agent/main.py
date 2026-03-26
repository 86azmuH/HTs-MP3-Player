from __future__ import annotations

import argparse

from bootstrap import resolve_directory
from controller_agent.agent import OfflineControllerAgent, run_forever


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run offline-first controller playback agent")
    parser.add_argument("--device-id", required=True, help="Unique controller id")
    parser.add_argument("--hub-url", required=True, help="Hub base URL, e.g. http://192.168.1.50:8000")
    parser.add_argument(
        "directory",
        nargs="?",
        default=None,
        help="Local music directory (defaults to media/ then cwd fallback)",
    )
    parser.add_argument(
        "--sync-interval",
        type=float,
        default=2.0,
        help="Sync loop interval in seconds (default: 2.0)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    directory = resolve_directory(args.directory)

    agent = OfflineControllerAgent(
        device_id=args.device_id,
        hub_base_url=args.hub_url,
        music_directory=str(directory),
        sync_interval_seconds=args.sync_interval,
    )
    run_forever(agent)


if __name__ == "__main__":
    main()
