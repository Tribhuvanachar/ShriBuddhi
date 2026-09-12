"""
parity_compute.py — the Python side of js/test-parity.js's cross-language
check. Reads a JSON array of Devanagari words/phrases from stdin, computes
search_toolkit_pkg's own to_slp1/phonetic_key/coarse_key/trigrams for each
(the SAME functions build_search_index.py itself calls at index time), and
writes a JSON array of results to stdout.

Not a general-purpose tool -- exists solely so test-parity.js can spawn one
python3 process and get every word's Python-side output in a single round
trip, instead of one subprocess per word.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from search_toolkit_pkg.normalize import phonetic_key, coarse_key, trigrams
from search_toolkit_pkg.translit import to_slp1


def main():
    words = json.loads(sys.stdin.read())
    out = []
    for w in words:
        slp1 = to_slp1(w, 'devanagari')
        pk = phonetic_key(slp1)
        ck = coarse_key(slp1)
        out.append({
            'input': w,
            'slp1': slp1,
            'pkey': pk,
            'ckey': ck,
            'trigrams': sorted(trigrams(pk)),
        })
    print(json.dumps(out))


if __name__ == '__main__':
    main()
