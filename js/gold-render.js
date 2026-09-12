// DGE Module: gold-render.js
// Renders a commentary object shaped to the Gold-Standard Commentary
// Contract (v2.2) -- see dge/GOLD_STANDARD_ARCHITECTURE.md for the full
// gap analysis and design rationale this file implements. A commentary
// only takes this path when render.js finds `commentaries[cKey].format ===
// 'gold_v2_2'`; every other (plain-string) commentary is completely
// unaffected -- this module is purely additive, same shape as
// footnote-engine.js: a pure function, absent data -> caller falls back.
window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['gold-render.js'] = 'v1.0 (first build: block parser for commentary_markdown -- title banners, मङ्गलम्/प्रमाणम्/फलितार्थः provenance containers, अवतरणिका transitions, colophons -- pratika<->word-pill bidirectional linking with the Gold-Standard badge and certificate wrapper render.js applies around this output; window.dgeToggleGoldSimple() is the badge\'s own view-switch)';

const DGEGoldRender = (function () {
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c];
    });
  }

  // Part D1 of the contract: every single/double daṇḍa bound to the
  // preceding syllable with a non-breaking space, so it can never wrap
  // onto a new line as an orphaned glyph. Applied to already-escaped text,
  // before any of this module's own HTML tags are injected -- daṇḍas never
  // appear inside the tag syntax this module adds, so running this early
  // is safe and matches the reference reader's own working order.
  function bindDandas(s) {
    if (!s) return '';
    return s.replace(/[ \t]+।/g, ' ।').replace(/[ \t]+॥/g, ' ॥');
  }

  // **"pratika"** -> an inline touch-target span, matched against
  // word_mappings by exact string equality (the contract's "Parity Rule").
  // A pratika string can legitimately recur (a common word quoted more
  // than once) -- each occurrence gets its own unique span id
  // (pratika-IDX-OCCURRENCE) so the HTML stays valid, but every occurrence
  // links back to the SAME word-pill (word-pill-IDX); the pill itself only
  // needs to jump to the first occurrence, not every one.
  // A pratika with no matching word_mappings entry (a real parity
  // violation -- tools/validate_gold_standard.py is the place that should
  // actually catch this before content ships) still renders, just without
  // a jump target, so a data-quality gap degrades to "looks like plain
  // bold text" rather than breaking the reader.
  function linkPratikas(escapedText, wordMappings) {
    const byPratika = {};
    (wordMappings || []).forEach(function (m, i) {
      if (m && m.pratika && !(m.pratika in byPratika)) byPratika[m.pratika] = i;
    });
    const occurrence = {};
    return escapedText.replace(/\*\*"([^"]*)"\*\*/g, function (whole, inner) {
      const idx = byPratika[inner];
      if (idx === undefined) {
        return '<strong class="dge-gold-unmapped" title="No matching word_mappings entry">“' + inner + '”</strong>';
      }
      const occ = (occurrence[idx] = (occurrence[idx] || 0) + 1) - 1;
      return '<span id="pratika-' + idx + '-' + occ + '" class="dge-gold-pratika" ' +
        'data-gold-target="word-pill-' + idx + '" onclick="window.dgeGoldJumpTo(this)">“' + inner + '”</span>';
    });
  }

  // Remaining inline markup once pratikas are already spans: **bold** that
  // ISN'T a pratika, and *italic* (single-asterisk, not the ** already
  // consumed above).
  function inline(s) {
    return s
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, '$1<em>$2</em>');
  }

  function pillGrid(wordMappings) {
    if (!wordMappings || !wordMappings.length) return '';
    const items = wordMappings.map(function (m, idx) {
      const gloss = m.gloss ? '<span class="dge-gold-pill-arrow">→</span><span class="dge-gold-pill-gloss">' + esc(m.gloss) + '</span>' : '';
      return '<div class="dge-gold-pill" id="word-pill-' + idx + '" data-gold-target="pratika-' + idx + '-0" ' +
        'onclick="window.dgeGoldJumpTo(this)"><span class="dge-gold-pill-mula">' + esc(m.mula_word || '') + '</span>' + gloss + '</div>';
    }).join('');
    return '<div class="dge-gold-pillgrid">' + items + '</div>';
  }

  // Splits commentary_markdown into blocks on blank lines and dispatches
  // each by its leading token -- the contract's own Discrete Provenance
  // Containers (Part B2). Order matters: more specific block markers are
  // checked before the generic paragraph fallback.
  function renderBlocks(markdown, wordMappings) {
    if (!markdown) return '';
    const linked = linkPratikas(bindDandas(esc(markdown)), wordMappings);
    const blocks = linked.split(/\n\n+/);
    let html = '';
    blocks.forEach(function (raw) {
      const b = raw.trim();
      if (!b) return;

      if (/^#{1,3}\s/.test(b)) {
        const lines = b.split('\n');
        const h1 = inline(lines[0].replace(/^#{1,3}\s*/, ''));
        const h2 = lines.length > 1 ? inline(lines[1].replace(/^#{1,3}\s*/, '')) : '';
        html += '<div class="dge-gold-titlebanner"><div class="dge-gold-title-h1">' + h1 + '</div>' +
          (h2 ? '<div class="dge-gold-title-h2">' + h2 + '</div>' : '') + '</div>';
        return;
      }

      if (/^&gt;\s*\[!मङ्गलम्\]/.test(b) || /^>\s*\[!मङ्गलम्\]/.test(b)) {
        const padas = b.split('\n').slice(1).map(function (l) { return l.replace(/^&gt;\s*|^>\s*/, '').trim(); })
          .filter(Boolean).map(function (l) { return '<div class="dge-gold-verse-pada">' + inline(l) + '</div>'; }).join('');
        html += '<div class="dge-gold-mangala"><span class="dge-gold-mangala-badge">✦ मङ्गलश्लोकः (टीकाकृतः) ✦</span>' + padas + '</div>';
        return;
      }

      const pramanaMatch = b.match(/^(?:&gt;|>)\s*\[!प्रमाणम्\s*\(([^)]*)\)\]/);
      if (pramanaMatch) {
        const cite = inline(pramanaMatch[1] || 'प्रमाणम्');
        const padas = b.split('\n').slice(1).map(function (l) { return l.replace(/^&gt;\s*|^>\s*/, '').trim(); })
          .filter(Boolean).map(function (l) { return '<div class="dge-gold-verse-pada">' + inline(l) + '</div>'; }).join('');
        html += '<div class="dge-gold-pramana">' + padas +
          '<div class="dge-gold-pramana-footer"><span class="dge-gold-citation-chip">📖 ' + cite + '</span></div></div>';
        return;
      }

      if (/^(?:&gt;|>)\s*\[!फलितार्थः\]/.test(b)) {
        const clean = b.replace(/^(?:&gt;|>)\s*\[!फलितार्थः\]\s*/, '').replace(/^(?:&gt;|>)\s*/gm, '').trim();
        html += '<div class="dge-gold-phalitartha"><span class="dge-gold-phalitartha-tag">✦ Phalitārtha / Concluding Purport</span>' +
          '<p>' + inline(clean) + '</p></div>';
        return;
      }

      if (/^---/.test(b)) {
        html += '<div class="dge-gold-colophon">' + inline(b.replace(/---/g, '').trim()) + '</div>';
        return;
      }

      // Avataraṇikā (*अवतरणिका —* ...): a context-setting transition line,
      // marked by this exact italic lead-in per Part B2. Styled distinctly
      // but stays a normal paragraph in the flow -- it isn't its own
      // provenance container the way मङ्गलम्/प्रमाणम्/फलितार्थः are.
      if (/^\*अवतरणिका\s*—\*/.test(b)) {
        const rest = inline(b.replace(/^\*अवतरणिका\s*—\*/, '').trim());
        html += '<div class="dge-gold-avataranika">✦ ' + rest + '</div>';
        return;
      }

      html += '<p>' + inline(b) + '</p>';
    });
    return html;
  }

  // Public entry point. Returns null (not an empty string) when there's no
  // commentary_markdown to render, so a caller can fall back to plain-text
  // rendering the same way footnote-engine.js's render() signals "nothing
  // to render here."
  function render(commentaryObj) {
    if (!commentaryObj || !commentaryObj.commentary_markdown) return null;
    return {
      pillGridHtml: pillGrid(commentaryObj.word_mappings),
      bodyHtml: renderBlocks(commentaryObj.commentary_markdown, commentaryObj.word_mappings)
    };
  }

  return { render: render };
})();

window.DGEGoldRender = DGEGoldRender;

// Bidirectional jump: shared by both word-pills and pratika spans (each
// carries its own target in data-gold-target, pointing at the other
// side's id) -- scroll-margin-top on both classes (see main.css) keeps the
// target clear of the fixed top bar, and the pulse class replays its
// animation on every click even if the same target was just pulsed
// (remove-reflow-add, not a toggle) so rapid back-and-forth tapping still
// gives visible feedback each time.
window.dgeGoldJumpTo = function (el) {
  const targetId = el && el.getAttribute('data-gold-target');
  if (!targetId) return;
  const target = document.getElementById(targetId);
  if (!target) return;
  target.scrollIntoView({ behavior: 'smooth', block: 'center' });
  target.classList.remove('dge-gold-pulse');
  void target.offsetWidth;
  target.classList.add('dge-gold-pulse');
};

// The Gold-Standard badge (render.js) IS the switch between the rich view
// (pill grid + provenance boxes + pratīka links, the default) and a
// simplified view (main.css folds all of that back to plain paragraph
// flow via .dge-gold-simple) -- a CSS-only toggle, not a re-render, so it
// costs nothing and can't drift out of sync with the underlying data.
window.dgeToggleGoldSimple = function (badgeEl) {
  const wrapper = badgeEl && badgeEl.closest('.dge-gold-wrapper');
  if (!wrapper) return;
  const simple = wrapper.classList.toggle('dge-gold-simple');
  badgeEl.textContent = simple ? '🏅 Gold (simple)' : '🏅 Gold';
};
