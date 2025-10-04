"""Rendering helpers for the Velleman VMP400 LCD."""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

try:
    from luma.core.interface.serial import spi
    from luma.lcd.device import st7789
except Exception:  # noqa: BLE001
    spi = None
    st7789 = None

from .state import PatchChain

LOGGER = logging.getLogger(__name__)
DEFAULT_FONT = str(Path(__file__).with_name("DejaVuSans.ttf"))


class Display:
    """Handle drawing the pedal chain on the Raspberry Pi display."""

    def __init__(self, width: int = 320, height: int = 480, rotation: int = 270) -> None:
        self.width = width
        self.height = height
        self.rotation = rotation
        self._device = None
        self._font = self._load_font()
        self._init_device()

    def _init_device(self) -> None:
        if spi is None or st7789 is None:
            LOGGER.warning("luma.lcd not available, display output will be logged only")
            return
        serial_interface = spi(device=0, port=0)
        self._device = st7789(serial_interface, width=self.width, height=self.height, rotate=self.rotation)

    def _load_font(self) -> ImageFont.FreeTypeFont:
        try:
            return ImageFont.truetype(DEFAULT_FONT, 28)
        except OSError:
            LOGGER.warning("Fallback to default PIL font")
            return ImageFont.load_default()

    def show_patch(self, patch: PatchChain) -> None:
        effects = patch.active_effects()
        image = Image.new("RGB", (self.width, self.height), color="black")
        draw = ImageDraw.Draw(image)

        y = 20
        draw.text((10, y), patch.patch_name or "Unknown Patch", font=self._font, fill="white")
        y += 50

        for index, effect in enumerate(effects, start=1):
            label = f"{index}. {effect.name}"
            draw.text((20, y), label, font=self._font, fill="cyan")
            y += 40

        if self._device is None:
            LOGGER.info("Patch display:\n%s", _render_text_preview(image))
            return

        self._device.display(image)


def _render_text_preview(image: Image.Image) -> str:
    """Return a text representation of the image for console preview."""

    downscaled = image.resize((40, 30))
    pixels = downscaled.load()
    lines: list[str] = []
    for y in range(downscaled.height):
        row: list[str] = []
        for x in range(downscaled.width):
            r, g, b = pixels[x, y]
            row.append("#" if r + g + b > 0 else " ")
        lines.append("".join(row))
    return "\n".join(lines)
