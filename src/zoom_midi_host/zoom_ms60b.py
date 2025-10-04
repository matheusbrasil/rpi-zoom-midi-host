"""High-level helper to interact with the Zoom MS-60B+."""

from __future__ import annotations

import logging
import time
from typing import Iterable, Optional

import mido

from .state import Effect, PatchChain
from .zoom_protocol import build_sysex, parse_sysex_response, ZoomProtocolError

LOGGER = logging.getLogger(__name__)

REQUEST_CURRENT_PATCH = [0x58, 0x29, 0x00, 0x00]
REQUEST_PATCH_NAME = [0x29, 0x00, 0x00, 0x00]
MAX_EFFECTS = 6


class ZoomMs60bPlus:
    """Client for fetching and controlling state from the Zoom MS-60B+."""

    def __init__(self, midi_in: mido.ports.BaseInput, midi_out: mido.ports.BaseOutput) -> None:
        self._in = midi_in
        self._out = midi_out

    def _request(self, payload: Iterable[int], timeout: float = 0.5) -> Optional[mido.Message]:
        """Send a SysEx request and wait for the first response."""

        message = build_sysex(payload)
        self._out.send(message)
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            for response in self._in.iter_pending():
                if response.type == "sysex":
                    return response
            time.sleep(0.01)
        LOGGER.warning("Timeout waiting for response to payload %s", payload)
        return None

    def identify(self) -> Optional[str]:
        """Return the reported pedal name, or ``None`` if it could not be read."""

        response = self._request(REQUEST_PATCH_NAME)
        if not response:
            return None
        try:
            data = parse_sysex_response(response)
        except ZoomProtocolError:
            LOGGER.exception("Failed to parse pedal identify response")
            return None
        return bytes(data[4:]).decode("ascii", errors="ignore").strip("\x00")

    def fetch_patch_chain(self) -> Optional[PatchChain]:
        """Fetch the current patch chain from the pedal."""

        response = self._request(REQUEST_CURRENT_PATCH)
        if not response:
            return None
        try:
            data = parse_sysex_response(response)
        except ZoomProtocolError:
            LOGGER.exception("Failed to parse patch response")
            return None

        patch_name = self._decode_patch_name(data)
        effects = [self._decode_effect(slot, data) for slot in range(MAX_EFFECTS)]
        active_effects = [effect for effect in effects if effect is not None]
        return PatchChain(patch_name=patch_name, effects=active_effects)

    @staticmethod
    def _decode_patch_name(data: list[int]) -> str:
        name_bytes = data[20:40]
        return bytes(name_bytes).decode("ascii", errors="ignore").strip("\x00 ")

    @staticmethod
    def _decode_effect(slot: int, data: list[int]) -> Optional[Effect]:
        base = 40 + slot * 16
        if base + 16 > len(data):
            return None
        effect_id = data[base]
        enabled = bool(data[base + 1])
        name = EFFECT_NAMES.get(effect_id, f"Effect {effect_id:02X}")
        return Effect(slot=slot, name=name, enabled=enabled)

    def toggle_effect(self, slot: int, enabled: bool) -> None:
        """Toggle an effect slot on the pedal."""

        command = [0x31, slot, 0x01 if enabled else 0x00]
        response = self._request(command)
        if not response:
            LOGGER.warning("Failed to toggle slot %s", slot)


EFFECT_NAMES = {
    0x01: "ZNR",
    0x02: "Limiter",
    0x03: "BassDrive",
    0x04: "Bass Muff",
    0x05: "Octaver",
    0x06: "Bass Synth",
}
