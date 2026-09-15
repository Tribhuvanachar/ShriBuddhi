// convert/github.js — minimal GitHub batch-commit writer,
// window.DGE.GitHub namespace. A leaner, Convert-scoped port of the same
// blob/tree/commit technique used by the main app's admin-editor.js
// (dgeAdminBatchCommit) — reusing the same TECHNIQUE per project
// convention, not a literal cross-file import, since this is a standalone
// page that doesn't load the main app's DOM or config.js. Shares the same
// localStorage token key as the main app's admin panel, so the token
// doesn't need re-entering if it's already saved there on this device.
window.DGE = window.DGE || {};
window.DGE.GitHub = (function () {
  const GH_API = 'https://api.github.com';
  // Mirrors GITHUB_REPO_CONFIG in the main app's js/config.js — update
  // both together if the repo ever changes.
  const REPO = { owner: 'Tribhuvanachar', repo: 'bhumandala', branch: 'main' };

  function getToken() { return localStorage.getItem('github_admin_pat') || ''; }
  function setToken(token) { localStorage.setItem('github_admin_pat', token || ''); }

  function headers() {
    const h = { 'Accept': 'application/vnd.github+json' };
    const t = getToken();
    if (t) h['Authorization'] = `token ${t}`;
    return h;
  }

  async function request(url, options) {
    const res = await fetch(url, options);
    if (!res.ok) {
      let msg = `${res.status} ${res.statusText}`;
      try { const j = await res.json(); if (j.message) msg += ` — ${j.message}`; } catch (e) { /* ignore */ }
      if (res.status === 401 || res.status === 403) msg += ' (check your GitHub token)';
      throw new Error(msg);
    }
    return res.status === 204 ? null : res.json();
  }

  function getBranchHead() {
    const { owner, repo, branch } = REPO;
    return request(`${GH_API}/repos/${owner}/${repo}/branches/${branch}?_=${Date.now()}`, { headers: headers(), cache: 'no-store' });
  }
  function getRecursiveTree() {
    const { owner, repo, branch } = REPO;
    return request(`${GH_API}/repos/${owner}/${repo}/git/trees/${branch}?recursive=1&_=${Date.now()}`, { headers: headers(), cache: 'no-store' });
  }
  function createBlob(base64Content) {
    const { owner, repo } = REPO;
    return request(`${GH_API}/repos/${owner}/${repo}/git/blobs`, {
      method: 'POST', headers: { ...headers(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: base64Content, encoding: 'base64' })
    });
  }
  function createTree(baseTreeSha, treeEntries) {
    const { owner, repo } = REPO;
    return request(`${GH_API}/repos/${owner}/${repo}/git/trees`, {
      method: 'POST', headers: { ...headers(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ base_tree: baseTreeSha, tree: treeEntries })
    });
  }
  function createCommit(message, treeSha, parentSha) {
    const { owner, repo } = REPO;
    return request(`${GH_API}/repos/${owner}/${repo}/git/commits`, {
      method: 'POST', headers: { ...headers(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, tree: treeSha, parents: [parentSha] })
    });
  }
  function updateRef(newCommitSha) {
    const { owner, repo, branch } = REPO;
    return request(`${GH_API}/repos/${owner}/${repo}/git/refs/heads/${branch}`, {
      method: 'PATCH', headers: { ...headers(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ sha: newCommitSha })
    });
  }

  function utf8ToBase64(str) {
    return btoa(unescape(encodeURIComponent(str)));
  }
  function base64ToUtf8(b64) {
    return decodeURIComponent(escape(atob((b64 || '').replace(/\n/g, ''))));
  }

  async function computeGitBlobSha(bytes) {
    const header = new TextEncoder().encode(`blob ${bytes.length}\0`);
    const combined = new Uint8Array(header.length + bytes.length);
    combined.set(header, 0);
    combined.set(bytes, header.length);
    const digest = await crypto.subtle.digest('SHA-1', combined);
    return Array.from(new Uint8Array(digest)).map(b => b.toString(16).padStart(2, '0')).join('');
  }

  // Reads a text file's current content straight from the repo (used to
  // fetch library.json fresh right before patching it).
  async function getFileText(path) {
    const { owner, repo, branch } = REPO;
    const file = await request(`${GH_API}/repos/${owner}/${repo}/contents/${path}?ref=${branch}&_=${Date.now()}`, { headers: headers(), cache: 'no-store' });
    return base64ToUtf8(file.content);
  }

  // fileEntries: [{ path, text }] (UTF-8 text content — this tool only
  // ever pushes JSON). Same atomic all-or-nothing behaviour as the main
  // app's batch commit: unchanged files are skipped with no API call,
  // everything that changed lands together in ONE commit.
  async function commitFiles(fileEntries, commitMessage) {
    if (!getToken()) throw new Error('No GitHub token set — paste one above first.');
    if (!fileEntries.length) return { uploaded: 0, unchanged: 0 };

    const head = await getBranchHead();
    const baseCommitSha = head.commit.sha;
    const baseTreeSha = head.commit.commit.tree.sha;

    let existingTree = [];
    try {
      const treeData = await getRecursiveTree();
      existingTree = treeData.tree || [];
    } catch (e) { /* new/empty repo — treat everything as new */ }
    const existingShaByPath = {};
    existingTree.forEach(e => { if (e.type === 'blob') existingShaByPath[e.path] = e.sha; });

    const changed = [];
    let unchanged = 0;
    for (const f of fileEntries) {
      const bytes = new TextEncoder().encode(f.text);
      const sha = await computeGitBlobSha(bytes);
      if (existingShaByPath[f.path] === sha) { unchanged++; continue; }
      changed.push({ path: f.path, base64: utf8ToBase64(f.text) });
    }
    if (!changed.length) return { uploaded: 0, unchanged };

    const treeEntries = [];
    for (const f of changed) {
      const blob = await createBlob(f.base64);
      treeEntries.push({ path: f.path, mode: '100644', type: 'blob', sha: blob.sha });
    }
    const newTree = await createTree(baseTreeSha, treeEntries);
    const newCommit = await createCommit(commitMessage, newTree.sha, baseCommitSha);
    await updateRef(newCommit.sha);
    return { uploaded: changed.length, unchanged };
  }

  return { getToken, setToken, commitFiles, getFileText, REPO };
})();
