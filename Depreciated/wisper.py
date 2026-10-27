import math
import os
import queue
import sysconfig
import time
import webbrowser
from collections import deque
from pathlib import Path


def add_cuda_dlls():
    """Tell Windows where pip-installed CUDA libraries live."""
    if not hasattr(os, "add_dll_directory"):
        return                                   # not Windows
    nvidia = Path(sysconfig.get_paths()["purelib"]) / "nvidia"
    for bin_dir in nvidia.glob("*/bin"):
        os.add_dll_directory(str(bin_dir))
        os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ["PATH"]


add_cuda_dlls()          # must run before faster_whisper is imported

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
import matcher as matcher_mod
from matcher import Matcher

# ---------------- audio settings ----------------
SAMPLE_RATE = 16000
BLOCK = 512                       # samples per audio block (32 ms)
BLOCK_SEC = BLOCK / SAMPLE_RATE

CALIBRATE_SEC = 1.5               # measure room noise at startup
THRESHOLD_MULT = 3.0              # speech = this many times louder than noise
MIN_THRESHOLD = 0.01              # never go below this RMS level
PRE_ROLL_SEC = 0.4                # audio kept from before speech began
END_SILENCE_SEC = 0.8             # this much quiet ends an utterance
MIN_SPEECH_SEC = 0.4              # ignore shorter blips (coughs, clicks)
MAX_UTTERANCE_SEC = 15.0          # force a cut so it never records forever

# ---------------- confidence settings ----------------
# Matcher already applies its own score cutoffs (TRIGGER_MIN_SCORE / PASSIVE_MIN_SCORE
# in matcher.py). On top of that, two more checks happen here:
#   speech conf = how sure Whisper is about its own transcription (0-1)
#   match score = Matcher's 0-100 score for the best page
STT_MIN = 0.40                    # below this, matches are reported but ignored

AUTO_OPEN = True                  # open the best page in your browser
OPEN_STT_MIN = 0.60               # speech confidence needed to auto-open
OPEN_SCORE_TRIGGERED = 80         # after "look up ...", score needed to auto-open
OPEN_SCORE_PASSIVE = 95           # with no trigger phrase, score needed to auto-open
CLOSE_SECOND_GAP = 3              # if #2 is within this many points, don't guess
OPEN_COOLDOWN_SEC = 10            # don't reopen the same page within this time

CLOSEST_COUNT = 5                 # how many nearest pages to print for every utterance

# Biases Whisper toward your vocabulary. Add names you care about.
INITIAL_PROMPT = ("Dungeons and Dragons spells: Bigby's Hand, Hunter's Mark, "
                  "Misty Step, Counterspell, Revivify, Fireball, Charm Person, "
                  "Spirit Guardians, Zone of Truth, Hellish Rebuke")

last_opened = {}                  # page path -> time it was last opened


def find_root():
    """Find the folder holding index.json and pages/ (here, or up to 2 levels up)."""
    here = Path(__file__).resolve().parent
    for d in (here, here.parent, here.parent.parent):
        if (d / "index.json").exists() and (d / "pages").is_dir():
            return d
    raise FileNotFoundError(f"Couldn't find index.json and a pages/ folder near {here}")


def load_model():
    try:
        m = WhisperModel("distil-large-v3", device="cuda", compute_type="float16")
        # CUDA libraries often only fail on first use, so force it now
        list(m.transcribe(np.zeros(SAMPLE_RATE, dtype="float32"))[0])
        print("Using GPU")
        return m
    except Exception as e:
        print("GPU failed, using CPU instead:", e)
        return WhisperModel("small.en", device="cpu", compute_type="int8")


def rms(block):
    return float(np.sqrt(np.mean(block ** 2)))


def speech_confidence(segments):
    """Whisper's own certainty, 0-1: duration-weighted mean of exp(avg_logprob)."""
    total = weighted = 0.0
    for s in segments:
        dur = max(s.end - s.start, 0.01)
        conf = math.exp(s.avg_logprob) * (1.0 - s.no_speech_prob)
        weighted += conf * dur
        total += dur
    return weighted / total if total else 0.0


def closest(matcher, text, top=5):
    """Nearest pages by score, ignoring the cutoffs. Same prep as Matcher.search()."""
    t = matcher_mod._dedupe(matcher_mod._norm(text))
    t, _ = matcher_mod._strip_trigger(t)
    return [(score, matcher.entries[i]) for score, i in matcher._rank(t)[:top]]


def on_match(triggered, stt_conf, hits):
    """hits = [(score, entry, path), ...] best first, pages that exist locally."""
    score, e, path = hits[0]
    need = OPEN_SCORE_TRIGGERED if triggered else OPEN_SCORE_PASSIVE
    if not AUTO_OPEN:
        return
    if score < need or stt_conf < OPEN_STT_MIN:
        print("  (not confident enough to open automatically)")
        return
    if len(hits) > 1 and hits[1][0] >= score - CLOSE_SECOND_GAP:
        print("  (close second match, not opening automatically)")
        return

    now = time.time()
    if now - last_opened.get(path, 0) < OPEN_COOLDOWN_SEC:
        return
    last_opened[path] = now
    print(f"  opening {path.name}")
    webbrowser.open(path.as_uri())


def handle_utterance(model, matcher, pages_dir, audio):
    segments, info = model.transcribe(
        audio,
        language="en",
        vad_filter=True,
        condition_on_previous_text=False,
        initial_prompt=INITIAL_PROMPT,
    )
    segments = list(segments)                  # generator: this runs the transcription
    text = " ".join(s.text.strip() for s in segments).strip()

    # printed for EVERY utterance, even when Whisper returns nothing
    print(f"\naudio {len(audio) / SAMPLE_RATE:.1f}s, "
          f"peak level {float(np.abs(audio).max()):.3f}, "
          f"after VAD {info.duration_after_vad:.1f}s, {len(segments)} segment(s)")
    if not text:
        print("  (Whisper returned no text)")
        return
    stt_conf = speech_confidence(segments)

    triggered, results = matcher.search(text)
    passed = {e["file"] for _, e in results}       # cleared Matcher's own cutoffs
    # keep only pages that actually exist in the pages folder
    hits = [(score, e, pages_dir / e["file"]) for score, e in results
            if (pages_dir / e["file"]).exists()]

    print(f"heard: {text!r}   (speech confidence {stt_conf:.2f}, "
          f"trigger: {triggered})")

    # always show the closest pages, even when nothing cleared the cutoffs
    nearest = closest(matcher, text, CLOSEST_COUNT)
    for score, e in nearest:
        flags = []
        if e["file"] in passed:
            flags.append("passed")
        if not (pages_dir / e["file"]).exists():
            flags.append("no local page")
        note = f"   [{', '.join(flags)}]" if flags else ""
        print(f"  {score:3}  {e['name']}  ({e['category']}){note}")
    if nearest:
        print("highest confidence:", nearest[0][1]["name"])

    if not hits:
        print("  (nothing cleared the match cutoff)")
        return
    if stt_conf < STT_MIN:
        print(f"  matches ignored: Whisper only {stt_conf:.2f} sure of what it heard")
        return
    on_match(triggered, stt_conf, hits)


def listen_forever(model, matcher, pages_dir):
    q = queue.Queue()

    def callback(indata, frames, time_info, status):
        q.put(indata[:, 0].copy())     # runs on the audio thread: just queue it

    pre_roll = deque(maxlen=int(PRE_ROLL_SEC / BLOCK_SEC))
    end_blocks = int(END_SILENCE_SEC / BLOCK_SEC)
    max_blocks = int(MAX_UTTERANCE_SEC / BLOCK_SEC)
    min_blocks = int(MIN_SPEECH_SEC / BLOCK_SEC)

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                        blocksize=BLOCK, callback=callback):
        # --- calibrate to the room's background noise ---
        print("Calibrating to background noise, stay quiet...")
        levels = [rms(q.get()) for _ in range(int(CALIBRATE_SEC / BLOCK_SEC))]
        threshold = max(MIN_THRESHOLD, float(np.median(levels)) * THRESHOLD_MULT)
        print(f"Speech threshold: {threshold:.4f}")
        print('Listening... say e.g. "look up fireball" (Ctrl+C to stop)')

        speech = []                    # blocks of the current utterance
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
                    handle_utterance(model, matcher, pages_dir, audio)


def main():
    root = find_root()
    pages_dir = root / "pages"
    matcher = Matcher(str(root / "index.json"))     # not cwd-dependent
    print(f"Loaded {len(matcher.entries)} index entries, pages in {pages_dir}")
    print("Loading speech model (first run downloads it, be patient)...")
    model = load_model()
    try:
        listen_forever(model, matcher, pages_dir)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()