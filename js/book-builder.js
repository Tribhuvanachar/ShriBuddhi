/* =========================================================================
   book-builder.js — prepare a book from the library and print it to PDF.

   Asked for from a publisher's point of view: pick a grantha and a
   commentary, or a range of sargas, or the verses you marked while reading,
   or a set from a corpus search; give it a title and a compiler; get a
   watermarked book out.

   WHY THE BROWSER PRINTS IT, and not a JS PDF library. jsPDF and pdfmake
   place glyphs one code point at a time. Devanagari does not work that way:
   क् + ष is one glyph क्ष, र् before a consonant becomes a repha riding the
   NEXT letter, and every saṃyuktākṣara in this corpus needs shaping those
   libraries do not do. A Sumadhva Vijaya rendered by jsPDF would be broken
   on nearly every line, confidently and invisibly to anyone who cannot read
   it. So the book is built as HTML, the browser shapes and paginates it,
   and Save-as-PDF in the print dialog produces the file. The same document
   feeds a headless-Chromium render later for a one-tap download — that is
   an extra delivery route for this exact output, not a rewrite.

   WHAT IS DELIBERATELY NOT HERE. No page-count estimate: the browser
   paginates at print time and any number shown before that would be a
   guess. No "download PDF" button that silently opens a print dialog —
   the button says what it does.
   ========================================================================= */
(function () {
  'use strict';
  window.DGE_VERSIONS = window.DGE_VERSIONS || {};
  window.DGE_VERSIONS['book-builder.js'] = 'v1.1 (11 Sep 2026: self-contained document + one-tap server PDF via renderBook) · v1.0 (publisher-style book preparation — cover, TOC, watermark, print-to-PDF)';

  var IMPRINT = 'Sarvamūla Digital Library';

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  /* Strip the reader's own markup out of a commentary before it goes into a
     book: word-tap spans, citation marks and pratīka links are reading aids,
     not typography. Footnote markers and line breaks are kept. */
  function plainText(html) {
    if (html == null) return '';
    var d = document.createElement('div');
    d.innerHTML = String(html).replace(/<br\s*\/?>/gi, '\n');
    return (d.textContent || '').replace(/[ \t]+\n/g, '\n').trim();
  }

  /* ---- The spec ---------------------------------------------------------
   * One plain object describes a whole book, so a preset can be saved,
   * shared or rebuilt later without re-driving the UI.
   */
  window.dgeBookDefaults = function () {
    return {
      title: '',
      subtitle: '',
      compiler: '',
      dedication: '',
      pageSize: 'a5',
      watermark: false,          // the diagonal one; the footer imprint is always on
      toc: true,
      includeCommentaries: [],   // commentary keys, in the order they should print
      includePadaccheda: false,
      sections: []               // [{ label, granthaSlug, units: [{id, sa, commentaries}] }]
    };
  };

  /* ---- Sources ----------------------------------------------------------
   * Each returns [{ id, sa, commentaries }] from what the reader already has
   * in memory, so preparing a book costs no extra fetch for the grantha the
   * person is looking at.
   */
  function unitsFromLoadedGrantha(filter) {
    var data = window.stotraData;
    if (!data || !data.shlokas) return [];
    return Object.keys(data.shlokas)
      .sort(function (a, b) { return Number(a) - Number(b); })
      .filter(function (id) { return !filter || filter(id, data.shlokas[id]); })
      .map(function (id) {
        var sh = data.shlokas[id] || {};
        return { id: id, sa: sh.sa || sh.sanskrit_text || '', commentaries: sh.commentaries || {} };
      })
      .filter(function (u) { return u.sa; });
  }

  window.dgeBookSources = {
    /** Everything in the grantha currently open. */
    whole: function () { return unitsFromLoadedGrantha(null); },

    /** A verse-number range, inclusive — "sargas 1 to 3" once the reader is
        in a sarga file, or any span the person types. */
    range: function (from, to) {
      var lo = Number(from), hi = Number(to);
      return unitsFromLoadedGrantha(function (id) {
        var n = Number(id);
        return (!isFinite(lo) || n >= lo) && (!isFinite(hi) || n <= hi);
      });
    },

    /** The verses starred while reading (state.js `marks`, per grantha). */
    favourites: function () {
      var marks = window.marks || {};
      return unitsFromLoadedGrantha(function (id) { return marks[id] && marks[id].fav; });
    },

    /** Verses marked with a reading status — the "I am working through
        these" set, which is a different selection from favourites. */
    studied: function () {
      var marks = window.marks || {};
      return unitsFromLoadedGrantha(function (id) {
        return marks[id] && (marks[id].status === 'practice' || marks[id].status === 'done');
      });
    },

    /** An explicit list of ids, which is how a corpus-search selection and
        the reader's own tick-boxes both arrive here. */
    ids: function (ids) {
      var want = {};
      (ids || []).forEach(function (i) { want[String(i)] = 1; });
      return unitsFromLoadedGrantha(function (id) { return want[String(id)]; });
    }
  };

  /* ---- Rendering --------------------------------------------------------- */

  /* A verse's stored text carries the reader's own line breaks as literal
     <br> tags. Escaping it whole printed "<br>" as words in the middle of
     every shloka (found 11 Sep 2026, looking at a rendered page). Escape
     first, THEN turn the breaks back into breaks: the order matters, because
     converting first would leave a real <br> in a string that then gets
     escaped anyway. Nothing else in the stored markup survives. */
  function verseHtml(text) {
    return esc(String(text == null ? '' : text).replace(/<br\s*\/?>/gi, '\n'))
      .replace(/\n/g, '<br>');
  }

  function renderVerse(u, spec, names) {
    var out = '<div class="dge-verse">';
    out += '<span class="dge-verse-num">' + esc(u.id) + '</span>';
    out += '<p class="dge-verse-text">' + verseHtml(u.sa) + '</p>';
    if (spec.includePadaccheda && window.dgePadaccheda && window.dgePadaccheda.units) {
      var rows = window.dgePadaccheda.units[String(u.id)];
      if (rows && rows.length) {
        out += '<p class="dge-padaccheda">' + rows.map(function (r) {
          return '<b>' + esc(r[0]) + '</b> = ' + esc(r.slice(2).join(' + '));
        }).join(' &nbsp;·&nbsp; ') + '</p>';
      }
    }
    (spec.includeCommentaries || []).forEach(function (key) {
      var text = u.commentaries && u.commentaries[key];
      if (typeof text !== 'string' || !text.trim()) return;
      out += '<div class="dge-comm">' +
        '<p class="dge-comm-title">' + esc(names[key] || key) + '</p>' +
        // plainText() has already turned <br> into newlines and stripped the
        // reader's spans; the breaks it left are real ones and should print.
        '<p class="dge-comm-body">' + esc(plainText(text)).replace(/\n/g, '<br>') + '</p></div>';
    });
    return out + '</div>';
  }

  /**
   * The whole book, as one standalone HTML document.
   *
   * Exported and pure (given a spec) so it can be unit-tested and, later,
   * handed to a headless renderer server-side without touching this page.
   */
  window.dgeBuildBookHtml = function (spec, opts) {
    var o = opts || {};
    var names = o.commentaryNames || {};
    var base = o.baseUrl || '';
    // Inlined when the caller has them (dgeBuildStandaloneBook fetches both),
    // linked otherwise. A server-side render needs the inlined form: the
    // renderer runs with every network request blocked, so a <link> would
    // silently produce an unstyled book.
    var icon = o.iconDataUri || (base + 'images/genie/favicon-192.png');
    var css = base + 'css/book-print.css';
    var total = (spec.sections || []).reduce(function (n, s) { return n + (s.units || []).length; }, 0);
    var today = new Date().toLocaleDateString('en-IN', { year: 'numeric', month: 'long', day: 'numeric' });

    var cover =
      '<section class="dge-cover">' +
      '<img class="dge-cover-icon" src="' + esc(icon) + '" alt="">' +
      '<h1>' + esc(spec.title || 'Untitled') + '</h1>' +
      (spec.subtitle ? '<h2>' + esc(spec.subtitle) + '</h2>' : '') +
      // The sources line names what the book draws on — but when there is
      // one section and its label is already the title, printing it again
      // is just the title twice on the same page.
      (function () {
        var labels = (spec.sections || []).map(function (s) { return s.label; }).filter(Boolean);
        var line = labels.join(' · ');
        if (!line || line === (spec.title || '')) return '';
        return '<p class="dge-cover-sources">' + esc(line) + '</p>';
      })() +
      (spec.compiler ? '<p class="dge-cover-compiler">' + esc(spec.compiler) + '</p>' : '') +
      '<p class="dge-cover-imprint">' + esc(IMPRINT) + ' · ' + esc(today) + '</p>' +
      '</section>';

    var front = '';
    if (spec.dedication) {
      front += '<section class="dge-frontmatter"><p class="dge-dedication">' +
        esc(spec.dedication).replace(/\n/g, '<br>') + '</p></section>';
    }
    if (spec.toc && (spec.sections || []).length > 1) {
      front += '<section class="dge-frontmatter dge-toc"><h3>Contents</h3><ol>' +
        spec.sections.map(function (s) {
          return '<li><span class="dge-toc-label">' + esc(s.label) + '</span>' +
            '<span class="dge-toc-count">' + (s.units || []).length + ' verses</span></li>';
        }).join('') + '</ol></section>';
    }

    var body = (spec.sections || []).map(function (s) {
      return '<section class="dge-book-section"><h2>' + esc(s.label) + '</h2>' +
        (s.units || []).map(function (u) { return renderVerse(u, spec, names); }).join('') +
        '</section>';
    }).join('');

    return '<!DOCTYPE html><html lang="sa"><head><meta charset="utf-8">' +
      '<title>' + esc(spec.title || 'Prepared book') + ' · ' + esc(IMPRINT) + '</title>' +
      '<meta name="viewport" content="width=device-width, initial-scale=1">' +
      (o.inlineCss ? '<style>' + String(o.inlineCss).replace(/<\/style/gi, '<\\/style') + '</style>'
                   : '<link rel="stylesheet" href="' + esc(css) + '">') +
      (spec.pageSize === 'a4' ? '<style>@page { size: A4; }</style>' : '') +
      '</head><body>' +
      // The preview toolbar is for a human looking at the book in a tab. A
      // document being rendered to PDF by a machine has nobody to press it,
      // and its onclick would be dead markup in a renderer with JavaScript
      // switched off.
      (o.forPrint ? '' :
        '<div class="dge-noprint" style="position:sticky;top:0;z-index:9;background:#1a1512;color:#fff;' +
        'padding:10px 14px;font:13px/1.4 system-ui,sans-serif;display:flex;gap:10px;align-items:center;">' +
        '<span>' + total + ' verses ready. Use your browser’s <b>Save as PDF</b> in the print dialog.</span>' +
        '<button onclick="window.print()" style="margin-left:auto;padding:6px 14px;border:0;border-radius:6px;' +
        'background:#e2664a;color:#fff;font:inherit;font-weight:700;cursor:pointer;">Print / Save as PDF</button>' +
        '</div>') +
      '<div class="dge-watermark' + (spec.watermark ? '' : ' dge-watermark-off') + '">' + esc(IMPRINT) + '</div>' +
      cover +
      '<div class="dge-book-body">' + front + body + '</div>' +
      '<div class="dge-runfoot"><img src="' + esc(icon) + '" alt="">' + esc(IMPRINT) + '</div>' +
      '</body></html>';
  };

  /**
   * Open the built book in its own window. A new window rather than an
   * iframe so the browser's own print dialog gets a document with nothing
   * of the reader's chrome in it, and so the person can look through the
   * whole thing before committing it to paper or PDF.
   */
  window.dgeOpenPreparedBook = function (spec, opts) {
    var html = window.dgeBuildBookHtml(spec, opts);
    var w = window.open('', '_blank');
    if (!w) {
      if (typeof showToast === 'function') showToast('Allow pop-ups for this site to open the prepared book.');
      return null;
    }
    w.document.open();
    w.document.write(html);
    w.document.close();
    return w;
  };

  /* ---- One-tap PDF ------------------------------------------------------
   *
   * The print dialog stays the default and the fallback: it is free, it
   * needs no account, and it is the same engine. This is the route that
   * hands back a FILE instead of asking someone to find "Save as PDF",
   * pick the paper size and hope. It needs appConfig.bookPdfUrl pointing at
   * the renderBook function, which needs the Blaze plan, which is why it is
   * off unless configured rather than always on.
   */

  /** Fetch text, or null — a missing asset must not stop a book being built. */
  function fetchText(url) {
    return fetch(url).then(function (r) { return r.ok ? r.text() : null; })
      .catch(function () { return null; });
  }

  /** Fetch an image as a data: URI, or null. */
  function fetchDataUri(url) {
    return fetch(url).then(function (r) { return r.ok ? r.blob() : null; })
      .then(function (b) {
        if (!b) return null;
        return new Promise(function (resolve) {
          var fr = new FileReader();
          fr.onload = function () { resolve(fr.result); };
          fr.onerror = function () { resolve(null); };
          fr.readAsDataURL(b);
        });
      }).catch(function () { return null; });
  }

  /**
   * The book as ONE self-contained document — stylesheet and imprint icon
   * inlined, no external reference left in it.
   *
   * This is what makes a server-side render safe to allow: the renderer can
   * then run with every network request blocked, because a correct book
   * needs nothing from the network. A document that does need something was
   * not built here.
   */
  window.dgeBuildStandaloneBook = function (spec, opts) {
    var o = opts || {};
    var base = o.baseUrl || '';
    return Promise.all([
      fetchText(base + 'css/book-print.css'),
      fetchDataUri(base + 'images/genie/favicon-192.png')
    ]).then(function (parts) {
      var merged = {};
      Object.keys(o).forEach(function (k) { merged[k] = o[k]; });
      merged.forPrint = true;
      if (parts[0]) merged.inlineCss = parts[0];
      if (parts[1]) merged.iconDataUri = parts[1];
      return window.dgeBuildBookHtml(spec, merged);
    });
  };

  /** The renderBook endpoint, or '' when one-tap PDF is not configured. */
  window.dgeBookPdfUrl = function () {
    var u = (window.appConfig && window.appConfig.bookPdfUrl) || '';
    return (typeof u === 'string' && u.trim()) ? u.trim().replace(/\/+$/, '') : '';
  };

  /**
   * Ask the server for the finished PDF and save it.
   *
   * Resolves to true when a file was delivered, false when the caller should
   * fall back to the print dialog — every failure path resolves false rather
   * than throwing, because "the download did not work" must land the person
   * on the working route, not on an error.
   */
  window.dgeDownloadPreparedBook = function (spec, opts) {
    var url = window.dgeBookPdfUrl();
    if (!url) return Promise.resolve(false);
    return window.dgeBuildStandaloneBook(spec, opts).then(function (html) {
      return Promise.resolve(
        (window.dgeIdTokenForApi ? window.dgeIdTokenForApi() : null)
      ).then(function (token) {
        if (!token) return false;
        return fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
          body: JSON.stringify({ spec: spec, html: html })
        }).then(function (r) {
          if (!r.ok) return false;
          return r.blob().then(function (blob) {
            var a = document.createElement('a');
            var href = URL.createObjectURL(blob);
            a.href = href;
            a.download = (String(spec.title || '').replace(/[^A-Za-z0-9 _-]+/g, ' ')
              .replace(/\s+/g, '-').replace(/^-+|-+$/g, '') || 'sarvamula-book') + '.pdf';
            document.body.appendChild(a);
            a.click();
            a.remove();
            setTimeout(function () { URL.revokeObjectURL(href); }, 10000);
            return true;
          });
        });
      });
    }).catch(function (e) {
      console.warn('[Book] PDF download failed, falling back to print:', e && e.message);
      return false;
    });
  };

  /** Who may prepare a book — a granted capability, like copy. */
  window.dgeMayPrepareBook = function () {
    return typeof window.dgeRoleCan === 'function' ? window.dgeRoleCan('book') : false;
  };
})();
