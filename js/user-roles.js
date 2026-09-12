// dge/js/user-roles.js — Superadmin "Manage Users" list (basic version).
// Client-side gate mirrors the is_superadmin localStorage check used
// everywhere else in this app; the REAL enforcement is Firestore
// security rules (dge/firebase/firestore.rules) — this UI physically
// cannot write a role change the rules reject, regardless of what runs
// here. No pagination yet (loads up to 200 most-recently-active users) —
// fine to start with, revisit once real volume makes that a problem.
window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['user-roles.js'] = 'v1.2 (10 Sep 2026: CSV sheet download + file upload, names as well as roles, header-driven columns; toolbar no longer collapses on a phone) \u00b7 v1.1 (custom roles, spreadsheet round-trip) \u00b7 v1.0 (List + search + change role)';

function dgeRolesEsc(s) {
  const d = document.createElement('div');
  d.textContent = s == null ? '' : String(s);
  return d.innerHTML;
}

window.openUserRolesModal = async function() {
  if (localStorage.getItem('is_superadmin') !== 'true') {
    if (typeof showToast === 'function') showToast('Super admin access required.');
    return;
  }
  if (!window.AUTH_CONFIG || !window.AUTH_CONFIG.enabled) {
    if (typeof showToast === 'function') showToast('Accounts are not set up yet on this deployment.');
    return;
  }
  // The SDK is loaded on demand (see user-auth.js). Normally it is
  // already there by the time an admin opens this screen, but awaiting
  // it keeps this page working if it is ever reached before startup
  // finished.
  if (typeof window.dgeEnsureFirebaseSdk === 'function') await window.dgeEnsureFirebaseSdk();
  if (typeof openModal === 'function') openModal('userRolesModal');
  await dgeRenderUserRolesList();
};

async function dgeRenderUserRolesList(filterText) {
  const body = document.getElementById('userRolesBody');
  if (!body) return;
  body.innerHTML = `<p style="font-size:12px; color:var(--muted-text);">Loading users…</p>`;

  let db;
  try {
    db = firebase.firestore();
  } catch (e) {
    body.innerHTML = `<p style="font-size:12px; color:var(--accent-red);">Firebase isn't initialized.</p>`;
    return;
  }

  try {
    const snap = await db.collection('users').orderBy('lastLoginAt', 'desc').limit(200).get();
    // Every role this deployment knows -- the fixed tiers in AUTH_CONFIG AND
    // any custom role created in admin/access-control.html. Until 10 Sep 2026
    // this read AUTH_CONFIG alone, so a role someone had just created to gate
    // a section with could not actually be granted to anybody from here: it
    // simply was not in the dropdown.
    if (typeof window.dgeLoadRoleAccessConfig === 'function') {
      try { await window.dgeLoadRoleAccessConfig(); } catch (e) { /* fall through to the fixed list */ }
    }
    const roles = (typeof window.dgeAllRoleIds === 'function' ? window.dgeAllRoleIds() : null)
      || (window.AUTH_CONFIG && window.AUTH_CONFIG.roles) || ['basic'];
    dgeUserRolesKnown = roles;
    const filter = (filterText || '').trim().toLowerCase();

    const rows = [];
    snap.forEach(doc => {
      const u = doc.data();
      const haystack = `${u.displayName || ''} ${u.email || ''} ${u.phoneNumber || ''}`.toLowerCase();
      if (filter && !haystack.includes(filter)) return;
      rows.push(Object.assign({ id: doc.id }, u));
    });

    if (!rows.length) {
      body.innerHTML = `<p style="font-size:12px; color:var(--muted-text);">${filter ? 'No users match that search.' : 'No users yet.'}</p>`;
      return;
    }

    // 7 Sep 2026: the verified-email list, as CSV — the "export" half of the
    // lead's ask. Only rows whose email the provider verified (emailVerified
    // true, or a legacy Google profile whose email predates the flag).
    const exportable = rows.filter(u => u.email && (u.emailVerified === true || u.emailVerified === undefined));
    // The count sits on its own full-width line and the buttons wrap under
    // it. Before this it shared one nowrap flex row with three buttons, and
    // on a phone the text was squeezed into a ~60px column reading one word
    // per line ("2 / shown / · 2 / with / a / verified / email") — reported
    // 10 Sep 2026 with a screenshot.
    body.innerHTML = `<div style="display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin:0 0 8px;">
        <span style="flex:1 1 100%; font-size:11px; color:var(--muted-text);">${rows.length} shown · ${exportable.length} with a verified email</span>
        <button class="btn-sm" style="font-size:11px;" onclick="window.dgeExportUserSheet()" title="Everyone shown, as a CSV that opens straight in Excel — edit the name and role columns and upload it back">⬇ Download sheet</button>
        <button class="btn-sm" style="font-size:11px;" onclick="window.dgeOpenBulkRolePaste()" title="Upload the edited sheet, or paste rows from it">⬆ Upload / paste</button>
      </div>` + rows.map(u => `
      <div style="border-top:1px dashed var(--card-border); padding:10px 0; display:flex; align-items:center; gap:8px;">
        <div style="flex:1; min-width:0;">
          <div style="font-size:13px; font-weight:700; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${dgeRolesEsc(u.displayName || u.email || u.phoneNumber || u.id)}</div>
          <div style="font-size:11px; color:var(--muted-text); overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${dgeRolesEsc(u.email || u.phoneNumber || '')}</div>
        </div>
        <select style="flex:none; font-size:12px; padding:6px; border-radius:6px; border:1px solid var(--card-border); background:var(--bg-main); color:var(--text-primary);"
                onchange="window.dgeChangeUserRole('${u.id}', this.value)">
          ${roles.map(r => `<option value="${dgeRolesEsc(r)}" ${r === u.role ? 'selected' : ''}>${dgeRolesEsc(r)}</option>`).join('')}
        </select>
      </div>`).join('');
  } catch (e) {
    console.error('[UserRoles] Failed to load users:', e);
    // "Missing or insufficient permissions" here almost always means one
    // thing: this person holds the 🔑 superadmin PASSKEY (which is why the
    // screen opened at all) but their Firestore ACCOUNT role is still
    // 'basic'. The rules enforce the account role, so the read is refused.
    // A bare error string left the lead stuck with no way forward; say what
    // is actually wrong and how to fix it once.
    if (typeof window.dgeIsPermissionError === 'function' && window.dgeIsPermissionError(e)) {
      body.innerHTML = window.dgeSuperadminBootstrapHtml({
        uid: window.dgeCurrentUser && window.dgeCurrentUser.uid,
        email: window.dgeCurrentUser && window.dgeCurrentUser.email
      });
      return;
    }
    body.innerHTML = `<p style="font-size:12px; color:var(--accent-red);">Couldn't load users: ${dgeRolesEsc(e.message || e)}</p>`;
  }
}

//: Filled by the list render; the paste parser validates against it so a
//: typo becomes a reported row rather than a role nobody can ever match.
let dgeUserRolesKnown = [];
/**
 * Split one spreadsheet line into cells. Tabs (a spreadsheet copy) or
 * commas (a CSV file), with quoted cells honoured so a name containing a
 * comma survives the round trip.
 */
function dgeSplitRow(line) {
  if (line.indexOf('\t') >= 0) return line.split('\t').map(c => c.trim());
  const cells = [];
  let cur = '', inQ = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (inQ) {
      if (ch === '"' && line[i + 1] === '"') { cur += '"'; i++; }
      else if (ch === '"') inQ = false;
      else cur += ch;
    } else if (ch === '"') inQ = true;
    else if (ch === ',') { cells.push(cur.trim()); cur = ''; }
    else cur += ch;
  }
  cells.push(cur.trim());
  return cells;
}

/**
 * Parse a block pasted or uploaded from a spreadsheet into
 * {email, role, name} rows.
 *
 * Pure and exported so it can be tested without Firebase. Two modes, and
 * which one applies is decided by the first line:
 *
 *   HEADER MODE   the first line names its columns (it contains "email"
 *                 and at least one of "role"/"name"). Columns are then read
 *                 BY NAME, in any order, and a displayName column can be
 *                 applied as well as a role. This is what the Download
 *                 sheet button produces, so the ordinary edit-and-upload
 *                 round trip always lands here.
 *
 *   LOOSE MODE    no recognisable header — a list someone typed. The email
 *                 is found by shape and the role is the RIGHTMOST cell that
 *                 names a role we know (taking the last cell outright would
 *                 pick up a trailing date column). Names are NOT applied in
 *                 this mode: guessing which free-text cell is a person's
 *                 name from an unlabelled list is exactly the kind of
 *                 confident wrong answer that overwrites real data.
 */
window.dgeParseRolePaste = function(text, knownRoles) {
  const known = (knownRoles || []).map(r => String(r).toLowerCase());
  const lines = String(text || '').split(/\r?\n/);
  const firstIdx = lines.findIndex(l => l.trim());
  if (firstIdx < 0) return [];

  const head = dgeSplitRow(lines[firstIdx]).map(c => c.toLowerCase().replace(/[^a-z]/g, ''));
  const col = { email: head.indexOf('email'), role: head.indexOf('role') };
  col.name = head.indexOf('displayname') >= 0 ? head.indexOf('displayname') : head.indexOf('name');
  const headerMode = col.email >= 0 && (col.role >= 0 || col.name >= 0);

  const rows = [];
  lines.forEach((line, i) => {
    if (!line.trim()) return;
    if (headerMode && i === firstIdx) return;                 // the header itself
    const cells = dgeSplitRow(line);
    let email = '', role = null, name = null;
    if (headerMode) {
      email = (cells[col.email] || '').toLowerCase();
      const r = col.role >= 0 ? (cells[col.role] || '').toLowerCase() : '';
      role = known.indexOf(r) >= 0 ? r : (r ? null : undefined);
      if (col.name >= 0) name = cells[col.name] || '';
    } else {
      email = (cells.find(c => c.indexOf('@') > 0) || '').toLowerCase();
      for (let k = cells.length - 1; k >= 0; k--) {
        if (known.indexOf(cells[k].toLowerCase()) >= 0) { role = cells[k].toLowerCase(); break; }
      }
      if (!email && role === null) return;                    // blank or a stray header
    }
    if (!email && role == null && name == null) return;
    rows.push({ line: i + 1, email: email, role: role === undefined ? null : role, name: name, raw: line.trim() });
  });
  return rows;
};

window.dgeExportUserSheet = async function() {
  try {
    const db = firebase.firestore();
    const snap = await db.collection('users').orderBy('lastLoginAt', 'desc').limit(1000).get();
    // CSV with a UTF-8 BOM rather than TSV: Excel double-click-opens this
    // straight into columns AND reads the BOM as "this is UTF-8", without
    // which a Devanagari or Kannada displayName arrives as mojibake and
    // gets saved back that way. The header row is what makes the upload
    // side read columns by NAME, so edit cells freely but keep it.
    const cell = (v) => '"' + String(v == null ? '' : v).replace(/"/g, '""') + '"';
    const lines = ['email,displayName,role,phone,lastLogin'];
    snap.forEach(doc => {
      const u = doc.data();
      const last = u.lastLoginAt && u.lastLoginAt.toDate ? u.lastLoginAt.toDate().toISOString().slice(0, 10) : '';
      lines.push([u.email || '', u.displayName || '', u.role || '', u.phoneNumber || '', last].map(cell).join(','));
    });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob(['\ufeff' + lines.join('\r\n') + '\r\n'], { type: 'text/csv;charset=utf-8' }));
    a.download = 'dge-users-' + new Date().toISOString().slice(0, 10) + '.csv';
    document.body.appendChild(a); a.click(); a.remove();
    if (typeof showToast === 'function') showToast((lines.length - 1) + ' user(s) exported. Edit the name and role columns, then upload it back.');
  } catch (e) {
    console.error('[UserRoles] Sheet export failed:', e);
    if (typeof showToast === 'function') showToast('Export failed: ' + (e.message || e));
  }
};

window.dgeOpenBulkRolePaste = function() {
  const body = document.getElementById('userRolesBody');
  if (!body) return;
  const known = dgeUserRolesKnown.length ? dgeUserRolesKnown
    : ((window.AUTH_CONFIG && window.AUTH_CONFIG.roles) || ['basic']);
  body.innerHTML = `
    <div style="font-size:12px; color:var(--muted-text); margin-bottom:8px;">
      Upload the sheet you downloaded and edited, or paste rows from it. Keep the
      <b>header row</b> — it is what lets the columns be read by name, so a
      <code>displayName</code> as well as a <code>role</code> can be applied, in any
      column order. Without a header, only email and role are read.
      Nothing is written until you press Apply.
    </div>
    <div style="font-size:11px; color:var(--muted-text); margin-bottom:8px;">
      Roles you can use: ${known.map(r => `<code>${dgeRolesEsc(r)}</code>`).join(' ')}
    </div>
    <label class="btn-sm" style="display:inline-block; cursor:pointer; margin-bottom:8px;">
      ⬆ Choose a .csv / .tsv file
      <input type="file" id="dgeBulkRoleFile" accept=".csv,.tsv,.txt,text/csv,text/plain"
             style="display:none;" onchange="window.dgeLoadBulkRoleFile(this)">
    </label>
    <span id="dgeBulkRoleFileName" style="font-size:11px; color:var(--muted-text); margin-left:6px;"></span>
    <textarea id="dgeBulkRoleText" rows="9" placeholder="email,displayName,role&#10;someone@example.com,Ravi,subscriber"
      style="width:100%; box-sizing:border-box; font:12px/1.4 ui-monospace,monospace; padding:8px;
             border:1px solid var(--card-border); border-radius:6px;
             background:var(--bg-main); color:var(--text-primary);"></textarea>
    <div style="display:flex; gap:8px; margin-top:8px;">
      <button class="btn-sm" onclick="window.dgeApplyBulkRolePaste()">✔ Apply</button>
      <button class="btn-sm" onclick="window.dgeRenderUserRolesListPublic()">Cancel</button>
    </div>
    <div id="dgeBulkRoleResult" style="margin-top:10px; font-size:12px;"></div>`;
};

/* The file goes into the same textarea the paste path uses, so there is one
   parser, one preview and one Apply — and the admin can still eyeball or
   correct what the file contained before anything is written. */
window.dgeLoadBulkRoleFile = function(input) {
  const file = input && input.files && input.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = function () {
    // Strip a UTF-8 BOM: Excel writes one back out, and left in place it
    // would glue itself to the first header cell so "email" never matches.
    const text = String(reader.result || '').replace(/^\ufeff/, '');
    const ta = document.getElementById('dgeBulkRoleText');
    if (ta) ta.value = text;
    const label = document.getElementById('dgeBulkRoleFileName');
    if (label) label.textContent = file.name + ' — ' + text.split(/\r?\n/).filter(l => l.trim()).length + ' line(s) loaded. Check, then Apply.';
  };
  reader.onerror = function () {
    const label = document.getElementById('dgeBulkRoleFileName');
    if (label) label.textContent = 'Could not read that file.';
  };
  reader.readAsText(file, 'utf-8');
};

window.dgeApplyBulkRolePaste = async function() {
  const ta = document.getElementById('dgeBulkRoleText');
  const out = document.getElementById('dgeBulkRoleResult');
  if (!ta || !out) return;
  const known = dgeUserRolesKnown.length ? dgeUserRolesKnown
    : ((window.AUTH_CONFIG && window.AUTH_CONFIG.roles) || ['basic']);
  const rows = window.dgeParseRolePaste(ta.value, known);
  if (!rows.length) { out.innerHTML = '<span style="color:var(--accent-red);">Nothing to apply.</span>'; return; }

  // Resolve emails to uids from the LIVE collection rather than the last
  // render: the sheet may name someone who signed in since it was downloaded.
  let byEmail = {}, current = {};
  try {
    const db = firebase.firestore();
    const snap = await db.collection('users').orderBy('lastLoginAt', 'desc').limit(1000).get();
    snap.forEach(doc => {
      const d = doc.data();
      const e = (d.email || '').toLowerCase();
      if (e) { byEmail[e] = doc.id; current[e] = d; }
    });
  } catch (e) {
    out.innerHTML = '<span style="color:var(--accent-red);">Could not read the user list: ' + dgeRolesEsc(e.message || e) + '</span>';
    return;
  }

  const me = (window.dgeCurrentUser && window.dgeCurrentUser.uid) || null;
  const results = [];
  let applied = 0, unchanged = 0;
  for (const r of rows) {
    if (!r.email) { results.push([r.line, r.raw, 'no email in this line']); continue; }
    const uid = byEmail[r.email];
    if (!uid) { results.push([r.line, r.email, 'no account with that email has signed in yet']); continue; }
    const now = current[r.email] || {};
    const patch = {};
    if (r.role && r.role !== now.role) patch.role = r.role;
    if (r.name != null && r.name !== '' && r.name !== now.displayName) patch.displayName = r.name;
    if (!Object.keys(patch).length) { unchanged++; continue; }
    // The rules forbid changing your OWN role, so say so rather than
    // letting Firestore reject the whole row with a bare permission error.
    if (patch.role && uid === me) {
      results.push([r.line, r.email, 'that is your own account — nobody may change their own role']);
      continue;
    }
    try {
      await firebase.firestore().collection('users').doc(uid).update(patch);
      applied++;
      results.push([r.line, r.email, Object.keys(patch).map(k => k + ' → ' + patch[k]).join(', '), true]);
    } catch (e) {
      results.push([r.line, r.email, 'refused: ' + (e.message || e)]);
    }
  }
  out.innerHTML =
    `<div style="font-weight:700; margin-bottom:6px;">${applied} changed, ${unchanged} already up to date, ` +
    `${rows.length - applied - unchanged} not applied.</div>` +
    results.map(x => `<div style="padding:2px 0; color:${x[3] ? 'inherit' : 'var(--accent-red)'};">
        <span style="opacity:.6;">line ${x[0]}</span> ${dgeRolesEsc(x[1])} — ${dgeRolesEsc(x[2])}</div>`).join('') +
    `<button class="btn-sm" style="margin-top:10px;" onclick="window.dgeRenderUserRolesListPublic()">← Back to the list</button>`;
};

window.dgeRenderUserRolesListPublic = function() { dgeRenderUserRolesList(); };

window.dgeExportVerifiedEmails = async function() {
  try {
    const db = firebase.firestore();
    const snap = await db.collection('users').orderBy('lastLoginAt', 'desc').limit(1000).get();
    const lines = ['email,displayName,role,phoneNumber,createdAt'];
    snap.forEach(doc => {
      const u = doc.data();
      if (!u.email || !(u.emailVerified === true || u.emailVerified === undefined)) return;
      const created = u.createdAt && u.createdAt.toDate ? u.createdAt.toDate().toISOString() : '';
      lines.push([u.email, u.displayName || '', u.role || '', u.phoneNumber || '', created].map(v => '"' + String(v).replace(/"/g, '""') + '"').join(','));
    });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([lines.join('\n') + '\n'], { type: 'text/csv' }));
    a.download = 'dge-verified-emails-' + new Date().toISOString().slice(0, 10) + '.csv';
    document.body.appendChild(a); a.click(); a.remove();
    if (typeof showToast === 'function') showToast((lines.length - 1) + ' verified email(s) exported.');
  } catch (e) {
    console.error('[UserRoles] Export failed:', e);
    if (typeof showToast === 'function') showToast('Export failed: ' + (e.message || e));
  }
};

window.dgeSearchUserRoles = function(text) {
  dgeRenderUserRolesList(text);
};

window.dgeChangeUserRole = async function(uid, newRole) {
  try {
    const db = firebase.firestore();
    await db.collection('users').doc(uid).update({ role: newRole });
    if (typeof showToast === 'function') showToast('Role updated.');
  } catch (e) {
    console.error('[UserRoles] Role change failed:', e);
    if (typeof window.dgeIsPermissionError === 'function' && window.dgeIsPermissionError(e)) {
      const body = document.getElementById('userRolesBody');
      if (body) {
        body.innerHTML = window.dgeSuperadminBootstrapHtml({
          uid: window.dgeCurrentUser && window.dgeCurrentUser.uid,
          email: window.dgeCurrentUser && window.dgeCurrentUser.email
        });
        return;
      }
    }
    if (typeof showToast === 'function') showToast('Could not change role: ' + (e.message || e));
    await dgeRenderUserRolesList(); // re-render so the dropdown reflects what's actually stored, not the rejected attempt
  }
};
