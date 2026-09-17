# images/

Static image assets. Currently: base templates for the "🖼️ Share as Image"
feature (`js/screenshot.js`).

## Templates saved so far

| File | Look | Branding baked in? |
|---|---|---|
| `template-01-jade-meander.jpg` | Teal/jade parchment, gold meander border | No |
| `template-02-lotus-watercolor.jpg` | Pink/gold lotus corners, watercolor wash | No |
| `template-03-temple-arch-dark.jpg` | Dark navy, gold temple arch + peacock feathers | No |
| `template-04-lotus-medallion.jpg` | Cream parchment, gold lotus corner medallions | No |
| `template-05-parchment-diya.png` | Aged red/gold parchment, diya + peacock feather | **Yes** — "sanatana vidya gurukula - 3 bu 1" is already in the pixels |
| `template-06-minimal-gold.png` | Minimal cream, thin gold frame, small lotus icon | **Yes** |
| `template-07-geometric-mihrab.png` | Vibrant red/teal/gold geometric mihrab arch | **Yes** |
| `template-08-watercolor-river.png` | Soft green watercolor, river + leaves | **Yes** |
| `template-09-stone-inscription.png` | Grayscale carved stone temple pillars | **Yes** |
| `_collage-uncropped-reference.png` | 5 more designs, but bundled as ONE image in a grid — see note below |

## Important: two different branding situations

Templates 01–04 are **clean** — no text baked in. `screenshot.js` should draw
the "Sarvamoola Digitisation Project · Sanatana Vidya Gurukula" + "Designed
by Tribhuvan Achar" footer on top of these, same as it does today.

Templates 05–09 (and every sub-image inside the collage) **already have**
"sanatana vidya gurukula - 3 bu 1" burned into the image itself, at a fixed
position near the bottom. If the code draws its OWN footer text on top of
these too, it'll double up / overlap. Once these get wired in, each
template needs a flag (e.g. `hasBakedBranding: true`) so the code skips
drawing its own footer for that one.

Each design also has a different-shaped "safe zone" for the shloka text —
a rectangle, a pointed temple arch, a rounded mihrab arch, etc. — so the
text placement/wrap width will need to be tuned per template, not one
generic center box for all of them.

## The collage file

`_collage-uncropped-reference.png` is 5 designs in a single 1254×1254 grid
image (2 rows × 3-ish columns), not 5 separate files. It's kept here only
as a visual reference. To actually use any of those 5 designs, they need
to be cropped out individually — happy to do that (crop coordinates can be
worked out from the grid), or if there's a way to re-export them
individually from whatever generated them, that'll give cleaner edges
than cropping a compressed collage.

## Chip icons (js/render.js)

Drawn PNGs replacing the earlier inline-SVG set, used for the per-shloka
Favorite/Status/Doubt/Notes/Snippets/⋯ chips:

| File | Used when |
|---|---|
| `icon-star-outline.png` | Favorite is off |
| `icon-star-filled.png` | Favorite is on (white, since the button background itself turns gold) |
| `icon-question-outline.png` | Doubt is off |
| `icon-question-filled.png` | Doubt is on |
| `icon-status-none.png` | No status assigned yet (dark ring, sits on light background) |
| `icon-status-pending.png` | Status = Pending (white ring, sits on the gray active background) |
| `icon-status-practice.png` | Status = Needs Practice (white, sits on orange) |
| `icon-status-done.png` | Status = Done (white, sits on green) |
| `icon-note.png` | Note-count badge |
| `icon-snippet.png` | Snippet-count badge |
| `icon-more.png` | The ⋯ actions-sheet button |

Note that `status-none`/`status-pending` are deliberately two separate
files, not one reused icon — the "no status yet" state sits on a plain
light background and needs a dark icon, while "Pending" sits on a
colored (muted-gray) active background and needs a white one. Same
reasoning applies to why star/question each have two files.

## Templates are now auto-discovered — no code changes needed

As of this version, the Share Image Template picker no longer reads from
a hardcoded list in `config.js`. Instead, the app queries GitHub's public
Contents API at runtime for whatever is actually in this folder right now
and offers every file matching `template*.png` / `.jpg` / `.jpeg`.

**To add a new template:** just upload a file here named
`template-whatever.png` (or `.jpg`) directly on GitHub. It'll show up in
the picker within an hour automatically (results are cached for an hour
to avoid hitting GitHub's API rate limit — tap "↻ Refresh" in the picker
to see it immediately without waiting).

**To exclude a file** that matches the naming pattern but shouldn't be
offered to end users (like a reference/working file), add its filename
(without extension) to `SHARE_TEMPLATE_EXCLUDE` in `js/config.js`.

**To fine-tune a specific template** (where exactly the shloka text sits,
or mark it as already having "सनातन विद्या गुरुकुल" baked into the
image), add an entry to `SHARE_TEMPLATE_OVERRIDES` in `js/config.js` keyed
by the filename without its extension. Anything without an override still
works — it just gets a generic centered text placement by default.

If GitHub's API is ever unreachable (offline, rate-limited), the picker
falls back to whatever was last successfully cached, or just "Plain" if
nothing has ever been cached yet — sharing never breaks entirely.
