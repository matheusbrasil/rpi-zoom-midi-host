# rpi-zoom-midi-host

A Raspberry Pi based MIDI host tailored for the **Zoom MS-60B+** bass multi-effect and the **M-Vave Chocolate Plus** footswitch controller.

The application runs as a small service on the Pi, automatically detects when the pedal is connected, renders the current patch chain on the Velleman VMP400 3.5" LCD, and maps the external footswitch buttons to useful MIDI commands for the pedal.

> **Note**: The project is inspired by and relies on public knowledge gathered from the following community projects: [ZeroPedal](https://github.com/matheusbrasil/zeropedal), [ZoomPedalFun](https://github.com/matheusbrasil/ZoomPedalFun), [zoom-zt2](https://github.com/matheusbrasil/zoom-zt2), [zoom-explorer](https://github.com/matheusbrasil/zoom-explorer) and the accompanying [Zoom SysEx gist](https://gist.github.com/matheusbrasil/d0ef99165ae88e6148c7abdf8af79930).

## Features

* Detects the Zoom MS-60B+ as soon as it is plugged into the Pi (USB Host mode).
* Opens MIDI in/out ports for both the pedal and the M-Vave controller.
* Requests the current patch chain and displays all enabled effects except the input slot on the VMP400 LCD.
* Offers a minimal footswitch mapping (enable/bypass slots) that can be extended for more complex workflows.
* Falls back to console previews when the LCD libraries are not available, enabling development on desktops.

## Hardware setup

1. Raspberry Pi with USB host capability (tested with Pi 4 Model B).
2. Velleman VMP400 3.5" display (SPI interface).
3. Zoom MS-60B+ pedal connected via USB.
4. M-Vave Chocolate Plus connected via USB.
5. Optional powered USB hub if the pedal requires additional current.

Follow Velleman's documentation to wire the SPI display. The default pin mapping in `luma.lcd` assumes CE0 on `/dev/spidev0.0` and the backlight pin wired to BCM 18.

## Software setup

```bash
sudo apt update
sudo apt install python3 python3-pip python3-dev libopenjp2-7 libtiff5 libatlas-base-dev
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install .
```

To run the service directly:

```bash
source .venv/bin/activate
zoom-midi-host
```

On first start the application will:

1. Start a background USB watcher.
2. Wait for the MS-60B+ to appear.
3. Query the current patch and effect chain.
4. Render the chain on the LCD (or console when the LCD stack is missing).
5. Attach to the M-Vave Chocolate Plus and begin listening for footswitch events.

## Footswitch mapping

The default mapping expects the M-Vave Chocolate Plus to emit MIDI notes 60–63 on button presses:

| Button | MIDI note | Action |
| ------ | --------- | ------ |
| A | 60 | Enable effect slot 2 |
| B | 61 | Enable effect slot 3 |
| C | 62 | Bypass effect slot 2 |
| D | 63 | Bypass effect slot 3 |

You can customise the mapping by editing `_default_actions()` in `src/zoom_midi_host/app.py`.

## Development

Format and lint the code using the optional dependencies:

```bash
pip install .[dev]
ruff check src
black src
mypy src
```

Unit tests (if/when added) will live under the `tests/` directory.

## Roadmap

* Integrate full parameter parsing based on Zoom's SysEx docs.
* Persist preferred footswitch mappings and patch snapshots.
* Provide a GTK based configuration UI when running over SSH.
* Add systemd unit files for auto-starting on boot.
