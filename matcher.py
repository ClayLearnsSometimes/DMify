import json
import re
from pathlib import Path

import jellyfish
import numpy as np
from rapidfuzz import fuzz, process

TRIGGERS = ("look up", "lookup", "pull up", "show me", "what is", "what does")
MAX_WINDOW = 7             # longest run of words to try (mishearing can split names up)
MIN_WINDOW_LETTERS = 4     # ignore tiny fragments like "of" or "the"
TRIGGER_MIN_SCORE = 70     # with a trigger word, accept looser matches
PASSIVE_MIN_SCORE = 90     # no trigger: only very confident matches
PASSIVE_MIN_LETTERS = 7    # no trigger: skip short names that are everyday words


def _norm(s):
    s = re.sub(r"[^a-z0-9 ]+", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()

def _dedupe(text):
    out = []
    for w in text.split():
        if not out or w != out[-1]:
            out.append(w)
    return " ".join(out)

def _phonetic(s):
    return "".join(jellyfish.metaphone(w) for w in s.split())

def _strip_trigger(text):
    """'ok lookup fire ball' -> ('fire ball', True)"""
    for trig in TRIGGERS:
        m = re.search(r"\b" + trig + r"\b", text)
        if m:
            return text[m.end():].strip(), True
    return text, False


class Matcher:
    def __init__(self, index_path="index.json"):
        self.entries = json.loads(Path(index_path).read_text(encoding="utf-8"))
        norms = [_norm(e["name"]) for e in self.entries]
        self.letters = [n.replace(" ", "") for n in norms]
        self.phon = [_phonetic(n) for n in norms]

    def _windows(self, text):
        words = text.split()
        seen = set()
        for n in range(1, min(MAX_WINDOW, len(words)) + 1):
            for i in range(len(words) - n + 1):
                w = " ".join(words[i:i + n])
                if len(w.replace(" ", "")) >= MIN_WINDOW_LETTERS and w not in seen:
                    seen.add(w)
                    yield w

    def _rank(self, text):
        wins = list(self._windows(text))
        if not wins:
            return []
        s1 = process.cdist([w.replace(" ", "") for w in wins], self.letters,
                           scorer=fuzz.ratio, workers=-1)
        s2 = process.cdist([_phonetic(w) for w in wins], self.phon,
                           scorer=fuzz.ratio, workers=-1)
        best = np.maximum(s1, s2).max(axis=0)          # best window for each name
        order = np.argsort(-best)[:20]
        return [(int(round(best[i])), int(i)) for i in order]

    def suggest(self, text, top=10, min_score=60):
        """For a search bar: no score cutoffs, and it copes with partial words."""
        t = _norm(text)
        letters = t.replace(" ", "")
        if not letters:
            return []

        found = {}                                   # entry number -> best score so far

        # 1. names that start with, or contain, what was typed (works for 1-3 letters)
        for i, name in enumerate(self.letters):
            if name.startswith(letters):
                found[i] = 100
            elif letters in name:
                found[i] = 90

        # 2. fuzzy + sound-alike matching (needs 4+ letters)
        if len(letters) >= MIN_WINDOW_LETTERS:
            for score, i in self._rank(t):
                found[i] = max(found.get(i, 0), score)

        ranked = [(i, s) for i, s in found.items() if s >= min_score]
        ranked = sorted(ranked, key=lambda kv: -kv[1])[:top]
        return [(score, self.entries[i]) for i, score in ranked]

    def search(self, text, top=5):
        """Returns (triggered, [(score, entry), ...])."""
        t = _dedupe(_norm(text))
        t, triggered = _strip_trigger(t)
        out = []
        for score, i in self._rank(t):
            if triggered:
                ok = score >= TRIGGER_MIN_SCORE
            else:
                ok = score >= PASSIVE_MIN_SCORE and len(self.letters[i]) >= PASSIVE_MIN_LETTERS
            if ok:
                out.append((score, self.entries[i]))
        return triggered, out[:top]