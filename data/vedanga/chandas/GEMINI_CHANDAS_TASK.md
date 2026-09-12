# DGE Chandas engine — Gemini task brief

Generated 06 Sep 2026, 11:11 AM IST by `tools/chandas/build_gemini_task.py`. Canonical URL: `https://raw.githubusercontent.com/Tribhuvanachar/bhumandala/main/data/vedanga/chandas/GEMINI_CHANDAS_TASK.md`

You are helping the Sarvamūla Digital Library (a Mādhva Sanskrit corpus) finish its classical-metre
(vṛtta) identifier. You have no repository access; **this file is your entire brief**. Everything you
return is verified mechanically by our engine before it is used, so precision matters more than volume:
answer `null` / `"unsure"` rather than inventing a verse or a lakṣaṇa.

## 0. How to answer

* Reply with **JSON only** (no prose before or after, no Markdown fences), one object per run:
  `{"schema": "dge_chandas_gemini_v1", "part": "A" | "B" | "C" | "D", "items": [ ... ]}`
* Work **one part per run**. If a part is too long for one reply, add `"batch": <n>` and do the batch we
  name in the prompt ("Part C batch 3"), or the first `40` items when no batch is named.
* Devanagari only for Sanskrit text. Split every verse into pādas with `\n` (four pādas for a
  catuṣpadī; an āryā-family verse also as four). No dandas, no verse numbers, no speaker lines.
* **Scan notation**: `L` = laghu, `G` = guru, one letter per akṣara, one string per pāda. Guru = long
  vowel, or a vowel followed by anusvāra/visarga/candrabindu/jihvāmūlīya/upadhmānīya, or followed by a
  conjunct; the last akṣara of a pāda is anceps. Gaṇa letters: य=LGG म=GGG त=GGL र=GLG ज=LGL
  भ=GLL न=LLL स=LLG ल=L ग=G.
* Cite sources exactly as `work chapter.verse` (e.g. `Kumārasambhava 1.1`, `Sumadhva Vijaya 7.10`,
  `Bhāgavata 4.9.6`, `Vṛttaratnākara 3.30`). Prefer Mādhva works (Sumadhva Vijaya, Rāghavendra Vijaya,
  Tīrthaprabandha, Dvādaśa Stotra, Madhva's own stotras), then Bhāgavata, Kālidāsa, Bhartṛhari,
  Māgha, Bhāravi, and the example verses printed in Vṛttaratnākara / Chandomañjarī / Śrutabodha.
* Give a `confidence` between 0 and 1 on every item. Self-check every example by scanning it: if your
  scan does not match the lakṣaṇa in §1, do not submit it.

## 1. The 245 vṛttas the engine knows (Chandojñānam table, AGPL-3.0 data)

`type`: sama = all four pādas alike; ardhasama = pādas 1,3 alike and 2,4 alike; viṣama = all differ;
upajāti = a named 4-pāda combination of indravajrā (I = GGLGGLLGLGG) and upendravajrā
(U = LGLGGLLGLGG) or of the other listed pādas. Yati = caesura positions counted in akṣaras.

| vṛtta (id) | other names | type | gaṇa | pattern L/G | akṣaras | yati | has verified example? |
|---|---|---|---|---|---|---|---|
| अतिरेखा | सुखेलक, प्रभद्रक | sama | नजभजर | `LLLLGLGLLLGLGLG` | 15 | 5,10 | **no** |
| अतिशायिनी | — | sama | ससजभजगग | `LLGLLGLGLGLLLGLGG` | 17 | 10,7 | **no** |
| अद्रितनया | अश्वललित | sama | नजभजभजभलग | `LLLLGLGLLLGLGLLLGLGLLLG` | 23 | 11,12 | **no** |
| अपराजिता | — | sama | ननरसलग | `LLLLLLGLGLLGLG` | 14 | 7,7 | **no** |
| अपवाह | — | sama | मननननननसगग | `GGGLLLLLLLLLLLLLLLLLLLLGGG` | 26 | 9,6,6,5 | **no** |
| असम्बाधा | — | sama | मतनसगग | `GGGGGLLLLLLGGG` | 14 | 5,9 | **no** |
| इन्द्रवज्रा | — | sama | ततजगग | `GGLGGLLGLGG` | 11 | 5,6 | yes |
| इन्द्रवंशा | — | sama | ततजर | `GGLGGLLGLGLG` | 12 | 5,7 | yes |
| उज्ज्वला | — | sama | ननभर | `LLLLLLGLLGLG` | 12 | — | **no** |
| उपस्थित | शिखण्डित | sama | जसतगग | `LGLLLGGGLGG` | 11 | — | **no** |
| उपेन्द्रवज्रा | — | sama | जतजगग | `LGLGGLLGLGG` | 11 | 5,6 | yes |
| ऋषभगजविलसित | गजतुरगविलसित | sama | भरनननग | `GLLGLGLLLLLLLLLG` | 16 | 7,11 | **no** |
| कलहंस | कुटजा, सिंहनाद, नन्दिनी | sama | सजससग | `LLGLGLLLGLLGG` | 13 | 6,7 | **no** |
| कुमारललिता | — | sama | जसग | `LGLLLGG` | 7 | 3,4 | **no** |
| कुसुमविचित्रा | — | sama | नयनय | `LLLLGGLLLLGG` | 12 | — | **no** |
| कुसुमितलतावेल्लिता | — | sama | मतनययय | `GGGGGLLLLLGGLGGLGG` | 18 | 5,6,7 | **no** |
| क्रौञ्चपदा | — | sama | भमसभननननग | `GLLGGGLLGGLLLLLLLLLLLLLLG` | 25 | 5,5,8,7 | yes |
| क्षमा | उत्पलिनी, चन्द्रिका | sama | ननततग | `LLLLLLGGLGGLG` | 13 | 7,6 | **no** |
| गजगति | — | sama | नभलग | `LLLGLLLG` | 8 | 4,4 | **no** |
| गीतिका | — | sama | सजसभरसलग | `LLGLGLLLGGLLGLGLLGLG` | 20 | 5,5,5,5 | **no** |
| चन्द्रलेखा | — | sama | मरमयय | `GGGGLGGGGLGGLGG` | 15 | 7,8 | **no** |
| चन्द्रवर्त्म | — | sama | रनभस | `GLGLLLGLLLLG` | 12 | 4,8 | **no** |
| चित्र | — | sama | रजरजरग | `GLGLGLGLGLGLGLGG` | 16 | 8,8 | **no** |
| चित्रपदा | — | sama | भभगग | `GLLGLLGG` | 8 | — | **no** |
| चित्रलेखा | — | sama | मभनययय | `GGGGLLLLLLGGLGGLGG` | 18 | 4,7,7 | **no** |
| जलधरमाला | — | sama | मभसम | `GGGGLLLLGGGG` | 12 | 4,8 | **no** |
| जलोद्धतगति | — | sama | जसजस | `LGLLLGLGLLLG` | 12 | 6,6 | **no** |
| तन्वी | — | sama | भतनसभभनय | `GLLGGLLLLLLGGLLGLLLLLLGG` | 24 | 5,7,12 | **no** |
| तामरस | — | sama | नजजय | `LLLLGLLGLLGG` | 12 | 5,7 | **no** |
| तारका | नाराच | sama | ननरररर | `LLLLLLGLGGLGGLGGLG` | 18 | 13,5 | **no** |
| तूणक | चामर | sama | रजरजर | `GLGLGLGLGLGLGLG` | 15 | 7,8 | **no** |
| तोटक | — | sama | सससस | `LLGLLGLLGLLG` | 12 | 6,6 | yes |
| त्वरितगति | — | sama | नजनग | `LLLLGLLLLG` | 10 | 5,5 | **no** |
| दोधक | — | sama | भभभगग | `GLLGLLGLLGG` | 11 | 6,5 | yes |
| द्रुतविलम्बित | हरिणप्लुत | sama | नभभर | `LLLGLLGLLGLG` | 12 | 4,8 | yes |
| नन्दन | — | sama | नजभजरर | `LLLLGLGLLLGLGLGGLG` | 18 | 11,7 | **no** |
| नर्दटक | नर्कुटक | sama | नजभजजलग | `LLLLGLGLLLGLLGLLG` | 17 | 8,9 | **no** |
| नवमालिनी | नवमालिका | sama | नजभय | `LLLLGLGLLLGG` | 12 | 8,4 | **no** |
| पञ्चकावली | धृतश्री, सरसी | sama | नजभजजजर | `LLLLGLGLLLGLLGLLGLGLG` | 21 | 7,7,7 | **no** |
| पञ्चचामर | — | sama | जरजरजग | `LGLGLGLGLGLGLGLG` | 16 | 8,8 | yes |
| पणव | — | sama | मनयग | `GGGLLLLGGG` | 10 | 5,5 | **no** |
| पथ्या | मञ्जरी | sama | सजसयलग | `LLGLGLLLGLGGLG` | 14 | 5,9 | **no** |
| पुट | — | sama | ननमय | `LLLLLLGGGLGG` | 12 | 8,4 | **no** |
| पृथ्वी | — | sama | जसजसयलग | `LGLLLGLGLLLGLGGLG` | 17 | 8,9 | yes |
| प्रभा | मन्दाकिनी, प्रमुदितवदना | sama | ननरर | `LLLLLLGLGGLG` | 12 | 7,5 | **no** |
| प्रमदा | कुररीरुता | sama | नजभजलग | `LLLLGLGLLLGLLG` | 14 | 6,8 | **no** |
| प्रमाणिका | नगस्वरूपिणी | sama | जरलग | `LGLGLGLG` | 8 | 4,4 | **no** |
| प्रमिताक्षरा | — | sama | सजसस | `LLGLGLLLGLLG` | 12 | 5,7 | yes |
| प्रहरणकलिका | — | sama | ननभनलग | `LLLLLLGLLLLLLG` | 14 | 7,7 | **no** |
| प्रहर्षिणी | — | sama | मनजरग | `GGGLLLLGLGLGG` | 13 | 3,10 | yes |
| भद्रिका २ | — | sama | ननरलग | `LLLLLLGLGLG` | 11 | — | **no** |
| भुजगशिशुभृता | — | sama | ननम | `LLLLLLGGG` | 9 | 7,2 | **no** |
| भुजङ्गप्रयात | — | sama | यययय | `LGGLGGLGGLGG` | 12 | 6,6 | yes |
| भुजङ्गविजृम्भित | भुजङ्गविलसित | sama | ममतनननरसलग | `GGGGGGGGLLLLLLLLLLGLGLLGLG` | 26 | 8,11,7 | **no** |
| भुजङ्गसङ्गता | — | sama | सजर | `LLGLGLGLG` | 9 | 3,6 | **no** |
| भ्रमरविलसित | भ्रमरविलसिता | sama | मभनलग | `GGGGLLLLLLG` | 11 | 4,7 | **no** |
| मञ्जुभाषिणी | प्रबोधिता, सुनन्दिनी | sama | सजसजग | `LLGLGLLLGLGLG` | 13 | 6,7 | yes |
| मणिमध्य | — | sama | भमस | `GLLGGGLLG` | 9 | 5,4 | **no** |
| मणिमाला | — | sama | तयतय | `GGLLGGGGLLGG` | 12 | 6,3 | yes |
| मत्तमयूर | — | sama | मतयसग | `GGGGGLLGGLLGG` | 13 | 4,9 | **no** |
| मत्तविलासिनी | — | sama | भभभभभभर | `GLLGLLGLLGLLGLLGLLGLG` | 21 | — | **no** |
| मत्ता | — | sama | मभसग | `GGGGLLLLGG` | 10 | 4,6 | **no** |
| मत्ताक्रीडा | — | sama | ममतननननलग | `GGGGGGGGLLLLLLLLLLLLLLG` | 23 | 8,15 | **no** |
| मत्तेभविक्रीडित | — | sama | सभरनमयलग | `LLGGLLGLGLLLGGGLGGLG` | 20 | 13,7 | **no** |
| मदलेखा | — | sama | मसग | `GGGLLGG` | 7 | — | **no** |
| मदिरा | मानिनी | sama | भभभभभभभग | `GLLGLLGLLGLLGLLGLLGLLG` | 22 | — | **no** |
| मधुमती | मधु | sama | ननग | `LLLLLLG` | 7 | — | **no** |
| मध्यक्षामा | कुटिला, हंसश्येनी | sama | मभनयगग | `GGGGLLLLLLGGGG` | 14 | 4,10 | **no** |
| मनोरमा | — | sama | नरजग | `LLLGLGLGLG` | 10 | — | **no** |
| मन्दाक्रान्ता | — | sama | मभनततगग | `GGGGLLLLLGGLGGLGG` | 17 | 4,6,7 | yes |
| मन्दारमाला | — | sama | तततततततग | `GGLGGLGGLGGLGGLGGLGGLG` | 22 | 4,6,6,6 | **no** |
| मयूरसारिणी | — | sama | रजरग | `GLGLGLGLGG` | 10 | — | **no** |
| माणवक | माणवकक्रीड | sama | भतलग | `GLLGGLLG` | 8 | 4,4 | **no** |
| मालती | यमुना | sama | नजजर | `LLLLGLLGLGLG` | 12 | 5,7 | **no** |
| मालिनी | — | sama | ननमयय | `LLLLLLGGGLGGLGG` | 15 | 8,7 | yes |
| मेघविस्फूर्जिता | — | sama | यमनसररग | `LGGGGGLLLLLGGLGGLGG` | 19 | 6,6,7 | **no** |
| रथोद्धता | — | sama | रनरलग | `GLGLLLGLGLG` | 11 | 3,8 | yes |
| रुक्मवती | चम्पकमाला | sama | भमसग | `GLLGGGLLGG` | 10 | 5,5 | **no** |
| रुचिरा | प्रभावती | sama | जभसजग | `LGLGLLLLGLGLG` | 13 | 4,9 | yes |
| ललिता | — | sama | तभजर | `GGLGLLLGLGLG` | 12 | — | **no** |
| कामक्रीडा | लीलाखेल | sama | ममममम | `GGGGGGGGGGGGGGG` | 15 | 8,7 | **no** |
| वंशपत्रपतित | — | sama | भरनभनलग | `GLLGLGLLLGLLLLLLG` | 17 | 10,7 | **no** |
| वंशस्थ | वंशस्थविल, वंशस्तनित | sama | जतजर | `LGLGGLLGLGLG` | 12 | 5,7 | yes |
| वसन्ततिलका | सिंहोन्नता, सिंहोद्धता, उद्धर्षिणी | sama | तभजजगग | `GGLGLLLGLLGLGG` | 14 | 8,6 | yes |
| वाणिनी | — | sama | नजभजरग | `LLLLGLGLLLGLGLGG` | 16 | — | **no** |
| वातोर्मी | — | sama | मभतगग | `GGGGLLGGLGG` | 11 | 4,7 | yes |
| वासन्ती | — | sama | मतनमगग | `GGGGGLLLLGGGGG` | 14 | 4,6,4 | **no** |
| विद्युन्माला | — | sama | ममगग | `GGGGGGGG` | 8 | 4,4 | **no** |
| वृत्ता | — | sama | ननसगग | `LLLLLLLLGGG` | 11 | 4,7 | **no** |
| वैश्वदेवी | — | sama | ममयय | `GGGGGGLGGLGG` | 12 | 5,7 | **no** |
| शशिकला | — | sama | ननननस | `LLLLLLLLLLLLLLG` | 15 | 7,8 | **no** |
| शार्दूलललित | — | sama | मसजसतस | `GGGLLGLGLLLGGGLLLG` | 18 | 12,6 | **no** |
| शार्दूलविक्रीडित | — | sama | मसजसततग | `GGGLLGLGLLLGGGLGGLG` | 19 | 12,7 | yes |
| शालिनी | — | sama | मततगग | `GGGGGLGGLGG` | 11 | 4,7 | yes |
| शिखरिणी | — | sama | यमनसभलग | `LGGGGGLLLLLGGLLLG` | 17 | 6,11 | yes |
| शुद्धविराट् | — | sama | मसजग | `GGGLLGLGLG` | 10 | — | **no** |
| श्येनी | श्येनिका | sama | रजरलग | `GLGLGLGLGLG` | 11 | — | **no** |
| सुमधुरा | — | sama | मरभरमनग | `GGGGLGGLLGLGGGGLLLG` | 19 | 7,6,6 | **no** |
| सुमन्दारमाला | — | sama | यययययययलग | `LGGLGGLGGLGGLGGLGGLGGLG` | 23 | 5,6,6,6 | **no** |
| सुमुखी | — | sama | नजजलग | `LLLLGLLGLLG` | 11 | 5,6 | **no** |
| सुरसा | — | sama | मरभरयनग | `GGGGLGGLLGLGLGGLLLG` | 19 | 7,7,5 | **no** |
| सुवदना | — | sama | मरभनयभलग | `GGGGLGGLLLLLLGGGLLLG` | 20 | 7,7,6 | **no** |
| स्रग्धरा | — | sama | मरभनययय | `GGGGLGGLLLLLLGGLGGLGG` | 21 | 7,7,7 | yes |
| स्रग्विणी | — | sama | रररर | `GLGGLGGLGGLG` | 12 | 6,6 | yes |
| स्वागता | — | sama | रनभगग | `GLGLLLGLLGG` | 11 | 3,8 | yes |
| हरिणी | — | sama | नसमरसलग | `LLLLLGGGGGLGLLGLG` | 17 | 6,4,7 | yes |
| हंसरुत | — | sama | मनगग | `GGGLLLGG` | 8 | — | **no** |
| हंसी १ | — | sama | ममतनननसग | `GGGGGGGGLLLLLLLLLLLLGG` | 22 | 8,14 | **no** |
| नदी १ | — | sama | मर | `GGGGLG` | 6 | — | **no** |
| पङ्क्ति | — | sama | भगग | `GLLGG` | 5 | — | **no** |
| कन्या | — | sama | मग | `GGGG` | 4 | — | **no** |
| सती | — | sama | नग | `LLLG` | 4 | — | **no** |
| तनुमध्या | — | sama | तय | `GGLLGG` | 6 | — | **no** |
| रमणी | — | sama | सस | `LLGLLG` | 6 | — | **no** |
| लासिनी | — | sama | जग | `LGLG` | 4 | — | **no** |
| वसुमती | — | sama | तस | `GGLLLG` | 6 | — | **no** |
| मणिराग | — | sama | रससग | `GLGLLGLLGG` | 10 | — | **no** |
| मन्दा | — | sama | तलग | `GGLLG` | 5 | — | **no** |
| प्रिया | — | sama | सलग | `LLGLG` | 5 | — | **no** |
| मुकुल | — | sama | मस | `GGGLLG` | 6 | — | **no** |
| मेघवितान | — | sama | सससग | `LLGLLGLLGG` | 10 | — | **no** |
| मौक्तिकदाम | — | sama | जजजज | `LGLLGLLGLLGL` | 12 | 6,6 | **no** |
| शशिवदना | — | sama | नय | `LLLLGG` | 6 | — | **no** |
| मौक्तिकमाला | श्री, अनुकूला | sama | भतनगग | `GLLGGLLLLGG` | 11 | 5,6 | **no** |
| सावित्री | विद्युल्लेखा | sama | मम | `GGGGGG` | 6 | — | **no** |
| हंसमाला | — | sama | सरग | `LLGGLGG` | 7 | — | **no** |
| हरनर्तक | मत्तकोकिल | sama | रसजजभर | `GLGLLGLGLLGLGLLGLG` | 18 | — | **no** |
| हलमुखी | — | sama | रनस | `GLGLLLLLG` | 9 | — | **no** |
| सोमराजी | — | sama | यय | `LGGLGG` | 6 | — | **no** |
| समृद्धि | — | sama | रग | `GLGG` | 4 | — | **no** |
| प्रीति | — | sama | रगग | `GLGGG` | 5 | — | **no** |
| बृहती | — | sama | ननन | `LLLLLLLLL` | 9 | — | **no** |
| भद्रक | — | sama | भरनरनरनग | `GLLGLGLLLGLGLLLGLGLLLG` | 22 | 4,6,6,6 | **no** |
| कुसुममालिका | शुद्धकामदा | sama | नररलग | `LLLGLGGLGLG` | 11 | — | **no** |
| हंसी २ | — | sama | मभनग | `GGGGLLLLLG` | 10 | — | **no** |
| दीपकमाला | — | sama | भमजग | `GLLGGGLGLG` | 10 | — | **no** |
| उपस्थिता | — | sama | तजजग | `GGLLGLLGLG` | 10 | — | **no** |
| भद्रिका १ | — | sama | रनर | `GLGLLLGLG` | 9 | — | **no** |
| मदनललिता | — | sama | मभनमनग | `GGGGLLLLLGGGLLLG` | 16 | 4,6,6 | **no** |
| प्रवरललित | — | sama | यमनसरग | `LGGGGGLLLLLGGLGG` | 16 | — | **no** |
| चकिता | — | sama | भसमतनग | `GLLLLGGGGGGLLLLG` | 16 | 8,8 | **no** |
| निशिपालक | — | sama | भजसनर | `GLLLGLLLGLLLGLG` | 15 | — | **no** |
| नलिनी | — | sama | ससससस | `LLGLLGLLGLLGLLG` | 15 | — | **no** |
| मानसहंस | — | sama | सजजभर | `LLGLGLLGLGLLGLG` | 15 | — | **no** |
| ऋषभ | — | sama | सजससय | `LLGLGLLLGLLGLGG` | 15 | — | **no** |
| उपमालिनी | — | sama | ननतभर | `LLLLLLGGLGLLGLG` | 15 | 8,7 | **no** |
| चन्द्रकान्ता | — | sama | ररमसय | `GLGGLGGGGLLGLGG` | 15 | 7,8 | **no** |
| एला | — | sama | सजननय | `LLGLGLLLLLLLLGG` | 15 | 5,10 | **no** |
| समानिका | — | sama | रजगल | `GLGLGLGL` | 8 | — | **no** |
| नाराचिका | — | sama | तरलग | `GGLGLGLG` | 8 | — | **no** |
| मोटनक | — | sama | तजजलग | `GGLLGLLGLLG` | 11 | — | **no** |
| उपचित्र | — | sama | सससलग | `LLGLLGLLGLG` | 11 | — | **no** |
| कुपुरुषजनिता | — | sama | ननरगग | `LLLLLLGLGGG` | 11 | — | **no** |
| अनवसिता | — | sama | नयभगग | `LLLLGGGLLGG` | 11 | — | **no** |
| विध्वङ्कमाला | — | sama | तततगग | `GGLGGLGGLGG` | 11 | — | **no** |
| सान्द्रपद | — | sama | भतनगल | `GLLGGLLLLGL` | 11 | — | **no** |
| प्रियंवदा | — | sama | नभजर | `LLLGLLLGLGLG` | 12 | — | **no** |
| ललना | — | sama | भमसस | `GLLGGGLLGLLG` | 12 | 5,7 | **no** |
| ललित | — | sama | ननमर | `LLLLLLGGGGLG` | 12 | — | **no** |
| द्रुतपद | — | sama | नभनय | `LLLGLLLLLLGG` | 12 | — | **no** |
| विद्याधार | — | sama | मममम | `GGGGGGGGGGGG` | 12 | — | **no** |
| सारङ्ग | — | sama | तततत | `GGLGGLGGLGGL` | 12 | — | **no** |
| मोटक | — | sama | भभभभ | `GLLGLLGLLGLL` | 12 | — | **no** |
| तरलनयन | — | sama | नननन | `LLLLLLLLLLLL` | 12 | — | **no** |
| चण्डी | — | sama | ननससग | `LLLLLLLLGLLGG` | 13 | — | **no** |
| मृगेन्द्रमुख | — | sama | नजजरग | `LLLLGLLGLGLGG` | 13 | — | **no** |
| मञ्जुहासिनी | — | sama | जतसजग | `LGLGGLLLGLGLG` | 13 | — | **no** |
| कुटजगति | — | sama | नजमतग | `LLLLGLGGGGGLG` | 13 | 7,6 | **no** |
| लोला | — | sama | मसमभगग | `GGGLLGGGGGLLGG` | 14 | 7,7 | **no** |
| नान्दीमुखी | — | sama | ननततगग | `LLLLLLGGLGGLGG` | 14 | 7,7 | **no** |
| नदी २ | — | sama | ननतजगग | `LLLLLLGGLLGLGG` | 14 | 7,7 | **no** |
| इन्दुवदना | वनमयूर | sama | भजसनगग | `GLLLGLLLGLLLGG` | 14 | 9,5 | yes |
| लक्ष्मी | — | sama | मसतभगग | `GGGLLGGGLGLLGG` | 14 | — | **no** |
| सुपवित्र | — | sama | ननननगग | `LLLLLLLLLLLLGG` | 14 | — | **no** |
| कुटिल | — | sama | सभनयगग | `LLGGLLLLLLGGGG` | 14 | 4,10 | **no** |
| कुमारी | — | sama | नजभजगग | `LLLLGLGLLLGLGG` | 14 | 8,6 | **no** |
| सुकेसर | — | sama | नरनरलग | `LLLGLGLLLGLGLG` | 14 | — | **no** |
| चन्द्रौरस | — | sama | मभनयलग | `GGGGLLLLLLGGLG` | 14 | — | **no** |
| चक्रपद | — | sama | भनननलग | `GLLLLLLLLLLLLG` | 14 | — | **no** |
| वासन्ती (श) | — | sama | मतनयगग | `GGGGGLLLLLGGGG` | 14 | — | **no** |
| स्रक् | — | sama | ननननस | `LLLLLLLLLLLLLLG` | 15 | 6,9 | **no** |
| मणिगुणनिकर | — | sama | ननननस | `LLLLLLLLLLLLLLG` | 15 | 8,7 | **no** |
| विपिनतिलक | — | sama | नसनरर | `LLLLLGLLLGLGGLG` | 15 | — | **no** |
| चित्रा | — | sama | मममयय | `GGGGGGGGGLGGLGG` | 15 | — | **no** |
| तरलि | — | sama | भसनजनर | `GLLLLGLLLLGLLLLGLG` | 18 | 11,7 | **no** |
| हंसगति | कविराजविराजित | sama | नजजजजजजलग | `LLLLGLLGLLGLLGLLGLLGLLG` | 23 | 8,6,6,3 | **no** |
| मङ्गलमहश्री | — | sama | भजसनभजसनगग | `GLLLGLLLGLLLGLLLGLLLGLLLGG` | 26 | 9,8,9 | **no** |
| महास्रग्धरा | — | sama | सततनसररग | `LLGGGLGGLLLLLLGGLGGLGG` | 22 | 9,7,6 | **no** |
| लयविभाति | — | sama | नससनसननसनननग | `LLLLLGLLGLLLLLGLLLLLLLLGLLLLLLLLLG` | 34 | 2,9,9,9,5 | **no** |
| लयग्राहि | — | sama | भजसनभजसनभय | `GLLLGLLLGLLLGLLLGLLLGLLLGLLLGG` | 30 | 2,8,8,8,4 | **no** |
| अपरवक्त्र | — | ardhasama | ननरलग/नजजर | `LLLLLLGLGLG / LLLLGLLGLGLG` | 11/12 |  | **no** |
| उपचित्र | — | ardhasama | सससलग/भभभगग | `LLGLLGLLGLG / GLLGLLGLLGG` | 11/11 |  | **no** |
| औपच्छन्दसिक, पुष्पिताग्रा | — | ardhasama | ननरय/नजजरग | `LLLLLLGLGLGG / LLLLGLLGLGLGG` | 12/13 |  | yes |
| वियोगिनी, वैतालीय, सुन्दरी | — | ardhasama | ससजग/सभरलग | `LLGLLGLGLG / LLGGLLGLGLG` | 10/11 |  | yes |
| वेगवती | — | ardhasama | सससग/भभभगग | `LLGLLGLLGG / GLLGLLGLLGG` | 10/11 |  | **no** |
| हरिणप्लुता | — | ardhasama | सससलग/नभभर | `LLGLLGLLGLG / LLLGLLGLLGLG` | 11/12 |  | **no** |
| वसन्तमालिका | — | ardhasama | ससजगग/सभरय | `LLGLLGLGLGG / LLGGLLGLGLGG` | 11/12 |  | yes |
| अनुष्टुभ् | — | ardhasama | ----लगग-/----लगल- | `----LGG- / ----LGL-` | 8/8 |  | **no** |
| उद्गता | — | vishama | सजसल/नसजग/भनजलग/सजसजग | `LLGLGLLLGL / LLLLLGLGLG / GLLLLLLGLLG / LLGLGLLLGLGLG` | 10/10/11/13 |  | **no** |
| अन्यविधोद्गता | — | vishama | सजसल/नसजग/भनभग/सजसजग | `LLGLGLLLGL / LLLLLGLGLG / GLLLLLGLLG / LLGLGLLLGLGLG` | 10/10/10/13 |  | yes |
| सौरभ | — | vishama | सजसल/नसजग/रनभग/सजसजग | `LLGLGLLLGL / LLLLLGLGLG / GLGLLLGLLG / LLGLGLLLGLGLG` | 10/10/10/13 |  | **no** |
| ललित | — | vishama | सजसल/नसजग/ननसस/सजसजग | `LLGLGLLLGL / LLLLLGLGLG / LLLLLLLLGLLG / LLGLGLLLGLGLG` | 10/10/12/13 |  | **no** |
| वक्त्र | — | vishama | मरगग/मरगग/ररगग/मरगग | `GGGGLGGG / GGGGLGGG / GLGGLGGG / GGGGLGGG` | 8/8/8/8 |  | **no** |
| उपजाति (कीर्ति) | — | upajati | जतजगग/ततजगग/ततजगग/ततजगग | `LGLGGLLGLGG / GGLGGLLGLGG / GGLGGLLGLGG / GGLGGLLGLGG` | 11/11/11/11 |  | yes |
| उपजाति (वाणी) | — | upajati | ततजगग/जतजगग/ततजगग/ततजगग | `GGLGGLLGLGG / LGLGGLLGLGG / GGLGGLLGLGG / GGLGGLLGLGG` | 11/11/11/11 |  | yes |
| उपजाति (माला) | — | upajati | जतजगग/जतजगग/ततजगग/ततजगग | `LGLGGLLGLGG / LGLGGLLGLGG / GGLGGLLGLGG / GGLGGLLGLGG` | 11/11/11/11 |  | yes |
| उपजाति (शाला) | — | upajati | ततजगग/ततजगग/जतजगग/ततजगग | `GGLGGLLGLGG / GGLGGLLGLGG / LGLGGLLGLGG / GGLGGLLGLGG` | 11/11/11/11 |  | yes |
| उपजाति (हंसी) | — | upajati | जतजगग/ततजगग/जतजगग/ततजगग | `LGLGGLLGLGG / GGLGGLLGLGG / LGLGGLLGLGG / GGLGGLLGLGG` | 11/11/11/11 |  | yes |
| उपजाति (माया) | — | upajati | जतजगग/जतजगग/जतजगग/ततजगग | `LGLGGLLGLGG / LGLGGLLGLGG / LGLGGLLGLGG / GGLGGLLGLGG` | 11/11/11/11 |  | yes |
| उपजाति (जाया) | — | upajati | ततजगग/जतजगग/जतजगग/ततजगग | `GGLGGLLGLGG / LGLGGLLGLGG / LGLGGLLGLGG / GGLGGLLGLGG` | 11/11/11/11 |  | yes |
| उपजाति (बाला) | — | upajati | ततजगग/ततजगग/ततजगग/जतजगग | `GGLGGLLGLGG / GGLGGLLGLGG / GGLGGLLGLGG / LGLGGLLGLGG` | 11/11/11/11 |  | yes |
| उपजाति (आर्द्रा) | — | upajati | जतजगग/ततजगग/ततजगग/जतजगग | `LGLGGLLGLGG / GGLGGLLGLGG / GGLGGLLGLGG / LGLGGLLGLGG` | 11/11/11/11 |  | yes |
| उपजाति (भद्रा) | — | upajati | ततजगग/जतजगग/ततजगग/जतजगग | `GGLGGLLGLGG / LGLGGLLGLGG / GGLGGLLGLGG / LGLGGLLGLGG` | 11/11/11/11 |  | yes |
| उपजाति (प्रेमा) | — | upajati | जतजगग/जतजगग/ततजगग/जतजगग | `LGLGGLLGLGG / LGLGGLLGLGG / GGLGGLLGLGG / LGLGGLLGLGG` | 11/11/11/11 |  | yes |
| उपजाति (रामा) | — | upajati | ततजगग/ततजगग/जतजगग/जतजगग | `GGLGGLLGLGG / GGLGGLLGLGG / LGLGGLLGLGG / LGLGGLLGLGG` | 11/11/11/11 |  | yes |
| उपजाति (ऋद्धि) | — | upajati | जतजगग/ततजगग/जतजगग/जतजगग | `LGLGGLLGLGG / GGLGGLLGLGG / LGLGGLLGLGG / LGLGGLLGLGG` | 11/11/11/11 |  | yes |
| उपजाति (सिद्धि/बुद्धि) | — | upajati | ततजगग/जतजगग/जतजगग/जतजगग | `GGLGGLLGLGG / LGLGGLLGLGG / LGLGGLLGLGG / LGLGGLLGLGG` | 11/11/11/11 |  | yes |
| उपजाति (वंशस्थ-इन्द्रवंशा १) | — | upajati | ततजर/जतजर/जतजर/जतजर | `GGLGGLLGLGLG / LGLGGLLGLGLG / LGLGGLLGLGLG / LGLGGLLGLGLG` | 12/12/12/12 |  | yes |
| उपजाति (वंशस्थ-इन्द्रवंशा २) | — | upajati | जतजर/ततजर/जतजर/जतजर | `LGLGGLLGLGLG / GGLGGLLGLGLG / LGLGGLLGLGLG / LGLGGLLGLGLG` | 12/12/12/12 |  | yes |
| उपजाति (वंशस्थ-इन्द्रवंशा ३) | — | upajati | ततजर/ततजर/जतजर/जतजर | `GGLGGLLGLGLG / GGLGGLLGLGLG / LGLGGLLGLGLG / LGLGGLLGLGLG` | 12/12/12/12 |  | yes |
| उपजाति (वंशस्थ-इन्द्रवंशा ४) | — | upajati | जतजर/जतजर/ततजर/जतजर | `LGLGGLLGLGLG / LGLGGLLGLGLG / GGLGGLLGLGLG / LGLGGLLGLGLG` | 12/12/12/12 |  | yes |
| उपजाति (वंशस्थ-इन्द्रवंशा ५) | — | upajati | ततजर/जतजर/ततजर/जतजर | `GGLGGLLGLGLG / LGLGGLLGLGLG / GGLGGLLGLGLG / LGLGGLLGLGLG` | 12/12/12/12 |  | **no** |
| उपजाति (वंशस्थ-इन्द्रवंशा ६) | — | upajati | ततजर/ततजर/ततजर/जतजर | `GGLGGLLGLGLG / GGLGGLLGLGLG / GGLGGLLGLGLG / LGLGGLLGLGLG` | 12/12/12/12 |  | yes |
| उपजाति (वंशस्थ-इन्द्रवंशा ७) | — | upajati | जतजर/ततजर/ततजर/जतजर | `LGLGGLLGLGLG / GGLGGLLGLGLG / GGLGGLLGLGLG / LGLGGLLGLGLG` | 12/12/12/12 |  | yes |
| उपजाति (वंशस्थ-इन्द्रवंशा ८) | — | upajati | जतजर/जतजर/जतजर/ततजर | `LGLGGLLGLGLG / LGLGGLLGLGLG / LGLGGLLGLGLG / GGLGGLLGLGLG` | 12/12/12/12 |  | yes |
| उपजाति (वंशस्थ-इन्द्रवंशा ९) | — | upajati | ततजर/जतजर/जतजर/ततजर | `GGLGGLLGLGLG / LGLGGLLGLGLG / LGLGGLLGLGLG / GGLGGLLGLGLG` | 12/12/12/12 |  | yes |
| उपजाति (वंशस्थ-इन्द्रवंशा १०) | — | upajati | जतजर/ततजर/जतजर/ततजर | `LGLGGLLGLGLG / GGLGGLLGLGLG / LGLGGLLGLGLG / GGLGGLLGLGLG` | 12/12/12/12 |  | **no** |
| उपजाति (वंशस्थ-इन्द्रवंशा ११) | — | upajati | ततजर/ततजर/जतजर/ततजर | `GGLGGLLGLGLG / GGLGGLLGLGLG / LGLGGLLGLGLG / GGLGGLLGLGLG` | 12/12/12/12 |  | yes |
| उपजाति (वंशस्थ-इन्द्रवंशा १२) | — | upajati | जतजर/जतजर/ततजर/ततजर | `LGLGGLLGLGLG / LGLGGLLGLGLG / GGLGGLLGLGLG / GGLGGLLGLGLG` | 12/12/12/12 |  | yes |
| उपजाति (वंशस्थ-इन्द्रवंशा १३) | — | upajati | ततजर/जतजर/ततजर/ततजर | `GGLGGLLGLGLG / LGLGGLLGLGLG / GGLGGLLGLGLG / GGLGGLLGLGLG` | 12/12/12/12 |  | yes |
| उपजाति (वंशस्थ-इन्द्रवंशा १४) | — | upajati | जतजर/ततजर/ततजर/ततजर | `LGLGGLLGLGLG / GGLGGLLGLGLG / GGLGGLLGLGLG / GGLGGLLGLGLG` | 12/12/12/12 |  | yes |
| उपजाति (शार्दूलविक्रीडित-स्रग्धरा १) | — | upajati | मसजसततग/मरभनययय/मरभनययय/मरभनययय | `GGGLLGLGLLLGGGLGGLG / GGGGLGGLLLLLLGGLGGLGG / GGGGLGGLLLLLLGGLGGLGG / GGGGLGGLLLLLLGGLGGLGG` | 19/21/21/21 |  | **no** |
| उपजाति (शार्दूलविक्रीडित-स्रग्धरा २) | — | upajati | मरभनययय/मसजसततग/मरभनययय/मरभनययय | `GGGGLGGLLLLLLGGLGGLGG / GGGLLGLGLLLGGGLGGLG / GGGGLGGLLLLLLGGLGGLGG / GGGGLGGLLLLLLGGLGGLGG` | 21/19/21/21 |  | **no** |
| उपजाति (शार्दूलविक्रीडित-स्रग्धरा ३) | — | upajati | मसजसततग/मसजसततग/मरभनययय/मरभनययय | `GGGLLGLGLLLGGGLGGLG / GGGLLGLGLLLGGGLGGLG / GGGGLGGLLLLLLGGLGGLGG / GGGGLGGLLLLLLGGLGGLGG` | 19/19/21/21 |  | **no** |
| उपजाति (शार्दूलविक्रीडित-स्रग्धरा ४) | — | upajati | मरभनययय/मरभनययय/मसजसततग/मरभनययय | `GGGGLGGLLLLLLGGLGGLGG / GGGGLGGLLLLLLGGLGGLGG / GGGLLGLGLLLGGGLGGLG / GGGGLGGLLLLLLGGLGGLGG` | 21/21/19/21 |  | **no** |
| उपजाति (शार्दूलविक्रीडित-स्रग्धरा ५) | — | upajati | मसजसततग/मरभनययय/मसजसततग/मरभनययय | `GGGLLGLGLLLGGGLGGLG / GGGGLGGLLLLLLGGLGGLGG / GGGLLGLGLLLGGGLGGLG / GGGGLGGLLLLLLGGLGGLGG` | 19/21/19/21 |  | **no** |
| उपजाति (शार्दूलविक्रीडित-स्रग्धरा ६) | — | upajati | मसजसततग/मसजसततग/मसजसततग/मरभनययय | `GGGLLGLGLLLGGGLGGLG / GGGLLGLGLLLGGGLGGLG / GGGLLGLGLLLGGGLGGLG / GGGGLGGLLLLLLGGLGGLGG` | 19/19/19/21 |  | **no** |
| उपजाति (शार्दूलविक्रीडित-स्रग्धरा ७) | — | upajati | मरभनययय/मसजसततग/मसजसततग/मरभनययय | `GGGGLGGLLLLLLGGLGGLGG / GGGLLGLGLLLGGGLGGLG / GGGLLGLGLLLGGGLGGLG / GGGGLGGLLLLLLGGLGGLGG` | 21/19/19/21 |  | **no** |
| उपजाति (शार्दूलविक्रीडित-स्रग्धरा ८) | — | upajati | मरभनययय/मरभनययय/मरभनययय/मसजसततग | `GGGGLGGLLLLLLGGLGGLGG / GGGGLGGLLLLLLGGLGGLGG / GGGGLGGLLLLLLGGLGGLGG / GGGLLGLGLLLGGGLGGLG` | 21/21/21/19 |  | **no** |
| उपजाति (शार्दूलविक्रीडित-स्रग्धरा ९) | — | upajati | मसजसततग/मरभनययय/मरभनययय/मसजसततग | `GGGLLGLGLLLGGGLGGLG / GGGGLGGLLLLLLGGLGGLGG / GGGGLGGLLLLLLGGLGGLGG / GGGLLGLGLLLGGGLGGLG` | 19/21/21/19 |  | **no** |
| उपजाति (शार्दूलविक्रीडित-स्रग्धरा १०) | — | upajati | मरभनययय/मसजसततग/मरभनययय/मसजसततग | `GGGGLGGLLLLLLGGLGGLGG / GGGLLGLGLLLGGGLGGLG / GGGGLGGLLLLLLGGLGGLGG / GGGLLGLGLLLGGGLGGLG` | 21/19/21/19 |  | **no** |
| उपजाति (शार्दूलविक्रीडित-स्रग्धरा ११) | — | upajati | मसजसततग/मसजसततग/मरभनययय/मसजसततग | `GGGLLGLGLLLGGGLGGLG / GGGLLGLGLLLGGGLGGLG / GGGGLGGLLLLLLGGLGGLGG / GGGLLGLGLLLGGGLGGLG` | 19/19/21/19 |  | **no** |
| उपजाति (शार्दूलविक्रीडित-स्रग्धरा १२) | — | upajati | मरभनययय/मरभनययय/मसजसततग/मसजसततग | `GGGGLGGLLLLLLGGLGGLGG / GGGGLGGLLLLLLGGLGGLGG / GGGLLGLGLLLGGGLGGLG / GGGLLGLGLLLGGGLGGLG` | 21/21/19/19 |  | **no** |
| उपजाति (शार्दूलविक्रीडित-स्रग्धरा १३) | — | upajati | मसजसततग/मरभनययय/मसजसततग/मसजसततग | `GGGLLGLGLLLGGGLGGLG / GGGGLGGLLLLLLGGLGGLGG / GGGLLGLGLLLGGGLGGLG / GGGLLGLGLLLGGGLGGLG` | 19/21/19/19 |  | **no** |
| उपजाति (शार्दूलविक्रीडित-स्रग्धरा १४) | — | upajati | मरभनययय/मसजसततग/मसजसततग/मसजसततग | `GGGGLGGLLLLLLGGLGGLGG / GGGLLGLGLLLGGGLGGLG / GGGLLGLGLLLGGGLGGLG / GGGLLGLGLLLGGGLGGLG` | 21/19/19/19 |  | **no** |


Totals: 245 vṛttas; 59 already have a verified example verse; **186 still need one** (Part A).

## 2. Part A — one authentic example verse for every vṛtta without one

For each vṛtta in §1 marked **no**, give one real verse (four pādas) actually composed in that metre, with its
source. Do not compose verses. A lakṣaṇa verse from Vṛttaratnākara / Chandomañjarī / Śrutabodha that is
itself written in the metre it defines is acceptable and should be marked `"kind": "lakshana_verse"`.
If you know no genuine verse, return `"example": null` — a null is useful, an invented verse is harmful.

Item shape:
```
{"vrutta": "<id from §1, exactly>", "example": {"text": "pāda1\npāda2\npāda3\npāda4", "source": "work chapter.verse",
  "kind": "verse" | "lakshana_verse", "scan": ["L/G of pāda1", "…", "…", "…"]}, "confidence": 0.0-1.0}
```
Vṛttas that need an example (do them in this order, `40` per batch):

* batch 1: अतिरेखा (15), अतिशायिनी (17), अद्रितनया (23), अपराजिता (14), अपवाह (26), असम्बाधा (14), उज्ज्वला (12), उपस्थित (11), ऋषभगजविलसित (16), कलहंस (13), कुमारललिता (7), कुसुमविचित्रा (12), कुसुमितलतावेल्लिता (18), क्षमा (13), गजगति (8), गीतिका (20), चन्द्रलेखा (15), चन्द्रवर्त्म (12), चित्र (16), चित्रपदा (8), चित्रलेखा (18), जलधरमाला (12), जलोद्धतगति (12), तन्वी (24), तामरस (12), तारका (18), तूणक (15), त्वरितगति (10), नन्दन (18), नर्दटक (17), नवमालिनी (12), पञ्चकावली (21), पणव (10), पथ्या (14), पुट (12), प्रभा (12), प्रमदा (14), प्रमाणिका (8), प्रहरणकलिका (14), भद्रिका २ (11)
* batch 2: भुजगशिशुभृता (9), भुजङ्गविजृम्भित (26), भुजङ्गसङ्गता (9), भ्रमरविलसित (11), मणिमध्य (9), मत्तमयूर (13), मत्तविलासिनी (21), मत्ता (10), मत्ताक्रीडा (23), मत्तेभविक्रीडित (20), मदलेखा (7), मदिरा (22), मधुमती (7), मध्यक्षामा (14), मनोरमा (10), मन्दारमाला (22), मयूरसारिणी (10), माणवक (8), मालती (12), मेघविस्फूर्जिता (19), रुक्मवती (10), ललिता (12), कामक्रीडा (15), वंशपत्रपतित (17), वाणिनी (16), वासन्ती (14), विद्युन्माला (8), वृत्ता (11), वैश्वदेवी (12), शशिकला (15), शार्दूलललित (18), शुद्धविराट् (10), श्येनी (11), सुमधुरा (19), सुमन्दारमाला (23), सुमुखी (11), सुरसा (19), सुवदना (20), हंसरुत (8), हंसी १ (22)
* batch 3: नदी १ (6), पङ्क्ति (5), कन्या (4), सती (4), तनुमध्या (6), रमणी (6), लासिनी (4), वसुमती (6), मणिराग (10), मन्दा (5), प्रिया (5), मुकुल (6), मेघवितान (10), मौक्तिकदाम (12), शशिवदना (6), मौक्तिकमाला (11), सावित्री (6), हंसमाला (7), हरनर्तक (18), हलमुखी (9), सोमराजी (6), समृद्धि (4), प्रीति (5), बृहती (9), भद्रक (22), कुसुममालिका (11), हंसी २ (10), दीपकमाला (10), उपस्थिता (10), भद्रिका १ (9), मदनललिता (16), प्रवरललित (16), चकिता (16), निशिपालक (15), नलिनी (15), मानसहंस (15), ऋषभ (15), उपमालिनी (15), चन्द्रकान्ता (15), एला (15)
* batch 4: समानिका (8), नाराचिका (8), मोटनक (11), उपचित्र (11), कुपुरुषजनिता (11), अनवसिता (11), विध्वङ्कमाला (11), सान्द्रपद (11), प्रियंवदा (12), ललना (12), ललित (12), द्रुतपद (12), विद्याधार (12), सारङ्ग (12), मोटक (12), तरलनयन (12), चण्डी (13), मृगेन्द्रमुख (13), मञ्जुहासिनी (13), कुटजगति (13), लोला (14), नान्दीमुखी (14), नदी २ (14), लक्ष्मी (14), सुपवित्र (14), कुटिल (14), कुमारी (14), सुकेसर (14), चन्द्रौरस (14), चक्रपद (14), वासन्ती (श) (14), स्रक् (15), मणिगुणनिकर (15), विपिनतिलक (15), चित्रा (15), तरलि (18), हंसगति (23), मङ्गलमहश्री (26), महास्रग्धरा (22), लयविभाति (34)
* batch 5: लयग्राहि (30), अपरवक्त्र (11/12), उपचित्र (11/11), वेगवती (10/11), हरिणप्लुता (11/12), अनुष्टुभ् (8/8), उद्गता (10/10/11/13), सौरभ (10/10/10/13), ललित (10/10/12/13), वक्त्र (8/8/8/8), उपजाति (वंशस्थ-इन्द्रवंशा ५) (12/12/12/12), उपजाति (वंशस्थ-इन्द्रवंशा १०) (12/12/12/12), उपजाति (शार्दूलविक्रीडित-स्रग्धरा १) (19/21/21/21), उपजाति (शार्दूलविक्रीडित-स्रग्धरा २) (21/19/21/21), उपजाति (शार्दूलविक्रीडित-स्रग्धरा ३) (19/19/21/21), उपजाति (शार्दूलविक्रीडित-स्रग्धरा ४) (21/21/19/21), उपजाति (शार्दूलविक्रीडित-स्रग्धरा ५) (19/21/19/21), उपजाति (शार्दूलविक्रीडित-स्रग्धरा ६) (19/19/19/21), उपजाति (शार्दूलविक्रीडित-स्रग्धरा ७) (21/19/19/21), उपजाति (शार्दूलविक्रीडित-स्रग्धरा ८) (21/21/21/19), उपजाति (शार्दूलविक्रीडित-स्रग्धरा ९) (19/21/21/19), उपजाति (शार्दूलविक्रीडित-स्रग्धरा १०) (21/19/21/19), उपजाति (शार्दूलविक्रीडित-स्रग्धरा ११) (19/19/21/19), उपजाति (शार्दूलविक्रीडित-स्रग्धरा १२) (21/21/19/19), उपजाति (शार्दूलविक्रीडित-स्रग्धरा १३) (19/21/19/19), उपजाति (शार्दूलविक्रीडित-स्रग्धरा १४) (21/19/19/19)

## 3. Part B — corrections to the table itself

Check §1 against Vṛttaratnākara (Kedārabhaṭṭa), Chandomañjarī (Gaṅgādāsa), Śrutabodha and Piṅgala's
Chandaḥsūtra with commentary. Report only real disagreements (wrong lakṣaṇa, wrong akṣara count, wrong or
missing yati, wrong or missing name, two names that are really one metre or one name that covers two).
Specific questions we already have:

1. The 14 indravajrā/upendravajrā upajāti names. Our table follows the prastāra order (first pāda changes
   fastest, I before U): 2 UIII कीर्ति, 3 IUII वाणी, 4 UUII माला, 5 IIUI शाला, 6 UIUI हंसी, 7 IUUI जाया,
   8 UUUI माया, 9 IIIU बाला, 10 UIIU आर्द्रा, 11 IUIU भद्रा, 12 UUIU प्रेमा, 13 IIUU रामा, 14 UIUU ऋद्धि,
   15 IUUU बुद्धि. The source table had ऋद्धि duplicated as IUII; we set it to UIUU by elimination.
   Confirm each name↔pattern from the Vṛttaratnākara commentary (tālavyādi mnemonic), especially
   ऋद्धि, and whether जाया/माया are the right way round.
2. Yati positions whose sum is not the pāda length: ऋषभगजविलसित and मणिमाला. Give the correct yati.
3. Any sama vṛtta in §1 whose L/G string you know to be wrong.

Item shape:
```
{"vrutta": "<id>", "field": "lakshana" | "yati" | "name" | "akshara_sankhya" | "merge" | "split",
 "current": "<what §1 says>", "proposed": "<correct value>", "authority": "text chapter.verse", "note": "", "confidence": 0.0-1.0}
```

## 4. Part C — verdicts on verses the engine could not name

387 verses from our corpus (Bhagavad Gītā, Sumadhva Vijaya, Rāghavendra Vijaya, Tīrthaprabandha,
Dvādaśa Stotra, Viṣṇu Sahasranāma, …) that the engine returns as अज्ञातम्, each with our own L/G scan and
pāda syllable counts. `reason` is the engine's guess at why. For each, decide:

* `"verdict": "metre"` — the verse is metrically fine and the metre is X (give `chandas`, and `scan` if our
  scan is wrong); include metres missing from §1 (then also add a Part D item);
* `"verdict": "text_defect"` — a typo / missing or extra akṣara / wrong line split; give `corrected_text`
  (full verse, four pādas) and `chandas`;
* `"verdict": "matra"` — an āryā-family or other mātrā metre (give `chandas` and mātrā per pāda);
* `"verdict": "prose"` — not a verse (colophon, gadya, mantra);
* `"verdict": "unsure"`.

Item shape:
```
{"id": "<id below>", "verdict": "metre" | "text_defect" | "matra" | "prose" | "unsure", "chandas": "<name or null>",
 "corrected_text": "<full verse or null>", "scan": ["…"] | null, "note": "<one line>", "confidence": 0.0-1.0}
```


### Part C batch 1 (items 1–40)

* `gita:2.5` (Bhagavad Gītā) — गुरूनहत्वा हि महानुभावान् / श्रेयो भोक्तुं भैक्ष्यमपीह लोके / हत्वार्थकामांस्तु गुरूनिहैव / भुञ्जीय भोगान् रुधिरप्रदिग्धान्
  scan `LGLGGLLGLGG|GGGGGLLGLGG|GGLGGLLGLGL|GGLGGLLGLGG` syllables [11, 11, 11, 11]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: इन्द्रवज्रा (1 भेदौ), विध्वङ्कमाला (2 भेदौ)
* `gita:2.6` (Bhagavad Gītā) — न चैतद्विद्मः कतरन्नो गरीयो / यद्वा जयेम यदि वा नो जयेयुः / यानेव हत्वा न जिजीविषाम / स्तेऽवस्थिताः प्रमुखे धार्तराष्ट्राः
  scan `LGGGGLLGGLGG|GGLGLLLGGLGG|GGLGGLLGLGL|GGLGLLGGLGG` syllables [12, 12, 11, 11]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose; nearest: भुजङ्गप्रयात (2 भेदौ), वैश्वदेवी (2 भेदौ)
* `gita:2.7` (Bhagavad Gītā) — कार्पण्यदोषोपहतस्वभावः / पृच्छामि त्वां धर्मसंमूढचेताः / यच्छ्रेयः स्यान्निश्िचतं ब्रूहि तन्मे / शिष्यस्तेऽहं शाधि मां त्वां प्रपन्नम्
  scan `GGLGGLLGLGG|GGGGGLGGLGG|GGGGGLGGLGG|GGGGGLGGLGG` syllables [11, 11, 11, 11]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: उपेन्द्रवज्रा (1 भेदौ), विध्वङ्कमाला (1 भेदौ), शालिनी (2 भेदौ)
* `gita:2.20` (Bhagavad Gītā) — न जायते म्रियते वा कदाचि / न्नायं भूत्वा भविता वा न भूयः / अजो नित्यः शाश्वतोऽयं पुराणो / न हन्यते हन्यमाने शरीरे
  scan `LGLGLLGGLGL|GGGGLLGGLGG|LGGGGLGGLGG|LGLGGLGGLGG` syllables [11, 11, 11, 11]; equal pādas of 11 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `gita:2.29` (Bhagavad Gītā) — आश्चर्यवत्पश्यति कश्चिदेन / माश्चर्यवद्वदति तथैव चान्यः / आश्चर्यवच्चैनमन्यः श्रृणोति / श्रुत्वाप्येनं वेद न चैव कश्चित्
  scan `GGLGGLLGLGL|GGLGLLLLGLGG|GGLGGLGGLGL|GGGGGLLGLGG` syllables [11, 12, 11, 11]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose; nearest: इन्द्रवज्रा (1 भेदौ), उपेन्द्रवज्रा (2 भेदौ), विध्वङ्कमाला (2 भेदौ)
* `gita:2.46` (Bhagavad Gītā) — यावानर्थ उदपाने सर्वतः संप्लुतोदके / तावान्सर्वेषु वेदेषु ब्राह्मणस्य विजानतः
  scan `GGGLLLGGGLGGLGLG|GGGGLGGGGLGLLGLG` syllables [16, 16]; equal pādas of 16 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `gita:2.70` (Bhagavad Gītā) — आपूर्यमाणमचलप्रतिष्ठं / समुद्रमापः प्रविशन्ति यद्वत् / तद्वत्कामा यं प्रविशन्ति सर्वे / स शान्तिमाप्नोति न कामकामी
  scan `GGLGLLLGLGG|LGLGGLLGLGG|GGGGGLLGLGG|LGLGGLLGLGG` syllables [11, 11, 11, 11]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: इन्द्रवज्रा (1 भेदौ), उपेन्द्रवज्रा (2 भेदौ), वातोर्मी (2 भेदौ)
* `gita:5.8` (Bhagavad Gītā) — नैव किंचित्करोमीति युक्तो मन्येत तत्त्ववित् / पश्यन् श्रृणवन्स्पृशञ्जिघ्रन्नश्नन्गच्छन्स्वपन् श्वसन्
  scan `GLGGLGGLGGGGLGLG|GGLLGLGGGGGGGLGLG` syllables [16, 17]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `gita:8.9` (Bhagavad Gītā) — कविं पुराणमनुशासितार / मणोरणीयांसमनुस्मरेद्यः / सर्वस्य धातारमचिन्त्यरूप / मादित्यवर्णं तमसः परस्तात्
  scan `LGLGLLLGLGL|LGLGGLLGLGG|GGLGGLLGLGL|GGLGGLLGLGG` syllables [11, 11, 11, 11]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: उपेन्द्रवज्रा (2 भेदौ)
* `gita:8.10` (Bhagavad Gītā) — प्रयाणकाले मनसाऽचलेन / भक्त्या युक्तो योगबलेन चैव / भ्रुवोर्मध्ये प्राणमावेश्य सम्यक् / स तं परं पुरुषमुपैति दिव्यम्
  scan `LGLGGLLGLGL|GGGGGLLGLGL|LGGGGLGGLGG|LGLGLLLLGLGG` syllables [11, 11, 11, 12]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose; nearest: उपेन्द्रवज्रा (1 भेदौ), इन्द्रवज्रा (2 भेदौ)
* `gita:8.11` (Bhagavad Gītā) — यदक्षरं वेदविदो वदन्ति / विशन्ति यद्यतयो वीतरागाः / यदिच्छन्तो ब्रह्मचर्यं चरन्ति / तत्ते पदं संग्रहेण प्रवक्ष्ये
  scan `LGLGGLLGLGL|LGLGLLGGLGG|LGGGGLGGLGL|GGLGGLGGLGG` syllables [11, 11, 11, 11]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: उपेन्द्रवज्रा (1 भेदौ), इन्द्रवज्रा (2 भेदौ)
* `gita:9.20` (Bhagavad Gītā) — त्रैविद्या मां सोमपाः पूतपापा / यज्ञैरिष्ट्वा स्वर्गतिं प्रार्थयन्ते / ते पुण्यमासाद्य सुरेन्द्रलोक / मश्नन्ति दिव्यान्दिवि देवभोगान्
  scan `GGGGGLGGLGG|GGGGGLGGLGG|GGLGGLLGLGL|GGLGGLLGLGG` syllables [11, 11, 11, 11]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: वातोर्मी (1 भेदौ), विध्वङ्कमाला (1 भेदौ), इन्द्रवज्रा (2 भेदौ)
* `gita:9.21` (Bhagavad Gītā) — ते तं भुक्त्वा स्वर्गलोकं विशालं / क्षीणे पुण्ये मर्त्यलोकं विशन्ति / एव त्रयीधर्ममनुप्रपन्ना / गतागतं कामकामा लभन्ते
  scan `GGGGGLGGLGG|GGGGGLGGLGL|GGLGGLLGLGG|LGLGGLGGLGG` syllables [11, 11, 11, 11]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: वातोर्मी (1 भेदौ), विध्वङ्कमाला (1 भेदौ), इन्द्रवज्रा (2 भेदौ)
* `gita:11.1` (Bhagavad Gītā) — मदनुग्रहाय परमं गुह्यमध्यात्मसंज्ञितम् / यत्त्वयोक्तं वचस्तेन मोहोऽयं विगतो मम
  scan `LLGLGLLLGGLGGLGLG|GLGGLGGLGGGLLGLL` syllables [17, 16]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `gita:11.16` (Bhagavad Gītā) — अनेकबाहूदरवक्त्रनेत्रं / पश्यामि त्वां सर्वतोऽनन्तरूपम् / नान्तं न मध्यं न पुनस्तवादिं / पश्यामि विश्वेश्वर विश्वरूप
  scan `LGLGGLLGLGG|GGGGGLGGLGG|GGLGGLLGLGG|GGLGGLLGLGL` syllables [11, 11, 11, 11]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: इन्द्रवज्रा (1 भेदौ), विध्वङ्कमाला (2 भेदौ)
* `gita:11.17` (Bhagavad Gītā) — किरीटिनं गदिनं चक्रिणं च / तेजोराशिं सर्वतोदीप्तिमन्तम् / पश्यामि त्वां दुर्निरीक्ष्यं समन्ता / द्दीप्तानलार्कद्युतिमप्रमेयम्
  scan `LGLGLLGGLGL|GGGGGLGGLGG|GGGGGLGGLGG|GGLGGLLGLGG` syllables [11, 11, 11, 11]; equal pādas of 11 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `gita:11.18` (Bhagavad Gītā) — त्वमक्षरं परमं वेदितव्यं / त्वमस्य विश्वस्य परं निधानम् / त्वमव्ययः शाश्वतधर्मगोप्ता / सनातनस्त्वं पुरुषो मतो मे
  scan `LGLGLLGGLGG|LGLGGLLGLGG|LGLGGLLGLGG|LGLGGLLGLGG` syllables [11, 11, 11, 11]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: उपस्थित (2 भेदौ), उपेन्द्रवज्रा (2 भेदौ), वातोर्मी (2 भेदौ)
* `gita:11.19` (Bhagavad Gītā) — अनादिमध्यान्तमनन्तवीर्य / मनन्तबाहुं शशिसूर्यनेत्रम् / पश्यामि त्वां दीप्तहुताशवक्त्रम् / स्वतेजसा विश्वमिदं तपन्तम्
  scan `LGLGGLLGLGL|LGLGGLLGLGG|GGGGGLLGLGG|LGLGGLLGLGG` syllables [11, 11, 11, 11]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: उपेन्द्रवज्रा (1 भेदौ), इन्द्रवज्रा (2 भेदौ)
* `gita:11.20` (Bhagavad Gītā) — द्यावापृथिव्योरिदमन्तरं हि / व्याप्तं त्वयैकेन दिशश्च सर्वाः / दृष्ट्वाऽद्भुतं रूपमुग्रं तवेदं / लोकत्रयं प्रव्यथितं महात्मन्
  scan `GGLGGLLGLGL|GGLGGLLGLGG|GGLGGLGGLGG|GGLGGLLGLGG` syllables [11, 11, 11, 11]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: इन्द्रवज्रा (1 भेदौ), उपेन्द्रवज्रा (2 भेदौ), विध्वङ्कमाला (2 भेदौ)
* `gita:11.21` (Bhagavad Gītā) — अमी हि त्वां सुरसङ्घाः विशन्ति / केचिद्भीताः प्राञ्जलयो गृणन्ति / स्वस्तीत्युक्त्वा महर्षिसिद्धसङ्घाः / स्तुवन्ति त्वां स्तुतिभिः पुष्कलाभिः
  scan `LGGGLLGGLGL|GGGGGLLGLGL|GGGGLGLGLGG|LGGGLLGGLGG` syllables [11, 11, 11, 11]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: वातोर्मी (2 भेदौ)
* `gita:11.22` (Bhagavad Gītā) — रुद्रादित्या वसवो ये च साध्या / विश्वेऽश्िवनौ मरुतश्चोष्मपाश्च / गन्धर्वयक्षासुरसिद्धसङ्घा / वीक्षन्ते त्वां विस्मिताश्चैव सर्वे
  scan `GGGGLLGGLGG|GGLGLLGGLGL|GGLGGLLGLGG|GGGGGLGGLGG` syllables [11, 11, 11, 11]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: शालिनी (1 भेदौ), विध्वङ्कमाला (2 भेदौ)
* `gita:11.23` (Bhagavad Gītā) — रूपं महत्ते बहुवक्त्रनेत्रं / महाबाहो बहुबाहूरुपादम् / बहूदरं बहुदंष्ट्राकरालं / दृष्ट्वा लोकाः प्रव्यथितास्तथाऽहम्
  scan `GGLGGLLGLGG|LGGGLLGGLGG|LGLGLLGGLGG|GGGGGLLGLGG` syllables [11, 11, 11, 11]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: उपेन्द्रवज्रा (1 भेदौ), विध्वङ्कमाला (1 भेदौ), शालिनी (2 भेदौ)
* `gita:11.24` (Bhagavad Gītā) — नभःस्पृशं दीप्तमनेकवर्णं / व्यात्ताननं दीप्तविशालनेत्रम् / दृष्ट्वा हि त्वां प्रव्यथितान्तरात्मा / धृतिं न विन्दामि शमं च विष्णो
  scan `LGLGGLLGLGG|GGLGGLLGLGG|GGGGGLLGLGG|LGLGGLLGLGG` syllables [11, 11, 11, 11]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: इन्द्रवज्रा (1 भेदौ), विध्वङ्कमाला (2 भेदौ)
* `gita:11.26` (Bhagavad Gītā) — अमी च त्वां धृतराष्ट्रस्य पुत्राः / सर्वे सहैवावनिपालसङ्घैः / भीष्मो द्रोणः सूतपुत्रस्तथाऽसौ / सहास्मदीयैरपि योधमुख्यैः
  scan `LGGGLLGGLGG|GGLGGLLGLGG|GGGGGLGGLGG|LGLGGLLGLGG` syllables [11, 11, 11, 11]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: वातोर्मी (1 भेदौ), शालिनी (2 भेदौ)
* `gita:11.27` (Bhagavad Gītā) — वक्त्राणि ते त्वरमाणा विशन्ति / दंष्ट्राकरालानि भयानकानि / केचिद्विलग्ना दशनान्तरेषु / संदृश्यन्ते चूर्णितैरुत्तमाङ्गैः
  scan `GGLGLLGGLGL|GGLGGLLGLGL|GGLGGLLGLGL|GGGGGLGGLGG` syllables [11, 11, 11, 11]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: वातोर्मी (2 भेदौ), विध्वङ्कमाला (2 भेदौ)
* `gita:11.30` (Bhagavad Gītā) — लेलिह्यसे ग्रसमानः समन्ता / ल्लोकान्समग्रान्वदनैर्ज्वलद्भिः / तेजोभिरापूर्य जगत्समग्रं / भासस्तवोग्राः प्रतपन्ति विष्णो
  scan `GGLGLLGGLGG|GGLGGLLGLGG|GGLGGLLGLGG|GGLGGLLGLGG` syllables [11, 11, 11, 11]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: वातोर्मी (1 भेदौ), विध्वङ्कमाला (1 भेदौ), इन्द्रवज्रा (2 भेदौ)
* `gita:11.31` (Bhagavad Gītā) — आख्याहि मे को भवानुग्ररूपो / नमोऽस्तु ते देववर प्रसीद / विज्ञातुमिच्छामि भवन्तमाद्यं / न हि प्रजानामि तव प्रवृत्तिम्
  scan `GGLGGLGGLGG|LGLGGLLGLGL|GGLGGLLGLGG|LGLGGLLGLGG` syllables [11, 11, 11, 11]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: इन्द्रवज्रा (1 भेदौ), शालिनी (1 भेदौ), उपेन्द्रवज्रा (2 भेदौ)
* `gita:11.32` (Bhagavad Gītā) — कालोऽस्मि लोकक्षयकृत्प्रवृद्धो / लोकान्समाहर्तुमिह प्रवृत्तः / ऋतेऽपि त्वां न भविष्यन्ति सर्वे / येऽवस्थिताः प्रत्यनीकेषु योधाः
  scan `GGLGGLLGLGG|GGLGGLLGLGG|LGGGLLGGLGG|GGLGGLGGLGG` syllables [11, 11, 11, 11]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: उपेन्द्रवज्रा (1 भेदौ), विध्वङ्कमाला (1 भेदौ), शालिनी (2 भेदौ)
* `gita:11.33` (Bhagavad Gītā) — तस्मात्त्वमुत्तिष्ठ यशो लभस्व / जित्वा शत्रून् भुङ्क्ष्व राज्यं समृद्धम् / मयैवैते निहताः पूर्वमेव / निमित्तमात्रं भव सव्यसाचिन्
  scan `GGLGGLLGLGL|GGGGGLGGLGG|LGGGLLGGLGL|LGLGGLLGLGG` syllables [11, 11, 11, 11]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: इन्द्रवज्रा (1 भेदौ), उपेन्द्रवज्रा (2 भेदौ), विध्वङ्कमाला (2 भेदौ)
* `gita:11.35` (Bhagavad Gītā) — एतच्छ्रुत्वा वचनं केशवस्य / कृताञ्जलिर्वेपमानः किरीटी / नमस्कृत्वा भूय एवाह कृष्णं / सगद्गदं भीतभीतः प्रणम्य
  scan `GGGGLLGGLGL|LGLGGLGGLGG|LGGGGLGGLGG|LGLGGLGGLGL` syllables [11, 11, 11, 11]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: वातोर्मी (1 भेदौ), शालिनी (2 भेदौ)
* `gita:11.37` (Bhagavad Gītā) — कस्माच्च ते न नमेरन्महात्मन् / गरीयसे ब्रह्मणोऽप्यादिकर्त्रे / अनन्त देवेश जगन्निवास / त्वमक्षरं सदसत्तत्परं यत्
  scan `GGLGLLGGLGG|LGLGGLGGLGG|LGLGGLLGLGL|LGLGLLGGLGG` syllables [11, 11, 11, 11]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: वातोर्मी (1 भेदौ), विध्वङ्कमाला (1 भेदौ), इन्द्रवज्रा (2 भेदौ)
* `gita:11.41` (Bhagavad Gītā) — सखेति मत्वा प्रसभं यदुक्तं / हे कृष्ण हे यादव हे सखेति / अजानता महिमानं तवेदं / मया प्रमादात्प्रणयेन वापि
  scan `LGLGGLLGLGG|GGLGGLLGLGL|LGLGLLGGLGG|LGLGGLLGLGL` syllables [11, 11, 11, 11]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: इन्द्रवज्रा (1 भेदौ), विध्वङ्कमाला (2 भेदौ)
* `gita:11.46` (Bhagavad Gītā) — किरीटिनं गदिनं चक्रहस्त / मिच्छामि त्वां द्रष्टुमहं तथैव / तेनैव रूपेण चतुर्भुजेन / सहस्रबाहो भव विश्वमूर्ते
  scan `LGLGLLGGLGL|GGGGGLLGLGL|GGLGGLLGLGL|LGLGGLLGLGG` syllables [11, 11, 11, 11]; equal pādas of 11 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `gita:11.48` (Bhagavad Gītā) — न वेदयज्ञाध्ययनैर्न दानै / र्न च क्रियाभिर्न तपोभिरुग्रैः / एवंरूपः शक्य अहं नृलोके / द्रष्टुं त्वदन्येन कुरुप्रवीर
  scan `LGLGGLLGLGG|LGLGGLLGLGG|GGGGGLLGLGG|GGLGGLLGLGL` syllables [11, 11, 11, 11]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: इन्द्रवज्रा (1 भेदौ), विध्वङ्कमाला (2 भेदौ)
* `gita:11.49` (Bhagavad Gītā) — मा ते व्यथा मा च विमूढभावो / दृष्ट्वा रूपं घोरमीदृङ्ममेदम् / व्यपेतभीः प्रीतमनाः पुनस्त्वं / तदेव मे रूपमिदं प्रपश्य
  scan `GGLGGLLGLGG|GGGGGLGGLGG|LGLGGLLGLGG|LGLGGLLGLGL` syllables [11, 11, 11, 11]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: उपेन्द्रवज्रा (1 भेदौ), विध्वङ्कमाला (1 भेदौ), शालिनी (2 भेदौ)
* `gita:11.50` (Bhagavad Gītā) — इत्यर्जुनं वासुदेवस्तथोक्त्वा / स्वकं रूपं दर्शयामास भूयः / आश्वासयामास च भीतमेनं / भूत्वा पुनः सौम्यवपुर्महात्मा
  scan `GGLGGLGGLGG|LGGGGLGGLGG|GGLGGLLGLGG|GGLGGLLGLGG` syllables [11, 11, 11, 11]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: इन्द्रवज्रा (1 भेदौ), शालिनी (1 भेदौ), उपेन्द्रवज्रा (2 भेदौ)
* `gita:12.1` (Bhagavad Gītā) — अर्जुन उवाचएवं सततयुक्ता ये भक्तास्त्वां पर्युपासते / येचाप्यक्षरमव्यक्तं तेषां के योगवित्तमाः
  scan `GLLLGLGGLLLGGGGGGGLGLG|GGGLLGGGGGGGLGLG` syllables [22, 16]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `gita:14.21` (Bhagavad Gītā) — अर्जुन उवाचकैर्लिंगैस्त्रीन्गुणानेतानतीतो भवति प्रभो / किमाचारः कथं चैतांस्त्रीन्गुणानतिवर्तते
  scan `GLLLGLGGGGLGGGLGGLLGLG|LGGGLGGGGLGLLGLG` syllables [22, 16]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `gita:15.2` (Bhagavad Gītā) — अधश्चोर्ध्वं प्रसृतास्तस्य शाखा गुणप्रवृद्धा विषयप्रवालाः / अधश्च मूलान्यनुसन्ततानि कर्मानुबन्धीनि मनुष्यलोके
  scan `LGGGLLGGLGGLGLGGLLGLGG|LGLGGLLGLGLGGLGGLLGLGG` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `gita:15.3` (Bhagavad Gītā) — न रूपमस्येह तथोपलभ्यते नान्तो न चादिर्न च संप्रतिष्ठा / अश्वत्थमेनं सुविरूढमूल मसङ्गशस्त्रेण दृढेन छित्त्वा
  scan `LGLGGLLGLGLGGGLGGLLGLGG|GGLGGLLGLGLLGLGGLLGLGG` syllables [23, 22]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose

### Part C batch 2 (items 41–80)

* `gita:15.4` (Bhagavad Gītā) — ततः पदं तत्परिमार्गितव्य यस्मिन्गता न निवर्तन्ति भूयः / तमेव चाद्यं पुरुषं प्रपद्ये यतः प्रवृत्तिः प्रसृता पुराणी
  scan `LGLGGLLGLGLGGLGLLGGLGG|LGLGGLLGLGGLGLGGLLGLGG` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `gita:17.1` (Bhagavad Gītā) — अर्जुन उवाचये शास्त्रविधिमुत्सृज्य यजन्ते श्रद्धयाऽन्विताः / तेषां निष्ठा तु का कृष्ण सत्त्वमाहो रजस्तमः
  scan `GLLLGLGGLLLGGLLGGGLGLG|GGGGLGGLGLGGLGLG` syllables [22, 16]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `gita:17.23` (Bhagavad Gītā) — तत्सदिति निर्देशो ब्रह्मणस्त्रिविधः स्मृतः / ब्राह्मणास्तेन वेदाश्च यज्ञाश्च विहिताः पुरा
  scan `GLLLGGGGLGLLGLG|GLGGLGGLGGLLLGLG` syllables [15, 16]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `gita:17.25` (Bhagavad Gītā) — तदित्यनभिसन्धाय फलं यज्ञतपःक्रियाः / दानक्रियाश्च विविधाः क्रियन्ते मोक्षकाङ्क्षि
  scan `LGLLLGGLLGGLLGLG|GGLGLLLGLGGGLGL` syllables [16, 15]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `gita:18.73` (Bhagavad Gītā) — अर्जुन उवाचनष्टो मोहः स्मृतिर्लब्धा त्वत्प्रसादान्मयाच्युत / स्थितोऽस्मि गतसन्देहः करिष्ये वचनं तव
  scan `GLLLGLGGGGLGGGGLGGLGLL|LGLLLGGGLGGLLGLL` syllables [22, 16]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `gita:18.74` (Bhagavad Gītā) — सञ्जय उवाचइत्यहं वासुदेवस्य पार्थस्य च महात्मनः / संवादमिममश्रौषमद्भुतं रोमहर्षणम्
  scan `GLLLGLGLGGLGGLGGLLLGLG|GGLLLGGLGLGGLGLG` syllables [22, 16]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_1:10` (Sumadhva Vijaya) — ये-ये गुणा नाम जगत्-प्रसिद्धा यं तेषु तेषु स्म निदर्शयन्ति / साक्षान्महा-भागवत-प्रबईं श्रीमन्तमेनं हनुमन्तमाहुः
  scan `GGLGGLLGLGGGGLGGLLGLGL|GGLGGLLGLLGGGLGGLLGLGG` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `sumadhva_vijaya:sarga_1:17` (Sumadhva Vijaya) — निबद्धय सेतुं रघुवंश-केतु- भ्रू-भङ्ग-सम्भ्रान्त-पयोधि-मद्ध्ये / मुष्टि-प्रहारं दशकाय सीता- सन्तर्जनाग्र्योत्तरमेषकोऽदात्
  scan `LGLLGGLLGLGGGGLGGLLGLGG|GGLGGLLGLGGGGLGGLLGLGG` syllables [23, 22]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_1:36` (Sumadhva Vijaya) — महा-गदं चण्ड-रणं पृथिव्यां बार्हद्रथं मनु निरस्य वीरः / राजानमत्युज्ज्वल-राज-सूयं चकार गोविन्द-सुरेन्द्रजाभ्याम्
  scan `LGLGGLLGLGGGGLGLLLGLGG|GGLGGLLGLGGLGLGGLLGLGG` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `sumadhva_vijaya:sarga_1:41` (Sumadhva Vijaya) — विजयेन युक्तो स कृष्ण-वर्मा मुहुर्महा-हेति-धरोऽप्रधृष्यः / भीष्म-द्विजाद्यैरति-भीषणाभं विपक्ष-कक्षं क्षपयन् विरेजे
  scan `LLGLGGLGLGGLGLGGLLGLGG|GGLGGLLGLGGLGLGGLLGLGG` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `sumadhva_vijaya:sarga_1:51` (Sumadhva Vijaya) — असत्-पदेऽसन् सदसद्-विविक्तं मायाख्यया संवृतिमभ्यधत्त / ब्रह्माप्यखण्डं बत शून्य-सिद्धयै प्रच्छन्न-बौद्धोऽयमतः प्रसिद्धः
  scan `LGLGGLLGLGGGGLGGLLGLGL|GGLGGLLGLGLGGGLGGLLGLGG` syllables [22, 23]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_2:15` (Sumadhva Vijaya) — गोविन्द-सुन्दर-कथा-सुधया स नृणाम् आनन्दयन्न किल केवलमिन्द्रियाणि / किन्तु प्रभो रजत-पीठ-पुरे पदाब्जं श्री-वल्लभस्य भजतामपि दैवतानाम्
  scan `GGLGLLLGLLGLLGGGLGLLLGLLGLGL|GGLGLLLGLLGLGGGGLGLLLGLLGLGG` syllables [28, 28]; equal pādas of 28 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `sumadhva_vijaya:sarga_2:16` (Sumadhva Vijaya) — इत्थं हरेर्गुण-कथा-सुधया सु-तृप्तो नैर्गुण्य-वादिषु जनेष्वपि साग्रहेषु / तत्वे स काल-चलधीरति-संशयालु- र्धीमान् धिया श्रवण-शोधितया प्रदद्धयौ
  scan `GGLGLLLGLLGLGGGGLGLLLGLLGLGL|GGLGLLLGLLGLGGGGLGLLLGLLGLGLG` syllables [28, 29]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_2:43` (Sumadhva Vijaya) — देवादि-सद्भिरनुपालितयाऽऽदरेण देव्याऽऽत्मनेव विलसत्-पदया नितान्तम् / अव्यक्तया प्रथमतो वदनेऽस्य वाण्या शालीनयेव भुवनार्चितया विजहे
  scan `GGLGLLLGLLGLGLGGLGLLLGLLGLGG|GGLGLLLGLLGLGGGGLGLLLGLLGLLG` syllables [28, 28]; equal pādas of 28 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `sumadhva_vijaya:sarga_3:10` (Sumadhva Vijaya) — विरह-दून-तयोगमनोन्मुखं न्यरुणदश्रु पुरा स ययोर्दृशोः / अथ तयोः प्रमदोत्थितमप्यदः प्रति-निरुद्धय गिरं गुरुरब्रवीत्
  scan `LLLGLLGLLGLGLLLGLLGLLGLG|LLLGLLGLLGLGLLLGLLLGLLGLG` syllables [24, 25]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_3:25` (Sumadhva Vijaya) — अथ कथं कथयेति तदा जने गदितवत्युचितार्थमुदाहरन् / स समलाळ्यत विस्मयिभिन्नैरै- रपि सुरैर्विजयाङ्कुर-पूजकैः
  scan `LLLGLLGLLGLGLLLGLLGLLGLG|LLLGLLGLLGGGLLLGLLGLLGLG` syllables [24, 24]; equal pādas of 24 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `sumadhva_vijaya:sarga_3:41` (Sumadhva Vijaya) — गिरिश-गुर्वमरेन्द्र-मुखैश्च य- च्चरणरेणुरधारि सुरेश्वरैः / क्षिति-सुराङ्गयभि-वन्दन-पूर्वकं स वि-दधेऽद्ध्ययनं छल-मानुषः
  scan `LLLGLLGLLGLGLLLGLLGLLGLG|LLLGLLLGLLGLGLLLGLLGLLGLG` syllables [24, 25]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_4:1` (Sumadhva Vijaya) — अथैष सल्लोक-दया-सुधाईया सदागम-स्तेन-निरास-कामया / रमा-वरावास-भुवा विशारदो विशालयाऽचिन्तयदात्मनो धिया
  scan `LGLGGLLGLGGGLGLGGLLGLGLG|LGLGGLLGLGLGLGLGGLLGLGLG` syllables [24, 24]; equal pādas of 24 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `sumadhva_vijaya:sarga_4:8` (Sumadhva Vijaya) — अभूत् कु-शास्त्राभ्यसनं न पातकं क्रमागताद् वि-प्रतिसारतो यतेः / यथा कु-शस्त्राद्धयसनं मुर-द्विषः पदाम्बुजे व्याध-वरस्य गर्हितम्
  scan `LGLGGLLGLGLGLGLGGLLGLGLG|LGLGGLLLGLGLGLGLGGLLGLGLG` syllables [24, 25]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_4:16` (Sumadhva Vijaya) — वराश्रमस्ते जरतोरनाथयो- जीवतोः स्यादयि नन्दनाऽवयोः / स-याचनं वाक्यमुदीर्य्य ताविदं परीत्य पुत्राय नतिं वितेनतुः
  scan `LGLGGLLGLGLGGLGGLLGLGLG|LGLGGLLGLGLGLGLGGLLGLGLG` syllables [23, 24]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_4:17` (Sumadhva Vijaya) — नतिर्न शुश्रूषु-जनाय शस्यते नतं भवद्-भयां स्फुटमत्र साम्प्रतम् / अहो विधात्रा स्वयमेव दापिता तदभ्यनुज्ञेति जगाद स प्रभुः
  scan `LGLGGLLGLGLGLGLGLGLLGLGLG|LGLGGLLGLGLGLGLGGLLGLGLG` syllables [25, 24]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_4:21` (Sumadhva Vijaya) — क्षणेन कौपीन-धरो निजं पटं विदार्य्य हे तात कुरुष्व साहसम् / प्रभुरब्रवीत् पुनः शुभान्तरायं न भवांश्चरेदिति
  scan `LGLGGLLGLGLGLGLGGLLGLGLG|LLGLGLGLGLGGLLGLGLL` syllables [24, 19]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_4:22` (Sumadhva Vijaya) — इतीममुक्त्वा न पुत्र पित्रोरवनं विना शुभं वदन्ति सन्तो ननु तौ सुतौ मृतौ / नि-वर्त्तमाने न हि पालकोऽस्ति नौ त्वयीति वक्तारमिमं सुतोऽब्रवीत्
  scan `LGLGGLGLGGLLGLGLGLGLGGLLGLGLG|LGLGGLLGLGLGLGLGGLLGLGLG` syllables [29, 24]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_4:23` (Sumadhva Vijaya) — यदा विरक्तः पुरुषः प्रजायते तदैव सन्यास-विधिः श्रुतौ श्रुतः / न सङ्ग-हीनोऽपि परि-ब्रव्रजामि वाम् अहं तु शुश्रूषुमकल्पयन्निति
  scan `LGLGGLLGLGLGLGLGGLLGLGLG|LGLGGLLGGLGLGLGLGGLLGLGLL` syllables [24, 25]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_4:36` (Sumadhva Vijaya) — वराश्रम-आचार-विशेष-शिक्षणं विधित्सुरस्याऽचरितं निशामयन् / विशेष-शिक्षां स्वयमाप्य धीरधी- र्य्यतीश्वरो विस्मयमायताऽन्तरम्
  scan `LGLLGGLLGLGLGLGLGGLLGLGLG|LGLGGLLGLGLGLGLGGLLGLGLG` syllables [25, 24]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_5:4` (Sumadhva Vijaya) — भिदा सु-साद्धयेत्यनुमानमत्र तैः प्रायुज्यताऽशु प्रति-पक्ष-भीषणम् / अखण्डयद् व्यक्तमखण्ड-धीरिदं स पक्ष-दक्षः फणिनं वि-राडिव
  scan `LGLGLGLLGLGLGGGLGGLLGLGLG|LGLGGLLGLGLGLGLGGLLGLGLL` syllables [25, 24]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_5:21` (Sumadhva Vijaya) — सम्भवत्- अक्लिष्ट-शब्दान्वयमेष सूत्रार्थमुच्चैर्वचनं तदाऽऽददे / मानीकृताम्नाय-युत-स्मृति क्षणा- देष्यत्कथा-ताण्डव-सूत्र-धारकम्
  scan `GLGGGLGGLLGLGGLGGLLGLGLG|GGLGGLLGLGLGGGLGGLLGLGLG` syllables [24, 24]; equal pādas of 24 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `sumadhva_vijaya:sarga_5:22` (Sumadhva Vijaya) — बुभुत्सया मत्सर-वर्जितान् जनान् स-मत्सरान् वा वि-जिगीषयाऽऽगतान् / श्रुत-प्रवीणानति-तार्किकान् मुहु- र्भङ्गत्याऽनया भङ्गमुपानिनाय सः
  scan `LGLGGLLGLGLGLGLGGLLGLGLG|LGLGGLLGLGLGGGGLGGLLGLGLG` syllables [24, 25]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_5:32` (Sumadhva Vijaya) — भिक्षावसाने द्वि-शताधिकैः फलै- प्रभुक्तैः परि-पूरितेऽपि ते / तनूदरे नास्ति गरिष्ठता कथं सुचित्त सत्यं वदताद् भवानिति
  scan `GGLGGLLGLGLGLGGLLGLGLG|LGLGGLLGLGLGLGLGGLLGLGLL` syllables [22, 24]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_5:41` (Sumadhva Vijaya) — स्फिग्-दूषणानि प्रतिपादयत्यलं सम्पूर्ण-सङ्खन्येऽस्य तु लक्ष्म-शास्त्रतः / तद्-दण्ड-सङ्खण्डन-संश्रवं व्यधात् तदक्षमोऽसौ प्रकृतिर्हि साऽसताम्
  scan `GGLGGLLGLGLGGGLGGGLLGLGLG|GGLGGLLGLGLGLGLGGLLGLGLG` syllables [25, 24]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_5:43` (Sumadhva Vijaya) — तमाव्रजन्तं यति-वेष-धारिणं दण्डं प्रकाश्यैष हसन्नभाषत / खण्ड्येत दण्डो यदि चण्ड न त्वया त्वं पण्डकोऽपण्डित वन्द्वय-वागिति
  scan `LGLGGLLGLGLGGGLGGLLGLGLL|GGLGGLLGLGLGGGLGGLLGLLGLL` syllables [24, 25]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_6:1` (Sumadhva Vijaya) — ऐतरेयमथ किश्चन सूक्तं सूचयन् सदसि तत्र गरिष्ठः / श्रोतुमिच्छति सभा भगवद्भयः सूक्त-भावमिति तावदुवाच
  scan `GLGLLLGLLGGGLGLLLGLLGG|GLGLLLGLLGLGGLGLLLGLLGL` syllables [22, 23]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_6:16` (Sumadhva Vijaya) — तत्प्रसङ्ग-बलतोऽखिल-विद्या- पाटवं पृथु-हृदः प्रतिबुद्धय / आनमन् स-बहु-मानममी तं यं नमन्ति किल नाकि-निकायाः
  scan `GLGLLLGLLGGGLGLLLGLLGLL|GLGLLLGLLGGGLGLLLGLLGG` syllables [23, 22]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_6:47` (Sumadhva Vijaya) — नेदृशं स्थलमलं शमल- नास्य तीर्थ-सलिलस्य समं वाः / नास्मदुक्ति-सदृशं हित-रूपं नास्ति विष्णु-सदृशं ननु दैवम्
  scan `GLGLLLGLLLGLGLLLGLLGG|GLGLLLGLLGGGLGLLLGLLGG` syllables [21, 22]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_7:5` (Sumadhva Vijaya) — तमिमं प्रविशन्तमाश्रमं द्वयधिक-त्रिंशदुदार-लक्षणम् / गुण-सार-विदः कुतूहलाद् अवलोक्यर्षय इत्यचिन्तयन्
  scan `LLGLLGLGLGLLLGGLLGLGLG|LLGLLGLGLGLLGGLLGLGLG` syllables [22, 21]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_7:31` (Sumadhva Vijaya) — रुचिरेण वंरैण-चर्मणा रुचि-राज-द्युति-चारु-रोचिषा परमोरु-नितम्ब-सङ्गिना परमाश्चर्य्य-तया विराज्यते
  scan `LLGLGGLGLGLLGGLLGLGLGLLGLLGLGLGLLGGLLGLGLG` syllables [42]; fewer than two pādas — prose, colophon, fragment, or a single line the splitter could not divide
* `sumadhva_vijaya:sarga_7:57` (Sumadhva Vijaya) — आस्यतामित्युदीर्योपविष्टे सत्यवत्याः सुते सत्य-वाचि / नन्दयन् मन्द-हासावलोकै- स्तान् मुनीन्द्रानिहोपाविशत् सः
  scan `GLGGLGGLGGGLGGLGGLGL|GLGGLGGLGGGLGGLGGLGG` syllables [20, 20]; equal pādas of 20 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `sumadhva_vijaya:sarga_8:23` (Sumadhva Vijaya) — सवने विकस्वर-गुण-स्वर-द्विजे स्फुरिते चरन् सकल-गोकुल-प्रियः / इत-काम-तापसरसाईधी-गिरः प्रतिलाळयन्नरमतैष सुन्दरीः
  scan `LLGLGLLLGLGLGLLGLGLLLGLGLG|LLGLGLLLGGGLGLLGLGLLLGLGLG` syllables [26, 26]; equal pādas of 26 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `sumadhva_vijaya:sarga_8:48` (Sumadhva Vijaya) — भवतोरितः सतत-सेवनामृते मम मङ्कुमस्तु भगन्ननुग्रहः / न लभेय वल्लभ-तमेदृशं सुखं जगतां त्रयेऽपि जगदेक-मङ्गलम्
  scan `LLGLGLLLGLGLGLLGLGLLGLGLG|LLGLGLLLGLGLGLLGLGLLLGLGLG` syllables [25, 26]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_9:46` (Sumadhva Vijaya) — विश्व-विस्मय-करः स्व-तेजसा वन्द्यमान-चरणः पुनर्जनैः / चित्र-दिग्-विजय-कीर्तिमान् मोदयन्ननुदिनं निजाः प्रजाः
  scan `GLGLLLGLGLGGLGLLLGLGLG|GLGLLLGLGGLGLLLGLGLG` syllables [22, 20]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose

### Part C batch 3 (items 81–120)

* `sumadhva_vijaya:sarga_9:51` (Sumadhva Vijaya) — ब्रह्म-वेदन-निविष्ट-चेतसां कर्म्म तत्र करणान्तरं भवेत् / ज्ञापयन्निति परात्म-वेदकः कर्म्म धर्म्ममपि साचीकरत्
  scan `GLGLLLGLGLGGLGLLLGLGLG|GLGLLLGLGLGGLGLLLGGLG` syllables [22, 21]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_9:52` (Sumadhva Vijaya) — यानि यानि चरितानि यान्यानीरितानि च मनो-हराण्यहो / तानि तानि च वितान-चेतसो विश्व-विस्मय-कराणि भान्ति हि
  scan `GLGLLLGLGGGLGLLLGLGLG|GLGLLLGLGLGGLGLLLGLGLL` syllables [21, 22]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_10:2` (Sumadhva Vijaya) — दशमति-शिष्यः कश्चि / च्छुभ-जनतायै कुतूहल-नतायै / विविध-सु-वृत्तं वाक्यं / काव्यमिवोचे स-नायक-स्तवकम्
  scan `LLLLGGGL|LLLLGGLGLLLGG|LLLLGGGG|GLLGGLGLGLLG` syllables [8, 13, 8, 12]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_10:9` (Sumadhva Vijaya) — इमान् स्व-स्व-पूर्वाश्रयानात्म-वाक्यात् / स-लीलं दयालुः स मूलाश्रयात्मा / निषेद्धूननादृत्य चानन्यलङ्घयां / तदाऽत्याययत् तां नदीं संसृतिं वा
  scan `LGGLGGLGGLGG|LGGLGGLGGLGG|LGGLGGLGGLGLG|LGGLGGLGGLGG` syllables [12, 12, 13, 12]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose; nearest: वैश्वदेवी (2 भेदौ)
* `sumadhva_vijaya:sarga_10:22` (Sumadhva Vijaya) — क्वचिच्छिला-च्छटा-भ्रमाद् / अमुं स-सङ्घमत्यजन् / अवेक्ष्य दस्यवः पुनः / कुतूहलात् तमानमन्
  scan `LGLGLGLG|LGLGLGLG|LGLGLGLG|LGLGLGLG` syllables [8, 8, 8, 8]; 4×8 syllables, but a pāda breaks the anuṣṭubh rules even allowing na/bha/ma/ra-vipulā: पादे 1 पञ्चम-सप्तमेषु लगल (न पथ्या, न विपुला); पादे 3 पञ्चम-सप्तमेषु लगल (न पथ्या, न विपुला)
* `sumadhva_vijaya:sarga_10:23` (Sumadhva Vijaya) — सत्योच्छेदे सेच्छापातं / व्याघ्राकारं दैत्य-व्याघ्रम् / प्राळेयाद्रेः प्रान्ते प्राज्ञः / पाणेर्लीला-लेशेनाऽस्यत्
  scan `GGGGGGGG|GGGGGGGG|GGGGGGGG|GGGGGGGG` syllables [8, 8, 8, 8]; 4×8 syllables, but a pāda breaks the anuṣṭubh rules even allowing na/bha/ma/ra-vipulā: पादे 2 पञ्चम-सप्तमेषु गगग (अपेक्षितं लगल); पादे 4 पञ्चम-सप्तमेषु गगग (अपेक्षितं लगल)
* `sumadhva_vijaya:sarga_10:24` (Sumadhva Vijaya) — प्राप स नारायणतः / शुद्ध-शिलात्म-प्रतिमाः / यासु स पद्मा-सहितो / दोष्यहितः सन्निहितः
  scan `GLLGGLLG|GLLGGLLG|GLLGGLLG|GLLGGLLG` syllables [8, 8, 8, 8]; 4×8 syllables, but a pāda breaks the anuṣṭubh rules even allowing na/bha/ma/ra-vipulā: पादे 1 द्वितीयतृतीये लघू; पादे 2 द्वितीयतृतीये लघू; पादे 2 पञ्चम-सप्तमेषु गलल (अपेक्षितं लगल); पादे 3 द्वितीयतृतीये लघू; पादे 4 द्वितीयतृतीये लघू; पादे 4 पञ्चम-सप्तमेषु गलल (अपेक्षितं लगल)
* `sumadhva_vijaya:sarga_10:28` (Sumadhva Vijaya) — न वानरेन्द्रस्य विलङ्घिताब्धे / र्नवा नरेन्द्रस्य विहर्तुरस्याम् / इमेऽस्मरंस्तद्-वपुषोऽन्यथाऽस्य / शक्तस्य शङ्कयेत विपत् कथं तैः
  scan `LGLGGLLGLGG|LGLGGLLGLGG|LGLGGLLGLGL|GGLGLGLLGLGG` syllables [11, 11, 11, 12]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose; nearest: इन्द्रवज्रा (1 भेदौ), विध्वङ्कमाला (2 भेदौ)
* `sumadhva_vijaya:sarga_11:9` (Sumadhva Vijaya) — सित-सौध-सन्तति-रुचा स्फुरिता / परितोऽरुणाश्म-गृह-पति-रुचिः / इह मच्छरीर-वलये लसिताम् / अनुयाति मूर्त्तिमसुरासुहृतः
  scan `LLGLGLLLGLLG|LLGLGLLLLLLG|LLGLGLLLGLLG|LLGLGLLLGLLG` syllables [12, 12, 12, 12]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: तोटक (2 भेदौ)
* `sumadhva_vijaya:sarga_11:10` (Sumadhva Vijaya) — शबळा वळीक-घटित-स्फटिक / द्युतिभिर्हरिन्मणि-मयी वळभी / प्रति-भाति यमुना मिळिता / सित-सौर-सैन्धव-पयोभिरिव
  scan `LLGLGLLLGLLL|LLGLGLLLGLLG|LLGLLLGLLG|LLGLGLLLGLLL` syllables [12, 12, 10, 12]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose; nearest: प्रमिताक्षरा (1 भेदौ)
* `sumadhva_vijaya:sarga_11:31` (Sumadhva Vijaya) — हरिणी-दृशां नि-वसनानि बृहत् / सु-नितम्ब-बिम्ब-रुचिरोरु-रुचा / शबळयन्ति मदनस्य जग / ज्जय-वैजयन्त्य इति निश्चिनुमः
  scan `LLGLGLLLGLLG|LLGLGLLLGLLG|LLLGLLLGLLL|LLGLGLLLGLLG` syllables [12, 12, 11, 12]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose; nearest: तोटक (2 भेदौ)
* `sumadhva_vijaya:sarga_11:46` (Sumadhva Vijaya) — प्रमदाति-रेकमुप-यातवता प्रमदा-गणेन चरतोपवने / उप-गीयते स्म मधुरं मधुजिच्चरितं सकान्त-ततिना समम्
  scan `LLGLGLLLGLLGLLGLGLLLGLLG|LLGLGLLLGLLGLLGLGLLLGLG` syllables [24, 23]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_11:74` (Sumadhva Vijaya) — इज्यते यज्ञ-शीलैः स यज्ञः प्राज्ञ-मध्ये परः प्रोच्यतेऽन्यैः / गीयते गेय-कीर्त्तिः सु-गीतैर्विद्ध्यबद्धैः सदाऽऽनन्द-सान्द्रैः
  scan `GLGGLGGLGGGLGGLGGLGG|GLGGLGGLGGGLGGLGGLGG` syllables [20, 20]; equal pādas of 20 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `sumadhva_vijaya:sarga_12:6` (Sumadhva Vijaya) — सत्यं सत्यं व्यावहार्यं विधत्ते / सर्वं मोहे सर्व निर्वाहिणी सा / ज्ञाने जाते दग्ध-वस्त्र-प्रतीतं / पक्के तस्मिंस्तप्त-लोहात्त-वारिवत्
  scan `GGGGGLGGLGG|GGGGGLGGLGG|GGGGGLGGLGG|GGGGGLGGLGLG` syllables [11, 11, 11, 12]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose; nearest: वातोर्मी (1 भेदौ), विध्वङ्कमाला (1 भेदौ), इन्द्रवज्रा (2 भेदौ)
* `sumadhva_vijaya:sarga_12:8` (Sumadhva Vijaya) — भ्रष्टा भाट्टा न प्रभा-कृत्-प्रभाऽभूत् / स्ता माहायानिकाद्याश्च यत्र / दुर्गं माया-वाद-सत्रं दिधक्षो / र्नपेक्ष्या नस्तत्त्व-वादाग्नि-जिह्वा
  scan `GGGGGLGGLGG|GGGGLGGLGL|GGGGGLGGLGG|LGGGGLGGLGG` syllables [11, 10, 11, 11]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose; nearest: वातोर्मी (1 भेदौ), विध्वङ्कमाला (1 भेदौ), इन्द्रवज्रा (2 भेदौ)
* `sumadhva_vijaya:sarga_12:21` (Sumadhva Vijaya) — यद्यप्येवं न ह्युपेक्ष्यो विपक्षः / किन्तु प्राप्तो नाधुनाऽऽक्रन्द-कालः / अप्यद्वन्द्व-स्वात्म-बोध-प्रतीतै / राचार्यैर्यच्छङ्कयते शङ्कराद्यैः
  scan `GGGGGLGGLGG|GGGGGLGGLGG|GGGGGLGGLGG|GGGGGLLGGLGG` syllables [11, 11, 11, 12]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose; nearest: वातोर्मी (1 भेदौ), विध्वङ्कमाला (1 भेदौ), इन्द्रवज्रा (2 भेदौ)
* `sumadhva_vijaya:sarga_12:35` (Sumadhva Vijaya) — काल्पीः क्लृप्तीर्व्यञ्जयंश्छान्दसीश्च / व्यक्तं शाब्दं शास्त्रमुद्भाव्य भूयः / स व्याख्यावुक्त-नैरुक्त-मार्गौ / ज्यायान् ज्योतिर्वेदिनां वेदमित्थम्
  scan `GGGGGLGGLGL|GGGGGLGGLGG|GGGGLGGLGG|GGGGGLGGLGG` syllables [11, 11, 10, 11]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose; nearest: शालिनी (1 भेदौ), वातोर्मी (2 भेदौ), विध्वङ्कमाला (2 भेदौ)
* `sumadhva_vijaya:sarga_12:42` (Sumadhva Vijaya) — कृष्णाभीष्टा शास्त्र-विस्पष्ट-संज्ञा / या स्वीया श्रीः पालिता सद्-द्विजेन / पद्माख्यासत्-सैन्धेवेनाहृतां तां / शुश्रावाग्र्यानन्द-तीर्थाख्य-पार्थः
  scan `GGGGGLGGLGG|GGGGGLGGLGL|GGGGGGGGLGG|GGGGGLGGLGG` syllables [11, 11, 11, 11]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: वातोर्मी (1 भेदौ), विध्वङ्कमाला (1 भेदौ), इन्द्रवज्रा (2 भेदौ)
* `sumadhva_vijaya:sarga_12:44` (Sumadhva Vijaya) — दुष्टात्माऽसौ सौभद्रमेकाकिनं यः / क्षेप्तुं हेतुः सौख्य-दाख्यं बभूव / हर्यंशोऽयं तं न चक्षाम भूयो / तोके सने सूकरं केसरीव
  scan `GGGGGGLGGLGG|GGGGGLGGLGL|GGGGGLGGLGG|GGLGGLGGLGL` syllables [12, 11, 11, 11]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose; nearest: भुजङ्गप्रयात (2 भेदौ), विद्याधार (2 भेदौ)
* `sumadhva_vijaya:sarga_12:52` (Sumadhva Vijaya) — धत्ते रूपाण्यनन्तान्यपि भुवनपतेर्हृदाऽप्येकपक्षो / दक्षः सद्भ्योऽखिलेभ्योऽप्यमृतमिह ददौ केवलं यो न मात्रे / पक्षिश्रेष्ठोऽपरः सन्नमितमतिपदोऽसम्पदे स्यादयं वो / मा दर्पं मायिसर्पा भजत भजत तास्ता गुहा द्राग् द्विजिह्वाः
  scan `GGGGLGGLLLLLLGLGGLGG|GGGGLGGLLLLLLGGLGGLGG|GGGGLGGLLLLLLGGLGGLGG|GGGGLGGLLLLLLGGLGGLGG` syllables [20, 21, 21, 21]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_13:6` (Sumadhva Vijaya) — गमनोत्सव-विस्मितैर्निषेव्यो विविधैर्जानपदैर्ज्जनैरजस्रम् / परिसृत्वर-कीर्त्तिरार्त्ति-मुक्त्यै पुरुषैर्द्दर-भुवश्च गम्यमानः
  scan `LLGLLGLGLGGLLGGLLGLGLGG|LLGLLGLGLGGLLGLLLGLGLGG` syllables [23, 23]; equal pādas of 23 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `sumadhva_vijaya:sarga_14:1` (Sumadhva Vijaya) — परिवृढ-घन-सद्-राज-सिंहोर्ज-शक्त्या त्यजति मलिन-भावं नीरस-त्वान्निकामम् / स्फुटमुदयति तेजस्वयुज्ज्वले मध्व-भानौ सु-जन-जलज-कान्त्यै विश्वमासीन्मनोज्ञम्
  scan `LLLLLLGGLGGLGGLLLLLLGGGLGGLGG|LLLLLLGGLGLGGLGGLLLLLLGGGLGGLGG` syllables [29, 31]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_14:8` (Sumadhva Vijaya) — अति-धवलित-दन्ता दन्त-काष्ठैः प्रशस्तै / रपि युगपदनेके सस्रुस्तत्र व्रतीन्द्राः / गुरुभिरभिहितेष्वाचार-भेदेषु निष्ठां / स्फुटमव-गमयन्तः सौष्ठवात् कर्मणां च
  scan `LLLLLLGGGLGGLGG|LLLLLLGGGGGGLGG|LLLLLLGGGLGGLGG|LLLLLLGGGLGGLGL` syllables [15, 15, 15, 15]; equal pādas of 15 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `sumadhva_vijaya:sarga_14:13` (Sumadhva Vijaya) — अमृतमपि निरीक्ष्याऽस्रावि निर्माल्य-सूने / घृतमिदमिति सद्यो भ्रान्तिमन्तोऽपि शिष्याः / श्रद्दधुरधिक-वाक्यैर्विभ्रमास्तच्च पश्चा / दनुदिनममृतान्नैस्तस्य सेव्यस्य शक्त्या
  scan `LLLLLLGGGLGGLGG|LLLLLLGGGLGGLGG|GLLLLLGGGLGGLGG|LLLLLLGGGLGGLGG` syllables [15, 15, 15, 15]; equal pādas of 15 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `sumadhva_vijaya:sarga_14:22` (Sumadhva Vijaya) — यत-वचसि जनेऽस्मिन्ना-नते सन्निरस्यन् / सिचय-यवनिकां तां सान्द्रय-जीमूत-रक्ताम् / रविरिव रवि-पूज्याङ्घ्रिः समाजान्तरिक्षे / व्यलसदति-शयालुः सन् सहस्र-प्रकाशः
  scan `LLLLLLGGGLGGLGG|LLLLLLGGGLLGGLGG|LLLLLLGGGLGGLGG|LLLLLLGGGLGGLGG` syllables [15, 16, 15, 15]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_14:23` (Sumadhva Vijaya) — त्रिभुवन-वर-तेजो-व्यक्त-वेदार्थ-शुक्ल / त्रियरसतया ये वर्णिता वर्ण-वर्याः / पृथु-मतिरथ तेषामैक्यमापाद्य सम्यक् / प्रवचन-परिशुद्ध्यै स्म प्रणौति प्रवीणः
  scan `LLLLLLGGGLGGLGL|LLLLLGGGLGGLGG|LLLLLLGGGLGGLGG|LLLLLLGGGLGGLGG` syllables [15, 14, 15, 15]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose; nearest: मालिनी (1 भेदौ)
* `sumadhva_vijaya:sarga_14:33` (Sumadhva Vijaya) — अविदित-रस-भेदं शीतळं लघ्वगन्धं / विमलममल-पाणिः पाणिजैरप्रविष्टम् / वदन-पवन-भीत्या पार्श्वतो बिभ्रदयं / कमथ करक-पूर्णं संयमीहाऽनिनाय
  scan `LLLLLLGGGLGGLGG|LLLLLLGGGLGGLGG|LLLLLLGGGLGGLLG|LLLLLLGGGLGGLGL` syllables [15, 15, 15, 15]; equal pādas of 15 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `sumadhva_vijaya:sarga_14:40` (Sumadhva Vijaya) — सहचर-परिक्लृप्ते सूक्ष्म-वस्त्रास्तृतेऽसा / ववि-तनु-रुह-रूपौशीर-वर्म्मे निषण्णः / अरमयदिह नाना-हृद्य-विद्या-विलासैः / कवि-जन-परिवारं मण्डयन् मण्डपाग्र्यम्
  scan `LLLLLGGGGLGGLGG|LLLLLLGGGLGGLGG|LLLLLLGGGLGGLGG|LLLLLLGGGLGGLGG` syllables [15, 15, 15, 15]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: मालिनी (1 भेदौ)
* `sumadhva_vijaya:sarga_14:44` (Sumadhva Vijaya) — ्येत पश्चा / न्ननु गुरव इदानीमुद्यता हि प्रवक्तुम् / न मननमधुना द्रागाव्रजेत्याह्वयत् तान् / श्रुत-परिचय-सक्तान् श्रावकान् श्रावकाग्र्यः
  scan `GLGG|LLLLLLGGGLGGLGG|LLLLLLGGGLGGLGG|LLLLLLGGGLGGLGG` syllables [4, 15, 15, 15]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose; nearest: कन्या (1 भेदौ), सती (2 भेदौ)
* `sumadhva_vijaya:sarga_14:49` (Sumadhva Vijaya) — व्यदधत परिदृष्ट-ज्योतिषः साधु सान्द्रयं / नियममवनि-देवा ज्योतिषोऽप्याऽवलोकात् / विहितमनु-सरन्तो धर्म्म-शास्त्र-प्रवीणाः / सवितरि सवितारं चिन्तयन्तस्त्रिलोक्याः
  scan `LLLLLLGGGLGGLGLG|LLLLLLGGGLGGLGG|LLLLLLGGGLGGLGG|LLLLLLGGGLGGLGG` syllables [16, 15, 15, 15]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_14:51` (Sumadhva Vijaya) — विधुरयमकळङ्कः स्याद् यदि स्यादवश्यं / ननु निज-सहजायाः सुन्दरास्येन्दु / इति सुर-ललनाभिलळितः खेचरीभिः / समधिक-मधुरिम्णा पूर्ण-चन्द्रस्तदैत्
  scan `LLLLLLGGGLGGLGG|LLLLLLGGGLGGL|LLLLLLGLLLGGLGG|LLLLLLGGGLGGLG` syllables [15, 13, 15, 14]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_15:35` (Sumadhva Vijaya) — किञ्चाखण्डेऽत्र वाक्यानि किञ्चिद् विदधते न हि / तान्यभ्यधुरभावं चेज्जाड्यास्तन्न शोभते
  scan `GGGGLGGLGGLLLGLL|GGLLLGGGGGGLGLG` syllables [16, 15]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_15:98` (Sumadhva Vijaya) — प्रेमामृतप्रसन्नास्यस्मिताङ्गापाङ्गपूर्वकम् / श्रीविष्णुतीर्थनामास्मै प्रीतीर्थः प्रदत्तवान्
  scan `GGLGLGGGLGGGLGLG|GGLGLGGGGGGLGLG` syllables [16, 15]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_15:127` (Sumadhva Vijaya) — अनयोः प्रथमे शिष्याश्रमे चाभवन्निह / अनन्त-बोधस्यानेके यतीन्द्रा बहु-देशजाः
  scan `LLGLLGGGLGGLGLL|LGLGGGGGLGGLLGLG` syllables [15, 16]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_16:24` (Sumadhva Vijaya) — इत्याद्यैरपि चरितैरनन्य-साद्ध्यै / स्थेष्ठां बहु-मतिमाप दुर्जनोऽस्मिन् / विद्वेषं व्यधित पुनर्निरस्त-भाग्ये / तस्मिन् दुर्म्मनसि तदेव शोभनं स्यात्
  scan `GGGLLLLGLGLGG|GGLLLLGLGLGG|GGGLLLLGLGLGG|GGGLLLLGLGLGG` syllables [13, 12, 13, 13]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_16:25` (Sumadhva Vijaya) — सम्प्राप्तं सह सह-जेन गण्ड-वाटं / स्वोजस्सम्प्रकटने आदिशद् विशङ्कम् / शुश्रूषामयमुचितो विधातुमीष / ल्लोकानामिति वचसा परीक्षकाणाम्
  scan `GGGLLLLGLGLGG|GGGLLLGGLGLGG|GGGLLLLGLGLGL|GGGLLLLGLGLGG` syllables [13, 13, 13, 13]; equal pādas of 13 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `sumadhva_vijaya:sarga_16:37` (Sumadhva Vijaya) — भीमत्वे सह सहजैः प्रतिष्ठितः प्राक् / पञ्चात्मा मुर-रिपु-रचितो यत्र / पाञ्चाल्या बलि-सलिलं समं ददत्या / सोऽस्मार्षीत् तमिममथ प्रपूज्य पूज्यः
  scan `GGGLLLLGLGLGG|GGGLLLLLLGGL|GGGLLLLGLGLGG|GGGLLLLGLGLGG` syllables [13, 12, 13, 13]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_16:42` (Sumadhva Vijaya) — सर्वज्ञोऽप्ययमधिकं न यज्ञभङ्गीं / संवेत्ति यतिरिति बद्धनिश्चयोऽसौ / आभान्तं परिषदि मत्सरादपृच्छत् / कर्म्मार्थश्रुतिगहनार्थखण्डभावम्
  scan `GGGLLLLGLGLGG|GGLLLLLGLGLGG|GGGLLLLGLGLGG|GGGLLLLGLGLGG` syllables [13, 13, 13, 13]; equal pādas of 13 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `sumadhva_vijaya:sarga_16:43` (Sumadhva Vijaya) — छन्दोभ्यश्च्युतरससङ्ग्रहप्रवीणान् / षष्ठेऽह्नि विहितान् प्रजाधिपेन / नाराशंस्यचरमचारुमन्त्रभेदान् / सोऽसौ तमभिदधद्विशंशयांशः
  scan `GGGLLLLGLGLGG|GGLLLGLGLGL|GGGLLLLGLGLGG|GGLLLLGLGLGG` syllables [13, 11, 13, 12]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `sumadhva_vijaya:sarga_16:49` (Sumadhva Vijaya) — इत्यूचे धरणीसुरेण केवलं नो / माध्वीयं विविधकथा कथासु मान्या / साक्षादप्यमरवरैरुदीर्य्यमाणा / गन्धर्वैर्द्युसदसि तन्मुदे जगेऽसौ
  scan `GGGLLGLGLGLGG|GGGLLLLGLGLGG|GGGLLLLGLGLGG|GGGLLLLGLGLGG` syllables [13, 13, 13, 13]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: प्रहर्षिणी (1 भेदौ)

### Part C batch 4 (items 121–160)

* `sumadhva_vijaya:sarga_16:54` (Sumadhva Vijaya) — नाकीन्द्रास्तमवनिभागमावसन्तं / सुश्लोकैरपि भुवनानि भूषयन्तम् / नेमुः स्वादूपनिषदं तदैतरेयीं / व्याख्यान्तं विविधविशिष्टशिष्यमध्ये
  scan `GGGLLLLGLGLGG|GGGLLLLGLGLGG|GGGGLLLGLGLGG|GGGLLLLGLGLGG` syllables [13, 13, 13, 13]; equal pādas of 13 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_2:1` (Rāghavendra Vijaya) — रामावतारस्य हरेरधत्त सेवां हनुमद्रूपुपा समीरः / भीमात्मना यादवभूषणस्य मध्वात्मना व्यासमुनित्वभाजः
  scan `GGLGGLLGLGLGGLLGGLGLGG|GGLGGLLGLGLGGLGGLLGLGG` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_2:2` (Rāghavendra Vijaya) — आभाष्य भाष्यं निगमान्तसूत्रव्याख्यात्मकं पूर्णमतिर्गुरुर्नः / संपादयध्वं मतसंप्रदायसमृद्धिमित्यादिदिशेयमीश्वरान्
  scan `GGLGGLLGLGGGGLGGLLGLGG|GGLGGLLGLGLLGLGGLLGLGLG` syllables [22, 23]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_2:4` (Rāghavendra Vijaya) — सिद्धान्तसंरोहविधौ नियुक्तेष्वेतेष्वनेक्रवतिषु प्रधानः / प्रेमास्पदं स्वीयगुरोः स पद्मनाभार्यवर्योऽकृत दर्शनर्द्धिम्
  scan `GGLGGLLGLGGGGLGLLLGLGG|GGLGGLLGLGLGGLGGLLGLGG` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_2:9` (Rāghavendra Vijaya) — अन्ते वसंतस्य गुरोरनेनासभाजवत्तां प्रतिमां वितीर्णाम् / संवर्धयन्नादिमसंप्रदायमन्योऽभवन्माधवकंसंयमीन्द्रः
  scan `GGLGGLLGLGGLGLGGLLGLGG|GGLGGLLGLGLGGLGGLLGGLGG` syllables [22, 23]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_2:11` (Rāghavendra Vijaya) — दृढासिना तत्त्वमसीतिवाचा सामर्थ्यभाजा परजीवभेदे / अवैदिकाम्यं मुनिरेष विदारण्यं शरण्यं कुदृशां बिभेद
  scan `LGLGGLLGLGGGGLGGLLGLGG|LGLGGLLGLLGGGLGGLLGLGL` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_2:12` (Rāghavendra Vijaya) — तल्लब्धबोधो विमतैकबाधो जयैकभूर्जयतीर्थनामा / व्याचष्ट पूर्णप्रमतिप्रणीतं सर्वं प्रबन्धं सरसैर्वचोभिः
  scan `GGLGGLLGLGGLGLGLLGLGG|GGLGGLLGLGGGGLGGLLGLGG` syllables [21, 22]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_2:23` (Rāghavendra Vijaya) — सा रामचन्द्रप्रतिमा जयीन्द्रात्सुधीन्द्रयोगीन्द्रमगात्क्रमेण / विस्तीर्णकीर्तिर्विभावावन्यां विख्यातविद्वज्जनवन्द्यपादः
  scan `GGLGGLLGLGGLGLGGLLGLGL|GGLGGLGGGGGGLGGLLGLGG` syllables [22, 21]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_2:24` (Rāghavendra Vijaya) — पवित्रितामेष धरां वितन्वन् सञ्चारतो दिग्विजयपदेशात् / श्रीवेङ्कटक्ष्मापरणीसमक्षे वादेन विद्वेषिबुधान् विजिग्ये
  scan `LGLGGLLGLGGGGLGGLLLLGG|GGLGGLLGLGGGGLGGLLGLGG` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_2:40` (Rāghavendra Vijaya) — स्त्रीयावनैश्वर्यकलान्यशिक्षाकृते रमेशांशनृपेण यस्याम् / मुक्तरुणेन्द्रोपलसौधदम्भाद्गुणत्रयं किं क्रमशॊ गृहीतम्
  scan `GGLGGLLGLGGLGLGGLLGLGG|GLLGGLLGLGGLGLGGLLLLGG` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_2:48` (Rāghavendra Vijaya) — न चन्द्ररेखा नखरेण क्लृप्ता न मोहनं केवलदर्शनेन / न रूक्षता नैव रुचिर्न हारास्तैर्दिभिर्यद्रमणीकुचानाम्
  scan `LGLGGLLGGGGLGLGGLLGLGL|LGLGGLLGLGGGLGGLLGLGG` syllables [22, 21]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_2:51` (Rāghavendra Vijaya) — न भ्रूविलासा नतमां स्थिरश्रीर्नारसोक्तिर्नतमां च यस्य / तेनेन्दुना यत्प्रमदामुखानां कथं कवीन्द्राः कथयन्तिसाम्यम्
  scan `GGLGGLLGLGGGLGGLLGLGL|GGLGGLLGLGGLGLGGLLGLGG` syllables [21, 22]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_3:15` (Rāghavendra Vijaya) — नगरान्निरगान्नरेन्द्रयोग्यात् सहजायः ससुहृज्जनोऽसुती सः / अखिलाथिंतदानदक्षशेषाचलभूषामणिदेवतां दिदृक्षुः
  scan `LLGLLGLGLGGLLGGLLGLGLGG|LLGGLGLGLGGLLGGLLGLGLGG` syllables [23, 23]; equal pādas of 23 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_3:24` (Rāghavendra Vijaya) — तनुशायिशिशोर्विरागता किं वितताऽङ्गेषु विशाललोचनायाः / परथा सततं हिते तरुण्या रुचিতে वस्तुनि किंतरां विरागः
  scan `LLGLLGLGLGGLLGGLLGLGLGG|LLGLLGLGLGGLLGLLGLGLGG` syllables [23, 22]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_3:27` (Rāghavendra Vijaya) — सभयो विधुरेष सह्यकेयात्स्वमपहृत्य निगूहितुं प्रवृत्तः / निजलक्ष्म निरस्य रोमराजिं निभृतोगर्भमुपेयिवानमुष्याः
  scan `LLGLLGLGLGGLLLGLLGLGLGG|LLGLLGLGLGGLLGGLLGLGLGG` syllables [23, 23]; equal pādas of 23 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_3:28` (Rāghavendra Vijaya) — कमितुः किमु मोहनाय कामोऽकृत कामं कठिनौ कुचौ तदीयौ / निजचुचुकनीलिमापदेशादचिरोपात्तमोगुणावभूताम्
  scan `LLGLLGLGLGGLLGGLLGLGLGG|LLLLLGLGLGGLLGGLGLGLGG` syllables [23, 22]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_3:29` (Rāghavendra Vijaya) — ततनामिनिभालबालमध्यादुदयद्रोमलताऽऽस्य कल्पशाखी / फलितोऽजनि किं पयोधराभ्यामुदयच्चुचुकनैल्य भृङ्गभाभ्याम्
  scan `LLGLLGLGLGGLLGGLLGLGLGG|LLGLLGLGLGGLLGLLLGLGLGG` syllables [23, 23]; equal pādas of 23 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_3:31` (Rāghavendra Vijaya) — तनयाभ्युदयादृणत्रयस्याप्यपनोदं कमितुर्विधातुमस्याः / पुरतोऽकृत तस्य लक्ष्मरेखात्रिवलीरूजभवो निरस्तररूपाः
  scan `LLGLLGLGLGGLLGGLLGLGLGG|LLGLLGLGLGGLLGGLLGLGLLGG` syllables [23, 24]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_3:32` (Rāghavendra Vijaya) — विमतं निखिलं च दृश्यभावाद्भवित सत्यमितीदृशानुमाने / अधिमध्यमपास्य हेत्वसिद्धिं प्रथिमा क्रोऽपि शनैःशनै र्जृजृम्भे
  scan `LLGLLGLGLGGLLLGLLGLGLGG|LLGLLGLGLGGLLGGLLGLGLGG` syllables [23, 23]; equal pādas of 23 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_3:36` (Rāghavendra Vijaya) — वसुधासुखवासस्य गर्भे कृतवासस्य नतभ्रुवोर्मकस्य / अजनिष्ट मनोरथोनुरूपः क्रमशः प्राप्तवति द्वितीयमासे
  scan `LLGLLGGLGGLLGGLLGLGLGL|LLGLLGLGLGGLLGGLLGLGLGG` syllables [22, 23]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_3:37` (Rāghavendra Vijaya) — भवने भुवनं कृशानुसप्तं परिक्लृप्तं नवशातकुम्भकुम्भैः / अपहाय नदीपयो हिमानीधवलं केवलमैच्छदच्छबुद्धिः
  scan `LLGLLGLGLGGLGGGLLGLGLGG|LLGLLGLGLGGLLGGLLGLGLGG` syllables [23, 23]; equal pādas of 23 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_3:45` (Rāghavendra Vijaya) — प्रददौ बहुकर्मधारयेण स्वबहुव्रीहिमुपादे द्वयाग्न्यान् / स तु तत्पुरुषैः पुनर्वितीर्णान्रचितद्वन्द्वफलान् धृताव्ययित्वात्
  scan `LLGLLGLGLGGLLGGLLGGLGG|LLGLLGLGLGGLLGGLLGLGLGG` syllables [22, 23]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_3:49` (Rāghavendra Vijaya) — घटते तनयेऽभिधा तदंशे गुणवृद्धयर्थमनुक्तिसिद्धये च / अतिदेशकृते हरेर्गुणानां विवदन्ते खलु जैमिनीयशौण्डाः
  scan `LLGLLGLGLGGLLGLGLLGLGLGL|LLGLLGLGLGGLLGGLLGLGLGG` syllables [24, 23]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_3:55` (Rāghavendra Vijaya) — विलिख्य भूमौ प्रथमं कुमारं रेखामिमामोमिति संपठेति / पित्रा नियुक्तः पुनरब्रवीत्तमलपे कथं सा गुणपूर्णसंज्ञा
  scan `LGLGGLLGLGGGGLGGLLGLGL|GGLGGLLGLGLLLGLGGLLGLGG` syllables [22, 23]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_3:57` (Rāghavendra Vijaya) — तनुजामष्टाब्दां ससहजयुगां काव्यकुशलां सुभद्रां भद्राङ्गीमिव मुसलिकंसारिसहिताम् / स दद्यां कस्मैचद्विदितकुलसंजातविदुषे चकारेत्थं बुद्धिं तनयवदनालोकमुदितः
  scan `LLGGGGLLLLLGGLLLGLGGGGGLLLLLGGLLLG|LGGGGGLLLLLGGLLLGLGGGGGLLLLLGGLLLG` syllables [34, 34]; equal pādas of 34 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_4:1` (Rāghavendra Vijaya) — अथेन्द्ररक्षोत्सुकवामनोद्भवप्रसिद्धिमत्काश्यपवंशसंभवः / भुवि श्रुतो डङ्किपुराधिनायको बभूव तिम्मण्णदण्डनायकाभिधः
  scan `LGLGGLLGLGLGLGLGGLLGLGLG|LGLGGLLGLGLGLGLGGLGLGLGLG` syllables [24, 25]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_4:13` (Rāghavendra Vijaya) — विहारभेदान्विविधान्विशालधीः सकृद्विलोक्ष्यैव सखिव्रजैः कृतान् / तानेव संगृह्य तपोभिशीलनाकृते सदैवतानुते स्म सादरम्
  scan `LGLGGLLGLGLGLGLGGLLGLGLG|GGLGGLLGLGLGLGLGLGLGLGLG` syllables [24, 24]; equal pādas of 24 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_4:18` (Rāghavendra Vijaya) — कपोलराजन्नवरोमवल्लरीनिबेष्टितुं याति तदा तदाननम् / समानतां तेन यदा बहिर्गलत्कलङ्करेखावृत्तमिन्दुमण्डलम्
  scan `LGLGGLLGLGLGLGLGGLLGLGLG|LGLGGLLGLGLGLGLGGGLGLGLG` syllables [24, 24]; equal pādas of 24 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_4:20` (Rāghavendra Vijaya) — विलम्बिते श्मश्रुमहः परं पराद्वितय यच्छृंखलमध्यसीमानि / तदाननच्छद्मसुवर्णभाजने विराजते विस्तृतशास्त्रशेवधिः
  scan `LGLGGLLGLGLGLLLGGLLGLGGL|LGLGGLLGLGLGLGLGGLLGLGLG` syllables [24, 24]; equal pādas of 24 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_4:23` (Rāghavendra Vijaya) — नवाकृतेरस्य ललाटतामसी विटार्धबिंबाग्रलसत्सुधारसम् / उदग्रनासाभ्रममार्गनिर्गमं बिभर्ति नोचेदमृतं कुतॊधरे
  scan `LGLGGLLGLGLGLGLGGLLGLGLG|LGLGGLLGLGLGLGLGGLLGLLLG` syllables [24, 24]; equal pādas of 24 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_4:25` (Rāghavendra Vijaya) — मनोहरे तन्मुखगर्भगमन्दिरे चिरं रसज्ञानिभतूलिकाञ्चिते / वचोऽधिदेव्यां शयनक्रियाजुषो रदावलिं हारलतेति मन्महे
  scan `LGLGGLLGLLGLGLGLGGLLGLGLG|LGLGGLLGLGLGLGLGGLLGLGLG` syllables [25, 24]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_4:29` (Rāghavendra Vijaya) — यदीयनासानिटिलद्युतिच्छलद्युसिन्धुसिन्धुप्रभुसंगमस्थले / स्फुरन्महावर्तविभूषितान्तरे विभिन्नवेले इव चिल्लबल्लरीके
  scan `LGLGGLLGLGLGLGLGGLLGLGLG|LGLGGLLGLGLGLGLGGLLGLGLGG` syllables [24, 25]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_4:33` (Rāghavendra Vijaya) — मृणालवल्लीं कथयन्ति कन्धरां मुखारविन्दस्य विकस्वरश्रियः / परे तु नालं मृदुलं गलं जगुर्मुखाभिधान्मुकुरस्य मन्दिरम्
  scan `LGLGGLLGLGLGLGLGGLLGLGLG|LGLGGLLGLGLGLGLGLLGLGLG` syllables [24, 23]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_4:35` (Rāghavendra Vijaya) — अमुष्य लोकत्रयलक्षणक्रियानिबोधनायेह नृणां तनुदरे / महामहिम्नोऽस्य वलित्रयच्छलात्कृता विधात्रा किमु चिह्नरेखिका
  scan `LGLGGLLGLGLGLGLGGLLGLLLG|LGLGGLLGLGLGLGLGGLLGLGLG` syllables [24, 24]; equal pādas of 24 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_4:38` (Rāghavendra Vijaya) — पदे कृते चेत्कठिने मया पदा व्रजेदयं तन्न सहे नवाकृतेः / चिरेण यानेन व्रजेद्वसुन्धरामितीव वेधा मृदुलेऽव्यधादिमे
  scan `LGLGGLLGLGLGLGLGGLLGLGLG|LGLGGGLGLGLGLGLGGLLGLGLG` syllables [24, 24]; equal pādas of 24 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_4:39` (Rāghavendra Vijaya) — ऋणादृषीणामथ मुक्तभाजनं मुमुक्षुरस्यः सुधियामृणद्वयात् / तदग्रजो वीक्ष्य विवाहंमङ्गलं विधातुमैच्छद्गुरुराजनामभाक्
  scan `LGLGGLLGLGLGLGLGGLLGLGLG|LGLGGLLGGGLGLGLGGLLGLGLG` syllables [24, 24]; equal pādas of 24 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_4:43` (Rāghavendra Vijaya) — पदेपदे पल्लवकान्ति सम्पदा निगूढगुल्फे नखराः प्रभाकराः / निरस्तकूर्मकृतिनीचजानुनी करौ तदूरू करिणो मनोहरौ
  scan `LGLGGLLGLGLGLGLGGLLGLGLG|LGLGLLLGLGLGLGLGGLLGLGLG` syllables [24, 24]; equal pādas of 24 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_4:46` (Rāghavendra Vijaya) — शिशोरमुष्यास्तिलकस्य केलिनीसखस्य डोलेव ललाटपट्टिका / चतुष्कपर्दायसशृङ्खलाश्रिता ललन्तिकारलनिगुच्छराजिता
  scan `LGLGGLLGLGLGLGLGGLLGLGLG|LGLGGLLGLGLGLGLGLLLGLGLG` syllables [24, 24]; equal pādas of 24 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_5:1` (Rāghavendra Vijaya) — अथ विवाहसमुत्सुककन्यकागुणमणी पितरौ निजमन्दिरात् / अगमतामभिवीक्षतुमादराद्दूरमुपागतमात्मपुरोदरम्
  scan `LLLGLLGLLGLGLLLGLLGLLGLG|LLLGLLGLLGLGGLLGLLGLLGLG` syllables [24, 24]; equal pādas of 24 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_5:6` (Rāghavendra Vijaya) — अभिदिदृक्षुजने वरमादरादुपगते भवनं तदनुज्ञया / कृतपरस्परसंक्थनो जनः सुखमुवास निशामिह वेश्मनि
  scan `LLLGLLGLLGLGLLLGLLGLLGLG|LLLGLLGLGLGLLLGLLGLLGLL` syllables [24, 23]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose

### Part C batch 5 (items 161–200)

* `raghavendra_vijaya:sarga_5:15` (Rāghavendra Vijaya) — प्रमिताक्षरामुचमनूद्य सुहृत्समुपाहृतान्यभिनवानि मुहुः / विविधानि पुरोहितजनावनयो र्वसनानि संसदि समर्पयताम्
  scan `LLGLGLLLGLLGLLGLGLLLGLLG|LLGLLGLLLGLLGLLGLGLLLGLLG` syllables [24, 25]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_5:19` (Rāghavendra Vijaya) — इन्द्राणी बलरिपुवैरिणीव वाणी लोकेशे कलशपयोधिन्यकेव / गोविन्दे गरलगले गिरीन्द्रकन्या कन्या स्याद्दयितमनःप्रहर्षणीयम्
  scan `GGGLLLLGLGLGGGGGLLLLGGLGL|GGGLLLLGLGLGGGGGLLLLGLGLGG` syllables [25, 26]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_5:23` (Rāghavendra Vijaya) — आगच्छन्पथि वध्वा साकं सर्वैः समं निजग्रामम् / काननभूषु वधूनां दोहललक्ष्मीरपश्यदुरुमेधाः
  scan `GGGLLGGGGGGLGLGGG|GLLGLLGGGLLGGLGLLLGG` syllables [17, 20]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_5:24` (Rāghavendra Vijaya) — चकितहरिणशावकेक्षणस्त्रीचरणहतोपि पुनः पुनर्यदीयः / ननु हसितरामशोकशाखी प्रकटयितुं नितरामशोकभावम्
  scan `LLLLLLGLGLGGLLLLGLLGLGLGG|LLLLLGLGLGGLLLLGLLGLGLGG` syllables [25, 24]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_5:30` (Rāghavendra Vijaya) — कुवलयदलनीललोचनानां तनुरुचिमीक्षितुमीक्षितोऽङ्गनाभिः / तिलकतरुरुदग्रसूनजालैर्दशतलोचनतामवाप नूनम्
  scan `LLLLLLGLGLGGLLLLGLLGLGLGG|LLLLLLGLGLGGLLLGLLGLGLGG` syllables [25, 24]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_5:40` (Rāghavendra Vijaya) — यासां नमेरुः कुचगौरवेण तुलायितो नाजनि हासपात्रम् / नकारयुक्तत्पदवाच्यभूरुहो जहास हासैः कुसुमैश्च तासाम्
  scan `GGLGGLLGLGLLGLGGLLGLGG|LGLGGLLGLGLGLGLGGLLGLGG` syllables [22, 23]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_6:3` (Rāghavendra Vijaya) — सह्यक्षमाभृन्नन्दिनीतीरदेशे भूयोभूयो भूसुपर्वाग्रहाराः / ग्रामे ग्रामे तद्गृहाणां सहस्रं गेहेगेहे पण्डिता एव सर्वे
  scan `GGLGGGLGGLGGGGGGGLGGLGG|GGGGGLGGLGGGGGGGLGGLGG` syllables [23, 22]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_6:5` (Rāghavendra Vijaya) — नित्यं यस्मिन् उर्वरेवाखिला भूः सालाः पूर्णा एव सर्वे फलौघैः / पृथ्वीदेशादीक्षिता एव सर्वे सह्यक्षमाभृन्नन्दिनीसन्निधानात्
  scan `GGGGGLGGLGGGGGGGLGGLGG|GGGGGLGGLGGGGLGGGLGGLGG` syllables [22, 23]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_6:7` (Rāghavendra Vijaya) — शाब्दं भाष्यं जायदेवीं च टिकां भाट्टं तन्त्रं भामतिं गौरवंश्च / व्यासर्योक्तां चन्द्रिकां वेकटार्यः यद्यद्ग्रेद्यं तत्तदभ्यस्यति स्म
  scan `GGGGGLGGLLGGGGGGLGGLGL|GGGGGLGGLGGGGGGGLGGLGL` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_6:8` (Rāghavendra Vijaya) — प्रातः स्नात्वा साधु वेदान्तभाष्यं शाब्दं पश्चात्तर्कशास्त्रं ततस्सः / पूर्वं तन्त्रं चावेदान्वेङ्कटार्यो तुर्ये यामे कांश्चिद्दन्दान्नैषीत्
  scan `GGGGGLGGLGGGGGGGLGGLGG|GGGGGGGGLGGGGGGGGGGGG` syllables [22, 21]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_6:10` (Rāghavendra Vijaya) — ब्रह्माभिन्नोजीवसंघः कुतस्त्वं ब्रूहीत्युक्ते केनचित्तद्बुधेन / मिथ्या यस्माद्विश्वमित्युक्तमात्रे किंचतोऽस्मिन्नान्न मानं त्वयोक्तम्
  scan `GGGGGLGGLGGGGGGGLGGLGL|GGGGGLGGLGGGLGGGLGGLGG` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_6:11` (Rāghavendra Vijaya) — शास्त्रे नोक्तो न श्रुतः केनचिद्वा यः किंचात्ः शब्द उक्तस्त्वयेति / उक्ते तेन प्रावदद्वेङ्कटार्यो व्यक्तंयस्त्वं नाश्रृणोः शाब्दभाष्यम्
  scan `GGGGGLGGLGGGGGGLGGLGL|GGGGGLGGLGGGGGGGLGGLGG` syllables [21, 22]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_6:13` (Rāghavendra Vijaya) — दण्डेनान्यस्ताडितः कुण्डलीव'प्साधातोर्यङ्लुगन्तस्य रूपम् / शन्न्रन्तस्येत्यर्धवाक्ये स' पाप्सत्तस्येत्युक्त्वा वादिनं पृच्छति स्म
  scan `GGGGGLGGLGGGGGGLGGLGG|GGGGGLGGLGGGGGGGLGGLGL` syllables [21, 22]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_6:17` (Rāghavendra Vijaya) — कालेनास्मिन् काकतालीयशब्दे जेतारं तं यायजूकान्कवीन्द्रान् / तस्यां पुर्यां तसमुद्राङ्कने च प्रौढं मेने यज्ञनारायणस्तम्
  scan `GGGGGLGGLGGGGGGGLGGLGG|GGGGLLGGLGGGGGGGLGGLGG` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_6:18` (Rāghavendra Vijaya) — विद्योद्योगाद्वासरान्यापयन्तं प्राप्तौन्नत्यं पातुर्कं निर्धनत्वम् / अत्यासन्नश्रीनिदानेन्दिरेषध्यानोपायो बुद्धिवार्धिं सिषेवे
  scan `GGGGGLGGLGGGGGGGGGGLGG|GGGGGLGGLGGGGGGGLGGLGG` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_6:19` (Rāghavendra Vijaya) — अढढस्यैकं वत्स्यतो नास्य नव्यं स्थूलं वस्त्रं संततं चालपमौल्यम् / नव्यं वस्त्रं नैव सूक्ष्मं कदापि क्षौमे तस्मिन् का कथाकिंचनस्य
  scan `LLGGGGLGGLGGGGGGGLGGLLGG|GGGGGLGGLGGGGGGGLGGLGL` syllables [24, 22]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_6:22` (Rāghavendra Vijaya) — छिन्ने वस्त्रे भिन्न पानीयपात्रे जीर्णस्थल्यां दस्युभिर्नीयमाने / प्रागाक्रुष्टं भाविकौपीनमस्य छागे यागे प्रागिवाभूतप्रयाजः
  scan `GGGGGLGGLGGGGGGGLGGLGG|GGGGGLGGLGLGGGGGLGGGLGG` syllables [22, 23]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_6:25` (Rāghavendra Vijaya) — एवं चेदप्यादराद्वोक्तृचिह्नं सन्धार्यायं शास्त्रमुख्यादजस्रम् / हर्षे प्राप्ता ह्यात्मधर्मानुरूपा पत्याकारस्पर्शानालापजाताम्
  scan `GGGGGLGGLGGGGGGGLGGLGG|GGGGGLGGLGGGGGGGGGGLGG` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_6:31` (Rāghavendra Vijaya) — अक्षाणा काणं कर्णपर्यन्तनेत्रं लोभागारं सन्ततौदार्यभाजम् / सन्ध्योपासावर्जितं यायजूकं दुष्टाचारं साधु कर्माचरन्तम्
  scan `GGGGGGLGGLGGGGGGGLGGLGG|GGGGGLGGLGGGGGGGLGGLGG` syllables [23, 22]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_6:35` (Rāghavendra Vijaya) — वेदव्याख्यासम्पदो नैव युक्ता व्यांसगे ते मज्जतो गेहजाते / तस्मादाशां मुञ्च तस्यां तरुण्यां शीघ्रं कुर्या बालमज्ञोपनीतम्
  scan `GGGGGLGGLGGGLGGGLGGLGG|GGGGGLGGLGGGGGGGLGGLGG` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_6:36` (Rāghavendra Vijaya) — श्रुत्वाऽश्रृण्वन्नेवमुक्तं गुरूणां गत्वायादेष चिन्तां दुरन्ताम् / निर्यायादित्येष निश्चित्य तावन्मत्यैरेतै रक्षति स्मनमेशः
  scan `GGGGGLGGLGGGGGGLGGLGG|GGGGGLGGLGGGGGGGLGLLGG` syllables [21, 22]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_6:37` (Rāghavendra Vijaya) — स्यास्यामश्चेल्ल्भ्यते संयमित्वं गच्छामश्चेत्तेऽधुना मां शपेरन् / स्थातुं शक्यं नैव गन्तुं च शक्यं कुर्मः किं वेत्यात्मनाऽध्यायदित्थम्
  scan `GGGGLGGLGGGGGGGLGGLGG|GGGGGLGGLGGGGGGGLGGLGG` syllables [21, 22]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_6:40` (Rāghavendra Vijaya) — कैषा योषा काञ्चनानर्घ्यभूषा दोषाधीशानना चारुवेषा / दोषातीता सान्द्रधम्मिल्लदोषा भाषादेवी सर्वसाक्षान्मनीषा
  scan `GGGGGLGGLGGGGGGLGGLGG|GGGGGLGGLGGGGGGGLGGLGG` syllables [21, 22]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_6:45` (Rāghavendra Vijaya) — आकल्पं मेऽकल्पयज्जीवनेच्छोर्वासं वल्ग्यास्तर्कनाट्योत्सुकायाः / सौधायान्न्यायामृताब्द्धिमत्यास्तात्पर्याद्या चन्द्रिकाख्या स यस्याः
  scan `GGGGGLGGLGGGGGGGLGGLGG|GGGGGLGLGGGGGGGLGGLGG` syllables [22, 21]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_6:46` (Rāghavendra Vijaya) — विख्यातो यः श्रीजयीन्द्रव्रतीन्द्रस्सरख्या लब्धा साधुकीर्तिर्मयोर्व्याम् / व्याख्याव्याजादालवालं व्यतानीत्तस्या वल्ग्या न्यायपूर्वामृतस्य
  scan `GGGGGLGGLGGLGGGGGLGGLGG|GGGGGLGGLGGGGGGGLGGLGL` syllables [23, 22]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_6:47` (Rāghavendra Vijaya) — चित्रैर्वणैः शोभितं श्लाधितार्थं व्याप्तं देशे क्षौमवासेतिनूलम् / प्रायच्छन्मे कण्टकोद्धारदम्भादाचन्द्रार्कस्थायि चारुप्रभावः
  scan `GGLGGLGGLGGGGGGGLGGLGG|GGGGGLGGLGGGGGGGLGGLGG` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_6:51` (Rāghavendra Vijaya) — सर्वं व्यर्थं भाति मे जीवनाड्याश्छिन्ने मूले चन्द्रिकासौधवल्लुयाः / व्याख्यानास्त्रं व्याकरोरूढमूलां धर्मी नोचेद्धर्मचिन्ता क्व दृष्टा
  scan `GGGGGLGGLGGGGGGGLGGLGLG|GGGGGLGGLGGGGGGGLGGLGG` syllables [23, 22]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_6:53` (Rāghavendra Vijaya) — श्रीरामार्वा पूज्यते येन तस्मिन् वासो यन्मेकल्पयद्व्यासदेवः / कर्मन्दीन्द्रैरेव पूजापि क्लृप्ता तस्मात्साहं तेषु नित्यं वसामि
  scan `GGGGGLGGLGGGGGGGLGGLGG|GGGGGLGGGGGGGGGGLGGLGL` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_6:55` (Rāghavendra Vijaya) — उत्सूत्रत्वं केवलं नाद्यपक्षे न्यायौघानां किं तु तत्पुस्तकानाम् / रक्षाभावाद्भक्षूणामूषिकानां मायावादिब्रह्मवन्निर्गुणानाम्
  scan `GGGGGLGGLGGGGGGGLGGLGG|GGGGGGGGLGGGGGGGLGGLGG` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_6:56` (Rāghavendra Vijaya) — आद्ये तन्त्रे प्रक्रियांयां विचारस्तत्रैव स्यात्कर्मणां निर्णयेोपि / किंचात्रैव न्यायपूर्वां सुधारख्यां भाष्यारम्भं शाब्दिका एव कुर्युः
  scan `GGGGGLGGLGGGGGGGLGGLGL|GGGGGLGGLGGGGGGGGLGGLGG` syllables [22, 23]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_6:57` (Rāghavendra Vijaya) — वक्ता विष्णोरुत्तमत्वं कथायाः भूपालानां भाति विद्वत्सभायाम् / शक्तेर्भानोः शक्तिपागेर्गेणेशः शक्रादीनां धूर्जटेर्वा तदा स्यात्
  scan `GGGGGLGGLGGGGGGGLGGLGG|GGGGGLGGGGGGGGGGLGGLGG` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_6:62` (Rāghavendra Vijaya) — हन्तेदानीं देवताया गुरूणामर्चगारं गुग्गुलुव्यूहधूमैः / दीपैर्दीप्तैर्दीष्यमानं तदानीं नित्यासक्तालातभूतास्यदीपैः
  scan `GGGGGLGGLGGGLGGGLGGLGG|GGGGGLGGLGGGGGGGLGGLGG` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_6:66` (Rāghavendra Vijaya) — भूयोभूयो बोधितस्साधकैस्तैः पारिव्राज्यं बाधकैर्न्यथात्वे / स्मारंस्मारं देवतोक्तं च विद्वान्बुङ्क्ते स्म स्वात्मजस्योपनीतौ
  scan `GGGGGLGGLGGGGGGGLGLGG|GGGGGLGGLGGGGGGLGGLGG` syllables [21, 21]; equal pādas of 21 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_6:67` (Rāghavendra Vijaya) — सोमादिभ्यो देवत्ताभ्यः प्रदानं पुत्रस्यैतन्मुख्यमेवंधिधस्य / लोके गौणं नूनमित्थं वदन्तं दृष्टा को वा नाश्रु सर्वो मुमोच
  scan `GGGGGGGGLGGGGGGGLGGLGL|GGGGGLGGLGGGGGGGLGGLGL` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_7:4` (Rāghavendra Vijaya) — गुरुपूर्णबोधमतसिन्धुचन्द्रमा यतिराडुपदिशदगाधमेधसाम् / अथ मानपद्धतिपुरःसरं कृती निजदर्शनं निखिलसम्पदां पदम्
  scan `LLGLGLLLGLGLGLLGLLLLLGLGLG|LLGLGLLLGLGLGLLGLGLLLGLGLG` syllables [26, 26]; equal pādas of 26 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_7:5` (Rāghavendra Vijaya) — कमलालये कमलया कटाक्षितो यमिराडवाप यमराडपायदम् / प्रणिर्नसुरर्घमहिलं कूपोर्मिलं सरलं श्रितेषु गरलं खलेखिले
  scan `LLGLGLLLGLGLGLLGLGLLLGLGLG|LGLLGLLLGGGLGLLGLGLLLGLGLG` syllables [26, 26]; equal pādas of 26 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_7:8` (Rāghavendra Vijaya) — अवगाह्य सह्यतनयासरस्वतोर्विमले चिरं व्यतिकरे व्यराजत / हृदि भावितो हरिरिवोदितस्तथा सरिदीशादर्शनकृतानुस्रमदः
  scan `LLGLGLLLGLGLGLLGLGLLLGLGLL|LLGLGLLLGLGLGLLGGGLLLGGLLG` syllables [26, 26]; equal pādas of 26 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_7:13` (Rāghavendra Vijaya) — हृदि बोधदुग्धरसवासनाकृतेः परिनिर्मिताविव पयोजतलुजौ / अपवर्गमार्गपरिबोधनाय मे चरणौ तवेश किमु चिह्णपल्लवौ
  scan `LLGLGLLLGLGLGLLGLGLLLGLLLG|LLGLGLLLGLGLGLLGLGLLLGLGLG` syllables [26, 26]; equal pādas of 26 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_7:14` (Rāghavendra Vijaya) — उपरि श्रितेन पुरतश्च नश्वरव्यवहारदूरगगिरामनावृतम् / प्रणवद्वयेन मणिन्नुपुरात्मना परिकर्मिते तव पदेपदे मुदाम्
  scan `LLGLGLLLGLGLGLLGLGLLLGLGLG|LLGLGLLGLLGLGLLGLGLLLGLGLG` syllables [26, 26]; equal pādas of 26 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_7:16` (Rāghavendra Vijaya) — अरुणाधरं तरुणचन्द्रसुन्दरं करुणाधरं वदनमीश तावकम् / सितकान्तिपूरनवचन्द्रिकाभरैर्मेव शार्वरं क्षिपति भव्यचेतसाम्
  scan `LLGLGLLLGLGLGLLGLGLLLGLGLG|LLGLGLLLGLGLGGLGLGLLLGLGLG` syllables [26, 26]; equal pādas of 26 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect

### Part C batch 6 (items 201–240)

* `raghavendra_vijaya:sarga_7:25` (Rāghavendra Vijaya) — हृतकल्पभूरुहतया पुनश्च भाजककल्पकल्पतरुरोहणाय यः / हलसंस्कृतो लहरिभिस्समन्ततः सकरीषराशिरपि सान्द्रशैलैः
  scan `LLGLGLLLGLGLGLLGLGLLLGLGLG|LLGLGLLLGLGLGLLGLGLLLGLGG` syllables [26, 25]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_7:26` (Rāghavendra Vijaya) — परिवृत्य पूरितजलांप्रं भ्रमिं स्फुरितास्फुरद्रुचिरविद्रुमां प्रगे / कवयो हि यत्र वरुणालये निशाकृतदीपशान्तिमभितः शशङ्किरे
  scan `LLGLGLLLGGLGLLGLGLLLGLGLG|LLGLGLLLGLGLGLLGLGLLLGLGLG` syllables [25, 26]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_7:27` (Rāghavendra Vijaya) — यतिनेतृवादारणधुर्यभास्करे प्रकटीकृते हि पतिना रसातलात् / तमसां ततिर्यदभियाद्वियोद्धृता बहिरप्युदीक्षितुमभूज्जडीकृता
  scan `LLGLGGLLGLGLGLLGLGLLLGLGLG|LLGLGLLLGLGLGLLGLGLLLGLGLG` syllables [26, 26]; equal pādas of 26 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_7:28` (Rāghavendra Vijaya) — मुखराण्डजा मणिमरीचिमौक्तिकैः प्रकटप्रवालमुकुला यदूर्मयः / मरुता न्तोन्नतिभृतो विरेजिरे वरुणालयोपवनशाखिका इव
  scan `LLGLGLLLGLGLGLLGLGLLLGLGLG|LLGGLLLGLGLGLLGLGLLLGLGLL` syllables [26, 25]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_7:29` (Rāghavendra Vijaya) — अमुमेत्य मुख्यतमाश्रयं निजं हरिरेष मां प्रतिनिधं त्यजेदिति / लुठति स्म यस्समयमूर्मिभिश्श्वसन्न्रिजरोघसि क्षितिगवीव रोधसि
  scan `LLGLGLLGLGLGLLGLGLLLGLGLL|LLGLGLLLGLGLGLLGLGLLLGLGLL` syllables [25, 26]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_7:40` (Rāghavendra Vijaya) — अवनीसुधाशसवनाशभूरुहो वनशैलमाप वनराशितस्ततः / भवनाशनं सपवनाशशायिनं नमन्नैरुपेतुमवने कृतादरम्
  scan `LLGLGLLLGLGLGLLGLGLLLGLGLG|LLGLGLLLGLGLGLGGLGLLLGLGLG` syllables [26, 26]; equal pādas of 26 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_7:43` (Rāghavendra Vijaya) — मधुरे यदीयशिखरेतिभास्वरे मुनयो विमुक्तिगतये समुद्गताः / अनवेक्ष्य हन्त स्रुतिमच्चरादिकान्न भवं व्रजन्ति हरिभक्तिगौरवात्
  scan `LLGLGLLLGLGLGLLGLGLLLGLGLG|LLGLGGLLGLGLGLLGLGLLLGLGLG` syllables [26, 26]; equal pādas of 26 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_7:46` (Rāghavendra Vijaya) — अधि्ताम्रपर्णि स निमज्ज्य तत्तटे लसिताः प्रणम्य नवदेवताः पराः / कृतमालिका सरिदलंकृतामगान्धुराभिधां मधुरवाङ्महापुरीम्
  scan `GGLGLLLGLGLGLLGLGLLLGLGLG|LLGLGLLLGLGLGLGLGLLLGLGLG` syllables [25, 25]; equal pādas of 25 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_7:48` (Rāghavendra Vijaya) — तत्र श्रीरङ्गनाथं तरुणतरणिरुग्वेदंरूपे विमाने कावेरीवारिपूरप्रसृमरपवनानन्दितानन्तभोगे / वन्द्यं देवैश्शयानं द्रुहिणभवमुखैरिष्टदं राघवेन्द्रः सानन्दं तं प्रणम्य प्रकटितविभवं तां निशामत्यनैषीत्
  scan `GGGGLGGLLLLLLGGGGGLGGGGGGLGGLLLLLLGGLGGLGG|GGGGLGGLLLLLLGGLGGLGGGGGGLGGLLLLLLGGLGGLGG` syllables [42, 42]; equal pādas of 42 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_8:18` (Rāghavendra Vijaya) — वल्लरीषु मलयाचलानिलस्पन्दितासु परपुष्टभामिनी / कामदिग्विजयकाहलनादभ्रान्तिदं निगदमातनुते स्म
  scan `GLGLLLGLGLGGLGLLLGLGLG|GLGLLLGLLGGGLGLLLGLLGL` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_8:22` (Rāghavendra Vijaya) — मारुताभिमुखषट्पदमण्डल्याकृतिस्मृतिभवापथिकेषु / अन्तकं मुधतया दिदीशे किं कुण्डलीकृतिरहो कुटिलेन
  scan `GLGLLLGLLGGGLGLLLGLLGL|GLGLLLGLGGGGLGLLLGLLGL` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_8:25` (Rāghavendra Vijaya) — शातकुम्भमयकुम्भकुचानामङ्घ्रिपातमतिदुर्लभमेत्य / संमदेन सहसा किमशोकः कुड्मलैर्भवदथ पुलकाङ्गः
  scan `GLGLLLGLLGGGLGLLLGLLGL|GLGLLLGLLGGGLGLLLLLLGG` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_8:29` (Rāghavendra Vijaya) — मल्लिकायुवतिर्यौवनधाता मन्मथप्रभुपरीभवदाता / काननज्वलूनबालकमातावास्रोजनि सरोजलपाता
  scan `GLGLLGGLLGGGLGLLLGLLGG|GLGLGLGLLGGGGLLLGLLGG` syllables [22, 21]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_8:31` (Rāghavendra Vijaya) — तापयत्यतितरां तरणिर्यल्लोकबन्धुरिति नाम कथं स्यात् / तत्सखस्य शुचिता शुचिमासश्चटका भुवि विचुकुशुरित्थम्
  scan `GLGLLLGLLGGGLGLLLGLLGG|GLGLLLGLLGGLLGLLLLLLGG` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_8:32` (Rāghavendra Vijaya) — छायया सह दिवैव कराग्रैः शम्बरम्बरहरेम्बररले / ज्येष्ठपूर्वमभियायिनि नूनं कोपताम्रनयना नलिनीति
  scan `GLGLLLGLLGGGLGLLLGLLLG|GLGLLLGLLGGGLGLLLGLLGL` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_8:40` (Rāghavendra Vijaya) — वारिदावलितिरोहितमित्रं मानसाभिमुखपाण्डुरपत्रम् / नृत्यदद्रितनयासुतपत्रं दीव्यति स्म दिनमब्जमित्रम्
  scan `GLGLLLGLLGGGLGLLLGLLGG|GLGLLLGLLGGGLGLLLGLGG` syllables [22, 21]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_8:46` (Rāghavendra Vijaya) — व्योम्नि सान्द्रतवारिदवृन्दे विद्युतासु विततासु समन्तात् / पुष्पवत्समुदयावनुमेयो फुल्लमीलितपयोरुहपङ्क्त्या
  scan `GLGLLGLLGGGLGLLLGLLGG|GLGLLLGLLGGGLGLLLGLLGG` syllables [21, 22]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_8:49` (Rāghavendra Vijaya) — स्वामिनिक्षतवसौ दिननाथे यत्पुराजनि दिनेष्वतिकार्श्यम् / तद्विमर्शमधिगम्य दिनानामद्य हृद्यत वासरवृद्धिः
  scan `GLGLLLGLLGGGLGLLLGLLGG|GLGLLLGLLGGGLGLLGLLGG` syllables [22, 21]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_8:60` (Rāghavendra Vijaya) — काम्यकर्मचयभञ्जनहेतूभूतदर्शनमिमं यमिधुर्यम् / वीक्ष्य बिभ्यदिव तत्फलभूतं शालिवृन्दमभवद्व्यनम्रम्
  scan `GLGLLLGLLGGGLGLLLGLLGG|GLGLLLGLLGGGLGLLLGLGG` syllables [22, 21]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_8:65` (Rāghavendra Vijaya) — पद्मिनीमनवलोक्य पतङ्गो मन्ददीधितिरिहास हिमौघैः / रव्यादर्शनवशादिव शोकादब्जिनी च तुहिनैः किमु लीना
  scan `GLGLLLGLLGGGLGLLLGLLGG|GGGLLLGLLGGGLGLLLGLLGG` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_8:66` (Rāghavendra Vijaya) — उष्णारश्मिरधिकं हिमभीतो हव्यवाहदिशमिच्छति गन्तुम् / अग्निरस्त्युत न वेति विवेक्तुं प्रागयादिव समीरणचारः
  scan `GGGLLLGLLGGGLGLLLGLLGG|GLGLLLGLLGGGLGLLLGLLGG` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_8:68` (Rāghavendra Vijaya) — गौतमाघपरिहारिणि तोये स्नानकर्म विरचय्य स विद्वान् / पूजितः प्रतिपदं प्रथितधीभिः प्राविशत्किल पुरीं विजयाख्याम्
  scan `GLGLLLGLLGGGLGLLLGLLGG|GLGLLLGLLLGGGLGLLLGLLGG` syllables [22, 23]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_8:70` (Rāghavendra Vijaya) — स्नातवानथ बुधैः सह कृष्णानिम्नगापयसि निर्जितमारः / तत्तटे जयगुरूक्तटीकां व्याकृतापि यतिराडणुभाष्यं
  scan `GLGLLLGLLGGGLGLLLGLLGG|GLGLLLGLGGGLGLLLGLLGG` syllables [22, 21]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_8:76` (Rāghavendra Vijaya) — प्रहृष्टेन चित्तेन मध्येप्रतोल्यां महावीरविलासेन तात्कालिकेन / भुजङ्गप्रयातेन भूदेववन्द्यो हनुमन्तमित्थं प्रणौति स्म देवम्
  scan `LGGLGGLGGLGGLGGLLGGLGGLGL|LGGLGGLGGLGGLLGLGGLGGLGG` syllables [25, 24]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_8:77` (Rāghavendra Vijaya) — वाद्यैश्चित्रैः शङ्खभेरीमृदङ्गैः फुल्लैः पुष्पैर्विविधमनुजैः कीर्यमाणैः समन्तात् / वीथ्यावीथ्यां युवतिकरगारातर्तिके राघवेन्द्रो रामे पूर्वं प्रविशति मठं प्राविशत्संपदाढ्यम्
  scan `GGGGGLGGLGGGGGGLLLLLGGLGGLGG|GGGGLLLLLGGGLGGLGGGGGGLLLLLGGLGGLGG` syllables [28, 35]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_9:3` (Rāghavendra Vijaya) — पाकशासनपुरे गुरूदितेर्हन्त वेदवचनैरपाकृते / अन्धकारदुरपह्नवगेहे शक्रदिङ्मुखमिदं प्रसीदति
  scan `GLGLLLGLGLGGLGLLLGLGLG|GLGLLLGLLGGGLGLLLGLGLL` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_9:8` (Rāghavendra Vijaya) — व्योमनामभृति कुम्भसंभवे वारिधिं पिबति शार्वराभिधम् / औषसारुणिमदम्भतः शनैः पद्मरागनिकरो विजृम्भत्
  scan `GLGLLLGLGLGGLGLLLGLGLG|GLGLLLGLGLGGLGLLLGLGG` syllables [22, 21]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_9:15` (Rāghavendra Vijaya) — अन्धकाररिपुभूमिभृद्दृणं जेतुमुत्कमनसो विभावसोः / वन्दिनो नु बिरुदालिवाचकाः प्रागविशन्ति मुखरा विहङ्गमाः
  scan `GLGLLLGLGLGGLGLLLGLGLG|GLGLLLGLGLGGLLGLLLGLGLG` syllables [22, 23]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_9:20` (Rāghavendra Vijaya) — एवमादिमगधोक्तिमाधुरीवारिपूरकृतसेचनदिव / बोधमेत्य यतिराट् समुत्थितो द्वोपिचर्ममयतल्पतल्लजात्
  scan `GLGLLLGLGLGGLGLLLGLLLL|GLGLLLGLGLGGLGLLLGLGLG` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_9:21` (Rāghavendra Vijaya) — द्वादशस्तुतिपुराणसंततीः श्रोतुमाननसमूहमेकदा / स्वं दशाधिकनवाननोदिशद्विश्वमूर्तिरिव चक्षुरागत्ः
  scan `GLGLLLGLGLGGLGLLLGLGLG|GLGLLLGLGLGGLGLLLGLGG` syllables [22, 21]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_9:24` (Rāghavendra Vijaya) — सोधिरुह्य शिबिकां गजेन्द्रमुत्तयुक्तिसंस्तुतिकृतादरः शनैः / स्नातुमभ्युपगतस्तरङ्गिणीं दक्षिणापथनिलिम्पनिम्नगात्
  scan `GLGLLLGLGLGLGLGLLLGLGLG|GLGLLLGLGLGGLGLLLGLGLG` syllables [23, 22]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_9:26` (Rāghavendra Vijaya) — यां प्रवाललहरीं मनोहरामुद्वहन्त्यधिवसन्तम्बुधौ / तीरचम्पकसुमोत्करा लसन्त्युत्सवाय कृतदीपिका इव
  scan `GLGLLLGLGLGGLGLLLGGLG|GLGLLLGLGLGGLGLLLGLGLL` syllables [21, 22]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_9:30` (Rāghavendra Vijaya) — कल्पिताचमनमत्र सादरं स्नानकर्म कुरुते स्म शास्त्रतः / अष्टषड्द्विपदक्षैरहरेर्मानितैर्मनुवरैस्त्रिधा क्रमात्
  scan `GLGLLLGLGLGGLGLLLGLGLG|GLGLLGGLLGGLGLLLGLGLG` syllables [22, 21]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_9:32` (Rāghavendra Vijaya) — उच्चरन्प्रणवमुत्थितोसिचत् स्वात्मगं पुरुषसूक्ततो हरिम् / विष्णुपदसलिलं पिबन् सुरास्तर्पितानकृत मन्त्रवारिभिः
  scan `GLGLLLGLGLGGLGLLLGLGLG|GLLLLLGLGLGGLGLLLGLGLG` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_9:33` (Rāghavendra Vijaya) — सालमलकमवस्तलोहिते वाससी तदनु संयमीश्वरः / ऊर्ध्वपुण्ड्रमतनिष्ट गोपिकाचन्दनेन सहपञ्चमुद्रिकम्
  scan `GLLLLLGLGLGGLGLLLGLGLG|GLGLLLGLGLGGLGLLLGLGLG` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_9:35` (Rāghavendra Vijaya) — तत्तटोपवनमेत्य पावनीः सोश्रृणोद् द्विजमुखात्कथां हरेः / आदिदैशिकसमर्चितोपलव्यासूमूर्तिपरिपूजनोत्सुकः
  scan `GLGLLLGLGLGGLGLLLGLGLG|GLGLLLGLGLGGGGLLLGLGLG` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_9:39` (Rāghavendra Vijaya) — पावयन्नथ महीं पदेपदे पार्वतींशमभिवन्द्य पङ्क्तौ / प्राविशत्ससुर विष्टपागमो मूर्तिमानिव मठं तथागमः
  scan `GLGLLLGLGLGGLGLLLGLGG|GLGLLLGLGLGGLGLLLGLGLG` syllables [21, 22]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_9:45` (Rāghavendra Vijaya) — अत्र कश्चिदमभ्यचोदयच्छुद्धमस्य विषयं स्वमानसम् / शुद्धवेदनफलं वदेन्न चेद्धन्धभङ्ग इति किं ततो वद
  scan `GLGLLGLGLGGLGLLLGLGLG|GLGLLLGLGLGGLGLLLGLGLL` syllables [21, 22]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_9:49` (Rāghavendra Vijaya) — अत्र तद्भ्रमनिरासनोत्सुकः सस्मितं सदयमब्रवीद्गुरुः / अस्ति किंचिद्हमर्थतः परं विष्णुनाम गुणपूर्णम तम्
  scan `GLGLLLGLGLGGLGLLLGLGLG|GLGGLGLGLGGLGLLLGLLG` syllables [22, 20]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_9:53` (Rāghavendra Vijaya) — वक्राम्भोजं विधत्ते मम सुहृदमिति प्राप्तरॊषो विवस्वान् म्लानं मीनेक्षणानां नयनयुगमयं क्लपयन्न्लब्णश्रीः / तच्छायाधारिणोस्मानपि तपति मुहुस्तं समाधेहि पाही- त्यारादम्भोजिनीनां शकुलकुलमयादाकुलं पादमूलम्
  scan `GGGGLGGLLLLLLGGLLGLGGGGGGLGGLLLLLLGLLGGGG|GGGGLGGLLLLLLGGLGGLGGGGGGLGGLLLLLLGGLGGLGG` syllables [41, 42]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose

### Part C batch 7 (items 241–280)

* `raghavendra_vijaya:sarga_9:54` (Rāghavendra Vijaya) — माद्यन्दिनस्नानकृते महान्तं मुनीन्द्रमित्थं किल कालशंसी / आगत्य मध्यन्दिनस्नानमस्मै न्यवेदयत्प्राप्तमहत्सचेताः
  scan `GGLGGLLGLGGLGLGGLLGLGG|GGLGGLGGLGGLGLGGLLGLGG` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_9:56` (Rāghavendra Vijaya) — निष्कुटविलसत्पुष्करवत्यां पुष्कलकीर्तिर्मस्करिधुर्यः / साधु निमज्ज्य सुधीजनमान्यो माधवमङ्गलगेहमयासीत्
  scan `GLLLLGGLLGGGLLGGGLLGG|GLLGLLGLLGGGLLGLLGLLGG` syllables [21, 22]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_9:60` (Rāghavendra Vijaya) — स्वत कवेरजापयोनघं हि किं पुनर्हरेः / पदं समाश्रितं चतुःपुमर्थदं भवेदिति
  scan `LLLGLGLGLGLGLGLG|LGLGLGLGLGLGLGLL` syllables [16, 16]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: पञ्चचामर (1 भेदौ)
* `raghavendra_vijaya:sarga_9:61` (Rāghavendra Vijaya) — पश्चात्कृत्वा हरिपादनतिं संयमीन्द्रोथ भुक्त्वा पुण्यं भैक्ष्यं तदनुरचयन् तर्कशब्दादिशास्त्रैः / विद्वद्वपूर्वाविधनगरात्प्राप्तवद्भिर्विनोदं ध्यायन्विष्णुं समयमनयत्सोयमासायमेवम्
  scan `GGGGLLGLLGGLGGLGGGGGGLLLLLGGLGGLGG|GGLGGLLLLGGLGGLGGGGGGLLLLLGGLGGLGG` syllables [34, 34]; equal pādas of 34 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_9:62` (Rāghavendra Vijaya) — श्रीमत्कश्यपवंशवार्धिशशिनः षड्दर्शनीवल्लभ श्रीलक्ष्मीनरसिंहवित्तविदुषः श्रीवेङ्कटाम्बामणौ / जातेनार्यदयासुधामयगिरा नारायणेनोदिते काव्ये चारुणि राघवेन्द्रविजये सर्गोभवन्नवमः
  scan `GGGLLGLGLLLGGGLGGLGGGGLLGLGLLLGGGLGGLG|GGGLLGLGLLLGGGLGGLGGGGLLGLGLLLGGGLGLLG` syllables [38, 38]; equal pādas of 38 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_10:25` (Rāghavendra Vijaya) — विप्रयुक्तसुदृशां विनयार्थं ध्वान्तकल्पजलधावभिवृद्धे / बिभ्रन्नश्रियमवापुरुडूनां ज्योतिरिङ्गणगणस्फुरणानि
  scan `GLGLLLGLLGGGLGLLLGLLGG|GGGLLLGLLGGGLGLLLGLLGL` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_10:26` (Rāghavendra Vijaya) — मारकारुकृताधतमिस्रं गोलमब्धिनलिनीविरहाग्नेः / ऊर्मिभस्त्रपवनैरतितप्तं शीतरश्म्युदयरागमिषेण
  scan `GLGLLGLLGGGLGLLLGLLGG|GLGLLLGLLGGGLGLLLGLLGL` syllables [21, 22]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_10:28` (Rāghavendra Vijaya) — पूर्वसिन्धुसलिलेन निषेक्तुं तारकाङ्कुरततिं ततरश्मि / इन्दुबिम्बपिटकं किमु दने दक्षिणोत्तरहरित्परिणीभ्याम्
  scan `GLGLLLGLLGGGLGLLLGLLGL|GLGLLLGLLLGGLGLLLGLLGG` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_10:36` (Rāghavendra Vijaya) — पूर्वशैलवृषभाचलदृशयं देवतीर्थमधिगम्य सुधांशुम् / हृष्यतोस्य भुवनस्य न मोघं चन्द्रिकात्मसुकृतत्वमयासीत्
  scan `GLGLLLGLLLLGGLGLLLGLLGG|GLGLLLGLLGGGLGLLLGLLGG` syllables [23, 22]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_10:37` (Rāghavendra Vijaya) — विष्टपे विधुरुचा विद्धाने क्षीरसागरनिमज्जनकेलिम् / पाठकर्म स समाप्य सरस्यां मङ्गुमन्त उदयुङ्क्त यतीन्द्रः
  scan `GLGLLLGGGGGLGLLLGLLGG|GLGLLLGLLGGGLGLLLGLLGG` syllables [21, 22]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_10:43` (Rāghavendra Vijaya) — आत्मनैव कमठेन वितन्वन्मन्दरेण च भवानरणी द्वे / मथनतोत्थितहलाहलवह्निं होतुमिन्द्ररिपुवृन्दहवींषि
  scan `GLGLLLGLLGGGLGLLLGLLGG|LLLGLLLGLLGGGLGLLLGLLGL` syllables [22, 23]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_10:46` (Rāghavendra Vijaya) — तावकं नरहरेऽतिविरुद्धं वेषधारणमिदं तनुते नः / अत्यसंघाटितकर्म च कृत्वा पालये प्रणतमित्युपदेशम्
  scan `GLGLLLGLLGGGLGLLLGLLGG|GLGGLLGLLGGGLGLLLGLLGG` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `raghavendra_vijaya:sarga_10:51` (Rāghavendra Vijaya) — बन्धनाय कृतमात्मजनन्या तादृशं च गुणमङ्गचकरोर्यत् / तेन निर्गुणमतानि निरस्यन्दर्शयस्यपि निजां गुणवत्ताम्
  scan `GLGLLLGLLGGGLGLLLGLLLGG|GLGLLLGLLGGGLGLLLGLLGG` syllables [23, 22]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_10:53` (Rāghavendra Vijaya) — त्वं कुचेलमुनिमीश कुचेलाद्यर्पणेन कृतवान्कुचेलम् / सोभवत्तदपि चारुकुचेलालंकृतस्तदिदमद्भुतमासीत्
  scan `GLGLLLGLLGGGLGLLLGLGG|GLGLLLGLLGGGLGLLLGLLGG` syllables [21, 22]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `raghavendra_vijaya:sarga_10:60` (Rāghavendra Vijaya) — संचरन् शिखिमुखोरगपीतस्वाश्वयानिललयातत्सघनेषु / सम्पतत्सु पतितो भुवि सिद्धा विस्मयं दधति हन्त यदन्तः
  scan `GLGLLLGLLGGGLGLLLGGLLGL|GLGLLLGLLGGGLGLLLGLLGG` syllables [23, 22]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `tirtha_prabandha:TP_DAK_003` (Tīrtha Prabandha) — श्रीरंगनाथः सुरसिद्धगीतः कारुण्यसिधुः कविवर्गबंधुः / स्मेरास्यचंद्रः स्मरतां महेंद्रक्ष्मारुट् प्रसन्नः क्षपयत्वघं नः
  scan `GGLGGLLGLGGGGLLGLLGLGG|GGLGGLLGLGGGGLGGLLGLGG` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `tirtha_prabandha:TP_DAK_015` (Tīrtha Prabandha) — सीत्तामात्मसुतां खलैरपहृत्तामानेष्यतः स्वां पुरीं / जामातुर्हितकारिणीव धरणी वार्ध्यंबुवृद्धाकृतिः / भूभारक्षपणोद्यतस्य सचिवीभूता महीध्रा इब / श्रीरामस्य भटैः कृतो विजयते सेतुर्विजेतुर्द्विषाम्
  scan `GGGLLGLGLLGGGGLGGLG|GGGLLGLGLLLGGGLGGLG|GGGLLGLGLLLGGGLGGLL|GGGLLGLGLLLGGGLGGLG` syllables [19, 19, 19, 19]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: शार्दूलविक्रीडित (1 भेदौ)
* `tirtha_prabandha:TP_DAK_017` (Tīrtha Prabandha) — न मूर्च्छति शिलोच्चये पवनवेग इत्यज्ञवाग् / यतो हनुमताऽऽहृताः सुबहवो मरुसूत्नुना / गभीरतरवारिधिच्छदनचुंचवः पर्वता / जयंति कृतसेतवः क्षपणहेतवो रक्षसाम्
  scan `LGLLLGLGLLLGLGGLG|LGLLLGLGLLLGLLGLG|LGLLLGLGLLLGLGGLG|LGLLLGLGLLLGLGGLG` syllables [17, 17, 17, 17]; equal pādas of 17 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `tirtha_prabandha:TP_DAK_021` (Tīrtha Prabandha) — कामद्विषं कामितदानदक्षं श्रीमज्जटाजूटविभासिगंगम् / रामेश्वरं रामकृतप्रतिष्ठं रामगृहीतार्धतनुं नतोऽस्मि
  scan `GGLGGLLGLGGGGLGGLLGLGG|GGLGGLLGLGGGLLGGLLGLGL` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `tirtha_prabandha:TP_DAK_022` (Tīrtha Prabandha) — कल्पांते सुरभूसुरासुरमुनिस्तोमं हरन् कं हरं / पृथ्व्यां पातककोटिपाटनपूट रामः समाराधयत् / यत्पादाब्जरजोऽहरन्मुनिवधूपापं श्रुता यत्कथा / मुक्तिं दोग्धि परेशितुः परमियं लीला खलध्वंसिनः
  scan `GGGLLGLGLLLGGGLGGLG|GGGLLGLGLLGLGGLGGLG|GGGLLGLGLLLGGGLGGLG|GGGLLGLGLLLGGGLGGLG` syllables [19, 19, 19, 19]; equal pādas of 19 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `tirtha_prabandha:TP_DAK_036` (Tīrtha Prabandha) — इंद्रशौचविधानात्ते न शुचींद्रातिपौरुषमू / अर्निद्रस्यमनश्शौचं मम कृत्वा तदार्जय
  scan `GLGLLGGGLLGGLGLLG|GGGLLGGGLLGGLGLL` syllables [17, 16]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `tirtha_prabandha:TP_DAK_044` (Tīrtha Prabandha) — यथा गुहामुखे नाथ शेषे शेषे रमापते / तथा हार्दगुहामध्यासीनो रमस्व मे
  scan `LGLGLGGLGGGGLGLG|LGGLLGGGGGLGLG` syllables [16, 14]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `tirtha_prabandha:TP_DAK_045` (Tīrtha Prabandha) — सुरगणपरिवारः शोभमानोरुहारः करिकरसमहस्तः कांचनोद्दीप्तवस्त्रः / शुभजनकृतगानः शेषभोगे शयानः प्रभुरयमविनाशः प्रीयतादिंरेशः
  scan `LLLLLLGGGLGGLGGLLLLLLGGGLGGLGG|LLLLLLGGGLGGLGGLLLLLLGGGLGGGG` syllables [30, 29]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `tirtha_prabandha:TP_PAS_007` (Tīrtha Prabandha) — काशीतले कृतपदाऽपि सरित् सुराणामायाति यद्गतपवित्ररोऽधुनाऽपि / रुद्रादिदेवगणसेवितसर्वभागं तद्रूप्यपीठपुरमप्रतिमं त्रिलोक्याम्
  scan `GGLGLLLGLLGLGGGGLGLLLGLGLGL|GGLGLLLGLLGLGGGGLGLLLGLLGLGG` syllables [27, 28]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `tirtha_prabandha:TP_PAS_022` (Tīrtha Prabandha) — अंगानुषंगतभुजंगमतुंगभोगं गंगातरंगकृतमंगलमौलिभागम् / संगीतलोलयतिपुंगवगीतगाथं त गौर्यपांगरसमाश्रय विश्वनाथम्
  scan `GGLGLLLGLLGLGGGGLGLLLGLLGLGG|GGLGLLLGLLGLGGLGLGLLLGLLGLGG` syllables [28, 28]; equal pādas of 28 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `tirtha_prabandha:TP_PAS_024` (Tīrtha Prabandha) — वंदारुनारदसनंदनमुख्ययोगिवृदैः प्रवंद्यचरतितैः परितश्च सेव्यम् / इंदिंदिरोपमसितेतरकंठकांतिं सौंदर्यमूर्तिममुमाश्रय विश्वनाथम्
  scan `GGLGLLLGLLGLGLLGLGLLLLGLLGLGG|GGLGLLLGLLGLGGGGLGLLLGLLGLGG` syllables [29, 28]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `tirtha_prabandha:TP_PAS_025` (Tīrtha Prabandha) — छंदश्चयस्तुतचरित्र पुरत्रयारे कुंदप्रसूनकृतसेवनतृप्तचित्त / त्वां दीनबंधुमरुणेंदुलत्कपर्दं वंदेऽरिमर्दन सुहृद्धन विश्वनाथ
  scan `GGLGLLLGLLGLGGGGLGLLLGLLGLGL|GGLGLLLGLGLGGGGLGLLLGLLGLGL` syllables [28, 27]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `tirtha_prabandha:TP_PAS_026` (Tīrtha Prabandha) — नन्दिकेश्वरः / सुचारुकर्णलांगूलशृंगांघ्य्ग्रुदरदृङ्मुखम् / ककुद्मंतं वृषं श्वेतं नौमि शंकरवाहनम्
  scan `GLGLG|LGLGLGGLGGLLLGLG|LGGGLGGGGLGLLGLG` syllables [5, 16, 16]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose; nearest: प्रिया (1 भेदौ), प्रीति (1 भेदौ), पङ्क्ति (2 भेदौ)
* `tirtha_prabandha:TP_PAS_053` (Tīrtha Prabandha) — श्रुतिशतवर्णितचरितं यतिहृन्निरतं यथेष्टगुणभरितम् / किंकरवरदमनिंद्यं शंकरनारायणं वंदे
  scan `LLLLGLLLLGLLGLLGLGLLLLLG|GLLLLLLGGGLLGGLGGG` syllables [24, 18]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `tirtha_prabandha:TP_PAS_054` (Tīrtha Prabandha) — शूलसुदर्शनसुरुचं बालेंदूज्वलकिरीटशोभितशिरसम् / पंकजमुखकरचरणं शंकरनारायणं वंदे
  scan `GLLGLLLLGGGGLLLGLGLLLLG|GLLLLLLLLGGLLGGLGGG` syllables [23, 19]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `tirtha_prabandha:TP_PAS_055` (Tīrtha Prabandha) — पीनोरुकटिसुनाभं ध्यानार्होरःस्थिताहिफणहारम् / शंखाभ्रवर्णमनघं शंकरनारायणं बंदे
  scan `GGLLLLGGGGGGLGLLLGG|GGLGLLLGGLLGGLGGG` syllables [19, 17]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `tirtha_prabandha:TP_PAS_059` (Tīrtha Prabandha) — मुरपुरहर लक्ष्मीपार्वतीकेलिलोल स्फुरदसितासितांगासह्यचक्रत्रिशूल / परतरगुरुमूर्ते पावनापारकीर्ते हरिहर तव पादांभोजयुग्मं नतोऽस्मि
  scan `LLLLLLGGGLGGLGGLLLLGLGGGLGGLGL|LLLLLLGGGLGGLGGLLLLLLGGGLGGLGL` syllables [30, 30]; equal pādas of 30 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `tirtha_prabandha:TP_PAS_066` (Tīrtha Prabandha) — मध्यस्थकृष्ण परिपालय भक्तवर्गं रुद्राश्रिताग्र रुजमर्दंय सेवकस्य / पद्मासनावसथमूल सृजास्य तंतुं सद्वंद्य पिप्पलतरो वितराखिलेष्टम्
  scan `GGLGLLLGLLGLGGGGLGLLLGGLGLGL|GGLGLLLGLLGLGGGGLGLLLGLLGLGG` syllables [28, 28]; equal pādas of 28 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `tirtha_prabandha:TP_PAS_067` (Tīrtha Prabandha) — तुंगातरंगपरिनर्तनपूतवात / संगेन तेंऽघ्रिप दलानि चलंति भांति / जन्मांतरोत्थदृढम्लदुरंतदुष्कृ / त्युन्मूलनोद्यतकरांगुलिकांतिमंति
  scan `GGLGLLLGLLGLGL|GGLGLLLGLLGLGL|GGLGLLGLLGLGL|GGLGLLLGLLGLGL` syllables [14, 14, 13, 14]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose; nearest: वसन्ततिलका (1 भेदौ)
* `tirtha_prabandha:TP_PAS_071` (Tīrtha Prabandha) — वरदातीरस्थ मधुलिंगम् / हर सायकनिर्दग्धपुर गायकधूर्धर / सुरनायक दैत्येंद्रवरदायक पाहि माम्
  scan `LLGGGLLLGG|LLGLLGGLLLGLLGLL|LLGLLGGLLLGLLGLG` syllables [10, 16, 16]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `tirtha_prabandha:TP_PAS_072` (Tīrtha Prabandha) — हे धर्मगंगे पापौघभंगे तुङ्गतरंगिणि / चेतो मदीयं सद्धर्मकर्मण्येव रिथरं कुरु
  scan `GGLGGGGLGGGLLGLL|GGLGGGGLGGGLLLGLL` syllables [16, 17]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `tirtha_prabandha:TP_PAS_081` (Tīrtha Prabandha) — गोकर्णभासितांगः प्रत्युपकुर्वन्निवांबिकारमणः / गोकर्णसंज्ञमधुना भासयति क्षेत्रमंबुधेस्तीरे
  scan `GGLGLGGGLLGGLGLGLLG|GGLGLLLGGLLGGLGLGGG` syllables [19, 19]; equal pādas of 19 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `tirtha_prabandha:TP_PAS_085` (Tīrtha Prabandha) — ध्याताऽऽध्यातांतशांतप्रियजनविभावायान्वहं या हृदंतः / ख्याताख्यातादृशाभ्युन्नतिवितरणशक्त्यालया या पयोब्धेः / जाताऽजातादिदेवव्रजमनुजततेः श्रेयसे भूयसे सा / माता मातापासाराधितपदकमलाऽधोक्षजप्रेयसी स्यात्
  scan `GGGGLGGLLLLLGGGLGGLGG|GGGGLGGLLLLLLGGLGGLGG|GGGGLGGLLLLLLGGLGGLGG|GGGGGGGLLLLLLGGLGGLGG` syllables [21, 21, 21, 21]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: स्रग्धरा (1 भेदौ)
* `tirtha_prabandha:TP_PAS_090` (Tīrtha Prabandha) — विश्वंभरां घनतरामपि भूरियत्नैर्निर्भिद्य यत्पदमुपेत्य बलींद्रगेहात् / आस्ते त्रिव्क्रमतनुर्हरिरद्वितीया सा द्वारकेप्सितपुमर्थकरी पुरी नः
  scan `GGLGLLLGLLGLGGGGLGLLLGLLGLGG|GGGLLLGLLGLGGGGLGLLLGLLGLGG` syllables [28, 27]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `tirtha_prabandha:TP_PAS_092` (Tīrtha Prabandha) — सगदोऽपि ह्यसौ देवः संसारे ह्यगदतामगात् / त्रिविक्रमोऽप्यसौ योगिमनसोऽविक्रमोऽभवत्
  scan `LLGGLGGGGGGLLLGLG|LGLGLGGLLLGGLGLG` syllables [17, 16]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose

### Part C batch 8 (items 281–320)

* `tirtha_prabandha:TP_PAS_097` (Tīrtha Prabandha) — फाले यल्लिखितं धुनोति विविधां रेखां विधात्रा कृतां / यल्लीलातिलकीकृत वितनुते विद्वल्ललामायितान् / ऊर्ध्वं यद्धृतमुच्चलोकपदवीसोपानमन्वेति तद् / गोपीचंदनमंजसा विजयते तापत्रयध्वंसनम्
  scan `GGGLLGLGLLLGGGLGGLG|GGGLLGLLLLLGGGLGGLG|GGGLLGLGLLLGGGLGGLG|GGGLLGLGLLLGGGLGGLG` syllables [19, 19, 19, 19]; equal pādas of 19 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `tirtha_prabandha:TP_PUR_002` (Tīrtha Prabandha) — जगन्नाथः / जगन्नाथो विजयते जगतामर्चितः सदा / ज्ञानाख्यरम्यपरशोर्यं दारु जगुरागमाः
  scan `LGGG|LGGGLLLGLLGGLGLG|GGLGLLLGGGLLLGLG` syllables [4, 16, 16]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose; nearest: कन्या (1 भेदौ), लासिनी (1 भेदौ), सती (2 भेदौ)
* `tirtha_prabandha:TP_PUR_003` (Tīrtha Prabandha) — मल्लिकार्जुनः / श्रीपर्वतकृतावासो भातीशो मल्लिकार्जुनः / बद्धस्वीयजटाजूटमध्यस्थ इव चंद्रमाः
  scan `GLGLG|GGLLLGGGGGGGLGLG|GGGLLGGLGGLLLGLG` syllables [5, 16, 16]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose; nearest: प्रिया (1 भेदौ), प्रीति (1 भेदौ), पङ्क्ति (2 भेदौ)
* `tirtha_prabandha:TP_PUR_005` (Tīrtha Prabandha) — यस्तंभे प्रकटीबभूव स मयि स्तंभायितेऽति स्फुटी / भूयाद्यो भवनाशिनीतटगतछिंद्यात् स मेऽमुं भवम् / योऽपाद्बालकमप्यसौ नरहरिर्मां बालिशं पातु यो / रक्षोः शिक्षदसौ प्रभुः खलकुलं शिक्षेदरूक्षप्रियः
  scan `GGGLLGLGLLLGGGLGGLG|GGGLLGLGLLLLGGLGGLG|GGGLLGLGLLLGGGLGGLG|GGGLLGLGLLLGGGLGGLG` syllables [19, 19, 19, 19]; equal pādas of 19 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `tirtha_prabandha:TP_PUR_007` (Tīrtha Prabandha) — विदारितरिपूदरप्रकटितांत्रमालाधरं / तदात्मजमुदावहप्रियतरोग्रलीलाकरम् / उदाररवपूरीतांबुजभवांडभांडांतरं / सदा नरहरिं श्रये नखनव्यवज्रांकुरम्
  scan `LGLLLGLGLLLGLGGLG|LGLLLGLGLLLGLGGLG|LGLLLGGGLLLGLGGLG|LGLLLGLGLLGLGGLG` syllables [17, 17, 17, 16]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `tirtha_prabandha:TP_PUR_012` (Tīrtha Prabandha) — तटिनीषु तुंगभद्रे स्वादूदकसंकुला त्वमसि नूनम् / कस्मात्तीर्थपदोऽसौ धत्ते त्वामेव दंष्ट्रयोर्नो चेत्
  scan `LLGLGLGGGGLLGLGLLLGG|GGGLLGGGGGGLGLGGG` syllables [20, 17]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `tirtha_prabandha:TP_PUR_014` (Tīrtha Prabandha) — विरूपाक्षः / पंपाध्यक्षो विरुपाक्षः संपदे स्यात्सतां सदा / यो हेमगिरिसीमायां राजते राजशेखरः
  scan `LGGG|GGGGLLGGGLGGLGLG|GGLLLGGGGLGGLGLG` syllables [4, 16, 16]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose; nearest: कन्या (1 भेदौ), लासिनी (1 भेदौ), सती (2 भेदौ)
* `tirtha_prabandha:TP_PUR_018` (Tīrtha Prabandha) — माध्वग्रंथान् स्वबंधूनिव सहसहृदाऽऽलिंग्य विज्ञातभावः / संयोज्यालंकृताभिः स्वसहजमतिसंभूतवाग्भिर्वधूभिः / कृत्वाऽन्योक्तीश्च दासीर्बुधाहृदयगृहं प्रौडवृत्तीश्च वृत्ती / र्दत्वाऽन्योन्याभियोगं जयमुनिरसकृद्वीक्ष्य रेमे कृतार्थः
  scan `GGGGLGGLLLLLLGGLGGLGG|GGGGLGGLLLLLLGGLGGLGG|GGGGLGGLGLLLLGGLGGLGG|GGGGLGGLLLLLLGGLGGLGG` syllables [21, 21, 21, 21]; equal pādas of 21 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `tirtha_prabandha:TP_PUR_025` (Tīrtha Prabandha) — शंकररविशशिमुख्याः किंकरपदवीमुपाश्रिता यस्य / वेंकटगिरिनाथोऽसौ पंकजनयनः परात्परो जयति
  scan `GLLLLLLGGGLLLLGLGLGGL|GLLLLGGGGLLLLGLGLGLLL` syllables [21, 21]; equal pādas of 21 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `tirtha_prabandha:TP_UTT_002` (Tīrtha Prabandha) — गुरुं कन्यागतं धन्या या पुरस्कृत्य सेव्यसे / श्रीकृष्णवेणि पापानि सा त्वं पुण्ययासि ध्रुवम्
  scan `LGGGLGGGGLGGLGLG|GGLGLGGLGGGLGGLG` syllables [16, 16]; equal pādas of 16 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `tirtha_prabandha:TP_UTT_006` (Tīrtha Prabandha) — तीरे सत्सरितस्तिरस्कृतधनासक्तिप्रियः / पादांभोजमिदं मदंकसहितः संचितयांतर्हृदि / पश्चात् ते कटिमात्र एव भविता संसारवार्धिर्न चे / च्छिक्षामीति हि लक्षयत्यनुदिनं स्वावस्थया विठ्ठलः
  scan `GGGLLGLGLLLGGGLG|GGGLLGLGLLLGGLLGGLL|GGGLLGLGLLLGGGLGGLG|GGGLLGLGLLLGGGLGGLG` syllables [16, 19, 19, 19]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `tirtha_prabandha:TP_UTT_009` (Tīrtha Prabandha) — विप्रर्षिंदेवकुलसंकुलतीरयुग्मा विद्राविताघतृणरेणुकणा स्ववातैः / स्वादूदकैः प्रशमिताखिललोकशोका गोदावरी शुभकरी सरिदुद्धरेन्नः
  scan `GGGGLLLGLLGLGGGGLGLLLGLLGLGG|GGLGLLLGLLGLGGGGLGLLLGLLGLGG` syllables [28, 28]; equal pādas of 28 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `tirtha_prabandha:TP_UTT_010` (Tīrtha Prabandha) — अहांसि हंसि सततं किल रासि पुण्यं / सिंहस्थिते सुरगुरौ न तदंब याचे / गोदे समस्तफलदे दिश कृष्णपादे / भक्तिं विरक्तिमितरत्र परत्र मुक्तिम्
  scan `LGLGLLLGLLGLGG|GGLGLLLGLLGLGG|GGLGLLLGLLGLGG|GGLGLLLGLLGLGG` syllables [14, 14, 14, 14]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: वसन्ततिलका (1 भेदौ)
* `tirtha_prabandha:TP_UTT_012` (Tīrtha Prabandha) — कालिंदि त्वमघान्वितानपि सतः कृत्वा पवित्रात्मनो / गंतुं नैव कदापि मुंचसि तव भ्रातुनिंकेतं प्रति / किंतु क्षीरपयोधिवासनिरतान् प्रीत्या करोष्याश्रितान् / स्निग्धे भर्तरि कामिनीजनरुचिस्तत्पक्ष एव ह्यलम्
  scan `GGGLLGLGLLLGGGLGGLG|GGGLLGLGLLLGGLGGGLL|GGGLLGLGLLLGGGLGGLG|GGGLLGLGLLLGGGLGGLG` syllables [19, 19, 19, 19]; equal pādas of 19 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `tirtha_prabandha:TP_UTT_014` (Tīrtha Prabandha) — प्र्यागमाधवो भूयाद्दयावारिनिधिर्हृदि / प्रकृष्टयागसदृशी सकृद्यस्य हि संस्मृतिः
  scan `GLGLGGGLGGLLGLL|LGLGLLLGLGGLLGLG` syllables [15, 16]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `tirtha_prabandha:TP_UTT_017` (Tīrtha Prabandha) — अज्ञानाद्यदि सज्जनेषु रचितद्रोहान्मया स्वर्धुनि / स्वस्फूर्त्या सुजनेषु दूषणगणारोपादवज्ञा तव / तर्हि त्वां सगरात्मजास्थिनिकरा जानंति किं तैः प्रभौ / द्रोहः किं न कृतः किमंब न हरावरोपिता चोरता
  scan `GGGLLGLGLLLGGGLGGLL|GGGLLGLGLLLGGGLGGLL|GGGLLGLGLLLGGGLGGLG|GGGLLGLGLLLGLGLGGLG` syllables [19, 19, 19, 19]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: शार्दूलविक्रीडित (1 भेदौ)
* `tirtha_prabandha:TP_UTT_029` (Tīrtha Prabandha) — विष्णुपादः / यद्यात्रा पितृमंडलस्य तनुते वैकुंठयात्रां परां / यत्र क्षिप्ततिला महांति तिलशः कुर्वंति पापान्यहो / पिण्डो यत्र समर्पितो यमभटान् पिंडीकरोत्यक्षता / मर्त्यं स्माक्षतमीड्यतां स्तुतिततिस्तं विष्णुपादं भजे
  scan `GLGG|GGGLLGLGLLLGGGLGGLG|GGGLLGLGLLLGGGLGGLG|GGGLLGLGLLLGGGLGGLG|GGGLLGLGLLLGGGLGGLG` syllables [4, 19, 19, 19, 19]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose; nearest: कन्या (1 भेदौ), सती (2 भेदौ)
* `tirtha_prabandha:TP_UTT_036` (Tīrtha Prabandha) — मुनींद्रमानसावालरूढकृष्णकथलता / विभाति नैमिषारण्यमही सर्वमहीयसी
  scan `LGLGLGGLGLGLLLLG|LGLGLGGLLGGLLGLG` syllables [16, 16]; equal pādas of 16 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `PrahladaKrutaNarasimha:PrahladaKrutaNarasimha:6` (Prahlāda-kṛta Narasiṃha Stotra) — सर्वे ह्यमी विधिकरास्तव सत्त्वधाम्नो / ब्रह्मादयो वयमिवेश न चोद्विजन्तः / क्षेमाय भूतय उत आत्मसुखाय चास्य / विक्रीडितं भगवतो रुचिरावतारैः
  scan `GGLGLLLGLLGLGG|GGLGLLLGLLGLGG|GGLGLLLLGLLGLGL|GGLGLLLGLLGLGG` syllables [14, 14, 15, 14]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `nakha_stuti:NNS_C01_V01` (Nakha Stuti) — पान्त्वस्मान् पुरुहूतवैरिबलवन्मातङ्गमाद्यद्घटाकुम्भोच्चाद्रिविपाटनाधिकपटुप्रत्येकवज्रायिताः / श्रीमत्कण्ठीरवास्यप्रततसुनखरादारितारातिदूरप्रध्वस्तध्वान्तशान्तप्रविततमनसा भाविता भूरिभागैः
  scan `GGGLLGLGLLLGGGLGGLGGGGLLGLGLLLGGGLGGLG|GGGGLGGLLLLLLGGLGGLGGGGGGLGGLLLLLLGGLGGLGG` syllables [38, 42]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C03_V02` (Dvādaśa Stotra) — न ततोस्त्परं जगतीड्यतमं परमात् परतः पुरुषोत्तमतः / तदलं बहुलोकविचिन्तनया प्रवणं कुरु मानसमीशपदे
  scan `LLGLGLLGLLGLLGLLGLLGLLG|LLGLLGLLGLLGLLGLLGLLGLLG` syllables [23, 24]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose; nearest: हंसगति (1 भेदौ)
* `dvadasha_stotra:DDS_C03_V06` (Dvādaśa Stotra) — न कर्मविमामलकालगुणप्रभृतीशमचित्तनु तद्धि यतः / चिदचित्तनु सर्वमसौ तु हरिर्यमयेदिति वैदिकमस्ति वचः
  scan `LGLLGLLGLLGLLGLLGLLGLLG|LLGLLGLLGLLGLLGLLGLLGLLG` syllables [23, 24]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose; nearest: हंसगति (1 भेदौ)
* `dvadasha_stotra:DDS_C04_V01` (Dvādaśa Stotra) — निजपूर्णसुखामितबोधतनुः परशक्तिरनन्तगुणः परमः / अजरारमरणः सकलार्तिहरः कमलापतिरीड्यतमोवतु नः
  scan `LLGLLGLLGLLGLLGLLGLLGLLG|LLGLLLGLLGLLGLLGLLGLLGLLG` syllables [24, 25]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C04_V08` (Dvādaśa Stotra) — इति देववरस्य हरेः स्तवनं कृतवान् मुनिरुत्तममादरतः / सुखतीर्थापदाभिहितः पठतस्तदिदं भवति ध्रुवमुच्चसुखम्
  scan `LLGLLGLLGLLGLLGLLGLLGLLG|LLGGLGLLGLLGLLGLLGLLGLLG` syllables [24, 24]; equal pādas of 24 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `dvadasha_stotra:DDS_C05_V01` (Dvādaśa Stotra) — वासुदेवापरिमेयसुधामन् शुद्धसदोदित सुन्दरीकान्त / धराधरधारणवेधुरधर्तः सौधृतिदीधितिवेधृविधातः
  scan `GLGGLLGLLGGGLLGLLGLGGL|LGLLGLLGLLGGGLLGLLGLLGG` syllables [22, 23]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C05_V02` (Dvādaśa Stotra) — अधिक बन्धं रन्धय बोधाच्छिन्धि पिधानं बन्धुरमद्धा / केशव केशव शासक वन्दे पाशधरार्चित शूरवरेश
  scan `LLLGGGLLGGGLLGGGLLGG|GLLGLLGLLGGGLLGLLGLLGL` syllables [20, 22]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C05_V03` (Dvādaśa Stotra) — नारायणामल कारण वन्दे कारण कारण पूर्णवरेण्य / माधव माधव साधक वन्दे बाधक बोधक शुद्धसमाधे
  scan `GGLGLLGLLGGGLLGLLGLLGL|GLLGLLGLLGGGLLGLLGLLGG` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `dvadasha_stotra:DDS_C05_V04` (Dvādaśa Stotra) — गोविन्द गोविन्द पुरन्दर वन्दे स्कन्दसुनन्दनवन्दितपाद / विष्णो सृजिष्णो ग्रसिष्णो विवन्दे कृष्ण सदुष्णवधिष्णो सुधृष्णो
  scan `GGLGGLLGLLGGGLLGLLGLLGL|GGLGGLGGLGGGLLGLLGGLGG` syllables [23, 22]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C05_V05` (Dvādaśa Stotra) — मधुसूदन दानवसादन वन्दे दैवतमोदित वेदितपाद / त्रिविक्रम निष्क्रम विक्रम वन्दे सङ्क्रम सुक्रम हुङ्कृतवक्त्र
  scan `LLGLLGLLGLLGGGLLGLLGLLGL|LGLLGLLGLLGGGLLGLLGLLGL` syllables [24, 23]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C05_V06` (Dvādaśa Stotra) — वामन वामन भामन वन्दे सामन सीमन सामन सानो / श्रीधर श्रीधर शन्धर वन्दे भूधर वार्धर कन्धरधारिन्
  scan `GLLGLLGLLGGGLLGLLGLLGG|GLGGLLGLLGGGLLGLLGLLGG` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `dvadasha_stotra:DDS_C05_V07` (Dvādaśa Stotra) — हृषीकेश सुकेश परेश विवन्दे शरणेश कलेश बलेश सुखेश / पद्मनाभ शुभोद्भव वन्दे सम्भृतलोकभराभर भूरे / दामोदर दूरतरान्तर वन्दे दारितपारगपाद परस्मात्
  scan `LGGLLGLLGLLGGLLGLLGLLGLLGL|GLGLLGLLGGGLLGLLGLLGG|GGLLGLLGLLGGGLLGLLGLLGG` syllables [26, 21, 23]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C05_V08` (Dvādaśa Stotra) — आनन्दतीर्थमुनीन्द्रकृता हरिगीतिरियं परमादरतः / परलोकवलिोकनसूर्यनिभा हरिभक्तिविवर्धनशौण्डतमा
  scan `GGLGLLGLLGLLGLLGLLGLLG|LLGLLLLLGLLGLLGLLGLLGLLG` syllables [22, 24]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose; nearest: मदिरा (1 भेदौ)
* `dvadasha_stotra:DDS_C06_V01` (Dvādaśa Stotra) — मत्स्यकरूप लयोदविहारिन् वेदविनेत्र चतुर्मुखवन्द्य / कूर्मस्वरूपक मन्दरधारिन् लोकविधारक देववरेण्य
  scan `GLLGLLGLLGGGLLGLLGLLGL|GGLGLLGLLGGGLLGLLGLLGL` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `dvadasha_stotra:DDS_C06_V05` (Dvādaśa Stotra) — देवकिनन्दन नन्दकुमार वृन्दावनाञ्चन गोकुलचन्द्र / कन्दफलाशन सुन्दररूप नन्दितगोकुलवन्दितपाद
  scan `GLLGLLGLLGLGGLGLLGLLGL|GLLGLLGLLGLGLLGLLGLLGL` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `dvadasha_stotra:DDS_C06_V06` (Dvādaśa Stotra) — इन्द्रसुतावक नन्दकहस्त चन्दनचर्चित सुन्दरिनाथ / इन्दीवरोदरदलनयन मन्दरधारिन् गोविन्द वन्दे
  scan `GLLGLLGLLGLGLLGLLGLLGL|GGLGLLLLLLLGLLGGGGLGG` syllables [22, 21]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C06_V07` (Dvādaśa Stotra) — चन्द्रशतानन कुन्दसुहास नन्दितदैवतानन्दसुपूर्ण / दैत्यविमोहक नित्यसुखादे देवसुबोधक बुद्धस्वरूप
  scan `GLLGLLGLLGLGLLGLGGLLGL|GLLGLLGLLGGGLLGLLGGLGL` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `dvadasha_stotra:DDS_C06_V08` (Dvādaśa Stotra) — दुष्टकुलान्तक कल्किस्वरूप धर्मविवर्धन मूलयुगादे / नारायणामलकारणमूर्ते पूर्णगुणार्णव नित्यसुबोध
  scan `GLLGLLGGLGLGLLGLLGLLGG|GGLGLLGLLGGGLLGLLGLLGL` syllables [22, 22]; equal pādas of 22 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `dvadasha_stotra:DDS_C06_V09` (Dvādaśa Stotra) — आनन्दतीर्थमुनीन्द्रकृता हरिगाथा / पापहरा शुभा नित्यसुखार्था
  scan `GGLGLLGLLGLLGG|GLLGLGGLLGG` syllables [14, 11]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C08_V01` (Dvādaśa Stotra) — वन्दिताशेषवन्द्योरुवृन्दारकं चन्दनाचर्चितोदारपीनांसकम् / इन्दिराचञ्चलापाङ्गनीराजितं मन्दरोद्धारिवृत्तोद्भुजाभोगिनम् / प्रीणयामो वासुदेवं देवतामण्डलाखण्डमण्डनं प्रीणयामो वासुदेवम्
  scan `GLGGLGGLGGLGGLGGLGGLGGLG|GLGGLGGLGGLGGLGGLGGLGGLG|GLGGGLGGGLGGLGGLGLGGLGGGLGG` syllables [24, 24, 27]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C08_V02` (Dvādaśa Stotra) — सृष्टिसंहारलीलावलिासाततं पुष्टषाड्गुण्यसद्विग्रहोल्लासिनम् / दुष्टनिश्शेषसंहारकर्मोद्यतं हृष्टपुष्टानुशिष्टप्रजासंश्रयम् / प्रीणयामो वासुदेवं देवतामण्डलाखण्डमण्डनं प्रीणयामो वासुदेवम्
  scan `GLGGLGGLLGLGGLGGLGGLGGLG|GLGGLGGLGGLGGLGGLGGLGGLG|GLGGGLGGGLGGLGGLGLGGLGGGLGG` syllables [24, 24, 27]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose

### Part C batch 9 (items 321–360)

* `dvadasha_stotra:DDS_C08_V03` (Dvādaśa Stotra) — उन्नतप्रार्थिताशेषसंसाधकं सन्नतालौकिकानन्ददश्रीपदम् / भिन्नकर्माशयप्राणिसम्प्रेरकं तन्न किं नेति विद्वत्सु मीमांसितम् / प्रीणयामो वासुदेवं देवतामण्डलाखण्डमण्डनं प्रीणयामो वासुदेवम्
  scan `GLGGLGGLGGLGGLGGLGGLGGLG|GLGGLGGLGGLGGLGGLGGLGGLG|GLGGGLGGGLGGLGGLGLGGLGGGLGG` syllables [24, 24, 27]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C08_V04` (Dvādaśa Stotra) — विप्रमुख्यैः सदा वेदवादोन्मुखैः सुप्रतापैः क्षितिशेश्वरैश्चार्चितम् / अप्रतर्क्योरुसंविद्गुणं निर्मलं सप्रकाशाजरानन्दरूपं परम् / प्रीणयामो वासुदेवं देवतामण्डलाखण्डमण्डनं प्रीणयामो वासुदेवम्
  scan `GLGGLGGLGGLGGLGGLLGLGGLG|GLGGLGGLGGLGGLGGLGGLGGLG|GLGGGLGGGLGGLGGLGLGGLGGGLGG` syllables [24, 24, 27]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C08_V05` (Dvādaśa Stotra) — अत्ययो यस्य केनापि न क्वापि हि प्रत्ययो यद्गुणेषूत्तमानां परः / सत्यसङ्कल्प एको वरेण्यो वशी मत्यनूनैः सदा वेदवादोदितः / प्रीणयामो वासुदेवं देवतामण्डलाखण्डमण्डनं प्रीणयामो वासुदेवम्
  scan `GLGGLGGLGGLGGLGGLGGLGGLG|GLGGLGGLGGLGGLGGLGGLGGLG|GLGGGLGGGLGGLGGLGLGGLGGGLGG` syllables [24, 24, 27]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C08_V06` (Dvādaśa Stotra) — पश्यतां दुःखसन्ताननिर्मूलनं दृश्यतां दृश्यतामित्यजेशार्चितम् / नश्यतां दूरगं सर्वदाप्यात्मगं वश्यतां स्वेच्छया सज्जनेष्वागतम् / प्रीणयामो वासुदेवं देवतामण्डलाखण्डमण्डनं प्रीणयामो वासुदेवम्
  scan `GLGGLGGLGGLGGLGGLGGLGGLG|GLGGLGGLGGLGGLGGLGGLGGLG|GLGGGLGGGLGGLGGLGLGGLGGGLGG` syllables [24, 24, 27]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C08_V07` (Dvādaśa Stotra) — अग्रजं यः ससर्जाजमग्र्याकृतिं विग्रहो यस्य सर्वे गुणा एव हि / उग्र आद्योपि यस्यात्मजाग्य्रात्मजः सद्गृहीतः सदा यः परं दैवतम् / प्रीणयामो वासुदेवं देवतामण्डलाखण्डमण्डनं प्रीणयामो वासुदेवम्
  scan `GLGGLGGLGGLGGLGGLGGLGGLL|GLGGLGGLGGLGGLGGLGGLGGLG|GLGGGLGGGLGGLGGLGLGGLGGGLGG` syllables [24, 24, 27]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C08_V08` (Dvādaśa Stotra) — अच्युतो यो गुणैर्नित्यमेवाखिलैः प्रच्युतोशेषदोषैः सदा पूर्तितः / उच्यते सर्ववेदोरुवादैरजः स्वर्चितो ब्रह्मरुद्रेन्द्रपूर्वैः सदा / प्रीणयामो वासुदेवं देवतामण्डलाखण्डमण्डनं प्रीणयामो वासुदेवम्
  scan `GLGGLGGLGGLGGLGGLGGLGGLG|GLGGLGGLGGLGGLGGLGGLGGLG|GLGGGLGGGLGGLGGLGLGGLGGGLGG` syllables [24, 24, 27]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C08_V09` (Dvādaśa Stotra) — धार्यते येन विश्वं सदाजादिकं वार्यतेशेषदुःखं निजध्यायिनाम् / पार्यते सर्वमन्यैर्न यत्पार्यते कार्यते चाखिलं सर्वभूतैः सदा / प्रीणयामो वासुदेवं देवतामण्डलाखण्डमण्डनं प्रीणयामो वासुदेवम्
  scan `GLGGLGGLGGLGGLGGLGGLGGLG|GLGGLGGLGGLGGLGGLGGLGGLG|GLGGGLGGGLGGLGGLGLGGLGGGLGG` syllables [24, 24, 27]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C08_V10` (Dvādaśa Stotra) — सर्वपापानि यत्संस्मृतेः सङ्क्षयं सर्वदा यान्ति भक्त्या विशुद्धात्मनाम् / शर्वगुर्वादिगीर्वाणसंस्थानदः कुर्वते कर्म यत्प्रीतये सज्जनाः / प्रीणयामो वासुदेवं देवतामण्डलाखण्डमण्डनं प्रीणयामो वासुदेवम्
  scan `GLGGLGGLGGLGGLGGLGGLGGLG|GLGGLGGLGGLGGLGGLGGLGGLG|GLGGGLGGGLGGLGGLGLGGLGGGLGG` syllables [24, 24, 27]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C08_V11` (Dvādaśa Stotra) — अक्षयं कर्म यस्मिन् परे स्वर्पितं प्रक्षयं यान्ति दुःखानि यन्नामतः / अक्षरो योजरः सर्वदैवामृतः कुक्षिगं यस्य विश्वं सदाजादिकम् / प्रीणयामो वासुदेवं देवतामण्डलाखण्डमण्डनं प्रीणयामो वासुदेवम्
  scan `GLGGLGGLGGLGGLGGLGGLGGLG|GLGGLGGLGGLGGLGGLGGLGGLG|GLGGGLGGGLGGLGGLGLGGLGGGLGG` syllables [24, 24, 27]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C08_V12` (Dvādaśa Stotra) — नन्दितीर्थोरुसन्नामिनो नन्दिनः सन्दधानाः सदानन्ददेवे मतिम् / मन्दहासारुणापाङ्गदत्तोन्नतिं नन्दिताशेषदेवादिवृन्दं सदा / प्रीणयामो वासुदेवं देवतामण्डलाखण्डमण्डनं प्रीणयामो वासुदेवम्
  scan `GLGGLGGLGGLGGLGGLGGLGGLG|GLGGLGGLGGLGGLGGLGGLGGLG|GLGGGLGGGLGGLGGLGLGGLGGGLGG` syllables [24, 24, 27]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C09_V01` (Dvādaśa Stotra) — अतिमत तमोगिरिसमितिविभेदन पितामहभूतिद गुणगणनलिय / शुभतमकथाशय परम सदोदित जगदेककारण राम रमारमण
  scan `LLLLLGLLLLLLGLLLGLLGLLLLLLLLL|LLLLLGLLLLLLGLLLLGLGLLGLLGLLL` syllables [29, 29]; equal pādas of 29 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `dvadasha_stotra:DDS_C09_V02` (Dvādaśa Stotra) — विधिभवमुखसुरसततसुवन्दित रमामनोहर भव मम शरणम् / शुभतमकथाशय परम सदोदित जगदेककारण राम रमारमण
  scan `LLLLLLLLLLLLGLLLGLGLLLLLLLLG|LLLLLGLLLLLLGLLLLGLGLLGLLGLLL` syllables [28, 29]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C09_V03` (Dvādaśa Stotra) — अगणितगुणगणमयशरीर हे विगतगुणेतर भव मम शरणम् / शुभतमकथाशय परम सदोदित जगदेककारण राम रमारमण
  scan `LLLLLLLLLLLGLGLLLLGLLLLLLLLG|LLLLLGLLLLLLGLLLLGLGLLGLLGLLL` syllables [28, 29]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C09_V04` (Dvādaśa Stotra) — अपरिमितसुखनिधिविमलसुदेह हे विगतसुखेतर भव मम शरणम् / शुभतमकथाशय परम सदोदित जगदेककारण राम रमारमण
  scan `LLLLLLLLLLLLLGLGLLLLGLLLLLLLLG|LLLLLGLLLLLLGLLLLGLGLLGLLGLLL` syllables [30, 29]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C09_V05` (Dvādaśa Stotra) — प्रचलितलयजलविहरणशाश्वत सुखमय मीन हे भव मम शरणम् / शुभतमकथाशय परम सदोदित जगदेककारण राम रमारमण
  scan `LLLLLLLLLLLLGLLLLLLGLGLLLLLLG|LLLLLGLLLLLLGLLLLGLGLLGLLGLLL` syllables [29, 29]; equal pādas of 29 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `dvadasha_stotra:DDS_C09_V06` (Dvādaśa Stotra) — सुरदितिजसुबलवलिुलितमन्दरधर परकूर्म हे भव मम शरणम् / शुभतमकथाशय परम सदोदित जगदेककारण राम रमारमण
  scan `LLLLLLLLLLLLGLLLLLLGLGLLLLLLG|LLLLLGLLLLLLGLLLLGLGLLGLLGLLL` syllables [29, 29]; equal pādas of 29 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `dvadasha_stotra:DDS_C09_V07` (Dvādaśa Stotra) — सगिरिवरधरातलवह सुसूकर परम विबोध हे भव मम शरणम् / शुभतमकथाशय परम सदोदित जगदेककारण राम रमारमण
  scan `LLLLLLGLLLLLGLLLLLLGLGLLLLLLG|LLLLLGLLLLLLGLLLLGLGLLGLLGLLL` syllables [29, 29]; equal pādas of 29 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `dvadasha_stotra:DDS_C09_V08` (Dvādaśa Stotra) — अतिबलदितिसुतहृदयविभेदन जय नृहरेमल भव मम शरणम् / शुभतमकथाशय परम सदोदित जगदेककारण राम रमारमण
  scan `LLLLLLLLLLLLGLLLLLLGLLLLLLLLG|LLLLLGLLLLLLGLLLLGLGLLGLLGLLL` syllables [29, 29]; equal pādas of 29 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `dvadasha_stotra:DDS_C09_V09` (Dvādaśa Stotra) — बलिमुखदितिसुतविजयविनाशन जगदवनाजित भव मम शरणम् / शुभतमकथाशय परम सदोदित जगदेककारण राम रमारमण
  scan `LLLLLLLLLLLLGLLLLLLGLLLLLLLLG|LLLLLGLLLLLLGLLLLGLGLLGLLGLLL` syllables [29, 29]; equal pādas of 29 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `dvadasha_stotra:DDS_C09_V10` (Dvādaśa Stotra) — अविजितकुनृपतिसमितिविखण्डन रमावर वीरप भव मम शरणम् / शुभतमकथाशय परम सदोदित जगदेककारण राम रमारमण
  scan `LLLLLLLLLLLLGLLLGLLGLLLLLLLLG|LLLLLGLLLLLLGLLLLGLGLLGLLGLLL` syllables [29, 29]; equal pādas of 29 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `dvadasha_stotra:DDS_C09_V11` (Dvādaśa Stotra) — खरतरनिशिचरदहन परामृत रघुवर मानद भव मम शरणम् / शुभतमकथाशय परम सदोदित जगदेककारण राम रमारमण
  scan `LLLLLLLLLLLLGLLLLLLGLLLLLLLLG|LLLLLGLLLLLLGLLLLGLGLLGLLGLLL` syllables [29, 29]; equal pādas of 29 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `dvadasha_stotra:DDS_C09_V12` (Dvādaśa Stotra) — सुललिततनुवर वरद महाबल यदुवर पार्थप भव मम शरणम् / शुभतमकथाशय परम सदोदित जगदेककारण राम रमारमण
  scan `LLLLLLLLLLLLGLLLLLLGLLLLLLLLG|LLLLLGLLLLLLGLLLLGLGLLGLLGLLL` syllables [29, 29]; equal pādas of 29 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `dvadasha_stotra:DDS_C09_V13` (Dvādaśa Stotra) — दितिसुतमोहन विमलविबोधन परगुणबुद्ध हे भव मम शरणम् / शुभतमकथाशय परम सदोदित जगदेककारण राम रमारमण
  scan `LLLLGLLLLLLGLLLLLLGLGLLLLLLG|LLLLLGLLLLLLGLLLLGLGLLGLLGLLL` syllables [28, 29]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C09_V14` (Dvādaśa Stotra) — कलिमलहुतवह सुभग महोत्सव शरणद कल्कीश हे भव मम शरणम् / शुभतमकथाशय परम सदोदित जगदेककारण राम रमारमण
  scan `LLLLLLLLLLLLGLLLLLLGGLGLLLLLLG|LLLLLGLLLLLLGLLLLGLGLLGLLGLLL` syllables [30, 29]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C09_V15` (Dvādaśa Stotra) — अखलिजनिवलिय परसुखकारण परपुरुषोत्तम भव मम शरणम् / शुभतमकथाशय परम सदोदित जगदेककारण राम रमारमण
  scan `LLLLLLLLLLLLGLLLLLLGLLLLLLLLG|LLLLLGLLLLLLGLLLLGLGLLGLLGLLL` syllables [29, 29]; equal pādas of 29 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `dvadasha_stotra:DDS_C09_V16` (Dvādaśa Stotra) — इति तव नुतिवरसततरतेर्भव सुशरणमुरुसुखतीर्थमुनेर्भगवन् / शुभतमकथाशय परम सदोदित जगदेककारण राम रमारमण
  scan `LLLLLLLLLLLLGLLLLLLLLLLGLLGLLG|LLLLLGLLLLLLGLLLLGLGLLGLLGLLL` syllables [30, 29]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C10_V01` (Dvādaśa Stotra) — अवनः श्रीपतिरप्रतिरधिकेशादिभवादे / करुणापूर्णवरप्रद ज्ञापय मे ते
  scan `LLGGLLGLLLLGGLLGG|LLGGLLGLGGLLGG` syllables [17, 14]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C10_V02` (Dvādaśa Stotra) — सुरवन्द्याधिप सद्वर भरिताशेषगुणालम् / करुणापूर्णवरप्रद ज्ञापय मे ते
  scan `LLGGLLGLLLLGGLLGG|LLGGLLGLGGLLGG` syllables [17, 14]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C10_V03` (Dvādaśa Stotra) — सकलध्वान्तविनाशक परमानन्दसुधाहो / करुणापूर्णवरप्रद ज्ञापय मे ते
  scan `LLGGLLGLLLLGGLLGG|LLGGLLGLGGLLGG` syllables [17, 14]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C10_V04` (Dvādaśa Stotra) — त्रिजगत्पोत सदार्चितचरणाशापतिधातो / करुणापूर्णवरप्रद ज्ञापय मे ते
  scan `LLGGLLGLLLLGGLLGG|LLGGLLGLGGLLGG` syllables [17, 14]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C10_V05` (Dvādaśa Stotra) — त्रिगुणातीत विधारक परितो देहि सुभक्तिम् / करुणापूर्णवरप्रद ज्ञापय मे ते
  scan `LLGGLLGLLLLGGLLGG|LLGGLLGLGGLLGG` syllables [17, 14]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C10_V06` (Dvādaśa Stotra) — शरणं कारणभावन भव मे तात सदालम् / करुणापूर्णवरप्रद ज्ञापय मे ते
  scan `LLGGLLGLLLLGGLLGG|LLGGLLGLGGLLGG` syllables [17, 14]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C10_V07` (Dvādaśa Stotra) — मरणप्राणद पालक जगदीशाव सुभक्तिम् / करुणापूर्णवरप्रद ज्ञापय मे ते
  scan `LLGGLLGLLLLGGLLGG|LLGGLLGLGGLLGG` syllables [17, 14]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C10_V08` (Dvādaśa Stotra) — तरुणादित्यसवर्णकचरणाब्जामलकीर्ते / करुणापूर्णवरप्रद ज्ञापय मे ते
  scan `LLGGLLGLLLLGGLLGG|LLGGLLGLGGLLGG` syllables [17, 14]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C10_V09` (Dvādaśa Stotra) — सलिलप्रोत्थसरागकमणिवर्णोच्चनखादे / करुणापूर्णवरप्रद ज्ञापय मे ते
  scan `LLGGLLGLLLLGGLLGG|LLGGLLGLGGLLGG` syllables [17, 14]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C10_V10` (Dvādaśa Stotra) — खजतूणीनिभपावनवरजङ्घमितशक्ते / करुणापूर्णवरप्रद ज्ञापय मे ते
  scan `LLGGLLGLLLLGLLLGG|LLGGLLGLGGLLGG` syllables [17, 14]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C10_V11` (Dvādaśa Stotra) — इभहस्तप्रभशोभनपरमोरुस्थरमाले / करुणापूर्णवरप्रद ज्ञापय मे ते
  scan `LLGGLLGLLLLGGLLGG|LLGGLLGLGGLLGG` syllables [17, 14]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C10_V12` (Dvādaśa Stotra) — असनोत्फुल्लसुपुष्पकसमवर्णावरणान्ते / करुणापूर्णवरप्रद ज्ञापय मे ते
  scan `LLGGLLGLLLLGGLLGG|LLGGLLGLGGLLGG` syllables [17, 14]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C10_V13` (Dvādaśa Stotra) — शतमोदोद्भवसुन्दरवरपद्मोत्थितनाभे / करुणापूर्णवरप्रद ज्ञापय मे ते
  scan `LLGGLLGLLLLGGLLGG|LLGGLLGLGGLLGG` syllables [17, 14]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C10_V14` (Dvādaśa Stotra) — जगदागूहकपल्लवसमकुक्षे शरणादे / करुणापूर्णवरप्रद ज्ञापय मे ते
  scan `LLGGLLGLLLLGGLLGG|LLGGLLGLGGLLGG` syllables [17, 14]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose

### Part C batch 10 (items 361–387)

* `dvadasha_stotra:DDS_C10_V15` (Dvādaśa Stotra) — जगदम्बामलसुन्दरगृलवक्षोवरयोगिन् / करुणापूर्णवरप्रद ज्ञापय मे ते
  scan `LLGGLLGLLLLGGLLGG|LLGGLLGLGGLLGG` syllables [17, 14]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C10_V16` (Dvādaśa Stotra) — दितिजान्तप्रद चक्रदरगदायुग्वरबाहो / करुणापूर्णवरप्रद ज्ञापय मे ते
  scan `LLGGLLGLLLLGGLLGG|LLGGLLGLGGLLGG` syllables [17, 14]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C10_V17` (Dvādaśa Stotra) — परमज्ञानमहानिधिवदनश्रीरमणेन्दो / करुणापूर्णवरप्रद ज्ञापय मे ते
  scan `LLGGLLGLLLLGGLLGG|LLGGLLGLGGLLGG` syllables [17, 14]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C10_V18` (Dvādaśa Stotra) — निखिलाघौघविनाशक परसौख्यप्रददृष्टे / करुणापूर्णवरप्रद ज्ञापय मे ते
  scan `LLGGLLGLLLLGGLLGG|LLGGLLGLGGLLGG` syllables [17, 14]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C10_V19` (Dvādaśa Stotra) — परमानन्दतीर्थमुनिराजो हरिगाथाम् / कृतावान्नित्यसुपूर्णैकपरमानन्दपदैषी
  scan `LLGGLGLLLGGLLGG|LGGGLLGGLLLGGLLGG` syllables [15, 17]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C12_V01` (Dvādaśa Stotra) — आनन्द मुकुन्द अरविन्दनयन / आनन्दतीर्थपरानन्दवरद
  scan `GGLLGLLLGLLLL|GGLGLLGGLLLL` syllables [13, 12]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `dvadasha_stotra:DDS_C12_V02` (Dvādaśa Stotra) — सुन्दरीमन्दिर गोविन्द वन्दे / आनन्दतीर्थपरानन्दवरद
  scan `GLGGLLGGLGG|GGLGLLGGLLLL` syllables [11, 12]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose; nearest: वातोर्मी (1 भेदौ), दोधक (2 भेदौ), शालिनी (2 भेदौ)
* `dvadasha_stotra:DDS_C12_V03` (Dvādaśa Stotra) — चन्द्रकमन्दिरनन्दक वन्दे / आनन्दतीर्थपरानन्दवरद
  scan `GLLGLLGLLGG|GGLGLLGGLLLL` syllables [11, 12]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose; nearest: स्वागता (2 भेदौ), मौक्तिकमाला (2 भेदौ)
* `dvadasha_stotra:DDS_C12_V04` (Dvādaśa Stotra) — चन्द्रसुरेन्द्रसुवन्दित वन्दे / आनन्दतीर्थपरानन्दवरद
  scan `GLLGLLGLLGG|GGLGLLGGLLLL` syllables [11, 12]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose; nearest: स्वागता (2 भेदौ), मौक्तिकमाला (2 भेदौ)
* `dvadasha_stotra:DDS_C12_V05` (Dvādaśa Stotra) — मन्दारस्यन्दकस्यन्दन वन्दे / आनन्दतीर्थपरानन्दवरद
  scan `GGGGLGGLLGG|GGLGLLGGLLLL` syllables [11, 12]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose; nearest: वातोर्मी (2 भेदौ)
* `dvadasha_stotra:DDS_C12_V06` (Dvādaśa Stotra) — वृन्दारकवृन्दसुवन्दित वन्दे / आनन्दतीर्थपरानन्दवरद
  scan `GGLLGLLGLLGG|GGLGLLGGLLLL` syllables [12, 12]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: तामरस (2 भेदौ), मणिमाला (2 भेदौ), मौक्तिकदाम (2 भेदौ)
* `dvadasha_stotra:DDS_C12_V07` (Dvādaśa Stotra) — मन्दारस्यन्दितमन्दिर वन्दे / आनन्दतीर्थपरानन्दवरद
  scan `GGGGLLGLLGG|GGLGLLGGLLLL` syllables [11, 12]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose; nearest: वातोर्मी (1 भेदौ), दोधक (2 भेदौ), भ्रमरविलसित (2 भेदौ)
* `dvadasha_stotra:DDS_C12_V08` (Dvādaśa Stotra) — मन्दिरस्यन्दनस्यन्दक वन्दे / आनन्दतीर्थपरानन्दवरद
  scan `GLGGLGGLLGG|GGLGLLGGLLLL` syllables [11, 12]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose; nearest: दोधक (2 भेदौ), स्वागता (2 भेदौ)
* `dvadasha_stotra:DDS_C12_V09` (Dvādaśa Stotra) — इन्दिरानन्दकसुन्दर वन्दे / आनन्दतीर्थपरानन्दवरद
  scan `GLGGLLGLLGG|GGLGLLGGLLLL` syllables [11, 12]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose; nearest: दोधक (1 भेदौ), स्वागता (1 भेदौ), वातोर्मी (2 भेदौ)
* `dvadasha_stotra:DDS_C12_V10` (Dvādaśa Stotra) — आनन्दचन्द्रिकास्यन्दन वन्दे / आनन्दतीर्थपरानन्दवरद
  scan `GGLGLGGLLGG|GGLGLLGGLLLL` syllables [11, 12]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose; nearest: दोधक (2 भेदौ)
* `vishnu_sahasranama:VSN_PP_X001` (Viṣṇu Sahasranāma Stotra) — श्रीपरमात्मने नमः / नारायणं नमस्कृत्य नरं चैव नरोत्तमम् / देवीं सरस्वतीं व्यासं ततो जयमुदीरयेत्
  scan `GLLGLGLG|GGLGLGGLLGGLLGLG|GGLGLGGGLGLLLGLG` syllables [8, 16, 16]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose; nearest: नाराचिका (1 भेदौ), गजगति (2 भेदौ), चित्रपदा (2 भेदौ)
* `vishnu_sahasranama:VSN_PP_X002` (Viṣṇu Sahasranāma Stotra) — ॐ अथ सकलसौभाग्यदायकं श्रीविष्णुसहस्रनामस्तोत्रम्
  scan `GLLLLLGGLGLGGGLLGLGGGG` syllables [22]; fewer than two pādas — prose, colophon, fragment, or a single line the splitter could not divide
* `vishnu_sahasranama:VSN_PP_V021` (Viṣṇu Sahasranāma Stotra) — अमृतांशूद्भवो बीजं शक्तिर्देवकीनन्दनः / त्रिसामा हृदयं तस्य शान्त्यर्थे विनियुज्यते
  scan `LLGGLGGGGGGLGGLG|LGGLLGGLGGGLLGLG` syllables [16, 16]; equal pādas of 16 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `vishnu_sahasranama:VSN_SK_X001` (Viṣṇu Sahasranāma Stotra) — श्रीकृष्णप्रीत्यर्थे विष्णोर्दिव्यसहस्रनामजपमहं / करिष्ये इति सङ्कल्पः / अथ ध्यानम्
  scan `GGGGGGGGGLLGLGLLLLG|LGGLLGGG|LGGG` syllables [19, 8, 4]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `vishnu_sahasranama:VSN_DH_V003` (Viṣṇu Sahasranāma Stotra) — ॐ शान्ताकारं भुजगशयनं पद्मनाभं सुरेशं / विश्वाधारं गगनसदृशं मेघवर्णं शुभाङ्गम् / लक्ष्मीकान्तं कमलनयनं योगिभिर्ध्यानगम्यं / वन्दे विष्णुं भवभयहरं सर्वलोकैकनाथम्
  scan `GGGGGLLLLLGGLGGLGG|GGGGLLLLLGGLGGLGG|GGGGLLLLLGGLGGLGG|GGGGLLLLLGGLGGLGG` syllables [18, 17, 17, 17]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose; nearest: चित्रलेखा (1 भेदौ)
* `vishnu_sahasranama:VSN_DH_V007` (Viṣṇu Sahasranāma Stotra) — छायायां पारिजातस्य हेमसिंहासनोपरि / आसीनमम्बुदश्याममायताक्षमलंकृतम् / चन्द्राननं चतुर्बाहुं श्रीवत्साङ्कितवक्षसं / रुक्मिणीसत्यभामाभ्यां सहितं कृष्णमाश्रये
  scan `GGGGLGGLGLGGLGLL|GGLGLGGLGLGLLGLG|GGLGLGGGGGGLLGLG|GLGGLGGGLLGGLGLG` syllables [16, 16, 16, 16]; equal pādas of 16 akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect
* `vishnu_sahasranama:VSN_ST_V001` (Viṣṇu Sahasranāma Stotra) — ॐ विश्वं विष्णुर्वषट्कारो भूतभव्यभवत्प्रभुः / भूतकृद्भूतभृद्भावो भूतात्मा भूतभावनः
  scan `GGGGGLGGGGLGLLGLG|GLGGLGGGGGGGLGLG` syllables [17, 16]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `vishnu_sahasranama:VSN_ST_V054` (Viṣṇu Sahasranāma Stotra) — सोमपोऽमृतपः सोमः पुरुजित्पुरुसत्तमः / विनयो जयः सत्यसन्धो दाशार्हः सात्वताम्पतिः
  scan `GLGLLGGGLLGLLGLG|LLGLGGLGGGGGGLGLG` syllables [16, 17]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `vishnu_sahasranama:VSN_ST_V092` (Viṣṇu Sahasranāma Stotra) — धनुर्धरो धनुर्वेदो दण्डो दमयिता दमः / अपराजितः सर्वसहो नियन्ताऽनियमोऽयमः
  scan `LGLGLGGGGGLLLGLG|LLGLGGLLGLGGLLGLG` syllables [16, 17]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `vishnu_sahasranama:VSN_PH_V028` (Viṣṇu Sahasranāma Stotra) — नमोऽस्त्वनन्ताय सहस्रमूर्तये / सहस्रपादाक्षिशिरोरुबाहवे / सहस्रनाम्ने पुरुषाय शाश्वते / सहस्रकोटियुगधारिणे नमः
  scan `LGLGGLLGLGLG|LGLGGLLGLGLG|LGLGGLLGLGLG|LGLGLLLGLGLG` syllables [12, 12, 12, 12]; equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches; nearest: इन्द्रवंशा (1 भेदौ), मालती (2 भेदौ), ललिता (2 भेदौ)
* `vishnu_sahasranama:VSN_UP_X001` (Viṣṇu Sahasranāma Stotra) — ॐ आपदामपहर्तारं दातारं सर्वसम्पदाम् / लोकाभिरामं श्रीरामं भूयो भूयो नमाम्यहम्
  scan `GGLGLLGGGGGGGLGLG|GGLGGGGGGGGGLGLG` syllables [17, 16]; unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose
* `vishnu_sahasranama:VSN_UP_X026` (Viṣṇu Sahasranāma Stotra) — हरिः ॐ तत्सत्
  scan `LGGGG` syllables [5]; fewer than two pādas — prose, colophon, fragment, or a single line the splitter could not divide; nearest: प्रिया (2 भेदौ), प्रीति (2 भेदौ)


## 5. Part D — metres missing from §1

List metres used in Mādhva kāvya and stotra literature (Sumadhva Vijaya, Rāghavendra Vijaya, Madhva's
Dvādaśa Stotra and other stotras, Vādirāja, Vyāsatīrtha, Jagannāthadāsa's Sanskrit works) or in standard
prosody manuals that are **not** in §1. Each with lakṣaṇa, gaṇa, akṣara count, yati, an authority, and one
genuine example verse (same rules as Part A). Skip anything already in §1 under another name — say so
in Part B instead.

Item shape:
```
{"vrutta": "<Devanagari name>", "type": "sama" | "ardhasama" | "vishama" | "matra", "gana": "…",
 "padas": ["L/G pāda1", "…"], "aksharas": [n, n, n, n], "yati": [..], "authority": "text chapter.verse",
 "example": {"text": "…", "source": "…", "scan": ["…"]}, "confidence": 0.0-1.0}
```

## 6. What happens to your answer

`tools/chandas/apply_gemini_chandas.py` re-scans every example with the engine and keeps only examples whose
engine result names the vṛtta you claimed; accepted examples become the engine's regression suite
(`tests/fixtures/chandas_examples.json`) and the `examples` field of the public metre database. Parts B, C, D
go into a human review report — nothing you say changes a lakṣaṇa or a grantha text without a person
checking the cited authority. So: cite precisely, scan honestly, and prefer `null` to a guess.
