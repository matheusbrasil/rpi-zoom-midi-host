"""Integration with the M-Vave Chocolate Plus MIDI controller."""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

import mido

from .state import FootswitchAction

LOGGER = logging.getLogger(__name__)


class MVaveListener:
    """Listen for footswitch messages and invoke callbacks."""

    def __init__(
        self,
        midi_in: mido.ports.BaseInput,
        actions: list[FootswitchAction],
        on_action: Callable[[FootswitchAction], None],
    ) -> None:
        self._midi_in = midi_in
        self._actions = {action.midi_note: action for action in actions}
        self._on_action = on_action
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        LOGGER.info("Started listening for M-Vave footswitch events")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        LOGGER.info("Stopped listening for M-Vave events")

    def _run(self) -> None:
        while not self._stop_event.is_set():
            for message in self._midi_in.iter_pending():
                if message.type == "note_on" and message.velocity > 0:
                    action = self._actions.get(message.note)
                    if action:
                        LOGGER.debug("Footswitch %s triggered", action.description)
                        self._on_action(action)
            self._stop_event.wait(0.01)
