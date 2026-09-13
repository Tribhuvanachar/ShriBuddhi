#!/usr/bin/env python3
"""Enrich the Jagannātha Tīrtha (Vyāsarāja Maṭha, jagannatha_v) node in the
canonical parampara.json with the full biography drawn from the two sources
the project lead supplied:

  * https://madhwayati.blogspot.com/2019/04/jagannatha-teertharu-1770-kumbakonam.html
  * https://www.sumadhwaseva.com/yatigalu/vyasaraja-mutt/jagannatha-tirtharu/

Fills the existing structured fields (titles, works, purva, contrib) that were
empty, and adds a new optional `bio` object — the "rich bio panel" the guru
detail views render (dgeGuruBioHtml in guru-data.js): a dhyāna-śloka, a
narrative summary, origin, works, anecdotes, his own commemorative verse, an
image, and the source links. Additive and idempotent — only jagannatha_v is
touched; re-running overwrites just that node's enriched fields.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, 'dge/guru-parampara/data/parampara.json')

BIO = {
    "image": "https://www.sumadhwaseva.com/wp-content/uploads/2009/12/JAGANNATHA-Teertharu-Kumbukonam.jpg",
    "dhyana": {
        "deva": "विद्वत्पङ्कजमार्ताण्डो वादिमत्तेभकेसरी।\nजगन्नाथगुरुर्भूयात् ज्यायसे श्रेयसे मम॥",
        "note": "Dhyāna-śloka — “May Guru Jagannātha, the sun that unfolds the "
                "lotus-scholars, the lion among rutting debater-elephants, be "
                "for my greater good.”"
    },
    "summary": (
        "Śrī Jagannātha Tīrtha — celebrated as <b>Bhāṣyadīpikācārya</b> after his "
        "masterwork — was the pontiff of the Vyāsarāja Maṭha from 1755 to 1770, with "
        "his bṛndāvana at Kumbhakoṇam. Tradition holds him to be an avatāra of "
        "Gālava Ṛṣi. He was among the very few Vyāsarāja Maṭha yatis to take saṁnyāsa "
        "directly from brahmacarya after Śrī Vyāsarāja himself. He studied for nearly "
        "thirty years under his guru Śrī Śeṣacandrikācārya, and his own commentaries "
        "on the Brahma-sūtra Bhāṣya remain indispensable to Mādhva students of every "
        "maṭha."
    ),
    "origin": (
        "Born in <b>Varavani</b> village on the north bank of the Pinākinī (Pennār) "
        "river, Gauribidanūr tāluk, Kolār district. Kauṇḍinya gotra, Tangedi family "
        "(Ṣaṣṭika vaṁśa). His forebears held rights over five villages known together "
        "as the “Varavani Pañcagrāma”; the family deity was Narasiṁha at "
        "Honnappanahaḷḷi."
    ),
    "anecdotes": [
        {
            "title": "Saved by Narasiṁha from the mango tree",
            "text": (
                "While travelling in the Tekkalu region of Tamil country he was "
                "pursued by hostile soldiers. He prayed to his family deity Narasiṁha, "
                "who burst forth from a nearby mango tree and destroyed the attackers. "
                "He recorded the deliverance in his own verse within the Bhāṣyadīpikā."
            )
        },
        {
            "title": "Swimming the Kāverī with the devara-peṭṭige",
            "text": (
                "When soldiers tried to seize the devara-peṭṭige (the casket of the "
                "worship-icons and ornaments), he swam some twenty kilometres down the "
                "rushing Kāverī holding the sacred chest so that no unqualified hand "
                "should touch it. A sword-wound taken in the act would have disqualified "
                "him from ritual service, but his guru healed him within forty-eight "
                "days through special Narasiṁha worship."
            )
        },
        {
            "title": "How the title Bhāṣyadīpikācārya was won",
            "text": (
                "One night his guru Śeṣacandrikācārya found the young ascetic asleep "
                "clutching a manuscript — the Bhāṣyadīpikā. On reading it he was "
                "astonished at its brilliance, conferred the honorific "
                "“Bhāṣyadīpikācārya,” and reinstated him as successor. The place where "
                "he composed his works — the Bhāvan Kalmaṇṭapam — still bears his image "
                "carved on a pillar."
            )
        }
    ],
    "verses": [
        {
            "deva": "आम्रस्तम्भात् समागत्य ताम्रतुण्डान् निहत्य यः।\nनम्रं नौमि जगन्नाथं ताम्रोपात्तं नृकेसरी॥",
            "iast": "āmrastambhāt samāgatya tāmratuṇḍān nihatya yaḥ | "
                    "namraṃ naumi jagannāthaṃ tāmropāttaṃ nṛkesarī ||",
            "note": "His own verse on the man-lion (Nṛkesarī) who came forth from the "
                    "mango-pillar and struck down the copper-armed foe — from the "
                    "Bhāṣyadīpikā. (Reading normalised from the two source sites.)"
        }
    ],
    "refs": [
        {"label": "madhwayati.blogspot.com",
         "url": "https://madhwayati.blogspot.com/2019/04/jagannatha-teertharu-1770-kumbakonam.html"},
        {"label": "sumadhwaseva.com",
         "url": "https://www.sumadhwaseva.com/yatigalu/vyasaraja-mutt/jagannatha-tirtharu/"}
    ]
}

ENRICH = {
    "titles": ["Bhāṣyadīpikācārya", "Vidvatpaṅkaja Mārtāṇḍa",
               "Vādimattebhakesarī", "Yatikulatilaka"],
    "works": ["Bhāṣyadīpikā", "Sūtradīpikā",
              "Rigbhāṣya-ṭīkā Tippaṇī (traced, unrecovered)"],
    "contrib": (
        "Pontiff of the Vyāsarāja Maṭha 1755–1770; disciple of Śeṣacandrikācārya and "
        "guru of Śrīnātha Tīrtha. Author of the Bhāṣyadīpikā and Sūtradīpikā on Madhva's "
        "Brahma-sūtra Bhāṣya — for which he is known as Bhāṣyadīpikācārya — held "
        "indispensable across all Mādhva maṭhas. One of the few Vyāsarāja Maṭha yatis to "
        "take saṁnyāsa directly from brahmacarya. Bṛndāvana at Kumbhakoṇam; ārādhanā on "
        "Puṣya Śukla Dvitīyā."
    ),
    "bio": BIO,
}


def main():
    data = json.load(open(SRC, encoding='utf-8'))
    nodes = data['nodes'] if isinstance(data, dict) and 'nodes' in data else data
    if isinstance(nodes, dict):
        node = nodes.get('jagannatha_v')
    else:
        node = next((n for n in nodes if n.get('id') == 'jagannatha_v'), None)
    if not node:
        raise SystemExit('jagannatha_v not found')
    node.update(ENRICH)
    # keep the two supplied source URLs in the tracking `sources` list too
    for u in (BIO['refs'][0]['url'], BIO['refs'][1]['url']):
        if u not in node.setdefault('sources', []):
            node['sources'].append(u)
    json.dump(data, open(SRC, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('enriched jagannatha_v: titles=%d works=%d anecdotes=%d verses=%d'
          % (len(node['titles']), len(node['works']),
             len(BIO['anecdotes']), len(BIO['verses'])))


if __name__ == '__main__':
    main()
