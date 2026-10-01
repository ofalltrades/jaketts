#!/usr/bin/env python3
import sys
import os
import argparse
import numpy as np
import soundfile as sf
import sounddevice as sd

# 1. Total framework warning and logger suppression
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
import warnings

warnings.filterwarnings("ignore")

try:
    import logging

    logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
    logging.getLogger("huggingface_hub.utils._validators").setLevel(logging.ERROR)
    logging.getLogger("huggingface_hub.hub_mixin").setLevel(logging.ERROR)
except:
    pass

from kokoro import KPipeline

try:
    from tqdm import tqdm
except ImportError:

    def tqdm(iterable, *args, **kwargs):
        return iterable


def main():
    # --- 2. Advanced Input Intercept for Shorthand Commands ---
    # If the user runs `jaketts -o story.txt` or `jaketts --output story.txt` (exactly 3 items),
    # argparse thinks story.txt is the output filename. If it's actually an existing text file,
    # we rewrite the argument layout behind the scenes so argparse parses it cleanly.
    if len(sys.argv) == 3 and sys.argv[1] in ["-o", "--output"]:
        potential_file = sys.argv[2]
        if os.path.isfile(potential_file) and not potential_file.lower().endswith(
            ".wav"
        ):
            # Convert to: ['jaketts', '-o', 'output.wav', 'story.txt']
            sys.argv = [sys.argv[0], sys.argv[1], "output.wav", potential_file]

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
        "-s",
        "--speed",
        type=float,
        default=1.0,
        help="Vocal generation speed multiplier. Defaults to 1.0.",
        metavar="MULTIPLIER",
    )

    parser.add_argument(
        "text_input", help="The actual text string to speak OR the path to a .txt file."
    )

    args = parser.parse_args()

    # Smart Input Detection
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
        pipeline = KPipeline(lang_code=lang_code, repo_id="hexgrad/Kokoro-82M")
    except Exception as e:
        print(f"❌ Failed to load pipeline: {e}")
        sys.exit(1)

    print(f"🗣️  Synthesizing text via voice '{args.voice}' (Speed: {args.speed}x)...")
    try:
        generator = pipeline(final_text, voice=args.voice, speed=args.speed)
    except Exception as e:
        print(f"❌ Error generating speech. Is '{args.voice}' a valid voice code?")
        sys.exit(1)

    # Stream Audio out loud or write seamlessly to an Output file
    if args.output is not None:
        print(f"💾 Gathering audio tracks for file output...")

        # Split text by paragraphs to initialize metrics
        paragraphs = [p for p in final_text.split("\n") if p.strip()]
        total_chunks = len(paragraphs) if paragraphs else 1

        audio_chunks = []
        pbar = tqdm(total=total_chunks, desc="Processing Sentences", unit="chunk")

        for _, _, audio in generator:
            if audio is not None:
                audio_chunks.append(audio)
                pbar.update(1)

        pbar.n = pbar.total
        pbar.refresh()
        pbar.close()

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
