# 🔊 jaketts

`jaketts` (and its short alias `jtts`) is a lightning-fast, ultra-realistic command-line text-to-speech utility for macOS. Powered by the open-weight **Kokoro-82M** neural engine, it synthesizes highly natural, human-like narration directly in your terminal—completely locally, completely offline, and without requiring any API keys.

By default, it features a rich, deep British voice (`bm_george`) optimized for storytelling and audiobook-style ingestion.

---

## ✨ Features
* 🔊 **Live Playback:** Streams synthesized speech directly through your default Mac speakers using system memory.
* 💾 **Audio Export:** Automatically stiches sentence fragments together to output crisp, high-fidelity `.wav` files via the `-o` or `--output` flags.
* 📖 **Smart Input Handling:** Accepts raw text strings or directly parses `.txt` files seamlessly.
* 🌍 **Global Execution:** Runs from any directory on your machine after running a single setup script.

---

## 🛠️ Prerequisites & Installation

### 1. Install System Dependencies
`jaketts` relies on `espeak-ng` for its phonetic mapping backend. Install it via Homebrew:
```bash
brew install espeak-ng
```

### 2. Clone the Repository & Configure Python
Because underlying text processing tools require pre-compiled binaries, we **strongly recommend** running this tool using a stable **Python 3.11 or 3.12** environment (managed easily via `mise` or native virtual environments).

```bash
# Clone the workspace
git clone https://github.com
cd jaketts

# (Optional) If using mise, lock this folder to Python 3.12
mise use python@3.12

# Initialize your local application sandbox
python -m venv .venv
source .venv/bin/activate

# Install requirements
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

### 3. Make the Command Global
Run the included installation script to register `jaketts` and `jtts` directly inside your machine's system execution paths:
```bash
chmod +x install.sh
./install.sh
```

---

## 🚀 Usage Examples

*Note: The very first time you execute a command, the app will automatically download the ~340MB neural model weights. Subsequent runs will process completely offline and execute instantly.*

### Basic Shorthand Execution (Live Playback)
Pass any text string directly to your shorter alias:
```bash
jtts "Three Rings for the Elven-kings under the sky, Seven for the Dwarf-lords in their halls of stone."
```

### Reading from Text Files
Pass a text file to read it straight out loud over your speakers:
```bash
jtts story.txt
```

### Saving Audio Files
To bypass the speakers and save directly to an output file, use the `-o` or `--output` flag:
```bash
# Saves the track using the default name 'output.wav'
jtts -o story.txt

# Saves the track using a custom file name
jtts -o fantasy_intro.wav "Deep in the land of Mordor where the Shadows lie."
```

### Overriding the Default Voice
If you want to shift away from the deep British male voice (`bm_george`), you can explicitly pass an alternative voice ID using the `-v` flag:
```bash
# Switch to a conversational American Female profile
jtts -v af_sarah "Hello from a clear American voice configuration."
```

---

## 🎛️ Voice Directory Reference
You can swap to any of Kokoro's built-in regional presets using the `-v` flag. Highly recommended profiles include:

| Voice ID | Accent | Gender | Best Used For... |
| :--- | :--- | :--- | :--- |
| `bm_george` | British | Male | **[Default]** Deep, steady, and clear audiobook tone. |
| `bm_lewis` | British | Male | Warm, documentary-ready cinematic narrator. |
| `bf_emma` | British | Female | Crisp, highly professional narrative spacing. |
| `af_heart` | American | Female | Highly melodic, emotional, and expressive. |
| `am_adam` | American | Male | Deep, classic American broadcast tone. |
