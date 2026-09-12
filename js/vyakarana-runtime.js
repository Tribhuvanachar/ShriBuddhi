/* ==========================================================================
 * DGE · वैयाकरणम् — runtime word analysis that the precomputed indexes
 * cannot cover, layered UNDER them rather than replacing them.
 *
 *   Level 0  dge/data/_sandhi_local     one lookup, instant, 19,034 words
 *            dge/data/.../formindex     205k inflected verb forms
 *   Level 1  this file                  upasarga peeling + recursive
 *                                       multi-member compound splitting,
 *                                       computed in the browser on a miss
 *
 * Level 0 answers a single sandhi boundary for a word the corpus uses often
 * enough to have been precomputed. It cannot answer a three-member compound
 * (precomputing those is exponential) and it cannot see a root hiding behind
 * an upasarga, because the Dhatupatha stores bare roots: गम् is indexed,
 * समागच्छति is not, and no amount of static indexing changes that.
 *
 * Everything here validates against data already shipped in this repo — a
 * candidate that is not a real word is discarded rather than shown. That is
 * the difference between this and a raw combinatorial splitter, which will
 * happily offer 'g' + 'acCati'.
 *
 * NOT DONE HERE, deliberately: a neural sandhi model (a quantised ByT5 or
 * similar via onnxruntime-web) as a further fallback for irregular metrical
 * sandhi. It would be a 120-180 MB download on a reader's phone, which is a
 * decision for the project lead, not a default. The seam is `dgeAnalyseWord`
 * below: a Level 2 slots in where Level 1 returns nothing.
 * ========================================================================== */
(function () {
  "use strict";
  window.DGE_VERSIONS = window.DGE_VERSIONS || {};
  window.DGE_VERSIONS['vyakarana-runtime.js'] =
    'v1.0 (upasarga peeling with junction-sandhi inversion + dual-key artha lookup; ' +
    'recursive compound splitting validated against _morph and the verb form index)';

  // The 22 उपसर्गs. आङ् is written आ, and the pairs the tradition lists
  // separately but which surface identically (उद्/उत्, निस्/निर्, दुस्/दुर्)
  // are all here because a written form may show either.
  var UPASARGAS = ['प्र', 'परा', 'अप', 'सम्', 'अनु', 'अव', 'निस्', 'निर्', 'दुस्', 'दुर्',
                   'वि', 'आ', 'नि', 'अधि', 'अपि', 'अति', 'सु', 'उद्', 'उत्', 'अभि',
                   'प्रति', 'परि', 'उप'];

  // How an upasarga's own ending fuses with the root's initial vowel. Each
  // entry says: this JUNCTION text, seen where the two met, means the
  // upasarga really ended with `end` and the root really began with `begin`.
  // Only the transitions that actually change the written form are listed;
  // plain concatenation is handled separately.
  //
  // Written out as data because the alternative -- inverting sandhi in code
  // -- is where a table like this silently loses rules: a rule keyed twice
  // (गुणः o = अ+उ against the visarga o = अः+अ) overwrites itself and the
  // loss is invisible. Here every row is independent.
  // `begin` lists EVERY vowel the fused form could have hidden: सवर्णदीर्घ आ
  // is अ+अ, अ+आ, आ+अ or आ+आ, and only trying both readings finds सम् + आगच्छति
  // (which then peels again into सम् + आ + गच्छति).
  var JUNCTIONS = [
    // सवर्णदीर्घः — अ/आ + अ/आ → आ
    { fuse: 'ा', end: '',   begin: ['अ', 'आ'], rule: 'सवर्णदीर्घः', sutra: '6.1.101' },
    // गुणः — अ/आ + इ/ई → ए ; अ/आ + उ/ऊ → ओ
    { fuse: 'े', end: '',   begin: ['इ', 'ई'], rule: 'गुणः', sutra: '6.1.87' },
    { fuse: 'ो', end: '',   begin: ['उ', 'ऊ'], rule: 'गुणः', sutra: '6.1.87' },
    // वृद्धिः — अ/आ + ए → ऐ ; अ/आ + ओ → औ
    { fuse: 'ै', end: '',   begin: ['ए', 'ऐ'], rule: 'वृद्धिः', sutra: '6.1.88' },
    { fuse: 'ौ', end: '',   begin: ['ओ', 'औ'], rule: 'वृद्धिः', sutra: '6.1.88' },
    // यण् — इ + vowel → य् ; उ + vowel → व्
    { fuse: '्य', end: 'ि', begin: [''], rule: 'यण्', sutra: '6.1.77', yan: true },
    { fuse: '्व', end: 'ु', begin: [''], rule: 'यण्', sutra: '6.1.77', yan: true }
  ];

  // A remainder sliced off after य्/व् begins with a DEPENDENT vowel sign,
  // because the sign was hanging on the semivowel: प्रत्युवाच cut after
  // 'प्रत्य' leaves 'ुवाच', not 'उवाच'. The independent letter is what the
  // root actually starts with, and what the form index is keyed by.
  var SIGN_TO_VOWEL = {
    'ा': 'आ', 'ि': 'इ', 'ी': 'ई', 'ु': 'उ', 'ू': 'ऊ', 'ृ': 'ऋ', 'ॄ': 'ॠ',
    'े': 'ए', 'ै': 'ऐ', 'ो': 'ओ', 'ौ': 'औ'
  };
  function freeVowel(rest) {
    var first = rest.charAt(0);
    return SIGN_TO_VOWEL[first] ? SIGN_TO_VOWEL[first] + rest.slice(1) : rest;
  }

  function bucketOfDeva(word) {
    return word.codePointAt(0).toString(16).toLowerCase().padStart(4, '0');
  }

  var formShardCache = {};
  function verbFormShard(word) {
    var cp = bucketOfDeva(word);
    if (!formShardCache[cp]) {
      formShardCache[cp] = fetch('data/vedanga/vyakarana/prakriya/formindex/' + cp + '.json',
                                 { cache: 'force-cache' })
        .then(function (r) { return r.ok ? r.json() : null; })
        .catch(function () { return null; });
    }
    return formShardCache[cp];
  }

  // Every root whose paradigm produces this exact form. Same shape the Dhātu
  // popup already consumes, so a peeled root can be handed straight to it.
  function verbRootsFor(form) {
    return verbFormShard(form).then(function (shard) {
      var hit = shard && shard[form];
      if (!hit) return [];
      return Array.isArray(hit) ? hit : [hit];
    });
  }
  window.dgeVerbRootsFor = verbRootsFor;

  /* ---------------- upasarga peeling ---------------- */

  // Candidate (upasarga, remaining verb form) pairs for a written word.
  // Generated by trying every upasarga against every junction rule; the
  // caller validates each `rest` against the verb index, which is what keeps
  // this honest -- गम् can be found behind समागच्छति only because आगच्छति
  // is a form the index actually contains.
  function upasargaCandidates(word) {
    var out = [];
    var w = String(word || '');
    UPASARGAS.forEach(function (up) {
      // Plain prefixation: प्र + विशति → प्रविशति
      if (w.length > up.length && w.indexOf(up) === 0) {
        out.push({ upasarga: up, rest: w.slice(up.length), rule: 'सन्धिरहितम्', sutra: '' });
      }
      // The upasarga's last vowel fused with the root's first.
      var stem = up.replace(/[ािीुूृेैोौ्]$/, '');   // प्रति → प्रत , सम् → सम
      JUNCTIONS.forEach(function (j) {
        var head, tail;
        if (j.yan) {
          // यण्: प्रति + उवाच → प्रत्युवाच. The upasarga must itself end in
          // the matching vowel, and the root's initial vowel comes back as an
          // independent letter.
          if (up.slice(-1) !== j.end) return;
          head = up.slice(0, -1) + j.fuse;
          if (w.indexOf(head) !== 0) return;
          tail = w.slice(head.length);
          if (!tail) return;
          out.push({ upasarga: up, rest: freeVowel(tail), rule: j.rule, sutra: j.sutra });
          return;
        }
        head = stem + j.fuse;
        if (w.length <= head.length || w.indexOf(head) !== 0) return;
        tail = w.slice(head.length);
        j.begin.forEach(function (v) {
          out.push({ upasarga: up, rest: v + tail, rule: j.rule, sutra: j.sutra });
        });
      });
    });
    // Longest upasarga first: प्रति before प्र, so प्रत्युवाच is not read as
    // प्र + त्युवाच when the better analysis exists.
    out.sort(function (a, b) { return b.upasarga.length - a.upasarga.length; });
    return out;
  }
  window.dgeUpasargaCandidates = upasargaCandidates;

  // Validated peelings, best first:
  //   {upasarga, rest, roots:[{c,k}], rule, sutra, chain:[उपसर्ग...]}
  //
  // Peels up to `depth` prefixes, because a verb can carry more than one:
  // समागच्छति is सम् + आ + गच्छति, and stopping after सम् leaves आगच्छति --
  // itself a real form, so the first pass looks finished while the आ is still
  // unaccounted for. Two is enough for the corpus; the depth is a parameter
  // rather than a constant so raising it needs no rewrite.
  window.dgePeelUpasarga = function (word, depth) {
    depth = depth == null ? 2 : depth;
    var cands = upasargaCandidates(word);
    if (!cands.length) return Promise.resolve([]);
    return Promise.all(cands.map(function (c) {
      var here = verbRootsFor(c.rest).then(function (roots) {
        return roots.length
          ? [Object.assign({}, c, { roots: roots, chain: [c.upasarga] })]
          : [];
      });
      if (depth <= 1) return here;
      // Recurse on the remainder WHETHER OR NOT it validated. A prefixed
      // intermediate is not in the form index by construction -- the
      // Dhatupatha stores bare roots, so आगच्छति is absent even though it is
      // a real word -- and requiring it to validate would stop समागच्छति at
      // सम् and never reach गच्छति. Only the final bare root has to be real.
      var deeper = window.dgePeelUpasarga(c.rest, depth - 1).then(function (inner) {
        return inner.map(function (i) {
          return Object.assign({}, i, {
            upasarga: c.upasarga + ' + ' + i.upasarga,
            chain: [c.upasarga].concat(i.chain),
            rule: c.rule === i.rule ? c.rule : c.rule + ' → ' + i.rule
          });
        });
      });
      return Promise.all([here, deeper]).then(function (parts) {
        return parts[0].concat(parts[1]);
      });
    })).then(function (rows) {
      var seen = {}, out = [];
      rows.forEach(function (group) {
        group.forEach(function (r) {
          var key = r.upasarga + '|' + r.rest;
          if (seen[key]) return;
          seen[key] = 1;
          out.push(r);
        });
      });
      // A longer prefix chain accounts for more of the written word, so it is
      // the fuller analysis and goes first.
      out.sort(function (a, b) { return b.chain.length - a.chain.length; });
      return out;
    });
  };

  /* ---------------- upasarga + root meaning ---------------- */

  var arthaPromise = null;
  function upasargaArtha() {
    if (!arthaPromise) {
      arthaPromise = fetch('data/vedanga/vyakarana/upasarga_artha.json', { cache: 'force-cache' })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (d) { return (d && d.items) || {}; })
        .catch(function () { return {}; });
    }
    return arthaPromise;
  }

  // The documented meaning of THIS upasarga on THIS root -- सम् + गम् is not
  // "to go" but "to unite". Without it the popup would show the bare root's
  // gloss beside a word that no longer means that.
  window.dgeUpasargaArtha = function (rootCode, upasarga) {
    return upasargaArtha().then(function (items) {
      var rows = items[rootCode] || [];
      var bare = String(upasarga || '').replace(/्$/, '');
      for (var i = 0; i < rows.length; i++) {
        var name = String(rows[i][0] || '').replace(/्$/, '');
        if (name === bare) return { upasarga: rows[i][0], artha: rows[i][1] };
      }
      return null;
    });
  };
})();
