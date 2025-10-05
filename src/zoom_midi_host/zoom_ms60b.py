"""High-level helper to interact with the Zoom MS-60B+."""

from __future__ import annotations

import logging
import struct
import time
from typing import Iterable, Optional

import mido

from .effect_catalog import get_effect_metadata
from .state import Effect, PatchChain
from .zoom_protocol import build_sysex, parse_sysex_response, ZoomProtocolError

LOGGER = logging.getLogger(__name__)

REQUEST_CURRENT_PATCH = [0x29]
COMMAND_PARAMETER_EDIT_ENABLE = [0x50]
COMMAND_PARAMETER_EDIT_DISABLE = [0x51]
COMMAND_SAY_HI = [0x05]
PATCH_RESPONSE_PREFIX_V1 = 0x28

MAX_EFFECTS = 6


class ZoomMs60bPlus:
    """Client for fetching and controlling state from the Zoom MS-60B+."""

    def __init__(self, midi_in: mido.ports.BaseInput, midi_out: mido.ports.BaseOutput) -> None:
        self._in = midi_in
        self._out = midi_out
        self._editor_enabled = False
        self._initialise_pedal()

    def _initialise_pedal(self) -> None:
        """Flush pending messages and enable the pedal's edit mode."""

        self._clear_pending()
        self._request(COMMAND_SAY_HI, timeout=0.3)
        response = self._request(COMMAND_PARAMETER_EDIT_ENABLE, timeout=0.5)
        if response is not None:
            self._editor_enabled = True
        else:
            LOGGER.warning("Parameter edit enable timed out; continuing without confirmation")

    def _clear_pending(self) -> None:
        for _ in self._in.iter_pending():
            pass

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
        if not data or data[0] != PATCH_RESPONSE_PREFIX_V1:
            LOGGER.warning("Unexpected patch response prefix: %s", data[:4])
            return None

        decompressed = self._unpack_seven_bit(data[1:])
        if decompressed is None:
            LOGGER.warning("Failed to unpack patch response")
            return None
        return self._parse_patch(decompressed)

    @staticmethod
    def _unpack_seven_bit(payload: Iterable[int]) -> Optional[bytes]:
        hibits = 0
        bit_index = -1
        output = bytearray()
        for byte in payload:
            if bit_index >= 0:
                if hibits & (1 << bit_index):
                    output.append(byte | 0x80)
                else:
                    output.append(byte)
                bit_index -= 1
            else:
                hibits = byte
                bit_index = 6
        if not output:
            return None
        return bytes(output)

    def _parse_patch(self, data: bytes) -> PatchChain:
        try:
            name = data[26:58].split(b"\x00", 1)[0].decode("utf-8", errors="ignore").strip()
        except Exception:  # pragma: no cover
            LOGGER.exception("Failed to decode patch name")
            name = "Unknown Patch"

        try:
            chunk = data.split(b"EDTB", 1)[1]
            chunk = chunk.split(b"PPRM", 1)[0]
        except IndexError:
            LOGGER.warning("Failed to locate EDTB section in patch data")
            return PatchChain(patch_name=name, effects=[])

        effects: list[Effect] = []
        if not chunk:
            return PatchChain(patch_name=name, effects=effects)

        effect_count = int(chunk[0] / 24) if chunk[0] else 0
        slot_pointer = 0
        for index in range(min(effect_count, MAX_EFFECTS)):
            base = 4 + index * 24
            if base + 24 > len(chunk):
                break
            union = struct.unpack_from("<I", chunk, base)[0]
            effect_object_id = (union >> 1) & 0x0FFFFFFF
            enabled = bool(union & 0x01)
            metadata = get_effect_metadata(effect_object_id)
            effects.append(
                Effect(
                    slot=slot_pointer,
                    name=metadata.name if metadata else f"Effect 0x{effect_object_id:08X}",
                    enabled=enabled,
                    icon_slug=metadata.slug if metadata else None,
                )
            )
            slot_pointer += 1

        return PatchChain(patch_name=name, effects=effects)

    def toggle_effect(self, slot: int, enabled: bool) -> None:
        """Toggle an effect slot on the pedal."""

        command = [
            0x64,
            0x03,
            0x00,
            slot,
            0x00,
            0x00,
            0x02 if enabled else 0x00,
            0x00,
            0x00,
            0x00,
        ]
        response = self._request(command)
        if not response:
            LOGGER.warning("Failed to toggle slot %s", slot)

    def close(self) -> None:
        if self._editor_enabled:
            self._request(COMMAND_PARAMETER_EDIT_DISABLE, timeout=0.2)
            self._editor_enabled = False


__all__ = ["ZoomMs60bPlus"]
