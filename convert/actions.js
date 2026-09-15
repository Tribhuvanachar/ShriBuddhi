// convert/actions.js — GitHub Actions REST calls, window.DGE.Actions
// namespace. Dispatches the server-side OCR pipeline workflows
// (ocr-preview-pages.yml / ocr-sanskrit-commentary.yml) and polls for
// their result, so the "Server Pipeline" tab never needs to run OCR
// itself in this browser tab (the whole reason that pipeline exists is
// that a real book times out a browser tab -- see server-pipeline.js).
// Reuses github.js's token (same localStorage key, paste once).
window.DGE = window.DGE || {};
window.DGE.Actions = (function () {
  const GH_API = 'https://api.github.com';
  const REPO = { owner: 'Tribhuvanachar', repo: 'bhumandala' };

  function getToken() { return window.DGE.GitHub.getToken(); }

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
      if (res.status === 401 || res.status === 403) {
        msg += ' (check your GitHub token has "repo" scope, or "Actions: Read and write" for a fine-grained token)';
      }
      throw new Error(msg);
    }
    return res.status === 204 ? null : res.json();
  }

  // workflow_dispatch's own response carries no run id, so callers use
  // the returned timestamp with findDispatchedRun() below to locate it.
  async function dispatchWorkflow(workflowFile, inputs) {
    if (!getToken()) throw new Error('No GitHub token set — paste one in the GitHub panel above first.');
    const { owner, repo } = REPO;
    const dispatchedAt = Date.now();
    await request(`${GH_API}/repos/${owner}/${repo}/actions/workflows/${workflowFile}/dispatches`, {
      method: 'POST', headers: { ...headers(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ ref: 'main', inputs })
    });
    return dispatchedAt;
  }

  // Finds "our" run by polling the workflow's runs list for the newest
  // workflow_dispatch run created at/after dispatchedAt (with slack for
  // clock skew between this browser and GitHub's servers, and for the
  // few seconds GitHub itself takes to register a dispatch as a run).
  async function findDispatchedRun(workflowFile, dispatchedAt, opts) {
    const { timeoutMs = 60000, pollMs = 3000, onProgress } = opts || {};
    const { owner, repo } = REPO;
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const data = await request(
        `${GH_API}/repos/${owner}/${repo}/actions/workflows/${workflowFile}/runs?event=workflow_dispatch&per_page=5&_=${Date.now()}`,
        { headers: headers(), cache: 'no-store' }
      );
      const run = (data.workflow_runs || []).find(r => new Date(r.created_at).getTime() >= dispatchedAt - 10000);
      if (run) return run;
      if (onProgress) onProgress('waiting for the run to appear...');
      await new Promise(r => setTimeout(r, pollMs));
    }
    throw new Error('Timed out waiting for the workflow run to appear — check the Actions tab on GitHub directly.');
  }

  async function waitForRunCompletion(runId, opts) {
    const { timeoutMs = 20 * 60 * 1000, pollMs = 5000, onProgress } = opts || {};
    const { owner, repo } = REPO;
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const run = await request(`${GH_API}/repos/${owner}/${repo}/actions/runs/${runId}?_=${Date.now()}`,
        { headers: headers(), cache: 'no-store' });
      if (onProgress) onProgress(run);
      if (run.status === 'completed') return run;
      await new Promise(r => setTimeout(r, pollMs));
    }
    throw new Error('Timed out waiting for the workflow run to finish — check it directly on GitHub.');
  }

  async function listRunArtifacts(runId) {
    const { owner, repo } = REPO;
    const data = await request(`${GH_API}/repos/${owner}/${repo}/actions/runs/${runId}/artifacts`,
      { headers: headers() });
    return data.artifacts || [];
  }

  async function downloadArtifactZip(artifactId) {
    const { owner, repo } = REPO;
    const res = await fetch(`${GH_API}/repos/${owner}/${repo}/actions/artifacts/${artifactId}/zip`,
      { headers: headers() });
    if (!res.ok) throw new Error(`Could not download artifact: ${res.status} ${res.statusText}`);
    return res.arrayBuffer();
  }

  // One-shot convenience: dispatch, find the run, wait for it, return
  // {run, artifacts}. Callers extract whichever artifact they need.
  async function runWorkflowAndWait(workflowFile, inputs, opts) {
    const dispatchedAt = await dispatchWorkflow(workflowFile, inputs);
    const found = await findDispatchedRun(workflowFile, dispatchedAt, opts);
    const finished = await waitForRunCompletion(found.id, opts);
    const artifacts = await listRunArtifacts(finished.id);
    return { run: finished, artifacts };
  }

  return {
    dispatchWorkflow, findDispatchedRun, waitForRunCompletion,
    listRunArtifacts, downloadArtifactZip, runWorkflowAndWait, REPO,
  };
})();
