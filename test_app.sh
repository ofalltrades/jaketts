#!/usr/bin/env bash

# Exit on unexpected errors, but handle handled exit codes gracefully
set -Eeuo pipefail

# Tracking test artifacts for post-execution cleanup
TEST_WAVS=()
TEST_TXT="test_input_payload.txt"

# Establish a trap cleanup loop to wipe artifacts even if tests crash midway
cleanup() {
    echo -e "\n🧹 Starting post-test environment cleanup..."
    if [ -f "$TEST_TXT" ]; then
        rm -f "$TEST_TXT"
        echo "   Deleted temporary text file: $TEST_TXT"
    fi
    for wav in "${TEST_WAVS[@]}"; do
        if [ -f "$wav" ]; then
            rm -f "$wav"
            echo "   Deleted temporary audio artifact: $wav"
        fi
    done
    echo "✅ Workspace is completely clean."
}
trap cleanup EXIT

echo "🧪 Starting Integrated CLI Testing Matrix for jaketts..."

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

if [ -z "${VIRTUAL_ENV:-}" ]; then
    echo "❌ Error: tests must run inside a virtual environment."
    echo "   Create one with: python3.12 -m venv .venv && source .venv/bin/activate"
    exit 1
fi

for command_name in python jaketts jtts; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
        echo "❌ Error: '$command_name' cannot be resolved. Run 'python -m pip install -e .' first."
        exit 1
    fi
done

for command_name in jaketts jtts; do
    command_path="$(command -v "$command_name")"
    if [[ "$command_path" != "$VIRTUAL_ENV"/bin/* ]]; then
        echo "❌ Error: '$command_name' resolves outside the active virtual environment:"
        echo "   $command_path"
        exit 1
    fi
done

module_path="$(python - <<'PYMODULE'
from pathlib import Path
import jaketts
print(Path(jaketts.__file__).resolve())
PYMODULE
)"
expected_module="$(python - <<'PYMODULE'
from pathlib import Path
print(Path('jaketts.py').resolve())
PYMODULE
)"

if [ "$module_path" != "$expected_module" ]; then
    echo "❌ Error: Python is not importing jaketts.py from this checkout:"
    echo "   $module_path"
    echo "   Run 'python -m pip install -e .' in the active virtual environment."
    exit 1
fi

expected_version="jaketts 1.0.10"
if [ "$(jaketts -v)" != "$expected_version" ] || [ "$(jtts -v)" != "$expected_version" ]; then
    echo "❌ Error: active CLI aliases are not JakeTTS 1.0.10."
    exit 1
fi

# Initialize a dummy content payload document for file integration tests
echo "In the land of Mordor where the Shadows lie." > "$TEST_TXT"

# -------------------------------------------------------------
echo -e "\n🔹 Test 1: Explicit Arguments with Custom File Output Target (-o)"
TEST_WAVS+=("test1_custom.wav")
jaketts -o test1_custom.wav am_adam "The architecture of the universe echoes with a magnificent rhythm."
if [ ! -s "test1_custom.wav" ]; then echo "❌ Test 1 Failed: Audio track missing."; exit 1; fi
echo "🎉 Test 1 Passed!"

# -------------------------------------------------------------
echo -e "\n🔹 Test 2: Inverted Order Options (Flags Last Layout Verification)"
TEST_WAVS+=("test2_inverted.wav")
jaketts am_adam "Testing dynamic argparse structural tracking." -o test2_inverted.wav
if [ ! -s "test2_inverted.wav" ]; then echo "❌ Test 2 Failed: Audio track missing."; exit 1; fi
echo "🎉 Test 2 Passed!"

# -------------------------------------------------------------
echo -e "\n🔹 Test 3: Bare Output Option Parameter Fallback Default (output.wav)"
TEST_WAVS+=("output.wav")
jaketts -o am_adam "This string maps directly into the fallback file name layout structure."
if [ ! -s "output.wav" ]; then echo "❌ Test 3 Failed: Default output file not generated."; exit 1; fi
echo "🎉 Test 3 Passed!"

# -------------------------------------------------------------
echo -e "\n🔹 Test 4: Custom Voice Selection and Custom Speed Modifier (-s)"
TEST_WAVS+=("test4_speed.wav")
jaketts af_heart -s 1.25 -o test4_speed.wav "Accelerating speech synthesis runtime limits cleanly."
if [ ! -s "test4_speed.wav" ]; then echo "❌ Test 4 Failed: Speed-modified output missing."; exit 1; fi
echo "🎉 Test 4 Passed!"

# -------------------------------------------------------------
echo -e "\n🔹 Test 5: Ingesting an Actual Text Document File Name Input"
TEST_WAVS+=("test5_file.wav")
jaketts -o test5_file.wav am_adam "$TEST_TXT"
if [ ! -s "test5_file.wav" ]; then echo "❌ Test 5 Failed: Text file ingestion broken."; exit 1; fi
echo "🎉 Test 5 Passed!"

# -------------------------------------------------------------
echo -e "\n🔹 Test 6: Ingesting a Text Document via Default Audiobook Narrator Fallback"
rm -f output.wav
jaketts -o "$TEST_TXT"
if [ ! -s "output.wav" ]; then
    echo "❌ Test 6 Failed: Shorthand text file routing broken."
    exit 1
fi
echo "🎉 Test 6 Passed!"

# -------------------------------------------------------------
echo -e "\n🔹 Test 7: Direct Speaker Playback Mode (Non-saving Live Stream Verification)"
echo "🔊 [AUDIO TEST] You should hear the deep British voice speaking next..."
jaketts "Three Rings for the Elven kings under the sky."
echo "🎉 Test 7 Passed!"

# -------------------------------------------------------------
echo -e "\n🔹 Test 8: Multi-Language Dynamic Prefix Parsing Verification"
TEST_WAVS+=("test8_ja.wav")

# Verify both successful synthesis and the actual Kokoro locale selected.
if ! test8_output="$(jaketts jf_alpha -o test8_ja.wav "こんにちは世界" 2>&1)"; then
    echo "$test8_output"
    echo "❌ Test 8 Failed: Japanese voice configuration crashed."
    exit 1
fi

echo "$test8_output"

if [ ! -s "test8_ja.wav" ]; then
    echo "❌ Test 8 Failed: Japanese output file missing or empty."
    exit 1
fi

if [[ "$test8_output" != *"Locale: ja"* ]]; then
    echo "❌ Test 8 Failed: jf_alpha did not select locale 'ja'."
    exit 1
fi

echo "🎉 Test 8 Passed!"

# -------------------------------------------------------------
echo -e "\n🔹 Test 9: Short Version Flag"
version_output="$(jaketts -v)"
if [[ "$version_output" != jaketts* ]]; then
    echo "❌ Test 9 Failed: -v did not return version."
    exit 1
fi
echo "🎉 Test 9 Passed!"

# -------------------------------------------------------------
echo -e "\n🔹 Test 10: Long Version Flag"
version_output="$(jaketts --version)"
if [[ "$version_output" != jaketts* ]]; then
    echo "❌ Test 10 Failed: --version did not return version."
    exit 1
fi
echo "🎉 Test 10 Passed!"

# -------------------------------------------------------------
echo -e "\n🔹 Test 11: Long Output Option"
TEST_WAVS+=("test11_long_output.wav")
jaketts --output test11_long_output.wav am_adam \
    "Testing the long output option."
if [ ! -s "test11_long_output.wav" ]; then
    echo "❌ Test 11 Failed."
    exit 1
fi
echo "🎉 Test 11 Passed!"

# -------------------------------------------------------------
echo -e "\n🔹 Test 12: Long Speed Option"
TEST_WAVS+=("test12_long_speed.wav")
jaketts --speed 1.15 --output test12_long_speed.wav am_adam \
    "Testing the long speed option."
if [ ! -s "test12_long_speed.wav" ]; then
    echo "❌ Test 12 Failed."
    exit 1
fi
echo "🎉 Test 12 Passed!"

# -------------------------------------------------------------
echo -e "\n🔹 Test 13: Equals Syntax"
TEST_WAVS+=("test13_equals.wav")
jaketts --output=test13_equals.wav --speed=1.1 am_adam \
    "Testing equals syntax."
if [ ! -s "test13_equals.wav" ]; then
    echo "❌ Test 13 Failed."
    exit 1
fi
echo "🎉 Test 13 Passed!"

# -------------------------------------------------------------
echo -e "\n🔹 Test 14: Short Equals Syntax"
TEST_WAVS+=("test14_short_equals.wav")
jaketts -o=test14_short_equals.wav -s=0.95 am_adam \
    "Testing short equals syntax."
if [ ! -s "test14_short_equals.wav" ]; then
    echo "❌ Test 14 Failed."
    exit 1
fi
echo "🎉 Test 14 Passed!"

# -------------------------------------------------------------
echo -e "\n🔹 Test 15: Voice Appears After Text"
TEST_WAVS+=("test15_voice_after_text.wav")
jaketts -o test15_voice_after_text.wav \
    "The voice identifier appears after this text." am_adam
if [ ! -s "test15_voice_after_text.wav" ]; then
    echo "❌ Test 15 Failed."
    exit 1
fi
echo "🎉 Test 15 Passed!"


# -------------------------------------------------------------
echo -e "\n🔹 Test 16: Bare -o Appears Last"
rm -f output.wav
jaketts am_adam \
    "The output switch occurs at the very end." -o
if [ ! -s "output.wav" ]; then
    echo "❌ Test 16 Failed."
    exit 1
fi
echo "🎉 Test 16 Passed!"

# -------------------------------------------------------------
echo -e "\n🔹 Test 17: Aggressively Mixed Argument Order"
TEST_WAVS+=("test17_mixed.wav")
jaketts \
    "Every argument is deliberately scrambled." \
    -s 1.05 \
    am_adam \
    -o test17_mixed.wav
if [ ! -s "test17_mixed.wav" ]; then
    echo "❌ Test 17 Failed."
    exit 1
fi
echo "🎉 Test 17 Passed!"


# -------------------------------------------------------------
echo -e "\n🔹 Test 18: Bare -o With Default Voice and Default Speed"
rm -f output.wav
if ! test18_output="$(jaketts -o \
    "No explicit voice was supplied in this invocation." 2>&1)"; then
    echo "$test18_output"
    echo "❌ Test 18 Failed: Default invocation crashed."
    exit 1
fi
echo "$test18_output"
if [ ! -s "output.wav" ]; then
    echo "❌ Test 18 Failed: Default output file missing or empty."
    exit 1
fi
if [[ "$test18_output" != *"Speed: 0.8x"* ]]; then
    echo "❌ Test 18 Failed: Default speed is not 0.8x."
    exit 1
fi
echo "🎉 Test 18 Passed!"

# -------------------------------------------------------------
echo -e "\n🔹 Test 19: Missing Text Must Fail"

if jaketts am_adam >/dev/null 2>&1; then
    echo "❌ Test 19 Failed: Missing text unexpectedly succeeded."
    exit 1
fi

echo "🎉 Test 19 Passed!"


# -------------------------------------------------------------
echo -e "\n🔹 Test 20: Invalid Speed Must Fail"
if jaketts am_adam -s banana \
    "This invocation must not synthesize." >/dev/null 2>&1; then
    echo "❌ Test 20 Failed: Invalid speed unexpectedly succeeded."
    exit 1
fi
echo "🎉 Test 20 Passed!"


# -------------------------------------------------------------
echo -e "\n🔹 Test 21: Exact 1.0.10 Version and Both CLI Aliases"
expected_version="jaketts 1.0.10"

if [ "$(jaketts -v)" != "$expected_version" ]; then
    echo "❌ Test 21 Failed: jaketts does not report exactly 1.0.10."
    exit 1
fi

if ! command -v jtts >/dev/null 2>&1; then
    echo "❌ Test 21 Failed: jtts alias is not installed."
    exit 1
fi

if [ "$(jtts -v)" != "$expected_version" ]; then
    echo "❌ Test 21 Failed: jtts does not report exactly 1.0.10."
    exit 1
fi

echo "🎉 Test 21 Passed!"


# -------------------------------------------------------------
echo -e "\n🔹 Test 22: Local Voice Bundle Inventory"

python - <<'PYVOICE'
import jaketts

voices = jaketts.get_available_voices()

assert len(voices) == 54, f"Expected 54 voices, found {len(voices)}"
assert jaketts.DEFAULT_VOICE == "bm_george"
assert "bm_george" in voices
assert "ff_siwis" in voices
assert "ff_sixtine" not in voices
assert "zf_xiaobei" in voices
assert "jf_alpha" in voices

print(f"   Local bundle contains {len(voices)} voices.")
print("   Current French ff_siwis present; stale ff_sixtine absent.")
PYVOICE

echo "🎉 Test 22 Passed!"


# -------------------------------------------------------------
echo -e "\n🔹 Test 23: Chinese Misaki → ONNX Synthesis Path"

TEST_WAVS+=("test23_zh.wav")

if ! test23_output="$(
    jaketts zf_xiaobei \
        -o test23_zh.wav \
        "清晨的阳光从窗户照了进来。" 2>&1
)"; then
    echo "$test23_output"
    echo "❌ Test 23 Failed: Chinese synthesis crashed."
    exit 1
fi

echo "$test23_output"

if [ ! -s "test23_zh.wav" ]; then
    echo "❌ Test 23 Failed: Chinese WAV is missing or empty."
    exit 1
fi

if [[ "$test23_output" != *"Locale: zh"* ]]; then
    echo "❌ Test 23 Failed: Chinese voice did not select locale zh."
    exit 1
fi

echo "🎉 Test 23 Passed!"


# -------------------------------------------------------------
echo -e "\n🔹 Test 24: Missing Assets Fail Locally Without Download Fallback"

python - <<'PYASSETS'
import tempfile
from pathlib import Path
import jaketts

original_candidates = jaketts._candidate_asset_dirs
original_paths = jaketts._ASSET_PATHS

try:
    with tempfile.TemporaryDirectory() as tmp:
        jaketts._ASSET_PATHS = None
        jaketts._candidate_asset_dirs = lambda: [Path(tmp)]

        try:
            jaketts.get_asset_paths()
        except RuntimeError as exc:
            message = str(exc)
            assert "could not find its local Kokoro assets" in message
            assert "does not download model or voice files while running" in message
        else:
            raise AssertionError("Missing assets unexpectedly succeeded.")
finally:
    jaketts._candidate_asset_dirs = original_candidates
    jaketts._ASSET_PATHS = original_paths

print("   Missing assets produce a local-only error.")
PYASSETS

echo "🎉 Test 24 Passed!"


# -------------------------------------------------------------
echo -e "\n🔹 Test 25: Generated WAV Structural Validation"

python - <<'PYWAV'
import numpy as np
import soundfile as sf

audio, rate = sf.read("test1_custom.wav", dtype="float32")

assert rate == 24000, f"Unexpected sample rate: {rate}"
assert audio.ndim == 1, f"Expected mono audio, got shape {audio.shape}"
assert len(audio) > 1000, "Audio is unexpectedly short."
assert np.isfinite(audio).all(), "Audio contains NaN or infinity."
assert float(np.max(np.abs(audio))) > 0.001, "Audio appears silent."

print(f"   Valid mono 24 kHz WAV with {len(audio)} samples.")
PYWAV

echo "🎉 Test 25 Passed!"


# -------------------------------------------------------------
echo -e "\n🔹 Test 26: Final Runtime Dependency Architecture"

python - <<'PYDEPS'
from importlib import metadata

requirements = metadata.requires("jaketts") or []
requirements_lower = [item.lower() for item in requirements]

assert any(item.startswith("kokoro-onnx==0.6.1") for item in requirements_lower)

for forbidden in ("torch", "transformers", "huggingface-hub", "kokoro>=", "kokoro=="):
    assert not any(
        item.startswith(forbidden) for item in requirements_lower
    ), f"Old runtime dependency still present: {forbidden}"

license_name = metadata.metadata("jaketts").get("License")
assert license_name == "0BSD", f"Unexpected package license metadata: {license_name!r}"

print("   kokoro-onnx 0.6.1 present.")
print("   Torch / Transformers / Hugging Face runtime dependencies absent.")
print("   Package license metadata is 0BSD.")
PYDEPS

echo "🎉 Test 26 Passed!"

echo -e "\n🚀 ALL INTEGRATION MATRIX TESTS PASSED SUCCESSFULLY!"
