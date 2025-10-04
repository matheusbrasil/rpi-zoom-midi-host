"""Configuration values and constants for the Zoom MIDI host."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple


@dataclass(frozen=True)
class PedalModel:
    """Information about a supported Zoom pedal."""

    name: str
    vendor_id: int
    product_ids: Tuple[int, ...]
    midi_port_keywords: Tuple[str, ...]


PEDAL_MODELS: Dict[str, PedalModel] = {
    "MS-60B+": PedalModel(
        name="Zoom MS-60B+",
        vendor_id=0x1686,
        product_ids=(0x01AD, 0x01AE),
        midi_port_keywords=("ZOOM MS-60B+", "MS-60B+"),
    ),
}

SUPPORTED_PEDAL_IDS: List[Tuple[int, int]] = [
    (model.vendor_id, product_id)
    for model in PEDAL_MODELS.values()
    for product_id in model.product_ids
]


def all_midi_keywords() -> Iterable[str]:
    """Return an iterable of all MIDI port keywords used for detection."""

    for model in PEDAL_MODELS.values():
        yield from model.midi_port_keywords
