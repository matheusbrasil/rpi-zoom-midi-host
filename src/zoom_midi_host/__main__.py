"""Command line entry point for the Zoom MIDI host."""

from __future__ import annotations

import argparse

from .app import run_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Zoom MS-60B+ MIDI host")
    parser.add_argument(
        "--foreground",
        action="store_true",
        help="Run in the foreground (default)"
    )
    _ = parser.parse_args()
    run_app()


if __name__ == "__main__":
    main()
