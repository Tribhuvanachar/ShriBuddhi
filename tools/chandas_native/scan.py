"""
Clean-room laghu-guru (light-heavy) scansion of Devanagari Sanskrit verse.

Implements the standard classical rule (Pingala's Chandahshastra tradition,
as taught in every Sanskrit prosody primer -- not derived from any specific
software implementation):

  1. Segment the string into akshara (syllables): each syllable = optional
     consonant cluster (onset) + one vowel (independent vowel letter, or a
     consonant carrying a dependent vowel sign / matra, or a bare consonant
     whose vowel is the inherent 'a').
  2. A syllable is GURU (heavy, marked G) if:
       a. its vowel is inherently long (aa/ii/uu/repha-long/e/ai/o/au), OR
       b. it is immediately followed by anusvara or visarga, OR
       c. it is immediately followed by a conjunct -- i.e. two or more
          consonants stand between this syllable's vowel and the next
          vowel (samyoga).
     Otherwise it is LAGHU (light, marked L).
  3. The final syllable of a pada is prosodically "anceps" (its natural
     weight is often overridden by the pause) -- for pattern matching we
     treat it as a wildcard that matches either L or G, rather than
     guessing.
"""

VIRAMA = "्"
ANUSVARA = "ं"
VISARGA = "ः"
CANDRABINDU = "ँ"

INDEPENDENT_LONG_VOWELS = set("आईऊॠॡएऐओऔ")
INDEPENDENT_SHORT_VOWELS = set("अइउऋऌ")
INDEPENDENT_VOWELS = INDEPENDENT_LONG_VOWELS | INDEPENDENT_SHORT_VOWELS

# dependent vowel signs (matras) attached to a consonant
LONG_MATRAS = set("ाीूॄॣेैोौ")
SHORT_MATRAS = set("िुृॢ")
MATRAS = LONG_MATRAS | SHORT_MATRAS

CONSONANTS = set(
    "कखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसहळ" "क़ख़ग़ज़ड़ढ़फ़य़"
)

WHITESPACE_AND_PUNCT = set(" \t\n।॥,.;:!?()-\"'")


def _is_consonant(ch):
    return ch in CONSONANTS


def syllabify(text):
    """Return a list of syllables, each a dict with the raw text and
    whether its own vowel is long, plus whether it's directly followed by
    anusvara/visarga and how many consonants follow before the next vowel."""
    chars = [c for c in text if c not in WHITESPACE_AND_PUNCT]
    n = len(chars)
    i = 0
    syllables = []
    while i < n:
        start = i
        # consume onset consonants (with their viramas) up to the vowel-bearer
        while i < n and _is_consonant(chars[i]):
            if i + 1 < n and chars[i + 1] == VIRAMA:
                i += 2  # consonant + virama, part of onset, keep going
            else:
                break  # this consonant carries the syllable's vowel
        if i >= n:
            # trailing consonant cluster with no vowel (rare/malformed) -- attach to previous
            if syllables:
                syllables[-1]["raw"] += "".join(chars[start:])
            break
        vowel_is_long = None
        if chars[i] in INDEPENDENT_VOWELS:
            vowel_is_long = chars[i] in INDEPENDENT_LONG_VOWELS
            i += 1
        elif _is_consonant(chars[i]):
            # consonant carries inherent 'a' (short) or an explicit matra
            i += 1
            if i < n and chars[i] in MATRAS:
                vowel_is_long = chars[i] in LONG_MATRAS
                i += 1
            else:
                vowel_is_long = False  # inherent short 'a'
        else:
            i += 1
            continue  # stray mark, skip
        # trailing anusvara/visarga/candrabindu directly on this syllable
        has_nasal_or_visarga = False
        if i < n and chars[i] in (ANUSVARA, VISARGA, CANDRABINDU):
            has_nasal_or_visarga = True
            i += 1
        syllables.append({
            "raw": "".join(chars[start:i]),
            "vowel_long": vowel_is_long,
            "nasal_visarga": has_nasal_or_visarga,
        })
    # now compute conjunct-follows: count consonants between this syllable's
    # vowel and the next syllable's vowel-bearer
    for idx, syl in enumerate(syllables):
        if idx + 1 >= len(syllables):
            syl["conjunct_follows"] = False
            continue
        nxt = syllables[idx + 1]["raw"]
        # onset consonants of next syllable, i.e. consonant+virama pairs before the vowel-bearer
        j = 0
        onset_consonants = 0
        while j < len(nxt) and _is_consonant(nxt[j]):
            if j + 1 < len(nxt) and nxt[j + 1] == VIRAMA:
                onset_consonants += 1
                j += 2
            else:
                onset_consonants += 1  # the vowel-bearing consonant itself
                j += 1
                break
        # a conjunct means 2+ consonants stand between the vowels: the
        # vowel-bearing consonant of the next syllable PLUS any consonants
        # before it in that same onset count as "between".
        syl["conjunct_follows"] = onset_consonants >= 2
    return syllables


def scan(text):
    """Return a string of 'L'/'G' for each syllable (last syllable = 'X' wildcard)."""
    syllables = syllabify(text)
    pattern = []
    for idx, syl in enumerate(syllables):
        is_last = idx == len(syllables) - 1
        if is_last:
            pattern.append("X")
            continue
        guru = syl["vowel_long"] or syl["nasal_visarga"] or syl["conjunct_follows"]
        pattern.append("G" if guru else "L")
    return "".join(pattern), syllables


def matches(pattern, template):
    """Does a scanned pattern (with 'X' wildcards) match a template of L/G?"""
    if len(pattern) != len(template):
        return False
    for p, t in zip(pattern, template):
        if p == "X" or t == "X":
            continue
        if p != t:
            return False
    return True


if __name__ == "__main__":
    import sys
    verse = sys.argv[1] if len(sys.argv) > 1 else "धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः"
    pattern, _syllables = scan(verse)
    print(verse)
    print(pattern, len(pattern))
