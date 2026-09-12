// dge/js/config-editor.js — form-based editor for the site's editable
// text settings. Super-admin only.
//
// DESIGN DECISION: this never touches config.js.
//
// config.js is executable JavaScript containing structure, functions,
// comments and API wiring. A UI that rewrote it would risk corrupting
// working code on a bad edit — which is exactly why a config UI was
// deferred for so long. Instead this reads and writes a plain data file,
// admin/config/config-overrides.json, holding ONLY the fields exposed below.
// core.js merges it over the defaults at load. Consequences:
//   - a mistake can only ever change a piece of text, never break the app
//   - deleting the overrides file restores every default instantly
//   - config.js stays the single source of structure, hand-edited as before
window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['config-editor.js'] = 'v1.3 (10 Sep 2026: a Word tools section -- appConfig.wordActions was read by config.js and written by nothing, so "turn Sandhi/Samasa off for everyone" had no page to do it on) \u00b7 v1.2 (toggle for appConfig.showCopyrightGatedCommentaries)';

const DGE_CONFIG_OVERRIDES_PATH = 'admin/config/config-overrides.json';
// What's New is content rather than a setting, and lives in its own file so
// the reader can fetch it fresh on every open (see modals.js). The editor
// still edits it in the same form; it just lands somewhere else on save.
const DGE_WHATS_NEW_PATH = 'admin/content/whats-new.json';
// The Support and About panels' text, likewise content rather than settings.
const DGE_READER_CONTENT_PATH = 'admin/content/reader.json';
const DGE_READER_CONTENT_KEYS = ['SPONSOR_CONFIG', 'CONTRIBUTORS_CONFIG', 'KEY_SPONSORS_CONFIG'];

// Only these are editable. Anything not listed here is untouchable from
// the UI by construction, not by validation — a field that isn't rendered
// can't be saved.
const DGE_EDITABLE_TEXT_FIELDS = [
  { key: 'appName', label: 'App name', hint: 'Shown in share images and page metadata.' },
  { key: 'contactEmail', label: 'Contact email', hint: 'Used by the About modal and sponsor links.' },
  { key: 'sarvamoolaProjectText', label: 'Project support text', hint: 'Shown in the support banner.' },
  { key: 'audioBaseUrl', label: 'Audio source base URL', hint: 'The shared host prefix for every grantha\'s audio (e.g. https://archive.org/download/) — must end with a slash. Each grantha\'s own identifier folder/filename stays exactly as stored; only this shared prefix changes. An end user can further override this on their own device in ⚙️ Settings.' }
];

let dgeConfigDraft = null;

function dgeEsc(s) {
  const d = document.createElement('div');
  d.textContent = s == null ? '' : String(s);
  return d.innerHTML;
}

// Builds the draft from what's currently live in memory (defaults already
// merged with any existing overrides), so the form always shows what the
// site is actually using right now.
function dgeBuildDraft() {
  const app = window.appConfig || {};
  const sp = window.SPONSOR_CONFIG || {};
  const co = window.CONTRIBUTORS_CONFIG || {};
  const ks = window.KEY_SPONSORS_CONFIG || {};
  const wn = window.WHATS_NEW_CONFIG || {};
  return {
    appConfig: {
      appName: app.appName || '',
      showCopyrightGatedCommentaries: app.showCopyrightGatedCommentaries === true,
      contactEmail: app.contactEmail || '',
      sarvamoolaProjectText: app.sarvamoolaProjectText || '',
      audioBaseUrl: app.audioBaseUrl || '',
      // Which word tools the 🕉️ Genie row offers, for EVERY visitor.
      // Shipped defaults live in WORD_ACTIONS (config.js); this object only
      // holds the ones an admin has deliberately overridden, so a tool added
      // to the registry later arrives switched to its own default rather than
      // silently off because an old save didn't mention it.
      wordActions: Object.assign({}, app.wordActions || {})
    },
    SPONSOR_CONFIG: {
      enabled: sp.enabled !== false,
      introText: sp.introText || '',
      contactForSponsorship: sp.contactForSponsorship || '',
      sponsorCategories: (sp.sponsorCategories || []).map(c => ({
        icon: c.icon || '', label: c.label || '',
        description: c.description || '', enabled: c.enabled !== false
      }))
    },
    CONTRIBUTORS_CONFIG: {
      enabled: co.enabled !== false,
      contributors: (co.contributors || []).map(c => ({ name: c.name || '', role: c.role || '' }))
    },
    KEY_SPONSORS_CONFIG: {
      enabled: ks.enabled !== false,
      sponsors: (ks.sponsors || []).map(s => ({ name: s.name || '', contribution: s.contribution || '' }))
    },
    WHATS_NEW_CONFIG: {
      enabled: wn.enabled !== false,
      updates: (wn.updates || []).map(u => ({ date: u.date || '', title: u.title || '', description: u.description || '' })),
      comingSoon: (wn.comingSoon || []).map(c => ({ title: c.title || '', description: c.description || '' }))
    }
  };
}

function dgeField(path, value, label, hint, multiline) {
  const input = multiline
    ? `<textarea rows="3" oninput="window.dgeConfigSet('${path}', this.value)"
         style="width:100%; box-sizing:border-box; font-size:13px; padding:8px;
                border:1px solid var(--card-border); border-radius:6px;
                background:var(--bg-main); color:var(--text-primary);">${dgeEsc(value)}</textarea>`
    : `<input type="text" value="${dgeEsc(value)}" oninput="window.dgeConfigSet('${path}', this.value)"
         style="width:100%; box-sizing:border-box; font-size:13px; padding:8px;
                border:1px solid var(--card-border); border-radius:6px;
                background:var(--bg-main); color:var(--text-primary);">`;
  return `<div style="margin-bottom:12px;">
    <label style="display:block; font-size:11px; font-weight:700; text-transform:uppercase;
                  color:var(--muted-text); margin-bottom:4px;">${dgeEsc(label)}</label>
    ${input}
    ${hint ? `<div class="hint" style="font-size:10px; margin-top:3px;">${dgeEsc(hint)}</div>` : ''}
  </div>`;
}

function dgeToggle(path, value, label) {
  return `<label style="display:flex; align-items:center; gap:8px; margin-bottom:12px; cursor:pointer;">
    <input type="checkbox" ${value ? 'checked' : ''}
           onchange="window.dgeConfigSet('${path}', this.checked)"
           style="width:20px; height:20px;">
    <span style="font-size:13px;">${dgeEsc(label)}</span>
  </label>`;
}

let dgeSectionSeq = 0;
// Which sections are open, keyed by title — survives across
// dgeRenderConfigEditor() re-renders (triggered by Add/Remove/Move row)
// so those actions don't silently collapse whatever the admin had open.
// Only reset when the editor is freshly opened (see openConfigEditor).
let dgeOpenSections = {};

// dgeEsc is HTML-escaping (safe for text NODE content) — it does nothing
// for a single quote, since a raw apostrophe is perfectly valid inside a
// text node. That makes it the WRONG escape for a value being embedded
// inside a single-quoted JS string literal in an onclick="" attribute — a
// title like "What's New" would end its own JS string early at the
// apostrophe, breaking the handler with a syntax error. This one escapes
// backslash and single-quote specifically for that context instead.
function dgeJsStringEsc(s) {
  return String(s).replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}

// Collapsible, and collapsed by default apart from the first — the full
// form is far taller than a phone screen, so showing it all at once made
// the panel unusable.
function dgeSection(title, body, openByDefault) {
  const id = 'cfgSec' + (dgeSectionSeq++);
  if (!(title in dgeOpenSections)) dgeOpenSections[title] = !!openByDefault;
  const isOpen = dgeOpenSections[title];
  return `<div style="margin-bottom:10px; border:1px solid var(--card-border);
                      border-radius:8px; background:var(--card-bg); overflow:hidden;">
    <div onclick="window.dgeToggleConfigSection('${id}', this, '${dgeJsStringEsc(title)}')"
         style="cursor:pointer; padding:12px; display:flex; align-items:center; gap:8px;
                font-size:12px; font-weight:800; text-transform:uppercase; color:var(--accent-red);">
      <span style="font-size:10px; width:10px;">${isOpen ? '▾' : '▸'}</span>
      <span style="flex:1;">${dgeEsc(title)}</span>
    </div>
    <div id="${id}" style="display:${isOpen ? 'block' : 'none'}; padding:0 12px 12px;">${body}</div>
  </div>`;
}

window.dgeToggleConfigSection = function(id, header, title) {
  const el = document.getElementById(id);
  if (!el) return;
  const open = el.style.display !== 'none';
  el.style.display = open ? 'none' : 'block';
  const arrow = header.querySelector('span');
  if (arrow) arrow.textContent = open ? '▸' : '▾';
  if (title) dgeOpenSections[title] = !open;
};

window.dgeConfigSet = function(path, value) {
  if (!dgeConfigDraft) return;
  const parts = path.split('.');
  let node = dgeConfigDraft;
  for (let i = 0; i < parts.length - 1; i++) {
    const k = /^\d+$/.test(parts[i]) ? parseInt(parts[i], 10) : parts[i];
    node = node[k];
    if (!node) return;
  }
  const last = parts[parts.length - 1];
  node[/^\d+$/.test(last) ? parseInt(last, 10) : last] = value;
};

window.dgeConfigAddRow = function(listPath, template) {
  const parts = listPath.split('.');
  let node = dgeConfigDraft;
  parts.forEach(p => { node = node[p]; });
  node.push(JSON.parse(template));
  dgeRenderConfigEditor();
};

window.dgeConfigRemoveRow = function(listPath, idx) {
  if (!confirm('Remove this entry?')) return;
  const parts = listPath.split('.');
  let node = dgeConfigDraft;
  parts.forEach(p => { node = node[p]; });
  node.splice(idx, 1);
  dgeRenderConfigEditor();
};

window.dgeConfigMoveRow = function(listPath, idx, delta) {
  const parts = listPath.split('.');
  let node = dgeConfigDraft;
  parts.forEach(p => { node = node[p]; });
  const newIdx = idx + delta;
  if (newIdx < 0 || newIdx >= node.length) return;
  [node[idx], node[newIdx]] = [node[newIdx], node[idx]];
  dgeRenderConfigEditor();
};

function dgeRenderConfigEditor() {
  dgeSectionSeq = 0;
  const el = document.getElementById('configEditorBody');
  if (!el || !dgeConfigDraft) return;
  const d = dgeConfigDraft;

  const general = DGE_EDITABLE_TEXT_FIELDS.map(f =>
    dgeField('appConfig.' + f.key, d.appConfig[f.key], f.label, f.hint,
             f.key === 'sarvamoolaProjectText')
  ).join('') + dgeToggle('appConfig.showCopyrightGatedCommentaries', d.appConfig.showCopyrightGatedCommentaries,
      'Show the Mahabharata Kannada translation & Tatparya Nirnaya excerpts (unlicensed source -- leave off unless rights are confirmed)');

  const sponsorRows = d.SPONSOR_CONFIG.sponsorCategories.map((c, i) => `
    <div style="border-top:1px dashed var(--card-border); padding-top:10px; margin-top:10px;">
      <div style="display:flex; gap:6px; align-items:center; margin-bottom:6px;">
        <input type="text" value="${dgeEsc(c.icon)}"
               oninput="window.dgeConfigSet('SPONSOR_CONFIG.sponsorCategories.${i}.icon', this.value)"
               style="width:46px; flex:none; text-align:center; font-size:16px; padding:6px;
                      border:1px solid var(--card-border); border-radius:6px;
                      background:var(--bg-main); color:var(--text-primary);">
        <input type="text" value="${dgeEsc(c.label)}" placeholder="Label"
               oninput="window.dgeConfigSet('SPONSOR_CONFIG.sponsorCategories.${i}.label', this.value)"
               style="flex:1; min-width:0; font-size:13px; padding:6px; border:1px solid var(--card-border);
                      border-radius:6px; background:var(--bg-main); color:var(--text-primary);">
        <button class="btn-sm" style="flex:none; color:var(--accent-red);"
                onclick="window.dgeConfigRemoveRow('SPONSOR_CONFIG.sponsorCategories', ${i})">🗑️</button>
      </div>
      <textarea rows="2"
        oninput="window.dgeConfigSet('SPONSOR_CONFIG.sponsorCategories.${i}.description', this.value)"
        style="width:100%; box-sizing:border-box; font-size:12px; padding:6px;
               border:1px solid var(--card-border); border-radius:6px;
               background:var(--bg-main); color:var(--text-primary);">${dgeEsc(c.description)}</textarea>
      ${dgeToggle(`SPONSOR_CONFIG.sponsorCategories.${i}.enabled`, c.enabled, 'Visible')}
    </div>`).join('');

  const contribRows = d.CONTRIBUTORS_CONFIG.contributors.map((c, i) => `
    <div style="border-top:1px dashed var(--card-border); padding-top:8px; margin-bottom:8px;">
      <div style="display:flex; gap:6px; margin-bottom:5px;">
        <input type="text" value="${dgeEsc(c.name)}" placeholder="Name"
               oninput="window.dgeConfigSet('CONTRIBUTORS_CONFIG.contributors.${i}.name', this.value)"
               style="flex:1; min-width:0; font-size:13px; padding:6px; border:1px solid var(--card-border);
                      border-radius:6px; background:var(--bg-main); color:var(--text-primary);">
        <button class="btn-sm" style="flex:none; ${i === 0 ? 'opacity:0.3;' : ''}" title="Move up"
                ${i === 0 ? 'disabled' : ''} onclick="window.dgeConfigMoveRow('CONTRIBUTORS_CONFIG.contributors', ${i}, -1)">▲</button>
        <button class="btn-sm" style="flex:none; ${i === d.CONTRIBUTORS_CONFIG.contributors.length - 1 ? 'opacity:0.3;' : ''}" title="Move down"
                ${i === d.CONTRIBUTORS_CONFIG.contributors.length - 1 ? 'disabled' : ''} onclick="window.dgeConfigMoveRow('CONTRIBUTORS_CONFIG.contributors', ${i}, 1)">▼</button>
        <button class="btn-sm" style="flex:none; color:var(--accent-red);"
                onclick="window.dgeConfigRemoveRow('CONTRIBUTORS_CONFIG.contributors', ${i})">🗑️</button>
      </div>
      <input type="text" value="${dgeEsc(c.role)}" placeholder="Role (optional)"
             oninput="window.dgeConfigSet('CONTRIBUTORS_CONFIG.contributors.${i}.role', this.value)"
             style="width:100%; box-sizing:border-box; font-size:12px; padding:6px;
                    border:1px solid var(--card-border); border-radius:6px;
                    background:var(--bg-main); color:var(--text-primary);">
    </div>`).join('');

  const keySponsorRows = d.KEY_SPONSORS_CONFIG.sponsors.map((s, i) => `
    <div style="border-top:1px dashed var(--card-border); padding-top:8px; margin-bottom:8px;">
      <div style="display:flex; gap:6px; margin-bottom:5px;">
        <input type="text" value="${dgeEsc(s.name)}" placeholder="Name"
               oninput="window.dgeConfigSet('KEY_SPONSORS_CONFIG.sponsors.${i}.name', this.value)"
               style="flex:1; min-width:0; font-size:13px; padding:6px; border:1px solid var(--card-border);
                      border-radius:6px; background:var(--bg-main); color:var(--text-primary);">
        <button class="btn-sm" style="flex:none; ${i === 0 ? 'opacity:0.3;' : ''}" title="Move up"
                ${i === 0 ? 'disabled' : ''} onclick="window.dgeConfigMoveRow('KEY_SPONSORS_CONFIG.sponsors', ${i}, -1)">▲</button>
        <button class="btn-sm" style="flex:none; ${i === d.KEY_SPONSORS_CONFIG.sponsors.length - 1 ? 'opacity:0.3;' : ''}" title="Move down"
                ${i === d.KEY_SPONSORS_CONFIG.sponsors.length - 1 ? 'disabled' : ''} onclick="window.dgeConfigMoveRow('KEY_SPONSORS_CONFIG.sponsors', ${i}, 1)">▼</button>
        <button class="btn-sm" style="flex:none; color:var(--accent-red);"
                onclick="window.dgeConfigRemoveRow('KEY_SPONSORS_CONFIG.sponsors', ${i})">🗑️</button>
      </div>
      <input type="text" value="${dgeEsc(s.contribution)}" placeholder="What they cover"
             oninput="window.dgeConfigSet('KEY_SPONSORS_CONFIG.sponsors.${i}.contribution', this.value)"
             style="width:100%; box-sizing:border-box; font-size:12px; padding:6px;
                    border:1px solid var(--card-border); border-radius:6px;
                    background:var(--bg-main); color:var(--text-primary);">
    </div>`).join('');

  const whatsNewUpdateRows = d.WHATS_NEW_CONFIG.updates.map((u, i) => `
    <div style="border-top:1px dashed var(--card-border); padding-top:8px; margin-bottom:8px;">
      <div style="display:flex; gap:6px; margin-bottom:5px;">
        <input type="date" value="${dgeEsc(u.date)}" title="Date (used to sort newest-first)"
               oninput="window.dgeConfigSet('WHATS_NEW_CONFIG.updates.${i}.date', this.value)"
               style="flex:none; width:130px; font-size:12px; padding:6px; border:1px solid var(--card-border);
                      border-radius:6px; background:var(--bg-main); color:var(--text-primary);">
        <input type="text" value="${dgeEsc(u.title)}" placeholder="Title"
               oninput="window.dgeConfigSet('WHATS_NEW_CONFIG.updates.${i}.title', this.value)"
               style="flex:1; min-width:0; font-size:13px; padding:6px; border:1px solid var(--card-border);
                      border-radius:6px; background:var(--bg-main); color:var(--text-primary);">
      </div>
      <textarea rows="2" placeholder="Description"
        oninput="window.dgeConfigSet('WHATS_NEW_CONFIG.updates.${i}.description', this.value)"
        style="width:100%; box-sizing:border-box; font-size:12px; padding:6px; margin-bottom:5px;
               border:1px solid var(--card-border); border-radius:6px;
               background:var(--bg-main); color:var(--text-primary);">${dgeEsc(u.description)}</textarea>
      <div style="display:flex; gap:6px;">
        <button class="btn-sm" style="flex:none; ${i === 0 ? 'opacity:0.3;' : ''}" title="Move up"
                ${i === 0 ? 'disabled' : ''} onclick="window.dgeConfigMoveRow('WHATS_NEW_CONFIG.updates', ${i}, -1)">▲</button>
        <button class="btn-sm" style="flex:none; ${i === d.WHATS_NEW_CONFIG.updates.length - 1 ? 'opacity:0.3;' : ''}" title="Move down"
                ${i === d.WHATS_NEW_CONFIG.updates.length - 1 ? 'disabled' : ''} onclick="window.dgeConfigMoveRow('WHATS_NEW_CONFIG.updates', ${i}, 1)">▼</button>
        <button class="btn-sm" style="flex:none; color:var(--accent-red); margin-left:auto;"
                onclick="window.dgeConfigRemoveRow('WHATS_NEW_CONFIG.updates', ${i})">🗑️ Remove</button>
      </div>
    </div>`).join('');

  const whatsNewComingSoonRows = d.WHATS_NEW_CONFIG.comingSoon.map((c, i) => `
    <div style="border-top:1px dashed var(--card-border); padding-top:8px; margin-bottom:8px;">
      <div style="display:flex; gap:6px; margin-bottom:5px;">
        <input type="text" value="${dgeEsc(c.title)}" placeholder="Title"
               oninput="window.dgeConfigSet('WHATS_NEW_CONFIG.comingSoon.${i}.title', this.value)"
               style="flex:1; min-width:0; font-size:13px; padding:6px; border:1px solid var(--card-border);
                      border-radius:6px; background:var(--bg-main); color:var(--text-primary);">
      </div>
      <textarea rows="2" placeholder="Description"
        oninput="window.dgeConfigSet('WHATS_NEW_CONFIG.comingSoon.${i}.description', this.value)"
        style="width:100%; box-sizing:border-box; font-size:12px; padding:6px; margin-bottom:5px;
               border:1px solid var(--card-border); border-radius:6px;
               background:var(--bg-main); color:var(--text-primary);">${dgeEsc(c.description)}</textarea>
      <div style="display:flex; gap:6px;">
        <button class="btn-sm" style="flex:none; ${i === 0 ? 'opacity:0.3;' : ''}" title="Move up (higher = shown first)"
                ${i === 0 ? 'disabled' : ''} onclick="window.dgeConfigMoveRow('WHATS_NEW_CONFIG.comingSoon', ${i}, -1)">▲</button>
        <button class="btn-sm" style="flex:none; ${i === d.WHATS_NEW_CONFIG.comingSoon.length - 1 ? 'opacity:0.3;' : ''}" title="Move down"
                ${i === d.WHATS_NEW_CONFIG.comingSoon.length - 1 ? 'disabled' : ''} onclick="window.dgeConfigMoveRow('WHATS_NEW_CONFIG.comingSoon', ${i}, 1)">▼</button>
        <button class="btn-sm" style="flex:none; color:var(--accent-red); margin-left:auto;"
                onclick="window.dgeConfigRemoveRow('WHATS_NEW_CONFIG.comingSoon', ${i})">🗑️ Remove</button>
      </div>
    </div>`).join('');

  // Word tools (the 🕉️ Genie row on a selection). The precedence this edits
  // is the MIDDLE one of three: shipped default < this global admin setting <
  // a reader's own per-device override (⚙️ → 🎛️). Asked for directly, 10 Sep
  // 2026 -- "those must be globally configurable ... either enabled or
  // disabled to all users; currently where do I do it, from which admin page
  // I'm not sure" -- and the honest answer was nowhere: appConfig.wordActions
  // was read by config.js and written by nothing.
  const registry = (window.WORD_ACTIONS || []);
  const wa = d.appConfig.wordActions || {};
  const POWERED_NOTE = {
    own: 'this project’s own offline data',
    gemini: 'a paid Gemini call — shown only to authorised accounts even when on',
    external: 'sends the selected text to a third-party service'
  };
  const wordToolRows = registry.length ? registry.map(a => {
    const on = (wa[a.id] !== undefined) ? !!wa[a.id] : !!a.enabled;
    const overridden = wa[a.id] !== undefined && !!wa[a.id] !== !!a.enabled;
    return `<label style="display:flex; align-items:flex-start; gap:8px; margin-bottom:10px; cursor:pointer;">
      <input type="checkbox" ${on ? 'checked' : ''}
             onchange="window.dgeConfigSet('appConfig.wordActions.${a.id}', this.checked)"
             style="width:20px; height:20px; flex:none; margin-top:1px;">
      <span style="font-size:13px; line-height:1.35;">
        <b>${dgeEsc(a.icon || '')} ${dgeEsc(a.label)}</b>
        ${overridden ? '<span style="font-size:10px; opacity:.7;"> · changed from default</span>' : ''}
        <br><span style="font-size:11px; color:var(--muted-text);">${dgeEsc(a.title || '')}
        — ${dgeEsc(POWERED_NOTE[a.powered] || a.powered || '')}</span>
      </span>
    </label>`;
  }).join('') : '<p class="hint">config.js did not load, so the tool list is unavailable.</p>';

  el.innerHTML =
    `<p class="hint" style="margin-top:0;">These settings are saved to
      <code>admin/config/config-overrides.json</code>, a plain data file — never to
      <code>config.js</code>. A mistake here can only change text, never break
      the app, and "Reset all" restores every default.</p>` +
    dgeSection('General', general, true) +
    dgeSection('Word tools (🕉️ Genie row)',
      `<p class="hint" style="margin-top:0;">Which tools appear when a reader selects a word,
        for <b>everyone</b>. A reader can still switch one off on their own device
        (⚙️ → 🎛️), but cannot switch on one you have turned off here.</p>` +
      wordToolRows) +
    dgeSection('Support / Sponsorship',
      dgeToggle('SPONSOR_CONFIG.enabled', d.SPONSOR_CONFIG.enabled, 'Show the Support section') +
      dgeField('SPONSOR_CONFIG.introText', d.SPONSOR_CONFIG.introText, 'Intro text', '', true) +
      dgeField('SPONSOR_CONFIG.contactForSponsorship', d.SPONSOR_CONFIG.contactForSponsorship, 'Sponsorship contact email', '') +
      `<div style="font-size:11px; font-weight:700; text-transform:uppercase; color:var(--muted-text); margin-top:10px;">Ways to sponsor</div>` +
      sponsorRows +
      `<button class="btn-sm" style="margin-top:10px;"
        onclick='window.dgeConfigAddRow("SPONSOR_CONFIG.sponsorCategories", ${JSON.stringify(JSON.stringify({icon:'🙏',label:'New category',description:'',enabled:true}))})'>➕ Add category</button>`) +
    dgeSection('Contributors',
      dgeToggle('CONTRIBUTORS_CONFIG.enabled', d.CONTRIBUTORS_CONFIG.enabled, 'Show the Contributors section') +
      contribRows +
      `<button class="btn-sm" style="margin-top:6px;"
        onclick='window.dgeConfigAddRow("CONTRIBUTORS_CONFIG.contributors", ${JSON.stringify(JSON.stringify({name:'',role:''}))})'>➕ Add contributor</button>`) +
    dgeSection('Key Sponsors',
      dgeToggle('KEY_SPONSORS_CONFIG.enabled', d.KEY_SPONSORS_CONFIG.enabled, 'Show the Key Sponsors section') +
      keySponsorRows +
      `<button class="btn-sm" style="margin-top:6px;"
        onclick='window.dgeConfigAddRow("KEY_SPONSORS_CONFIG.sponsors", ${JSON.stringify(JSON.stringify({name:'',contribution:''}))})'>➕ Add sponsor</button>`) +
    dgeSection("What's New / Coming Soon",
      dgeToggle('WHATS_NEW_CONFIG.enabled', d.WHATS_NEW_CONFIG.enabled, 'Show this section (via the About modal)') +
      `<div style="font-size:11px; font-weight:700; text-transform:uppercase; color:var(--muted-text); margin-top:10px;">What's New (shown newest-first by date)</div>` +
      whatsNewUpdateRows +
      `<button class="btn-sm" style="margin-top:6px; margin-bottom:16px;"
        onclick='window.dgeConfigAddRow("WHATS_NEW_CONFIG.updates", ${JSON.stringify(JSON.stringify({date:'',title:'',description:''}))})'>➕ Add update</button>` +
      `<div style="font-size:11px; font-weight:700; text-transform:uppercase; color:var(--muted-text); margin-top:10px;">Coming Soon (order below = display order)</div>` +
      whatsNewComingSoonRows +
      `<button class="btn-sm" style="margin-top:6px;"
        onclick='window.dgeConfigAddRow("WHATS_NEW_CONFIG.comingSoon", ${JSON.stringify(JSON.stringify({title:'',description:''}))})'>➕ Add coming-soon item</button>`);
}

window.openConfigEditor = function() {
  if (localStorage.getItem('is_superadmin') !== 'true') {
    if (typeof showToast === 'function') showToast('Super admin access required.');
    return;
  }
  dgeConfigDraft = dgeBuildDraft();
  dgeOpenSections = { 'General': true };
  if (typeof openModal === 'function') openModal('configEditorModal');
  dgeRenderConfigEditor();
};

window.dgeSaveConfigOverrides = async function() {
  if (!dgeConfigDraft) return;
  if (typeof dgeAdminUpsertFile !== 'function') {
    if (typeof showToast === 'function') showToast('Admin editor not loaded — cannot save.');
    return;
  }
  const btn = document.getElementById('configSaveBtn');
  if (btn) { btn.disabled = true; btn.textContent = 'Saving…'; }
  try {
    // dgeAdminUpsertFile expects base64. btoa() alone breaks on non-Latin1
    // characters, and these fields routinely hold Devanagari and emoji —
    // so encode to UTF-8 bytes first, then base64 those.
    const encode = function (obj) {
      const bytes = new TextEncoder().encode(JSON.stringify(obj, null, 2));
      let binary = '';
      bytes.forEach(b => { binary += String.fromCharCode(b); });
      return btoa(binary);
    };

    // Two files, because they are two different things: settings the site
    // merges over its defaults, and the What's New panel's own content. The
    // _readme is preserved so saving from the UI does not strip the notes
    // whoever edits the file by hand relies on.
    const settings = Object.assign({}, dgeConfigDraft);
    const whatsNew = settings.WHATS_NEW_CONFIG;
    delete settings.WHATS_NEW_CONFIG;

    // The reader's editorial blocks travel with it, not with the settings.
    const readerContent = {};
    DGE_READER_CONTENT_KEYS.forEach(function (k) {
      if (settings[k]) { readerContent[k] = settings[k]; delete settings[k]; }
    });

    await dgeAdminUpsertFile(DGE_CONFIG_OVERRIDES_PATH, encode(settings),
      dgeAdminBuildCommitMessage('Update site config'));

    if (whatsNew) {
      const existing = window.WHATS_NEW_CONFIG || {};
      const merged = Object.assign({}, whatsNew);
      if (existing._readme) merged._readme = existing._readme;
      await dgeAdminUpsertFile(DGE_WHATS_NEW_PATH, encode(merged),
        dgeAdminBuildCommitMessage("Update What's New"));
    }

    if (Object.keys(readerContent).length) {
      // Re-read rather than reconstruct: this file may hold keys the form does
      // not show, and its _readme, both of which a blind write would drop.
      let existing = {};
      try {
        const r = await fetch(window.dgeContentUrl('reader.json') + '?t=' + Date.now(),
                              { cache: 'no-store' });
        if (r.ok) existing = await r.json();
      } catch (e) { /* first write, or offline — fall through to a plain write */ }
      await dgeAdminUpsertFile(DGE_READER_CONTENT_PATH,
        encode(Object.assign({}, existing, readerContent)),
        dgeAdminBuildCommitMessage('Update reader content'));
    }
    if (typeof showToast === 'function') showToast('Saved. Reloading to apply…');
    setTimeout(() => location.reload(), 900);
  } catch (e) {
    if (typeof showToast === 'function') showToast('Save failed: ' + e.message);
    if (btn) { btn.disabled = false; btn.textContent = '💾 Save Changes'; }
  }
};

window.dgeResetConfigOverrides = async function() {
  if (!confirm('Reset ALL settings to their defaults?\n\nThis deletes the overrides file. Nothing in config.js is touched, so every default comes straight back.')) return;
  try {
    await dgeAdminDelete(DGE_CONFIG_OVERRIDES_PATH, 'file');
    if (typeof showToast === 'function') showToast('Reset. Reloading…');
    setTimeout(() => location.reload(), 900);
  } catch (e) {
    if (typeof showToast === 'function') showToast('Reset failed (the file may not exist yet): ' + e.message);
  }
};
