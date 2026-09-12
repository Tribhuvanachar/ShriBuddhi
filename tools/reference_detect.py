#!/usr/bin/env python3
"""
reference_detect.py — find the places a commentary is CITING a scholarly
source, and only those.

THE RULE THIS REPLACES. Until 10 Sep 2026 a word was linked because it existed
in a database. That is not evidence of anything: one Sanskrit surface form can
be a noun, a verb form, a kṛdanta, half of a sandhi join and a dictionary
headword at once. तन्त्राणि is an ordinary noun that also sits in the dhātu
data; भावः likewise. Linking on presence made a claim about every one of them
that was usually false, and a wrong scholarly link misleads a reader in a way
a missing one never does.

THE RULE THAT REPLACES IT, in two stages that must both pass:

    is the commentator visibly CITING something here?
              ↓  (context: an artha beside its root, a कोश's name after इति,
              ↓   a sūtra's own words in quotation)
    does the thing cited exist in the authoritative list?
              ↓  (validation: dhātupāṭha, kośa registry, sūtrapāṭha)
            link

Never the second stage alone. A candidate that clears context but not
validation is dropped; a word that clears validation but has no citation
context around it is left as ordinary text, which is what it is.

WHAT EACH DETECTOR TREATS AS EVIDENCE

  धातु    A root standing next to ITS OWN traditional artha. The dhātupāṭha
          records both — ज्वल दीप्तौ, जि जये, दिश अतिसर्जने, भू सत्तायाम् —
          so "ज्वल दीप्ताविति" is a citation because दीप्ता… is the artha
          recorded for ज्वल and for nothing else nearby. That is a far
          stronger signal than इति alone, which ends ordinary sentences
          constantly. Grammatical terminology (लिट्, यङ्, णिच्) beside a root
          counts as a weaker second signal.

  कोश     A lexicon named in a citation frame: इति अमरः, इत्यामरः,
          अमरकोशे, इति धनञ्जयः. The name alone is never enough — अमर is an
          ordinary word meaning "deathless".

  सूत्र   The sūtra's own words, verbatim. Reuses the discipline
          build_sutra_prayoga_index.py already established and measured:
          Aho-Corasick over normalised text, word boundaries checked in the
          ORIGINAL, and a short sūtra needs a citation signal rather than bare
          presence (प्रत्ययः 3.1.1 otherwise "matches" every philosophical use
          of the word, 694 of them, all noise).

OVERLAP. A sūtra citation contains words; some of them are roots. The sūtra
wins and takes its whole span with it, so ज्वल दीप्ताविति is one dhātu
citation rather than three unrelated links.
"""

import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sanskrit_text import (normalize, normalize_with_map, is_protected,   # noqa: E402
                           fold, DEVA_LETTER)

try:
    import ahocorasick
except ImportError:                                          # pragma: no cover
    ahocorasick = None

# --- shared cues ------------------------------------------------------------
ITI = re.compile(r'^\s*(इति|इत्य)')
OPENQ = ('‘', '“', "'", '"', '॥')
CLOSEQ = ('’', '”', "'", '"', '।', '॥')
#: Grammatical terminology that marks a root citation: lakāras, kṛt and taddhita
#: pratyayas, the vikaraṇas. A root beside one of these is being discussed AS a
#: root, whatever else it might mean.
VYAKARANA_CUE = re.compile(
    r'(लट्|लिट्|लुट्|लृट्|लेट्|लोट्|लङ्|लिङ्|लुङ्|लृङ्'
    r'|यङ्|सन्|णिच्|क्विप्|क्त्वा|क्तवतु|तुमुन्|शतृ|शानच्|तव्य|अनीयर्'
    r'|ण्वुल्|तृच्|ल्युट्|घञ्|अच्|ठक्|धातु|धातोः|प्रत्यय|विकरण|गण)')
#: Words that say a lexicon is being quoted.
KOSHA_FRAME = re.compile(r'(इति|इत्य|उक्त|कोशे?|अभिधाने)')


def _clean_root(dhatu):
    """The bare written root, without the upadeśa's accent and it-markers.

    ज्वलँ is written ज्वल in a commentary; ग॒मॢँ is गम्. The markers are
    Pāṇini's bookkeeping, not part of the word anyone quotes."""
    out = dhatu or ''
    for mark in ('॒', '॑', 'ँ', 'ऽ', '॒', '॑'):
        out = out.replace(mark, '')
    return out.strip()


def _artha_stem(artha):
    """Enough of an artha to recognise it when sandhi has eaten its ending.

    दीप्तौ + इति is written दीप्ताविति — the औ is gone. Matching the artha
    minus its final vowel sign finds it anyway, and is still specific: दीप्त
    appears beside ज्वल and essentially nowhere else."""
    a = normalize((artha or '').split(',')[0].split('(')[0]).strip()
    a = re.sub(r'[ािीुूृेैोौ]$', '', a)
    return a


class DhatuDetector:
    """A root is linked when its own traditional artha stands beside it."""

    #: How far after the root to look for its artha. One or two words.
    ARTHA_WINDOW = 26
    #: A root shorter than this is not evidence of anything on its own — जि,
    #: भू and दा are also ordinary words and syllables inside longer ones.
    MIN_ROOT_LEN = 2
    #: Terminology alone is too weak a signal for a two-letter root.
    MIN_CUED_ROOT_LEN = 3

    def __init__(self, dhatus):
        self.by_root = {}
        for item in dhatus:
            root = _clean_root(item.get('dhatu'))
            if len(root) < self.MIN_ROOT_LEN:
                continue
            self.by_root.setdefault(root, []).append({
                'id': item.get('id'),
                'dhatu': item.get('dhatu'),
                'artha': item.get('artha') or '',
                'artha_norm': normalize((item.get('artha') or '').split(',')[0].split('(')[0]).strip(),
                'artha_stem': _artha_stem(item.get('artha')),
                'gana': item.get('gana'),
            })
        self.automaton = None
        if ahocorasick and self.by_root:
            a = ahocorasick.Automaton()
            for root in self.by_root:
                a.add_word(root, root)
            a.make_automaton()
            self.automaton = a

    def _candidates(self, text):
        if self.automaton:
            for end, root in self.automaton.iter(text):
                yield end - len(root) + 1, end + 1, root
        else:                                                # pragma: no cover
            for root in self.by_root:
                for m in re.finditer(re.escape(root), text):
                    yield m.start(), m.end(), root

    def detect(self, text):
        """[{type, start, end, surface, ref_id, reason, confidence}] over `text`."""
        out = []
        for start, end, root in self._candidates(text):
            # Word boundaries in the source: a root is not a root because it
            # happens to sit inside a longer word.
            if start > 0 and DEVA_LETTER.match(text[start - 1]):
                continue
            if end < len(text) and DEVA_LETTER.match(text[end]):
                continue
            if is_protected(text, start, end):
                continue
            window = text[end:end + self.ARTHA_WINDOW]
            nwindow = normalize(window)
            best = None
            for entry in self.by_root[root]:
                # The artha exactly as recorded first: जि's artha is जये and
                # the text writes जये, so there is nothing to approximate.
                # Only where sandhi has eaten its ending (दीप्तौ + इति →
                # दीप्ताविति) does the stem stand in, and a stem that short is
                # not specific enough to be evidence on its own.
                full = entry['artha_norm']
                stem = entry['artha_stem']
                if full and full in nwindow:
                    best = (entry, 'high', 'root beside its own artha (%s)' % entry['artha'])
                    break
                if stem and len(stem) >= 3 and stem in nwindow:
                    best = (entry, 'high', 'root beside its own artha (%s)' % entry['artha'])
                    break
            if best is None and len(root) >= self.MIN_CUED_ROOT_LEN and VYAKARANA_CUE.search(window):
                # A root next to grammatical terminology is being discussed as
                # a root — weaker than its own artha, still a citation frame.
                # Not for a two-letter root: तु is a root AND the commonest
                # particle in the language, and it turned up inside an
                # Amarakośa quotation on the strength of a nearby क्रिया.
                entry = self.by_root[root][0]
                best = (entry, 'medium', 'root beside grammatical terminology')
            if best is None:
                continue
            entry, confidence, reason = best
            out.append({
                'type': 'dhatu',
                'start': start,
                'end': end,
                'surface': text[start:end],
                'ref_id': entry['id'],
                'label': '%s · %s' % (entry['dhatu'], entry['artha']),
                'confidence': confidence,
                'reason': reason,
            })
        return out


class KoshaDetector:
    """A lexicon is linked when it is NAMED in a citation frame."""

    FRAME_BEFORE = 14
    FRAME_AFTER = 10

    def __init__(self, registry):
        #: {written name: kosha slug}. Configurable rather than hard-coded, so
        #: adding a lexicon is a data change.
        self.registry = registry
        self.names = sorted(registry, key=len, reverse=True)
        self.pattern = re.compile('|'.join(re.escape(n) for n in self.names)) if self.names else None

    def detect(self, text):
        if not self.pattern:
            return []
        out = []
        for m in self.pattern.finditer(text):
            start, end = m.start(), m.end()
            if start > 0 and DEVA_LETTER.match(text[start - 1]):
                # अमर inside अमरकोशे is handled by the longer name winning;
                # inside an unrelated word it is not a citation.
                continue
            before = text[max(0, start - self.FRAME_BEFORE):start]
            after = text[end:end + self.FRAME_AFTER]
            named = m.group(0)
            # A danda or an इत्यर्थः between the frame word and the name means
            # the frame closed the sentence BEFORE and has nothing to do with
            # this word: "…इत्यर्थः । विश्वं सकलम्" is not a citation of
            # Viśvakośa, it is the ordinary word viśva starting a new clause.
            if '।' in before or '॥' in before or is_protected(text, max(0, start - self.FRAME_BEFORE), start):
                before = ''
            # A name that already says "kośa" carries its own frame; a bare
            # name needs इति or उक्त around it. अमर on its own means
            # "deathless" and is not a citation of anything.
            # A name written with इति already fused onto it carries its own
            # frame: इत्यामरः IS "इति + अमरः", the citation and the name in
            # one word, which is how print usually has it.
            self_framing = ('कोश' in named or 'अभिधान' in named
                            or named.startswith('इति') or named.startswith('इत्य'))
            if not self_framing and not (KOSHA_FRAME.search(before) or KOSHA_FRAME.search(after)):
                continue
            out.append({
                'type': 'kosha',
                'start': start,
                'end': end,
                'surface': named,
                'ref_id': self.registry[named],
                'label': self.registry[named],
                'confidence': 'high' if self_framing else 'medium',
                'reason': 'lexicon named in a citation frame',
            })
        return out


class SutraDetector:
    """A sūtra is linked when its own words appear, and identify it uniquely.

    Two tiers, both validated against the sūtrapāṭha and neither fuzzy:

      whole      the sūtra's complete text, verbatim. Guards inherited from
                 build_sutra_prayoga_index.py, which were tuned against a first
                 build that was inspected rather than trusted: word boundaries
                 checked in the ORIGINAL text, and a short sūtra needs a
                 citation signal rather than bare presence (प्रत्ययः 3.1.1
                 otherwise "matches" every philosophical use of the word, 694
                 of them, all noise).

      fragment   a distinctive piece of it. Commentaries rarely quote a whole
                 sūtra: they quote the opening and close with इत्यादिना
                 (प्रियस्थिरेत्यादिना for 6.4.157), or quote across an
                 omission (धातोरेकाचः क्रियासमभिहारे यङ् for 3.1.22
                 धातोरेकाचो हलादेः क्रियासमभिहारे यङ्). Every contiguous run
                 of words in every sūtra is indexed, and kept ONLY where it
                 belongs to one sūtra alone. Ambiguity is designed out rather
                 than scored: संज्ञायाम् opens three sūtras and is 2.1.43
                 entire, so it identifies nothing and is not in the index.
    """

    MIN_QUOTE_NORM = 8
    FREESTANDING_NORM = 14
    CUE = re.compile(r'(अष्टाध्यायी|पाणिन|पा\s*[.।॰०]\s*सू|सूत्र|व्याकरणसूत्र)')
    FRAGMENT_MIN = 12
    #: Below this a fragment needs a citation signal, as a short sūtra does.
    #: A 16-character folded run that belongs to ONE sūtra out of 3,962 is
    #: already a specific claim — uniqueness is doing most of the work here,
    #: which is why this sits lower than the whole-sūtra threshold.
    FRAGMENT_FREESTANDING = 16
    #: इति as a commentary writes it: standing alone, or fused onto the word
    #: before it (शानचौ + इति → शानचाविति).
    ITI_TAIL = re.compile(r'^\s*(?:इति|इत्य)|^[ािीेैोौवय]{0,2}(?:ति|त्य)')

    def __init__(self, sutras):
        self.by_id = {}
        self.norm_len = {}
        self.multiword = {}
        entries = []
        owners = {}
        for item in sutras:
            sid = item.get('id')
            raw = item.get('sanskrit_text') or ''
            if not sid or not raw:
                continue
            self.by_id[sid] = item
            n = normalize(raw)
            self.norm_len[sid] = len(n)
            self.multiword[sid] = ' ' in raw.strip()
            if len(n) >= self.MIN_QUOTE_NORM:
                entries.append((n, sid))
            words = [w for w in raw.split() if w]
            for i in range(len(words)):
                for j in range(i + 1, len(words) + 1):
                    frag = fold(' '.join(words[i:j]))
                    if len(frag) < self.FRAGMENT_MIN:
                        continue
                    owners.setdefault(frag, set()).add(sid)
                    if len(frag) > 70:
                        break
        self.fragments = {f: next(iter(ids)) for f, ids in owners.items() if len(ids) == 1}

        self.automaton = None
        self.frag_automaton = None
        if ahocorasick and entries:
            a = ahocorasick.Automaton()
            for n, sid in entries:
                if a.exists(n):
                    a.get(n).append(sid)
                else:
                    a.add_word(n, [sid])
            a.make_automaton()
            self.automaton = a
        if ahocorasick and self.fragments:
            fa = ahocorasick.Automaton()
            for frag, sid in self.fragments.items():
                fa.add_word(frag, (frag, sid))
            fa.make_automaton()
            self.frag_automaton = fa

    def detect(self, text):
        ntext, omap = normalize_with_map(text)
        if not ntext:
            return []
        out, seen = [], set()
        if self.automaton:
            for end, ids in self.automaton.iter(ntext):
                for sid in ids:
                    if sid in seen:
                        continue
                    nlen = self.norm_len[sid]
                    n0 = max(0, end - (nlen - 1))
                    o0 = omap[n0]
                    o1 = omap[min(len(omap) - 1, end)]
                    if o0 > 0 and DEVA_LETTER.match(text[o0 - 1]):
                        continue
                    if o1 + 1 < len(text) and DEVA_LETTER.match(text[o1 + 1]):
                        continue
                    if nlen < self.FREESTANDING_NORM:
                        after = text[o1 + 1:o1 + 12]
                        before = text[max(0, o0 - 3):o0]
                        around = text[max(0, o0 - 50):min(len(text), o1 + 30)]
                        # The quote has to CLOSE just after the sūtra, or the
                        # sūtra is only a word inside somebody else's
                        # quotation: ‘स्त्रियां मूर्तिस्तनुस्तनूः’ इत्यमरः is
                        # Amara being quoted, and 4.1.3 स्त्रियाम् happens to
                        # be its first word.
                        closing = text[o1 + 1:o1 + 4]
                        quoted = (any(q in before for q in OPENQ)
                                  and any(q in closing for q in CLOSEQ))
                        cued = self.CUE.search(around)
                        # A following इति counts only for a MULTI-word sūtra:
                        # a single ordinary word closes statements with इति all
                        # the time (मम प्रयोजनम् इति भावः is not a citation of
                        # 5.1.108, and 39 such non-citations turned up in the
                        # first build of the prayoga index).
                        if not (quoted or cued or (self.multiword[sid] and ITI.match(after))):
                            continue
                    if is_protected(text, o0, o1 + 1):
                        continue
                    seen.add(sid)
                    out.append(self._ref(text, o0, o1 + 1, sid, 'high',
                                         'sutra text quoted verbatim'))
        out += self._fragments(text, ntext, omap, seen)
        return out

    def _fragments(self, text, ntext, omap, seen):
        if not self.frag_automaton:
            return []
        ftext = fold(text)
        if len(ftext) != len(ntext):
            # fold() is 1:1 with normalize() by construction; if that ever
            # stops being true, refuse rather than misplace every span.
            return []
        out = []
        for end, (frag, sid) in self.frag_automaton.iter(ftext):
            if sid in seen:
                continue
            n0 = max(0, end - len(frag) + 1)
            o0 = omap[n0]
            o1 = omap[min(len(omap) - 1, end)]
            if o0 > 0 and DEVA_LETTER.match(text[o0 - 1]):
                continue
            if len(frag) < self.FRAGMENT_FREESTANDING:
                after = text[o1 + 1:o1 + 14]
                around = text[max(0, o0 - 50):min(len(text), o1 + 30)]
                quoted = any(q in text[max(0, o0 - 3):o0] for q in OPENQ)
                if not (quoted or self.CUE.search(around) or self.ITI_TAIL.match(after)):
                    continue
            if is_protected(text, o0, o1 + 1):
                continue
            seen.add(sid)
            out.append(self._ref(text, o0, o1 + 1, sid, 'medium',
                                 'a phrase belonging to this sutra and no other'))
        return out

    def _ref(self, text, start, end, sid, confidence, reason):
        return {
            'type': 'sutra',
            'start': start,
            'end': end,
            'surface': text[start:end],
            'ref_id': sid,
            'label': '%s · %s' % (sid, self.by_id[sid].get('sanskrit_text', '')),
            'confidence': confidence,
            'reason': reason,
        }


#: Which reference wins when two claim the same characters. A sūtra citation
#: contains words and some of them are roots; the sūtra is what the
#: commentator is doing.
PRIORITY = {'sutra': 3, 'kosha': 2, 'dhatu': 1}


def resolve_overlaps(references):
    """One reference per stretch of text.

    Longest span first, then priority: a recognised citation consumes its own
    characters so nothing inside it is linked separately. ज्वल दीप्ताविति is
    one dhātu citation, not three unrelated links."""
    ordered = sorted(references,
                     key=lambda r: (-(r['end'] - r['start']), -PRIORITY.get(r['type'], 0),
                                    r['start']))
    kept = []
    for ref in ordered:
        if any(ref['start'] < k['end'] and k['start'] < ref['end'] for k in kept):
            continue
        kept.append(ref)
    return sorted(kept, key=lambda r: r['start'])


def detect_all(text, dhatu=None, kosha=None, sutra=None):
    """Every reference in one passage, overlaps resolved."""
    refs = []
    if sutra:
        refs += sutra.detect(text)
    if kosha:
        refs += kosha.detect(text)
    if dhatu:
        refs += dhatu.detect(text)
    return resolve_overlaps(refs)
