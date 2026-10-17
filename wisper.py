import os
import sysconfig
from pathlib import Path

def add_cuda_dlls():
    """Tell Windows where pip-installed CUDA libraries live."""
    nvidia = Path(sysconfig.get_paths()["purelib"]) / "nvidia"
    for bin_dir in nvidia.glob("*/bin"):
    
        os.add_dll_directory(str(bin_dir))
        os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ["PATH"]

add_cuda_dlls()          # must run before faster_whisper is imported

import sounddevice as sd
from faster_whisper import WhisperModel
from matcher import Matcher

SAMPLE_RATE = 16000
SECONDS = 5


def load_model():
    try:
        m = WhisperModel("distil-large-v3", device="cuda", compute_type="float16")
        print("Using GPU")
        return m
    except Exception as e:
        print("GPU failed, using CPU instead:", e)
        return WhisperModel("small.en", device="cpu", compute_type="int8")


def main():
    print("Loading speech model (first run downloads it, be patient)...")
    model = load_model()
    matcher = Matcher()

    input("Press Enter, then speak...")
    print("Recording...")
    audio = sd.rec(int(SECONDS * SAMPLE_RATE),
                   samplerate=SAMPLE_RATE, channels=1, dtype="float32")
    sd.wait()
    audio = audio.flatten()
    print("Transcribing...")
    print("peak level:", round(float(abs(audio).max()), 3))   # under ~0.02 = mic too quiet

    segments, info = model.transcribe(
        audio,
        language="en",
        vad_filter=True,
        condition_on_previous_text=False,
    )
    segments = list(segments)       # it's a generator; this runs the transcription
    text = " ".join(s.text.strip() for s in segments)

    print(f"audio {info.duration:.1f}s, after VAD {info.duration_after_vad:.1f}s, "
          f"{len(segments)} segment(s)")
    print("I heard:", repr(text))
    triggered, results = matcher.search(text)
    print("trigger word heard:", triggered)
    for score, e in results:
        print(f"  {score:3}  {e['name']}  ({e['category']})")
    if not results:
        print("  (nothing matched)")


if __name__ == "__main__":
    main()