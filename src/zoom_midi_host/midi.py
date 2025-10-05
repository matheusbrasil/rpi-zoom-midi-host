"""Helper utilities for interacting with MIDI devices."""

from __future__ import annotations

import logging
from typing import Iterable, Optional, Tuple

import mido

from .config import all_midi_keywords

LOGGER = logging.getLogger(__name__)


def find_matching_port(names: Iterable[str], keywords: Iterable[str]) -> Optional[str]:
    """Return the first MIDI port whose name contains one of the given keywords."""

    keywords = list(keywords)
    for name in names:
        lowered = name.lower()
        for keyword in keywords:
            if keyword.lower() in lowered:
                return name
    return None


def find_zoom_port_names() -> Tuple[Optional[str], Optional[str]]:
    """Return the input/output port names for the Zoom pedal if available."""

    input_names = mido.get_input_names()
    output_names = mido.get_output_names()
    LOGGER.info("Available MIDI inputs: %s", [repr(name) for name in input_names])
    LOGGER.info("Available MIDI outputs: %s", [repr(name) for name in output_names])

    input_name = find_matching_port(input_names, all_midi_keywords())
    output_name = find_matching_port(output_names, all_midi_keywords())

    LOGGER.info("Zoom MIDI input: %s", input_name or "not found")
    LOGGER.info("Zoom MIDI output: %s", output_name or "not found")
    return input_name, output_name


def open_m_vave_ports() -> Tuple[Optional[mido.ports.BaseInput], Optional[mido.ports.BaseOutput]]:
    """Open MIDI ports for the M-Vave Chocolate Plus."""

    keywords = ("M-VAVE", "CHOCOLATR", "Chocolate")
    input_name = find_matching_port(mido.get_input_names(), keywords)
    output_name = find_matching_port(mido.get_output_names(), keywords)

    LOGGER.info("M-Vave input: %s", input_name or "not found")
    LOGGER.info("M-Vave output: %s", output_name or "not found")

    input_port = mido.open_input(input_name) if input_name else None
    output_port = mido.open_output(output_name) if output_name else None
    return input_port, output_port
