# Signal generator


Synthetic signal generator (simulated EEG or uniform noise) that is streamed over the network with [Lab Streaming Layer (LSL)](https://labstreaminglayer.org/). It is meant to test [MEDUSA](https://www.medusabci.com/) and any other LSL receiver (LabRecorder, viewers, your own scripts) without a real amplifier.

## Installation

1. Download the installer from the **[latest GitHub release](https://github.com/medusabci/lsl-signal-generator/releases/latest)** (`signal_generator_setup_<version>.exe`) and run it.
   - By default it is installed for your user only, without administrator rights. The wizard lets you choose an installation for all users.
   - It creates a Start menu shortcut and, optionally, a desktop one.
   - To update, run the installer of the new version: it replaces the installed one.
2. Open **Signal generator**, adjust the parameters and press **Start**.

You do not need to install Python or any dependency.

## Usage

| Parameter | What it does |
|---|---|
| Stream name / type | Name and type of the LSL stream. Receivers find the stream by its name. |
| Chunk size | Samples sent together in each push (16 by default). It does not change the sample rate, only the latency and the CPU load. |
| Format | `float32`, `double64`, `int32` or `int16`. |
| Number of channels / Channel labels | Number of channels and their labels separated by `;`. When the number of channels changes (arrows, keyboard or mouse wheel) the labels are rewritten with the standard 10-20, 10-10 and 10-05 names (without `LPA`, `NAS` or `RPA`). |
| Units | Units written in the meta-data (e.g. `uV`). |
| Sample rate | Nominal sample rate. |
| Generator | `EEG (closed eyes)`: pink noise + 10 and 20 Hz tones. `EEG (open eyes)`: pink noise only. `Uniform`: white noise with configurable mean and standard deviation. The EEG generators can add the 50 Hz power-line interference and its 100 Hz harmonic. |

- The parameters are locked while transmitting and are remembered between sessions.
- The bottom bar shows whether the stream is being transmitted, the samples sent, the effective rate and whether any receiver is reading the stream (LSL does not tell which one).
- Errors and warnings are written to `logs/` (next to the program, or to `%LOCALAPPDATA%\SignalGenerator\logs` if that folder is not writable).

## How it transmits

- **Exact rate.** The chunks are sent against an absolute schedule (`start + k · chunk_size / fs`). The delay of each iteration does not accumulate, so the effective rate is the nominal one. Measured in v2.4 with 4 channels, 250 Hz and 16-sample chunks for 40 s: 250.0000 Hz (≈ 0 ppm); v2.3 gave 249.868 Hz (−528 ppm).
- **Time stamps.** Each chunk is stamped with `local_clock()` when it is pushed (like `gNEEDaccess.exe` and [signal-gtec](../signal-gtec)); LSL back-fills the previous samples with `1/fs`.
- **Pre-computed signal.** It is generated before starting (a loop of about 64 s, limited to 64 MB; it lasts a whole number of seconds when possible so that the tones are continuous when the loop restarts) and played in a loop, so sending does not depend on the cost of generating it.
- **Meta-data.** XDF/LSL conventions: per channel `label`, `unit` (and `units`, for compatibility with v2.3 and with the MEDUSA outlet) and `type`; also `manufacturer`, `acquisition` and `synchronization` (`can_drop_samples = false`). `offset_mean` is not written: there is no acquisition delay.
- **CPU.** A single sender thread that sleeps and only busy-waits for the last ~1.5 ms before each chunk: ≈ 2 % of one core with the default settings.

## Building from source

Requirements: Windows, Python 3.10, and [Inno Setup 6 or 7](https://jrsoftware.org/isinfo.php) (`winget install JRSoftware.InnoSetup`).

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

To run without building:

```powershell
.\.venv\Scripts\python src\main.py
```

To build the installer:

```powershell
.\build_release.ps1
```

The result is `release\signal_generator_setup_<version>.exe`. The version is defined in a single place, `src/version.py`. Options: `-SkipBuild` (reuses `dist\` and only rebuilds the installer) and `-SkipInstaller` (PyInstaller only).

## Structure

| Path | Content |
|---|---|
| `src/main.py` | Main window |
| `src/signal_generator.py` | Signal generators and LSL transmission |
| `src/logging_setup.py` | File logging, exceptions and native crashes |
| `src/version.py` | Version of the application |
| `src/gui/` | Style, theme, icons and interface utilities |
| `installer/signal_generator.iss` | Inno Setup script |
| `build_release.ps1` | Build and packaging |


