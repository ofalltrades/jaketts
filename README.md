# 🔊 JakeTTS

`jaketts` — also available as the shorter `jtts` command — is a local text-to-speech utility for macOS powered by the open-weight **Kokoro-82M** model via ONNX Runtime.

It can play synthesized speech directly through your speakers, save WAV files, read plain-text files, switch between Kokoro voices, adjust playback speed, and launch a Qt desktop interface when run with no arguments.

The default voice is `bm_george`.

**JakeTTS 1.0.10 is the final release of the open-source application.** The JakeTTS source code remains available under 0BSD, but the project is no longer under active feature development.

<img width="1926" height="1556" alt="jttsui" src="https://github.com/user-attachments/assets/a76369e4-c193-42b3-9c34-d774bad38f50" />

## Project status

JakeTTS 1.0.10 is the final planned release. No new features, enhancement requests, or request-driven changes are planned. The repository will remain available, but JakeTTS is no longer under active development.

If you use the free/open-source JakeTTS and want to extend it, change its behavior, add platforms, or maintain it further, **fork the repository and continue from your own fork**. Defects may be addressed at the maintainer's discretion, but no ongoing maintenance or support is promised.

## Features

- 🔊 Direct speaker playback
- 💾 WAV file export
- 📖 Plain-text file input
- 🗣️ Voice selection from the installed Kokoro voice bundle
- ⏩ Adjustable speech speed with a 0.80× default
- 🌍 Kokoro voice families for English, Spanish, French, Hindi, Italian, Japanese, Brazilian Portuguese, and Mandarin Chinese
- 🖥️ Qt desktop GUI with voice, exact speed, volume, and Stop controls
- 🔒 Fully local synthesis once dependencies and runtime assets are installed — no model or voice downloads at runtime
- ⚡ `jaketts` and `jtts` command aliases
- 🇯🇵 Lightweight local Japanese support using UniDic Lite instead of a first-run full-UniDic download
- 🧠 Kokoro ONNX FP16 inference instead of the much larger PyTorch runtime

## Runtime assets

JakeTTS 1.0.10 uses two local Kokoro assets:

- `kokoro-v1.0.fp16.onnx`
- `voices-v1.0.bin`

JakeTTS never downloads these files while synthesizing speech. It looks for them in this order:

1. the directory named by `JAKETTS_ASSET_DIR`
2. an `assets` directory beside `jaketts.py`
3. `<python-prefix>/share/jaketts` (used by the Homebrew package)

Homebrew installs the assets automatically. PyPI users can install them in a stable per-user directory and point JakeTTS at it:

```bash
ASSET_DIR="$HOME/.local/share/jaketts"
mkdir -p "$ASSET_DIR"

curl -L --fail \
  -o "$ASSET_DIR/kokoro-v1.0.fp16.onnx" \
  https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.fp16.onnx

curl -L --fail \
  -o "$ASSET_DIR/voices-v1.0.bin" \
  https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin

export JAKETTS_ASSET_DIR="$ASSET_DIR"
```

The expected SHA-256 hashes are:

| Asset | SHA-256 |
| --- | --- |
| `kokoro-v1.0.fp16.onnx` | `f3a290d384fbb27966d462905c71a46cef9e5fd00516b40df32a0b4afe77ac96` |
| `voices-v1.0.bin` | `bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d` |

For a source checkout, you may instead place both files in `./assets`, which is beside `jaketts.py`.

Once dependencies and these two assets are installed, normal JakeTTS use does not require an internet connection.

## Requirements

The Python package requires Python 3.10 through Python 3.12 (`>=3.10,<3.13`). The final release was tested primarily on Python 3.12, and the Homebrew package uses Python 3.12.

Version 1.0.10 uses `kokoro-onnx` for inference. Japanese and Chinese use lightweight local Misaki G2P paths before the phonemes are passed to the same ONNX model. Other supported languages use the local eSpeak-based phonemizer included in the installed runtime.

## Installation with Homebrew

On Apple Silicon Macs running macOS 14 Sonoma or newer:

```bash
brew install ofalltrades/tap/jaketts
```

That installs the Python runtime, the local FP16 Kokoro model, the 54-voice v1.0 bundle, and both command aliases.

Verify the installation:

```bash
jtts -v
```

Launch the desktop GUI:

```bash
jtts
```

Or synthesize from the terminal:

```bash
jtts "Hello from JakeTTS"
```

The Homebrew formula is maintained at [ofalltrades/homebrew-tap](https://github.com/ofalltrades/homebrew-tap).

## Installation from PyPI

Install the Python code and dependencies:

```bash
python -m pip install jaketts
```

Then install the two runtime assets using the commands in **Runtime assets** above. Keep `JAKETTS_ASSET_DIR` set to that directory when running JakeTTS.

Both commands are installed:

```bash
jaketts --version
jtts --version
```

## Installation from GitHub

```bash
git clone https://github.com/ofalltrades/jaketts.git
cd jaketts
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Download the two runtime assets into `./assets` (using the same upstream URLs and hashes shown in **Runtime assets**). Editable mode means changes to `jaketts.py` are used immediately without reinstalling the package.

## Usage

### Launch the desktop GUI

```bash
jtts
```

The GUI launches in its own process, so the terminal prompt returns immediately while the desktop window remains open. It warms the local ONNX speech engine in a background thread.

### Speak text using the default voice

```bash
jtts "Three Rings for the Elven-kings under the sky."
```

### Choose a voice

Voice IDs can be placed before or after the text:

```bash
jtts af_sarah "Hello from an American female voice."
jtts "This uses Adam." am_adam
```

If no installed voice ID is supplied, `bm_george` is used.

### Japanese and Chinese

Japanese and Mandarin Chinese are phonemized locally and then synthesized by Kokoro through ONNX Runtime:

```bash
jtts jf_alpha "こんにちは世界"
jtts zf_xiaobei "清晨的阳光从窗户照了进来。"
```

There is no first-run dictionary or model download.

### Read a text file

```bash
jtts story.txt
jtts am_adam story.txt
```

### Save WAV audio

A bare `-o` saves to `output.wav`:

```bash
jtts -o "Save this narration."
```

Specify a filename:

```bash
jtts -o narration.wav "Save this narration."
jtts --output narration.wav am_adam "Save this narration."
```

Equals syntax is supported:

```bash
jtts --output=narration.wav "Save this narration."
```

### Change speech speed

The default is `0.8` (shown as `0.80×` in the GUI):

```bash
jtts -s 1.25 "Speak this a little faster."
jtts --speed 0.9 am_adam "Speak this a little slower."
jtts --speed=1.1 "Slightly faster speech."
```

`kokoro-onnx` exposes sentence and clause pauses independently from spoken-word speed. JakeTTS 1.0.10 uses conservative fixed pause values internally.

### Flexible argument ordering

```bash
jtts am_adam "Hello" -o hello.wav
jtts -o hello.wav "Hello" am_adam
jtts "Hello" -s 1.1 am_adam -o hello.wav
jtts am_adam "Hello" -o
```

### Show the installed version

```bash
jtts -v
jtts --version
```

## Voice reference

The voice menu and CLI voice recognition are read directly from the installed `voices-v1.0.bin` bundle rather than from a duplicated hard-coded list. The current bundle contains 54 voices.

Some useful examples include:

| Voice ID | Family | Description |
| --- | --- | --- |
| `bm_george` | British English | Default narrator |
| `bm_lewis` | British English | Male British voice |
| `bf_emma` | British English | Female British voice |
| `af_heart` | American English | Expressive female voice |
| `af_sarah` | American English | Female American voice |
| `am_adam` | American English | Male American voice |
| `ff_siwis` | French | Female French voice |
| `jf_alpha` | Japanese | Female Japanese voice |
| `pf_dora` | Brazilian Portuguese | Female Brazilian Portuguese voice |
| `zf_xiaobei` | Mandarin Chinese | Female Mandarin Chinese voice |

## Development and testing

The final source tree includes `test_app.sh`, a 26-test integration matrix. Run it from an editable install in an isolated virtual environment so the commands under test resolve to the current checkout rather than to an older global or Homebrew installation:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e .

# Put the two runtime files in ./assets, or point at an existing asset directory.
export JAKETTS_ASSET_DIR="$HOME/.local/share/jaketts"

./test_app.sh
```

The test script intentionally refuses to run against a different installed copy of JakeTTS.

## Privacy / offline behavior

JakeTTS does not use a hosted TTS API and does not fetch model or voice files during normal operation. To verify an installation, disconnect networking and synthesize or export a WAV file; all speech inference should continue to work locally.

## License

JakeTTS's own source code is released under the **BSD Zero Clause License (0BSD)**. You may use, copy, modify, distribute, or sell the JakeTTS code for any purpose, with or without fee, subject to the license text in `LICENSE`.

**0BSD applies only to JakeTTS's own code. It does not relicense the model, Python packages, native libraries, dictionaries, or other third-party components used at runtime.** The current dependency tree includes components under Apache-2.0, MIT/BSD-style licenses, LGPL, and GPL terms. In particular, `kokoro-onnx` depends on GPLv3-or-later `phonemizer` and on `espeakng-loader`, which loads the GPLv3-or-later eSpeak NG library, while PySide6/Qt and libsndfile have LGPL/commercial licensing considerations.

If you redistribute JakeTTS or build another product from it, you are responsible for complying with the licenses of the third-party components you distribute or link. Do not assume that JakeTTS's 0BSD license makes the complete runtime stack permissively licensed. See `THIRD_PARTY_NOTICES.md` in the source repository for the key licensing notes and upstream sources.
