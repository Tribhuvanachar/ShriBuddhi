// DGE Module: footnote-engine.js
// Renders a Gemini-enrichment block (see tools/gemini_enrich.py's
// `gemini_enrichment: {segments, references}` shape, and dge/PENDING.md's
// "Reference Resolution Engine" for why every reference here carries a
// confidence-tiered status rather than being presented as fact) as inline
// superscript footnote markers plus a footnote list, matching the visual
// pattern of dge/js/backlinks.js's citation popovers/links.
window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['footnote-engine.js'] = 'v1.1 (footnote list items now show the same dge-ai-badge as commentary blocks, since every reference here started as a Gemini proposal)';

const DGEFootnotes = (function () {
  const STATUS_LABEL = {
    verified: 'Verified',
    possible: 'Possible match',
    unresolved: 'Unresolved — needs review'
  };
  const STATUS_CLASS = {
    verified: 'dge-fn-verified',
    possible: 'dge-fn-possible',
    unresolved: 'dge-fn-unresolved'
  };

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function targetHref(ref) {
    if (!ref.target_slug) return null;
    var href = 'index.html?path=' + encodeURIComponent(ref.target_slug);
    if (ref.target_unit_id) href += '&jumpVedicId=' + encodeURIComponent(ref.target_unit_id);
    return href;
  }

  // Builds inline HTML from `enrichment.segments`, injecting a numbered
  // <sup> marker after each segment that carries reference_ids. Text is
  // escaped here (segments are raw corpus/Gemini text, not markup) — the
  // caller may run its own markup (e.g. render.js's highlightText) over the
  // RESULT afterwards, since that function is written to skip text already
  // inside a tag.
  function renderInline(enrichment) {
    if (!enrichment || !Array.isArray(enrichment.segments)) return null;
    var refs = enrichment.references || {};
    var order = [];
    var html = '';
    enrichment.segments.forEach(function (seg) {
      html += esc(seg.text || '');
      (seg.reference_ids || []).forEach(function (rid) {
        if (!refs[rid]) return;
        if (order.indexOf(rid) === -1) order.push(rid);
        var n = order.indexOf(rid) + 1;
        var status = refs[rid].status || 'unresolved';
        var cls = STATUS_CLASS[status] || '';
        var label = STATUS_LABEL[status] || status;
        html += '<sup class="dge-fn-mark ' + cls + '" data-fn-ref="' + esc(rid) +
                '" title="Footnote ' + n + ': ' + esc(label) + '">' + n + '</sup>';
      });
    });
    return { html: html, order: order };
  }

  function renderFootnoteList(enrichment, order) {
    var refs = enrichment.references || {};
    if (!order.length) return '';
    var items = order.map(function (rid, idx) {
      var ref = refs[rid];
      if (!ref) return '';
      var n = idx + 1;
      var status = ref.status || 'unresolved';
      var label = STATUS_LABEL[status] || status;
      var href = targetHref(ref);
      var locator = ref.target_unit_id ? (' ' + esc(ref.target_unit_id)) : '';
      var targetHtml = href
        ? '<a href="' + href + '" class="dge-fn-target">' +
          esc(ref.target_title || ref.target_slug) + locator + '</a>'
        : (ref.source_guess
            ? '<span class="dge-fn-target-guess">' + esc(ref.source_guess) +
              ' (not found in this library’s copy)</span>'
            : '');
      // Every reference here started as a Gemini proposal (see
      // tools/gemini_enrich.py) -- the "AI" badge marks that origin
      // regardless of status, same convention as commentary blocks
      // (core.js's dgeIsAiGeneratedCommentaryKey / render.js).
      return '<li id="fn-' + esc(rid) + '" class="dge-fn-item ' + (STATUS_CLASS[status] || '') + '">' +
             '<span class="dge-fn-num">' + n + '.</span> ' +
             '<span class="dge-ai-badge" title="AI-proposed -- not author-verified">AI</span> ' +
             '<span class="dge-fn-quote">“' + esc(ref.quoted_text) + '”</span> ' +
             (targetHtml ? ('— ' + targetHtml + ' ') : '') +
             '<span class="dge-fn-status">' + esc(label) + '</span>' +
             '</li>';
    }).join('');
    return '<ol class="dge-fn-list">' + items + '</ol>';
  }

  // Public entry point. Given one item/shloka's `geminiEnrichment` block,
  // returns {html, footnotesHtml}, or null when there is nothing to render
  // (no enrichment data, or an enrichment run that found zero citations) —
  // callers should fall back to plain-text rendering in that case, same as
  // before this feature existed.
  function render(enrichment) {
    var inline = renderInline(enrichment);
    if (!inline || !inline.order.length) return null;
    return {
      html: inline.html,
      footnotesHtml: renderFootnoteList(enrichment, inline.order)
    };
  }

  return { render: render };
})();

window.DGEFootnotes = DGEFootnotes;
