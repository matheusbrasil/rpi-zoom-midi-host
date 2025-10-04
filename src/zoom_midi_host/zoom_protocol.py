"""Low level Zoom SysEx protocol helpers."""

from __future__ import annotations

import logging
from typing import Iterable, List

import mido

LOGGER = logging.getLogger(__name__)

ZOOM_SYSEX_HEADER = [0x52, 0x00, 0x6E]


class ZoomProtocolError(RuntimeError):
    """Raised when the Zoom pedal returns an unexpected response."""


def build_sysex(command: Iterable[int]) -> mido.Message:
    """Build a SysEx message for the Zoom pedal."""

    data = list(ZOOM_SYSEX_HEADER)
    data.extend(command)
    LOGGER.debug("Sending SysEx: %s", " ".join(f"{byte:02X}" for byte in data))
    return mido.Message("sysex", data=data)


def parse_sysex_response(message: mido.Message) -> List[int]:
    """Validate and strip the Zoom SysEx header from a response."""

    if message.type != "sysex":
        raise ZoomProtocolError("Expected SysEx message")
    data = list(message.data)
    if data[:3] != ZOOM_SYSEX_HEADER:
        raise ZoomProtocolError("Unexpected SysEx header")
    LOGGER.debug(
        "Received SysEx: %s", " ".join(f"{byte:02X}" for byte in data)
    )
    return data[3:]
