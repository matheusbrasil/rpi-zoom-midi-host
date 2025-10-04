"""Helper utilities for interacting with MIDI devices."""

from __future__ import annotations

import contextlib
import logging
from typing import Iterable, Optional

import mido

from .config import all_midi_keywords

LOGGER = logging.getLogger(__name__)


def find_matching_port(names: Iterable[str], keywords: Iterable[str]) -> Optional[str]:
    """Return the first MIDI port whose name contains one of the given keywords."""

    for name in names:
        lowered = name.lower()
        for keyword in keywords:
            if keyword.lower() in lowered:
                return name
    return None


def open_zoom_ports() -> tuple[Optional[mido.ports.BaseInput], Optional[mido.ports.BaseOutput]]:
    """Open MIDI input and output ports connected to the Zoom pedal."""

    input_name = find_matching_port(mido.get_input_names(), all_midi_keywords())
    output_name = find_matching_port(mido.get_output_names(), all_midi_keywords())

    LOGGER.info("Zoom MIDI input: %s", input_name or "not found")
    LOGGER.info("Zoom MIDI output: %s", output_name or "not found")

    input_port = mido.open_input(input_name) if input_name else None
    output_port = mido.open_output(output_name) if output_name else None
    return input_port, output_port


def open_m_vave_ports() -> tuple[Optional[mido.ports.BaseInput], Optional[mido.ports.BaseOutput]]:
    """Open MIDI ports for the M-Vave Chocolate Plus."""

    keywords = ("M-VAVE", "CHOCOLATR", "Chocolate")
    input_name = find_matching_port(mido.get_input_names(), keywords)
    output_name = find_matching_port(mido.get_output_names(), keywords)

    LOGGER.info("M-Vave input: %s", input_name or "not found")
    LOGGER.info("M-Vave output: %s", output_name or "not found")

    input_port = mido.open_input(input_name) if input_name else None
    output_port = mido.open_output(output_name) if output_name else None
    return input_port, output_port


@contextlib.contextmanager
def managed_ports(open_fn):
    """Context manager that opens ports using ``open_fn`` and closes them afterwards."""

    input_port, output_port = open_fn()
    try:
        yield input_port, output_port
    finally:
        if input_port:
            input_port.close()
        if output_port:
            output_port.close()
