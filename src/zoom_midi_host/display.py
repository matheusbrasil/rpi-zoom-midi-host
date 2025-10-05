"""Rendering helpers for the Velleman VMP400 LCD."""

from __future__ import annotations

import logging
from functools import lru_cache
import re
from pathlib import Path
from importlib import util

from PIL import Image, ImageDraw, ImageFont

spi = None
ili9341 = None

_SPI_SPEC = util.find_spec("luma.core.interface.serial")
_LCD_SPEC = util.find_spec("luma.lcd.device")
if _SPI_SPEC is not None and _LCD_SPEC is not None:
    from luma.core.interface.serial import spi as _spi  # type: ignore
    from luma.lcd.device import ili9341 as _ili9341  # type: ignore

    spi = _spi
    ili9341 = _ili9341

from .state import PatchChain

LOGGER = logging.getLogger(__name__)
DEFAULT_FONT = str(Path(__file__).with_name("DejaVuSans.ttf"))
EFFECT_ASSETS_DIR = Path(__file__).with_name("assets") / "effects"
MAX_VISIBLE_EFFECTS = 4
ICON_SIZE = (120, 120)
ICON_PADDING = 20

# Pin assignments follow the VMP400 manual: GPIO24 (DC) on pin 18, GPIO25 (RST) on pin 22 and
# CE0 on pin 24 for the LCD chip select. Touch panel pins remain unused by the host application.
SPI_PORT = 0
SPI_DEVICE = 0
GPIO_DC = 24
GPIO_RST = 25


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
        if spi is None or ili9341 is None:
            LOGGER.warning("luma.lcd not available, display output will be logged only")
            return
        try:
            serial_interface = spi(device=SPI_DEVICE, port=SPI_PORT, gpio_DC=GPIO_DC, gpio_RST=GPIO_RST)
            self._device = ili9341(
                serial_interface,
                width=self.width,
                height=self.height,
                rotate=self.rotation,
            )
        except ModuleNotFoundError as exc:
            LOGGER.warning(
                "Unable to initialise SPI display (%s). Install `python3-rpi.gpio` and `python3-spidev` on the Pi.",
                exc,
            )
        except Exception:  # pragma: no cover - hardware specific failure path
            LOGGER.exception("Failed to initialise SPI display, falling back to console rendering")

    def _load_font(self) -> ImageFont.FreeTypeFont:
        try:
            return ImageFont.truetype(DEFAULT_FONT, 28)
        except OSError:
            LOGGER.warning("Fallback to default PIL font")
            return ImageFont.load_default()

    def show_patch(self, patch: PatchChain) -> None:
        effects = patch.active_effects(skip_first=True, only_enabled=False)[:MAX_VISIBLE_EFFECTS]
        image = Image.new("RGB", (self.width, self.height), color="black")
        draw = ImageDraw.Draw(image)

        y = 20
        draw.text((10, y), patch.patch_name or "Unknown Patch", font=self._font, fill="white")
        y += 60

        if effects:
            self._draw_effect_grid(image, draw, effects, start_y=y)
        else:
            draw.text((20, y), "No active effects", font=self._font, fill="cyan")

        if self._device is None:
            LOGGER.info("Patch display:\n%s", _render_text_preview(image))
            return

        self._device.display(image)

    def show_message(self, message: str) -> None:
        """Render a simple status message to the display."""

        lines = [line.strip() for line in message.splitlines() if line.strip()]
        if not lines:
            lines = [""]

        image = Image.new("RGB", (self.width, self.height), color="black")
        draw = ImageDraw.Draw(image)

        total_height = 0
        line_metrics: list[tuple[int, int]] = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=self._font)
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            line_metrics.append((width, height))
            total_height += height

        spacing = 10
        total_height += spacing * (len(lines) - 1)
        current_y = max((self.height - total_height) // 2, 0)

        for line, (text_width, height) in zip(lines, line_metrics):
            x = max((self.width - text_width) // 2, 0)
            draw.text((x, current_y), line, font=self._font, fill="cyan")
            current_y += height + spacing

        if self._device is None:
            LOGGER.info("Display message:\n%s", _render_text_preview(image))
            return

        self._device.display(image)

    def _draw_effect_grid(self, image: Image.Image, draw: ImageDraw.ImageDraw, effects, start_y: int) -> None:
        columns = 2
        slot_height = ICON_SIZE[1] + 60
        slot_width = (self.width - ICON_PADDING * (columns + 1)) // columns

        for index, effect in enumerate(effects):
            row, col = divmod(index, columns)
            x = ICON_PADDING + col * (slot_width + ICON_PADDING)
            y = start_y + row * slot_height

            icon_key = effect.icon_slug or effect.name
            icon = self._load_effect_icon(icon_key, effect.name)
            if not effect.enabled:
                icon = self._dim_icon(icon)
            icon_x = x + (slot_width - ICON_SIZE[0]) // 2
            mask = None
            if icon.mode == "RGBA":
                mask = icon.split()[-1]
                icon = icon.convert("RGB")
            image.paste(icon, (icon_x, y), mask)

            label = effect.name
            text_width, _ = draw.textsize(label, font=self._font)
            text_x = x + (slot_width - text_width) // 2
            draw.text((text_x, y + ICON_SIZE[1] + 20), label, font=self._font, fill="cyan")

    def _load_effect_icon(self, effect_key: str, display_label: str) -> Image.Image:
        key = _sanitise_name(effect_key)
        icon = _cached_icon(key)
        if icon is None:
            icon = self._create_placeholder_icon(display_label)
        return icon.copy()

    def _create_placeholder_icon(self, effect_name: str) -> Image.Image:
        icon = Image.new("RGB", ICON_SIZE, color="#222222")
        draw = ImageDraw.Draw(icon)
        text = effect_name[:10]
        text_width, text_height = draw.textsize(text, font=self._font)
        draw.text(
            ((ICON_SIZE[0] - text_width) / 2, (ICON_SIZE[1] - text_height) / 2),
            text,
            font=self._font,
            fill="white",
        )
        return icon

    @staticmethod
    def _dim_icon(icon: Image.Image) -> Image.Image:
        if icon.mode != "RGBA":
            icon = icon.convert("RGBA")
        r, g, b, a = icon.split()
        dim_alpha = a.point(lambda value: int(value * 0.5))
        dimmed = Image.merge("RGBA", (r, g, b, dim_alpha))
        return dimmed


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


def _sanitise_name(effect_name: str) -> str:
    slug = re.sub(r"[^0-9a-zA-Z]+", "_", effect_name.lower()).strip("_")
    return slug


@lru_cache(maxsize=128)
def _cached_icon(key: str) -> Image.Image | None:
    path = EFFECT_ASSETS_DIR / f"{key}.png"
    if not path.exists():
        return None
    try:
        icon = Image.open(path)
        if icon.mode not in {"RGB", "RGBA"}:
            icon = icon.convert("RGBA")
        if icon.size != ICON_SIZE:
            icon = icon.resize(ICON_SIZE, Image.LANCZOS)
        return icon
    except OSError:
        LOGGER.warning("Failed to load icon for %s", key)
        return None
