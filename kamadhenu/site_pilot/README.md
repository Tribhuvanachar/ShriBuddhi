# Kamadhenu site pilot — pulled from Buddhi (12 Sep 2026)

Removed from the public site because it's still a pilot: the standalone
"Kamadhenu trials" demo page (`pages_kamadhenu/`), the reader-integration
script (`kamadhenu.js`, was loaded directly by pages/reader/render.html
in Buddhi), and its data (`data_kamadhenu/`).

`kamadhenu.js` talks to a real, paid Hugging Face ZeroGPU Space
(`appConfig.kamadhenuSpaceUrl`, PRO account) -- it was live and callable
by any public visitor before this move, each call spending real GPU
compute. Buddhi's `js/config.js` now has `kamadhenuSpaceUrl: ""` (its own
documented kill-switch) and no longer loads `kamadhenu.js` at all.

To re-deploy once the pilot is ready: put `kamadhenu.js` back in Buddhi's
`js/`, `pages_kamadhenu/kamadhenu.html` back under `pages/kamadhenu/`,
`data_kamadhenu/` back under `data/kamadhenu/`, restore the nav-rail entry
in `js/dge-nav-rail.js` (removed in the same commit as this move), and
set `kamadhenuSpaceUrl` back to the deployed Space's URL.
