# Ask Claude — what it was, what is left, how to bring it back

*Written 30 Sep 2026 from `.github/workflows/ask-claude.yml`. The page half of this feature
is not in the repository, so this records what the workflow shows it did.*

## What it was

A chat with Claude from inside the library's own website, meant for the lead working from a
phone. Two halves:

1. **The page** (an "Ask Claude" tab on the old site, not in ShriBuddhi or Jagat). The lead typed a
   request, optionally naming library paths (`data/…/data.json`). The page committed
   `tasks/inbox/<id>.json` to `main` with the lead's own token, then polled that file.
2. **The workflow** (`ask-claude.yml`, kept). A push touching `tasks/inbox/*.json` woke a runner.
   It listed requests with `status: "pending"`, marked them "working", and ran a Claude Code
   session (`anthropics/claude-code-action@v1`, `--max-turns 80`) with the prompt in the file.

The session's rules, from the prompt: a **question** is answered from the repository; a
**change** (delete, pair, categorise, rename, move, fix) is made on a branch `claude/inbox-<id>`
and opened as a pull request, never on `main`; anything reserved for the lead (money, deleting
data, publishing, DNS) becomes a proposal with status `needs-answer`; it never calls Gemini.
It replies by appending to the file's `thread` and setting status `answered`, `done` or
`needs-answer`, and the page shows it. Round trip was two to four minutes.

Safety built into the workflow: only `tasks/inbox/` triggers it, its own reply commits are
skipped (no loop), one request at a time, and `--max-turns` caps the spend.

Needs one secret: `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN`.

## State today

Dormant. There is no `tasks/` folder, no `tasks/README.md` (the protocol the prompt says to read
first) and no page that writes requests, so nothing ever triggers it. The workflow's prompt now
names ShriBuddhi. Nothing in it touches Jagat, and nothing should: requests and replies are
workshop traffic.

## To bring it back

1. Add `admin/ask-claude.html` that commits `tasks/inbox/<id>.json` **to ShriBuddhi** (the
   Library Manager's "Publish shelf" code shows the pattern: Contents API, token typed into the
   page and held in memory only).
2. Restore `tasks/README.md` (the JSON shape: `id`, `instruction`, `sections[]`, `status`,
   `thread[]`) and `tasks/WEEKLY_INSTRUCTIONS.md` (step 5 of the prompt edits it).
3. Set `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN`.

A private repository that Claude edits from a phone is also an open door, so decide who may
write to `tasks/inbox/` before step 1.
