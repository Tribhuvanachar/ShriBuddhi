"""Text conventions shared by the exporter, the dry run and the evaluation renderer (Kamadhenu Phase 8).

model_text() is the Vāgdhenu `model_text` convention (prep_text.strip_punct at the pinned commit in
tools/kamadhenu/space/build_space.sh), so a verse is spelled for training exactly as the Space spells it at
inference: a stray Latin colon becomes a visarga, daṇḍas / pipes / slashes / quotes / parentheses / digits are
dropped, a hyphen JOINS (compounds stay continuous), ZWJ/ZWNJ go, every run of whitespace — including the
pāda newline the pilot keeps — becomes one space. Avagraha (ऽ) and ॐ stay. No phonetic conversion: IndicF5 is a
character model and learns the pronunciation of a written string from the audio.
"""
import re

VISARGA = "ः"
PUNCT_DROP = set("।॥|/\\—–\"'“”‘’„«»‹›*•·().,;!?‌‍")
DEVA_DIGITS = "०१२३४५६७८९"


def model_text(text):
    t = str(text or "").replace(":-", VISARGA).replace(":", VISARGA)
    out = []
    for c in t:
        if c in PUNCT_DROP or c.isdigit() or c in DEVA_DIGITS or c in "-–—":
            continue
        out.append(c)
    return re.sub(r"\s+", " ", "".join(out)).strip()


def load_vocab(path):
    """vocab.txt → ordered list; index 0 must be the space (the trainer asserts it for char vocabs)."""
    with open(path, encoding="utf-8") as f:
        return [line[:-1] if line.endswith("\n") else line for line in f]


def unknown_chars(text, vocab):
    vs = vocab if isinstance(vocab, set) else set(vocab)
    return sorted({c for c in text if c not in vs})
