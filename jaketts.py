#!/usr/bin/env python3
import sys
import os
import argparse
import numpy as np
import soundfile as sf
import sounddevice as sd
from kokoro import KPipeline


def main():
    # --- Intercept bare '-o <file>' layout ---
    # If the user typed `jaketts -o story.txt` (len == 3), argparse thinks story.txt is the output name.
    # If story.txt is actually an existing text file, we fix it by inserting 'output.wav' in between.
    if len(sys.argv) == 3 and sys.argv[1] in ["-o", "--output"]:
        potential_file = sys.argv[2]
        if os.path.isfile(potential_file) and not potential_file.endswith(".wav"):
            sys.argv.insert(2, "output.wav")

    parser = argparse.ArgumentParser(
        description="🔊 Jake's Text-to-Speech CLI utility powered by Kokoro AI Engine."
    )

    parser.add_argument(
        "-o",
        "--output",
        nargs="?",
        const="output.wav",
        default=None,
        help="Path to save the .wav file instead of playing it aloud. Defaults to 'output.wav'.",
        metavar="FILENAME",
    )

    parser.add_argument(
        "-v",
        "--voice",
        default="bm_george",
        help="The voice profile identifier to use. Defaults to 'bm_george'.",
        metavar="VOICE_ID",
    )

    parser.add_argument(
        "text_input", help="The actual text string to speak OR the path to a .txt file."
    )

    args = parser.parse_args()

    # Smart Input Detection: Check if text_input points to a real file path
    final_text = args.text_input
    if os.path.isfile(args.text_input):
        print(f"📖 Reading text from file: {os.path.abspath(args.text_input)}")
        try:
            with open(args.text_input, "r", encoding="utf-8") as f:
                final_text = f.read().strip()
        except Exception as e:
            print(f"❌ Error reading file: {e}")
            sys.exit(1)

    if not final_text:
        print("❌ Error: No text content found to synthesize.")
        sys.exit(1)

    # Determine regional language profile code dynamically
    lang_code = args.voice.lower()
    if lang_code not in ["a", "b", "e", "f", "h", "i", "j", "p", "z"]:
        lang_code = "b" if lang_code.startswith("b") else "a"

    print(f"🤖 Initializing Kokoro Engine (Locale: {lang_code})...")
    try:
        pipeline = KPipeline(lang_code=lang_code)
    except Exception as e:
        print(f"❌ Failed to load pipeline: {e}")
        sys.exit(1)

    print(f"🗣️  Processing text via voice '{args.voice}'...")
    try:
        generator = pipeline(final_text, voice=args.voice)
    except Exception as e:
        print(f"❌ Error generating speech. Is '{args.voice}' a valid voice code?")
        sys.exit(1)

    # Stream Audio out loud or write seamlessly to an Output file
    if args.output is not None:
        print(f"💾 Gathering audio tracks for file output...")
        audio_chunks = [audio for _, _, audio in generator if audio is not None]
        if not audio_chunks:
            print("❌ No audio data generated.")
            sys.exit(1)
        combined_audio = np.concatenate(audio_chunks)

        sf.write(args.output, combined_audio, 24000)
        print(f"✨ Success! Audio file written to: {os.path.abspath(args.output)}")
    else:
        print("🔊 Playing audio directly through your speakers...")
        for _, _, audio in generator:
            if audio is not None:
                sd.play(audio, samplerate=24000)
                sd.wait()


if __name__ == "__main__":
    main()
