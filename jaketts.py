#!/usr/bin/env python3
import sys
import os
import argparse
import re
import subprocess

# Allow Kokoro/PyTorch to use Apple Silicon MPS when available while
# falling back to CPU for unsupported operations. Existing user settings win.
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

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

LANGUAGE_CODES = {"a", "b", "e", "f", "h", "i", "j", "p", "z"}


def get_language_code(voice):
    """Return the Kokoro language code encoded by a voice ID."""
    code = voice[:1].lower()
    return code if code in LANGUAGE_CODES else "a"


def ensure_language_resources(lang_code, status_callback=None):
    """Download one-time language resources that pip cannot bundle directly."""
    if lang_code != "j":
        return

    try:
        import unidic
    except ImportError as exc:
        raise RuntimeError(
            "Japanese support is not installed. Reinstall jaketts so its "
            "Japanese dependencies are available."
        ) from exc

    mecabrc = os.path.join(unidic.DICDIR, "mecabrc")
    if os.path.isfile(mecabrc):
        return

    message = (
        "📚 Japanese support needs the UniDic dictionary. "
        "Downloading it now (one-time setup, about 526 MB)..."
    )
    if status_callback is not None:
        status_callback(message)
    else:
        print(message)

    try:
        subprocess.run(
            [sys.executable, "-m", "unidic", "download"],
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            "Automatic UniDic download failed. Check your network connection "
            "and that this Python environment is writable, then try again."
        ) from exc

    if not os.path.isfile(mecabrc):
        raise RuntimeError(
            "UniDic reported a successful download, but its dictionary files "
            "could not be found afterward."
        )

    done_message = "✅ Japanese dictionary is ready."
    if status_callback is not None:
        status_callback(done_message)
    else:
        print(done_message)


from importlib.metadata import version, PackageNotFoundError

try:
    JAKETTS_VERSION = version("jaketts")
except PackageNotFoundError:
    JAKETTS_VERSION = "unknown"

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


# --- LAZY RUNTIME IMPORTS ---
# Kokoro pulls in PyTorch/Transformers, which is expensive. Keep those imports
# out of the fast CLI paths (-v, argument validation, detached GUI launcher)
# and load them only when synthesis actually begins.
_KPIPELINE_CLASS = None


def get_kpipeline_class():
    global _KPIPELINE_CLASS
    if _KPIPELINE_CLASS is None:
        # Do not redirect sys.stderr while importing Kokoro. Libraries such as
        # huggingface_hub can create logging handlers during import and retain
        # that stream; redirecting it to a temporary file would leave those
        # handlers pointing at a closed file after the context exits.
        import logging

        previous_disable_level = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            from kokoro import KPipeline as imported_pipeline
        finally:
            logging.disable(previous_disable_level)

        # Some libraries configure their own loggers during import, so apply
        # our quiet CLI policy again after the import has completed.
        for logger_name in (
            "huggingface_hub",
            "huggingface_hub.utils._http",
            "huggingface_hub.utils._validators",
            "huggingface_hub.utils._auth",
        ):
            logging.getLogger(logger_name).setLevel(logging.ERROR)

        _KPIPELINE_CLASS = imported_pipeline
    return _KPIPELINE_CLASS


def get_tqdm():
    try:
        from tqdm import tqdm as imported_tqdm
        return imported_tqdm
    except ImportError:
        class _SimpleProgress:
            def __init__(self, total=None, **_kwargs):
                self.total = total or 0
                self.n = 0

            def update(self, amount=1):
                self.n += amount

            def refresh(self):
                pass

            def close(self):
                pass

        return _SimpleProgress


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


# Internal flag used only by the detached GUI child process.
GUI_CHILD_FLAG = "--_jaketts-gui-child"


def launch_desktop_gui_detached():
    """Launch the desktop GUI in a detached child process and return immediately."""
    command = [sys.executable, os.path.abspath(__file__), GUI_CHILD_FLAG]

    try:
        subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    except OSError:
        # If detaching is unavailable for any reason, still give the user a GUI.
        launch_desktop_gui()


# --- NATIVE DESKTOP GUI APP ---
def launch_desktop_gui():
    """Launch the native Tkinter desktop interface when no CLI args are given."""
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    import threading
    import queue

    # Keep one Kokoro model warm for the lifetime of the GUI. Pipelines are
    # cached per language and share the same language-independent model.
    pipeline_cache = {}
    shared_model = None
    pipeline_lock = threading.Lock()

    root = tk.Tk()
    root.title("jaketts — Text to Speech")

    # Brand palette: deep teal-blue for structure, brighter cyan-blue for
    # interactive accents, and pale blue surfaces to avoid a flat white UI.
    brand = "#006186"
    accent = "#219ac8"
    accent_hover = "#1888b3"
    brand_hover = "#004d6a"
    bg = "#eaf5f8"
    card = "#f8fcfd"
    card_alt = "#e2f3f8"
    text_bg = "#fcfeff"
    border = "#9bc9d8"
    ink = "#12313d"
    muted = "#55727d"
    header_muted = "#c8eaf5"
    soft = "#d8edf4"

    root.configure(bg=bg)

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure("App.TFrame", background=bg)
    style.configure("Header.TFrame", background=brand)
    style.configure("Card.TFrame", background=card)
    style.configure("TintCard.TFrame", background=card_alt)
    style.configure("Title.TLabel", background=brand, foreground="white", font=("Helvetica", 24, "bold"))
    style.configure("Subtitle.TLabel", background=brand, foreground=header_muted, font=("Helvetica", 11))
    style.configure("Version.TLabel", background=brand, foreground=header_muted, font=("Helvetica", 9, "bold"))
    style.configure("CardTitle.TLabel", background=card, foreground=brand, font=("Helvetica", 11, "bold"))
    style.configure("Field.TLabel", background=card_alt, foreground=brand, font=("Helvetica", 9, "bold"))
    style.configure("Value.TLabel", background=card_alt, foreground=ink, font=("Helvetica", 9, "bold"))
    style.configure("CardValue.TLabel", background=card, foreground=muted, font=("Helvetica", 9, "bold"))
    style.configure("Status.TLabel", background=bg, foreground=brand, font=("Helvetica", 10, "bold"))
    style.configure(
        "Primary.TButton",
        background=accent,
        foreground="white",
        borderwidth=0,
        focusthickness=0,
        padding=(18, 11),
        font=("Helvetica", 10, "bold"),
    )
    style.map(
        "Primary.TButton",
        background=[("active", accent_hover), ("pressed", brand), ("disabled", "#8eb8c7")],
        foreground=[("disabled", "#e9f4f7")],
    )
    style.configure(
        "Secondary.TButton",
        background=soft,
        foreground=brand,
        borderwidth=0,
        focusthickness=0,
        padding=(14, 10),
        font=("Helvetica", 10, "bold"),
    )
    style.map(
        "Secondary.TButton",
        background=[("active", "#c8e5ef"), ("pressed", "#b6dce9")],
        foreground=[("active", brand_hover)],
    )
    style.configure(
        "Brand.Horizontal.TProgressbar",
        troughcolor="#cce6ef",
        background=accent,
        bordercolor="#cce6ef",
        lightcolor=accent,
        darkcolor=accent,
    )
    style.configure(
        "Brand.Horizontal.TScale",
        background=card_alt,
        troughcolor="#b9dae5",
    )
    style.configure(
        "Brand.TCombobox",
        fieldbackground="white",
        background="white",
        foreground=ink,
        arrowcolor=brand,
        bordercolor=border,
        lightcolor=border,
        darkcolor=border,
        padding=5,
    )
    style.map(
        "Brand.TCombobox",
        fieldbackground=[("readonly", "white")],
        selectbackground=[("readonly", "white")],
        selectforeground=[("readonly", ink)],
        bordercolor=[("focus", accent)],
    )
    style.configure(
        "Brand.Vertical.TScrollbar",
        background=soft,
        troughcolor=card,
        arrowcolor=brand,
        bordercolor=card,
        lightcolor=soft,
        darkcolor=soft,
    )

    # Match the native combobox popup to the rest of the palette where Tk
    # exposes those option-database hooks.
    root.option_add("*TCombobox*Listbox.background", "white")
    root.option_add("*TCombobox*Listbox.foreground", ink)
    root.option_add("*TCombobox*Listbox.selectBackground", accent)
    root.option_add("*TCombobox*Listbox.selectForeground", "white")

    main_frame = ttk.Frame(root, style="App.TFrame", padding=(26, 22, 26, 22))
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Header band
    header = ttk.Frame(main_frame, style="Header.TFrame", padding=(20, 16))
    header.pack(fill=tk.X, pady=(0, 16))
    header.columnconfigure(0, weight=1)

    title_block = ttk.Frame(header, style="Header.TFrame")
    title_block.grid(row=0, column=0, sticky="w")
    ttk.Label(title_block, text="jaketts", style="Title.TLabel").pack(anchor="w")
    ttk.Label(
        title_block,
        text="Local text-to-speech powered by Kokoro-82M",
        style="Subtitle.TLabel",
    ).pack(anchor="w", pady=(2, 0))
    ttk.Label(header, text=f"v{JAKETTS_VERSION}", style="Version.TLabel").grid(
        row=0, column=1, sticky="ne", pady=(8, 0)
    )

    # Text editor card
    editor_card = ttk.Frame(main_frame, style="Card.TFrame", padding=16)
    editor_card.pack(fill=tk.BOTH, expand=True)

    editor_header = ttk.Frame(editor_card, style="Card.TFrame")
    editor_header.pack(fill=tk.X, pady=(0, 8))
    editor_header.columnconfigure(0, weight=1)
    ttk.Label(editor_header, text="Text", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
    char_count_var = tk.StringVar(value="0 characters")
    ttk.Label(editor_header, textvariable=char_count_var, style="CardValue.TLabel").grid(row=0, column=1, sticky="e")

    text_container = ttk.Frame(editor_card, style="Card.TFrame")
    text_container.pack(fill=tk.BOTH, expand=True)

    text_scroll = ttk.Scrollbar(text_container, style="Brand.Vertical.TScrollbar")
    text_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    text_box = tk.Text(
        text_container,
        yscrollcommand=text_scroll.set,
        wrap=tk.WORD,
        height=14,
        font=("Helvetica", 12),
        bg=text_bg,
        fg=ink,
        insertbackground=ink,
        selectbackground="#b9e5f5",
        relief=tk.FLAT,
        borderwidth=0,
        highlightthickness=1,
        highlightbackground=border,
        highlightcolor=accent,
        padx=12,
        pady=12,
        undo=True,
    )
    text_box.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
    text_scroll.config(command=text_box.yview)

    def update_character_count(_event=None):
        if text_box.edit_modified():
            content = text_box.get("1.0", "end-1c")
            count = len(content)
            char_count_var.set(f"{count:,} character" + ("" if count == 1 else "s"))
            text_box.edit_modified(False)

    text_box.bind("<<Modified>>", update_character_count)
    text_box.edit_modified(False)

    # Voice / speed / volume controls
    controls_card = ttk.Frame(main_frame, style="TintCard.TFrame", padding=16)
    controls_card.pack(fill=tk.X, pady=(14, 0))
    for column in range(3):
        controls_card.columnconfigure(column, weight=1, uniform="controls")

    ttk.Label(controls_card, text="VOICE", style="Field.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(controls_card, text="SPEED", style="Field.TLabel").grid(row=0, column=1, sticky="w", padx=(18, 0))
    ttk.Label(controls_card, text="VOLUME", style="Field.TLabel").grid(row=0, column=2, sticky="w", padx=(18, 0))

    voice_var = tk.StringVar(value="[en-gb] bm_george")
    voice_dropdown = ttk.Combobox(
        controls_card,
        textvariable=voice_var,
        state="readonly",
        width=24,
        style="Brand.TCombobox",
    )
    voice_dropdown["values"] = (
        "[en-us] af_heart", "[en-us] af_sarah", "[en-us] af_bella", "[en-us] af_nicole",
        "[en-us] af_sky", "[en-us] af_alloy", "[en-us] af_aoede", "[en-us] af_jessica",
        "[en-us] af_river", "[en-us] am_adam", "[en-us] am_michael", "[en-us] am_echo",
        "[en-us] am_eric", "[en-us] am_fenrir", "[en-us] am_liam", "[en-us] am_onizuka",
        "[en-us] am_puck", "[en-us] am_santa", "[en-gb] bm_george", "[en-gb] bm_lewis",
        "[en-gb] bf_emma", "[en-gb] bf_isabella", "[en-gb] bm_fable", "[en-gb] bm_daniel",
        "[en-gb] bf_alice", "[en-gb] bf_lily", "[es] ef_dora", "[es] em_alex",
        "[fr] ff_sixtine", "[fr] fm_julien", "[hi] hf_ananya", "[hi] hf_kavya",
        "[hi] hm_anshul", "[hi] hm_shiwani", "[it] if_sara", "[it] im_nicola",
        "[ja] jf_alpha", "[ja] jf_glowing", "[ja] jf_neutral", "[ja] jf_reader",
        "[ja] jm_kanta", "[pt] pf_doris", "[pt] pm_ramon", "[zh] zf_xiaobei",
        "[zh] zf_xiaoni", "[zh] zf_xiaoxiao", "[zh] zf_xiaoyi", "[zh] zm_yunjian",
        "[zh] zm_yunxi", "[zh] zm_yunxia", "[zh] zm_yunyang",
    )
    voice_dropdown.grid(row=1, column=0, sticky="ew", pady=(7, 0))

    speed_var = tk.DoubleVar(value=1.0)
    speed_row = ttk.Frame(controls_card, style="TintCard.TFrame")
    speed_row.grid(row=1, column=1, sticky="ew", padx=(18, 0), pady=(7, 0))
    speed_row.columnconfigure(0, weight=1)
    speed_scale = ttk.Scale(speed_row, from_=0.5, to=2.0, variable=speed_var, orient=tk.HORIZONTAL, style="Brand.Horizontal.TScale")
    speed_scale.grid(row=0, column=0, sticky="ew")
    speed_label = ttk.Label(speed_row, text="1.00×", style="Value.TLabel", width=6, anchor="e")
    speed_label.grid(row=0, column=1, padx=(8, 0))

    volume_var = tk.DoubleVar(value=100.0)
    volume_row = ttk.Frame(controls_card, style="TintCard.TFrame")
    volume_row.grid(row=1, column=2, sticky="ew", padx=(18, 0), pady=(7, 0))
    volume_row.columnconfigure(0, weight=1)
    volume_scale = ttk.Scale(volume_row, from_=0, to=100, variable=volume_var, orient=tk.HORIZONTAL, style="Brand.Horizontal.TScale")
    volume_scale.grid(row=0, column=0, sticky="ew")
    volume_label = ttk.Label(volume_row, text="100%", style="Value.TLabel", width=5, anchor="e")
    volume_label.grid(row=0, column=1, padx=(8, 0))

    def update_speed_label(*_args):
        speed_label.config(text=f"{speed_var.get():.2f}×")

    def update_volume_label(*_args):
        volume_label.config(text=f"{round(volume_var.get()):d}%")

    speed_var.trace_add("write", update_speed_label)
    volume_var.trace_add("write", update_volume_label)

    # Status / progress
    progress_bar = ttk.Progressbar(main_frame, orient=tk.HORIZONTAL, mode="determinate", style="Brand.Horizontal.TProgressbar")
    progress_bar.pack(fill=tk.X, pady=(14, 7))
    status_var = tk.StringVar(value="Ready")
    ttk.Label(main_frame, textvariable=status_var, style="Status.TLabel").pack(anchor="w")

    action_frame = ttk.Frame(main_frame, style="App.TFrame")
    action_frame.pack(fill=tk.X, pady=(14, 0))
    action_frame.columnconfigure(2, weight=1)

    ui_queue = queue.Queue()
    shutdown_event = threading.Event()

    def post_ui(callback, *args):
        """Queue a UI operation for the Tk main thread unless shutdown began."""
        if not shutdown_event.is_set():
            ui_queue.put((callback, args))

    def process_ui_queue():
        if shutdown_event.is_set():
            return
        try:
            while True:
                callback, args = ui_queue.get_nowait()
                if shutdown_event.is_set():
                    return
                callback(*args)
        except queue.Empty:
            pass
        if not shutdown_event.is_set():
            root.after(40, process_ui_queue)

    def set_status(message):
        post_ui(status_var.set, message)

    def set_buttons_enabled(enabled):
        state = "normal" if enabled else "disabled"
        for button in (open_button, clear_button, save_button, play_button):
            button.config(state=state)

    def set_busy(enabled):
        post_ui(set_buttons_enabled, not enabled)

    def set_indeterminate_progress():
        progress_bar.config(mode="indeterminate")
        progress_bar.start(10)

    def set_determinate_progress(maximum):
        progress_bar.stop()
        progress_bar.config(mode="determinate", maximum=maximum, value=0)

    def step_progress():
        progress_bar.step(1)

    def reset_progress():
        progress_bar.stop()
        progress_bar.config(mode="determinate", value=0)

    def get_cached_pipeline(lang_code):
        nonlocal shared_model

        with pipeline_lock:
            cached = pipeline_cache.get(lang_code)
            if cached is not None:
                return cached

            pipeline_class = get_kpipeline_class()
            if shared_model is None:
                pipeline = pipeline_class(
                    lang_code=lang_code,
                    repo_id="hexgrad/Kokoro-82M",
                )
                shared_model = pipeline.model
            else:
                pipeline = pipeline_class(
                    lang_code=lang_code,
                    repo_id="hexgrad/Kokoro-82M",
                    model=shared_model,
                )

            pipeline_cache[lang_code] = pipeline
            return pipeline

    def apply_volume(audio, volume_level):
        import numpy as np

        audio_array = np.asarray(audio, dtype=np.float32)
        if volume_level >= 0.999:
            return audio_array
        return np.clip(audio_array * volume_level, -1.0, 1.0)

    def open_text_file():
        file_path = filedialog.askopenfilename(
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            text_box.delete("1.0", tk.END)
            text_box.insert("1.0", content)
            text_box.edit_modified(True)
            update_character_count()
            status_var.set(f"Loaded {os.path.basename(file_path)}")
        except Exception as e:
            messagebox.showerror("Open file failed", f"Could not read the text file:\n\n{e}")

    def clear_text():
        text_box.delete("1.0", tk.END)
        text_box.edit_modified(True)
        update_character_count()
        status_var.set("Ready")
        text_box.focus_set()

    def run_synthesis(action_type):
        input_text = text_box.get("1.0", "end-1c").strip()
        if not input_text:
            messagebox.showwarning("Nothing to speak", "Enter some text or open a text file first.")
            return

        save_path = None
        if action_type == "save":
            save_path = filedialog.asksaveasfilename(
                defaultextension=".wav",
                filetypes=[("WAV Audio", "*.wav")],
                initialfile="output.wav",
            )
            if not save_path:
                status_var.set("Save cancelled")
                return

        voice = voice_var.get().split()[-1]
        lang_code = get_language_code(voice)
        speed = speed_var.get()
        volume_level = volume_var.get() / 100.0

        def worker():
            try:
                if shutdown_event.is_set():
                    return

                set_busy(True)
                set_status("Loading speech engine…")
                post_ui(set_indeterminate_progress)

                ensure_language_resources(lang_code, status_callback=set_status)
                if shutdown_event.is_set():
                    return

                pipeline = get_cached_pipeline(lang_code)
                if shutdown_event.is_set():
                    return

                paragraphs = [p for p in input_text.split("\n") if p.strip()]
                total_p = len(paragraphs) if paragraphs else 1
                post_ui(set_determinate_progress, total_p)
                set_status(f"Generating with {voice}…")

                if action_type == "play":
                    import sounddevice as sd

                    for para in paragraphs:
                        if shutdown_event.is_set():
                            return
                        generator = pipeline(para, voice=voice, speed=speed)
                        for _, _, audio in generator:
                            if shutdown_event.is_set():
                                return
                            if audio is not None:
                                sd.play(apply_volume(audio, volume_level), samplerate=24000)
                                sd.wait()
                                if shutdown_event.is_set():
                                    return
                        post_ui(step_progress)
                    if not shutdown_event.is_set():
                        set_status("Playback finished")
                else:
                    audio_chunks = []
                    for para in paragraphs:
                        if shutdown_event.is_set():
                            return
                        generator = pipeline(para, voice=voice, speed=speed)
                        for _, _, audio in generator:
                            if shutdown_event.is_set():
                                return
                            if audio is not None:
                                audio_chunks.append(apply_volume(audio, volume_level))
                        post_ui(step_progress)

                    if not audio_chunks:
                        raise RuntimeError("Generation produced no audio data.")

                    import numpy as np
                    import soundfile as sf

                    combined = np.concatenate(audio_chunks)
                    sf.write(save_path, combined, 24000)
                    set_status(f"Saved {os.path.basename(save_path)}")
                    post_ui(
                        messagebox.showinfo,
                        "Saved",
                        f"Audio exported successfully to:\n\n{save_path}",
                    )

            except Exception as e:
                if not shutdown_event.is_set():
                    set_status("Synthesis failed")
                    post_ui(messagebox.showerror, "Synthesis failed", str(e))
            finally:
                if not shutdown_event.is_set():
                    post_ui(reset_progress)
                    set_busy(False)

        threading.Thread(target=worker, daemon=True).start()

    open_button = ttk.Button(action_frame, text="Open text file", style="Secondary.TButton", command=open_text_file)
    open_button.grid(row=0, column=0, sticky="w")
    clear_button = ttk.Button(action_frame, text="Clear", style="Secondary.TButton", command=clear_text)
    clear_button.grid(row=0, column=1, sticky="w", padx=(8, 0))
    save_button = ttk.Button(action_frame, text="Save WAV", style="Secondary.TButton", command=lambda: run_synthesis("save"))
    save_button.grid(row=0, column=3, sticky="e", padx=(0, 8))
    play_button = ttk.Button(action_frame, text="Play speech", style="Primary.TButton", command=lambda: run_synthesis("play"))
    play_button.grid(row=0, column=4, sticky="e")

    def close_gui():
        """Stop active playback/work and close without worker/Tk races."""
        if shutdown_event.is_set():
            return

        shutdown_event.set()
        try:
            sd_module = sys.modules.get("sounddevice")
            if sd_module is not None:
                sd_module.stop()
        except Exception:
            pass

        # Drop queued callbacks so no worker operation can touch widgets after
        # the Tk interpreter has been destroyed. The worker is a daemon thread,
        # so the detached GUI process can exit even if Kokoro is between chunks.
        try:
            while True:
                ui_queue.get_nowait()
        except queue.Empty:
            pass

        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close_gui)

    # Build the complete layout before choosing the window size. This prevents
    # lower controls from being clipped by a fixed geometry that is smaller than
    # the widgets' requested size. The resulting requested size is also the hard
    # minimum, so resizing can never hide required controls.
    root.update_idletasks()
    requested_width = root.winfo_reqwidth()
    requested_height = root.winfo_reqheight()

    minimum_width = max(requested_width, 820)
    minimum_height = max(requested_height, 680)
    root.minsize(minimum_width, minimum_height)

    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    initial_width = max(minimum_width, min(1040, screen_width - 80))
    initial_height = max(minimum_height, min(820, screen_height - 80))

    x = max(0, (screen_width - initial_width) // 2)
    y = max(0, (screen_height - initial_height) // 3)
    root.geometry(f"{initial_width}x{initial_height}+{x}+{y}")

    text_box.focus_set()
    process_ui_queue()
    root.mainloop()

def main():
    if len(sys.argv) == 1:
        launch_desktop_gui_detached()
        sys.exit(0)

    # The detached child uses this private flag to enter the GUI without
    # recursively spawning another process.
    if sys.argv[1:] == [GUI_CHILD_FLAG]:
        launch_desktop_gui()
        sys.exit(0)

    # --- THE ADVANCED COMMAND REARRANGER INTERCEPT ---
    raw_args = sys.argv[1:]

    # Preserve -v / --version exactly as requested.
    if "-v" in raw_args or "--version" in raw_args:
        print(f"jaketts {JAKETTS_VERSION}")
        sys.exit(0)

    detected_voice = "bm_george"
    voice_found = False

    output_requested = False
    output_file = None

    detected_speed = "1.0"
    speed_found = False

    text_tokens = []

    i = 0
    while i < len(raw_args):
        arg = raw_args[i]
        arg_lower = arg.lower()

        # ------------------------------------------------------------
        # Voice ID
        # ------------------------------------------------------------
        if arg_lower in VOICE_WHITELIST and not voice_found:
            detected_voice = arg_lower
            voice_found = True
            i += 1
            continue

        # ------------------------------------------------------------
        # Output
        # ------------------------------------------------------------
        if arg in ("-o", "--output"):
            output_requested = True

            if i + 1 < len(raw_args):
                candidate = raw_args[i + 1]

                # Only consume the following token as an output target
                # when it clearly looks like a WAV filename.
                if candidate.lower().endswith(".wav"):
                    output_file = candidate
                    i += 2
                    continue

            # Bare -o / --output defaults to output.wav.
            # Crucially, the following token remains available for
            # voice/text detection.
            output_file = "output.wav"
            i += 1
            continue

        # Explicit assignment syntax is unambiguous.
        if arg.startswith("--output="):
            output_requested = True
            value = arg.split("=", 1)[1].strip()
            output_file = value or "output.wav"
            i += 1
            continue

        if arg.startswith("-o="):
            output_requested = True
            value = arg.split("=", 1)[1].strip()
            output_file = value or "output.wav"
            i += 1
            continue

        # ------------------------------------------------------------
        # Speed
        # ------------------------------------------------------------
        if arg in ("-s", "--speed"):
            if i + 1 < len(raw_args):
                candidate = raw_args[i + 1]

                if candidate.lower() not in VOICE_WHITELIST and candidate not in (
                    "-o",
                    "--output",
                    "-s",
                    "--speed",
                    "-v",
                    "--version",
                ):
                    detected_speed = candidate
                    speed_found = True
                    i += 2
                    continue

            # Let argparse give a useful float conversion error.
            detected_speed = "__missing_speed__"
            speed_found = True
            i += 1
            continue

        if arg.startswith("--speed="):
            detected_speed = arg.split("=", 1)[1]
            speed_found = True
            i += 1
            continue

        if arg.startswith("-s="):
            detected_speed = arg.split("=", 1)[1]
            speed_found = True
            i += 1
            continue

        # Everything else becomes text.
        text_tokens.append(arg)
        i += 1

    text_content = " ".join(text_tokens)

    # ------------------------------------------------------------
    # Reconstruct argv into the canonical order argparse expects.
    # ------------------------------------------------------------
    new_argv = [sys.argv[0]]

    if output_requested:
        new_argv.extend(["-o", output_file or "output.wav"])

    if speed_found:
        new_argv.extend(["-s", detected_speed])

    new_argv.append(detected_voice)

    if text_content:
        new_argv.append(text_content)

    sys.argv = new_argv

    # ------------------------------------------------------------
    # ARGPARSE ENGINE
    # ------------------------------------------------------------
    parser = argparse.ArgumentParser(
        description="🔊 Jake's Smart Text-to-Speech CLI utility powered by Kokoro."
    )

    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {JAKETTS_VERSION}",
        help="Show the application's version number and exit.",
    )

    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output filename.",
    )

    parser.add_argument(
        "-s",
        "--speed",
        type=float,
        default=1.0,
        help="Speed multiplier.",
    )

    parser.add_argument(
        "voice",
        help="The voice profile ID.",
    )

    parser.add_argument(
        "text_input",
        help="The text string or path to a .txt file.",
    )

    args = parser.parse_args()

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

    lang_code = get_language_code(args.voice)

    try:
        ensure_language_resources(lang_code)
    except RuntimeError as e:
        print(f"❌ {e}")
        sys.exit(1)

    print(f"🤖 Initializing Kokoro Engine (Locale: {lang_code})...")
    try:
        pipeline_class = get_kpipeline_class()
        pipeline = pipeline_class(lang_code=lang_code, repo_id="hexgrad/Kokoro-82M")
    except Exception as e:
        print(f"❌ Failed to load pipeline: {e}")
        sys.exit(1)

    print(f"🗣️  Synthesizing text via voice '{args.voice}' (Speed: {args.speed}x)...")

    if args.output is not None:
        import numpy as np
        import soundfile as sf

        tqdm = get_tqdm()
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
        import sounddevice as sd

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
