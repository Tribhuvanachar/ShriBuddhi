// js/admin-editor.js
// Maps to F-019: Admin GitHub File Manager
//
// Lets the admin (and only the admin) browse, upload, edit, rename, move,
// and delete files anywhere in this repo, directly from the live site —
// using their OWN GitHub Personal Access Token (same BYOK pattern as the
// AI provider keys), gated behind a secret URL flag. Nobody else can see
// or use this: the gate only reveals the UI, and without a real PAT
// pasted into THIS specific browser, none of the write calls succeed.
//
// SECURITY NOTE FOR THE ADMIN: use a fine-grained PAT scoped to ONLY this
// repo, with "Contents: Read and write" permission — not a classic
// all-access token — and set an expiration on it. See images/README.md
// or the in-app note in Settings for details.

window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['admin-editor.js'] = 'v1.21 (Cut/Copy/Paste: select several files/folders, then Cut or Copy them — a clipboard bar stays visible while you browse anywhere in your allowed tree (survives closing the modal and even a page reload) — then Paste Here drops or duplicates them all in one commit. Copy keeps the source; Cut removes it and is consumed on paste. Replaces the earlier one-shot "Move Selected".)';

const GH_API = 'https://api.github.com';
let dgeAdminCurrentPath = '';
let dgeAdminDragSourcePath = null;
let dgeAdminSortMode = 'name'; // 'name' | 'modified' — toggled via dgeAdminToggleSort()
let dgeAdminSelectedItems = new Map(); // path -> type, cleared on every navigate (selection is per-folder)
// Cut/Copy clipboard — deliberately NOT cleared on navigate (that's the
// whole point: browse elsewhere to find the destination) and persisted to
// localStorage so it survives closing the modal or reloading the page.
// { mode: 'cut'|'copy', items: [{path,type}] } | null
let dgeAdminClipboard = null;
try {
  const dgeAdminSavedClipboard = localStorage.getItem('admin_clipboard');
  if (dgeAdminSavedClipboard) dgeAdminClipboard = JSON.parse(dgeAdminSavedClipboard);
} catch (e) { dgeAdminClipboard = null; }

// ---------------------------------------------------------------
// Superadmin gate
// ---------------------------------------------------------------
function dgeCheckSuperadminGate() {
  try {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('superadmin');
    if (code && window.ADMIN_ACCESS_LEVELS && window.ADMIN_ACCESS_LEVELS[code]) {
      localStorage.setItem('is_superadmin', 'true');
      localStorage.setItem('admin_root_path', window.ADMIN_ACCESS_LEVELS[code].rootPath);
    }
  } catch (e) { /* ignore */ }
  return localStorage.getItem('is_superadmin') === 'true';
}
window.dgeCheckSuperadminGate = dgeCheckSuperadminGate;

// UI-discoverable alternative to manually typing ?superadmin=CODE into
// the URL — same validation, same effect, just reachable by tapping 🔑
// instead of editing the address bar.
window.dgeShowSuperAdminAccessPrompt = function() {
  const code = prompt('Enter super admin code:');
  if (!code) return;
  if (window.ADMIN_ACCESS_LEVELS && window.ADMIN_ACCESS_LEVELS[code]) {
    localStorage.setItem('is_superadmin', 'true');
    localStorage.setItem('admin_root_path', window.ADMIN_ACCESS_LEVELS[code].rootPath);
    if (typeof showToast === 'function') showToast('Super admin access granted.');
    location.reload();
  } else {
    if (typeof showToast === 'function') showToast('Incorrect code.');
  }
};

// The path this device's access code is bound to — navigation can never
// go above this, regardless of what's clicked or dragged. Defaults to
// 'dge' (the narrowest, safest scope) if nothing was ever granted.
//
// Deliberately NOT `localStorage.getItem(...) || 'dge'`: a full-repo grant
// stores '' (empty string, meaning "no restriction"), and '' is falsy —
// the || would have silently replaced it with 'dge' again, undoing the
// grant. Only an actually-absent key (never granted at all) falls back.
function dgeAdminGetRootPath() {
  const stored = localStorage.getItem('admin_root_path');
  return stored !== null ? stored : 'dge';
}

function dgeAdminGetName() {
  return localStorage.getItem('admin_editor_name') || 'Admin';
}

// Appends who made a change and when to every commit message, so GitHub's
// own commit history becomes scannable at a glance (which edit, by whom,
// at what time) without clicking into each commit individually — and
// makes reverting to a specific version straightforward.
function dgeAdminBuildCommitMessage(action) {
  const name = dgeAdminGetName();
  const timestamp = new Date().toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' });
  return `${action} — by ${name} at ${timestamp}`;
}

// Split out from the DOMContentLoaded listener below (8 Sep 2026) so a real
// Firebase sign-in can reveal these tools too, not only the ?superadmin=CODE
// passkey — see dgeIsAdmin()'s bridge in user-auth.js, which calls this
// again once a signed-in user's own role resolves to admin/superadmin. Safe
// to call more than once: every branch just (re)shows elements that are
// already hidden by default in the markup.
function dgeRevealAdminTools() {
  if (!dgeCheckSuperadminGate()) return;
  const btn = document.getElementById('adminToolsBtn');
  if (btn) btn.style.display = 'flex';
  ['adminFilesItem', 'adminConfigItem', 'adminConvertItem', 'adminLibraryManagerItem', 'adminKoshaManagerItem', 'adminAshtadhyayiManagerItem', 'adminHolyPlacesManagerItem', 'adminAudioManagerItem', 'adminDasaCaptureItem', 'adminContentProvenanceItem', 'adminRepoMapItem', 'adminOcrReviewItem'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = 'flex';
  });
  // Manage Users / Access Control only make sense once accounts are
  // actually set up — showing them before then would just be menu items
  // that always toast "not set up yet" (see openUserRolesModal in
  // user-roles.js and admin/access-control.html's own gate).
  if (window.AUTH_CONFIG && window.AUTH_CONFIG.enabled) {
    ['adminUserRolesItem', 'adminAccessControlItem', 'adminViewAsItem'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = 'flex';
    });
  }
}
window.dgeRevealAdminTools = dgeRevealAdminTools;

// The 🔑 Access menu is hidden from visitors in the markup (see index.html).
// It comes back for an admin device — EITHER tier, deliberately not gated on
// dgeRevealAdminTools's superadmin check, because "Log out (clear access)"
// lives in that menu and an admin-passkey holder must be able to reach it to
// hand the device back. ?superadmin=CODE is still handled by
// dgeCheckSuperadminGate below, so a first entry needs no visible button.
function dgeRevealAccessMenu() {
  let admin = false;
  try {
    admin = localStorage.getItem('acharyaAuthorized') === 'true' ||
            localStorage.getItem('is_superadmin') === 'true';
  } catch (e) { /* private mode: menu stays hidden */ }
  const btn = document.getElementById('accessKeyBtn');
  if (btn) btn.style.display = admin ? 'flex' : 'none';
}
window.dgeRevealAccessMenu = dgeRevealAccessMenu;
document.addEventListener('DOMContentLoaded', dgeRevealAccessMenu);

document.addEventListener('DOMContentLoaded', dgeRevealAdminTools);

// ---------------------------------------------------------------
// GitHub API helpers
// ---------------------------------------------------------------
function dgeGithubToken() {
  return localStorage.getItem('github_admin_pat') || '';
}

function dgeGithubHeaders() {
  const headers = { 'Accept': 'application/vnd.github+json' };
  const token = dgeGithubToken();
  if (token) headers['Authorization'] = `token ${token}`;
  return headers;
}

function dgeUtf8ToBase64(str) {
  return btoa(unescape(encodeURIComponent(str)));
}
function dgeBase64ToUtf8(b64) {
  return decodeURIComponent(escape(atob((b64 || '').replace(/\n/g, ''))));
}

async function dgeGithubRequest(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try { const j = await res.json(); if (j.message) msg += ` — ${j.message}`; } catch (e) { /* ignore */ }
    if (res.status === 401 || res.status === 403) msg += ' (check your GitHub token in Settings)';
    if (msg.includes('does not match')) msg += ' — this file was likely deleted, moved, or edited elsewhere since it was opened here. Close and reopen it, then try again.';
    throw new Error(msg);
  }
  return res.status === 204 ? null : res.json();
}

function dgeGithubListDir(dirPath) {
  const { owner, repo, branch } = GITHUB_REPO_CONFIG;
  const url = `${GH_API}/repos/${owner}/${repo}/contents/${dirPath}?ref=${branch}&_=${Date.now()}`;
  return dgeGithubRequest(url, { headers: dgeGithubHeaders(), cache: 'no-store' });
}

function dgeGithubGetFile(filePath) {
  const { owner, repo, branch } = GITHUB_REPO_CONFIG;
  const url = `${GH_API}/repos/${owner}/${repo}/contents/${filePath}?ref=${branch}&_=${Date.now()}`;
  return dgeGithubRequest(url, { headers: dgeGithubHeaders(), cache: 'no-store' });
}

function dgeGithubPutFile(filePath, contentBase64, message, sha) {
  const { owner, repo, branch } = GITHUB_REPO_CONFIG;
  const url = `${GH_API}/repos/${owner}/${repo}/contents/${filePath}`;
  const body = { message, content: contentBase64, branch };
  if (sha) body.sha = sha;
  return dgeGithubRequest(url, {
    method: 'PUT',
    headers: { ...dgeGithubHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
}

function dgeGithubDeleteFile(filePath, message, sha) {
  const { owner, repo, branch } = GITHUB_REPO_CONFIG;
  const url = `${GH_API}/repos/${owner}/${repo}/contents/${filePath}`;
  return dgeGithubRequest(url, {
    method: 'DELETE',
    headers: { ...dgeGithubHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, sha, branch })
  });
}

function dgeGithubGetBranchHead() {
  const { owner, repo, branch } = GITHUB_REPO_CONFIG;
  const url = `${GH_API}/repos/${owner}/${repo}/branches/${branch}?_=${Date.now()}`;
  return dgeGithubRequest(url, { headers: dgeGithubHeaders(), cache: 'no-store' });
}

function dgeGithubCreateBlob(base64Content) {
  const { owner, repo } = GITHUB_REPO_CONFIG;
  const url = `${GH_API}/repos/${owner}/${repo}/git/blobs`;
  return dgeGithubRequest(url, {
    method: 'POST',
    headers: { ...dgeGithubHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: base64Content, encoding: 'base64' })
  });
}

function dgeGithubCreateTree(baseTreeSha, treeEntries) {
  const { owner, repo } = GITHUB_REPO_CONFIG;
  const url = `${GH_API}/repos/${owner}/${repo}/git/trees`;
  return dgeGithubRequest(url, {
    method: 'POST',
    headers: { ...dgeGithubHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ base_tree: baseTreeSha, tree: treeEntries })
  });
}

function dgeGithubCreateCommit(message, treeSha, parentSha) {
  const { owner, repo } = GITHUB_REPO_CONFIG;
  const url = `${GH_API}/repos/${owner}/${repo}/git/commits`;
  return dgeGithubRequest(url, {
    method: 'POST',
    headers: { ...dgeGithubHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, tree: treeSha, parents: [parentSha] })
  });
}

function dgeGithubUpdateRef(newCommitSha) {
  const { owner, repo, branch } = GITHUB_REPO_CONFIG;
  const url = `${GH_API}/repos/${owner}/${repo}/git/refs/heads/${branch}`;
  return dgeGithubRequest(url, {
    method: 'PATCH',
    headers: { ...dgeGithubHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ sha: newCommitSha })
  });
}

// GitHub's directory-listing endpoint doesn't include a modified date per
// file — the only way to get one is a per-file commit-history lookup
// (?per_page=1 for just the most recent). Deliberately NOT called on every
// navigation — only when "Sort: Modified" is active — since it's one extra
// API call per FILE in the current folder.
function dgeGithubGetFileLastModified(filePath) {
  const { owner, repo, branch } = GITHUB_REPO_CONFIG;
  const url = `${GH_API}/repos/${owner}/${repo}/commits?path=${encodeURIComponent(filePath)}&sha=${branch}&per_page=1&_=${Date.now()}`;
  return dgeGithubRequest(url, { headers: dgeGithubHeaders(), cache: 'no-store' });
}

function dgeFormatShortDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }) + ' ' + d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
}

window.dgeAdminToggleSort = function() {
  dgeAdminSortMode = dgeAdminSortMode === 'name' ? 'modified' : 'name';
  const btn = document.getElementById('adminSortBtn');
  if (btn) btn.textContent = dgeAdminSortMode === 'modified' ? '🕒 Sort: Modified' : '🔤 Sort: Name';
  dgeAdminNavigate(dgeAdminCurrentPath);
};

window.dgeAdminToggleMoreMenu = function() {
  const el = document.getElementById('adminMoreMenu');
  if (!el) return;
  el.style.display = (el.style.display === 'flex') ? 'none' : 'flex';
};

function dgeEscapeHtmlSafe(s) {
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

window.dgeAdminToggleRecentActivity = function() {
  const panel = document.getElementById('adminActivityPanel');
  if (!panel) return;
  const willShow = panel.style.display !== 'block';
  panel.style.display = willShow ? 'block' : 'none';
  if (willShow) dgeAdminRenderRecentActivity();
};

// Shows the last 5 commits on the branch, each with its own Undo button.
// Undo creates a NEW commit that reverses just THAT commit's changes —
// nothing is destroyed or force-pushed, the full history (including the
// undone commit itself) stays intact and visible on GitHub. See
// dgeAdminUndoCommit below for how it targets an arbitrary commit
// (not just the most recent one) safely.
async function dgeAdminRenderRecentActivity() {
  const panel = document.getElementById('adminActivityPanel');
  if (!panel) return;
  panel.innerHTML = '<div class="note-preview-box" style="margin:0;">Loading recent activity…</div>';

  try {
    const { owner, repo, branch } = GITHUB_REPO_CONFIG;
    const url = `${GH_API}/repos/${owner}/${repo}/commits?sha=${branch}&per_page=5&_=${Date.now()}`;
    const commits = await dgeGithubRequest(url, { headers: dgeGithubHeaders(), cache: 'no-store' });
    if (!commits || !commits.length) {
      panel.innerHTML = '<div class="note-preview-box" style="margin:0;">No commit history found.</div>';
      return;
    }

    panel.innerHTML = `<div style="font-size:11px; font-weight:700; color:var(--muted-text); text-transform:uppercase; margin-bottom:6px;">Recent Activity</div>` +
      commits.map((c, i) => {
        const msg = dgeEscapeHtmlSafe((c.commit.message || '').split('\n')[0]);
        const date = new Date(c.commit.author.date).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' });
        return `<div style="padding:8px 0; ${i < commits.length - 1 ? 'border-bottom:1px solid var(--card-border);' : ''}">
          <div style="font-size:12px; font-weight:600;">${msg}</div>
          <div style="font-size:10px; color:var(--muted-text); margin-top:2px;">${date} · ${c.sha.slice(0, 7)}</div>
          <button class="btn-sm" style="color:var(--accent-red); margin-top:4px;" onclick="window.dgeAdminUndoCommit('${c.sha}')">↩️ Undo This</button>
        </div>`;
      }).join('');
  } catch (e) {
    panel.innerHTML = `<div class="note-preview-box" style="margin:0; color:var(--accent-red);">Couldn't load activity: ${e.message}</div>`;
  }
}

// Fetches the full recursive tree at an arbitrary commit-ish sha (a
// commit sha works directly with the trees API, same as a tree sha) and
// returns it as a path -> blob-sha Map, blobs only (submodules/symlinks
// excluded — not something this admin tool creates). Truncation is
// surfaced rather than silently producing a partial, wrong-looking diff.
async function dgeGithubGetBlobMapAt(shaish) {
  const { owner, repo } = GITHUB_REPO_CONFIG;
  const url = `${GH_API}/repos/${owner}/${repo}/git/trees/${shaish}?recursive=1&_=${Date.now()}`;
  const data = await dgeGithubRequest(url, { headers: dgeGithubHeaders(), cache: 'no-store' });
  if (data.truncated) {
    console.warn(`[Undo] GitHub truncated the tree listing at ${shaish} — this repo may now be too large for a full-tree revert to see every changed file.`);
  }
  const map = new Map();
  (data.tree || []).forEach(entry => {
    if (entry.type === 'blob') map.set(entry.path, entry.sha);
  });
  return map;
}

// Reverts exactly ONE commit's changes, regardless of where it sits in
// history — unlike a plain "reset to parent" (which only works when the
// commit being undone IS the current tip), this diffs commitSha against
// its own parent to find what THAT commit actually changed, then applies
// the inverse of just those paths on top of the CURRENT head tree. Any
// unrelated commits that happened before or after are left completely
// alone, which is the whole point: admin-panel commits are frequently
// unrelated edits to different files, and forcing a full linear undo
// chain through all of them to reach one older change was needless and
// risked reverting things nobody wanted touched.
// Per-path conflict check: if some LATER commit already changed a path
// that this revert would also touch, reverting it blindly could silently
// clobber that later, unrelated edit. Detected by comparing the current
// head's blob sha for that path against what commitSha itself set it
// to — a mismatch means someone touched it since, so that one path is
// skipped (reported to the admin) rather than guessed at, the same way
// `git revert` itself would surface a conflict instead of resolving it.
window.dgeAdminUndoCommit = async function(commitSha) {
  if (!confirm('Undo this specific change?\n\nThis creates a new commit that reverses just this one\'s changes — nothing is erased from history, and any unrelated commits before or after it are left untouched.')) return;

  dgeAdminShowWorking();
  try {
    const { owner, repo } = GITHUB_REPO_CONFIG;

    const commitDetail = await dgeGithubRequest(`${GH_API}/repos/${owner}/${repo}/git/commits/${commitSha}`, { headers: dgeGithubHeaders(), cache: 'no-store' });
    const parentSha = commitDetail.parents && commitDetail.parents[0] && commitDetail.parents[0].sha;
    if (!parentSha) throw new Error('This is the very first commit in the repo — there\'s nothing before it to undo to.');

    const head = await dgeGithubGetBranchHead();
    const headCommitSha = head.commit.sha;

    const [parentMap, commitMap, headMap] = await Promise.all([
      dgeGithubGetBlobMapAt(parentSha),
      dgeGithubGetBlobMapAt(commitSha),
      dgeGithubGetBlobMapAt(headCommitSha)
    ]);

    // Union of every path touched by this commit (added, removed, or
    // changed), each mapped to what it should become on revert.
    const allPaths = new Set([...parentMap.keys(), ...commitMap.keys()]);
    const treeEntries = [];
    const skippedConflicts = [];

    allPaths.forEach(path => {
      const beforeSha = parentMap.get(path) || null; // state this commit changed FROM
      const afterSha = commitMap.get(path) || null;  // state this commit changed TO
      if (beforeSha === afterSha) return; // untouched by this commit

      const currentSha = headMap.get(path) || null;
      if (currentSha !== afterSha) {
        // Someone changed (or deleted/recreated) this path after the
        // commit being undone — reverting it now would silently discard
        // that later, unrelated edit instead of just this commit's.
        skippedConflicts.push(path);
        return;
      }

      if (beforeSha === null) {
        // This commit created the file; revert = remove it.
        treeEntries.push({ path, mode: '100644', type: 'blob', sha: null });
      } else {
        // This commit modified (or deleted) the file; revert = restore
        // the parent's blob content at this path.
        treeEntries.push({ path, mode: '100644', type: 'blob', sha: beforeSha });
      }
    });

    if (!treeEntries.length) {
      if (skippedConflicts.length) {
        throw new Error(`Every path this commit touched (${skippedConflicts.length}) was changed again since — nothing left that could be safely undone without also discarding those later edits.`);
      }
      throw new Error('This commit made no file changes that could be found to undo.');
    }

    const headCommitDetail = await dgeGithubRequest(`${GH_API}/repos/${owner}/${repo}/git/commits/${headCommitSha}`, { headers: dgeGithubHeaders(), cache: 'no-store' });
    const newTree = await dgeGithubCreateTree(headCommitDetail.tree.sha, treeEntries);
    const newCommit = await dgeGithubCreateCommit(
      dgeAdminBuildCommitMessage(`Undo: ${(commitDetail.message || '').split('\n')[0]}`),
      newTree.sha,
      headCommitSha
    );
    await dgeGithubUpdateRef(newCommit.sha);

    const summary = `Undone (${treeEntries.length} file(s) reverted)` +
      (skippedConflicts.length ? `, ${skippedConflicts.length} skipped — changed again since: ${skippedConflicts.join(', ')}` : '') + '.';
    if (typeof showToast === 'function') showToast(summary);
    dgeAdminNavigate(dgeAdminCurrentPath);
    dgeAdminRenderRecentActivity();
  } catch (e) {
    if (typeof showToast === 'function') showToast('Undo failed: ' + e.message);
  } finally {
    dgeAdminHideWorking();
  }
};

// Full recursive tree — used for folder-level rename/move, where every
// descendant file needs to be relocated.
function dgeGithubGetRecursiveTree() {
  const { owner, repo, branch } = GITHUB_REPO_CONFIG;
  const url = `${GH_API}/repos/${owner}/${repo}/git/trees/${branch}?recursive=1&_=${Date.now()}`;
  return dgeGithubRequest(url, { headers: dgeGithubHeaders(), cache: 'no-store' });
}

const DGE_TEXT_EXTENSIONS = ['.js', '.json', '.html', '.css', '.md', '.txt', '.svg', '.yml', '.yaml'];
function dgeIsTextFile(name) {
  return DGE_TEXT_EXTENSIONS.some(ext => name.toLowerCase().endsWith(ext));
}

// ---------------------------------------------------------------
// Modal open / PAT check
// ---------------------------------------------------------------
function dgeAdminShowWorking() {
  const el = document.getElementById('adminEditorWorking');
  if (el) el.style.display = 'flex';
}
function dgeAdminHideWorking() {
  const el = document.getElementById('adminEditorWorking');
  if (el) el.style.display = 'none';
}

window.openAdminEditor = function() {
  if (!dgeCheckSuperadminGate()) return;
  const tokenInput = document.getElementById('adminGithubTokenInput');
  if (tokenInput) tokenInput.value = dgeGithubToken();
  const nameInput = document.getElementById('adminNameInput');
  if (nameInput) nameInput.value = dgeAdminGetName();
  if (typeof openModal === 'function') openModal('adminEditorModal');
  // Return to wherever was last being browsed, not back to the root —
  // dgeAdminCurrentPath survives a close (the modal only hides, it
  // doesn't reset any state) so this just needs to not override it.
  dgeAdminNavigate(dgeAdminCurrentPath || dgeAdminGetRootPath());
  dgeAdminUpdateClipboardBar();
};

window.saveAdminGithubToken = function() {
  const tokenInput = document.getElementById('adminGithubTokenInput');
  if (!tokenInput) return;
  localStorage.setItem('github_admin_pat', tokenInput.value.trim());
  const nameInput = document.getElementById('adminNameInput');
  if (nameInput) localStorage.setItem('admin_editor_name', nameInput.value.trim() || 'Admin');
  if (typeof showToast === 'function') showToast('Saved to this device.');
  dgeAdminNavigate(dgeAdminCurrentPath);
};

// ---------------------------------------------------------------
// Navigation + listing render
// ---------------------------------------------------------------
async function dgeAdminNavigate(path) {
  dgeAdminHideWorking();
  const root = dgeAdminGetRootPath();
  // Hard clamp: never allow the current folder to end up above the
  // granted root, regardless of how this was called.
  if (root && path !== root && !path.startsWith(root + '/')) {
    path = root;
  }
  dgeAdminCurrentPath = path;
  dgeAdminSelectedItems.clear();

  const upBtn = document.getElementById('adminUpBtn');
  if (upBtn) {
    const atBoundary = (path === root);
    upBtn.disabled = atBoundary;
    upBtn.style.opacity = atBoundary ? '0.4' : '1';
    upBtn.style.cursor = atBoundary ? 'default' : 'pointer';
  }

  const listEl = document.getElementById('adminEditorList');
  const crumbEl = document.getElementById('adminEditorBreadcrumb');
  if (!listEl) return;

  listEl.innerHTML = `<div style="padding:20px; text-align:center; color:var(--muted-text); font-size:12px;">Loading…</div>`;

  if (crumbEl) {
    // Only render breadcrumb segments from the granted root onward — a
    // scoped admin never sees (or can drop onto) anything above it.
    const rootParts = root.split('/').filter(Boolean);
    const allParts = path.split('/').filter(Boolean);
    const visibleParts = allParts.slice(rootParts.length);
    let acc = root;
    // An empty root is the repo root itself (bhumandala) — label it as
    // such rather than a bare "/", and don't let the next segment pick up
    // a leading slash from an empty accumulator ("" + "/dge" = "/dge",
    // an invalid path one level narrower than intended).
    let crumbHtml = `<span class="admin-crumb" data-path="${root}" onclick="window.dgeAdminNavigateClick('${root}')" ondragover="event.preventDefault(); this.classList.add('drag-over');" ondragleave="this.classList.remove('drag-over');" ondrop="window.dgeAdminHandleDrop(event, '${root}')">${root || 'bhumandala'}</span>`;
    visibleParts.forEach(p => {
      acc = acc ? acc + '/' + p : p;
      const dest = acc;
      crumbHtml += ` / <span class="admin-crumb" data-path="${dest}" onclick="window.dgeAdminNavigateClick('${dest}')" ondragover="event.preventDefault(); this.classList.add('drag-over');" ondragleave="this.classList.remove('drag-over');" ondrop="window.dgeAdminHandleDrop(event, '${dest}')">${p}</span>`;
    });
    crumbEl.innerHTML = crumbHtml;
  }

  if (!dgeGithubToken()) {
    listEl.innerHTML = `<div class="note-preview-box" style="margin:0;">Paste your GitHub token above and tap Save to browse and edit files.</div>`;
    return;
  }

  try {
    const items = await dgeGithubListDir(path);
    let sorted = [...items].sort((a, b) => {
      if (a.type !== b.type) return a.type === 'dir' ? -1 : 1;
      return a.name.localeCompare(b.name);
    });

    let modifiedByPath = {};
    if (dgeAdminSortMode === 'modified') {
      const fileItems = sorted.filter(i => i.type === 'file');
      if (fileItems.length) {
        listEl.innerHTML = `<div style="padding:20px; text-align:center; color:var(--muted-text); font-size:12px;">Loading modified dates for ${fileItems.length} file(s)…</div>`;
        const results = await Promise.all(fileItems.map(async item => {
          try {
            const commits = await dgeGithubGetFileLastModified(item.path);
            const c = commits && commits[0];
            const date = c && c.commit && c.commit.author && c.commit.author.date;
            return { path: item.path, date: date || null };
          } catch (e) {
            return { path: item.path, date: null };
          }
        }));
        results.forEach(r => { modifiedByPath[r.path] = r.date; });

        // Folders still sort by name first (a folder's "modified" date
        // would mean aggregating every descendant file — expensive and
        // not worth it here); files within this folder sort newest first.
        const dirs = sorted.filter(i => i.type === 'dir');
        const files = fileItems.slice().sort((a, b) => {
          const da = modifiedByPath[a.path], db = modifiedByPath[b.path];
          if (!da && !db) return a.name.localeCompare(b.name);
          if (!da) return 1;
          if (!db) return -1;
          return new Date(db) - new Date(da);
        });
        sorted = [...dirs, ...files];
      }
    }

    listEl.innerHTML = sorted.map(item => {
      const icon = item.type === 'dir' ? '📁' : (dgeIsTextFile(item.name) ? '📝' : '🖼️');
      const modifiedLabel = (dgeAdminSortMode === 'modified' && item.type === 'file' && modifiedByPath[item.path])
        ? `<span class="admin-file-size">${dgeFormatShortDate(modifiedByPath[item.path])}</span>`
        : (item.type === 'file' ? `<span class="admin-file-size">${dgeFormatBytes(item.size)}</span>` : '');
      const rowAction = `onclick="window.dgeAdminRowClick(event, '${item.path}', '${item.type}', '${item.name.replace(/'/g, "\\'")}')"`;
      const isOpenFile = item.type === 'file' && item.path === dgeAdminOpenFilePath;

      const checked = dgeAdminSelectedItems.has(item.path) ? 'checked' : '';

      return `
        <div class="admin-file-row${isOpenFile ? ' admin-file-row-open' : ''}" draggable="true"
             data-path="${item.path}" data-type="${item.type}"
             ondragstart="window.dgeAdminDragStart(event, '${item.path}')"
             ${item.type === 'dir' ? `ondragover="event.preventDefault(); this.classList.add('drag-over');" ondragleave="this.classList.remove('drag-over');" ondrop="window.dgeAdminHandleDrop(event, '${item.path}')"` : ''}>
          <input type="checkbox" class="admin-select-checkbox" ${checked} onclick="event.stopPropagation(); window.dgeAdminToggleSelect('${item.path}', '${item.type}', this.checked)">
          <div class="admin-file-main" ${rowAction}>
            <span>${icon}</span>
            <span class="admin-file-name">${item.name}</span>
            ${modifiedLabel}
          </div>
          <div class="admin-file-actions">
            ${item.type === 'dir' ? `<button class="btn-icon" title="Download this folder as a .zip" onclick="event.stopPropagation(); window.dgeAdminDownloadFolderZip('${item.path}')">📦</button>` : `<button class="btn-icon" title="Download this file" onclick="event.stopPropagation(); window.dgeAdminDownloadFile('${item.path}')">⬇️</button>`}
            <button class="btn-icon" title="Rename" onclick="event.stopPropagation(); window.dgeAdminRename('${item.path}', '${item.type}')">✏️</button>
            <button class="btn-icon" title="Delete" onclick="event.stopPropagation(); window.dgeAdminDelete('${item.path}', '${item.type}', '${item.sha || ''}')">🗑️</button>
          </div>
        </div>`;
    }).join('') || `<div class="note-preview-box" style="margin:0;">Empty folder.</div>`;

    dgeAdminUpdateSelectionBar();
    dgeAdminUpdateClipboardBar();
  } catch (e) {
    // A 404 here usually means this folder just stopped existing — most
    // often because its last remaining file was deleted, and Git doesn't
    // track empty folders. Rather than dead-ending on an error, step up
    // to the parent folder automatically (unless we're already at the
    // granted root, which can't disappear).
    if (String(e.message).includes('404') && path !== root) {
      const parts = path.split('/').filter(Boolean);
      parts.pop();
      const parentPath = parts.join('/');
      if (typeof showToast === 'function') showToast('That folder no longer exists (its last file was likely just removed) — moved up a level.');
      dgeAdminNavigate(parentPath || root);
      return;
    }
    listEl.innerHTML = `<div class="note-preview-box" style="margin:0; color:var(--accent-red);">Couldn't load this folder: ${e.message}</div>`;
  }
}
window.dgeAdminNavigate = dgeAdminNavigate;

window.dgeAdminNavigateClick = function(path) {
  dgeAdminNavigate(path);
};

function dgeFormatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

window.dgeAdminGoUp = function() {
  const root = dgeAdminGetRootPath();
  if (dgeAdminCurrentPath === root) return; // already at the boundary — Up does nothing, by design
  const parts = dgeAdminCurrentPath.split('/').filter(Boolean);
  parts.pop();
  const candidate = parts.join('/');
  // Never allow landing above the granted root, even via odd path math
  if (root && !(candidate === root || candidate.startsWith(root + '/'))) {
    dgeAdminNavigate(root);
    return;
  }
  dgeAdminNavigate(candidate);
};

// ---------------------------------------------------------------
// Open / edit / save a text file
// ---------------------------------------------------------------
let dgeAdminOpenFileSha = null;
let dgeAdminOpenFilePath = null;
// Bumped on every dgeAdminOpenFile call and captured locally by each one
// — if a slower earlier fetch resolves AFTER a faster later one (opening
// file B right after file A, whose GitHub API response is still
// in-flight), this stops the stale A response from landing in the
// textarea after B's correct content is already showing. Reported as
// "clicked a new file, still saw the old one until I closed and
// reopened it" — this guard removes that possibility regardless of the
// exact timing that triggers it.
let dgeAdminOpenFileRequestId = 0;

window.dgeAdminOpenFile = async function(path, name) {
  if (!dgeIsTextFile(name)) {
    if (typeof showToast === 'function') showToast('This file type can only be uploaded/replaced, not edited inline here.');
    return;
  }
  const editorBox = document.getElementById('adminEditorFileBox');
  const nameEl = document.getElementById('adminEditorFileName');
  const textarea = document.getElementById('adminEditorTextarea');
  if (!editorBox || !textarea) return;

  const myRequestId = ++dgeAdminOpenFileRequestId;

  editorBox.style.display = 'block';
  editorBox.scrollIntoView({ behavior: 'smooth', block: 'start' });
  if (nameEl) nameEl.innerText = 'Loading ' + path + '…';
  textarea.value = '';

  try {
    const file = await dgeGithubGetFile(path);
    if (myRequestId !== dgeAdminOpenFileRequestId) return; // a newer open has since started — discard this stale result
    dgeAdminOpenFileSha = file.sha;
    dgeAdminOpenFilePath = path;
    textarea.value = dgeBase64ToUtf8(file.content);
    if (nameEl) nameEl.innerText = path;
    document.querySelectorAll('#adminEditorList .admin-file-row').forEach(row => {
      row.classList.toggle('admin-file-row-open', row.dataset.path === path);
    });
  } catch (e) {
    if (myRequestId !== dgeAdminOpenFileRequestId) return;
    if (nameEl) nameEl.innerText = 'Failed to load: ' + e.message;
  }
};

window.dgeAdminCloseFileEditor = function() {
  const editorBox = document.getElementById('adminEditorFileBox');
  if (editorBox) editorBox.style.display = 'none';
  dgeAdminOpenFileSha = null;
  dgeAdminOpenFilePath = null;
  dgeAdminOpenFileRequestId++; // invalidate any still-in-flight open
  document.querySelectorAll('#adminEditorList .admin-file-row-open').forEach(row => row.classList.remove('admin-file-row-open'));
};

window.dgeAdminSelectAllText = function() {
  const ta = document.getElementById('adminEditorTextarea');
  if (ta) { ta.focus(); ta.select(); }
};

window.dgeAdminClearAllText = function() {
  const ta = document.getElementById('adminEditorTextarea');
  if (!ta) return;
  if (!confirm('Clear all text in the editor? This only clears the box here — nothing is saved to GitHub until you tap Save.')) return;
  ta.value = '';
  ta.focus();
};

window.dgeAdminSaveFile = async function() {
  if (!dgeAdminOpenFilePath) return;
  const textarea = document.getElementById('adminEditorTextarea');
  if (!textarea) return;

  const warnings = await dgeAdminValidateGranthaFileEntries([
    { path: dgeAdminOpenFilePath, bytes: new TextEncoder().encode(textarea.value) }
  ]);
  if (warnings.length && !confirm(`This save looks off:\n\n${warnings.join('\n\n')}\n\nSave anyway?`)) return;

  const rawMsg = prompt('Commit message:', `Update ${dgeAdminOpenFilePath}`);
  if (rawMsg === null) return;
  const msg = dgeAdminBuildCommitMessage(rawMsg);
  if (msg === null) return;

  try {
    dgeAdminShowWorking();
    await dgeGithubPutFile(dgeAdminOpenFilePath, dgeUtf8ToBase64(textarea.value), msg, dgeAdminOpenFileSha);
    if (typeof showToast === 'function') showToast('Saved to GitHub.');
    window.dgeAdminCloseFileEditor();
    dgeAdminNavigate(dgeAdminCurrentPath);
  } catch (e) {
    dgeAdminHideWorking();
    if (typeof showToast === 'function') showToast('Save failed: ' + e.message);
  }
};

// ---------------------------------------------------------------
// Content sanity checks — run on any batch of files about to be pushed
// through this admin tool, before the commit happens. This tool is a
// raw file browser: it diffs bytes and pushes them with zero awareness
// of what a grantha data.json is supposed to look like. Fine for
// arbitrary file management, but it means a content mistake — the wrong
// file in the wrong sarga folder, a whole chapter duplicated under two
// paths, content pushed to a path nobody registered in library.json so
// it's unreachable — previously went through with no warning at all.
// Found exactly this happening to a real upload: "Raghavendra Vijaya"
// sarga files systematically off by one (folder sarga_1 held sarga 2's
// content, ... folder sarga_9 held sarga 10's content), sarga 10
// duplicated under both sarga_9 and sarga_10, no true sarga_1 anywhere
// in the batch, and the whole grantha never added to library.json so it
// couldn't show up anywhere regardless. These checks don't block the
// push — this tool has to stay usable for arbitrary non-grantha files
// too — but they surface anything that looks wrong before it goes live
// instead of after, either as a confirm() the admin can override or (for
// the zip flow, which already has its own preview step) as a warning
// banner alongside the file list.
async function dgeAdminValidateGranthaFileEntries(fileEntries) {
  const warnings = [];
  const decoder = new TextDecoder('utf-8');
  const parsed = []; // { path, data, error }

  fileEntries
    .filter(f => /\/data\.json$/.test(f.path))
    .forEach(f => {
      try {
        parsed.push({ path: f.path, data: JSON.parse(decoder.decode(f.bytes)), error: null });
      } catch (e) {
        parsed.push({ path: f.path, data: null, error: e.message });
      }
    });
  if (!parsed.length) return warnings;

  parsed.forEach(({ path, error }) => {
    if (error) warnings.push(`"${path}" is not valid JSON (${error}) — it will still be uploaded as-is.`);
  });

  // Every existing grantha folder in the library uses
  // lowercase_with_underscores. A space or uppercase letter usually
  // means the folder was named straight from a delivery zip rather than
  // following the site's own convention. URL routing itself tolerates
  // either (library.js falls back to encodeURIComponent for anything
  // that isn't a plain slug) so this is a style nag, not a functional
  // requirement.
  //
  // 23 Aug 2026: the project lead deliberately chose PascalCase for these
  // four folders (SarvaMula/DvaitaVedanta/SetuTila under Vedanta/Dvaita,
  // and DvaitaVedanta/Itara/Stotra/prahlada_kruta_narasimha) as the new naming standard going
  // forward, so they're exempted here rather than nagging on every future
  // load of this editor.
  const DGE_INTENTIONAL_PASCAL_CASE = new Set([
    'SarvaMula', 'DvaitaVedanta', 'SetuTila', 'PrahladaKrutaNarasimha'
  ]);
  const badSegs = new Set();
  parsed.forEach(({ path }) => {
    path.replace(/^data\//, '').split('/').slice(0, -1).forEach(seg => {
      if (/[ A-Z]/.test(seg) && !DGE_INTENTIONAL_PASCAL_CASE.has(seg)) badSegs.add(seg);
    });
  });
  badSegs.forEach(seg => {
    warnings.push(`Folder name "${seg}" has a space or uppercase letter — every other grantha folder here uses lowercase_with_underscores. Consider renaming before this goes live.`);
  });

  // Self-consistency of the legacy {metadata, shlokas:{...}} shape this
  // site's grantha pages actually understand.
  parsed.forEach(({ path, data, error }) => {
    if (error || !data || !data.metadata || !data.shlokas) return;
    const folderName = path.split('/').slice(-2, -1)[0];
    // Prefer the newer metadata.id (23 Aug 2026 standard: matches the
    // folder name exactly by convention) over metadata.stotraCode, which
    // can now deliberately diverge from the folder -- e.g. pns/ was
    // renamed to PrahladaKrutaNarasimha/ but keeps stotraCode: "pns" on
    // purpose, as the stable localStorage/audio-cache namespace existing
    // readers' saved progress already lives under (see core.js's
    // STOTRA_CODE_CONTINUITY). Falls back to stotraCode for older files
    // that don't have an id field yet.
    const code = data.metadata.id || data.metadata.stotraCode;
    if (code && code !== folderName) {
      warnings.push(`"${path}": folder is named "${folderName}" but its own metadata.id/stotraCode says "${code}" — this file may hold the wrong chapter/sarga's content.`);
    }
    const declared = data.metadata.totalShlokas;
    const actual = Object.keys(data.shlokas).length;
    if (typeof declared === 'number' && declared !== actual) {
      warnings.push(`"${path}": metadata.totalShlokas says ${declared} but the file actually has ${actual} shloka(s).`);
    }
  });

  // Byte-identical shloka content under two different paths in the same
  // batch almost always means a misplaced/duplicated file, not two
  // genuinely identical chapters.
  const bySignature = new Map();
  parsed.forEach(({ path, data, error }) => {
    if (error || !data || !data.shlokas) return;
    const sig = JSON.stringify(data.shlokas);
    if (!bySignature.has(sig)) bySignature.set(sig, []);
    bySignature.get(sig).push(path);
  });
  bySignature.forEach(paths => {
    if (paths.length > 1) warnings.push(`Identical shloka content appears under ${paths.length} different paths — likely a misplaced or duplicated file: ${paths.join(', ')}`);
  });

  // Not registered in library.json yet -- the file will sit on GitHub
  // but be unreachable: no Library-browser entry and no URL route to it.
  try {
    const library = await (window.dgeLibraryCatalogPromise || Promise.resolve(null));
    const known = new Set((library && library.granthas || []).map(g => g.path));
    const unregistered = parsed.filter(({ path, data, error }) => !error && data && data.metadata && data.shlokas && !known.has('dge/' + path));
    if (unregistered.length) {
      warnings.push(`${unregistered.length} file(s) here look like grantha data but have no entry in data/library.json yet — they will NOT appear in the Library browser or be reachable by a reading-page URL until an entry is added for each one.`);
    }
  } catch (e) { /* best effort only */ }

  return warnings;
}

// ---------------------------------------------------------------
// Upload (single or multiple) — via file picker or OS drag-drop onto
// the file list background
// ---------------------------------------------------------------
window.dgeAdminUploadFiles = async function(fileList) {
  if (!fileList || !fileList.length) return;
  if (typeof showToast === 'function') showToast(`Preparing ${fileList.length} file(s)…`);
  dgeAdminShowWorking();

  try {
    const fileEntries = [];
    for (const file of fileList) {
      const bytes = await dgeReadFileAsUint8Array(file);
      const targetPath = (dgeAdminCurrentPath ? dgeAdminCurrentPath + '/' : '') + file.name;
      fileEntries.push({ path: targetPath, bytes });
    }
    const warnings = await dgeAdminValidateGranthaFileEntries(fileEntries);
    if (warnings.length && !confirm(`This upload looks off:\n\n${warnings.join('\n\n')}\n\nUpload anyway?`)) {
      dgeAdminHideWorking();
      return;
    }
    const label = fileEntries.length === 1 ? `Upload ${fileEntries[0].path.split('/').pop()}` : `Upload ${fileEntries.length} file(s)`;
    const result = await dgeAdminBatchCommit(fileEntries, dgeAdminBuildCommitMessage(label));
    if (result.uploaded === 0) {
      if (typeof showToast === 'function') showToast(`Nothing to commit — already matched GitHub.`);
    } else {
      if (typeof showToast === 'function') showToast(`Committed ${result.uploaded} changed file(s) in one commit${result.unchanged ? ` (${result.unchanged} unchanged, skipped)` : ''}.`);
    }
  } catch (e) {
    if (typeof showToast === 'function') showToast('Upload failed: ' + e.message);
  } finally {
    dgeAdminHideWorking();
  }
  dgeAdminNavigate(dgeAdminCurrentPath);
};

// Uploads an entire local folder, preserving its internal structure.
// file.webkitRelativePath looks like "myFolder/sub/file.js" — everything
// after the first segment (the folder name itself, which the browser
// always includes) gets appended under the current admin folder, so the
// SUBFOLDER structure is preserved without recreating the top-level
// folder name redundantly.
window.dgeAdminUploadFolder = async function(fileList) {
  if (!fileList || !fileList.length) return;
  const topFolderName = (fileList[0].webkitRelativePath || '').split('/')[0] || 'this folder';
  if (typeof showToast === 'function') showToast(`Preparing "${topFolderName}" (${fileList.length} file(s))…`);
  dgeAdminShowWorking();

  try {
    const currentFolderName = (dgeAdminCurrentPath || '').split('/').filter(Boolean).pop() || '';
    const fileEntries = [];
    for (const file of fileList) {
      // webkitRelativePath includes the selected folder's own name as its
      // first segment (e.g. "myfolder/sub/file.js") — normally kept as-is
      // so the folder itself is recreated here, EXCEPT when that name
      // matches the admin folder already being stood in, which would
      // otherwise double up (see dgeStripRedundantFolderPrefix).
      const rel = file.webkitRelativePath || file.name;
      const relPath = dgeStripRedundantFolderPrefix(rel, currentFolderName);
      if (!relPath) continue;
      const bytes = await dgeReadFileAsUint8Array(file);
      const targetPath = (dgeAdminCurrentPath ? dgeAdminCurrentPath + '/' : '') + relPath;
      fileEntries.push({ path: targetPath, bytes });
    }
    const warnings = await dgeAdminValidateGranthaFileEntries(fileEntries);
    if (warnings.length && !confirm(`This upload looks off:\n\n${warnings.join('\n\n')}\n\nUpload anyway?`)) {
      dgeAdminHideWorking();
      return;
    }
    const result = await dgeAdminBatchCommit(
      fileEntries,
      dgeAdminBuildCommitMessage(`Upload (folder) ${topFolderName} — ${fileEntries.length} file(s)`)
    );
    if (result.uploaded === 0) {
      if (typeof showToast === 'function') showToast(`Nothing to commit — all ${result.unchanged} file(s) already matched GitHub.`);
    } else {
      if (typeof showToast === 'function') showToast(`Committed ${result.uploaded} changed file(s) in one commit (${result.unchanged} unchanged, skipped).`);
    }
  } catch (e) {
    if (typeof showToast === 'function') showToast('Folder upload failed: ' + e.message);
  } finally {
    dgeAdminHideWorking();
  }
  dgeAdminNavigate(dgeAdminCurrentPath);
};

// Extracts a .zip file entirely client-side (JSZip — already loaded for
// the folder-download feature) and pushes only the files that actually
// changed to GitHub, all as ONE commit — see dgeAdminBatchCommit above.
// Two things this handles that a naive extract-and-upload wouldn't:
//  - Redundant leading folder segment (see dgeStripRedundantFolderPrefix)
//    — matters a lot here since the admin's access is root-locked to
//    "dge" and every delivery zip is itself wrapped in "dge/".
//  - Directories in the zip that end up with no files under them (after
//    stripping) get a ".gitkeep" placeholder — Git has no concept of an
//    empty directory at all, so without this an empty folder in the zip
//    simply wouldn't appear on GitHub.
let dgeAdminPendingZip = null; // { fileEntries, emptyDirCount, sourceName } -- awaiting confirmation

// Extracts a .zip file entirely client-side (JSZip — already loaded for
// the folder-download feature) and shows exactly what it WOULD commit —
// every target path, total size, empty-folder count — before anything
// actually touches GitHub. Nothing is pushed until dgeAdminConfirmZipUpload
// is explicitly tapped.
// Two things this handles that a naive extract-and-upload wouldn't:
//  - Redundant leading folder segment (see dgeStripRedundantFolderPrefix)
//    — matters a lot here since the admin's access is root-locked to
//    "dge" and every delivery zip is itself wrapped in "dge/".
//  - Directories in the zip that end up with no files under them (after
//    stripping) get a ".gitkeep" placeholder — Git has no concept of an
//    empty directory at all, so without this an empty folder in the zip
//    simply wouldn't appear on GitHub.
window.dgeAdminUploadZip = async function(file) {
  if (!file) return;
  if (typeof JSZip === 'undefined') {
    if (typeof showToast === 'function') showToast('Zip library not loaded — check your connection and try again.');
    return;
  }

  if (typeof showToast === 'function') showToast(`Reading "${file.name}"…`);
  dgeAdminShowWorking();

  try {
    const zip = await JSZip.loadAsync(file);
    const allEntries = Object.values(zip.files);
    const fileZipEntries = allEntries.filter(f => !f.dir);
    const dirZipEntries = allEntries.filter(f => f.dir);
    if (!fileZipEntries.length && !dirZipEntries.length) throw new Error('This zip appears to be empty.');

    const currentFolderName = (dgeAdminCurrentPath || '').split('/').filter(Boolean).pop() || '';

    const fileEntries = [];
    for (const entry of fileZipEntries) {
      const relPath = dgeStripRedundantFolderPrefix(entry.name, currentFolderName);
      if (!relPath) continue;
      const bytes = await entry.async('uint8array');
      const targetPath = (dgeAdminCurrentPath ? dgeAdminCurrentPath + '/' : '') + relPath;
      fileEntries.push({ path: targetPath, bytes });
    }
    if (!fileEntries.length && !dirZipEntries.length) throw new Error('No files found inside this zip.');

    // Any directory in the zip with no file living under it needs an
    // explicit placeholder, or it silently won't exist on GitHub at all.
    const nonEmptyDirPrefixes = new Set();
    fileEntries.forEach(f => {
      const parts = f.path.split('/');
      let acc = '';
      for (let i = 0; i < parts.length - 1; i++) {
        acc = acc ? acc + '/' + parts[i] : parts[i];
        nonEmptyDirPrefixes.add(acc);
      }
    });
    let emptyDirCount = 0;
    for (const dirEntry of dirZipEntries) {
      const relDir = dgeStripRedundantFolderPrefix(dirEntry.name.replace(/\/$/, ''), currentFolderName);
      if (!relDir) continue;
      const targetDirPath = (dgeAdminCurrentPath ? dgeAdminCurrentPath + '/' : '') + relDir;
      if (!nonEmptyDirPrefixes.has(targetDirPath)) {
        fileEntries.push({ path: targetDirPath + '/.gitkeep', bytes: new Uint8Array(0) });
        nonEmptyDirPrefixes.add(targetDirPath);
        emptyDirCount++;
      }
    }

    const warnings = await dgeAdminValidateGranthaFileEntries(fileEntries);
    dgeAdminPendingZip = { fileEntries, emptyDirCount, sourceName: file.name, warnings };
    dgeAdminRenderZipPreview();
  } catch (e) {
    if (typeof showToast === 'function') showToast('Reading zip failed: ' + e.message);
  } finally {
    dgeAdminHideWorking();
  }
};

function dgeAdminRenderZipPreview() {
  const panel = document.getElementById('adminZipPreview');
  if (!panel || !dgeAdminPendingZip) return;
  const { fileEntries, emptyDirCount, sourceName, warnings } = dgeAdminPendingZip;

  const totalBytes = fileEntries.reduce((sum, f) => sum + (f.bytes ? f.bytes.length : 0), 0);
  const VISIBLE_LIMIT = 50;
  const shown = fileEntries.slice(0, VISIBLE_LIMIT);
  const remaining = fileEntries.length - shown.length;

  const warningsHtml = (warnings && warnings.length) ? `
    <div style="font-size:12px; margin-bottom:10px; padding:8px; background:#fff3cd; border:1px solid #e0b846; border-radius:6px; color:#5c4500;">
      <div style="font-weight:800; margin-bottom:4px;">⚠️ ${warnings.length} thing(s) look off — review before confirming:</div>
      ${warnings.map(w => `<div style="margin-top:4px;">• ${w}</div>`).join('')}
    </div>` : '';

  panel.style.display = 'block';
  panel.innerHTML = `
    <div style="font-weight:800; font-size:13px; margin-bottom:6px;">📦 About to upload from "${sourceName}"</div>
    <div style="font-size:12px; margin-bottom:8px;">${fileEntries.length} file(s), ${dgeFormatBytes(totalBytes)} total${emptyDirCount ? `, including ${emptyDirCount} empty folder(s) via .gitkeep` : ''}</div>
    ${warningsHtml}
    <div style="max-height:180px; overflow-y:auto; font-size:11px; font-family:monospace; background:var(--bg-main); border-radius:6px; padding:8px; margin-bottom:10px;">
      ${shown.map(f => `<div>${f.path}</div>`).join('')}
      ${remaining > 0 ? `<div style="color:var(--muted-text); margin-top:4px;">…and ${remaining} more</div>` : ''}
    </div>
    <div style="display:flex; gap:8px;">
      <button class="btn-sm" style="background:var(--accent-red); color:#fff;" onclick="window.dgeAdminConfirmZipUpload()">✅ Confirm & Upload</button>
      <button class="btn-sm" onclick="window.dgeAdminCancelZipUpload()">❌ Cancel</button>
    </div>`;
}

window.dgeAdminCancelZipUpload = function() {
  dgeAdminPendingZip = null;
  const panel = document.getElementById('adminZipPreview');
  if (panel) { panel.style.display = 'none'; panel.innerHTML = ''; }
};

window.dgeAdminConfirmZipUpload = async function() {
  if (!dgeAdminPendingZip) return;
  const { fileEntries, emptyDirCount, sourceName } = dgeAdminPendingZip;

  const panel = document.getElementById('adminZipPreview');
  if (panel) { panel.style.display = 'none'; panel.innerHTML = ''; }
  dgeAdminPendingZip = null;
  dgeAdminShowWorking();

  try {
    const result = await dgeAdminBatchCommit(
      fileEntries,
      dgeAdminBuildCommitMessage(`Sync from zip "${sourceName}" — ${fileEntries.length} file(s) in zip`)
    );

    if (result.uploaded === 0) {
      if (typeof showToast === 'function') showToast(`Nothing to commit — all ${result.unchanged} file(s) in the zip already matched GitHub.`);
    } else {
      if (typeof showToast === 'function') showToast(`Committed ${result.uploaded} changed file(s) in one commit (${result.unchanged} unchanged, skipped)${emptyDirCount ? `, including ${emptyDirCount} empty folder(s) preserved via .gitkeep` : ''}.`);
    }
    dgeAdminNavigate(dgeAdminCurrentPath);
  } catch (e) {
    if (typeof showToast === 'function') showToast('Zip upload failed: ' + e.message);
  } finally {
    dgeAdminHideWorking();
  }
};

// Uploads/writes a file whether or not something already exists at that
// path — GitHub's PUT requires the CURRENT sha to update an existing
// file; without one it's treated as "create new" and rejected with a
// 422 if the path is already taken. This checks first and supplies the
// sha automatically when needed, so Upload/Upload Folder correctly
// overwrite existing files instead of erroring on every one of them.
async function dgeAdminUpsertFile(targetPath, base64, message) {
  let sha;
  try {
    const existing = await dgeGithubGetFile(targetPath);
    sha = existing.sha;
  } catch (e) {
    // Doesn't exist yet — that's fine, sha stays undefined and this
    // becomes a create rather than an update.
  }
  await dgeGithubPutFile(targetPath, base64, message, sha);
}

// Git's blob sha is sha1("blob " + byteLength + "\0" + content) — computing
// this locally (Web Crypto, no library) lets us know whether a file has
// actually changed WITHOUT fetching or re-uploading it, just by comparing
// against the sha already sitting in the repo's tree listing.
async function dgeComputeGitBlobSha(bytes) {
  const header = new TextEncoder().encode(`blob ${bytes.length}\0`);
  const combined = new Uint8Array(header.length + bytes.length);
  combined.set(header, 0);
  combined.set(bytes, header.length);
  const digest = await crypto.subtle.digest('SHA-1', combined);
  return Array.from(new Uint8Array(digest)).map(b => b.toString(16).padStart(2, '0')).join('');
}

function dgeUint8ToBase64(bytes) {
  let binary = '';
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize));
  }
  return btoa(binary);
}

// A zip/folder upload's own internal paths often start with a folder name
// that MATCHES the admin folder you're currently standing in (e.g. every
// delivery zip for this project is wrapped in a top-level "dge/" folder,
// and the admin's own access is root-locked to "dge" — so uploading from
// there would otherwise land at "dge/dge/..."). Stripping one redundant
// matching leading segment fixes that automatically, regardless of which
// folder happens to be current when the upload runs. Returns '' if the
// entry WAS just the folder name itself with nothing under it.
//
// Checked against BOTH the currently-browsed folder AND the admin's
// root-locked folder (usually "dge"), not just the former: every delivery
// zip is wrapped in the root folder name specifically, not whatever
// subfolder the admin happens to be standing in when they upload. Syncing
// a "dge/..." zip while browsing dge/css (currentFolderName === "css")
// used to skip stripping entirely and land at dge/css/dge/... — a stale
// duplicate of the whole app that shipped and sat unnoticed for several
// commits (see PROJECT_STATUS.md history) until it was found and deleted.
function dgeStripRedundantFolderPrefix(relPath, currentFolderName) {
  const rootFolderName = (dgeAdminGetRootPath() || '').split('/').filter(Boolean).pop();
  const candidates = [currentFolderName, rootFolderName].filter(Boolean);
  for (const name of candidates) {
    if (relPath === name) return '';
    if (relPath.startsWith(name + '/')) return relPath.slice(name.length + 1);
  }
  return relPath;
}

async function dgeReadFileAsUint8Array(file) {
  const buf = await file.arrayBuffer();
  return new Uint8Array(buf);
}

// ---------------------------------------------------------------
// Batch diff-commit — the core of "sync only what changed, in one
// commit" behaviour. Given a list of { path, bytes } entries:
//   1. Reads the current branch head + its recursive tree ONCE (not
//      per file).
//   2. Computes each entry's git blob sha locally and skips any file
//      that's byte-identical to what's already on GitHub — no API
//      call at all for unchanged files.
//   3. For files that are new or different, creates blobs, builds one
//      new tree on top of the existing base tree (untouched files are
//      inherited automatically via base_tree — they don't need to be
//      listed), creates ONE commit, and moves the branch ref forward.
// This is atomic: either every changed file lands together in that one
// commit, or (if something fails before the ref update) nothing on
// GitHub changes at all — unlike the old per-file loop, where a failure
// partway through left some files updated and others not.
// ---------------------------------------------------------------
async function dgeAdminBatchCommit(fileEntries, commitMessage) {
  if (!fileEntries.length) return { uploaded: 0, unchanged: 0 };

  const head = await dgeGithubGetBranchHead();
  const baseCommitSha = head.commit.sha;
  const baseTreeSha = head.commit.commit.tree.sha;

  let existingTree = [];
  try {
    const treeData = await dgeGithubGetRecursiveTree();
    existingTree = treeData.tree || [];
    // GitHub truncates this response for very large trees. The repo now
    // holds thousands of data files, so this is a real possibility — and
    // a truncated listing makes the "skip unchanged files" comparison
    // unreliable. Surfaced rather than silently trusted.
    if (treeData.truncated) {
      console.warn('[Upload] GitHub truncated the repository tree listing. ' +
        'Change-detection may be incomplete; files will be re-uploaded rather than skipped.');
    }
  } catch (e) {
    // Empty/new repo or branch — fine, everything is treated as new.
  }
  const existingShaByPath = {};
  existingTree.forEach(entry => {
    if (entry.type === 'blob') existingShaByPath[entry.path] = entry.sha;
  });

  const changed = [];
  let unchanged = 0;
  for (const f of fileEntries) {
    const localSha = await dgeComputeGitBlobSha(f.bytes);
    if (existingShaByPath[f.path] === localSha) {
      unchanged++;
    } else {
      changed.push(f);
    }
  }

  if (!changed.length) return { uploaded: 0, unchanged };

  const treeEntries = [];
  for (const f of changed) {
    const blob = await dgeGithubCreateBlob(dgeUint8ToBase64(f.bytes));
    treeEntries.push({ path: f.path, mode: '100644', type: 'blob', sha: blob.sha });
  }

  const newTree = await dgeGithubCreateTree(baseTreeSha, treeEntries);
  const newCommit = await dgeGithubCreateCommit(commitMessage, newTree.sha, baseCommitSha);
  await dgeGithubUpdateRef(newCommit.sha);

  // Verify the files actually landed, rather than assuming a successful
  // API response means the content is correct. A file silently failing to
  // update — while everything reported success — cost real debugging time
  // once, so this now re-reads the tree and confirms every changed file's
  // sha matches what was just pushed.
  try {
    const check = await dgeGithubGetRecursiveTree();
    const afterSha = {};
    (check.tree || []).forEach(e => { if (e.type === 'blob') afterSha[e.path] = e.sha; });
    const notLanded = [];
    for (const f of changed) {
      const expected = await dgeComputeGitBlobSha(f.bytes);
      if (afterSha[f.path] !== expected) notLanded.push(f.path);
    }
    if (notLanded.length) {
      console.error('[Upload] Files did NOT land as expected:', notLanded);
      throw new Error(
        `${notLanded.length} file(s) did not update on GitHub despite the commit succeeding: ` +
        notLanded.slice(0, 5).join(', ') + (notLanded.length > 5 ? ' …' : '') +
        '. Try uploading those file(s) individually with the Upload button.'
      );
    }
  } catch (e) {
    if (e.message && e.message.includes('did not update')) throw e;
    console.warn('[Upload] Could not verify the commit landed:', e);
  }

  return { uploaded: changed.length, unchanged };
}

// ---------------------------------------------------------------
// New folder (Git has no real empty folders — create a .gitkeep
// placeholder file inside the new path to make it exist)
// ---------------------------------------------------------------
window.dgeAdminNewFolder = async function() {
  const name = prompt('New folder name:');
  if (!name) return;
  const targetPath = (dgeAdminCurrentPath ? dgeAdminCurrentPath + '/' : '') + name.trim() + '/.gitkeep';
  try {
    dgeAdminShowWorking();
    await dgeGithubPutFile(targetPath, dgeUtf8ToBase64(''), dgeAdminBuildCommitMessage(`Create folder ${name}`));
    if (typeof showToast === 'function') showToast('Folder created.');
    dgeAdminNavigate(dgeAdminCurrentPath);
  } catch (e) {
    dgeAdminHideWorking();
    if (typeof showToast === 'function') showToast('Failed: ' + e.message);
  }
};

// Creates a new blank file, restricted to a curated extension list
// (ADMIN_NEW_FILE_EXTENSIONS in config.js) rather than allowing anything.
window.dgeAdminNewFile = async function() {
  const allowed = window.ADMIN_NEW_FILE_EXTENSIONS || ['.js', '.json', '.html', '.css', '.md', '.txt'];
  const name = prompt(`New file name (allowed types: ${allowed.join(', ')}):`, 'untitled.txt');
  if (!name) return;
  const trimmed = name.trim();
  const hasAllowedExt = allowed.some(ext => trimmed.toLowerCase().endsWith(ext));
  if (!hasAllowedExt) {
    if (typeof showToast === 'function') showToast(`File type not allowed. Use one of: ${allowed.join(', ')}`);
    return;
  }
  const targetPath = (dgeAdminCurrentPath ? dgeAdminCurrentPath + '/' : '') + trimmed;
  try {
    dgeAdminShowWorking();
    await dgeGithubPutFile(targetPath, dgeUtf8ToBase64(''), dgeAdminBuildCommitMessage(`Create ${trimmed}`));
    if (typeof showToast === 'function') showToast('File created.');
    dgeAdminNavigate(dgeAdminCurrentPath);
  } catch (e) {
    dgeAdminHideWorking();
    if (typeof showToast === 'function') showToast('Failed: ' + e.message);
  }
};

// Fetches an image from an external URL and uploads it into the current
// folder. Honest limitation: this only works when the source host sends
// permissive CORS headers — many image hosts (and most social/CMS sites)
// don't, and the fetch will fail for those. There's no way around this
// from client-side JS; it would need a server-side proxy to fetch on the
// browser's behalf, which this static site doesn't have.
window.dgeAdminAddImageFromUrl = async function() {
  const url = prompt('Image URL to fetch and upload here:');
  if (!url || !url.trim()) return;
  const trimmedUrl = url.trim();

  let filename;
  try {
    const u = new URL(trimmedUrl);
    filename = u.pathname.split('/').pop() || 'image.png';
    if (!/\.[a-z0-9]+$/i.test(filename)) filename += '.png';
  } catch (e) {
    if (typeof showToast === 'function') showToast('That doesn\'t look like a valid URL.');
    return;
  }

  if (typeof showToast === 'function') showToast('Fetching image…');
  try {
    dgeAdminShowWorking();
    const res = await fetch(trimmedUrl);
    if (!res.ok) throw new Error(`Fetch failed: ${res.status}`);
    const blob = await res.blob();
    const base64 = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result.substring(reader.result.indexOf(',') + 1));
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
    const targetPath = (dgeAdminCurrentPath ? dgeAdminCurrentPath + '/' : '') + filename;
    await dgeAdminUpsertFile(targetPath, base64, dgeAdminBuildCommitMessage(`Add image from URL: ${trimmedUrl}`));
    if (typeof showToast === 'function') showToast('Image uploaded.');
    dgeAdminNavigate(dgeAdminCurrentPath);
  } catch (e) {
    dgeAdminHideWorking();
    if (typeof showToast === 'function') showToast(`Couldn't fetch that image — likely a CORS restriction from the source site (${e.message}). Try downloading it and using Upload instead.`);
  }
};

// ---------------------------------------------------------------
// Rename (file: get+put-new-path+delete-old; folder: same, repeated
// across every descendant via the recursive tree)
// ---------------------------------------------------------------
window.dgeAdminRename = async function(path, type) {
  const root = dgeAdminGetRootPath();
  const newPathRaw = prompt('Edit the full path (rename and/or move it here):', path);
  if (!newPathRaw || newPathRaw.trim() === path) return;
  const newPath = newPathRaw.trim().replace(/^\/+/, '').replace(/\/+$/, '');
  if (!newPath) return;
  if (root && newPath !== root && !newPath.startsWith(root + '/')) {
    if (typeof showToast === 'function') showToast("Can't move outside your allowed folder.");
    return;
  }
  const oldName = path.split('/').pop();
  const newName = newPath.split('/').pop();

  try {
    dgeAdminShowWorking();
    if (type === 'file') {
      await dgeAdminMoveOneFile(path, newPath, dgeAdminBuildCommitMessage(`Move/rename ${oldName} to ${newPath}`));
    } else {
      await dgeAdminMoveFolder(path, newPath);
    }
    if (typeof showToast === 'function') showToast('Moved/renamed.');
    dgeAdminNavigate(dgeAdminCurrentPath);
  } catch (e) {
    dgeAdminHideWorking();
    if (typeof showToast === 'function') showToast('Rename failed: ' + e.message);
  }
};

function dgeGithubGetBlob(sha) {
  const { owner, repo } = GITHUB_REPO_CONFIG;
  const url = `${GH_API}/repos/${owner}/${repo}/git/blobs/${sha}`;
  return dgeGithubRequest(url, { headers: dgeGithubHeaders() });
}

// Fetches a file's base64 content reliably regardless of size. GitHub's
// Contents API silently omits `content` (no error — it just isn't
// there) for files above roughly 1MB, which is exactly what caused a
// renamed file to end up 0 bytes: the code trusted an empty string as
// real content. This checks for that and falls back to the Git Blobs
// API (much higher size limit) before ever writing anything.
async function dgeAdminGetFileContentSafe(path) {
  const file = await dgeGithubGetFile(path);

  // A genuinely empty file (0 bytes, e.g. a .gitkeep placeholder) legitimately
  // has empty content — that's correct, not a failure, and must not be
  // confused with "content missing because the file is too large."
  if (file.size === 0) {
    return { content: '', sha: file.sha };
  }

  let content = file.content;
  if (!content || !content.replace(/\n/g, '').trim()) {
    const blob = await dgeGithubGetBlob(file.sha);
    content = blob.content;
  }
  if (!content || !content.replace(/\n/g, '').trim()) {
    throw new Error(`Could not read content for "${path}" (it may be too large, or a transient GitHub API issue) — stopped before writing anything, to avoid creating an empty file.`);
  }
  return { content: content.replace(/\n/g, ''), sha: file.sha };
}

/**
 * The tree entries that move `oldPath` to `newPath`, given a repository tree.
 *
 * WHY THIS IS PURE. It is the whole correctness of a move -- which blobs go
 * where, which paths are cleared, what is refused -- so it is a plain function
 * over a tree listing, testable without a token or a network.
 *
 * THE KEY POINT: a git move NEVER TOUCHES CONTENT. A tree entry is
 * {path, mode, type, sha}, so the new path simply reuses the EXISTING blob
 * sha and the old path is cleared with sha:null. Nothing is downloaded and
 * nothing is uploaded -- a 68 MB file moves as fast as a 1 KB one. The old
 * per-file loop fetched every file into the browser and pushed it back,
 * which is where the minutes went.
 *
 * Returns { entries, moved, blocked }. `blocked` is non-empty when the move
 * must not proceed.
 */
window.dgeAdminMoveTreeEntries = function (tree, oldPath, newPath) {
  const blobs = (tree || []).filter(t => t && t.type === 'blob');
  const under = p => p === oldPath || p.indexOf(oldPath + '/') === 0;
  const hits = blobs.filter(t => under(t.path));

  const blocked = [];
  if (!hits.length) blocked.push(`nothing at "${oldPath}"`);
  if (newPath === oldPath) blocked.push('the source and destination are the same path');
  // Moving a folder inside itself would build a tree that contains its own
  // parent and loses the rest -- refuse rather than produce it.
  if (newPath.indexOf(oldPath + '/') === 0) blocked.push('a folder cannot be moved inside itself');

  // A submodule is a commit pointer, not a blob; it has no content to
  // re-point and moving it this way would silently drop it.
  if ((tree || []).some(t => t && t.type === 'commit' && under(t.path))) {
    blocked.push('the selection contains a submodule');
  }

  const destinations = new Set(blobs.map(t => t.path));
  const entries = [];
  hits.forEach(t => {
    const rel = t.path === oldPath ? '' : t.path.slice(oldPath.length + 1);
    const dest = rel ? newPath + '/' + rel : newPath;
    if (destinations.has(dest) && !under(dest)) {
      blocked.push(`"${dest}" already exists`);
      return;
    }
    // mode is carried over, not assumed: an executable (100755) or a symlink
    // (120000) that came back as a plain 100644 would be quietly corrupted.
    entries.push({ path: dest, mode: t.mode || '100644', type: 'blob', sha: t.sha });
    entries.push({ path: t.path, mode: t.mode || '100644', type: 'blob', sha: null });
  });

  return { entries, moved: hits.length, blocked };
};

/**
 * Move a file or a whole folder in ONE commit.
 *
 * Replaces a loop that did GET-content + PUT + DELETE per file -- three API
 * calls and TWO commits each. Renaming 177 files that way was ~531 requests
 * and ~354 commits; this is five requests and one commit, whatever the count.
 *
 * It is also atomic, which matters more than the speed. The old loop could
 * die halfway and leave both folders half-populated (it did, on 11 Sep 2026),
 * and a retry with no idempotency wrote the same move twice.
 */
async function dgeAdminMovePath(oldPath, newPath, message) {
  const treeData = await dgeGithubGetRecursiveTree();
  // A truncated listing means the descendant set is incomplete, and moving on
  // it would leave files behind at the old path with no sign anything was
  // missed. Refuse: a half-move is worse than a failed one.
  if (treeData && treeData.truncated) {
    throw new Error('GitHub truncated its file listing for this repository, so a safe move cannot be planned. Move a smaller folder, or do this one with git.');
  }

  const plan = window.dgeAdminMoveTreeEntries((treeData || {}).tree || [], oldPath, newPath);
  if (plan.blocked.length) throw new Error(plan.blocked[0]);

  const head = await dgeGithubGetBranchHead();
  const newTree = await dgeGithubCreateTree(head.commit.commit.tree.sha, plan.entries);
  const newCommit = await dgeGithubCreateCommit(message, newTree.sha, head.commit.sha);
  await dgeGithubUpdateRef(newCommit.sha);
  return plan.moved;
}

// Kept as the single-file entry point so existing callers read unchanged.
// Both shapes are the same operation now -- git has no notion of a folder,
// only of paths, so "move a folder" was always "move every file under it".
async function dgeAdminMoveOneFile(oldPath, newPath, message) {
  return dgeAdminMovePath(oldPath, newPath, message);
}

// Downloads a folder and everything in it as a single .zip, built
// entirely client-side with JSZip. Uses the Git Blobs API (not the
// Contents API) to fetch each file's bytes, since the Contents API
// silently omits content for files above ~1MB — the same lesson learned
// from the earlier rename data-loss bug applies here.
// Downloads a single file, reusing the same safe content-fetch as
// rename/move — so large files (>1MB, where the Contents API omits
// content) download correctly via the Blobs API fallback too.
window.dgeAdminDownloadFile = async function(path) {
  try {
    dgeAdminShowWorking();
    const { content } = await dgeAdminGetFileContentSafe(path);
    const byteChars = atob(content);
    const byteNumbers = new Array(byteChars.length);
    for (let i = 0; i < byteChars.length; i++) byteNumbers[i] = byteChars.charCodeAt(i);
    const byteArray = new Uint8Array(byteNumbers);
    const blob = new Blob([byteArray]);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = path.split('/').pop();
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    if (typeof showToast === 'function') showToast('Downloaded.');
  } catch (e) {
    if (typeof showToast === 'function') showToast('Download failed: ' + e.message);
  } finally {
    dgeAdminHideWorking();
  }
};

let dgeAdminZipInProgress = false;
let dgeAdminZipCancelled = false;

// GitHub generates this entirely server-side in one request — much faster
// than fetching hundreds of individual file blobs through the API one at
// a time, but it's the WHOLE repo, not a specific folder (there's no
// GitHub endpoint that scopes a zip to a subfolder). Offered as a manual
// option here, and auto-suggested for large folder downloads below.
window.dgeAdminDownloadGithubRepoZip = async function() {
  const { owner, repo, branch } = GITHUB_REPO_CONFIG;
  const url = `${GH_API}/repos/${owner}/${repo}/zipball/${branch}`;
  if (typeof showToast === 'function') showToast('Requesting full repo zip from GitHub…');
  dgeAdminShowWorking();
  try {
    const res = await fetch(url, { headers: dgeGithubHeaders() });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const blob = await res.blob();
    const dlUrl = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = dlUrl;
    a.download = `${repo}-${branch}.zip`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(dlUrl);
    if (typeof showToast === 'function') showToast('Full repo zip downloaded — extract locally and grab whatever folder you need.');
  } catch (e) {
    if (typeof showToast === 'function') showToast('Repo zip download failed: ' + e.message);
  } finally {
    dgeAdminHideWorking();
  }
};

window.dgeAdminDownloadFolderZip = async function(folderPath) {
  // Tapping the same folder's zip button again while one is already
  // running cancels it, instead of starting a second one — simplest way
  // to offer "abort" without adding a whole new visible button.
  if (dgeAdminZipInProgress) {
    dgeAdminZipCancelled = true;
    if (typeof showToast === 'function') showToast('Cancelling…');
    return;
  }

  if (typeof JSZip === 'undefined') {
    if (typeof showToast === 'function') showToast('Zip library failed to load — check your connection and try again.');
    return;
  }
  dgeAdminShowWorking();

  try {
    const tree = await dgeGithubGetRecursiveTree();
    const descendants = tree.tree.filter(t => t.type === 'blob' && t.path.startsWith(folderPath + '/'));
    if (!descendants.length) {
      throw new Error('No files found in this folder according to GitHub\'s current tree.');
    }

    if (descendants.length > 150) {
      const useGithubZip = confirm(
        `This folder has ${descendants.length} files — building the zip here in the browser fetches each one individually and will take a while.\n\n` +
        `GitHub can generate a zip of the ENTIRE repo instantly on their end instead (extract just "${folderPath}" from it afterward) — much faster.\n\n` +
        `Use GitHub's fast whole-repo download instead?`
      );
      if (useGithubZip) {
        dgeAdminHideWorking();
        window.dgeAdminDownloadGithubRepoZip();
        return;
      }
    }

    dgeAdminZipInProgress = true;
    dgeAdminZipCancelled = false;
    if (typeof showToast === 'function') showToast(`Zipping "${folderPath}"… (0/${descendants.length}) — tap 📦 again to cancel`);

    const zip = new JSZip();
    let done = 0;
    const CONCURRENCY = 12; // fetched in parallel batches instead of one at a time
    let nextIndex = 0;

    async function worker() {
      while (nextIndex < descendants.length) {
        if (dgeAdminZipCancelled) return;
        const entry = descendants[nextIndex++];
        const blob = await dgeGithubGetBlob(entry.sha);
        if (dgeAdminZipCancelled) return;
        const relativePath = entry.path.slice(folderPath.length + 1);
        zip.file(relativePath, blob.content, { base64: true });
        done++;
        if (typeof showToast === 'function' && done % 20 === 0) showToast(`Zipping… ${done}/${descendants.length} — tap 📦 again to cancel`);
      }
    }

    await Promise.all(Array.from({ length: Math.min(CONCURRENCY, descendants.length) }, worker));

    if (dgeAdminZipCancelled) {
      if (typeof showToast === 'function') showToast('Zip cancelled.');
      return;
    }

    const zipBlob = await zip.generateAsync({ type: 'blob' });
    const folderName = folderPath.split('/').pop() || 'download';
    const url = URL.createObjectURL(zipBlob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${folderName}.zip`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);

    if (typeof showToast === 'function') showToast(`Downloaded ${folderName}.zip (${descendants.length} file(s)).`);
  } catch (e) {
    if (typeof showToast === 'function') showToast('Zip download failed: ' + e.message);
  } finally {
    dgeAdminZipInProgress = false;
    dgeAdminHideWorking();
  }
};

async function dgeAdminMoveFolder(oldFolderPath, newFolderPath) {
  const n = await dgeAdminMovePath(oldFolderPath, newFolderPath,
    dgeAdminBuildCommitMessage(`Move ${oldFolderPath} to ${newFolderPath}`));
  if (typeof showToast === 'function') showToast(`Moved ${n} file(s) in one commit.`);
  return n;
}

// ---------------------------------------------------------------
// Multi-select + batch move — several sources, one destination folder,
// one commit. Each source keeps its own basename at the destination
// (same rule single drag-and-drop uses); a source already blocked (name
// collision, moving a folder into itself, etc.) is skipped and reported
// rather than failing the whole batch, since the rest are still valid.
// ---------------------------------------------------------------
async function dgeAdminBatchMove(items, destFolder) {
  if (!items.length) return { moved: 0, blocked: [] };

  const treeData = await dgeGithubGetRecursiveTree();
  if (treeData && treeData.truncated) {
    throw new Error('GitHub truncated its file listing for this repository, so a safe move cannot be planned. Move fewer/smaller items, or do this one with git.');
  }
  const tree = (treeData || {}).tree || [];

  const allEntries = [];
  const claimedDest = new Set();
  const blocked = [];
  let moved = 0;

  items.forEach(item => {
    const name = item.path.split('/').pop();
    const newPath = destFolder ? destFolder + '/' + name : name;
    if (newPath === item.path) {
      blocked.push(`"${item.path}" is already in that folder`);
      return;
    }
    const plan = window.dgeAdminMoveTreeEntries(tree, item.path, newPath);
    if (plan.blocked.length) {
      blocked.push(`"${item.path}": ${plan.blocked[0]}`);
      return;
    }
    // Two selected items landing on the same destination (e.g. same-named
    // folders from different parents) would silently overwrite one
    // another in the merged tree — catch it before it's staged.
    const collides = plan.entries.some(e => e.sha !== null && claimedDest.has(e.path));
    if (collides) {
      blocked.push(`"${newPath}" collides with another selected item's destination`);
      return;
    }
    plan.entries.forEach(e => { if (e.sha !== null) claimedDest.add(e.path); });
    allEntries.push(...plan.entries);
    moved += plan.moved;
  });

  if (!allEntries.length) {
    throw new Error(blocked[0] || 'Nothing to move.');
  }

  const head = await dgeGithubGetBranchHead();
  const newTree = await dgeGithubCreateTree(head.commit.commit.tree.sha, allEntries);
  const message = dgeAdminBuildCommitMessage(
    items.length === 1 ? `Move ${items[0].path} to ${destFolder || '/'}` : `Move ${items.length} item(s) to ${destFolder || '/'}`
  );
  const newCommit = await dgeGithubCreateCommit(message, newTree.sha, head.commit.sha);
  await dgeGithubUpdateRef(newCommit.sha);
  return { moved, blocked };
}

// ---------------------------------------------------------------
// Multi-select + batch copy — same planning as batch move, but only the
// "add at destination" tree entries are kept; the "clear the old path"
// entries (sha: null) are dropped, so the source is left untouched.
// ---------------------------------------------------------------
async function dgeAdminBatchCopy(items, destFolder) {
  if (!items.length) return { copied: 0, blocked: [] };

  const treeData = await dgeGithubGetRecursiveTree();
  if (treeData && treeData.truncated) {
    throw new Error('GitHub truncated its file listing for this repository, so a safe copy cannot be planned. Copy fewer/smaller items, or do this one with git.');
  }
  const tree = (treeData || {}).tree || [];

  const allEntries = [];
  const claimedDest = new Set();
  const blocked = [];
  let copied = 0;

  items.forEach(item => {
    const name = item.path.split('/').pop();
    const newPath = destFolder ? destFolder + '/' + name : name;
    if (newPath === item.path) {
      blocked.push(`"${item.path}" is already in that folder`);
      return;
    }
    const plan = window.dgeAdminMoveTreeEntries(tree, item.path, newPath);
    if (plan.blocked.length) {
      blocked.push(`"${item.path}": ${plan.blocked[0]}`);
      return;
    }
    const additions = plan.entries.filter(e => e.sha !== null);
    const collides = additions.some(e => claimedDest.has(e.path));
    if (collides) {
      blocked.push(`"${newPath}" collides with another selected item's destination`);
      return;
    }
    additions.forEach(e => claimedDest.add(e.path));
    allEntries.push(...additions);
    copied += additions.length;
  });

  if (!allEntries.length) {
    throw new Error(blocked[0] || 'Nothing to copy.');
  }

  const head = await dgeGithubGetBranchHead();
  const newTree = await dgeGithubCreateTree(head.commit.commit.tree.sha, allEntries);
  const message = dgeAdminBuildCommitMessage(
    items.length === 1 ? `Copy ${items[0].path} to ${destFolder || '/'}` : `Copy ${items.length} item(s) to ${destFolder || '/'}`
  );
  const newCommit = await dgeGithubCreateCommit(message, newTree.sha, head.commit.sha);
  await dgeGithubUpdateRef(newCommit.sha);
  return { copied, blocked };
}

// ---------------------------------------------------------------
// Cut / Copy / Paste clipboard. Saved to localStorage (not just the
// in-memory dgeAdminMovePickItems this replaced) so it survives closing
// the modal AND a full page reload — "remember it" was the explicit ask.
// Cut is consumed by the next successful Paste (classic cut behavior);
// Copy stays in the clipboard so it can be pasted into more than one
// destination, until something new is cut/copied or it's cleared.
// ---------------------------------------------------------------
function dgeAdminSaveClipboard() {
  try {
    if (dgeAdminClipboard) localStorage.setItem('admin_clipboard', JSON.stringify(dgeAdminClipboard));
    else localStorage.removeItem('admin_clipboard');
  } catch (e) { /* ignore — clipboard just won't survive a reload this time */ }
}

function dgeAdminUpdateClipboardBar() {
  const bar = document.getElementById('adminClipboardBar');
  const countEl = document.getElementById('adminClipboardCount');
  if (!bar) return;
  const active = !!(dgeAdminClipboard && dgeAdminClipboard.items && dgeAdminClipboard.items.length);
  bar.style.display = active ? 'flex' : 'none';
  if (active && countEl) {
    const verb = dgeAdminClipboard.mode === 'cut' ? 'Cut' : 'Copied';
    countEl.textContent = `${verb}: ${dgeAdminClipboard.items.length} item(s) — browse into any folder, then tap "Paste Here".`;
  }
}
window.dgeAdminUpdateClipboardBar = dgeAdminUpdateClipboardBar;

// Cut/Copy hand the current checkbox selection off to the clipboard and
// clear the checkboxes — from here on, tapping a folder row navigates
// into it like normal (dgeAdminRowClick only intercepts taps when
// dgeAdminSelectedItems is non-empty, and it's empty now), so the whole
// repo tree is reachable as a destination to paste into.
window.dgeAdminCutSelected = function() {
  const items = Array.from(dgeAdminSelectedItems.entries()).map(([path, type]) => ({ path, type }));
  if (!items.length) return;
  dgeAdminClipboard = { mode: 'cut', items };
  dgeAdminSaveClipboard();
  dgeAdminSelectedItems.clear();
  dgeAdminUpdateSelectionBar();
  dgeAdminUpdateClipboardBar();
  if (typeof showToast === 'function') showToast(`Cut ${items.length} item(s) — browse to a folder and tap Paste Here.`);
};

window.dgeAdminCopySelected = function() {
  const items = Array.from(dgeAdminSelectedItems.entries()).map(([path, type]) => ({ path, type }));
  if (!items.length) return;
  dgeAdminClipboard = { mode: 'copy', items };
  dgeAdminSaveClipboard();
  dgeAdminSelectedItems.clear();
  dgeAdminUpdateSelectionBar();
  dgeAdminUpdateClipboardBar();
  if (typeof showToast === 'function') showToast(`Copied ${items.length} item(s) — browse to a folder and tap Paste Here. You can paste it again elsewhere too.`);
};

window.dgeAdminClearClipboard = function() {
  dgeAdminClipboard = null;
  dgeAdminSaveClipboard();
  dgeAdminUpdateClipboardBar();
};

window.dgeAdminPasteHere = async function() {
  if (!dgeAdminClipboard || !dgeAdminClipboard.items.length) return;
  const { mode, items } = dgeAdminClipboard;
  const dest = dgeAdminCurrentPath;
  const verb = mode === 'cut' ? 'Move' : 'Copy';
  const names = items.map(i => i.path.split('/').pop()).join(', ');
  const warn = mode === 'cut' ? "\nThis can't be undone from here." : '';
  if (!confirm(`${verb} ${items.length} item(s) into "${dest || '/'}"?\n${names}${warn}`)) return;

  try {
    dgeAdminShowWorking();
    const result = mode === 'cut' ? await dgeAdminBatchMove(items, dest) : await dgeAdminBatchCopy(items, dest);
    const count = mode === 'cut' ? result.moved : result.copied;

    if (mode === 'cut') {
      const wasOpenFileAffected = dgeAdminOpenFilePath && items.some(i =>
        i.path === dgeAdminOpenFilePath || (i.type === 'dir' && dgeAdminOpenFilePath.startsWith(i.path + '/'))
      );
      if (wasOpenFileAffected) window.dgeAdminCloseFileEditor();
      dgeAdminClipboard = null; // a cut is consumed by its paste; a copy stays for pasting elsewhere
      dgeAdminSaveClipboard();
    }
    dgeAdminUpdateClipboardBar();

    if (result.blocked.length) {
      const more = result.blocked.length > 1 ? ` (+${result.blocked.length - 1} more)` : '';
      if (typeof showToast === 'function') showToast(`${verb}d ${count} file(s). Skipped: ${result.blocked[0]}${more}`);
    } else if (typeof showToast === 'function') {
      showToast(`${verb}d ${items.length} item(s) (${count} file(s)) into "${dest || '/'}" in one commit.`);
    }
    dgeAdminNavigate(dgeAdminCurrentPath);
  } catch (e) {
    dgeAdminHideWorking();
    if (typeof showToast === 'function') showToast(`${verb} failed: ` + e.message);
  }
};

// ---------------------------------------------------------------
// Delete
// ---------------------------------------------------------------
// Deletes one or more files/folders in ONE commit — a tree entry with
// sha: null removes that path when built on top of the current base
// tree (same Git Data API technique as dgeAdminBatchCommit, in reverse).
// Folders are expanded to every descendant file first, since Git only
// ever tracks files, never folders directly — "deleting a folder" really
// means deleting everything inside it.
async function dgeAdminBatchDelete(items) {
  if (!items.length) return { deleted: 0 };

  const head = await dgeGithubGetBranchHead();
  const baseCommitSha = head.commit.sha;
  const baseTreeSha = head.commit.commit.tree.sha;

  const tree = await dgeGithubGetRecursiveTree();
  const allBlobPaths = tree.tree.filter(t => t.type === 'blob').map(t => t.path);

  const pathsToDelete = new Set();
  items.forEach(item => {
    if (item.type === 'dir') {
      allBlobPaths.forEach(p => {
        if (p === item.path || p.startsWith(item.path + '/')) pathsToDelete.add(p);
      });
    } else {
      pathsToDelete.add(item.path);
    }
  });
  if (!pathsToDelete.size) return { deleted: 0 };

  const treeEntries = Array.from(pathsToDelete).map(p => ({ path: p, mode: '100644', type: 'blob', sha: null }));
  const newTree = await dgeGithubCreateTree(baseTreeSha, treeEntries);
  const message = dgeAdminBuildCommitMessage(items.length === 1 ? `Delete ${items[0].path}` : `Delete ${items.length} item(s)`);
  const newCommit = await dgeGithubCreateCommit(message, newTree.sha, baseCommitSha);
  await dgeGithubUpdateRef(newCommit.sha);
  return { deleted: pathsToDelete.size };
}

window.dgeAdminDelete = async function(path, type) {
  let confirmMsg = type === 'dir'
    ? `Delete the folder "${path}" and everything inside it? This can't be undone from here.`
    : `Delete "${path}"? This can't be undone from here.`;

  if (type === 'file') {
    const siblingCount = document.querySelectorAll('#adminEditorList .admin-file-row').length;
    if (siblingCount <= 1) {
      confirmMsg = `This is the only item in this folder. Git doesn't track empty folders, so deleting it will remove the folder itself too. Continue?`;
    }
  }

  if (!confirm(confirmMsg)) return;

  try {
    dgeAdminShowWorking();
    await dgeAdminBatchDelete([{ path, type }]);
    if (dgeAdminOpenFilePath === path || (type === 'dir' && dgeAdminOpenFilePath && dgeAdminOpenFilePath.startsWith(path + '/'))) {
      window.dgeAdminCloseFileEditor();
    }
    if (typeof showToast === 'function') showToast('Deleted.');
    dgeAdminNavigate(dgeAdminCurrentPath);
  } catch (e) {
    if (typeof showToast === 'function') showToast('Delete failed: ' + e.message);
    dgeAdminHideWorking();
  }
};

// ---------------------------------------------------------------
// Multi-select + batch delete
// ---------------------------------------------------------------
function dgeAdminUpdateSelectionBar() {
  const bar = document.getElementById('adminSelectionBar');
  const countEl = document.getElementById('adminSelectionCount');
  if (!bar) return;
  const count = dgeAdminSelectedItems.size;
  bar.style.display = count ? 'flex' : 'none';
  if (countEl) countEl.textContent = `${count} selected`;
}

window.dgeAdminToggleSelect = function(path, type, checked) {
  if (checked) dgeAdminSelectedItems.set(path, type);
  else dgeAdminSelectedItems.delete(path);
  dgeAdminUpdateSelectionBar();
};

// Tapping a row normally opens/navigates into it. But once ANY item is
// already selected (selection mode active), tapping the rest of a row —
// not just its small checkbox — toggles selection instead. This is what
// stops a slightly-off tap from accidentally opening a folder while
// trying to select several items to delete: the very first checkbox tap
// still has to land precisely, but every tap after that is forgiving.
window.dgeAdminRowClick = function(event, path, type, name) {
  if (dgeAdminSelectedItems.size > 0) {
    const nowChecked = !dgeAdminSelectedItems.has(path);
    window.dgeAdminToggleSelect(path, type, nowChecked);
    const row = event.currentTarget.closest('.admin-file-row');
    const checkbox = row ? row.querySelector('.admin-select-checkbox') : null;
    if (checkbox) checkbox.checked = nowChecked;
    return;
  }
  if (type === 'dir') window.dgeAdminNavigateClick(path);
  else window.dgeAdminOpenFile(path, name);
};

window.dgeAdminSelectAllInFolder = function() {
  document.querySelectorAll('#adminEditorList .admin-file-row').forEach(row => {
    const path = row.getAttribute('data-path');
    const type = row.getAttribute('data-type');
    dgeAdminSelectedItems.set(path, type);
    const cb = row.querySelector('.admin-select-checkbox');
    if (cb) cb.checked = true;
  });
  dgeAdminUpdateSelectionBar();
};

window.dgeAdminClearSelection = function() {
  dgeAdminSelectedItems.clear();
  document.querySelectorAll('#adminEditorList .admin-select-checkbox').forEach(cb => { cb.checked = false; });
  dgeAdminUpdateSelectionBar();
};

window.dgeAdminDeleteSelected = async function() {
  const items = Array.from(dgeAdminSelectedItems.entries()).map(([path, type]) => ({ path, type }));
  if (!items.length) return;
  const names = items.map(i => i.path.split('/').pop()).join(', ');
  if (!confirm(`Delete ${items.length} selected item(s) in one commit?\n${names}\nThis can't be undone from here.`)) return;

  try {
    dgeAdminShowWorking();
    const result = await dgeAdminBatchDelete(items);
    const wasOpenFileAffected = dgeAdminOpenFilePath && items.some(i =>
      i.path === dgeAdminOpenFilePath || (i.type === 'dir' && dgeAdminOpenFilePath.startsWith(i.path + '/'))
    );
    if (wasOpenFileAffected) window.dgeAdminCloseFileEditor();
    dgeAdminSelectedItems.clear();
    if (typeof showToast === 'function') showToast(`Deleted ${result.deleted} file(s) across ${items.length} selected item(s) — one commit.`);
    dgeAdminNavigate(dgeAdminCurrentPath);
  } catch (e) {
    dgeAdminHideWorking();
    if (typeof showToast === 'function') showToast('Batch delete failed: ' + e.message);
  }
};

// ---------------------------------------------------------------
// Drag-and-drop move: drag a file/folder row onto another folder row
// (or a breadcrumb segment) to move it there
// ---------------------------------------------------------------
window.dgeAdminDragStart = function(e, path) {
  dgeAdminDragSourcePath = path;
  e.dataTransfer.effectAllowed = 'move';
};

// Auto-scrolls the admin modal's body while dragging near its top/bottom
// edge, so folders above or below the current viewport become reachable
// as drop targets without needing to release and manually scroll first.
let dgeAdminAutoScrollTimer = null;
document.addEventListener('dragover', (e) => {
  const modal = document.getElementById('adminEditorModal');
  if (!modal || modal.style.display === 'none' || !modal.style.display) return;
  const body = modal.querySelector('.modal-body');
  if (!body) return;

  const rect = body.getBoundingClientRect();
  const EDGE = 60;
  const y = e.clientY;

  clearInterval(dgeAdminAutoScrollTimer);
  if (y - rect.top < EDGE && y >= rect.top) {
    dgeAdminAutoScrollTimer = setInterval(() => { body.scrollTop -= 12; }, 16);
  } else if (rect.bottom - y < EDGE && y <= rect.bottom) {
    dgeAdminAutoScrollTimer = setInterval(() => { body.scrollTop += 12; }, 16);
  }
});
document.addEventListener('dragend', () => clearInterval(dgeAdminAutoScrollTimer));
document.addEventListener('drop', () => clearInterval(dgeAdminAutoScrollTimer));

// The list's own background (not a specific folder row) only accepts
// real OS file drops for upload. An internal row dragged here and
// released — without landing precisely on a folder or breadcrumb
// segment — is intentionally a no-op: the file stays exactly where it
// was, no error, nothing happens.
window.dgeAdminHandleBackgroundDrop = async function(e) {
  e.preventDefault();
  document.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over'));

  if (e.dataTransfer.files && e.dataTransfer.files.length) {
    await window.dgeAdminUploadFiles(e.dataTransfer.files);
  }
  dgeAdminDragSourcePath = null;
};

// Drop target = a SPECIFIC folder row or breadcrumb segment — the only
// valid places to actually move a file to.
window.dgeAdminHandleDrop = async function(e, targetFolderPath) {
  e.preventDefault();
  e.stopPropagation();
  document.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over'));

  if (e.dataTransfer.files && e.dataTransfer.files.length) {
    const prevPath = dgeAdminCurrentPath;
    dgeAdminCurrentPath = targetFolderPath;
    await window.dgeAdminUploadFiles(e.dataTransfer.files);
    dgeAdminCurrentPath = prevPath;
    return;
  }

  if (!dgeAdminDragSourcePath || dgeAdminDragSourcePath === targetFolderPath) { dgeAdminDragSourcePath = null; return; }
  const name = dgeAdminDragSourcePath.split('/').pop();
  const newPath = targetFolderPath ? targetFolderPath + '/' + name : name;
  if (newPath === dgeAdminDragSourcePath) { dgeAdminDragSourcePath = null; return; }

  const rowEl = document.querySelector(`.admin-file-row[data-path="${dgeAdminDragSourcePath}"]`);
  const type = rowEl ? rowEl.dataset.type : 'file';

  try {
    dgeAdminShowWorking();
    if (type === 'dir') {
      await dgeAdminMoveFolder(dgeAdminDragSourcePath, newPath);
    } else {
      await dgeAdminMoveOneFile(dgeAdminDragSourcePath, newPath, dgeAdminBuildCommitMessage(`Move ${name} to ${targetFolderPath}`));
    }
    if (typeof showToast === 'function') showToast(`Moved ${name}.`);
    dgeAdminNavigate(dgeAdminCurrentPath);
  } catch (err) {
    dgeAdminHideWorking();
    if (typeof showToast === 'function') showToast('Move failed: ' + err.message);
  }
  dgeAdminDragSourcePath = null;
};
