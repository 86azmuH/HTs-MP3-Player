from __future__ import annotations

import argparse
import time
from pathlib import Path

from controller_agent.sync_client import SyncClient, SyncClientError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync local controller media folder to hub")
    parser.add_argument("--device-id", required=True, help="Unique controller id")
    parser.add_argument("--hub-url", required=True, help="Hub base URL, e.g. http://192.168.1.50:8000")
    parser.add_argument(
        "--watch-dir",
        default="controller_media",
        help="Controller media folder to sync (default: controller_media)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=3.0,
        help="Sync interval in seconds (default: 3.0)",
    )
    return parser.parse_args()


def snapshot_mp3s(directory: Path) -> dict[str, tuple[int, int]]:
    result: dict[str, tuple[int, int]] = {}
    for file_path in sorted(directory.glob("*.mp3"), key=lambda p: p.name.lower()):
        if not file_path.is_file():
            continue
        stat = file_path.stat()
        result[file_path.name] = (int(stat.st_mtime_ns), int(stat.st_size))
    return result


def run() -> None:
    args = parse_args()
    watch_dir = Path(args.watch_dir).expanduser().resolve()
    watch_dir.mkdir(parents=True, exist_ok=True)

    client = SyncClient(args.hub_url)
    previous = snapshot_mp3s(watch_dir)

    print(f"Watching {watch_dir} for MP3 changes (device_id={args.device_id})")

    while True:
        try:
            current = snapshot_mp3s(watch_dir)

            changed_or_new = [
                name for name, signature in current.items() if previous.get(name) != signature
            ]
            if changed_or_new:
                paths = [watch_dir / name for name in changed_or_new]
                upload_resp = client.upload_library_files(args.device_id, paths)
                print(upload_resp.get("message", "Upload complete"))

            reconcile_resp = client.reconcile_library(args.device_id, list(current.keys()))
            removed_count = int(reconcile_resp.get("removed_count", 0))
            if removed_count > 0:
                print(reconcile_resp.get("message", "Reconcile complete"))

            previous = current
        except SyncClientError as exc:
            print(f"Sync error: {exc}")
        except Exception as exc:
            print(f"Unexpected media sync error: {exc}")

        time.sleep(max(1.0, args.interval))


if __name__ == "__main__":
    run()
