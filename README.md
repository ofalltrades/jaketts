# 🔊 JakeTTS

`jaketts` — also available as the shorter `jtts` command — is a local text-to-speech utility for macOS powered by the open-weight **Kokoro-82M** model.

It can play synthesized speech directly through your speakers, save WAV files, read plain-text files, switch between Kokoro voices, adjust playback speed, and launch a Qt desktop interface when run with no arguments.

The default voice is `bm_george`.

**JakeTTS 1.0.10 is the final feature release of the open-source application.** The project remains available as a small, permissively licensed local TTS tool; future product development continues separately.

## Features

- 🔊 Direct speaker playback
- 💾 WAV file export
- 📖 Plain-text file input
- 🗣️ Voice selection from the installed Kokoro voice bundle
- ⏩ Adjustable speech speed with a 0.80× default
- 🌍 Kokoro voice families for English, Spanish, French, Hindi, Italian, Japanese, Portuguese, and Chinese
- 🖥️ Qt desktop GUI with voice, exact speed, volume, and Stop controls
- 🔒 Fully local synthesis after installation — no model or voice downloads at runtime
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

Homebrew installs the assets automatically. Source/PyPI users can download them once during setup:

```bash
mkdir -p assets

curl -L --fail \
  -o assets/kokoro-v1.0.fp16.onnx \
  https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.fp16.onnx

curl -L --fail \
  -o assets/voices-v1.0.bin \
  https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin
```

Once dependencies and these two assets are installed, normal JakeTTS use does not require an internet connection.

## Requirements

JakeTTS supports Python 3.10 through Python 3.12.

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

Then place the two runtime assets described above in a local directory and either put them in an `assets` directory beside a source checkout or point JakeTTS at them:

```bash
export JAKETTS_ASSET_DIR="$HOME/.local/share/jaketts"
```

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

Download the runtime assets into `./assets` using the commands in **Runtime assets** above. Editable mode means changes to `jaketts.py` are used immediately without reinstalling the package.

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

Japanese and Chinese are phonemized locally and then synthesized by Kokoro ONNX:

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

Kokoro ONNX exposes sentence and clause pauses independently from spoken-word speed. JakeTTS 1.0.10 uses conservative fixed pause values internally, leaving a clean foundation for more advanced prose-aware pacing in downstream projects.

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
| `pf_dora` | Portuguese | Female Portuguese voice |
| `zf_xiaobei` | Chinese | Female Chinese voice |

## Privacy / offline behavior

JakeTTS does not use a hosted TTS API and does not fetch model or voice files during normal operation. To verify an installation, disconnect networking and synthesize or export a WAV file; all speech inference should continue to work locally.

## License

JakeTTS itself is released under the **BSD Zero Clause License (0BSD)**. You may use, copy, modify, distribute, or sell the JakeTTS code for any purpose, with or without fee, subject to the license text in `LICENSE`.

Third-party dependencies and model assets retain their own licenses.
