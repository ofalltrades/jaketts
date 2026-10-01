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


# --- QT DESKTOP GUI APP ---
def launch_desktop_gui():
    """Launch the PySide6/Qt desktop interface when no CLI args are given."""
    import threading

    try:
        from PySide6.QtCore import QObject, Qt, Signal
        from PySide6.QtWidgets import (
            QApplication,
            QComboBox,
            QDoubleSpinBox,
            QFileDialog,
            QGridLayout,
            QGroupBox,
            QHBoxLayout,
            QLabel,
            QMainWindow,
            QMessageBox,
            QPlainTextEdit,
            QProgressBar,
            QPushButton,
            QSizePolicy,
            QSlider,
            QVBoxLayout,
            QWidget,
        )
    except ImportError as exc:
        raise RuntimeError(
            "The desktop GUI requires PySide6. Install it with "
            "`python -m pip install PySide6-Essentials` and try again."
        ) from exc

    # Keep one Kokoro model warm for the lifetime of the GUI. Pipelines are
    # cached per language and share the same language-independent model.
    pipeline_cache = {}
    shared_model = None
    pipeline_lock = threading.Lock()

    shutdown_event = threading.Event()
    job_cancel_event = threading.Event()
    job_running_event = threading.Event()

    class UiBridge(QObject):
        """Thread-safe signals used by synthesis workers to update Qt widgets."""

        status_changed = Signal(str)
        busy_changed = Signal(bool)
        progress_indeterminate = Signal()
        progress_determinate = Signal(int)
        progress_step = Signal()
        progress_reset = Signal()
        info_requested = Signal(str, str)
        error_requested = Signal(str, str)

    bridge = UiBridge()

    class JakettsWindow(QMainWindow):
        def closeEvent(self, event):
            if shutdown_event.is_set():
                event.accept()
                return

            shutdown_event.set()
            job_cancel_event.set()
            try:
                sd_module = sys.modules.get("sounddevice")
                if sd_module is not None:
                    sd_module.stop()
            except Exception:
                pass

            event.accept()

    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv)

    # Always request Qt's light color scheme, regardless of the macOS
    # system appearance. This keeps the native platform style and accent
    # color while preventing Jaketts from switching into dark mode.
    style_hints = app.styleHints()
    if hasattr(style_hints, "setColorScheme"):
        style_hints.setColorScheme(Qt.ColorScheme.Light)

    app.setApplicationName("jaketts")
    app.setApplicationDisplayName("JakeTTS")
    app.setOrganizationName("jaketts")

    window = JakettsWindow()
    window.setWindowTitle("JakeTTS — Text to Speech")
    window.setMinimumSize(800, 620)
    window.resize(960, 740)

    # Deliberately avoid application-wide stylesheets here. Qt will use the
    # platform style and system palette while keeping the app in light mode.

    root = QWidget()
    window.setCentralWidget(root)

    main_layout = QVBoxLayout(root)
    main_layout.setContentsMargins(24, 20, 24, 20)
    main_layout.setSpacing(16)

    # Header. Typography is adjusted, but colors come entirely from the
    # current system palette.
    header = QWidget()
    header_layout = QHBoxLayout(header)
    header_layout.setContentsMargins(0, 0, 0, 0)
    header_layout.setSpacing(12)

    title_column = QVBoxLayout()
    title_column.setSpacing(2)
    title = QLabel("JakeTTS")
    title_font = title.font()
    title_font.setPointSize(title_font.pointSize() + 9)
    title_font.setBold(True)
    title.setFont(title_font)

    subtitle = QLabel("Local text-to-speech powered by Kokoro-82M")
    subtitle.setEnabled(False)
    title_column.addWidget(title)
    title_column.addWidget(subtitle)

    version_label = QLabel(f"Version {JAKETTS_VERSION}")
    version_label.setEnabled(False)
    version_label.setAlignment(
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
    )

    header_layout.addLayout(title_column, 1)
    header_layout.addWidget(version_label, 0, Qt.AlignmentFlag.AlignVCenter)
    main_layout.addWidget(header)

    # Native group boxes provide lightweight visual structure without
    # hard-coded backgrounds or borders.
    editor_card = QGroupBox()
    editor_card_font = editor_card.font()
    editor_card_font.setPointSize(editor_card_font.pointSize() + 3)
    editor_card.setFont(editor_card_font)
    editor_layout = QVBoxLayout(editor_card)
    editor_layout.setContentsMargins(12, 14, 12, 12)
    editor_layout.setSpacing(8)

    editor_header = QHBoxLayout()
    editor_title = QLabel("Text")
    char_count_label = QLabel("0 characters")
    char_count_label.setEnabled(False)
    editor_header.addWidget(editor_title)
    editor_header.addStretch(1)
    editor_header.addWidget(char_count_label)

    text_box = QPlainTextEdit()
    text_box.setPlaceholderText("Type or paste text to speak…")
    text_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    text_box.setMinimumHeight(280)

    editor_layout.addLayout(editor_header)
    editor_layout.addWidget(text_box, 1)
    main_layout.addWidget(editor_card, 1)

    def update_character_count():
        count = len(text_box.toPlainText())
        suffix = "character" if count == 1 else "characters"
        char_count_label.setText(f"{count:,} {suffix}")

    text_box.textChanged.connect(update_character_count)

    # Voice / speed / volume controls
    controls_card = QGroupBox("Speech settings")
    controls_grid = QGridLayout(controls_card)
    controls_grid.setContentsMargins(12, 14, 12, 12)
    controls_grid.setHorizontalSpacing(20)
    controls_grid.setVerticalSpacing(8)
    controls_grid.setColumnStretch(0, 4)
    controls_grid.setColumnStretch(1, 3)
    controls_grid.setColumnStretch(2, 3)

    for column, text in enumerate(("Voice", "Speed", "Volume")):
        label = QLabel(text)
        controls_grid.addWidget(label, 0, column)

    voice_dropdown = QComboBox()
    voice_items = (
        ("[en-us] af_heart", "af_heart"),
        ("[en-us] af_sarah", "af_sarah"),
        ("[en-us] af_bella", "af_bella"),
        ("[en-us] af_nicole", "af_nicole"),
        ("[en-us] af_sky", "af_sky"),
        ("[en-us] af_alloy", "af_alloy"),
        ("[en-us] af_aoede", "af_aoede"),
        ("[en-us] af_jessica", "af_jessica"),
        ("[en-us] af_river", "af_river"),
        ("[en-us] am_adam", "am_adam"),
        ("[en-us] am_michael", "am_michael"),
        ("[en-us] am_echo", "am_echo"),
        ("[en-us] am_eric", "am_eric"),
        ("[en-us] am_fenrir", "am_fenrir"),
        ("[en-us] am_liam", "am_liam"),
        ("[en-us] am_onizuka", "am_onizuka"),
        ("[en-us] am_puck", "am_puck"),
        ("[en-us] am_santa", "am_santa"),
        ("[en-gb] bm_george", "bm_george"),
        ("[en-gb] bm_lewis", "bm_lewis"),
        ("[en-gb] bf_emma", "bf_emma"),
        ("[en-gb] bf_isabella", "bf_isabella"),
        ("[en-gb] bm_fable", "bm_fable"),
        ("[en-gb] bm_daniel", "bm_daniel"),
        ("[en-gb] bf_alice", "bf_alice"),
        ("[en-gb] bf_lily", "bf_lily"),
        ("[es] ef_dora", "ef_dora"),
        ("[es] em_alex", "em_alex"),
        ("[fr] ff_sixtine", "ff_sixtine"),
        ("[fr] fm_julien", "fm_julien"),
        ("[hi] hf_ananya", "hf_ananya"),
        ("[hi] hf_kavya", "hf_kavya"),
        ("[hi] hm_anshul", "hm_anshul"),
        ("[hi] hm_shiwani", "hm_shiwani"),
        ("[it] if_sara", "if_sara"),
        ("[it] im_nicola", "im_nicola"),
        ("[ja] jf_alpha", "jf_alpha"),
        ("[ja] jf_glowing", "jf_glowing"),
        ("[ja] jf_neutral", "jf_neutral"),
        ("[ja] jf_reader", "jf_reader"),
        ("[ja] jm_kanta", "jm_kanta"),
        ("[pt] pf_doris", "pf_doris"),
        ("[pt] pm_ramon", "pm_ramon"),
        ("[zh] zf_xiaobei", "zf_xiaobei"),
        ("[zh] zf_xiaoni", "zf_xiaoni"),
        ("[zh] zf_xiaoxiao", "zf_xiaoxiao"),
        ("[zh] zf_xiaoyi", "zf_xiaoyi"),
        ("[zh] zm_yunjian", "zm_yunjian"),
        ("[zh] zm_yunxi", "zm_yunxi"),
        ("[zh] zm_yunxia", "zm_yunxia"),
        ("[zh] zm_yunyang", "zm_yunyang"),
    )
    for display, voice_id in voice_items:
        voice_dropdown.addItem(display, voice_id)
    voice_dropdown.setCurrentIndex(18)
    controls_grid.addWidget(voice_dropdown, 1, 0)

    speed_row = QHBoxLayout()
    speed_slider = QSlider(Qt.Orientation.Horizontal)
    speed_slider.setRange(50, 200)
    speed_slider.setValue(80)
    speed_slider.setSingleStep(1)
    speed_spin = QDoubleSpinBox()
    speed_spin.setRange(0.50, 2.00)
    speed_spin.setDecimals(2)
    speed_spin.setSingleStep(0.05)
    speed_spin.setValue(0.80)
    speed_spin.setSuffix("×")
    speed_spin.setFixedWidth(86)
    speed_row.addWidget(speed_slider, 1)
    speed_row.addWidget(speed_spin)
    controls_grid.addLayout(speed_row, 1, 1)

    volume_row = QHBoxLayout()
    volume_slider = QSlider(Qt.Orientation.Horizontal)
    volume_slider.setRange(0, 100)
    volume_slider.setValue(100)
    volume_label = QLabel("100%")
    volume_label.setMinimumWidth(42)
    volume_label.setAlignment(
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
    )
    volume_row.addWidget(volume_slider, 1)
    volume_row.addWidget(volume_label)
    controls_grid.addLayout(volume_row, 1, 2)

    def sync_speed_from_slider(value):
        speed_spin.blockSignals(True)
        speed_spin.setValue(value / 100.0)
        speed_spin.blockSignals(False)

    def sync_speed_from_spin(value):
        speed_slider.blockSignals(True)
        speed_slider.setValue(round(value * 100))
        speed_slider.blockSignals(False)

    speed_slider.valueChanged.connect(sync_speed_from_slider)
    speed_spin.valueChanged.connect(sync_speed_from_spin)
    volume_slider.valueChanged.connect(lambda value: volume_label.setText(f"{value}%"))

    main_layout.addWidget(controls_card)

    # Status and progress use native widgets. The status text lives in the
    # QMainWindow status bar, which also follows the system palette.
    progress_bar = QProgressBar()
    progress_bar.setRange(0, 1)
    progress_bar.setValue(0)
    progress_bar.setTextVisible(False)
    main_layout.addWidget(progress_bar)

    status_bar = window.statusBar()
    status_bar.showMessage("Ready")

    # Action buttons. Keeping these text-only lets macOS draw the standard
    # button chrome; the default Speak button receives the system accent.
    actions = QHBoxLayout()
    actions.setSpacing(8)

    def make_button(text):
        return QPushButton(text)

    open_button = make_button("Open Text File…")
    clear_button = make_button("Clear")
    stop_button = make_button("Stop")
    save_button = make_button("Save WAV…")
    play_button = make_button("Speak")
    play_button.setDefault(True)
    stop_button.setEnabled(False)

    actions.addWidget(open_button)
    actions.addWidget(clear_button)
    actions.addStretch(1)
    actions.addWidget(stop_button)
    actions.addWidget(save_button)
    actions.addWidget(play_button)
    main_layout.addLayout(actions)

    def set_busy_ui(busy):
        enabled = not busy
        for widget in (
            open_button,
            clear_button,
            save_button,
            play_button,
            voice_dropdown,
            speed_slider,
            speed_spin,
            volume_slider,
        ):
            widget.setEnabled(enabled)
        stop_button.setEnabled(busy)

    def set_progress_indeterminate():
        progress_bar.setRange(0, 0)

    def set_progress_determinate(maximum):
        progress_bar.setRange(0, max(1, maximum))
        progress_bar.setValue(0)

    def step_progress():
        if progress_bar.maximum() > 0:
            progress_bar.setValue(min(progress_bar.value() + 1, progress_bar.maximum()))

    def reset_progress():
        progress_bar.setRange(0, 1)
        progress_bar.setValue(0)

    bridge.status_changed.connect(status_bar.showMessage)
    bridge.busy_changed.connect(set_busy_ui)
    bridge.progress_indeterminate.connect(set_progress_indeterminate)
    bridge.progress_determinate.connect(set_progress_determinate)
    bridge.progress_step.connect(step_progress)
    bridge.progress_reset.connect(reset_progress)
    bridge.info_requested.connect(
        lambda title, message: QMessageBox.information(window, title, message)
    )
    bridge.error_requested.connect(
        lambda title, message: QMessageBox.critical(window, title, message)
    )

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

    def job_cancelled():
        return shutdown_event.is_set() or job_cancel_event.is_set()

    def warm_speech_engine():
        """Warm the default Kokoro model in the background after GUI launch."""
        if shutdown_event.is_set():
            return

        bridge.status_changed.emit("Warming speech engine…")
        try:
            get_cached_pipeline("b")
        except Exception:
            # Warm-up is opportunistic. Play/Save will surface real failures.
            pass
        finally:
            if not shutdown_event.is_set() and not job_running_event.is_set():
                bridge.status_changed.emit("Ready")

    def open_text_file():
        file_path, _ = QFileDialog.getOpenFileName(
            window,
            "Open text file",
            "",
            "Text Files (*.txt);;All Files (*)",
        )
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                text_box.setPlainText(handle.read())
            status_bar.showMessage(f"Loaded {os.path.basename(file_path)}")
        except Exception as exc:
            QMessageBox.critical(
                window,
                "Open file failed",
                f"Could not read the text file:\n\n{exc}",
            )

    def clear_text():
        text_box.clear()
        status_bar.showMessage("Ready")
        text_box.setFocus()

    def run_synthesis(action_type):
        input_text = text_box.toPlainText().strip()
        if not input_text:
            QMessageBox.warning(
                window,
                "Nothing to speak",
                "Enter some text or open a text file first.",
            )
            return

        save_path = None
        if action_type == "save":
            save_path, _ = QFileDialog.getSaveFileName(
                window,
                "Save WAV",
                "output.wav",
                "WAV Audio (*.wav)",
            )
            if not save_path:
                status_bar.showMessage("Save cancelled")
                return
            if not save_path.lower().endswith(".wav"):
                save_path += ".wav"

        voice = voice_dropdown.currentData()
        lang_code = get_language_code(voice)
        speed = speed_spin.value()
        volume_level = volume_slider.value() / 100.0
        job_cancel_event.clear()
        job_running_event.set()

        def worker():
            try:
                if job_cancelled():
                    return

                bridge.busy_changed.emit(True)
                bridge.status_changed.emit("Loading speech engine…")
                bridge.progress_indeterminate.emit()

                ensure_language_resources(
                    lang_code,
                    status_callback=bridge.status_changed.emit,
                )
                if job_cancelled():
                    return

                pipeline = get_cached_pipeline(lang_code)
                if job_cancelled():
                    return

                paragraphs = [
                    p.strip() for p in re.split(r"\n+", input_text) if p.strip()
                ]
                if not paragraphs:
                    paragraphs = [input_text]

                bridge.progress_determinate.emit(len(paragraphs))
                bridge.status_changed.emit(f"Generating with {voice}…")

                if action_type == "play":
                    import sounddevice as sd

                    for para in paragraphs:
                        if job_cancelled():
                            return
                        generator = pipeline(para, voice=voice, speed=speed)
                        for _, _, audio in generator:
                            if job_cancelled():
                                return
                            if audio is not None:
                                sd.play(
                                    apply_volume(audio, volume_level), samplerate=24000
                                )
                                sd.wait()
                                if job_cancelled():
                                    return
                        bridge.progress_step.emit()

                    if not job_cancelled():
                        bridge.status_changed.emit("Playback finished")
                else:
                    audio_chunks = []
                    for para in paragraphs:
                        if job_cancelled():
                            return
                        generator = pipeline(para, voice=voice, speed=speed)
                        for _, _, audio in generator:
                            if job_cancelled():
                                return
                            if audio is not None:
                                audio_chunks.append(apply_volume(audio, volume_level))
                        bridge.progress_step.emit()

                    if not audio_chunks:
                        raise RuntimeError("Generation produced no audio data.")

                    import numpy as np
                    import soundfile as sf

                    combined = np.concatenate(audio_chunks)
                    sf.write(save_path, combined, 24000)
                    bridge.status_changed.emit(f"Saved {os.path.basename(save_path)}")
                    bridge.info_requested.emit(
                        "Saved",
                        f"Audio exported successfully to:\n\n{save_path}",
                    )

            except Exception as exc:
                if not job_cancelled():
                    bridge.status_changed.emit("Synthesis failed")
                    bridge.error_requested.emit("Synthesis failed", str(exc))
            finally:
                job_running_event.clear()
                if not shutdown_event.is_set():
                    was_stopped = job_cancel_event.is_set()
                    bridge.progress_reset.emit()
                    bridge.busy_changed.emit(False)
                    if was_stopped:
                        bridge.status_changed.emit("Stopped")

        threading.Thread(target=worker, daemon=True).start()

    def stop_current_job():
        if job_cancel_event.is_set():
            return

        job_cancel_event.set()
        status_bar.showMessage("Stopping…")
        try:
            sd_module = sys.modules.get("sounddevice")
            if sd_module is not None:
                sd_module.stop()
        except Exception:
            pass

    open_button.clicked.connect(open_text_file)
    clear_button.clicked.connect(clear_text)
    stop_button.clicked.connect(stop_current_job)
    save_button.clicked.connect(lambda: run_synthesis("save"))
    play_button.clicked.connect(lambda: run_synthesis("play"))

    # Center the initial window on the active screen.
    screen = app.primaryScreen()
    if screen is not None:
        available = screen.availableGeometry()
        frame = window.frameGeometry()
        frame.moveCenter(available.center())
        window.move(frame.topLeft())

    window.show()
    text_box.setFocus()
    threading.Thread(target=warm_speech_engine, daemon=True).start()

    if owns_app:
        app.exec()


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

    detected_speed = "0.8"
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
        default=0.8,
        help="Speed multiplier (default: 0.8).",
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
