// convert/gemini.js — Gemini proofreading, window.DGE.Gemini namespace.
// Same endpoint/model convention as the main reader app's ai.js, for
// consistency across the project.
window.DGE = window.DGE || {};
window.DGE.Gemini = (function () {

  // Some pages carry two independent OCR readings (Vision + a Tesseract
  // cross-check, when that opt-in was used); app.js formats those pages
  // with "[Vision]"/"[Tesseract]" labels. This prompt explicitly asks Gemini
  // to compare rather than blindly rewrite — per the project's OCR
  // verification policy, correction happens only where the readings agree
  // or context clearly resolves a disagreement, and every shloka gets a
  // self-reported classification instead of a silent, unqualified rewrite.
  const PROOFREAD_PROMPT = `You are proofreading raw OCR output from a scanned Sanskrit/Kannada devotional text.

Some pages below include TWO independent OCR readings from different engines, in this format:
--- Page N ---
[Vision]
<text>
[Tesseract]
<text>
Pages with only one reading show it with no engine label — there was nothing to compare it against.

Rules:
1. Correct OCR mistakes only (misread characters, broken/merged words, obvious scan artifacts). Do not rewrite, summarize, paraphrase, or "improve" the wording.
2. When two readings are given for a page: where they agree (even loosely, allowing for the kind of surface variation different OCR engines produce), that agreement is strong evidence — use it directly rather than inventing a third reading. Where they disagree, use context (grammar, known vocabulary, metre, the surrounding sentence) to choose the more plausible one.
3. Preserve Sanskrit and Kannada text exactly as intended — do not modernize or alter it.
4. Preserve the original paragraph and page order for the actual sentences/lines themselves.
5. Verse-number markers ("॥ १॥", "॥ २॥", ...) are a known weak point of the OCR layer, not something to trust blindly: when verse numbers are printed in their own visual column/margin on the page, OCR can read that whole column as one separate block and splice it back in slightly offset, landing a marker after the wrong shloka's last line. If this looks like what happened — numbers not incrementing where they visually sit, or a shloka reading oddly short or long compared to its neighbors — use the markers' own strict sequence (they always increase by exactly 1 within one sarga/chapter) together with where each verse's sense, grammar, and metre naturally complete to reattach each marker to its real shloka boundary. This only changes which existing text belongs under which "number" — it never means inventing, dropping, or actually reordering the underlying sentences (rule 4 still applies to those).
6. Where distinguishable, identify which portions are the mula shloka (verse) text versus commentary/explanation.
7. Never invent text that isn't grounded in at least one OCR reading for that page, beyond fixing an obvious small OCR-level error (broken characters, merged words) that context clearly resolves.
8. For every shloka, self-report a "classification":
   - "accept": the two readings agree, or only one reading existed and it's unambiguous and plausible as-is.
   - "review": readings disagreed, or a verse-marker boundary needed reattaching per rule 5, and you resolved it using context — likely correct, but a human should still glance at it.
   - "unresolved": you cannot determine confident text (readings are implausible, contradictory, or the source itself looks illegible). Keep your best-guess text in "sa" regardless, but do not invent details neither reading actually shows.
   Add a brief "note" explaining why, but only when classification is not "accept" — omit it (empty string) otherwise.
9. Also report which page (the number from the "--- Page N ---" marker) each shloka came from, in "page".
10. Watch for two specific structural problems, since they're easy to miss shloka-by-shloka but matter a lot downstream: (a) a chapter/sarga boundary — a chapter-opening line ("अथ <ordinal> सर्गः") or a closing colophon ("इति ... <ordinal> सर्गः") — that looks incomplete, garbled, or only half-legible, since that's exactly what breaks automatic chapter splitting later; (b) one verse's text that looks like it was actually split into two separate shlokas (or two verses merged into one) by a misplaced verse-number marker, beyond what rule 5 above already resolves. When either happens, still give your best-effort corrected text, but set "classification" to "review" and say specifically what you noticed in "note" (e.g. "possible sarga boundary here — colophon text looks incomplete" or "this may be two verses merged into one shloka"), so a human reviewer sees exactly what to double-check instead of having to re-read everything.
11. Output ONLY valid JSON — no markdown code fences, no explanations before or after, no trailing commentary.

Output exactly this JSON shape:
{
  "shlokas": [
    { "number": 1, "page": 3, "sa": "corrected shloka text", "commentary": "corrected commentary text, or empty string if none", "classification": "accept", "note": "" }
  ]
}

If a page doesn't cleanly split into shloka/commentary, put the whole corrected text in "sa" and leave "commentary" empty — do not invent a split that isn't actually there in the source.

Raw OCR input follows:
`;

  // Constrains Gemini's decoding to always emit syntactically valid JSON
  // matching this shape — this is the primary fix for "Could not parse
  // JSON from the model's response" failures, which were previously
  // caused by the model emitting an unescaped character or similar
  // syntax slip somewhere inside a long free-form response.
  const PROOFREAD_RESPONSE_SCHEMA = {
    type: 'object',
    properties: {
      shlokas: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            number: { type: 'integer' },
            page: { type: 'integer' },
            sa: { type: 'string' },
            commentary: { type: 'string' },
            classification: { type: 'string', enum: ['accept', 'review', 'unresolved'] },
            note: { type: 'string' }
          },
          required: ['sa', 'classification']
        }
      }
    },
    required: ['shlokas']
  };

  // Delegates network + error classification to the shared window.DGEGemini
  // client (js/gemini.js) -- same human-readable quota/permission/network
  // messages and one-step lighter-model fallback as Ashtadhyayi/Kosha now
  // get. The structured-JSON-output constraint (responseMimeType/Schema)
  // and the finishReason/JSON-parse checks below are Convert-specific and
  // stay on top of the shared client's response rather than inside it.
  async function proofread(ocrPagesText, apiKey, model, contextAnchor, maxOutputTokens) {
    // No hardcoded fallback name here on purpose -- passing model through
    // as-is (undefined when the caller has none) lets window.DGEGemini's
    // own DEFAULT_MODEL be the single source of truth for "what to use
    // when nothing is picked", instead of this file keeping its own
    // separately-hardcoded (and previously stale/inconsistent) copy.
    //
    // contextAnchor (optional) is a short human-supplied description of
    // what the text actually is (e.g. "Bhagavad Gita Chapter 1, Bhavadipa
    // commentary by Raghavendra Yati") -- giving Gemini this lets it
    // resolve ambiguous OCR errors against real context instead of
    // guessing blind. Prepended, not baked into PROOFREAD_PROMPT itself,
    // so the prompt's behavior is unchanged when it's left blank.
    const anchor = contextAnchor ? `Context anchor: this text is from ${contextAnchor}.\n\n` : '';
    const prompt = anchor + PROOFREAD_PROMPT + '\n\n' + ocrPagesText;

    const generationConfig = {
      responseMimeType: 'application/json',
      responseSchema: PROOFREAD_RESPONSE_SCHEMA
    };
    // Overrides the shared client's own default (8192) -- a dense
    // multi-page commentary chunk's full corrected text plus per-shloka
    // classification/notes can genuinely need more room than that.
    // Confirmed directly against real Gemini output on real classical-kavya
    // text (Sumadhva Vijaya, 6 dense pages including verse + an editorial
    // citrakavya appendix): the shared 8192 default hit MAX_TOKENS partway
    // through, while 32768 completed cleanly. 16384 as Convert's OWN floor
    // when the admin hasn't typed a value -- still well under what a run
    // that genuinely needs more can raise it to, but no longer the
    // conversational-chat-sized default meant for unrelated Gemini features
    // elsewhere on the site (Kosha, Ashtadhyayi), which this file doesn't
    // touch.
    generationConfig.maxOutputTokens = maxOutputTokens || 16384;

    const r = await window.DGEGemini.generate({
      prompt: prompt, apiKey: apiKey, model: model,
      generationConfig: generationConfig
    });

    if (!r.ok) {
      // Tag the error with DGEGemini's classified `kind` (e.g. "quota") so
      // app.js's retry loop can back off appropriately long for a real
      // rate limit instead of using the same short delay as a network blip.
      const e = new Error(r.error.title + ': ' + r.error.message + ' ' + r.error.action);
      e.kind = r.error.kind;
      throw e;
    }

    const candidate = r.raw && r.raw.candidates && r.raw.candidates[0];
    const finishReason = candidate && candidate.finishReason;

    // Check finishReason BEFORE attempting to parse — a MAX_TOKENS cutoff
    // can still leave a non-empty but incomplete `text`, which would
    // otherwise reach the JSON parser and surface as a confusing generic
    // syntax error instead of the real cause.
    if (finishReason === 'MAX_TOKENS') {
      // Tagged 'max_tokens' so app.js's retry loop doesn't burn through
      // several automatic retries on this -- the exact same request would
      // hit the exact same limit every time; only a setting change (not
      // waiting) fixes it.
      const e = new Error('Gemini\'s response was cut off before finishing (hit the output token limit) — this chunk\'s full corrected text needed more room than allowed. Either raise "Max output tokens per Gemini response" above, or lower the chunk size, then re-run Proofread (it will resume from this chunk).');
      e.kind = 'max_tokens';
      throw e;
    }
    if (finishReason && finishReason !== 'STOP') {
      throw new Error(`Gemini stopped early (reason: ${finishReason}) instead of completing normally.`);
    }

    if (!r.text) {
      throw new Error('Gemini returned no usable content.');
    }
    if (r.fellBack) console.warn('[Convert] ' + r.notice);

    return window.DGE.Utils.parseJsonLoose(r.text);
  }

  // Fetches the real, current list of models this specific key can use,
  // straight from Gemini's own models.list endpoint -- so the model picker
  // always reflects reality instead of a hardcoded name that can go stale
  // (exactly what happened with this file's own old 'gemini-3.6-flash'
  // fallback). Filtered to models that actually support generateContent
  // (the list also includes embedding/other non-chat models we can't use
  // here). Returns [{ id: 'gemini-2.5-flash', displayName: '...' }, ...].
  async function listModels(apiKey) {
    if (!apiKey) throw new Error('Enter your Gemini API key first.');
    const url = 'https://generativelanguage.googleapis.com/v1beta/models?key=' + encodeURIComponent(apiKey);
    let res;
    try {
      res = await fetch(url);
    } catch (e) {
      throw new Error('Could not reach Gemini to list models: ' + (e.message || e));
    }
    const payload = await res.json().catch(() => null);
    if (!res.ok) {
      const msg = (payload && payload.error && payload.error.message) || ('HTTP ' + res.status);
      throw new Error('Gemini rejected the models.list request: ' + msg);
    }
    const models = (payload && payload.models) || [];
    return models
      .filter(m => Array.isArray(m.supportedGenerationMethods) && m.supportedGenerationMethods.includes('generateContent'))
      .map(m => ({ id: (m.name || '').replace(/^models\//, ''), displayName: m.displayName || m.name }))
      .filter(m => m.id);
  }

  return { proofread, listModels };
})();
