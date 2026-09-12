# ब्रह्मसूत्रम् (माध्वप्रस्थानम्) — ಪಂಡಿತರ ಉತ್ತರಗಳ ದಾಖಲೆ / Record of the Scholar's Answers

*Received 3 Sep 2026 via the project lead; applied to the edition the same
day (compile_grantha_v2.py). This file is the provenance record of what
the scholar confirmed and corrected.*

## Question 1 — commentary chains and authors (as answered)

| Commentary | Author (scholar) | Commented on (scholar) | Note |
|---|---|---|---|
| अभिनवचन्द्रिका | श्रीसत्यनाथतीर्थः | तत्त्वप्रकाशिका | author supplied |
| भावबोधः | श्रीरघूत्तमतीर्थः | तत्त्वप्रकाशिका | author supplied |
| भावदीपः | श्रीराघवेन्द्रतीर्थः | तत्त्वप्रकाशिका | confirmed |
| गुर्वर्थदीपिका | श्रीवादिराजतीर्थः | तत्त्वप्रकाशिका | **corrected** (source had Rāghavendra) |
| सत्तर्कदीपावली | श्रीपद्मनाभतीर्थः | — (भाष्यम्, by chronology: Madhva's direct disciple) | **corrected** (source had Vyāsatīrtha) |
| तत्त्वप्रकाशिकाभावबोधः | श्रीरघूत्तमतीर्थः | तत्त्वप्रकाशिका | confirmed |
| तत्त्वसुबोधिनी | पाण्डुरङ्गि-श्रीनिवासाचार्यः | तत्त्वप्रकाशिका | author supplied |
| वाक्यार्थमञ्जरी | शर्करा-श्रीनिवासतीर्थः | तत्त्वप्रकाशिका | author supplied |
| वाक्यार्थमुक्तावली | ताम्रपर्णी-श्रीनिवासाचार्यः | तत्त्वप्रकाशिका | author supplied |
| वाक्यार्थविवरणम् | बिदरहळ्ळि-श्रीनिवासतीर्थः | तत्त्वप्रकाशिका | author supplied |
| विवृतिः | (still unknown) | तत्त्वप्रकाशिका | chain confirmed; author open |

## Question 2 — the sūtrapāṭha

- **2a.** All six restored sūtras (1.4.17 जगद्वाचित्वात्, 2.1.24, 2.1.26,
  3.2.33, 3.3.54, 4.2.2) marked ✔ — positions and readings correct.
- **2b.** All three Śāṅkara-pāṭha sūtras marked **ಮಾಧ್ವಪಾಠದಲ್ಲಿ ಇಲ್ಲ** (absent
  from the Mādhva pāṭha). Note added on apply: for Śaṅkara 4.4.19 the
  *form* is absent but the matter exists — the Mādhva pāṭha reads and
  divides it as our 4.4.20 (विकारावर्ति च तथा हि दर्शयति) + 4.4.21
  (स्थितिमाह दर्शयतश्चैवं प्रत्यक्षानुमाने): pāṭha-bheda, not omission.
- **2c.** 4.2.17 (तदोकोऽग्रज्वलनं …) — **ಒಂದೇ ಸೂತ್ರ** (one sūtra). ✔
- **2d + Appendix.** The full 564-sūtra appendix was returned **without a
  single alteration** — a complete ratification of every position and
  reading (verified mechanically: zero text diffs against the committed
  list). One extraction artifact rode along unnoticed: the layer label
  "सूत्रभाष्यम्" glued to 4.4.20's text; stripped on apply.

## Applied changes

1. `work.json`: all 15 layers now carry scholar-confirmed
   `commentary_on` chains and authors (two author corrections above);
   `review_status` records the confirmation and the pāṭha-bheda notes.
2. `sutra/data.json`: 4.4.20 label-artifact stripped. No other text or
   position changed — none was needed.
3. Question 3 (Nyāyasudhā family chains/authors) was not part of this
   reply and remains open on the live sheet.
