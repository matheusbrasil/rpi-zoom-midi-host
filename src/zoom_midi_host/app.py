"""Application orchestration for the Raspberry Pi Zoom MIDI host."""

from __future__ import annotations

import logging
import signal
from typing import Optional

from .display import Display
from .m_vave import MVaveListener
from .midi import managed_ports, open_m_vave_ports, open_zoom_ports
from .state import FootswitchAction, PatchChain
from .usb_monitor import UsbMonitor
from .zoom_ms60b import ZoomMs60bPlus

LOGGER = logging.getLogger(__name__)


class ZoomMidiHostApp:
    """Main application that glues together USB, MIDI, and display logic."""

    def __init__(self) -> None:
        self._display = Display()
        self._monitor = UsbMonitor(on_connect=self._on_pedal_connected, on_disconnect=self._on_pedal_disconnected)
        self._pedal: Optional[ZoomMs60bPlus] = None
        self._m_vave_listener: Optional[MVaveListener] = None
        self._running = False

    def run(self) -> None:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
        self._running = True
        self._display.show_message("Waiting for Zoom MS-60B+")
        self._monitor.start()
        self._install_signal_handlers()
        LOGGER.info("Zoom MIDI host running. Waiting for devices...")
        try:
            while self._running:
                signal.pause()
        except KeyboardInterrupt:
            LOGGER.info("Shutting down due to keyboard interrupt")
        finally:
            self._monitor.stop()
            if self._m_vave_listener:
                self._m_vave_listener.stop()

    def _install_signal_handlers(self) -> None:
        signal.signal(signal.SIGTERM, self._handle_exit)
        signal.signal(signal.SIGINT, self._handle_exit)

    def _handle_exit(self, signum, frame) -> None:  # noqa: ANN001, D401
        """Signal handler that terminates the main loop."""

        LOGGER.info("Received signal %s", signum)
        self._running = False

    def _on_pedal_connected(self, event) -> None:
        LOGGER.info("Zoom pedal connected: %s", event)
        with managed_ports(open_zoom_ports) as (midi_in, midi_out):
            if midi_in is None or midi_out is None:
                LOGGER.error("Failed to open Zoom MIDI ports")
                return
            self._pedal = ZoomMs60bPlus(midi_in, midi_out)
            patch = self._pedal.fetch_patch_chain()
            if patch:
                self._display.show_patch(patch)
            else:
                self._display.show_message("Zoom MS-60B+ connected\nNo patch data")
            self._setup_m_vave()

    def _on_pedal_disconnected(self, event) -> None:
        LOGGER.info("Zoom pedal disconnected: %s", event)
        if self._m_vave_listener:
            self._m_vave_listener.stop()
            self._m_vave_listener = None
        self._pedal = None
        self._display.show_message("Waiting for Zoom MS-60B+")

    def _setup_m_vave(self) -> None:
        if self._pedal is None:
            return
        with managed_ports(open_m_vave_ports) as (midi_in, _):
            if midi_in is None:
                LOGGER.warning("M-Vave controller not detected")
                return
            actions = self._default_actions()
            self._m_vave_listener = MVaveListener(midi_in, actions, self._handle_action)
            self._m_vave_listener.start()

    def _handle_action(self, action: FootswitchAction) -> None:
        if not self._pedal:
            LOGGER.warning("Received footswitch action with no pedal connected")
            return
        if action.command == "toggle":
            assert action.argument is not None
            self._pedal.toggle_effect(action.argument, enabled=True)
        elif action.command == "bypass":
            assert action.argument is not None
            self._pedal.toggle_effect(action.argument, enabled=False)
        else:
            LOGGER.warning("Unknown footswitch command: %s", action.command)
        patch = self._pedal.fetch_patch_chain()
        if patch:
            self._display.show_patch(patch)

    @staticmethod
    def _default_actions() -> list[FootswitchAction]:
        return [
            FootswitchAction(midi_note=60, description="Enable slot 2", command="toggle", argument=1),
            FootswitchAction(midi_note=61, description="Enable slot 3", command="toggle", argument=2),
            FootswitchAction(midi_note=62, description="Bypass slot 2", command="bypass", argument=1),
            FootswitchAction(midi_note=63, description="Bypass slot 3", command="bypass", argument=2),
        ]


def run_app() -> None:
    app = ZoomMidiHostApp()
    app.run()


__all__ = ["ZoomMidiHostApp", "run_app"]
