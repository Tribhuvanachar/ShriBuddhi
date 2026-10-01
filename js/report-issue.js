/* =========================================================================
   report-issue.js — "Report a problem", from any page, with the context an editor needs.

   A reader who finds a wrong verse, a missing commentary, a dhātu with a wrong form, a
   sandhi split that is not one, or a word that will not resolve should be able to say so
   in two taps, and the person who fixes it should not have to ask "which page? which text?
   what was on screen?". So the form fills that in itself:

     feature   which part of the site this was raised from (reader, sandhi popover, dhātu, ...)
     subject   the verse id / word / root the report is about, when the caller knows it
     page      full URL, the library path (?path=), the page title, the script mode
     selected  whatever text the reader had selected
     extra     what the feature was showing at that moment (the analysis, the split, ...)
     browser   user agent, viewport, time (ISO)
     picture   a screenshot of the page (the reader can untick it; it is taken before the form opens)

   Where it goes:
     * signed in  -> a document in Firestore `reports/` (firebase/firestore.rules lets any signed-in
                     user create one and only admins read it); admin/reports.html lists them with the
                     screenshot. Nothing is e-mailed to the editor's inbox.
     * not signed in, or the write fails -> the reader's own mail app, pre-filled with every field
                     except the picture, which is offered as a download to attach.

   Entry points: the footer's "Report a problem" (js/site-footer.js, js/dge-shell.js), the word
   popover's ⚑ (js/intellisense.js), the verse/typo form and the "report as missing" links
   (js/modals.js). Anything else:   window.dgeReport({ feature, subject, extra, category })
   A page may define window.dgeReportContext = function(){ return {...} } to add its own fields.
   ========================================================================= */
(function () {
  'use strict';
  if (window.dgeReport) return;

  var CATEGORIES = [
    ['wrong-text', 'Wrong or garbled text (a typo, a missing line)'],
    ['missing-text', 'A text, commentary or verse is missing'],
    ['wrong-mapping', 'A commentary / ṭippaṇī is attached to the wrong verse or work'],
    ['wrong-form', 'A dhātu, śabda or other form is wrong'],
    ['not-resolving', 'A word, dhātu or śabda does not resolve'],
    ['wrong-split', 'A sandhi or padaccheda split is wrong'],
    ['other', 'Something else']
  ];
  var SELF = (document.currentScript && document.currentScript.src) || '';

  function el(tag, attrs, html) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    if (html != null) e.innerHTML = html;
    return e;
  }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  function nearestVerseId(node) {
    for (var n = node && (node.nodeType === 1 ? node : node.parentElement); n && n !== document.body; n = n.parentElement) {
      var v = n.getAttribute && (n.getAttribute('data-shloka-id') || n.getAttribute('data-uid') || n.getAttribute('data-id') || n.getAttribute('data-unit'));
      if (v) return v;
      if (n.id && /^(shloka|sh|verse|unit|s)[-_]?[\w.]+$/i.test(n.id)) return n.id;
    }
    return '';
  }

  function gather(opts) {
    var sel = '', verse = '';
    try {
      var s = window.getSelection && window.getSelection();
      if (s && !s.isCollapsed) { sel = s.toString().trim().slice(0, 400); verse = nearestVerseId(s.anchorNode); }
    } catch (e) { /* none */ }
    var q = new URLSearchParams(location.search);
    var base = {
      feature: opts.feature || 'page',
      subject: String(opts.subject || verse || '').slice(0, 300),
      url: location.href,
      path: q.get('path') || q.get('grantha') || q.get('gen') || location.hash.replace(/^#/, '') || '',
      title: document.title,
      selected: sel,
      script: (function () { try { return localStorage.getItem('dge.script') || localStorage.getItem('dge.kavya.v2') || ''; } catch (e) { return ''; } })().slice(0, 120),
      extra: opts.extra || '',
      ua: navigator.userAgent.slice(0, 250),
      viewport: window.innerWidth + 'x' + window.innerHeight,
      at: new Date().toISOString()
    };
    try {
      if (typeof window.dgeReportContext === 'function') {
        var c = window.dgeReportContext() || {};
        Object.keys(c).forEach(function (k) { if (c[k] != null && k !== 'screenshot') base[k] = typeof c[k] === 'string' ? c[k].slice(0, 1000) : c[k]; });
      }
    } catch (e) { /* a page's hook must never break the form */ }
    return base;
  }

  function loadScript(src) {
    return new Promise(function (ok, no) {
      var s = document.createElement('script');
      s.src = src; s.onload = ok; s.onerror = no;
      document.head.appendChild(s);
    });
  }

  // A small JPEG of the page. Never throws; resolves '' when it cannot.
  function shoot() {
    var go = function () {
      return window.html2canvas(document.body, {
        scale: Math.min(1, 900 / Math.max(window.innerWidth, 600)),
        logging: false, useCORS: true, backgroundColor: null,
        x: window.scrollX, y: window.scrollY, width: window.innerWidth, height: window.innerHeight,
        windowWidth: window.innerWidth, windowHeight: window.innerHeight
      }).then(function (cv) {
        var q = 0.6, out = cv.toDataURL('image/jpeg', q);
        while (out.length > 600000 && q > 0.2) { q -= 0.1; out = cv.toDataURL('image/jpeg', q); }
        return out.length > 650000 ? '' : out;
      });
    };
    var p = window.html2canvas ? Promise.resolve() :
      loadScript('https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js');
    return p.then(go).catch(function () { return ''; });
  }

  function mailBody(r) {
    return ['Feature: ' + r.feature, 'Category: ' + r.category, 'Subject: ' + r.subject,
            'Library path: ' + r.path, 'Page: ' + r.url, 'Title: ' + r.title,
            r.selected ? 'Selected text: ' + r.selected : '', r.extra ? 'On screen: ' + r.extra : '',
            'Script: ' + r.script, 'Browser: ' + r.ua, 'Viewport: ' + r.viewport, 'Time: ' + r.at, '',
            'What is wrong:', r.message].filter(function (x) { return x !== ''; }).join('\n');
  }

  function sendFirestore(r) {
    return Promise.resolve().then(function () {
      var fb = window.firebase;
      if (!fb || !fb.auth || !fb.firestore) return Promise.reject(new Error('no-sdk'));
      var u = fb.auth().currentUser;
      if (!u) return Promise.reject(new Error('signed-out'));
      var doc = {
        uid: u.uid, email: u.email || '', feature: r.feature, category: r.category, message: r.message,
        subject: r.subject, url: r.url, path: r.path, title: r.title, selected: r.selected,
        extra: typeof r.extra === 'string' ? r.extra : JSON.stringify(r.extra).slice(0, 2000),
        ua: r.ua, viewport: r.viewport, script: r.script, createdAt: fb.firestore.FieldValue.serverTimestamp(), status: 'new'
      };
      if (r.screenshot) doc.screenshot = r.screenshot;
      return fb.firestore().collection('reports').add(doc);
    });
  }

  function open(opts) {
    opts = opts || {};
    var ctx = gather(opts);
    var overlay = el('div', { 'class': 'dge-rp-overlay', role: 'dialog', 'aria-modal': 'true', 'aria-label': 'Report a problem' });
    var shotPromise = null;
    var shotData = '';
    // The picture is taken BEFORE the form is on screen, so it shows what the reader was looking at.
    shotPromise = Promise.race([shoot(), new Promise(function (r) { setTimeout(function () { r(''); }, 5000); })])
      .then(function (d) { shotData = d; return d; });

    shotPromise.then(function () {
      var card = el('div', { 'class': 'dge-rp-card' });
      card.innerHTML =
        '<div class="dge-rp-head"><b>Report a problem</b><button class="dge-rp-x" aria-label="Close">✕</button></div>' +
        '<label class="dge-rp-l">What kind of problem?<select class="dge-rp-cat">' +
        CATEGORIES.map(function (c) { return '<option value="' + c[0] + '"' + (c[0] === (opts.category || '') ? ' selected' : '') + '>' + esc(c[1]) + '</option>'; }).join('') +
        '</select></label>' +
        '<label class="dge-rp-l">What is wrong, and what should it be?<textarea class="dge-rp-msg" rows="4" placeholder="e.g. the second line has a missing word; it should read …">' + esc(opts.message || '') + '</textarea></label>' +
        '<details class="dge-rp-ctx"><summary>What will be sent with this</summary><table>' +
        [['Feature', ctx.feature], ['Subject', ctx.subject], ['Library path', ctx.path], ['Page', ctx.url], ['Selected text', ctx.selected],
         ['On screen', typeof ctx.extra === 'string' ? ctx.extra : JSON.stringify(ctx.extra)], ['Time', ctx.at]]
          .filter(function (p) { return p[1]; }).map(function (p) { return '<tr><td>' + esc(p[0]) + '</td><td>' + esc(String(p[1]).slice(0, 300)) + '</td></tr>'; }).join('') +
        '</table></details>' +
        (shotData ? '<label class="dge-rp-chk"><input type="checkbox" class="dge-rp-shot" checked> Include a screenshot of this page</label>' +
                    '<img class="dge-rp-thumb" alt="Screenshot preview" src="' + shotData + '">' : '<p class="dge-rp-note">A screenshot could not be taken here.</p>') +
        '<div class="dge-rp-actions"><button class="dge-rp-send">Send</button><button class="dge-rp-mail">E-mail instead</button></div>' +
        '<p class="dge-rp-status" aria-live="polite"></p>';
      overlay.appendChild(card);
      document.body.appendChild(overlay);
      var status = card.querySelector('.dge-rp-status');
      function build() {
        var r = JSON.parse(JSON.stringify(ctx));
        r.category = card.querySelector('.dge-rp-cat').value;
        r.message = card.querySelector('.dge-rp-msg').value.trim();
        var chk = card.querySelector('.dge-rp-shot');
        r.screenshot = (shotData && chk && chk.checked) ? shotData : '';
        return r;
      }
      function close() { overlay.remove(); }
      card.querySelector('.dge-rp-x').onclick = close;
      overlay.addEventListener('click', function (e) { if (e.target === overlay) close(); });
      function viaMail(r) {
        var email = window.DGE_CONTACT_EMAIL || 'sanatanavidyagurukulam@gmail.com';
        if (r.screenshot) {
          var a = el('a', { href: r.screenshot, download: 'report-screenshot.jpg' }); document.body.appendChild(a); a.click(); a.remove();
        }
        location.href = 'mailto:' + email + '?subject=' + encodeURIComponent('Report: ' + r.feature + (r.subject ? ' — ' + r.subject : '')) +
                        '&body=' + encodeURIComponent(mailBody(r) + (r.screenshot ? '\n\n(Please attach the screenshot that was just saved: report-screenshot.jpg)' : ''));
      }
      card.querySelector('.dge-rp-mail').onclick = function () {
        var r = build(); if (!r.message) { status.textContent = 'Please say what is wrong first.'; return; } viaMail(r);
      };
      card.querySelector('.dge-rp-send').onclick = function () {
        var r = build(); if (!r.message) { status.textContent = 'Please say what is wrong first.'; return; }
        status.textContent = 'Sending…';
        sendFirestore(r).then(function () {
          status.textContent = 'Thank you — the editors have it.';
          setTimeout(close, 1800);
        }).catch(function (e) {
          status.textContent = (e && e.message === 'signed-out') ? 'Sign in to send it directly; opening your e-mail instead…' : 'Could not send directly; opening your e-mail instead…';
          setTimeout(function () { viaMail(r); }, 900);
        });
      };
      var t = card.querySelector('.dge-rp-msg'); if (t) t.focus();
    });
  }

  window.dgeReport = open;
  window.dgeReportEnsureCss = function () {
    if (document.getElementById('dge-rp-css')) return;
    var href = '';
    try { href = new URL('../css/report-issue.css', SELF).href; } catch (e) { href = 'css/report-issue.css'; }
    var l = el('link', { id: 'dge-rp-css', rel: 'stylesheet', href: href }); document.head.appendChild(l);
  };
  window.dgeReportEnsureCss();
})();
