#!/usr/bin/env python3
"""
padaccheda.py — पदच्छेदः: cutting a written Sanskrit word back into the words
that were joined to make it, using only data this repository already ships.

THE PROBLEM IS NOT WHITESPACE. Sanskrit text already carries spaces at most
word boundaries; what it does not carry is a boundary where sandhi has welded
two words into one written token. Sumadhva Vijaya 1.1 writes

    नारायणायाखिलकारणाय

which is नारायणाय + अखिलकारणाय, fused at आय + अ → आया. A splitter that only
looked for substrings would never find the second word, because अखिलकारणाय's
initial अ is not present in the written form at all — it was absorbed. So the
split has to UNDO the junction, not merely locate it.

THE METHOD. Model the token as a graph: nodes are character positions 0..n,
and an edge i→j means "a real word occupies S[i:j], possibly after restoring
what sandhi took from its end, and leaves the next word starting at j with
what sandhi took from ITS beginning". Every edge is validated against the
shipped vocabulary — 295,958 words: कोश headwords, 205k tiṅanta forms, 49k
kṛdantas — so a candidate that is not a real word is discarded rather than
offered. Then take the cheapest path from 0 to n.

That validation is the whole difference between this and a combinatorial
splitter, which will happily offer न + आरायणायाखिलकारणाय.

COST, AND WHY IT IS SHAPED THIS WAY. Two words that are both common beat five
that are individually possible. Each piece costs a fixed amount for existing
at all (so the shortest analysis wins ties), minus a term for how often the
corpus actually uses it, plus a penalty for being very short — a two-character
piece is usually the splitter finding a particle inside a longer word rather
than a real boundary.

WHAT THIS IS NOT. It is not a parser: it offers no case, number or agreement,
and it cannot tell a correct split from a merely possible one when both halves
are real words. Where a text ships a human-made padaccheda, that is used and
this never runs. Accuracy is measured, not asserted — see
tools/build_padaccheda.py --evaluate.
"""

import re
import unicodedata
from heapq import heappush, heappop

# --- Devanagari mechanics ---------------------------------------------------
VIRAMA = '्'
SIGN_TO_VOWEL = {
    'ा': 'आ', 'ि': 'इ', 'ी': 'ई', 'ु': 'उ', 'ू': 'ऊ', 'ृ': 'ऋ', 'ॄ': 'ॠ',
    'ॢ': 'ऌ', 'े': 'ए', 'ै': 'ऐ', 'ो': 'ओ', 'ौ': 'औ',
}
VOWEL_TO_SIGN = {v: k for k, v in SIGN_TO_VOWEL.items()}
INDEPENDENT_VOWELS = set('अआइईउऊऋॠऌॡएऐओऔ')
MATRAS = set(SIGN_TO_VOWEL) | {VIRAMA, 'ं', 'ः', 'ँ'}

# Junction table: the written form at the seam, and what the two words really
# ended and began with. Read as "seeing `fuse` here means the left word ended
# with `left` and the right word began with one of `right`".
#
# Written out as data for the same reason vyakarana-runtime.js's copy is: the
# alternative, inverting sandhi in code, is where a rule keyed twice silently
# overwrites itself. गुणः ओ = अ + उ and the visarga ओ = अः + अ are BOTH true
# and must both be tried; a dict keyed on 'ओ' can only hold one.
JUNCTIONS = [
    # सवर्णदीर्घः — अ/आ + अ/आ → आ
    ('ा', ['', 'ा'], ['अ', 'आ'], 'सवर्णदीर्घः', '6.1.101'),
    ('ी', ['ि', 'ी'], ['इ', 'ई'], 'सवर्णदीर्घः', '6.1.101'),
    ('ू', ['ु', 'ू'], ['उ', 'ऊ'], 'सवर्णदीर्घः', '6.1.101'),
    # गुणः — अ/आ + इ/ई → ए ; अ/आ + उ/ऊ → ओ ; अ/आ + ऋ → अर्
    ('े', ['', 'ा'], ['इ', 'ई'], 'गुणः', '6.1.87'),
    ('ो', ['', 'ा'], ['उ', 'ऊ'], 'गुणः', '6.1.87'),
    # वृद्धिः — अ/आ + ए/ऐ → ऐ ; अ/आ + ओ/औ → औ
    ('ै', ['', 'ा'], ['ए', 'ऐ'], 'वृद्धिः', '6.1.88'),
    ('ौ', ['', 'ा'], ['ओ', 'औ'], 'वृद्धिः', '6.1.88'),
    # यण् — इ/ई + vowel → य् ; उ/ऊ + vowel → व् ; ऋ + vowel → र्
    ('्य', ['ि', 'ी'], None, 'यण्', '6.1.77'),
    ('्व', ['ु', 'ू'], None, 'यण्', '6.1.77'),
    ('्र', ['ृ'], None, 'यण्', '6.1.77'),
    # विसर्गः — अः + voiced → ओ ; आः + voiced → आ ; ः + श/ष/स → श्च etc.
    ('ो', ['ः'], None, 'विसर्गः (उत्वम्)', '6.1.113'),
    ('ा', ['ाः'], None, 'विसर्गलोपः', '8.3.14'),
    ('र्', ['ः'], None, 'विसर्गस्य रः', '8.2.66'),
    ('श्', ['ः'], ['श'], 'श्चुत्वम्', '8.4.40'),
    ('ष्', ['ः'], ['ष'], 'ष्टुत्वम्', '8.4.41'),
    ('स्', ['ः'], ['स'], 'विसर्गस्य सः', '8.3.34'),
    # जश्त्वम् — a word-final unvoiced stop is written voiced before a vowel or
    # a voiced sound: तत् + इति → तदिति, तस्मात् + इति → तस्मादिति. Without
    # this the commonest citation form in the whole grammatical literature is
    # invisible, and the search falls back on nonsense (तस् + मा + आदित्).
    ('द्', ['त्'], None, 'जश्त्वम्', '8.2.39'),
    ('ब्', ['प्'], None, 'जश्त्वम्', '8.2.39'),
    ('ग्', ['क्'], None, 'जश्त्वम्', '8.2.39'),
    ('ज्', ['च्'], None, 'जश्त्वम्', '8.2.39'),
    ('ड्', ['ट्'], None, 'जश्त्वम्', '8.2.39'),
    # श्चुत्वम् + छत्वम् — त् + श् → च्छ्: तत् + श्रुत्वा → तच्छ्रुत्वा.
    ('च्छ्', ['त्'], ['श्'], 'श्चुत्वम्+छत्वम्', '8.4.40'),
    ('च्', ['त्'], ['च', 'छ'], 'श्चुत्वम्', '8.4.40'),
    ('ज्', ['त्'], ['ज', 'झ'], 'श्चुत्वम्', '8.4.40'),
    ('ल्', ['त्'], ['ल'], 'लत्वम्', '8.4.60'),
    ('न्न', ['त्'], ['न'], 'अनुनासिकः', '8.4.45'),
    ('द्ध', ['त्'], ['ध'], 'जश्त्वम्', '8.2.39'),
    # अनुस्वारः — a final म् before a consonant is written ं.
    ('ं', ['म्'], None, 'अनुस्वारः', '8.3.23'),
]

# A word can also simply abut the next with no change at all — the commonest
# case of all, and the one a rule table would miss by looking only at seams.
PLAIN = ('', [''], None, 'सन्धिरहितम्', '')


def is_devanagari(text):
    return any('ऀ' <= c <= 'ॿ' for c in text)


AVAGRAHA = 'ऽ'


def expand_avagraha(word):
    """सोऽपि → सो + अपि.

    The avagraha is not punctuation to be stripped: it is a printed mark
    saying "an अ stood here and was elided", which is precisely the boundary
    a padaccheda wants. Dropping it (as the word-mark normaliser does, where
    it only needs a lookup key) would throw away the one place the text tells
    us where the join is."""
    if AVAGRAHA not in word:
        return word
    return word.replace(AVAGRAHA, 'अ')


def strip_punct(word):
    return re.sub(r'^[।॥॰,.;:!?"\'()\[\]{}—–\-…*‘’“”\s]+|'
                  r'[।॥॰,.;:!?"\'()\[\]{}—–\-…*‘’“”\s]+$', '', word or '')


def restore_left(prefix, ending):
    """The left word with what sandhi took from its end put back.

    A prefix ending in a consonant carries an inherent 'a' that a vowel sign
    would have replaced, so restoring '' (inherent a) and restoring 'ा' are
    different words and both are tried by the caller."""
    if not prefix:
        return None
    if ending == '':
        return prefix
    if ending in MATRAS or ending in ('ाः', 'ः'):
        return prefix + ending
    return prefix + ending


def restore_right(rest, beginning):
    """The right word with its absorbed initial vowel put back."""
    if beginning is None:
        # यण् and the visarga rules leave the right word's own initial intact.
        first = rest[:1]
        if first in SIGN_TO_VOWEL:
            return SIGN_TO_VOWEL[first] + rest[1:]
        return rest
    return beginning + rest


class Segmenter:
    """Splits one written token into the words joined to make it.

    vocab  set of real Devanagari words
    freq   optional {word: corpus count}, used only to prefer the analysis a
           reader is more likely to be looking at
    """

    #: A piece has to earn its place: every extra cut costs this much.
    CUT_COST = 10.0
    #: Below this many characters a piece is usually a particle found inside a
    #: longer word rather than a real boundary.
    SHORT_LEN = 3
    SHORT_PENALTY = 6.0
    #: How much corpus frequency is allowed to move a decision. Capped, so a
    #: very common short word cannot buy an implausible split.
    FREQ_WEIGHT = 1.0
    FREQ_CAP = 8.0
    #: Tokens longer than this are left alone: the lattice is quadratic in
    #: length and a 40-character compound is a compound, not a sandhi join.
    MAX_LEN = 32
    #: A split into more pieces than this is noise, whatever it costs.
    MAX_PIECES = 6

    def __init__(self, vocab, freq=None, stems=None, avyaya=None, inflected=None, verbs=None):
        self.vocab = vocab
        self.freq = freq or {}
        # The two sets that tell a compound from a pair of joined words.
        # A samāsa's non-final members are prātipadikas — bare stems, with no
        # case ending at all — while two words joined by sandhi are each
        # complete. So पूर्वशैलशिखरे is पूर्व-शैल-शिखरे (both पूर्व and शैल are
        # stems) and मुहुर्महान्तः is मुहुः + महान्तः (मुहुः is an
        # indeclinable, a whole word). Nothing here is guessed from the shape
        # of the word: the lemmas come straight out of _morph's subanta
        # records, which name the stem each form was derived from.
        self.stems = stems or set()
        self.avyaya = avyaya or set()
        # Forms that carry a case ending. The lemma list has real gaps —
        # प्राण is a word this corpus uses 2,664 times and is in no subanta
        # record as a lemma — so "is a stem" is answered two ways: it is
        # named as a lemma, OR it is a known word carrying no case ending at
        # all, which is what a prātipadika is.
        self.inflected = inflected or set()
        # A finite verb is a whole word, never a compound member.
        self.verbs = verbs or set()

    def word_cost(self, word):
        import math
        cost = self.CUT_COST
        if len(word) < self.SHORT_LEN:
            cost += self.SHORT_PENALTY
        n = self.freq.get(word, 0)
        if n:
            cost -= min(self.FREQ_CAP, self.FREQ_WEIGHT * math.log1p(n))
        return cost

    def edges_from(self, text):
        """Every word that can start at position 0 of `text`.

        Yields (consumed, left_word, carry, rule): `consumed` characters of
        `text` are used up, `left_word` is the real word found there, and
        `carry` is what sandhi hands forward to the next word and must be
        prepended to the remainder before it is looked up."""
        out = []
        n = len(text)
        for j in range(1, n + 1):
            piece = text[:j]
            # Never cut inside a syllable: a vowel sign, virāma or anusvāra
            # belongs to the consonant before it. The one real exception is
            # handled first, because it is the commonest junction there is.
            if j < n and text[j] in MATRAS:
                if text[j] in SIGN_TO_VOWEL:
                    out.extend(self._consonant_vowel_edges(text, j))
                continue
            if piece in self.vocab:
                out.append((j, piece, '', PLAIN[3]))
            for fuse, lefts, rights, rule, _sutra in JUNCTIONS:
                if not piece.endswith(fuse):
                    continue
                stem = piece[:len(piece) - len(fuse)]
                if not stem:
                    continue
                for left in lefts:
                    cand = restore_left(stem, left)
                    if not cand or cand not in self.vocab:
                        continue
                    if rights is None:
                        # यण्/विसर्ग: the right word keeps its own initial. After
                        # a यण् seam that initial is sitting in the text as a
                        # DEPENDENT sign (प्रत्य|ुवाच), so it is lifted to the
                        # independent letter and consumed here.
                        tail = text[j:]
                        if not tail:
                            continue
                        if tail[0] in SIGN_TO_VOWEL:
                            out.append((j + 1, cand, SIGN_TO_VOWEL[tail[0]], rule))
                        else:
                            out.append((j, cand, '', rule))
                    else:
                        for right in rights:
                            out.append((j, cand, right, rule))
        return out

    #: A word-final stop is written voiced before a vowel (जश्त्वम्), so the
    #: consonant seen at the seam has to be un-voiced to recover the left word.
    DEVOICE = {'द': 'त', 'ब': 'प', 'ग': 'क', 'ज': 'च', 'ड': 'ट',
               'ध': 'थ', 'भ': 'फ', 'घ': 'ख', 'झ': 'छ', 'ढ': 'ठ'}

    def _consonant_vowel_edges(self, text, j):
        """The join with no virāma left to see: तत् + इति → तदिति.

        A consonant-final word before a vowel-initial one loses its virāma
        entirely — the vowel sign takes its place, and the consonant is voiced
        on the way (8.2.39). So at a vowel SIGN the character before it may be
        the last letter of the previous word rather than part of this one, and
        the sign itself is the next word's own initial vowel. Nothing in the
        writing marks this; without the rule, तदिति and तस्मादिति — the
        commonest citation forms in the grammatical literature — have no
        analysis at all, and the search settles for nonsense instead
        (तस् + मा + आदित् + युत् + तरस्य).
        """
        out = []
        cons = text[j - 1]
        if cons in MATRAS or not is_devanagari(cons):
            return out
        stem = text[:j - 1]
        if not stem:
            return out
        vowel = SIGN_TO_VOWEL[text[j]]
        # The devoiced reading first: तत् is the editorially standard recovery
        # of तदिति, and तद् is also a real stem, so on an exact tie the one a
        # padaccheda would print should win.
        for letter in (self.DEVOICE.get(cons), cons):
            if not letter:
                continue
            cand = stem + letter + VIRAMA
            if cand in self.vocab:
                # j+1: the consonant and the vowel sign are both consumed here,
                # the vowel handed forward as the next word's first letter.
                out.append((j + 1, cand, vowel, 'जश्त्वम् / स्वरसन्धिः'))
        return out

    def split(self, token):
        """[(word, rule), …] for the cheapest analysis, or None.

        None means no analysis worth showing: either nothing parsed, or the
        only parse is the token itself, which is not a split."""
        s = expand_avagraha(strip_punct(token))
        if not s or not is_devanagari(s) or len(s) > self.MAX_LEN:
            return None
        if s in self.vocab and len(s) <= self.SHORT_LEN + 2:
            # A short word that is itself in the lexicon is a word, not a join.
            return None
        return self._search(s)

    def _search(self, s, force_split=False, stem_gate=False,
                min_piece=0, min_freq=0, max_pieces=None):
        """The lattice both analyses run on.

        Dijkstra over (position in s, what the previous junction handed
        forward) — the carry is part of the state because the vocabulary
        lookup for the next piece depends on it. Two gates make one search
        answer two questions:

          force_split  refuse the undivided token however cheap it is. A
                       compound is usually in the lexicon whole, so without
                       this the answer to "what is धर्मक्षेत्रे made of" is
                       always "धर्मक्षेत्रे".
          stem_gate    every piece but the last must be a bare stem, which is
                       what a samāsa's non-final members are.
        """
        max_pieces = max_pieces or self.MAX_PIECES
        start = (0, '')
        best = {start: 0.0}
        back = {}
        heap = [(0.0, 0, 0, '')]      # cost, pieces so far, position, carry
        goal = None
        while heap:
            cost, pieces, i, carry = heappop(heap)
            key = (i, carry)
            if cost > best.get(key, float('inf')) + 1e-9:
                continue
            if i == len(s) and not carry:
                if not force_split or pieces >= 2:
                    goal = key
                    break
                continue
            if pieces >= max_pieces:
                continue
            text = carry + s[i:]
            for consumed, word, give, rule in self.edges_from(text):
                # `consumed` counts characters of `text`; the ones belonging
                # to the carry are already behind us.
                advance = consumed - len(carry)
                if advance <= 0:
                    continue
                j = i + advance
                if j > len(s):
                    continue
                is_last = (j == len(s) and not give)
                if force_split and i == 0 and is_last:
                    # The undivided token. Under force_split it is not an
                    # answer — and it must not even be explored, because the
                    # search state is keyed on position alone: letting the
                    # one-piece path reach the end first records a cost no
                    # real split can beat, and the compound is never found.
                    # (धर्मक्षेत्रे was only ever split because the whole
                    # compound happened to fall below the frequency gate.)
                    continue
                if min_piece and len(word.rstrip(VIRAMA)) < min_piece \
                        and word not in self.VIGRAHA_SHORT_MEMBERS:
                    continue
                if min_freq and self.freq and self.freq.get(word, 0) < min_freq:
                    continue
                if stem_gate and not is_last and not self.is_stem(word):
                    continue
                nxt = (j, give)
                c = cost + self.word_cost(word)
                if stem_gate:
                    # A compound member is the BARE stem, so where a junction
                    # offers two readings of the same span the unmarked one is
                    # right: कल्याण-गुण-एक-धाम्ने, not कल्याण-गुणा-…, even
                    # though गुणा is also a word and the corpus writes it more
                    # often (1,518 against 1,299). Frequency is the wrong
                    # judge of a question grammar has already settled.
                    c += 0.5 * len(word)
                if c < best.get(nxt, float('inf')):
                    best[nxt] = c
                    back[nxt] = (key, word, rule)
                    heappush(heap, (c, pieces + 1, j, give))
        if goal is None:
            return None
        out = []
        cur = goal
        while cur in back:
            prev, word, rule = back[cur]
            out.append((word, rule))
            cur = prev
        out.reverse()
        if len(out) < 2:
            return None
        return out

    # ---- confidence -------------------------------------------------------
    #: A split is only worth showing a reader if we would defend it. These are
    #: the conditions under which we would; anything else is reported as no
    #: analysis rather than a guess dressed as an answer.
    CONFIDENT_MAX_PIECES = 3
    CONFIDENT_MIN_FREQ = 3
    CONFIDENT_MIN_PIECE_LEN = 3
    #: The words allowed to be shorter than that. A short piece is otherwise
    #: almost always a case ending mistaken for a word — विकटेन cut as
    #: विकटा + इन, अंशवो as अंश + वो, तन्वीषु as तन्वी + इषु, all of which are
    #: single declined forms. Sanskrit's genuinely free-standing short words
    #: are a small closed class, so listing them is exact rather than a
    #: heuristic, and इव has to be on it or सखीव → सखी + इव is lost with the
    #: noise.
    SHORT_WORDS = frozenset([
        'इव', 'इति', 'अपि', 'एव', 'च', 'तु', 'हि', 'वा', 'न', 'स्म', 'ननु',
        'यत्', 'तत्', 'सः', 'सा', 'ते', 'मे', 'नु', 'उ', 'ह', 'वै', 'अथ',
        'यदि', 'तदा', 'सदा', 'कदा', 'पुनः', 'इह', 'अतः', 'ततः', 'यथा', 'तथा',
        'अहम्', 'त्वम्', 'मया', 'किम्', 'सह', 'विना', 'प्रति', 'अनु', 'उप',
    ])

    # ---- samāsa vs sandhi -------------------------------------------------
    SEAM_SAMASA = '-'
    SEAM_SANDHI = '+'

    def seam_between(self, left, right, rule=None):
        """Which mark belongs between two pieces.

        Both sides matter. मेखला is a stem, so looking only leftward marks
        मेखलेव as मेखला-इव — but इव is an indeclinable, a whole word, and the
        join is sandhi. An avyaya on EITHER side is a word boundary, however
        stem-like the other side looks (इति and एव are themselves listed as
        lemmas in the morphology, which is why the avyaya reading has to
        win)."""
        if self.is_whole_word(left) or self.is_whole_word(right):
            return self.SEAM_SANDHI
        # Plain abutment inside ONE written token is what a compound is: two
        # members written together with nothing happening at the seam. That
        # reading beats the lemma lookup, which has gaps — प्राण is used 2,664
        # times in this corpus and is in no subanta record as a lemma, while
        # being a valid vocative, so asking the morphology whether it is a
        # stem gets श्री-प्राण-नाथाय wrong at the second seam.
        if rule == PLAIN[3]:
            return self.SEAM_SAMASA
        return self.SEAM_SAMASA if self.is_stem(left) else self.SEAM_SANDHI

    def is_whole_word(self, word):
        """Something that can only stand as a word, never as a compound member:
        an indeclinable, a finite verb, or one of the particles.

        The morphology's avyaya records do not cover इति — it is listed there
        as a lemma and an inflected form, and nowhere as an indeclinable — so
        the particle list has to carry it, or कान्तायेति comes out as
        कान्ताय-इति."""
        return word in self.avyaya or word in self.verbs or word in self.SHORT_WORDS

    def is_stem(self, word):
        """A bare prātipadika: named as a lemma, or a word the morphology
        knows and has never seen carrying a case ending."""
        if word in self.avyaya:
            return False
        if word in self.stems:
            return True
        return bool(self.inflected) and word in self.vocab and word not in self.inflected

    #: A compound member carries no case ending, so the short-particle
    #: exemption does not apply to it; and a token this short is a word.
    #: A compound is a long word. Below this it is far likelier that a short
    #: token is being cut into two lexicon entries that happen to abut —
    #: कान्ताय into कान्ता-अय, नैच्छत् into ना-ऐच्छत्.
    VIGRAHA_MIN_TOKEN = 9
    #: Members are substantial. Two-character members are where the damage
    #: was: सभाजितानि came out as सभा-जि-तानि, जि being a real root and तानि
    #: a real form, and the whole thing nonsense.
    VIGRAHA_MIN_MEMBER = 3
    #: Except the numerals, which are genuinely short and genuinely common as
    #: first members (कल्याण-गुण-एक-धाम्ने).
    VIGRAHA_SHORT_MEMBERS = frozenset(['एक', 'द्वि', 'त्रि', 'षट्', 'सप्त', 'अष्ट', 'नव', 'दश'])
    VIGRAHA_MAX_MEMBERS = 5
    VIGRAHA_MIN_FREQ = 5

    def vigraha(self, token):
        """Break a compound into its members, or None.

        Distinct from split() in what it is allowed to do: a samāsa is ONE
        word, usually one the lexicon lists in full (धर्मक्षेत्रे is in
        there), so the cheapest path is always the undivided token and the
        sandhi search correctly refuses to cut it. Here that single-piece
        answer is excluded on purpose, and the constraint that replaces it is
        grammatical rather than economic: every member but the last has to be
        a bare stem. That is a real property of compounds, not a heuristic,
        and it is what keeps प्रसिद्धा from being offered as प्र-सिद्धा.

        The junctions are the same ones split() uses, because a compound
        joins its members with sandhi like anything else — कल्याण + गुण + एक
        + धाम्ने is written कल्याणगुणैकधाम्ने, with गुण + एक fused to गुणै by
        वृद्धिः. A plain-concatenation-only splitter misses every compound
        that does that, which is most of the long ones."""
        s = expand_avagraha(strip_punct(token))
        if not s or not is_devanagari(s) or len(s) < self.VIGRAHA_MIN_TOKEN or len(s) > self.MAX_LEN:
            return None
        if not self.stems:
            return None
        got = self._search(s, force_split=True, stem_gate=True,
                           min_piece=self.VIGRAHA_MIN_MEMBER,
                           min_freq=self.VIGRAHA_MIN_FREQ,
                           max_pieces=self.VIGRAHA_MAX_MEMBERS)
        if not got:
            return None
        members = [w for w, _rule in got]
        # The last member carries the compound's inflection, so it has to be a
        # form the morphology actually recognises. अय is a lexicon entry and
        # not a plausible final member of anything.
        last = members[-1]
        if self.inflected and last not in self.inflected and not self.is_stem(last):
            return None
        return members

    def analyse(self, token):
        """{'token', 'pieces', 'seams'} — the token opened out as far as this
        library can, or None.

        Composed rather than special-cased: sandhi is undone first, then each
        resulting word is offered to the compound splitter, so a token that is
        both a sandhi join AND a compound comes out with both kinds of seam in
        the right places."""
        parts = self.confident_split(token)
        words = parts if parts else [(strip_punct(token), None)]
        pieces, seams = [], []
        # _search records with each word the junction that ENDS it, so the
        # rule describing a seam belongs to the piece before it, not after.
        prev_rule = None
        for word, rule in words:
            members = self.vigraha(word)
            chunk = members if members else [word]
            for m, member in enumerate(chunk):
                if pieces:
                    # Inside a vigraha result every seam is a compound seam by
                    # construction — the search would not have accepted the
                    # member otherwise. Only the seam BETWEEN two
                    # sandhi-separated words has to be classified, and only
                    # there does the lemma list's coverage matter. (प्राण is
                    # used 2,664 times in this corpus and appears in no
                    # subanta record as a lemma; asking "is प्राण a stem" of
                    # a member the compound search already validated is
                    # asking a question that has been answered.)
                    seams.append(self.SEAM_SAMASA if m
                                 else self.seam_between(pieces[-1], member, prev_rule))
                pieces.append(member)
            prev_rule = rule
        if len(pieces) < 2:
            return None
        return {'token': strip_punct(token), 'pieces': pieces, 'seams': seams}

    def confident_split(self, token):
        """The split, or None where the analysis is not one we would defend.

        Every piece has to be a word the corpus actually uses — not merely one
        the lexicon lists — because the failure mode that matters is a
        plausible-looking wrong cut. तस्मादित्युत्तरस्य parses as
        तस्मात् + इत् + युत् + तरस्य: four real lexicon entries, three of them
        nonsense in context, and no reader is served by seeing it."""
        got = self.split(token)
        if not got:
            return None
        if len(got) > self.CONFIDENT_MAX_PIECES:
            return None
        for word, _rule in got:
            bare = word.rstrip(VIRAMA)
            if len(bare) < self.CONFIDENT_MIN_PIECE_LEN and word not in self.SHORT_WORDS:
                return None
            if self.freq and self.freq.get(word, 0) < self.CONFIDENT_MIN_FREQ:
                return None
        return got
