#!/usr/bin/env python3
"""Build the Krama/Kramahetu rule-logic layer from the ingested sutra text.

This is the interpretation step that dge/RV_PRATISHAKHYA_KRAMA_ARCHITECTURE.md
sec.6.1/sec.10 flagged as still needed after the raw sutra text (sec.4b) and
the VedaVishtaram cross-check (sec.4c) were done. It is fundamentally
different in kind from those two: sec.4b/4c are citations (what the source
says), this file is INTERPRETATION (what the source means, as a rule a
generator could execute) -- grounded in Uvata's Bhasya wherever possible,
but ultimately this session's own reading of Sanskrit grammatical prose, not
independently attested. Every entry's "basis" field says what it rests on;
none of this has been validated against an actual attested Krama-patha text
(dge/RV_PRATISHAKHYA_KRAMA_ARCHITECTURE.md sec.7's VALIDATE mode / sec.10's
open question about a ground-truth source) -- that validation is still the
next real step before trusting this to generate anything.

Scope, stated honestly rather than silently: patala 10 (Krama, all 22
sutras) is fully worked out, since it is the direct algorithmic core. Of
patala 11's 71 sutras (Kramahetu -- literally "reasons for Krama"), 14 that
give operative content directly extending patala 10 (the catuhkrama sutra
11.19; the default-case sutras 11.22-23; the parigraha phonetic-reversion
block 11.36-46; the sthitopasthita confirmation 11.61) are worked out in the
same depth. The remaining 57 patala-11 sutras are classified (domain,
rule_type, a one-line summary) but NOT reduced to conditions/action/
exceptions in this pass -- most of that material is genuinely rationale,
historical lineage (11.65 names Prabahravya as the first teacher of Krama),
or debate among named grammarians about WHY patala 10's rules are as they
are, not additional operative content a generator would execute. Extending
this file to cover them is real future work, not something this pass
skipped by accident -- each stub says why.

Run: python3 tools/pratishakhya/build_krama_rules.py
Writes: dge/data/vedanga/shiksha/pratishakhya/rigveda_pratishakhya/krama_kramahetu_rules.json
"""
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SUTRA_DATA_PATH = (
    REPO_ROOT / "dge/data/vedanga/shiksha/pratishakhya/rigveda_pratishakhya/data.json"
)
OUT_PATH = (
    REPO_ROOT
    / "dge/data/vedanga/shiksha/pratishakhya/rigveda_pratishakhya/krama_kramahetu_rules.json"
)

UVATA = "Uvata's Bhasya (via VedaVishtaram, vedavishtaram.in), cross-checked against the sutra text itself"

# ---------------------------------------------------------------------------
# Patala 10 -- Krama-Patala. All 22 sutras, fully worked out.
# ---------------------------------------------------------------------------
PATALA_10 = [
    dict(sutra=1, domain="adhikara", rule_type="adhikara",
         summary="Heading: everything until stated otherwise falls under the topic 'Krama'.",
         conditions=[], action=[], exceptions=[],
         examples=[], confidence="high", basis=UVATA),

    dict(sutra=2, domain="structural_pairing", rule_type="operative",
         summary="The base Krama algorithm: for a run of pada-patha words within one ardharca, form consecutive overlapping pairs (W1,W2),(W2,W3),... by 'taking back' the second word of each pair to start the next.",
         conditions=["A sequence of pada-patha words W_1..W_n within a single ardharca"],
         action=[
             "For i = 1 to n-1: emit the Krama pair (W_i, W_i+1)",
             "The second word of each pair (W_i+1) is 'taken back' (pratyadaya) to become the first word of the next pair",
             "Continue until the ardharca is complete (10.18 prohibits continuing across an ardharca boundary)",
         ],
         exceptions=["10.3-10.4's avasana exceptions stop the chain early for certain monosyllables/pluta words",
                     "10.6 onward: sandhi within a pair follows 10.6's default-plus-Parigraha-exceptions rule, not raw concatenation"],
         examples=["RV 1.1.1 ardharca 1, pada sequence parjanyaya/pra/gayata/divah/putraya/miilhuse -> pairs parjanyaaya-pra | pra-gaayata | gaayata-divah | divah-putraaya | putraaya-miilhuse (per Uvata's own worked example on this sutra)"],
         confidence="high", basis=UVATA),

    dict(sutra=3, domain="avasana_exception", rule_type="operative",
         summary="Certain monosyllabic/enclitic pratika words (e.g. the interjections a, oom) stop the Krama chain early (avasyanti) rather than continuing to pair forward, EXCEPT the vowel 'o'.",
         conditions=["Current word is a single akshara (monosyllable)",
                     "That syllable is not the vowel 'o'",
                     "[LOW CONFIDENCE -- see caveat] further conditions involving 'su'/'sma' before a following 'nah', word-external separation (vyavayi), and elided/pluta-final forms, per the sutra's own compressed enumeration"],
         action=["Stop the pairing chain at this word rather than combining it forward with the next word",
                 "The word after it starts a fresh pair instead of continuing the chain"],
         exceptions=["10.4 extends this same stopping behaviour to pluta-initial words"],
         examples=["aa mandram | mandram-aa vareNyam (the interjection 'aa' stops rather than pairing onward past 'mandram')",
                   "ut-u tyam | oom ity oom | tyam jaatavedasam (oom stops similarly)"],
         confidence="low",
         basis=UVATA + "; this sutra carries one of only two genuinely unresolved OCR/edition-variant gaps in patala 10-11 (see RV_PRATISHAKHYA_KRAMA_ARCHITECTURE.md sec.4c) and its own compressed enumeration ('ekavarnam anokaram nate su sma iti nahpare, padena ca vyavetam...') was not fully parsed word-by-word here -- treat the action above as the confirmed core (monosyllable-stops-chain) and the bracketed conditions as needing a specialist's confirmation before being trusted for generation.",
         caveat="Do not encode this predicate into a generator without a specialist re-reading the full compressed sutra text against Uvata's gloss line by line."),

    dict(sutra=4, domain="avasana_exception", rule_type="operative",
         summary="Pluta (protracted) words and the like also stop the Krama chain early, same as 10.3's monosyllables.",
         conditions=["Current word is pluta (vowel-protracted) or of the 'et cetera' (prabhrti) class 10.3 gestures at"],
         action=["Stop the pairing chain at this word, same as 10.3"],
         exceptions=[],
         examples=["shunashcicChepam niditam | naraa vaa shamsam puuShaNam (a pluta-adjacent stop point per Uvata's example)"],
         confidence="medium",
         basis=UVATA + "; Uvata's own commentary on this sutra is largely about WHY it's needed as a separate statement from 10.3 (to prevent over-generalizing 10.7's parigraha net to avasana words), which is meta-justification, not new conditions -- the operative content is the one-line extension stated above.",
         ),

    dict(sutra=5, domain="phonetic_reversion", rule_type="operative",
         summary="At the point where a word is 'taken back' to start the next pair (pratyadana) or where a chain stops (avasana), do not pronounce the sandhi-combined form that word would have with its neighbour -- use its unmodified pada form.",
         conditions=["Word W is at a pratyadana point (about to be reused as the first word of the next pair)",
                     "OR word W is at an avasana point (the chain stops here, per 10.3-10.4)"],
         action=["Render W in its own pre-sandhi pada-patha form, not the samhita-sandhi form it would take with the adjacent word"],
         exceptions=[],
         examples=["ghaneva vajrin (continuous samhita form) -> at the pratyadana/avasana point, revert to ghanaa iva (unsandhied)",
                   "yacChakvariiShu bRhataa -> mo Shu Nah stays as its pada form, not the samhita-combined shape"],
         confidence="high", basis=UVATA),

    dict(sutra=6, domain="default_sandhi", rule_type="operative",
         summary="DEFAULT rule: within a Krama pair, apply the same sandhi as in continuous Samhita recitation -- EXCEPT for avagrhya (split-compound) words, iti-marked words, the dhakshi/dhukshi examples in their vikrta (altered) form, and pluta words, which fall under Parigraha (10.7 onward) instead.",
         conditions=["A Krama pair (W_i, W_i+1), not otherwise covered by an avasana/pratyadana exception (10.3-10.5)"],
         action=["Apply ordinary Samhita-patha sandhi between the two words",
                 "UNLESS the pair involves an avagrhya (compound-split) word, an iti-marked word, a dhakshi/dhukshi-type word in vikrta form, or a pluta word -- route those to the Parigraha mechanism (10.7-10.22) instead"],
         exceptions=["avagrhya compounds", "iti-marked words", "dhakshi/dhukshi vikrta forms", "pluta words"],
         examples=["vaajeShu saasahiH | saasahir bhavaH (ordinary default sandhi, no Parigraha needed)"],
         confidence="high", basis=UVATA),

    dict(sutra=7, domain="parigraha_scope", rule_type="definitional",
         summary="Defines part of Parigraha's SCOPE: words whose phonetic modification is internal to the word itself (not caused by an adjacent word) -- i.e. avagrhya compound-splits, iti-marked words, and the dhakshi/dhukshi vikrta forms -- require Parigraha (special retained treatment), not the plain default sandhi of 10.6.",
         conditions=["A word's modification (vikara) is antahpada (internal, e.g. from being written as a split compound in the pada-patha) and not caused by (ananyakarita) an adjacent word"],
         action=["Route the word to Parigraha (isPragrhya-in-Parigraha / requiresParigraha predicate should return true)"],
         exceptions=[],
         examples=["puraH-hitam (an avagrhya compound split) -> parigraha applies",
                   "indraagnii iti indraagnii (iti-marked word repeated)",
                   "dhakShi/dhukShi in their vikrta ('nu-dakShi', 'dukShan') forms, contrasted with 'niichaa tam. tam dhakShi.' where the plain (non-vikrta) form does NOT trigger this"],
         confidence="high", basis=UVATA,
         caveat="This is the sutra that DIRECTLY replaces the naive 'Parigraha = word + iti + iti + word' formula the original Gemini-derived review correctly flagged as wrong: Parigraha's scope is defined here plus 10.8-10.9, and its actual rendering mechanism is defined separately in 10.12-10.14 (sthita/upasthita/sthitopasthita)."),

    dict(sutra=8, domain="parigraha_scope", rule_type="definitional",
         summary="Extends Parigraha's scope: a word situated in the middle of a longer multi-word combined phrase (bahumadhyagata) also requires Parigraha, not just simple two-word compounds.",
         conditions=["Word sits in the middle of a group of more than two combined words (bahumadhyagata)"],
         action=["Route the word to Parigraha"],
         exceptions=[],
         examples=["iiyate naraa ca shamsam daivyam -> naraashamsam requires parigraha as the middle element",
                   "shunashcicChepam niditam -> shunaHshepam", "naraa vaa shamsam puuShaNam -> naraashamsam"],
         confidence="high", basis=UVATA),

    dict(sutra=9, domain="parigraha_scope", rule_type="definitional",
         summary="Extends Parigraha's scope again: a word at the very end of an ardharca also requires Parigraha, even without being a compound or bahumadhyagata word -- because it has nothing to pair forward with inside the ardharca (10.18 forbids crossing the boundary), its correct form is instead confirmed via Parigraha's sthita/upasthita mechanism.",
         conditions=["Word is the last word of an ardharca (ardharcantya)"],
         action=["Route the word to Parigraha"],
         exceptions=[],
         examples=["putraaya miiLhuShe (the closing words of RV 1.1.1's first ardharca)"],
         confidence="high", basis=UVATA),

    dict(sutra=10, domain="phonetic_reversion", rule_type="operative",
         summary="A non-nasalized 'aa' vowel-ending immediately preceding an ardharca-final Parigraha word should NOT be taken in its sandhi-combined form.",
         conditions=["Word ends in a plain (non-nasalized) 'aa' produced by sandhi",
                     "That word immediately precedes an ardharca-final Parigraha word (10.9)"],
         action=["Do not use the sandhi-combined 'aa' form at this position -- see 10.11 for the repair"],
         exceptions=["Does not apply if the word does not immediately precede the ardharca-final word (tested by Uvata's 'tanuuShaa' counter-example)",
                     "Does not apply to a nasalized aa-m̐ (tested by Uvata's 'gambhiira aam̐ ugraputre' counter-example)"],
         examples=["mandram-aa vareNyam (the combined 'mandramaa' is NOT used here)"],
         confidence="high", basis=UVATA),

    dict(sutra=11, domain="phonetic_reversion", rule_type="operative",
         summary="Repair procedure for 10.10: take the word back to its unmodified form, then pronounce it again together with the following word.",
         conditions=["10.10's condition applies (a non-nasalized sandhi-aa before an ardharca-final Parigraha word)"],
         action=["Take the word back to its original (pratyadaya) unmodified form",
                 "Pronounce it again combined with the word that follows"],
         exceptions=[],
         examples=["mandram-aa vareNyam -> revert to mandram, then re-pair as 'aa vareNyam'"],
         confidence="high", basis=UVATA),

    dict(sutra=12, domain="sthita_upasthita_definition", rule_type="definitional",
         summary="Defines the technical term 'upasthita': a word given together with the particle 'iti'.",
         conditions=[], action=["Term definition: upasthita = word + iti"], exceptions=[],
         examples=["baahuu iti"], confidence="high", basis=UVATA),

    dict(sutra=13, domain="sthita_upasthita_definition", rule_type="definitional",
         summary="Defines the technical term 'sthita': the bare word alone, without 'iti'.",
         conditions=[], action=["Term definition: sthita = bare word, no iti"], exceptions=[],
         examples=["agnim"], confidence="high", basis=UVATA),

    dict(sutra=14, domain="sthita_upasthita_definition", rule_type="definitional",
         summary="Defines the technical term 'sthitopasthita': where BOTH the sthita and upasthita forms are uttered together (word, then word+iti, then word again) -- this is the actual mechanism behind 'Parigraha', not a universal word+iti formula.",
         conditions=[], action=["Term definition: sthitopasthita = sthita + upasthita given together (W ... W iti W pattern)"],
         exceptions=[],
         examples=["vibhaavaso iti vibhaavaso"], confidence="high", basis=UVATA,
         caveat="This is the single most important definitional sutra for correcting the naive 'Parigraha = word + iti + iti + word' formula: sthitopasthita is a NAMED, SCOPED category (triggered by 10.7-10.9's conditions), not applied to every word."),

    dict(sutra=15, domain="disambiguation", rule_type="optional",
         summary="When the first word of a to-be-Parigraha-treated pair has a phonetically ambiguous word-final sound, an indicator/demonstrator (the sthitopasthita repetition) may be used to disambiguate which word is meant -- but Uvata explicitly notes this is OPTIONAL ('iShTam', preferred/desired), not obligatory.",
         conditions=["The first word's final sound, once sandhi-merged, would be ambiguous among 2+ distinct underlying words (e.g. tat/tam/taam all reducing similarly)"],
         action=["Optionally use the sthitopasthita demonstration to disambiguate: give the specific word + iti + the same word"],
         exceptions=["Not obligatory -- Uvata: 'iShTavacanaad eva asya aanityatvam gamyate' (its non-obligatory nature follows from the word 'iShTam')"],
         examples=["tan naH -> tat iti tat | tam naH -> tam iti tam | taam tvaam -> taam iti taam"],
         confidence="high", basis=UVATA),

    dict(sutra=16, domain="samasa_handling", rule_type="operative",
         summary="When a compound (samasa) word undergoes Parigraha's second (repeated) utterance, it should be split at the avagraha rather than pronounced as one fused unit.",
         conditions=["A compound word is being given in the second (repeated/pauses-marked) utterance within Parigraha"],
         action=["Render the repeated utterance with the avagraha split shown, not as a fused compound"],
         exceptions=[],
         examples=["purojitii vaH -> the repeat is given as purojitii iti puraH-jitii (avagraha-split), not purojitii again"],
         confidence="high", basis=UVATA),

    dict(sutra=17, domain="phonetic_detail", rule_type="operative",
         summary="A word ending in visarga (here exemplified by 'svaH') that follows an iti-marked word in Parigraha should be pronounced with a slight extra prolongation, as if with an avagraha, rather than either fully fused or fully disjoined.",
         conditions=["A visarga-final word directly follows an iti-marked (upasthita) word within Parigraha (as taught by earlier teachers, per Uvata)"],
         action=["Pronounce with an avagraha-like extra mora of duration"],
         exceptions=[],
         examples=["sva(á)r iti svaH (the extra mora before the visarga)"],
         confidence="medium", basis=UVATA),

    dict(sutra=18, domain="ardharca_boundary", rule_type="operative",
         summary="Sandhi does not occur across an ardharca (half-verse) boundary -- the single most load-bearing structural constraint on the whole Krama algorithm.",
         conditions=["Two words fall on opposite sides of an ardharca boundary"],
         action=["Do not apply sandhi between them -- 10.2's pairing chain does not cross this boundary either (it restarts fresh in the next ardharca)"],
         exceptions=[], examples=[], confidence="high", basis=UVATA),

    dict(sutra=19, domain="samaya_pause", rule_type="operative",
         summary="At recognized ('drshtakrama', established-by-precedent) 'samaya'-marked junction points, Krama pairing still applies throughout, but the exact pause/continuation point may fall one word or two words before the samaya point depending on the specific case.",
         conditions=["A 'samaya' (established special junction) point occurs in the pada sequence"],
         action=["Apply Krama pairing across the samaya point (per 10.2's general algorithm)",
                 "Choose to pause (avasyet) one word or two words before the samaya point, per the specific attested case -- not a single fixed distance"],
         exceptions=["Does not extend by mere similarity of reasoning (hetu-samanya) to unattested cases -- Uvata explicitly rejects generalizing this to verses like 'agner vayam prathamasya amRtaanaam' for lack of an established 'samaya' designation there"],
         examples=["pra pra vaH | vas triShTubham iSham mandadviiraaya indave | yoniShTa indra sadane akaari | akaari tam aa nRbhiH puruhuutaH"],
         confidence="medium", basis=UVATA),

    dict(sutra=20, domain="pragrhya_in_parigraha", rule_type="operative",
         summary="Several specific phonetic phenomena -- n-as-ushman treatment, nati (retroflexion) in a pluta/upacarita context, and praslesha (close junction) of a Pragrhya word -- revert to their natural/unmodified (prakrti) form specifically when Parigraha is being performed. This is the direct answer to 'how does Pragrhya behave inside Parigraha'.",
         conditions=["Parigraha is being performed on a word exhibiting nakara-ushma-vat treatment, or a nati under pluta/upacarita conditions, or praslesha of a Pragrhya word"],
         action=["Render the phenomenon in its natural/base (prakrti) form rather than its normal-context sandhi-modified form"],
         exceptions=[], examples=[], confidence="high", basis=UVATA,
         caveat="Directly implements what the original review demanded: 'Do not implement Parigraha as a universal word+iti operation... derive Pragrhya-in-Parigraha behaviour from the actual rules.'"),

    dict(sutra=21, domain="shuddhakshara_agama", rule_type="operative",
         summary="The shuddhakshara-agama (a pure-vowel augment inserted in normal continuous recitation) is removed/absent when Parigraha is performed.",
         conditions=["A word normally carries a shuddhakshara-agama insertion in continuous Samhita recitation", "Parigraha is being performed on/around that word"],
         action=["Omit the shuddhakshara-agama in the Parigraha rendering"],
         exceptions=[], examples=["su-chandra dasma -> suchandra iti su-chandra (no extra augment in the repeat)", "pariShkRNvann-aniShkRtam -> parikRNvan iti pari-kRNvan"],
         confidence="high", basis=UVATA + " (11.43 gives the worked examples for this same rule)"),

    dict(sutra=22, domain="rephita", rule_type="operative",
         summary="Three specific phonetic categories follow the NORMAL (non-Parigraha-reverted) rule instead: (1) rephita words (whose repha would otherwise become visarga) retain the repha-derived form specifically before an UNVOICED sibilant/ushman; (2) a 'duu-bhava' lengthening (duH- -> duu-) applies to a specific word class; (3) words like 'svadhitiH iva' likewise keep the normal form.",
         conditions=["Category 1: a rephita word is followed by an unvoiced ushman (sh/SH/s)",
                     "Category 2: a word beginning 'duH-' belongs to the specific dU-bhava class",
                     "Category 3: the word is 'svadhitiH' followed by 'iva'"],
         action=["Category 1: retain the repha-derived consonant form (do not revert to Parigraha's usual un-sandhied form)",
                 "Category 2: lengthen duH- to duu- (e.g. duHnasham -> duuNaasham)",
                 "Category 3: keep the normal continuous-recitation form"],
         exceptions=["Explicitly does NOT apply before a VOICED sound -- Uvata's counter-example 'svarjitam mahi' stays svarjitam, not reverted"],
         examples=["svashcakShaaH rathiraH -> svashcakShaaH (rephita+unvoiced sibilant, normal form kept)",
                   "duHnasham sakhyam -> duuNaasham (dU-bhava)",
                   "janasya duurdhyaH -> duuDhyaH", "duurLabho rathaH -> duuLabhaH",
                   "svadhitiiva riiyate -> svadhitiH iva (kept as in continuous recitation)"],
         confidence="high", basis=UVATA + "; also directly confirms 11.40's dU-bhava examples (duuNaasha/duuDhya/duuLabha) verbatim."),
]

# ---------------------------------------------------------------------------
# Patala 11 -- Kramahetu-Patala. Worked out in full for the 14 sutras that
# extend patala 10 operationally; the rest are classified only (see the
# STUB_SUMMARIES table and the module docstring for why).
# ---------------------------------------------------------------------------
PATALA_11_DETAILED = [
    dict(sutra=19, domain="catuhkrama", rule_type="operative",
         summary="The explicit Sakala-specific practice: in certain triple-junction (trisangama) cases, the Sakalas perform a FOUR-FOLD repetition (catuhkrama) rather than the two or three-fold repetition otherwise discussed in 11.1-11.18's build-up.",
         conditions=["A trisangama (triple-junction) case as built up through 11.1-11.18's progressively justified dvikrama/trikrama reasoning"],
         action=["Perform catuhkrama: four repetitions/passes over the relevant word-junction, per Sakala practice, superseding the alternative (paksantara) view mentioned by 'tu'"],
         exceptions=[],
         examples=["udu Shu NaH (Uvata's cited example)"],
         confidence="high", basis=UVATA,
         caveat="This is THE sutra the original Gemini-derived review specifically flagged as essential and missing from the naive prompt. 11.1-11.18 is its full justificatory build-up (not separately detailed in this pass -- see the stub table) and should be read before implementing this rule, since 'trisangama' is defined progressively across those sutras."),

    dict(sutra=22, domain="default_case", rule_type="operative",
         summary="'Ayavana' (non-mixing/unambiguous) case: when the preceding word of a krama pair is NOT itself the cause (nimitta) of the phonetic change under discussion, the simple two-word (dvabhyam) Krama procedure applies -- i.e. no extra repetition is needed.",
         conditions=["The preceding word in a Krama pair is not the causal trigger for the phonetic phenomenon in question"],
         action=["Apply plain two-word Krama pairing (10.2's base algorithm), no extra repetition"],
         exceptions=["Where there IS such mixing/ambiguity (yaavana), a fuller (bahu-) krama repetition applies instead -- see 11.24 onward"],
         examples=["agnim iiLe | iiLe purohitam (RV 1.1.1's own opening pair, cited by Uvata as the plain unambiguous case)", "mo Shu NaH"],
         confidence="high", basis=UVATA),

    dict(sutra=23, domain="default_sandhi", rule_type="operative",
         summary="Apply sandhi word-by-word as normal in cases where the causing factor (hetu) for a special phonetic change is absent (apetahetu) -- e.g. once the specific triggering word is no longer adjacent, the plain (non-triggered) sandhi form is used.",
         conditions=["The specific word that causes a conditioned sandhi change (e.g. ratva/retroflexion after 'pra') is not present/adjacent in this pairing"],
         action=["Apply the plain, unconditioned sandhi form"],
         exceptions=[],
         examples=["pra NaH (pra causes N-retroflexion of naH) vs. na indro (without pra adjacent, plain 'na' form, no retroflexion) -- Uvata notes this clause exists specifically to remove any doubt (viloपa-sanshaya) about whether the retroflexion might persist by elision"],
         confidence="high", basis=UVATA),

    dict(sutra=36, domain="pragrhya_in_parigraha", rule_type="operative",
         summary="During Parigraha, revert nakara-lopa (n-elision), ushma-bhava (n-as-sibilant), and ra-bhava (n-as-r) treatments of a final 'n' to their natural (un-elided/un-modified) form, purely to display the word's true underlying form.",
         conditions=["Parigraha is being performed on a word whose final 'n' would otherwise show lopa/ushma/ra treatment in continuous recitation"],
         action=["Render the final 'n' in its natural, unelided/unmodified form"],
         exceptions=[],
         examples=["asmaam̐ asmaam̐ it -> asmaan asmaan iti asmaan (lopa reverted)",
                   "svatavaam̐ paayu -> svatavaan iti svatavaan (ushma reverted)",
                   "abhiishuum̐r iva saarathiH -> abhiishuun iti abhiishuun (ra-bhava reverted)"],
         confidence="high", basis=UVATA),

    dict(sutra=37, domain="pragrhya_in_parigraha", rule_type="operative",
         summary="During Parigraha, revert 'nati' (retroflexion) to its natural form, for the same display purpose as 11.36.",
         conditions=["Parigraha is being performed on a word exhibiting nati (retroflexion)"],
         action=["Render in its natural, non-retroflexed form"],
         exceptions=[], examples=["suShumaa yaatam -> susuma iti susuma", "durhaNoH -> duH-hanoH"],
         confidence="high", basis=UVATA),

    dict(sutra=38, domain="pragrhya_in_parigraha", rule_type="operative",
         summary="During Parigraha, revert pluta (protraction) and upacarita treatments to their natural form, for the same reason as 11.36-37.",
         conditions=["Parigraha is being performed on a pluta or upacarita word"],
         action=["Render in the natural, non-pluta/non-upacarita form"],
         exceptions=[], examples=["makShuu makShuu kRNuhi -> makShu iti makShu", "jyotiShkRd asi -> jyotiH-kRt iti jyotiH-kRt"],
         confidence="high", basis=UVATA),

    dict(sutra=39, domain="pragrhya_in_parigraha", rule_type="operative",
         summary="During Parigraha, where a Pragrhya word has become a single fused unit (ekii-bhava) with an adjacent accented vowel, revert to display the Pragrhya word's natural separate form.",
         conditions=["A Pragrhya word has undergone ekii-bhava (fusion) with an adjacent svara-udaya (accented vowel onset)", "Parigraha is being performed"],
         action=["Render the Pragrhya word in its natural, unfused form"],
         exceptions=[], examples=["dampatii iva -> dampatii iti dampatii"],
         confidence="high", basis=UVATA),

    dict(sutra=40, domain="rephita", rule_type="operative",
         summary="Specific named rephita/duu-bhava example words (dunasha, durdhya, durlabha) revert to their natural duu-form under Parigraha, matching 10.22's general dU-bhava rule with concrete instances.",
         conditions=["Parigraha applies to duunaasha/duuDhya/duuLabha-class words"],
         action=["Display in natural duu-form"], exceptions=[],
         examples=["duuNaasha, duuDhya, duuLabha (all confirmed via VedaVishtaram cross-check, RV_PRATISHAKHYA_KRAMA_ARCHITECTURE.md sec.4c)"],
         confidence="high", basis=UVATA),

    dict(sutra=41, domain="rephita", rule_type="operative",
         summary="During Parigraha, revert a repha that arises before an unvoiced ushman to its natural ushman-final form, for display purposes -- the mirror image of 10.22's category-1 rule (which keeps the repha OUTSIDE Parigraha).",
         conditions=["A repha arises from an ushman before an unvoiced consonant", "Parigraha is being performed"],
         action=["Render in the natural (pre-repha) ushman-final form"],
         exceptions=[], examples=["svashcanaaH -> svaH-canaaH", "dhuuHsadam -> dhuuH-sadam", "puuHpatim -> puuH-patim"],
         confidence="high", basis=UVATA),

    dict(sutra=42, domain="parigraha_scope", rule_type="operative",
         summary="A named broad-application case ('mahapradesha', lit. 'great scope' -- applying wherever the same pattern recurs across every recitation instance) and the specific word 'svadhitiH iva' both get the natural-form display treatment under Parigraha.",
         conditions=["Parigraha applies to a mahapradesha-class recurring pattern, or to 'svadhitiH iva' specifically"],
         action=["Display in the natural form"], exceptions=[],
         examples=["naakShaa induH svadhitiiva aha -- repha-loss and lengthening already fixed by ancient convention (per Uvata) -> svadhitiH iva"],
         confidence="medium", basis=UVATA),

    dict(sutra=43, domain="shuddhakshara_agama", rule_type="operative",
         summary="During Parigraha, remove a shuddhakshara-sandhi-derived augment, matching 10.21's general rule with concrete instances.",
         conditions=["Parigraha applies to a word carrying a shuddhakshara-sandhi augment"],
         action=["Omit the augment in the Parigraha display"],
         exceptions=[], examples=["suchandra dasma -> suchandra iti su-chandra",
                                    "pariShkRNvann aniShkRtam -> parikRNvan iti pari-kRNvan",
                                    "dhuurShadam vanarShadam -> dhuuHsadam iti dhuuH-sadam, vanasadam iti vana-sadam"],
         confidence="high", basis=UVATA),

    dict(sutra=44, domain="dvaipada_procedure", rule_type="operative",
         summary="Procedural refinement for the two utterances of a Parigraha-treated compound/split word (dvaipada): in the FIRST utterance (abhikrama) use the previously-established (purva) modified form; in the SECOND (repeated) utterance use the form as caused by what follows (uttarakarita), not the first utterance's form. Any OTHER modification the word independently carries is read the same (anusamhita) in both utterances -- except when the modification is at the very end or very beginning of the word, which is never given in both utterances.",
         conditions=["A word undergoes Parigraha's two-utterance (dvaipada) treatment"],
         action=["First utterance: use the purva-vidhana (previously-established/prior-context) modified form",
                 "Second utterance: use the uttara-karita (following-context-caused) form, not the first utterance's form",
                 "Any other, self-caused modification not from either adjacent context: read identically (as in continuous Samhita) in both utterances"],
         exceptions=["A modification located at the very start or end of the word is never given in both utterances (antagata-adi-yoh tu na)"],
         examples=["pra ma indo -> pra NaH (first utterance, purva form) / na indo (second utterance, uttara form, not 'pra NaH' repeated)"],
         confidence="medium", basis=UVATA,
         caveat="This is one of the more intricate procedural sutras -- the exact scope of 'antagata-adi' deserves a second read against more examples before encoding as executable logic with full confidence."),

    dict(sutra=45, domain="dvaipada_procedure", rule_type="operative",
         summary="For the specific set of phenomena covered by 11.36 onward (nakara-lopa etc.), the SECOND utterance within Parigraha should sometimes be given exactly as in continuous Samhita (without undoing the sandhi) rather than reverted to the natural form -- specifically when the causing factor for that sandhi tracks with (anveti) the FIRST utterance of Parigraha.",
         conditions=["The word falls under the 11.36-class phenomena", "The causal factor for the sandhi change tracks with (belongs to) Parigraha's first utterance rather than the second"],
         action=["Give the second utterance in its normal Samhita (sandhi-applied) form, not reverted to natural form"],
         exceptions=[],
         examples=["shyenaam̐ iva dhrajataH -> shyenaan iti shyenaan iva", "vishvashcandraa amitrahan -> vishvashcandraa iti vishva-chandraaH"],
         confidence="medium", basis=UVATA),

    dict(sutra=46, domain="pragrhya_in_parigraha", rule_type="operative",
         summary="In cases of a double-ushman junction (dvyushma) forming an ushma-sandhi, do NOT apply the extra variation (vikrama) that 11.36-45's reversion mechanism would otherwise suggest -- keep it invariant.",
         conditions=["The junction involves two adjacent ushman (sibilant/spirant) sounds forming an ushma-sandhi"],
         action=["Do not vary/revert this form under Parigraha -- render it the same way in both utterances"],
         exceptions=["Restricted specifically to the double-ushman case (dvyushma) -- Uvata's counter-example 'divaH pRthivyoH' with only a single ushman-adjacency does NOT fall under this restriction and follows the ordinary variation rule instead"],
         examples=["niShShidhvariiH te -> niHsidhvariiH (invariant, not varied)", "svarShaataa yat -> svaHsaataa (invariant)"],
         confidence="medium", basis=UVATA),

    dict(sutra=61, domain="sthita_upasthita_definition", rule_type="operative",
         summary="Confirms, as specifically Sakala practice, that the sthita and sthitopasthita forms (not upasthita alone) are what correctly display a word -- rejecting an earlier view that any one of sthiti/upasthiti/sthitopasthiti could be used interchangeably. The Sakalas specifically perform sthitopasthita in Krama (not just sthiti or upasthiti alone).",
         conditions=["A word requires Parigraha display (per 10.7-10.9)"],
         action=["Use sthita and sthitopasthita forms specifically (per Sakala practice), not upasthita alone, to correctly display the word"],
         exceptions=["Uvata notes this corrects an prior view ('yad uktam adhastaat sthity-upasthita-sthitopasthitaanaam anyatamena pada-pradarshanam aacaranti iti tad ayuktam') that held any of the three could be used interchangeably"],
         examples=[], confidence="medium", basis=UVATA,
         caveat="This sutra is specifically about WHICH of the three named forms (10.12-10.14) is correct Sakala practice -- a refinement of 10.14, not a new mechanism."),
]

STUB_SUMMARIES = {
    # patala, sutra -> (domain, rule_type, one-line summary)
    1: ("catuhkrama_buildup", "rationale", "Opening framing: Krama as taught by aursye-lopa (elision of the visible-cause reasoning); introduces samana-kaala pada-samhita (two words uttered in a single time-unit) as the basic unit under discussion."),
    2: ("catuhkrama_buildup", "operative-undetailed", "Discusses avilopa-karana (non-elision-causing) words that some hold should still be passed over (atigamya) in certain cases -- part of the dvikrama/trikrama build-up toward 11.19's catuhkrama; not separately encoded in this pass."),
    3: ("catuhkrama_buildup", "operative-undetailed", "A one-syllable, non-dvi-yoni (not derived from two sources) word is passed over out of fear of anunasikya (nasalization) ambiguity -- part of the same build-up."),
    4: ("catuhkrama_buildup", "operative-undetailed", "Nati (retroflexion) caused by a preceding element is itself a cause for the following [word's treatment] -- part of the dvikrama justification chain."),
    5: ("catuhkrama_buildup", "rationale", "Restates/elaborates 11.4's two-cause (ubhaya-hetu) reasoning with the 'pari itaH' example."),
    6: ("catuhkrama_buildup", "rationale", "Notes that other [teachers], having considered the sandhya (junction) cause, institute a double-krama (dvikrama) here."),
    7: ("catuhkrama_buildup", "operative-undetailed", "The word 'tamaH' is excluded (apodyate) due to uncertainty (samshaya) about whether it's caused by a following repha; likewise 'aavaH'."),
    8: ("rephita", "operative-undetailed", "Discusses the 'na dhakShi dhukShi' pair and whether they too are excluded on similar grounds -- carries the sole unresolved uncertain-reading word in patala 10-11 (11.8, see RV_PRATISHAKHYA_KRAMA_ARCHITECTURE.md sec.4c)."),
    9: ("catuhkrama_buildup", "operative-undetailed", "The word 'svasaaram' is excluded on similar grounds; distinguishes an upasarga-caused (prefix-caused) case, which by that lineage of reasoning IS carried out with five [repetitions] (panchabhih)."),
    10: ("catuhkrama_buildup", "operative-undetailed", "Further build-up involving 'saha'/'iim'-marked words, guna-augment-caused retention, and pluta words -- 'these [too fall under uncertainty of cause] (nimitta-samshayat)'."),
    11: ("catuhkrama_buildup", "rationale", "States that a double-abhikrama (dvyabhikrama) is prescribed by those who hold a prior cause (purva-nimitta) is the determinant, specifically for the three uttama (last-in-series) cases; 'immediately following' is the operative criterion for them."),
    12: ("catuhkrama_buildup", "rationale", "Immediately-following applies even for the fourth and sixth [cases]; questions why a double-abhikrama would NOT apply there."),
    13: ("catuhkrama_buildup", "operative-undetailed", "Defines 'anaanupurvya' (out-of-natural-order) cases via the non-appearance of the expected pada-sandhi, word-external separation, and intervening words -- terminology feeding 11.14-11.16."),
    14: ("catuhkrama_buildup", "rationale", "Others hold a double-krama on the basis (aashraya) of an established-then-lost (krta-vilupta) phonetic combination (varna-samhita)."),
    15: ("catuhkrama_buildup", "operative-undetailed", "Elaborates the anaanupurvya (out-of-order) procedure: proceeding word-by-natural-order with a preceding element, then across the separated/intervening portions."),
    16: ("catuhkrama_buildup", "operative-undetailed", "Continues: thence without an intervening element (niraaha), for the other of the two [words]; thence, by the unseparated portion, the combination (samhita) belongs to what follows."),
    17: ("catuhkrama_buildup", "rationale", "In an immediately-adjacent triple-krama-causing case, if [the condition holds] by three [words], Gargya [prescribes] again by three more."),
    18: ("catuhkrama_buildup", "operative-undetailed", "In a triple-junction (trisangama) case, a five-fold (panchabhi) accommodation of the aarshi (attested/traditional reading) applies -- the direct precursor to 11.19's catuhkrama."),
    20: ("catuhkrama_qualification", "rationale", "Notes that, due to the absence of elision (alopa-bhava), others perform a many-fold krama (bahukrama); per-instance (pratisvam), the aarshi reading is sometimes not carried out."),
    21: ("catuhkrama_qualification", "rationale", "In cases other than the fully-general triple-etc. instances, [teachers] recall the Sakala practice repeatedly, by a fixed-count convention (sankhya-niyamena)."),
    24: ("samaya_pause", "operative-undetailed", "Extends 11.22-23's default/samaya-pause mechanics: with two words or one word, one should pause at or go past the samaya point while continuing to combine, per the specific case."),
    25: ("parigraha_scope", "operative-undetailed", "Broadens Parigraha's scope further: words-with-iti that are part of a compound, situated in the middle of a many-word group (bahukrame madhyagatani), attaining a third-occurrence status, or bearing an ushman/vikrta/pluta quality without a competing cause (ananyayogam) -- all these, having gone past (atitya), should have their pada-hood (padataam) displayed. Extends 10.7-10.9's scope-defining sutras with more categories; not separately broken into conditions/action in this pass given its density."),
    26: ("catuhkrama_qualification", "rationale", "Notes a case where, per Gargya, a triple-abhikrama recurs."),
    27: ("disambiguation", "rationale", "Recalls the 10.15-style demonstration for an unseen-word-final-sound case in the first [of a pair], but notes here it is without an indicator (niraaha codakah) -- a qualification/counter-case to 10.15."),
    28: ("sthita_upasthita_definition", "rationale", "Restates 10.13's definition: when a word is uttered alone, that is called 'sthiti'."),
    29: ("sthita_upasthita_definition", "rationale", "Restates 10.12's definition: when it is iti-final, that is 'upasthita'."),
    30: ("sthita_upasthita_definition", "rationale", "Restates: when [a word] is inverted and combined (viparyasya samasya), that is when they perform 'sthitopasthita' (10.14)."),
    31: ("samasa_handling", "operative-undetailed", "When [a teacher], speaking again, [gives] a compound there, one should split it at the avagraha -- restates/extends 10.16."),
    32: ("phonetic_detail", "operative-undetailed", "From 'svaH' onward, in other [similar words] too, one should apply sandhi; a duration-retention (kaala-dharana) like that of avagraha is recalled to exist in Parigraha as 'upadha' -- restates/extends 10.17."),
    33: ("dvaipada_procedure", "operative-undetailed", "Detailed procedure for the two utterances of a Parigraha word: proceed on both sides with the combined (anusamhita) form, then display its pada-hood afterward; or, word-by-word, combine by either alternative, in the three uttama (last-in-series) cases, given the possibility of non-elision here."),
    34: ("samasa_handling", "operative-undetailed", "A word without a raga-consonant junction is excepted with an 'aa'; having stated it again, one should proceed as before (purvavat) with the resolution (adhyavasaya) -- an exception to 11.31-33's compounding procedure."),
    35: ("catuhkrama_qualification", "rationale", "Likewise, in an accidentally-arising (yadRccha-upanata) many-fold-krama case, one should proceed krama-wise, releasing (nihsRjan) that [word's] individual pada-forms."),
    47: ("parigraha_scope", "operative-undetailed", "When same-time or immediately-adjacent avasana-causing [words] coincide, [and it is] a case of the word's own fault (doSha) rather than a gap in the reason (hetv-asangrahe), the established aarshi [reading] is dropped by the alternative -- a further qualifying/exception case for Parigraha's scope."),
    48: ("phonetic_reversion", "operative-undetailed", "On m-elision, with an altered-vowel base, in a third-occurrence state, the FIRST [form] is fixed (dhruvam) -- a phonetic-reversion detail parallel to 11.36-46."),
    49: ("phonetic_reversion", "rationale", "Or, the reverse, for those who have adopted the other [reading]."),
    50: ("phonetic_reversion", "operative-undetailed", "When both [words] have a nasal-vowel onset [a further phonetic-reversion case, not detailed in this pass]."),
    51: ("phonetic_reversion", "operative-undetailed", "When [a vowel is] preceded by a nasalized nati [a further phonetic-reversion case, not detailed in this pass]."),
    52: ("svara_krama", "rationale", "Thus the sequence (krama) of the syllable [that] falls on one and the same [pada] -- transitions into the accent(svara)-in-Krama section that runs through 11.53-60."),
    53: ("svara_krama", "operative-undetailed", "A preceding [syllable] should not, here, obtain samhita-status via a svarita accent, when its accent-onset is fixed (niyata-svarodaye) -- opens the Krama-accent rules; not separately encoded in this pass (see module docstring: the whole 11.47-60 accent block is future work)."),
    54: ("svara_krama", "operative-undetailed", "How an anudatta (unaccented) syllable comes under the sway of the accent-onset of the following word's beginning."),
    55: ("svara_krama", "operative-undetailed", "When the accent-onset is fixed and udatta-preceded, the following [accent] is lost (viLopa), un-fixed, when it is a lesser (avara) one."),
    56: ("svara_krama", "operative-undetailed", "When [an accent] would strike a syllable that is not its [own] cause, [describes] one part of a svarita and what follows it."),
    57: ("svara_krama", "operative-undetailed", "When udatta-preceded, and also where an anudatta-junction [occurs], when it obtains either of two accents, or even many."),
    58: ("svara_krama", "rationale", "As the accent and syllable-junction of those two [words] is [normally] fashioned, so [it is retained] here; others say an aarshya-loss (non-attested-reading loss) occurs at the point of non-appearance in the Krama sequence, [while] others speak of a non-aarsha accent."),
    59: ("svara_krama", "rationale", "If an unattested [reading] is seen in an aarshi context in Krama, some call it a loss; thus [describes] the causes of aarshi-loss-in-Krama, [applied] though Krama-consistently, joining even many [instances]."),
    60: ("svara_krama", "operative-undetailed", "When a word, or the word-final [portion], does not reach its accent-resting-point (svaravasanam) [and instead] is what applies here; then it does not obtain a [new] form once removed (nirakrtam), unless without it (niraaha) one returns [to the earlier] word."),
    62: ("recitation_completeness", "rationale", "One should proceed through (kramet) ALL words without omission (nirbruvan) -- they recall this [as the point of Krama]. Meta-statement about Krama's completeness requirement, not a new phonetic/structural rule."),
    63: ("recitation_completeness", "rationale", "One should not skip over (na utkramet) what has already been practiced; speaking of the method (varma) and origin (smrti-sambhavau) of Krama, one should recite the rest in due sequence (samadhim anu) after it."),
    64: ("lineage_history", "rationale", "As originally taught, the Krama-shastra [should be recited] from the beginning again, not variously and separately -- it is not proper [to do otherwise]."),
    65: ("lineage_history", "rationale", "Thus Prabahravya spoke, and taught Krama; he, the first proclaimer of Krama, declared it first. (Names the traditional first teacher of the Krama method.)"),
    66: ("purpose_rationale", "rationale", "Argues Krama has no purpose in mere word-combination-knowledge for those whose grasp rests on prior-established convention alone; it is not a complete accomplishment, nor does it enable any other accomplisher, nor produce or remove [meaning] on its own, nor is it [itself] a Vedic text -- an objection Krama's value is then defended against in 11.67-69."),
    67: ("purpose_rationale", "rationale", "If accomplishment is reversed for what is unaccomplished, so is non-accomplishment reversed for what is accomplished -- a dialectical rebuttal to 11.66's objection."),
    68: ("purpose_rationale", "rationale", "Where exceptions co-exist with the general teaching, Krama is not without purpose in works of instruction (pradesha-shastra)."),
    69: ("purpose_rationale", "rationale", "Krama is meaningful: from the reversal [shown in 11.67], from the perception of scriptural agreement, from the absence of reliance on either side's prior-establishment alone, from wide acceptance by the learned, and from being confirmed by scriptural transmission (shruti) -- it produces right understanding (sanmanakarah)."),
    70: ("purpose_rationale", "rationale", "Without Krama, the accent of a two-word combination, and the culminating act (paaraNa-karma) of recitation, would not be accomplished."),
    71: ("purpose_rationale", "rationale", "Therefore, the augmentation (bRmhanam) of the Rig and Yajur[-vedas] by words and accents, and likewise their study, [proceeds] by the threefold [Samhita-Pada-Krama recitation]."),
}


def load_sutra_lookup():
    with open(SUTRA_DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {(it["patala"], it["sutra"]): it for it in data["items"]}


def build_entry(patala, detail, lookup):
    sutra_item = lookup[(patala, detail["sutra"])]
    return {
        "id": f"{patala}.{detail['sutra']}",
        "patala": patala,
        "sutra": detail["sutra"],
        "sutra_text_devanagari": sutra_item["text_devanagari"],
        "sutra_text_iast": sutra_item["text_iast"],
        "domain": detail["domain"],
        "rule_type": detail["rule_type"],
        "summary": detail["summary"],
        "conditions": detail["conditions"],
        "action": detail["action"],
        "exceptions": detail["exceptions"],
        "examples": detail["examples"],
        "confidence": detail["confidence"],
        "basis": detail["basis"],
        "caveat": detail.get("caveat", ""),
        "validated_against_attested_krama": False,
    }


def build_stub(patala, sutra, domain, rule_type, summary, lookup):
    sutra_item = lookup[(patala, sutra)]
    return {
        "id": f"{patala}.{sutra}",
        "patala": patala,
        "sutra": sutra,
        "sutra_text_devanagari": sutra_item["text_devanagari"],
        "sutra_text_iast": sutra_item["text_iast"],
        "domain": domain,
        "rule_type": rule_type,
        "summary": summary,
        "conditions": [],
        "action": [],
        "exceptions": [],
        "examples": [],
        "confidence": "unclassified",
        "basis": "Sutra text only, one-line paraphrase; not reduced to conditions/action in this pass -- see module docstring.",
        "caveat": "Not yet worked out in operative detail.",
        "validated_against_attested_krama": False,
    }


def main():
    lookup = load_sutra_lookup()
    rules = []

    for detail in PATALA_10:
        rules.append(build_entry(10, detail, lookup))

    detailed_11 = {d["sutra"] for d in PATALA_11_DETAILED}
    for detail in PATALA_11_DETAILED:
        rules.append(build_entry(11, detail, lookup))

    for sutra in range(1, 72):
        if sutra in detailed_11:
            continue
        domain, rule_type, summary = STUB_SUMMARIES[sutra]
        rules.append(build_stub(11, sutra, domain, rule_type, summary, lookup))

    rules.sort(key=lambda r: (r["patala"], r["sutra"]))

    out = {
        "schema": "generic",
        "note": (
            "Rule-logic interpretation layer built on top of "
            "rigveda_pratishakhya/data.json's raw sutra text (patala 10, Krama, "
            "all 22 sutras) and a targeted subset of patala 11 (Kramahetu) that "
            "directly extends it operationally (14 of 71 sutras). This is "
            "INTERPRETATION, not citation -- see this file's own generating "
            "script (tools/pratishakhya/build_krama_rules.py) for the full "
            "scope statement and the caveat that NONE of this has yet been "
            "validated against an actual attested Krama-patha text "
            "(dge/RV_PRATISHAKHYA_KRAMA_ARCHITECTURE.md sec.7/sec.10). The "
            "remaining 57 patala-11 sutras are classified (domain/rule_type/"
            "one-line summary) but not reduced to conditions/action -- most "
            "of patala 11 beyond the 14 detailed sutras is rationale, "
            "historical lineage, or grammarians' debate, not new operative "
            "content a generator would execute."
        ),
        "source_sutras": "dge/data/vedanga/shiksha/pratishakhya/rigveda_pratishakhya/data.json",
        "items": rules,
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    n_operative = sum(1 for r in rules if r["rule_type"] not in ("rationale", "adhikara") and r["confidence"] != "unclassified")
    print(f"Wrote {len(rules)} rule entries ({n_operative} fully worked out) to {OUT_PATH}")


if __name__ == "__main__":
    main()
