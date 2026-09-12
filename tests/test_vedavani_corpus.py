import importlib.util
import pathlib

spec = importlib.util.spec_from_file_location(
    "vedavani_corpus", pathlib.Path(__file__).resolve().parents[1] / "tools" / "vedavani_hf" / "vedavani_corpus.py")
vc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vc)


def test_norm_strips_accents_spaces_and_unifies_letters():
    assert vc.norm("अ॒ग्निमी॑ळे पु॒रोहि॑तं ।") == "अग्निमीडेपुरोहितं"
    assert vc.norm("अपोऽग्रियो") == "अपोग्रियो"
    assert vc.norm("Rigveda 1.1.1") == ""


def test_parse_name_variants():
    assert vc.parse_name("Rigveda_35_0340.wav") == ("rigveda", "Rigveda_35", 340)
    assert vc.parse_name("RigVeda_Part_016_0164.wav") == ("rigveda", "RigVeda_Part_016", 164)
    assert vc.parse_name("Atharvaveda_Kanda_11_0221.wav") == ("atharvaveda", "Atharvaveda_Kanda_11", 221)


class FakeIndex(vc.RigvedaIndex):
    def __init__(self, riks):
        self.ids = [r[0] for r in riks]
        self.texts = [vc.norm(r[1]) for r in riks]
        self.starts, self.big, pos = [], "", 0
        for t in self.texts:
            self.starts.append(pos)
            self.big += t
            pos += len(t)
        import collections
        self.grams = collections.defaultdict(list)
        for i, t in enumerate(self.texts):
            for k in range(0, max(0, len(t) - 7), 4):
                self.grams[t[k:k + 8]].append(i)


RIKS = [
    ("1.1.1", "अग्निमीळे पुरोहितं यज्ञस्य देवमृत्विजम् । होतारं रत्नधातमम् ॥"),
    ("1.1.2", "अग्निः पूर्वेभिर्ऋषिभिरीड्यो नूतनैरुत । स देवाँ एह वक्षति ॥"),
    ("1.1.3", "अग्निना रयिमश्नवत्पोषमेव दिवेदिवे । यशसं वीरवत्तमम् ॥"),
    ("2.9.9", "स नः सुदीतिः सुदृशा शतक्रतू यूयं पात स्वस्तिभिः सदा नः ॥"),
    ("2.9.10", "प्र वो अग्निः यूयं पात स्वस्तिभिः सदा नः ॥"),
]


def rows(*specs):
    out = []
    for name, text in specs:
        veda, group, seq = vc.parse_name(name)
        out.append({"audio_file": name, "text": text, "veda": veda, "group": group, "seq": seq})
    return out


def test_map_exact_span_fuzzy_resolved_and_unmatched():
    idx = FakeIndex(RIKS)
    rs = rows(("R_1_0001.wav", "अग्निमीळे पुरोहितं यज्ञस्य"),
              ("R_1_0002.wav", "होतारं रत्नधातमम् अग्निः पूर्वेभिर्ऋषिभिरीड्यो"),   # crosses 1.1.1 → 1.1.2
              ("R_1_0003.wav", "अग्निना रयिमश्नवत् पोषमेव दिवे दिवे यशसं वीरवन्तमम्"),  # one letter off → fuzzy
              ("R_2_0010.wav", "स नः सुदीतिः सुदृशा शतक्रतू"),
              ("R_2_0011.wav", "यूयं पात स्वस्तिभिः सदा नः"),                       # refrain in 2.9.9 and 2.9.10
              ("R_2_0012.wav", "प्र वो अग्निः"),
              ("R_3_0001.wav", "कश्चिदन्यः पाठः यो न विद्यते संहितायाम्"),
              ("R_3_0002.wav", "नमः"))
    stats = vc.map_rows(rs, idx)
    by = {r["audio_file"]: r for r in rs}
    assert by["R_1_0001.wav"]["match"] == "exact" and by["R_1_0001.wav"]["rik_ids"] == "1.1.1"
    assert by["R_1_0002.wav"]["match"] == "exact_span" and by["R_1_0002.wav"]["rik_ids"] == "1.1.1;1.1.2"
    assert by["R_1_0003.wav"]["match"] == "fuzzy" and by["R_1_0003.wav"]["rik_ids"] == "1.1.3"
    assert by["R_2_0011.wav"]["match"] == "resolved" and by["R_2_0011.wav"]["rik_ids"] == "2.9.9"
    assert by["R_3_0001.wav"]["match"] == "unmatched" and by["R_3_0001.wav"]["rik_ids"] == ""
    assert by["R_3_0002.wav"]["match"] == "too_short"
    assert stats["exact"] == 3 and stats["resolved"] == 1 and stats["unmatched"] == 1


def test_wav_info_parses_riff_header():
    import struct
    data = b"\x00\x00" * 16000
    fmt = struct.pack("<HHIIHH", 1, 1, 16000, 32000, 2, 16)
    b = b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE" + b"fmt " + struct.pack("<I", 16) + fmt + b"data" + struct.pack("<I", len(data)) + data
    assert vc.wav_info(b) == {"channels": 1, "rate": 16000, "bits": 16, "duration_s": 1.0}
    assert vc.wav_info(b"not a wav") is None
