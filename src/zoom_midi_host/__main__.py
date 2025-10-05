"""Command line entry point for the Zoom MIDI host."""

from __future__ import annotations

import argparse

from .app import run_app
from .service import install_systemd_service


def main() -> None:
    parser = argparse.ArgumentParser(description="Zoom MS-60B+ MIDI host utilities")
    parser.add_argument(
        "--foreground",
        action="store_true",
        help="Run in the foreground (default)",
    )

    subparsers = parser.add_subparsers(dest="command")
    install_parser = subparsers.add_parser(
        "install-service", help="Install the application as a systemd service"
    )
    install_parser.add_argument(
        "--scope",
        choices=("user", "system"),
        default="user",
        help="Install the service for the current user (default) or system-wide",
    )
    install_parser.add_argument(
        "--user",
        help="User account to run the service under when installing system-wide",
    )
    install_parser.add_argument(
        "--no-enable",
        action="store_true",
        help="Do not enable the service after installation",
    )
    install_parser.add_argument(
        "--no-start",
        action="store_true",
        help="Do not start the service after installation",
    )

    args = parser.parse_args()

    if args.command == "install-service":
        install_systemd_service(
            scope=args.scope,
            user=args.user,
            enable=not args.no_enable,
            start=not args.no_start,
        )
        return

    run_app()


if __name__ == "__main__":
    main()
