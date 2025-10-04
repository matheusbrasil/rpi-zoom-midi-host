"""Monitor USB devices to detect supported Zoom pedals."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

import usb.core
import usb.util

from .config import SUPPORTED_PEDAL_IDS

LOGGER = logging.getLogger(__name__)


@dataclass
class UsbEvent:
    """Represents a USB device connection event."""

    vendor_id: int
    product_id: int

    @property
    def id_tuple(self) -> tuple[int, int]:
        return (self.vendor_id, self.product_id)


class UsbMonitor:
    """Poll the USB bus looking for supported pedals."""

    def __init__(
        self,
        poll_interval: float = 1.0,
        on_connect: Optional[Callable[[UsbEvent], None]] = None,
        on_disconnect: Optional[Callable[[UsbEvent], None]] = None,
    ) -> None:
        self.poll_interval = poll_interval
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._connected: set[tuple[int, int]] = set()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        LOGGER.debug("USB monitor started")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        LOGGER.debug("USB monitor stopped")

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._scan()
            except Exception as exc:  # noqa: BLE001 - keep thread alive
                LOGGER.exception("USB monitor error: %s", exc)
            time.sleep(self.poll_interval)

    def _scan(self) -> None:
        current = set(iter_supported_devices())
        new = current - self._connected
        removed = self._connected - current

        for vendor_id, product_id in new:
            LOGGER.info("Detected supported Zoom pedal: %04x:%04x", vendor_id, product_id)
            if self.on_connect:
                self.on_connect(UsbEvent(vendor_id, product_id))

        for vendor_id, product_id in removed:
            LOGGER.info(
                "Zoom pedal disconnected: %04x:%04x", vendor_id, product_id
            )
            if self.on_disconnect:
                self.on_disconnect(UsbEvent(vendor_id, product_id))

        self._connected = current


def iter_supported_devices() -> Iterable[tuple[int, int]]:
    """Yield vendor/product ids for connected pedals that we support."""

    for device in usb.core.find(find_all=True):
        vendor_id = int(device.idVendor)
        product_id = int(device.idProduct)
        if (vendor_id, product_id) in SUPPORTED_PEDAL_IDS:
            yield (vendor_id, product_id)
