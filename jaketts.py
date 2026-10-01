#!/usr/bin/env python3
import sys
import os
import argparse
import re
import numpy as np
import soundfile as sf
import sounddevice as sd

# Silence torch, tokenizer, and huggingface framework warnings completely
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
import warnings

warnings.filterwarnings("ignore")

VOICE_WHITELIST = {
    "af_heart",
    "af_sarah",
    "af_bella",
    "af_nicole",
    "af_sky",
    "af_alloy",
    "af_aoede",
    "af_jessica",
    "af_river",
    "am_adam",
    "am_michael",
    "am_echo",
    "am_eric",
    "am_fenrir",
    "am_liam",
    "am_onizuka",
    "am_puck",
    "am_santa",
    "bm_george",
    "bm_lewis",
    "bf_emma",
    "bf_isabella",
    "bm_fable",
    "bm_daniel",
    "bf_alice",
    "bf_lily",
    "ef_dora",
    "em_alex",
    "ff_sixtine",
    "fm_julien",
    "hf_ananya",
    "hf_kavya",
    "hm_anshul",
    "hm_shiwani",
    "if_sara",
    "im_nicola",
    "jf_alpha",
    "jf_glowing",
    "jf_neutral",
    "jf_reader",
    "jm_kanta",
    "pf_doris",
    "pm_ramon",
    "zf_xiaobei",
    "zf_xiaoni",
    "zf_xiaoxiao",
    "zf_xiaoyi",
    "zm_yunjian",
    "zm_yunxi",
    "zm_yunxia",
    "zm_yunyang",
}

PYTHON_VERSION = "1.0.4"


try:
    import logging

    # Silence the standard huggingface_hub loggers
    logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
    logging.getLogger("huggingface_hub.utils._validators").setLevel(logging.ERROR)
    logging.getLogger("huggingface_hub.hub_mixin").setLevel(logging.ERROR)

    # Silence the explicit unauthenticated warning submodule
    logging.getLogger("huggingface_hub.utils._auth").setLevel(logging.ERROR)
except:
    pass

# --- SILENT CORE IMPORT BLOCK ---
import contextlib

with contextlib.redirect_stderr(open(os.devnull, "w")):
    # This temporarily redirects all library boot warnings straight to the trash
    from kokoro import KPipeline

try:
    from tqdm import tqdm
except ImportError:

    def tqdm(iterable, *args, **kwargs):
        return iterable


# --- BATCH PROCESSING PIPELINE ---
def process_text_in_batches(pipeline, text, voice, speed, pbar=None):
    """
    Safely breaks text into smaller paragraph blocks to prevent
    memory exhaustion on massive inputs.
    """
    paragraphs = [p.strip() for p in re.split(r"\n+", text) if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    audio_chunks = []

    for para in paragraphs:
        try:
            generator = pipeline(para, voice=voice, speed=speed)
            for _, _, audio in generator:
                if audio is not None:
                    audio_chunks.append(audio)
            if pbar:
                pbar.update(1)
        except Exception as e:
            print(f"\n⚠️ Warning: Failed to synthesize segment: {e}")
            continue

    return audio_chunks


# --- NATIVE DESKTOP GUI APP ---
def launch_desktop_gui():
    """
    Launches a modern, themed Tkinter desktop interface.
    Only runs if the user executes the command with zero parameters.
    """
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    import threading

    root = tk.Tk()
    root.title("🔊 jaketts - Text to Speech")
    root.geometry("600x500")
    root.minsize(500, 400)

    style = ttk.Style(root)
    style.theme_use("clam" if sys.platform == "darwin" else "default")

    main_frame = ttk.Frame(root, padding="15")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(
        main_frame, text="Enter Text or Load a File:", font=("Helvetica", 12, "bold")
    ).pack(anchor=tk.W, pady=(0, 5))

    container = ttk.Frame(main_frame)
    container.pack(fill=tk.BOTH, expand=True)

    text_scroll = ttk.Scrollbar(container)
    text_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    text_box = tk.Text(
        container,
        yscrollcommand=text_scroll.set,
        wrap=tk.WORD,
        font=("Helvetica", 11),
        height=10,
    )
    text_box.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
    text_scroll.config(command=text_box.yview)

    control_frame = ttk.Frame(main_frame, padding="10")
    control_frame.pack(fill=tk.X, pady=10)

    ttk.Label(control_frame, text="Voice:").grid(row=0, column=0, sticky=tk.W, padx=5)
    voice_var = tk.StringVar(value="bm_george")
    voice_dropdown = ttk.Combobox(
        control_frame, textvariable=voice_var, state="readonly", width=12
    )
    voice_dropdown["values"] = (
        "[en-us] af_heart",
        "[en-us] af_sarah",
        "[en-us] af_bella",
        "[en-us] af_nicole",
        "[en-us] af_sky",
        "[en-us] af_alloy",
        "[en-us] af_aoede",
        "[en-us] af_jessica",
        "[en-us] af_river",
        "[en-us] am_adam",
        "[en-us] am_michael",
        "[en-us] am_echo",
        "[en-us] am_eric",
        "[en-us] am_fenrir",
        "[en-us] am_liam",
        "[en-us] am_onizuka",
        "[en-us] am_puck",
        "[en-us] am_santa",
        "[en-gb] bm_george",
        "[en-gb] bm_lewis",
        "[en-gb] bf_emma",
        "[en-gb] bf_isabella",
        "[en-gb] bm_fable",
        "[en-gb] bm_daniel",
        "[en-gb] bf_alice",
        "[en-gb] bf_lily",
        "[es] ef_dora",
        "[es] em_alex",
        "[fr] ff_sixtine",
        "[fr] fm_julien",
        "[hi] hf_ananya",
        "[hi] hf_kavya",
        "[hi] hm_anshul",
        "[hi] hm_shiwani",
        "[it] if_sara",
        "[it] im_nicola",
        "[ja] jf_alpha",
        "[ja] jf_glowing",
        "[ja] jf_neutral",
        "[ja] jf_reader",
        "[ja] jm_kanta",
        "[pt] pf_doris",
        "[pt] pm_ramon",
        "[zh] zf_xiaobei",
        "[zh] zf_xiaoni",
        "[zh] zf_xiaoxiao",
        "[zh] zf_xiaoyi",
        "[zh] zm_yunjian",
        "[zh] zm_yunxi",
        "[zh] zm_yunxia",
        "[zh] zm_yunyang",
    )
    voice_dropdown.grid(row=0, column=1, padx=5, sticky=tk.W)

    ttk.Label(control_frame, text="Speed:").grid(row=0, column=2, sticky=tk.W, padx=15)
    speed_var = tk.DoubleVar(value=1.0)
    speed_scale = ttk.Scale(
        control_frame,
        from_=0.5,
        to=2.0,
        variable=speed_var,
        orient=tk.HORIZONTAL,
        length=120,
    )
    speed_scale.grid(row=0, column=3, padx=5, sticky=tk.W)

    speed_label = ttk.Label(control_frame, text="1.0x")
    speed_label.grid(row=0, column=4, padx=2)

    def update_speed_label(*args):
        speed_label.config(text=f"{speed_var.get():.2f}x")

    speed_var.trace_add("write", update_speed_label)

    progress_bar = ttk.Progressbar(main_frame, orient=tk.HORIZONTAL, mode="determinate")
    progress_bar.pack(fill=tk.X, pady=5)

    status_label = ttk.Label(main_frame, text="Ready", font=("Helvetica", 10, "italic"))
    status_label.pack(anchor=tk.W, pady=2)

    def open_text_file():
        file_path = filedialog.askopenfilename(
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                text_box.delete("1.0", tk.END)
                text_box.insert("1.0", content)
                status_label.config(
                    text=f"📖 Loaded file: {os.path.basename(file_path)}"
                )
            except Exception as e:
                messagebox.showerror("Error", f"Failed to read text file:\n{e}")

    def run_synthesis(action_type):
        input_text = text_box.get("1.0", tk.END).strip()
        if not input_text:
            messagebox.showwarning(
                "Warning", "Please provide or load some text content first!"
            )
            return

        dropdown_selection = voice_var.get()
        # Extracts the raw voice name from the end (e.g., "af_heart")
        voice = dropdown_selection.split()[-1]

        # Pulls the prefix inside the brackets to set the language code (a, b, e, f, h, i, j, p, z)
        prefix = dropdown_selection.split("]")[0].replace("[", "").strip()
        if "-" in prefix:
            # Safely converts 'en-us' to 'a' and 'en-gb' to 'b'
            lang_code = "a" if prefix.endswith("us") else "b"
        else:
            # Takes the first letter for other locales ('es' -> 'e', 'ja' -> 'j')
            lang_code = prefix[0]

        speed = speed_var.get()

        def worker():
            try:
                status_label.config(text="🤖 Loading AI Neural Engine Checkpoints...")
                progress_bar.config(mode="indet")
                progress_bar.start(10)

                pipeline = KPipeline(lang_code=lang_code, repo_id="hexgrad/Kokoro-82M")

                paragraphs = [p for p in input_text.split("\n") if p.strip()]
                total_p = len(paragraphs) if paragraphs else 1

                progress_bar.stop()
                progress_bar.config(mode="determinate", maximum=total_p, value=0)
                status_label.config(text="🗣️  Generating Speech Array Channels...")

                if action_type == "play":
                    for para in paragraphs:
                        generator = pipeline(para, voice=voice, speed=speed)
                        for _, _, audio in generator:
                            if audio is not None:
                                sd.play(audio, samplerate=24000)
                                sd.wait()
                        progress_bar.step(1)
                    status_label.config(text="✨ Finished live playback successfully!")
                else:
                    audio_chunks = []
                    for para in paragraphs:
                        generator = pipeline(para, voice=voice, speed=speed)
                        for _, _, audio in generator:
                            if audio is not None:
                                audio_chunks.append(audio)
                        progress_bar.step(1)

                    if audio_chunks:
                        combined = np.concatenate(audio_chunks)
                        root.after(0, lambda: save_audio_file(combined))
                    else:
                        status_label.config(
                            text="❌ Generation produced no audio data."
                        )

            except Exception as e:
                root.after(
                    0, lambda: messagebox.showerror("Error", f"Synthesis broken:\n{e}")
                )
                status_label.config(text="❌ Process Failed.")
            finally:
                root.after(0, lambda: progress_bar.config(value=0))

        threading.Thread(target=worker, daemon=True).start()

    def save_audio_file(audio_data):
        save_path = filedialog.asksaveasfilename(
            defaultextension=".wav", filetypes=[("WAV Audio", "*.wav")]
        )
        if save_path:
            try:
                sf.write(save_path, audio_data, 24000)
                status_label.config(
                    text=f"✨ Saved track to: {os.path.basename(save_path)}"
                )
                messagebox.showinfo(
                    "Success", f"Audio track exported successfully to:\n{save_path}"
                )
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save file:\n{e}")
        else:
            status_label.config(text="⚠️ File export cancelled.")

    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(fill=tk.X, pady=10)

    ttk.Button(btn_frame, text="📖 Open File", command=open_text_file).pack(
        side=tk.LEFT, padx=5
    )
    ttk.Button(
        btn_frame, text="🔊 Play Speech", command=lambda: run_synthesis("play")
    ).pack(side=tk.RIGHT, padx=5)
    ttk.Button(
        btn_frame, text="💾 Save WAV File", command=lambda: run_synthesis("save")
    ).pack(side=tk.RIGHT, padx=5)

    root.mainloop()


# --- PRIMARY COMMAND LINE INTERFACE ROUTING ENGINE ---
def main():
    if len(sys.argv) == 1:
        launch_desktop_gui()
        sys.exit(0)

    # --- Smart Whitelist Voice Detection Intercept ---
    # Default fallback voice remains bm_george
    active_voice = "bm_george"

    # Scan the terminal inputs to check if any string matches a known voice ID
    for arg in sys.argv[1:]:
        if arg.lower() in VOICE_WHITELIST:
            active_voice = arg.lower()
            sys.argv.remove(arg)  # Safely strip it out so argparse doesn't break
            break

    # Advanced Input Intercept for terminal shorthand commands
    if len(sys.argv) == 3 and sys.argv[1] in ["-o", "--output"]:
        potential_file = sys.argv[2]
        if os.path.isfile(potential_file) and not potential_file.lower().endswith(
            ".wav"
        ):
            sys.argv = [sys.argv[0], "-o", "output.wav", potential_file]

    # --- Modernized Argparse Configuration ---
    parser = argparse.ArgumentParser(
        description="🔊 Jake's Smart Text-to-Speech CLI utility powered by Kokoro."
    )

    # -v and --version are now the undisputed version checkers
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {PYTHON_VERSION}",
        help="Show the application's version number and exit.",
    )

    parser.add_argument(
        "-o",
        "--output",
        nargs="?",
        const="output.wav",
        default=None,
        help="Output filename.",
    )

    parser.add_argument(
        "-s", "--speed", type=float, default=1.0, help="Vocal speed modifier parameter."
    )

    parser.add_argument(
        "text_input", help="The text string or path to a .txt file input source."
    )

    args = parser.parse_args()

    # Re-inject our smart-detected voice back into the args namespace
    args.voice = active_voice

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

    if args.output is not None:
        print(f"💾 Gathering audio tracks for batch file output...")
        paragraphs = [p for p in final_text.split("\n") if p.strip()]
        total_chunks = len(paragraphs) if paragraphs else 1

        pbar = tqdm(
            total=total_chunks, desc="Processing Paragraph Blocks", unit="chunk"
        )
        audio_chunks = process_text_in_batches(
            pipeline, final_text, args.voice, args.speed, pbar=pbar
        )

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
        paragraphs = [p for p in final_text.split("\n") if p.strip()]
        if not paragraphs:
            paragraphs = [final_text]

        for para in paragraphs:
            try:
                generator = pipeline(para, voice=args.voice, speed=args.speed)
                for _, _, audio in generator:
                    if audio is not None:
                        sd.play(audio, samplerate=24000)
                        sd.wait()
            except Exception as e:
                print(f"\n⚠️ Error speaking segment: {e}")


if __name__ == "__main__":
    main()
