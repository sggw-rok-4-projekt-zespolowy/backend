"""
Seed the database with tracks by calling the local /track endpoint.

Usage:
    python seed_tracks.py                  # use default track list below
    python seed_tracks.py 123 456 789      # pass Deezer track IDs as arguments

The server must be running at BASE_URL before you run this script.
"""

import sys
import time

import requests

from app.config import settings

BASE_URL = settings.BASE_URL

DEFAULT_TRACK_IDS = [
    "3135556",
    "906554",
    "916424",
    "128743581",
    "912706",
    "1652258222",
    "67238735",
    "865463452",
    "6543876",
    "128743521",
]


def seed(track_ids: list[int]) -> None:
    print(f"Seeding {len(track_ids)} track(s) into {BASE_URL}/track ...\n")

    ok = 0
    skipped = 0
    failed = 0

    for track_id in track_ids:
        try:
            resp = requests.post(
                f"{BASE_URL}/track",
                json={"deezer_track_id": track_id},
                timeout=30,
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                print(
                    f"  [OK]      {track_id} — {data.get('title', '?')} ({data.get('year', '?')})"
                )
                ok += 1
            elif resp.status_code == 400:
                print(f"  [SKIP]    {track_id} — already in database")
                skipped += 1
            else:
                print(f"  [FAILED]  {track_id} — HTTP {resp.status_code}: {resp.text}")
                failed += 1
        except requests.exceptions.ConnectionError:
            print(f"  [ERROR]   Cannot connect to {BASE_URL}. Is the server running?")
            sys.exit(1)
        except Exception as e:
            print(f"  [ERROR]   {track_id} — {e}")
            failed += 1

        # Brief pause to avoid hammering the Deezer API
        time.sleep(0.5)

    print(f"\nDone. {ok} added, {skipped} skipped, {failed} failed.")


if __name__ == "__main__":
    ids = [int(arg) for arg in sys.argv[1:]] if len(sys.argv) > 1 else DEFAULT_TRACK_IDS
    seed(ids)
