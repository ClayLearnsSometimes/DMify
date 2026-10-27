import sys
import math
import queue
import time
import os
import sysconfig
import traceback
from pathlib import Path

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

from PySide6.QtWidgets import (QApplication, QMainWindow, QSplitter, QListWidget,
                               QListWidgetItem, QLineEdit, QVBoxLayout, QWidget)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl, Qt, QThread, Signal
from PySide6.QtGui import QIcon

from matcher import Matcher #Do I still need this... I know i need sleep
import matcher as matcher_mod

# ---------------- Base Path Setup (Supports PyInstaller .exe) ----------------
if getattr(sys, 'frozen', False):
    BASE = Path(sys._MEIPASS)
    # Use the folder where the .exe actually lives for logs/data if needed
    EXE_DIR = Path(sys.executable).parent
else:
    BASE = Path(__file__).resolve().parent
    EXE_DIR = BASE

# ---------------- CUDA DLL setup for Windows ----------------
# ---------------- CUDA DLL setup for Windows ----------------
def add_cuda_dlls():
    if not hasattr(os, "add_dll_directory"):
        return
    
    # If running as an .exe, look inside the bundled PyInstaller folder; otherwise use .venv site-packages
    if getattr(sys, 'frozen', False):
        nvidia = BASE / "nvidia"
    else:
        nvidia = Path(sysconfig.get_paths()["purelib"]) / "nvidia"

    if nvidia.exists():
        for bin_dir in nvidia.glob("*/bin"):
            os.add_dll_directory(str(bin_dir))
            os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ["PATH"]
        for lib_dir in nvidia.glob("*/lib"):
            os.add_dll_directory(str(lib_dir))
            os.environ["PATH"] = str(lib_dir) + os.pathsep + os.environ["PATH"]

add_cuda_dlls()

add_cuda_dlls()

# ---------------- Audio & Whisper Settings ----------------
SAMPLE_RATE = 16000
BLOCK = 512
BLOCK_SEC = BLOCK / SAMPLE_RATE
CALIBRATE_SEC = 1.5
THRESHOLD_MULT = 3.0
MIN_THRESHOLD = 0.01
PRE_ROLL_SEC = 0.4
END_SILENCE_SEC = 0.8
MIN_SPEECH_SEC = 0.4
MAX_UTTERANCE_SEC = 5

STT_MIN = 0.40
AUTO_OPEN = False
OPEN_STT_MIN = 0.60
OPEN_SCORE_TRIGGERED = 80
OPEN_SCORE_PASSIVE = 95
CLOSE_SECOND_GAP = 3
OPEN_COOLDOWN_SEC = 10
CLOSEST_COUNT = 3  # Max 3 results per detection

INITIAL_PROMPT = ("Dungeons and Dragons spells: Bigby's Hand, Hunter's Mark, "
                  "Misty Step, Counterspell, Revivify, Fireball, Charm Person, "
                  "Spirit Guardians, Zone of Truth, Hellish Rebuke")

def load_whisper_model():
    # 1. Try CUDA (NVIDIA GPU) first
    try:
        print("Attempting to load Whisper on GPU (CUDA)...")
        m = WhisperModel("distil-large-v3", device="cuda", compute_type="float16")
        list(m.transcribe(np.zeros(SAMPLE_RATE, dtype="float32"))[0])
        print("Whisper successfully loaded on GPU!")
        return m
    except Exception as e:
        print(f"GPU unavailable or failed ({e}). Switching to optimized CPU fallback...")

    # 2. Upgraded CPU Fallback: Distil-Large-V3 (INT8) + Full Core Utilization
    try:
        # Determine optimal thread count based on available cores
        threads = os.cpu_count() or 4
        print(f"Loading Whisper on CPU using base.en (INT8) across {threads} threads...")
        
        m = WhisperModel(
            "base.en", 
            device="cpu", 
            compute_type="int8", 
            cpu_threads=threads
        )
        print("CPU fallback successfully loaded!")
        return m
    except Exception as e2:
        print(f"CPU fallback failed: {e2}")
        raise e2

def rms(block):
    return float(np.sqrt(np.mean(block ** 2)))

def speech_confidence(segments):
    total = weighted = 0.0
    for s in segments:
        dur = max(s.end - s.start, 0.01)
        conf = math.exp(s.avg_logprob) * (1.0 - s.no_speech_prob)
        weighted += conf * dur
        total += dur
    return weighted / total if total else 0.0


# ---------------- Whisper Background Worker ----------------
class WhisperWorker(QThread):
    utterance_result = Signal(str, float, bool, list, list)

    def __init__(self, matcher_obj, pages_dir):
        super().__init__()
        self.matcher = matcher_obj
        self.pages_dir = pages_dir

    def run(self):
        try:
            model = load_whisper_model()

            q = queue.Queue()
            def callback(indata, frames, time_info, status):
                q.put(indata[:, 0].copy())

            from collections import deque
            pre_roll = deque(maxlen=int(PRE_ROLL_SEC / BLOCK_SEC))
            end_blocks = int(END_SILENCE_SEC / BLOCK_SEC)
            max_blocks = int(MAX_UTTERANCE_SEC / BLOCK_SEC)
            min_blocks = int(MIN_SPEECH_SEC / BLOCK_SEC)

            with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                                blocksize=BLOCK, callback=callback):
                levels = [rms(q.get()) for _ in range(int(CALIBRATE_SEC / BLOCK_SEC))]
                threshold = max(MIN_THRESHOLD, float(np.median(levels)) * THRESHOLD_MULT)

                speech = []
                quiet_run = 0

                while True:
                    block = q.get()
                    loud = rms(block) > threshold

                    if not speech:
                        if loud:
                            speech = list(pre_roll) + [block]
                            quiet_run = 0
                        else:
                            pre_roll.append(block)
                        continue

                    speech.append(block)
                    quiet_run = 0 if loud else quiet_run + 1

                    if quiet_run >= end_blocks or len(speech) >= max_blocks:
                        voiced = len(speech) - quiet_run
                        audio = np.concatenate(speech)
                        speech, quiet_run = [], 0
                        pre_roll.clear()
                        
                        if voiced >= min_blocks:
                            segments, info = model.transcribe(
                                audio,
                                language="en",
                                vad_filter=True,
                                condition_on_previous_text=False,
                                initial_prompt=INITIAL_PROMPT,
                            )
                            segments = list(segments)
                            text = " ".join(s.text.strip() for s in segments).strip()
                            if not text:
                                continue
                            
                            stt_conf = speech_confidence(segments)
                            triggered, results = self.matcher.search(text)
                            hits = [(score, e, self.pages_dir / e["file"]) for score, e in results
                                    if (self.pages_dir / e["file"]).exists()]
                            
                            t_norm = matcher_mod._dedupe(matcher_mod._norm(text))
                            t_norm, _ = matcher_mod._strip_trigger(t_norm)
                            nearest = [(score, self.matcher.entries[i]) for score, i in self.matcher._rank(t_norm)[:CLOSEST_COUNT]]

                            self.utterance_result.emit(text, stt_conf, triggered, hits, nearest)
        except Exception as e:
            # Write the exact crash traceback to an error.log file next to the executable
            error_log_path = EXE_DIR / "error.log"
            error_log_path.write_text(traceback.format_exc(), encoding="utf-8")
            print("Audio stream crashed, logged to error.log")


# ---------------- Main Application Window ----------------
class MainWindow(QMainWindow):
    def __init__(self, base_path, matcher_obj):
        super().__init__()
        self.base = base_path
        self.pages = self.base / "pages"
        self.welcome_page = self.base / "welcome" / "welcome.html"
        self.matcher = matcher_obj
        
        self.last_opened = {}
        self.whisper_history = []

        self.init_ui()
        self.init_whisper()

    def init_ui(self):
        self.setWindowTitle("DMify")
        self.resize(1200, 700)

        # Set window icon
        icon_path = self.base / "icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # 1. Top Search Bar
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search spells, feats, monsters...")
        self.search_box.setClearButtonEnabled(True)
        main_layout.addWidget(self.search_box)

        # 2. Splitter for Left Panel (Passive Listening Feed) & Right Panel (Browser)
        self.results_list = QListWidget()
        
        sidebar_container = QWidget()
        sidebar_layout = QVBoxLayout(sidebar_container)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.addWidget(self.results_list)

        self.browser = QWebEngineView()

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(sidebar_container)
        splitter.addWidget(self.browser)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([250, 800])

        main_layout.addWidget(splitter)
        self.setCentralWidget(central_widget)

        # Signals
        self.search_box.textChanged.connect(self.on_search_changed)
        self.search_box.returnPressed.connect(self.on_search_return_pressed)
        self.results_list.itemClicked.connect(self.on_item_clicked)

        self.show_file(self.welcome_page)

    def init_whisper(self):
        self.worker = WhisperWorker(self.matcher, self.pages)
        self.worker.utterance_result.connect(self.handle_whisper_utterance)
        self.worker.start()

    def show_file(self, path):
        if not path.exists():
            print(f"Page not found: {path}")
            return
        self.browser.setUrl(QUrl.fromLocalFile(str(path)))

    def load_page(self, filename):
        self.show_file(self.pages / filename)

    def on_search_changed(self, text):
        self.results_list.clear()
        text = text.strip()
        
        if not text:
            self.refresh_whisper_display()
            return

        for score, entry in self.matcher.suggest(text):
            item = QListWidgetItem(f"{entry['name']}  ({score})")
            item.setData(Qt.UserRole, entry["file"])
            self.results_list.addItem(item)

    def on_search_return_pressed(self):
        if self.results_list.count() > 0:
            top_item = self.results_list.item(0)
            self.on_item_clicked(top_item)

    def on_item_clicked(self, item):
        filename = item.data(Qt.UserRole)
        if filename:
            self.load_page(filename)

    def handle_whisper_utterance(self, text, stt_conf, triggered, hits, nearest):
        print(f"Heard: {text!r} (conf: {stt_conf:.2f}, triggered: {triggered})")
        
        # Add up to 3 results ordered by confidence (highest first)
        for score, entry in reversed(nearest):
            self.whisper_history.insert(0, {
                "name": entry["name"],
                "category": entry["category"],
                "file": entry["file"],
                "score": score,
                "heard": text
            })
        
        # Cap history at 30 items
        self.whisper_history = self.whisper_history[:30]

        if not self.search_box.text().strip():
            self.refresh_whisper_display()

        if hits and AUTO_OPEN:
            score, e, path = hits[0]
            need = OPEN_SCORE_TRIGGERED if triggered else OPEN_SCORE_PASSIVE
            if score >= need and stt_conf >= OPEN_STT_MIN:
                if not (len(hits) > 1 and hits[1][0] >= score - CLOSE_SECOND_GAP):
                    now = time.time()
                    if now - self.last_opened.get(path, 0) >= OPEN_COOLDOWN_SEC:
                        self.last_opened[path] = now
                        print(f"Auto-opening: {path.name}")
                        self.show_file(path)

    def refresh_whisper_display(self):
        self.results_list.clear()
        for entry in self.whisper_history:
            item = QListWidgetItem(f"{entry['name']} ({entry['score']})")
            item.setData(Qt.UserRole, entry["file"])
            self.results_list.addItem(item)


def main():
    INDEX = BASE / "index.json"

    if not INDEX.exists():
        sys.exit("index.json not found. Run reindex.py first.")

    matcher = Matcher(str(INDEX))
    if not matcher.entries:
        sys.exit("index.json is empty. Run reindex.py first.")

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    # Fix Windows taskbar grouping so the custom icon appears correctly
    if os.name == 'nt':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("DMify.App.1.0")

    # Set application icon
    icon_path = BASE / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow(BASE, matcher)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()