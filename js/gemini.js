/*!
 * DGE Gemini — shared BYOK client with human error messages + one-step model fallback.
 *
 * Built once, used by Ashtadhyayi, Kosha and Convert. No dependencies, no build step.
 * Talks directly to generativelanguage.googleapis.com with the user's own key
 * (BYOK, stored in localStorage). Nothing here is granted by DGE — quota and billing
 * live entirely on the user's Google key, so quota errors are surfaced as *their*
 * account issue with an actionable message, not a DGE failure.
 *
 * Exposes window.DGEGemini. Also works as an ES module (export at bottom).
 *
 *   const r = await DGEGemini.generate({ prompt: "explain 1.1.1" });
 *   if (r.ok) show(r.text, r.modelUsed, r.fellBack);
 *   else showError(r.error.title, r.error.message, r.error.action);
 */
(function (root) {
  "use strict";

  // ---- Config -------------------------------------------------------------
  // localStorage keys the existing pages already use for BYOK. If a page uses
  // different keys, pass apiKey/model explicitly to generate() and these are ignored.
  var LS_KEY = "dge_gemini_api_key";
  var LS_MODEL = "dge_gemini_model";

  var API_BASE = "https://generativelanguage.googleapis.com/v1beta/models/";

  // Default primary + the single fallback we drop to when the primary is
  // unavailable or quota-limited. Flash is cheaper/higher-free-quota than Pro,
  // so it is the natural one-step fallback. Kept in preference order.
  //
  // Pinned versioned IDs go stale -- confirmed directly against a real,
  // freshly-created API key: both "gemini-2.5-flash" AND its own fallback
  // "gemini-2.5-flash-lite" returned a 404 ("no longer available to new
  // users"), even though models.list still lists them with generateContent
  // support (that list apparently doesn't reflect real per-key
  // availability). With BOTH primary and fallback dead, every AI feature
  // on the site would fail outright for any newly-issued key, with no
  // automatic recovery. Switched to Google's own "-latest" rolling aliases,
  // which stay pointed at whatever's current -- verified working against
  // the same key that hit the 404s.
  var DEFAULT_MODEL = "gemini-flash-latest";
  var FALLBACK_MODEL = "gemini-flash-lite-latest";

  // The models a page may offer, in one place and exported, so a settings
  // <select> is built from this list instead of keeping its own copy of it.
  // The Ashtadhyayi page kept its own copy and was still offering four dead
  // ids -- gemini-2.0-flash, -flash-lite, gemini-1.5-flash, -1.5-pro -- long
  // after this file had moved off pinned ids for exactly that reason, and
  // defaulted to one of them, so its AI was broken for any new key. A page
  // that builds its menu from here cannot drift again.
  //
  // Only aliases actually confirmed working against a real key are listed. A
  // "pro" tier alias very likely exists too, but adding an id nobody here has
  // exercised is the precise mistake this list exists to prevent -- add it
  // once someone has seen it answer.
  var MODELS = [
    { id: "gemini-flash-latest",      label: "Flash — fast, recommended" },
    { id: "gemini-flash-lite-latest", label: "Flash Lite — cheapest" }
  ];

  // Error "kind" constants so callers can branch if they want to.
  var KIND = {
    NO_KEY: "no_key",
    BAD_KEY: "bad_key",
    QUOTA: "quota",
    PERMISSION: "permission",
    MODEL_MISSING: "model_missing",
    BAD_REQUEST: "bad_request",
    BLOCKED: "blocked",
    OVERLOADED: "overloaded",
    NETWORK: "network",
    UNKNOWN: "unknown"
  };

  // ---- Small helpers ------------------------------------------------------
  function getKey() {
    try { return (root.localStorage && root.localStorage.getItem(LS_KEY)) || ""; }
    catch (e) { return ""; }
  }
  function getModel() {
    try { return (root.localStorage && root.localStorage.getItem(LS_MODEL)) || DEFAULT_MODEL; }
    catch (e) { return DEFAULT_MODEL; }
  }
  function setKey(k) { try { root.localStorage.setItem(LS_KEY, k || ""); } catch (e) {} }
  function setModel(m) { try { root.localStorage.setItem(LS_MODEL, m || DEFAULT_MODEL); } catch (e) {} }

  // Build the standard request body from either a plain prompt or full contents.
  function buildBody(opts) {
    var body = {};
    if (opts.contents) {
      body.contents = opts.contents;
    } else {
      body.contents = [{ role: "user", parts: [{ text: String(opts.prompt || "") }] }];
    }
    if (opts.system) {
      body.systemInstruction = { parts: [{ text: String(opts.system) }] };
    }
    // maxOutputTokens: 2048 was the long-standing default here and is
    // genuinely too low for anything that has to return a full page (or
    // several) of structured JSON in one response -- a dense commentary
    // chunk's corrected text + per-shloka classification/note easily runs
    // past that, hitting MAX_TOKENS mid-response with no way to recover
    // the cut-off JSON. Raised to a still-conservative-but-much-safer
    // 8192; callers needing more (e.g. Convert's large chunks) can still
    // override via opts.generationConfig.maxOutputTokens.
    body.generationConfig = Object.assign(
      { temperature: 0.3, maxOutputTokens: 8192 },
      opts.generationConfig || {}
    );
    if (opts.safetySettings) body.safetySettings = opts.safetySettings;
    return body;
  }

  // Turn a fetch Response / caught exception into a normalized error object.
  // `payload` is the parsed JSON error body when we have one.
  function classify(status, payload, thrown) {
    var apiMsg =
      (payload && payload.error && payload.error.message) ||
      (thrown && thrown.message) || "";
    var apiStatus = payload && payload.error && payload.error.status; // e.g. RESOURCE_EXHAUSTED

    // Network / CORS / offline — fetch rejected before any HTTP status.
    if (thrown && status == null) {
      return err(KIND.NETWORK,
        "Can’t reach Gemini",
        "The request to Google’s Gemini API didn’t go through.",
        "Check your internet connection and try again. If you’re offline, the AI features need a connection.",
        apiMsg);
    }

    if (status === 400 && /API key not valid|API_KEY_INVALID/i.test(apiMsg)) {
      return err(KIND.BAD_KEY,
        "Your Gemini API key isn’t valid",
        "Google rejected the API key saved in this browser.",
        "Open the key settings, paste a fresh key from Google AI Studio (aistudio.google.com/apikey), and save.",
        apiMsg);
    }
    if (status === 400) {
      return err(KIND.BAD_REQUEST,
        "Gemini couldn’t process that request",
        "The request was malformed or the prompt was too long for this model.",
        "Try a shorter prompt, or open fewer commentary layers before asking.",
        apiMsg);
    }
    if (status === 401 || status === 403 || apiStatus === "PERMISSION_DENIED") {
      // Free API not enabled / key restricted / model not allowed for this key.
      return err(KIND.PERMISSION,
        "This key can’t use Gemini here",
        "Your key was recognised but isn’t allowed to call this model — usually the Generative Language API isn’t enabled on the key’s Google project, or the key has referrer/IP restrictions.",
        "In Google AI Studio create a key with no restrictions, or enable the “Generative Language API” for that project.",
        apiMsg);
    }
    if (status === 429 || apiStatus === "RESOURCE_EXHAUSTED") {
      return err(KIND.QUOTA,
        "Your Gemini quota is used up",
        "This is a limit on your own Google API key — DGE can’t raise it. Free-tier keys reset per minute and per day; a burst of requests or the daily cap will trigger this.",
        "Wait a minute and retry, switch to a lighter model (Flash / Flash-Lite), or enable billing on your key at aistudio.google.com to lift the free-tier cap.",
        apiMsg);
    }
    if (status === 404) {
      return err(KIND.MODEL_MISSING,
        "That Gemini model isn’t available",
        "The selected model name doesn’t exist or your key can’t access it.",
        "Pick a different model in settings (e.g. gemini-flash-latest).",
        apiMsg);
    }
    if (status === 503 || status === 500 || apiStatus === "UNAVAILABLE") {
      return err(KIND.OVERLOADED,
        "Gemini is busy right now",
        "Google’s servers returned a temporary overload/error for this model.",
        "Wait a few seconds and try again — this usually clears on its own.",
        apiMsg);
    }
    return err(KIND.UNKNOWN,
      "Gemini request failed",
      apiMsg || ("Unexpected response" + (status ? " (HTTP " + status + ")" : "") + "."),
      "Try again; if it keeps happening, check your key and model in settings.",
      apiMsg);
  }

  function err(kind, title, message, action, detail) {
    return { kind: kind, title: title, message: message, action: action, detail: detail || "" };
  }

  // Extract text from a generateContent response, or return a BLOCKED error.
  function extractText(data) {
    if (data && data.promptFeedback && data.promptFeedback.blockReason) {
      return { blocked: err(KIND.BLOCKED,
        "Gemini blocked this response",
        "Google’s safety filter stopped the answer (reason: " + data.promptFeedback.blockReason + ").",
        "Rephrase the question and try again.",
        "") };
    }
    var cand = data && data.candidates && data.candidates[0];
    if (cand && cand.finishReason === "SAFETY") {
      return { blocked: err(KIND.BLOCKED,
        "Gemini blocked this response",
        "The answer was filtered by Google’s safety system.",
        "Rephrase the question and try again.", "") };
    }
    var parts = cand && cand.content && cand.content.parts;
    var text = parts ? parts.map(function (p) { return p.text || ""; }).join("") : "";
    return { text: text };
  }

  // ---- One HTTP attempt against a specific model ---------------------------
  function attempt(model, key, body, signal) {
    var url = API_BASE + encodeURIComponent(model) + ":generateContent?key=" + encodeURIComponent(key);
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: signal
    }).then(function (res) {
      if (res.ok) {
        return res.json().then(function (data) { return { ok: true, data: data }; });
      }
      return res.json().catch(function () { return null; }).then(function (payload) {
        return { ok: false, status: res.status, error: classify(res.status, payload, null) };
      });
    }, function (thrown) {
      // Abort is not an error we should dress up.
      if (thrown && thrown.name === "AbortError") throw thrown;
      return { ok: false, status: null, error: classify(null, null, thrown) };
    });
  }

  // Which failures are worth a one-step fallback to a lighter model?
  function shouldFallback(kind) {
    return kind === KIND.QUOTA || kind === KIND.MODEL_MISSING || kind === KIND.OVERLOADED;
  }

  // ---- Public: generate() -------------------------------------------------
  // opts: { prompt | contents, system, generationConfig, safetySettings,
  //         apiKey, model, fallbackModel, signal }
  // Returns a Promise that ALWAYS resolves (never rejects except on abort):
  //   success -> { ok:true, text, modelUsed, fellBack, raw }
  //   failure -> { ok:false, error:{ kind, title, message, action, detail }, modelUsed }
  function generate(opts) {
    opts = opts || {};
    var key = opts.apiKey != null ? opts.apiKey : getKey();
    var primary = opts.model || getModel() || DEFAULT_MODEL;
    var fallback = opts.fallbackModel !== undefined
      ? opts.fallbackModel
      : (primary === FALLBACK_MODEL ? null : FALLBACK_MODEL);

    if (!key) {
      return Promise.resolve({
        ok: false,
        modelUsed: primary,
        error: err(KIND.NO_KEY,
          "No Gemini API key set",
          "The AI features use your own Google Gemini key, kept only in this browser.",
          "Add a free key from Google AI Studio (aistudio.google.com/apikey) in settings to turn on AI.",
          "")
      });
    }

    var body = buildBody(opts);

    return attempt(primary, key, body, opts.signal).then(function (r1) {
      if (r1.ok) {
        var ex = extractText(r1.data);
        if (ex.blocked) return { ok: false, modelUsed: primary, error: ex.blocked };
        return { ok: true, text: ex.text, modelUsed: primary, fellBack: false, raw: r1.data };
      }
      // primary failed — one-step fallback only for the recoverable kinds
      if (fallback && shouldFallback(r1.error.kind)) {
        return attempt(fallback, key, body, opts.signal).then(function (r2) {
          if (r2.ok) {
            var ex2 = extractText(r2.data);
            if (ex2.blocked) return { ok: false, modelUsed: fallback, error: ex2.blocked };
            return {
              ok: true, text: ex2.text, modelUsed: fallback, fellBack: true, raw: r2.data,
              notice: "Switched to " + fallback + " because " + primary + " was unavailable."
            };
          }
          // fallback also failed — report the ORIGINAL (usually clearer) error,
          // but note both models were tried.
          var e = r1.error;
          e.detail = (e.detail ? e.detail + " " : "") + "(fallback " + fallback + " also failed.)";
          return { ok: false, modelUsed: fallback, error: e, fellBack: true };
        });
      }
      return { ok: false, modelUsed: primary, error: r1.error, fellBack: false };
    });
  }

  // ---- Optional: default DOM error renderer -------------------------------
  // Callers can use their own UI; this is a drop-in for pages that just want
  // a consistent block. Returns an HTMLElement (does not insert it).
  function renderError(error, opts) {
    opts = opts || {};
    var box = document.createElement("div");
    box.className = "dge-gemini-error " + (opts.className || "");
    box.setAttribute("role", "alert");
    box.style.cssText = opts.style ||
      "border:1px solid #e0b4b4;background:#fff6f6;color:#5c1f1f;" +
      "padding:12px 14px;border-radius:8px;font-size:0.95em;line-height:1.45;margin:8px 0;";
    var t = document.createElement("strong");
    t.textContent = error.title;
    box.appendChild(t);
    var m = document.createElement("div");
    m.textContent = error.message;
    m.style.margin = "4px 0";
    box.appendChild(m);
    if (error.action) {
      var a = document.createElement("div");
      a.textContent = "→ " + error.action;
      a.style.opacity = "0.85";
      box.appendChild(a);
    }
    return box;
  }

  // ---- Export -------------------------------------------------------------
  var api = {
    generate: generate,
    renderError: renderError,
    getKey: getKey, setKey: setKey,
    getModel: getModel, setModel: setModel,
    KIND: KIND,
    DEFAULT_MODEL: DEFAULT_MODEL,
    FALLBACK_MODEL: FALLBACK_MODEL,
    MODELS: MODELS,
    // true if `m` is one of the ids above; a page uses this to spot a model
    // saved by an older build and quietly fall back rather than 404 forever.
    isKnownModel: function (m) {
      for (var i = 0; i < MODELS.length; i++) if (MODELS[i].id === m) return true;
      return false;
    },
    // let a page override storage keys if it uses different ones
    configure: function (o) {
      o = o || {};
      if (o.lsKey) LS_KEY = o.lsKey;
      if (o.lsModel) LS_MODEL = o.lsModel;
      if (o.defaultModel) DEFAULT_MODEL = o.defaultModel;
      if (o.fallbackModel) FALLBACK_MODEL = o.fallbackModel;
    }
  };

  root.DGEGemini = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : this);
