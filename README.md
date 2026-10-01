# 🔊 jaketts

`jaketts` — also available as the shorter `jtts` command — is a local text-to-speech utility for macOS powered by the open-weight **Kokoro-82M** model.

It can play synthesized speech directly through your speakers, save WAV files, read plain-text files, switch between Kokoro voices, adjust playback speed, and launch a small Tkinter desktop interface when run with no arguments.

The default voice is `bm_george`.

## Features

- 🔊 Direct speaker playback
- 💾 WAV file export
- 📖 Plain-text file input
- 🗣️ Optionless voice selection
- ⏩ Adjustable speech speed
- 🌍 Multiple Kokoro language/voice families
- 🖥️ Native Tkinter GUI when launched without arguments
- 🔒 Local synthesis with no API key required
- ⚡ `jaketts` and `jtts` command aliases
- 🇯🇵 Automatic one-time Japanese dictionary setup when a Japanese voice is first used

## Requirements

`jaketts` currently supports Python 3.10 through Python 3.12.

## Installation from PyPI

Install the published package into your preferred Python environment:

```bash
python -m pip install jaketts
```

That installs both commands:

```bash
jaketts --version
jtts --version
```

Japanese support uses the full UniDic dictionary. The required Python packages are installed by pip, and the first time you select a Japanese voice, `jaketts` automatically downloads the UniDic dictionary into the same Python environment. This is a one-time download of roughly 526 MB.

## Installation from GitHub

Clone the repository, enter it, and install it in editable mode:

```bash
git clone https://github.com/ofalltrades/jaketts.git
cd jaketts
python -m pip install -e .
```

Editable mode means changes to `jaketts.py` are used immediately without reinstalling the package. Re-run `python -m pip install -e .` after changing package metadata or dependencies.

If you prefer an isolated virtual environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

To update a source checkout later:

```bash
git pull --ff-only origin main
```

If the update changed dependencies or package metadata, follow it with:

```bash
python -m pip install -e .
```

## Usage

### Launch the desktop GUI

Run either command with no arguments:

```bash
jaketts
```

or:

```bash
jtts
```

### Speak text using the default voice

```bash
jtts "Three Rings for the Elven-kings under the sky."
```

### Choose a voice

Voice IDs are passed directly without a `--voice` flag:

```bash
jtts af_sarah "Hello from an American female voice."
```

```bash
jtts am_adam "Hello from an American male voice."
```

The voice can appear before or after the text:

```bash
jtts "This also uses Adam." am_adam
```

If no recognized voice ID is supplied, `bm_george` is used.

### Japanese voices

Japanese voices work without a separate setup command:

```bash
jtts jf_alpha "こんにちは世界"
```

On the first Japanese invocation only, `jaketts` downloads the full UniDic dictionary automatically. Later Japanese invocations reuse the downloaded dictionary.

### Read a text file

```bash
jtts story.txt
```

With an explicit voice:

```bash
jtts am_adam story.txt
```

### Save to the default output file

A bare `-o` or `--output` saves to `output.wav`:

```bash
jtts -o "Save this narration."
```

This also works when a voice immediately follows `-o`:

```bash
jtts -o am_adam "Save this using Adam."
```

### Save to a custom WAV file

```bash
jtts -o narration.wav "Save this narration."
```

or:

```bash
jtts --output narration.wav am_adam "Save this narration."
```

Equals syntax is also supported:

```bash
jtts --output=narration.wav "Save this narration."
```

### Change speech speed

```bash
jtts -s 1.25 "Speak this a little faster."
```

```bash
jtts --speed 0.9 am_adam "Speak this a little slower."
```

Equals syntax is supported as well:

```bash
jtts --speed=1.1 "Slightly faster speech."
```

### Flexible argument ordering

The CLI normalizes recognized options and voice IDs before handing them to `argparse`, so these layouts are valid:

```bash
jtts am_adam "Hello" -o hello.wav
jtts -o hello.wav "Hello" am_adam
jtts "Hello" -s 1.1 am_adam -o hello.wav
jtts am_adam "Hello" -o
```

### Show the installed version

`-v` is the version flag:

```bash
jtts -v
```

or:

```bash
jtts --version
```

## Voice reference

Some commonly useful Kokoro voices include:

| Voice ID | Family | Description |
| --- | --- | --- |
| `bm_george` | British English | Default narrator |
| `bm_lewis` | British English | Male British voice |
| `bf_emma` | British English | Female British voice |
| `af_heart` | American English | Expressive female voice |
| `af_sarah` | American English | Female American voice |
| `am_adam` | American English | Male American voice |
| `ff_sixtine` | French | Female French voice |
| `jf_alpha` | Japanese | Female Japanese voice |
| `pf_doris` | Portuguese | Female Portuguese voice |
| `zf_xiaobei` | Chinese | Female Chinese voice |

The complete supported voice list is defined in `VOICE_WHITELIST` inside `jaketts.py` and is also available in the desktop GUI.

## Testing

The repository includes an integration test matrix covering output routing, flexible argument ordering, speed options, version flags, text-file input, default voice behavior, and multilingual voice routing.

Run it with:

```bash
./test_app.sh
```

The test script creates temporary WAV/text artifacts and removes them automatically when the test run exits.

## Development

Install the clone in editable mode:

```bash
python -m pip install -e .
```

The package version is defined in `setup.py`. `jaketts.py` reads the installed package metadata using `importlib.metadata`, so the runtime version output does not need a second hardcoded version string.

Before building a release:

```bash
./test_app.sh
rm -rf dist build *.egg-info
python -m build
python -m twine check dist/*
```

## License

See `LICENSE` for the project's license terms.
