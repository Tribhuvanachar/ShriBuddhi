# vidyut-prakriya — in-browser Paninian derivation engine

`vidyut_prakriya.js` + `vidyut_prakriya_bg.wasm` are **vidyut-prakriya**
(https://github.com/ambuda-org/vidyut, the Ambuda project, **Apache-2.0**)
compiled to WebAssembly with `wasm-pack build --target web --release` from
the crate's own `src/wasm.rs` bindings. No source modifications.

Used by `rupasiddhi.html` (`js/rupasiddhi.js`) to derive tinanta /
krdanta / subanta forms — with any stack of upasargas and sanadi
(णिच्/सन्/यङ्/यङ्लुक्) affixes, in any of the 11 lakaras, kartari or
karmani — **on the reader's own device**, each step of the derivation
naming the rule that fired. Nothing is sent to any server, and no
pregenerated data is needed beyond the ~67 KB per-root argument index
(`data/vedanga/vyakarana/dhatu_wasm_index.json`).

The same engine (as a native library) already generates this repo's
precomputed `prakriya/` data via `tools/build_prakriya.py` — the two agree
by construction.

Note: the .wasm here is the plain `--release` output, not additionally
shrunk by `wasm-opt` (the sandbox's binaryen was too old for the
reference-types this build uses and produced a wasm that failed at
`Table.grow` on init — tested, not assumed). GitHub Pages serves it
gzipped at roughly a third of its on-disk size. If rebuilding with a
current binaryen, verify `Vidyut.init()` still succeeds before shipping.
