"""High-level helper to interact with the Zoom MS-60B+."""

from __future__ import annotations

import logging
import time
from typing import Iterable, Optional

import mido

from .effect_catalog import get_effect_metadata
from .state import Effect, PatchChain
from .zoom_protocol import build_sysex, parse_sysex_response, ZoomProtocolError

LOGGER = logging.getLogger(__name__)

REQUEST_CURRENT_PATCH_V2 = [0x64, 0x13]
REQUEST_CURRENT_PATCH_V1 = [0x29]
COMMAND_PARAMETER_EDIT_ENABLE = [0x50]
COMMAND_PARAMETER_EDIT_DISABLE = [0x51]
COMMAND_SAY_HI = [0x05]
PATCH_RESPONSE_PREFIX_V2 = (0x64, 0x12)
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

        self._clear_pending()
        response = self._request(REQUEST_CURRENT_PATCH_V2, timeout=2.0)
        data = None
        if response is not None:
            try:
                data = parse_sysex_response(response)
            except ZoomProtocolError:
                LOGGER.exception("Failed to parse patch response")
                data = None
            else:
                if len(data) < 2 or tuple(data[:2]) != PATCH_RESPONSE_PREFIX_V2:
                    LOGGER.warning("Unexpected patch response prefix: %s", data[:4])
                    data = None
        if data is None:
            LOGGER.info("Falling back to legacy patch request")
            response = self._request(REQUEST_CURRENT_PATCH_V1, timeout=1.5)
            if response is None:
                return None
            try:
                data = parse_sysex_response(response)
            except ZoomProtocolError:
                LOGGER.exception("Failed to parse patch response")
                return None
            if not data or data[0] != PATCH_RESPONSE_PREFIX_V1:
                LOGGER.warning("Unexpected legacy patch response prefix: %s", data[:4])
                return None

        decoded = self._unpack_sysex(response.data[4:])
        if not decoded:
            LOGGER.warning("Failed to decode patch payload")
            return None
        patch = self._parse_patch(decoded)
        if patch is None:
            LOGGER.warning("Unable to parse patch data")
        return patch

    @staticmethod
    def _unpack_sysex(payload: Iterable[int]) -> bytes:
        data = bytearray()
        hibits = 0
        loop = -1
        for byte in payload:
            if loop != -1:
                data.append((byte | 0x80) if (hibits & (1 << loop)) else byte)
                loop -= 1
            else:
                hibits = byte
                loop = 6
        return bytes(data)

    def _parse_patch(self, data: bytes) -> Optional[PatchChain]:
        masked = bytes(byte & 0x7F for byte in data)

        patch_name = "Unknown Patch"
        ptcf_index = self._find_tag(data, b"PTCF")
        if ptcf_index != -1:
            ptcf_length = int.from_bytes(masked[ptcf_index + 4 : ptcf_index + 8], "little", signed=False)
            ptcf_payload = masked[ptcf_index + 8 : ptcf_index + 8 + ptcf_length]
            if len(ptcf_payload) >= 4 + 4 + 4 + 6 + 10:
                short_name = ptcf_payload[4 + 4 + 4 + 6 : 4 + 4 + 4 + 6 + 10]
                patch_name = short_name.split(b"\x00", 1)[0].decode("utf-8", errors="ignore").strip() or patch_name

        if not patch_name:
            name_index = self._find_tag(data, b"NAME")
            if name_index != -1:
                name_length = int.from_bytes(masked[name_index + 4 : name_index + 8], "little", signed=False)
                name_payload = masked[name_index + 8 : name_index + 8 + name_length]
                patch_name = name_payload.split(b"\x00", 1)[0].decode("utf-8", errors="ignore").strip() or "Unknown Patch"

        edtb_index = self._find_tag(data, b"EDTB")
        if edtb_index == -1:
            LOGGER.warning("EDTB chunk not found in patch payload")
            return PatchChain(patch_name=patch_name, effects=[])

        edtb_length = int.from_bytes(masked[edtb_index + 4 : edtb_index + 8], "little", signed=False)
        edtb_data = data[edtb_index + 8 : edtb_index + 8 + edtb_length]
        next_tag_index = self._next_tag_index(data, edtb_index + 8)
        if next_tag_index != -1:
            edtb_data = data[edtb_index + 8 : next_tag_index]

        effects: list[Effect] = []
        effect_count = min(len(edtb_data) // 24, MAX_EFFECTS)
        for slot in range(effect_count):
            base = slot * 24
            if base + 4 > len(edtb_data):
                break
            b0 = edtb_data[base] & 0x7F
            b1 = edtb_data[base + 1] & 0x7F
            b2 = edtb_data[base + 2] & 0x7F
            b3 = edtb_data[base + 3] & 0x7F
            union = (b3 << 24) | (b2 << 16) | (b1 << 8) | b0
            effect_id = (union >> 1) & 0x0FFFFFFF
            enabled = bool(union & 0x01)
            metadata = get_effect_metadata(effect_id)
            effects.append(
                Effect(
                    slot=slot,
                    name=metadata.name if metadata else f"Effect 0x{effect_id:08X}",
                    enabled=enabled,
                    icon_slug=metadata.slug if metadata else None,
                )
            )

        return PatchChain(patch_name=patch_name, effects=effects)

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

    @staticmethod
    def _find_tag(data: bytes, tag: bytes, start: int = 0) -> int:
        tag_len = len(tag)
        for idx in range(start, len(data) - tag_len + 1):
            for offset, value in enumerate(tag):
                if (data[idx + offset] & 0x7F) != value:
                    break
            else:
                return idx
        return -1

    def _next_tag_index(self, data: bytes, start: int) -> int:
        tags = (b"NAME", b"PRM2", b"TXE1", b"TXJ1", b"PPRM")
        indices = [self._find_tag(data, tag, start) for tag in tags]
        indices = [idx for idx in indices if idx != -1]
        return min(indices) if indices else -1


__all__ = ["ZoomMs60bPlus"]
