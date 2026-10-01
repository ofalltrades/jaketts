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

# Ensure binary execution shortcut exists inside python environment paths
if ! command -v jaketts &> /dev/null; then
    echo "❌ Error: 'jaketts' executable shortcut cannot be resolved. Did you run 'pip install -e .' first?"
    exit 1
fi

# Initialize a dummy content payload document for file integration tests
echo "In the land of Mordor where the Shadows lie." > "$TEST_TXT"

# -------------------------------------------------------------
echo -e "\n🔹 Test 1: Explicit Arguments with Custom File Output Target (-o)"
TEST_WAVS+=("test1_custom.wav")
jaketts -o test1_custom.wav -v am_adam "The architecture of the universe echoes with a magnificent rhythm."
if [ ! -f "test1_custom.wav" ]; then echo "❌ Test 1 Failed: Audio track missing."; exit 1; fi
echo "🎉 Test 1 Passed!"

# -------------------------------------------------------------
echo -e "\n🔹 Test 2: Inverted Order Options (Flags Last Layout Verification)"
TEST_WAVS+=("test2_inverted.wav")
jaketts -v am_adam "Testing dynamic argparse structural tracking." -o test2_inverted.wav
if [ ! -f "test2_inverted.wav" ]; then echo "❌ Test 2 Failed: Audio track missing."; exit 1; fi
echo "🎉 Test 2 Passed!"

# -------------------------------------------------------------
echo -e "\n🔹 Test 3: Bare Output Option Parameter Fallback Default (output.wav)"
TEST_WAVS+=("output.wav")
jaketts -o -v am_adam "This string maps directly into the fallback file name layout structure."
if [ ! -f "output.wav" ]; then echo "❌ Test 3 Failed: Default output file not generated."; exit 1; fi
echo "🎉 Test 3 Passed!"

# -------------------------------------------------------------
echo -e "\n🔹 Test 4: Custom Voice Selection and Custom Speed Modifiers (-v, -s)"
TEST_WAVS+=("test4_speed.wav")
jaketts -v af_heart -s 1.25 -o test4_speed.wav "Accelerating speech synthesis runtime limits cleanly."
if [ ! -f "test4_speed.wav" ]; then echo "❌ Test 4 Failed: Speed-modified output missing."; exit 1; fi
echo "🎉 Test 4 Passed!"

# -------------------------------------------------------------
echo -e "\n🔹 Test 5: Ingesting an Actual Text Document File Name Input"
TEST_WAVS+=("test5_file.wav")
jaketts -o test5_file.wav -v am_adam "$TEST_TXT"
if [ ! -f "test5_file.wav" ]; then echo "❌ Test 5 Failed: Text file ingestion broken."; exit 1; fi
echo "🎉 Test 5 Passed!"

# -------------------------------------------------------------
echo -e "\n🔹 Test 6: Ingesting a Text Document via Default Audiobook Narrator Fallback"
# Passing -o by itself triggers output.wav, allowing your payload filename to satisfy the text position cleanly
jaketts -o "$TEST_TXT"
if [ ! -f "output.wav" ]; then echo "❌ Test 6 Failed: Shorthand text file routing broken."; exit 1; fi
echo "🎉 Test 6 Passed!"

# -------------------------------------------------------------
echo -e "\n🔹 Test 7: Direct Speaker Playback Mode (Non-saving Live Stream Verification)"
echo "🔊 [AUDIO TEST] You should hear the deep British voice speaking next..."
jaketts "Three Rings for the Elven kings under the sky."
echo "🎉 Test 7 Passed!"

# -------------------------------------------------------------
echo -e "\n🔹 Test 8: Multi-Language Dynamic Prefix Parsing Verification"
TEST_WAVS+=("test8_ja.wav")
# Verifies that passing a non-English voice code dynamically maps languages cleanly in the backend
jaketts -v jf_alpha -o test8_ja.wav "こんにちは世界"
if [ ! -f "test8_ja.wav" ]; then echo "❌ Test 8 Failed: Japanese voice configuration crashed."; exit 1; fi
echo "🎉 Test 8 Passed!"

echo -e "\n🚀 ALL INTEGRATION MATRIX TESTS PASSED SUCCESSFULLY!"
