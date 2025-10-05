"""Helpers for installing the Zoom MIDI host as a systemd service."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

LOGGER = logging.getLogger(__name__)

SERVICE_NAME = "zoom-midi-host.service"


def install_systemd_service(
    scope: str = "user",
    *,
    user: str | None = None,
    enable: bool = True,
    start: bool = True,
) -> Path:
    """Install (and optionally enable) the systemd unit for the application."""

    if scope not in {"user", "system"}:
        raise ValueError("scope must be 'user' or 'system'")

    exec_cmd = f"{sys.executable} -m zoom_midi_host --foreground"
    environment = "PYTHONUNBUFFERED=1"
    wanted_by = "default.target" if scope == "user" else "multi-user.target"

    service_dir = _service_directory(scope)
    service_dir.mkdir(parents=True, exist_ok=True)
    service_path = service_dir / SERVICE_NAME

    service_lines = [
        "[Unit]",
        "Description=Zoom MS-60B+ MIDI Host",
        "After=network-online.target sound.target",
        "Wants=network-online.target",
        "",
        "[Service]",
        "Type=simple",
        f"Environment={environment}",
        f"ExecStart={exec_cmd}",
        "Restart=on-failure",
        "RestartSec=3",
    ]

    if scope == "system" and user:
        service_lines.append(f"User={user}")
    elif scope == "system" and not _is_root():
        LOGGER.warning("Installing a system service normally requires root privileges")

    service_lines.extend(
        [
            "",
            "[Install]",
            f"WantedBy={wanted_by}",
        ]
    )

    service_path.write_text("\n".join(service_lines) + "\n", encoding="utf-8")
    LOGGER.info("Wrote systemd service file to %s", service_path)

    if enable:
        _run_systemctl(["--user" if scope == "user" else None, "enable", SERVICE_NAME], scope)
    if start:
        _run_systemctl(["--user" if scope == "user" else None, "start", SERVICE_NAME], scope)

    return service_path


def _service_directory(scope: str) -> Path:
    if scope == "user":
        return Path.home() / ".config" / "systemd" / "user"
    return Path("/etc/systemd/system")


def _run_systemctl(arguments: list[str | None], scope: str) -> None:
    args = ["systemctl"]
    for value in arguments:
        if value is None:
            continue
        args.append(value)

    LOGGER.info("Running %s", " ".join(args))
    try:
        result = subprocess.run(args, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        LOGGER.warning("systemctl is not available on this system; skipping %s", args[-2:])
        return

    if result.returncode != 0:
        LOGGER.warning("systemctl command failed (%s): %s", result.returncode, result.stderr.strip())
        if scope == "user" and "Failed to connect" in result.stderr:
            LOGGER.info(
                "systemd user services require lingering to be enabled. Run 'loginctl enable-linger %s'",
                os.environ.get("USER", "<user>"),
            )


def _is_root() -> bool:
    try:
        return os.geteuid() == 0
    except AttributeError:  # pragma: no cover - Windows fallback
        return False


__all__ = ["install_systemd_service"]
