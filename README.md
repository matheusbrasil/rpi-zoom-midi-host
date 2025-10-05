# rpi-zoom-midi-host

A Raspberry Pi based MIDI host tailored for the **Zoom MS-60B+** bass multi-effect and the **M-Vave Chocolate Plus** footswitch controller.

The application runs as a small service on the Pi, automatically detects when the pedal is connected, renders the current patch chain on the Velleman VMP400 3.5" LCD, and maps the external footswitch buttons to useful MIDI commands for the pedal.

> **Note**: The project is inspired by and relies on public knowledge gathered from the following community projects: [ZeroPedal](https://github.com/matheusbrasil/zeropedal), [ZoomPedalFun](https://github.com/matheusbrasil/ZoomPedalFun), [zoom-zt2](https://github.com/matheusbrasil/zoom-zt2), [zoom-explorer](https://github.com/matheusbrasil/zoom-explorer) and the accompanying [Zoom SysEx gist](https://gist.github.com/matheusbrasil/d0ef99165ae88e6148c7abdf8af79930).

## Features

* Detects the Zoom MS-60B+ as soon as it is plugged into the Pi (USB Host mode).
* Opens MIDI in/out ports for both the pedal and the M-Vave controller.
* Requests the current patch chain and displays up to four enabled effects (skipping the input slot) with artwork on the VMP400 LCD.
* Offers a minimal footswitch mapping (enable/bypass slots) that can be extended for more complex workflows.
* Falls back to console previews when the LCD libraries are not available, enabling development on desktops.

## Hardware setup

1. Raspberry Pi with USB host capability (tested with Pi 4 Model B).
2. Velleman VMP400 3.5" display (SPI interface).
3. Zoom MS-60B+ pedal connected via USB.
4. M-Vave Chocolate Plus connected via USB.
5. Optional powered USB hub if the pedal requires additional current.

Follow Velleman's documentation to wire the SPI display. The default pin mapping in `luma.lcd` assumes CE0 on `/dev/spidev0.0` and the backlight pin wired to BCM 18.

## Preparing the Raspberry Pi

1. Flash the latest **Raspberry Pi OS Lite** image to a microSD card and boot the Pi.
2. Update the base system and install system dependencies required by Pillow, RtMidi and the SPI display drivers:

   ```bash
   sudo apt update
   sudo apt full-upgrade -y
   sudo apt install -y python3 python3-pip python3-venv python3-dev libopenjp2-7 libtiff5 libatlas-base-dev \
       libjpeg-dev zlib1g-dev libfreetype6-dev liblcms2-dev libharfbuzz-dev libfribidi-dev libxcb1 \
       poppler-utils imagemagick git
   ```

3. Enable the hardware interfaces required by the pedal chain:

   ```bash
   sudo raspi-config nonint do_spi 0   # Enable SPI for the VMP400
   sudo raspi-config nonint do_i2c 0   # Optional: keep disabled if unused
   sudo raspi-config nonint do_ssh 0   # Optional but recommended for remote administration
   ```

   Reboot the Pi once the interfaces have been enabled.

4. Connect the VMP400 to the SPI pins (3V3, GND, SCLK, MOSI, MISO, CE0 and BCM18 for the backlight) and plug the Zoom pedal and M-Vave controller into the USB ports. A powered hub is strongly recommended if the pedal draws additional current while enumerating.

5. Clone this repository onto the Pi and follow the software setup instructions below.

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

### Effect artwork

The application renders the active effect chain using the artwork from Zoom's [official MS-60B+ FX list](https://zoomcorp.com/media/documents/E_MS-60Bplus_FX-list.pdf).  **The images are not distributed with the repository** to keep the tree free of large binary assets.  Place your own copies under `src/zoom_midi_host/assets/effects` using a *slugified* version of the effect name (e.g. `Bass Muff` → `bass_muff.png`).

To install or refresh the artwork:

1. Download the PDF to your workstation or Pi.
2. Extract the embedded images using `pdfimages`:

   ```bash
   mkdir -p artwork
   pdfimages -png E_MS-60Bplus_FX-list.pdf artwork/effect
   ```

3. Review the extracted PNG files, rename them to match the effect slugs and copy them to `src/zoom_midi_host/assets/effects/`.
4. Add a new entry to `zoom_midi_host/effect_catalog.py` so the firmware can associate the effect ID with the image slug.

During development or when an icon is missing the renderer falls back to a text placeholder, so the application keeps working even with an incomplete icon set.

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
