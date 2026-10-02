#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import warnings

warnings.filterwarnings("ignore")

DEFAULT_VOICE = "bm_george"
MODEL_FILENAME = "kokoro-v1.0.fp16.onnx"
VOICES_FILENAME = "voices-v1.0.bin"
KOKORO_SAMPLE_RATE = 24000
DEFAULT_SENTENCE_PAUSE = 0.25
DEFAULT_CLAUSE_PAUSE = 0.10
DEFAULT_PARAGRAPH_PAUSE = 0.45

LANGUAGE_BY_PREFIX = {
    "a": "en-us",
    "b": "en-gb",
    "e": "es",
    "f": "fr-fr",
    "h": "hi",
    "i": "it",
    "j": "ja",
    "p": "pt-br",
    "z": "zh",
}

try:
    JAKETTS_VERSION = version("jaketts")
except PackageNotFoundError:
    JAKETTS_VERSION = "unknown"

_ASSET_PATHS = None
_VOICE_CATALOG = None
_KOKORO_CLASS = None
_G2P_CACHE = {}


def get_language_tag(voice):
    """Return the language tag encoded by a Kokoro voice ID."""
    return LANGUAGE_BY_PREFIX.get(voice[:1].lower(), "en-us")


def _candidate_asset_dirs():
    """Return local-only locations that may contain the Kokoro assets."""
    candidates = []
    configured = os.environ.get("JAKETTS_ASSET_DIR")
    if configured:
        candidates.append(Path(configured).expanduser())

    module_dir = Path(__file__).resolve().parent
    candidates.extend(
        [
            module_dir / "assets",
            Path(sys.prefix) / "share" / "jaketts",
        ]
    )

    # Preserve order while removing duplicate paths.
    unique = []
    seen = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def get_asset_paths():
    """Resolve the local FP16 model and voice bundle without using the network."""
    global _ASSET_PATHS
    if _ASSET_PATHS is not None:
        return _ASSET_PATHS

    checked = []
    for asset_dir in _candidate_asset_dirs():
        model_path = asset_dir / MODEL_FILENAME
        voices_path = asset_dir / VOICES_FILENAME
        checked.append(str(asset_dir))
        if model_path.is_file() and voices_path.is_file():
            _ASSET_PATHS = (model_path, voices_path)
            return _ASSET_PATHS

    locations = "\n  - ".join(checked)
    raise RuntimeError(
        "JakeTTS could not find its local Kokoro assets. Expected "
        f"{MODEL_FILENAME} and {VOICES_FILENAME}.\n\n"
        "Checked:\n  - "
        f"{locations}\n\n"
        "Install the JakeTTS runtime assets or set JAKETTS_ASSET_DIR to the "
        "directory containing those two files. JakeTTS does not download "
        "model or voice files while running."
    )


def get_available_voices():
    """Read the voice IDs directly from the installed local voice bundle."""
    global _VOICE_CATALOG
    if _VOICE_CATALOG is not None:
        return _VOICE_CATALOG

    _, voices_path = get_asset_paths()
    import numpy as np

    voices = np.load(voices_path, allow_pickle=False)
    try:
        names = tuple(sorted(voices.files))
    finally:
        voices.close()

    if not names:
        raise RuntimeError(f"No voices were found in {voices_path}.")
    if DEFAULT_VOICE not in names:
        raise RuntimeError(
            f"The local voice bundle does not contain the default voice {DEFAULT_VOICE}."
        )

    _VOICE_CATALOG = names
    return _VOICE_CATALOG


def get_kokoro_class():
    """Import the ONNX engine lazily and keep CLI fast paths lightweight."""
    global _KOKORO_CLASS
    if _KOKORO_CLASS is None:
        try:
            import onnxruntime as ort

            # Suppress harmless graph-optimization warnings emitted while the
            # FP16 model is loaded. Real errors still surface normally.
            ort.set_default_logger_severity(3)
        except Exception:
            pass

        from kokoro_onnx import Kokoro

        _KOKORO_CLASS = Kokoro
    return _KOKORO_CLASS


def create_kokoro_engine():
    """Create Kokoro entirely from local assets."""
    model_path, voices_path = get_asset_paths()
    kokoro_class = get_kokoro_class()
    return kokoro_class(str(model_path), str(voices_path))


def get_g2p(language):
    """Return the lightweight local G2P used for Japanese or Chinese."""
    cached = _G2P_CACHE.get(language)
    if cached is not None:
        return cached

    if language == "ja":
        from misaki import ja

        g2p = ja.JAG2P(version="cutlet")
    elif language == "zh":
        from misaki import zh

        g2p = zh.ZHG2P()
    else:
        raise ValueError(f"No custom G2P is required for language {language!r}.")

    _G2P_CACHE[language] = g2p
    return g2p


def get_pause_timing(speed):
    """Return prose timing independent of the model's spoken-word speed.

    JakeTTS keeps these values deliberately conservative.
    """
    _ = speed
    return DEFAULT_SENTENCE_PAUSE, DEFAULT_CLAUSE_PAUSE


def synthesize_text(engine, text, voice, speed):
    """Synthesize one text block with local ONNX inference."""
    language = get_language_tag(voice)
    payload = text
    is_phonemes = False

    if language in {"ja", "zh"}:
        result = get_g2p(language)(text)
        payload = result[0] if isinstance(result, tuple) else result
        is_phonemes = True

    sentence_pause, clause_pause = get_pause_timing(speed)
    return engine.create(
        payload,
        voice=voice,
        speed=speed,
        lang=language,
        is_phonemes=is_phonemes,
        trim=True,
        sentence_pause=sentence_pause,
        clause_pause=clause_pause,
    )


def add_paragraph_pause(audio, sample_rate=KOKORO_SAMPLE_RATE):
    """Append a fixed paragraph break without changing spoken-word speed."""
    import numpy as np

    silence = np.zeros(int(DEFAULT_PARAGRAPH_PAUSE * sample_rate), dtype=audio.dtype)
    return np.concatenate((audio, silence))


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


def process_text_in_batches(engine, text, voice, speed, pbar=None):
    """Synthesize paragraph blocks while preserving an explicit paragraph gap."""
    paragraphs = [p.strip() for p in re.split(r"\n+", text) if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    audio_chunks = []
    sample_rate = KOKORO_SAMPLE_RATE

    for index, para in enumerate(paragraphs):
        try:
            audio, sample_rate = synthesize_text(engine, para, voice, speed)
            if audio is not None:
                if index < len(paragraphs) - 1:
                    audio = add_paragraph_pause(audio, sample_rate)
                audio_chunks.append(audio)
            if pbar:
                pbar.update(1)
        except Exception as exc:
            print(f"\n⚠️ Warning: Failed to synthesize segment: {exc}")
            continue

    return audio_chunks, sample_rate


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
        from PySide6.QtGui import QColor, QPalette
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

    # Keep one local ONNX engine warm for the lifetime of the GUI.
    speech_engine = None
    engine_lock = threading.Lock()

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

    # macOS can return different light palettes depending on the Python host.
    # Normalize the neutral surface colors while preserving the native macOS
    # widget style, accent color, text colors, and control rendering.
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(236, 236, 236))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(245, 245, 245))
    palette.setColor(QPalette.ColorRole.Button, QColor(236, 236, 236))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(0, 0, 0, 63))
    app.setPalette(palette)

    app.setApplicationName("jaketts")
    app.setApplicationDisplayName("JakeTTS")
    app.setOrganizationName("jaketts")

    try:
        available_voices = get_available_voices()
    except Exception as exc:
        QMessageBox.critical(None, "JakeTTS assets missing", str(exc))
        return

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

    subtitle = QLabel("Local text-to-speech powered by Kokoro-82M via ONNX Runtime")
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
    for voice_id in available_voices:
        voice_dropdown.addItem(f"[{get_language_tag(voice_id)}] {voice_id}", voice_id)
    default_index = voice_dropdown.findData(DEFAULT_VOICE)
    if default_index >= 0:
        voice_dropdown.setCurrentIndex(default_index)
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

    def get_cached_engine():
        nonlocal speech_engine

        with engine_lock:
            if speech_engine is None:
                speech_engine = create_kokoro_engine()
            return speech_engine

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
            get_cached_engine()
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

                engine = get_cached_engine()
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

                    for index, para in enumerate(paragraphs):
                        if job_cancelled():
                            return
                        audio, sample_rate = synthesize_text(
                            engine, para, voice, speed
                        )
                        if job_cancelled():
                            return
                        if index < len(paragraphs) - 1:
                            audio = add_paragraph_pause(audio, sample_rate)
                        sd.play(apply_volume(audio, volume_level), samplerate=sample_rate)
                        sd.wait()
                        if job_cancelled():
                            return
                        bridge.progress_step.emit()

                    if not job_cancelled():
                        bridge.status_changed.emit("Playback finished")
                else:
                    audio_chunks = []
                    sample_rate = KOKORO_SAMPLE_RATE
                    for index, para in enumerate(paragraphs):
                        if job_cancelled():
                            return
                        audio, sample_rate = synthesize_text(
                            engine, para, voice, speed
                        )
                        if job_cancelled():
                            return
                        if index < len(paragraphs) - 1:
                            audio = add_paragraph_pause(audio, sample_rate)
                        audio_chunks.append(apply_volume(audio, volume_level))
                        bridge.progress_step.emit()

                    if not audio_chunks:
                        raise RuntimeError("Generation produced no audio data.")

                    import numpy as np
                    import soundfile as sf

                    combined = np.concatenate(audio_chunks)
                    sf.write(save_path, combined, sample_rate)
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

    try:
        voice_whitelist = set(get_available_voices())
    except RuntimeError as exc:
        print(f"❌ {exc}")
        sys.exit(1)

    detected_voice = DEFAULT_VOICE
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
        if arg_lower in voice_whitelist and not voice_found:
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

                if candidate.lower() not in voice_whitelist and candidate not in (
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
        description="🔊 Local text-to-speech powered by Kokoro-82M via ONNX Runtime."
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

    language = get_language_tag(args.voice)

    print(f"🤖 Initializing local Kokoro ONNX Engine (Locale: {language})...")
    try:
        engine = create_kokoro_engine()
    except Exception as exc:
        print(f"❌ Failed to load local speech engine: {exc}")
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
        audio_chunks, sample_rate = process_text_in_batches(
            engine, final_text, args.voice, args.speed, pbar=pbar
        )

        pbar.n = pbar.total
        pbar.refresh()
        pbar.close()

        if not audio_chunks:
            print("❌ No audio data generated.")
            sys.exit(1)

        combined_audio = np.concatenate(audio_chunks)
        sf.write(args.output, combined_audio, sample_rate)
        print(f"✨ Success! Audio file written to: {os.path.abspath(args.output)}")
    else:
        import sounddevice as sd

        print("🔊 Playing audio directly through your speakers...")
        paragraphs = [p for p in final_text.split("\n") if p.strip()]
        if not paragraphs:
            paragraphs = [final_text]

        for index, para in enumerate(paragraphs):
            try:
                audio, sample_rate = synthesize_text(
                    engine, para, args.voice, args.speed
                )
                if index < len(paragraphs) - 1:
                    audio = add_paragraph_pause(audio, sample_rate)
                sd.play(audio, samplerate=sample_rate)
                sd.wait()
            except Exception as exc:
                print(f"\n⚠️ Error speaking segment: {exc}")


if __name__ == "__main__":
    main()
