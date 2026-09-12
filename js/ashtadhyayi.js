/* ==========================================================================
 * DGE · Ashtadhyayi module  (additive, non-destructive)  v1.6.1
 *   v1.6.1 — admin/content/ashtadhyayi-layers.json: a site-wide, admin-level
 *            visibility gate on commentary layers and enrichment fields
 *            (distinct from each reader's own layer toggle), fetched fresh
 *            on every load. Ships with the ashtadhyayi.com English gloss
 *            field turned off (see dge/PENDING.md, 23 Aug) -- its data was
 *            also stripped from sutrapatha/data.json, not just hidden here.
 *   v1.2.0 — Stream 5: +Siddhānta-Kaumudī, +Mahābhāṣya, +Vasu(Eng) layers;
 *            padaccheda / anvaya / anuvṛtti / adhikāra / sūtra-type analysis panel.
 *   v1.2.1 — re-applied the shared DGEGemini client to askGemini() (Stream 5's
 *            delivery predated it and had reverted to a raw fetch call).
 *   v1.2.2 — aiLang now defaults from the main reader's onboarding language
 *            preference (dge_lang_pref) instead of always starting at "en".
 *   v1.3.0 — Siddhānta-Kaumudī reading-order navigation (partial, ~28%).
 *   v1.3.1 — resolveSkRefs(): "<{SK###}>" markers rendered as plain
 *            parenthetical citations (superseded by linkSkRefs in v1.5.0).
 *   v1.4.0 — full SK mapping (3961/3962, kaumudi_order v2): dual-order
 *            header (AK ‹› | कौमुदी ‹›), 70-prakarana drawer, LSK badge,
 *            jump box takes "sk 350"/"lsk 32".
 *   v1.5.0 — anuvritti/adhikara as tappable jumps + forward traces
 *            (governs-through / carried-into); SK self-citations
 *            (<{SK354}> raw markup) rendered as live कौमुदी links;
 *            corpus-usage search button; ✏️ sutra-correction report.
 *
 * Blended Read⇄Compare UI for the Paninian sutrapatha + commentary layers
 * (Kashika / Balamanorama / Tattvabodhini / Nyasa), with a REAL Gemini
 * (bring-your-own-key) tutor grounded on the open commentaries.
 *
 * Data source is pluggable:
 *   - if window.DGE_SAMPLE = {rows:[{id,sutra,kashika,balamanorama,...}]} is
 *     present (the self-contained preview), data is served from memory;
 *   - otherwise each layer is fetched lazily from
 *     data/vedanga/vyakarana/ashtadhyayi/<folder>/data.json  (sutrapatha eagerly).
 *
 * Preferences + Gemini key persist to localStorage on the real site; in
 * preview mode (window.DGE_INMEM) they live only in memory.
 * Reuses window.Sanscript for transliteration if present. Touches no other
 * DGE js/*.js logic.
 * ========================================================================== */
(function () {
  "use strict";
  // Page-relative to dge/vyakarana/ashtadhyayi.html (moved one directory
  // deeper than dge/ in the Phase 10 restructure -- ../ reaches dge/data/).
  var BASE = "../data/vedanga/vyakarana/ashtadhyayi/";
  var META = {
    kashika:      {t:"काशिकावृत्तिः", sub:"Kāśikā-vṛtti", who:"Vāmana–Jayāditya", tag:"var(--k)", role:"tika"},
    siddhanta_kaumudi:{t:"सिद्धान्तकौमुदी", sub:"Siddhānta-Kaumudī", who:"Bhaṭṭoji Dīkṣita", tag:"var(--sk)", role:"tika"},
    mahabhashya:  {t:"महाभाष्यम्", sub:"Mahā-bhāṣya", who:"Patañjali", tag:"var(--mb)", role:"bhashya",
                      path:"../data/vedanga/vyakarana/ashtadhyayi/mahabhashya_patanjali/data.json"},
    balamanorama: {t:"बालमनोरमा", sub:"Bāla-manoramā", who:"Vāsudeva Dīkṣita", tag:"var(--b)", role:"tippani"},
    tattvabodhini:{t:"तत्त्वबोधिनी", sub:"Tattva-bodhinī", who:"Jñānendra Sarasvatī", tag:"var(--t)", role:"tippani"},
    nyasa:        {t:"न्यासः", sub:"Kāśikāvivaraṇapañjikā", who:"Jinendrabuddhi", tag:"var(--n)", role:"tippani"},
    vasu:         {t:"Vasu · English", sub:"S.C. Vasu (1891)", who:"Śrīśa Chandra Vasu", tag:"var(--vs)", role:"translation", lang:"en",
                      path:"../data/vedanga/vyakarana/ashtadhyayi/vasu/data.json"},
    vasu_kaumudi: {t:"Vasu · SK English", sub:"S.C. Vasu, Siddhānta-Kaumudī tr. (1905-07)", who:"Śrīśa Chandra Vasu", tag:"var(--vs)", role:"translation", lang:"en",
                      path:"../data/vedanga/vyakarana/ashtadhyayi/vasu_kaumudi/data.json"}
  };
  var ORDER = ["kashika","siddhanta_kaumudi","mahabhashya","balamanorama","tattvabodhini","nyasa","vasu","vasu_kaumudi"];
  var INMEM = !!window.DGE_INMEM || !!window.DGE_SAMPLE;

  // Site-wide, admin-level gate on which commentary layers (and which
  // per-sutra enrichment fields, e.g. the removed ashtadhyayi.com English
  // gloss) are even offered to a reader at all -- see
  // admin/content/ashtadhyayi-layers.json's own _readme for why this is a
  // separate thing from state.enabled below (that one is each reader's own
  // preference among whichever layers THIS gate already approved). Fetched
  // fresh on every load, no caching, so an admin toggle takes effect for
  // every visitor without a code deploy. Defaults to "everything visible"
  // if the config can't be reached, so a fetch hiccup never silently hides
  // real content -- the config is a deny-list applied on top of ORDER, not
  // the thing that has to succeed for the reader to see anything.
  var siteVisibleFields = {};
  function loadLayerVisibility(){
    return fetchJSON("../admin/content/ashtadhyayi-layers.json?t=" + Date.now()).then(function(cfg){
      var layers = (cfg && cfg.layers) || {};
      ORDER = ORDER.filter(function(k){ return !(layers[k] && layers[k].visible === false); });
      siteVisibleFields = (cfg && cfg.fields) || {};
    }).catch(function(){ /* unreachable -- leave ORDER/siteVisibleFields at their defaults */ });
  }
  // Per-sutra enrichment field (not a layer/data.json), gated the same way.
  function fieldVisible(key){ return !(siteVisibleFields[key] && siteVisibleFields[key].visible === false); }

  var LS = {
    get: function(k, d){ try { if(INMEM) return (mem[k]!==undefined?mem[k]:d); var v=localStorage.getItem("dge.ash."+k); return v===null?d:JSON.parse(v);}catch(e){return d;} },
    set: function(k, v){ try { if(INMEM){mem[k]=v;return;} localStorage.setItem("dge.ash."+k, JSON.stringify(v)); }catch(e){} }
  };
  var mem = {};

  var state = {
    sutras: [], byId: {}, layers: {}, idx: 0,
    enabled: LS.get("enabled", {kashika:true, siddhanta_kaumudi:true, balamanorama:true, tattvabodhini:false, nyasa:false, mahabhashya:false, vasu:false, vasu_kaumudi:false}),
    script: LS.get("script", "devanagari"),
    mode: LS.get("mode", "read"),
    font: LS.get("font", 17),
    collapsed: {},
    // Siddhanta Kaumudi's reading order -- byId maps a sutra id to its
    // entry {kaumudiIndex, laghu?, chapter?} (kaumudi_order/data.json v2,
    // essentially complete: 3961 of 3962 sutras), list is those ids sorted
    // by kaumudiIndex, chapters the 70 traditional prakaranas.
    kaumudi: { byId: {}, list: [], chapters: [] },
    // id -> [ids] whose anuvritti names this sutra as a source; the forward
    // half of the anuvritti trace, inverted once at boot. adhikaraInto is
    // the same for adhikara headings: how far this sutra's rule governs.
    anuvrittiInto: {},
    adhikaraInto: {},
    navMode: LS.get("navMode", "ashtadhyayi")
  };

  function $(s, r){ return (r||document).querySelector(s); }
  function esc(s){ return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;"); }
  function devnum(n){ var m={0:"०",1:"१",2:"२",3:"३",4:"४",5:"५",6:"६",7:"७",8:"८",9:"९"};
    return String(n).split("").map(function(d){return m[d]||d;}).join(""); }
  function tl(t){ if(state.script==="devanagari"||!window.Sanscript) return t;
    try{ return window.Sanscript.t(t,"devanagari",state.script);}catch(e){return t;} }
  function iast(t){ try{ return window.Sanscript?window.Sanscript.t(t,"devanagari","iast"):"";}catch(e){return "";} }
  function fetchJSON(u){ return fetch(u).then(function(r){ if(!r.ok) throw new Error(u+" "+r.status); return r.json(); }); }

  /* ---------- data source ---------- */
  function loadSutrapatha(){
    if (window.DGE_SAMPLE){
      state.sutras = window.DGE_SAMPLE.rows.map(function(r){ return {id:r.id, sanskrit_text:r.sutra}; });
      state.sutras.forEach(function(it){ state.byId[it.id]=it; });
      // build all layers in memory
      ORDER.forEach(function(f){
        var L = state.layers[f] = {loaded:true, loading:false, byId:{}};
        window.DGE_SAMPLE.rows.forEach(function(r){ if(r[f]) L.byId[r.id]={id:r.id, sanskrit_text:r[f]}; });
      });
      return Promise.resolve();
    }
    return fetchJSON(BASE+"sutrapatha/data.json").then(function(d){
      state.sutras = d.items||[];
      state.sutras.forEach(function(it){ state.byId[it.id]=it; });
      // Invert anuvritti and adhikara once: which sutras carry THIS one's
      // words forward, and how far THIS sutra's adhikara governs.
      state.sutras.forEach(function(it){
        (it.anuvritti||[]).forEach(function(a){
          if(!a.from) return;
          (state.anuvrittiInto[a.from]=state.anuvrittiInto[a.from]||[]).push(it.id);
        });
        (it.adhikara_refs||[]).forEach(function(r){
          if(!r[1] || r[1]===it.id) return;
          (state.adhikaraInto[r[1]]=state.adhikaraInto[r[1]]||[]).push(it.id);
        });
      });
    });
  }
  // Non-fatal, fire-and-forget: a reader browsing in plain Ashtadhyayi
  // order (the default) never needs this file, and its own absence
  // shouldn't hold up the sutra that DID load.
  function loadKaumudiOrder(){
    return fetchJSON(BASE+"kaumudi_order/data.json").then(function(d){
      (d.items||[]).forEach(function(it){ state.kaumudi.byId[it.id]=it; });
      state.kaumudi.list = (d.items||[]).slice().sort(function(a,b){ return a.kaumudiIndex-b.kaumudiIndex; }).map(function(it){ return it.id; });
      state.kaumudi.chapters = d.chapters||[];
      renderHero();
    }).catch(function(){ /* fine without it */ });
  }
  function kaumudiOf(id){ return state.kaumudi.byId[id] || null; }
  function chapterOf(entry){
    if(!entry || !entry.chapter) return null;
    return state.kaumudi.chapters[entry.chapter-1] || null;
  }
  function ensureLayer(folder){
    var L = state.layers[folder];
    if (L && (L.loaded||L.loading)) return L.promise||Promise.resolve(L);
    L = state.layers[folder] = {loaded:false, loading:true, byId:{}};
    var url = (META[folder]&&META[folder].path) ? META[folder].path : BASE+folder+"/data.json";
    L.promise = fetchJSON(url).then(function(d){
      (d.items||[]).forEach(function(it){ L.byId[it.id]=it; });
      L.loaded=true; L.loading=false; return L;
    }).catch(function(e){ L.loading=false; L.error=e; return L; });
    return L.promise;
  }

  /* ---------- render ---------- */
  function renderHero(){
    var row = state.sutras[state.idx]; if(!row) return;
    var p = row.id.split(".");
    $("#dge-a").textContent = tl(devnum(p[0]));
    $("#dge-p").textContent = tl(devnum(p[1]));
    $("#dge-s").textContent = tl(devnum(p[2]));
    $("#dge-hnum").textContent = row.id;
    if(state.navMode==="kaumudi" && state.kaumudi.list.length){
      var kent = kaumudiOf(row.id);
      $("#dge-hpos").textContent = kent ? ("कौमुदी #"+kent.kaumudiIndex) : "कौमुद्यां नास्ति";
      $("#dge-htotal").textContent = state.kaumudi.list.length.toLocaleString();
    } else {
      $("#dge-hpos").textContent = "#"+(state.idx+1);
      $("#dge-htotal").textContent = state.sutras.length.toLocaleString();
    }
    renderDualNav(row);
    var kb=$("#dge-kaumudiBadge");
    if(kb){
      var ke = kaumudiOf(row.id);
      var kch = chapterOf(ke);
      var t = ke ? ("सिद्धान्तकौमुद्याम् #"+ke.kaumudiIndex
                    +(kch?(" · "+kch.name):"")
                    +(ke.laghu?(" · लघुकौमुद्याम् #"+ke.laghu):"")) : "";
      kb.textContent = t ? tl(t) : "";
      kb.style.display = t ? "" : "none";
    }
    var hs=$("#dge-hsutra"); hs.textContent=tl(row.sanskrit_text); hs.className="sutra "+(state.script==="iast"?"":"deva");
    $("#dge-hsutraIt").textContent = iast(row.sanskrit_text);
    var prevTxt, nextTxt;
    if(state.navMode==="kaumudi" && state.kaumudi.list.length){
      var kl=state.kaumudi.list, kpos2=kl.indexOf(row.id);
      var prevRow = kpos2>0 ? state.byId[kl[kpos2-1]] : (kpos2===-1 ? state.byId[kl[kl.length-1]] : null);
      var nextRow = (kpos2>=0 && kpos2<kl.length-1) ? state.byId[kl[kpos2+1]] : (kpos2===-1 ? state.byId[kl[0]] : null);
      prevTxt = prevRow ? tl(prevRow.sanskrit_text) : "—";
      nextTxt = nextRow ? tl(nextRow.sanskrit_text) : "—";
    } else {
      prevTxt = state.idx>0?tl(state.sutras[state.idx-1].sanskrit_text):"—";
      nextTxt = state.idx<state.sutras.length-1?tl(state.sutras[state.idx+1].sanskrit_text):"—";
    }
    $("#dge-prevT").textContent = prevTxt;
    $("#dge-nextT").textContent = nextTxt;
    $("#dge-prevTTop").textContent = prevTxt;
    $("#dge-nextTTop").textContent = nextTxt;
    renderAnalysis(row);
  }
  /* ---------- dual navigation: Ashtadhyayi order · Kaumudi order ---------- */
  // Two always-visible clusters, tapping a cluster's label makes that
  // order the one Previous/Next and the arrow keys follow. Replaces the
  // old single toggle button, which hid the Kaumudi position unless you
  // switched modes.
  // 24 Aug 2026: each cluster used to also carry its own dn-arrow prev/
  // next pair -- a real 3rd/4th stepping control, functionally parallel
  // to (not just a mode-switch for) #dge-prevBtnTop/#dge-nextBtnTop and
  // the bottom #dge-prevBtn/#dge-nextBtn, which already step whichever
  // order is active. Project lead's direct clutter report ("Kaumudi
  // navigation, Ashtadhyayi navigation... upper navigation, lot of
  // unwanted stuff") -- confirmed via investigation these were genuinely
  // redundant, not just visually busy: removed here, leaving only the
  // mode-switch labels + chapters button. Stepping itself is unaffected
  // (nav-top/nav call the same goNav()/go()/goKaumudi() this always did).
  function renderDualNav(row){
    var box=$("#dge-dualnav"); if(!box) return;
    var ke = kaumudiOf(row.id);
    var akOn = state.navMode!=="kaumudi", skOn = !akOn;
    box.innerHTML =
      '<span class="dn-cluster'+(akOn?' on':'')+'" data-order="ashtadhyayi">'
      +'<button class="dn-label" data-nav="ak-mode" title="browse in Ashtadhyayi order"><span class="deva">'+tl("अष्टाध्यायी")+'</span> '+esc(row.id)+'</button>'
      +'</span>'
      +'<span class="dn-cluster'+(skOn?' on':'')+(ke?'':' dn-none')+'" data-order="kaumudi">'
      +'<button class="dn-label" data-nav="sk-mode" title="browse in Siddhanta Kaumudi reading order"><span class="deva">'+tl("कौमुदी")+'</span> '+(ke?devnum(ke.kaumudiIndex):"—")+'</button>'
      +'</span>'
      +'<button class="dn-chapters" data-nav="chapters" title="Siddhanta Kaumudi prakarana list — topical index"><span class="deva">'+tl("प्रकरणानि")+'</span><span class="dn-gloss">· Topics</span> ☰</button>';
  }
  function setNavMode(m){
    state.navMode = m; LS.set("navMode", m);
    renderHero();
  }
  /* ---------- साहित्ये प्रयोगाः (corpus usages of this sutra) ---------- */
  // Built by tools/build_sutra_prayoga_index.py; sharded per adhyaya.
  // Entry: [slug, unit, kind(quote|ref), rank, snippet, title].
  var prayogaCache = {};
  var PRAYOGA_RANKS = ["सर्वमूलम्", "द्वैतवेदान्तग्रन्थाः", "दाससाहित्यम्", "अन्यग्रन्थाः"];
  function prettySlug(slug){
    var parts=slug.split("/");
    return parts.slice(-2).join(" › ").replace(/_/g," ");
  }
  function openPrayoga(){
    var row=state.sutras[state.idx]; if(!row) return;
    var m=$("#dge-prayogaModal"), body=$("#dge-prayogaBody"); if(!m||!body) return;
    var adhyaya=row.id.split(".")[0];
    body.innerHTML='<h4 class="deva">'+tl("साहित्ये प्रयोगाः")+' · '+esc(row.id)+'</h4><div class="an-empty">…</div>';
    m.classList.add("open"); $("#dge-backdrop").classList.add("open");
    var p = prayogaCache[adhyaya] ||
      (prayogaCache[adhyaya]=fetchJSON(BASE+"prayoga_index/a"+adhyaya+".json").catch(function(){ return {}; }));
    p.then(function(d){
      var ent=d[row.id];
      var h='<h4 class="deva">'+tl("साहित्ये प्रयोगाः")+' · '+esc(row.id)
        +' <span class="deva" style="font-weight:400;color:var(--muted)">'+esc(tl(row.sanskrit_text))+'</span></h4>';
      if(ent && ent.e && ent.e.length){
        h+='<div class="pry-count">'+ent.n+' usages across the library'
          +(ent.n>ent.e.length?' · showing the first '+ent.e.length:'')+'</div>';
        var byRank={};
        ent.e.forEach(function(e){ (byRank[e[3]]=byRank[e[3]]||[]).push(e); });
        [0,1,2,3].forEach(function(rk){
          var list=byRank[rk]; if(!list) return;
          h+='<div class="pry-grp deva">'+tl(PRAYOGA_RANKS[rk])+' <small>('+list.length+')</small></div>';
          list.forEach(function(e){
            var snip=esc(e[4]);
            var hl=esc(row.sanskrit_text.trim());
            if(hl && snip.indexOf(hl)!==-1) snip=snip.split(hl).join('<mark>'+hl+'</mark>');
            h+='<button class="pry-row" data-slug="'+esc(e[0])+'" data-unit="'+esc(e[1])+'">'
              +'<span class="pry-title deva">'+esc(e[5]||prettySlug(e[0]))
              +(e[2]==="ref"?' <span class="pry-kind">पा.सू.</span>':'')
              +'<span class="pry-unit">'+esc(e[1])+'</span></span>'
              +'<span class="pry-snip deva">'+snip+'</span>'
              +'</button>';
          });
        });
      } else {
        h+='<div class="an-empty">No indexed usages of this sutra in the library yet — '
          +'the index covers verbatim quotations and explicit पा.सू. citations '
          +'(rebuilt automatically as granthas are added).</div>';
      }
      h+='<button class="btn" id="dge-prayogaSearch" style="margin-top:12px">🔍 search the whole corpus live</button>';
      body.innerHTML=h;
    });
  }

  // ✏️ report a text error — the same [DGE-CONTENT-GAP] template
  // shabda.js/modals.js already emit, so the planned triage pipeline reads
  // one shape (Type/Surface/Context/Page/Timestamp). Renamed "Suggest a
  // correction" wherever it appears in UI (critique #20) rather than a bare
  // pencil icon reading as if the canonical text were casually editable.
  function reportCorrection(){
    var row=state.sutras[state.idx]; if(!row) return;
    var email=window.DGE_CONTACT_EMAIL||"sanatanavidyagurukulam@gmail.com";
    var subject=encodeURIComponent("[DGE-CONTENT-GAP] sutra-correction — "+row.id);
    var lines=["Type: sutra-correction","Surface: "+row.id,
      "Context: "+row.sanskrit_text,
      "Page: "+location.href.split("#")[0]+"#"+row.id,
      "Timestamp: "+new Date().toISOString(),
      "", "What is wrong (please describe, or paste the corrected text):", ""];
    location.href="mailto:"+email+"?subject="+subject+"&body="+encodeURIComponent(lines.join("\n"));
  }

  /* ---------- Kaumudi prakarana drawer ---------- */
  function openChapters(){
    var m=$("#dge-chaptersModal"); if(!m) return;
    var row=state.sutras[state.idx];
    var cur = kaumudiOf(row&&row.id);
    var curCh = cur && cur.chapter;
    var firstIdOf = {};
    // items are sorted by kaumudiIndex, so the first id seen per chapter is
    // that prakarana's opening sutra.
    state.kaumudi.list.forEach(function(id){
      var e=state.kaumudi.byId[id];
      if(e && e.chapter && firstIdOf[e.chapter]===undefined) firstIdOf[e.chapter]=id;
    });
    var h='<h4 class="deva">'+tl("सिद्धान्तकौमुदी — प्रकरणानि")+'</h4><div class="chp-list">';
    state.kaumudi.chapters.forEach(function(c){
      if(!c.count) return;
      h+='<button class="chp-row'+(c.n===curCh?' on':'')+'" data-ch="'+c.n+'" data-first="'+esc(firstIdOf[c.n]||"")+'">'
        +'<span class="chp-n">'+devnum(c.n)+'</span>'
        +'<span class="chp-name deva">'+tl(c.name)+'</span>'
        +'<span class="chp-range">'+devnum(c.from)+'–'+devnum(c.to)+'</span>'
        +'</button>';
    });
    h+='</div>';
    $("#dge-chaptersBody").innerHTML=h;
    m.classList.add("open"); $("#dge-backdrop").classList.add("open");
    var on=m.querySelector(".chp-row.on"); if(on) on.scrollIntoView({block:"center"});
  }
  /* ---------- padaccheda / anvaya / anuvritti (sutra analysis) ---------- */
  function renderAnalysis(row){
    var strip=$("#dge-sutrameta"), panel=$("#dge-analysis");
    if(!strip||!panel) return;
    var devCls = state.script==="iast"?"":"deva";
    // always-visible compact strip: padaccheda words + type badge
    var s="";
    if(row.padaccheda&&row.padaccheda.length){
      s+='<span class="pc-lbl">पदच्छेद</span> '+row.padaccheda.map(function(w){
        return '<span class="pc-w '+devCls+'">'+esc(tl(w))+'</span>'; }).join('<span class="pc-plus">+</span>');
    }
    if(row.sutra_type&&(row.sutra_type.label_dev||row.sutra_type.label)){
      s+='<span class="pc-type" title="'+esc(row.sutra_type.label||"")+'">'
        +(row.sutra_type.label_dev?'<span class="deva">'+esc(row.sutra_type.label_dev)+'</span> ':'')
        +esc(row.sutra_type.label||"")+'</span>';
    }
    strip.innerHTML=s;
    // toggle panel: anvaya, anuvritti (backward + forward), adhikara, English
    var rows="";
    if(row.anvaya) rows+=arow("अन्वयः · anvaya (prose order)", '<span class="'+devCls+'">'+esc(tl(row.anvaya))+'</span>');
    if(row.anuvritti&&row.anuvritti.length){
      var av=row.anuvritti.map(function(a){
        return '<span class="anu-w '+devCls+'">'+esc(tl(a.word))+'</span>'
          +(a.from?'<button class="anu-src an-ref" data-id="'+esc(a.from)+'" title="open the sutra these words carry over from">‹ '+a.from+'</button>':''); }).join(", ");
      rows+=arow("अनुवृत्तिः · anuvṛtti (carried-over words)", av);
    }
    // The inverse trace: which later sutras inherit THIS sutra's words.
    // Computed once at boot from the same anuvritti data (see boot()).
    var fwd = state.anuvrittiInto[row.id];
    if(fwd && fwd.length){
      var span = fwd.length<=4
        ? fwd.map(function(id){ return '<button class="an-ref" data-id="'+esc(id)+'">'+id+'</button>'; }).join(", ")
        : '<button class="an-ref" data-id="'+esc(fwd[0])+'">'+fwd[0]+'</button> … '
          +'<button class="an-ref" data-id="'+esc(fwd[fwd.length-1])+'">'+fwd[fwd.length-1]+'</button>'
          +' <span class="anu-cnt">('+fwd.length+' sūtras)</span>';
      rows+=arow("अनुवर्तते · carried forward into", span);
    }
    // This sutra as an adhikara head: the span of sutras it governs.
    var gov = state.adhikaraInto[row.id];
    if(gov && gov.length){
      var gspan = '<button class="an-ref" data-id="'+esc(gov[0])+'">'+gov[0]+'</button> … '
        +'<button class="an-ref" data-id="'+esc(gov[gov.length-1])+'">'+gov[gov.length-1]+'</button>'
        +' <span class="anu-cnt">('+gov.length+' sūtras)</span>';
      rows+=arow("अधिकारविस्तारः · governs through", gspan);
    }
    if(row.adhikara_refs&&row.adhikara_refs.length){
      var ad=row.adhikara_refs.map(function(r){
        var t='<span class="'+devCls+'">'+esc(tl(r[0]))+'</span>';
        return r[1] ? '<span class="adhi-item">'+t+'<button class="anu-src an-ref" data-id="'+esc(r[1])+'" title="open the sutra where this adhikara begins">‹ '+r[1]+'</button></span>' : t;
      }).join(" · ");
      rows+=arow("अधिकारः · adhikāra (governing rule)", ad);
    } else if(row.adhikara){
      rows+=arow("अधिकारः · adhikāra (governing rule)", '<span class="'+devCls+'">'+esc(tl(row.adhikara))+'</span>');
    }
    if(row.english && fieldVisible("english")) rows+=arow("English gloss", esc(row.english));
    panel.innerHTML=rows||'<div class="an-empty">No structured analysis on record for this sūtra.</div>';
    var hasStrip=!!s, hasPanel=!!rows;
    $("#dge-pcBtn").style.display=(hasStrip||hasPanel)?"":"none";
  }
  function arow(label, val){ return '<div class="an-row"><div class="an-k">'+label+'</div><div class="an-v">'+val+'</div></div>'; }
  function nl2br(s){ return s.replace(/\n/g,"<br>"); }
  // The Siddhanta-Kaumudi text cites itself as raw <{SK354}> markers (and
  // Unadi as <{उ...}>) — 748 sutras' worth rendered as literal markup
  // until now. With the full SK mapping in hand they become live jumps:
  // कौमुदी-३५४ opens the sutra holding that Kaumudi position. Runs on the
  // ALREADY-ESCAPED text, so the pattern matches &lt;{SK354}&gt;.
  function idByKaumudi(n){
    for(var i=0;i<state.kaumudi.list.length;i++){
      var id=state.kaumudi.list[i];
      if(state.kaumudi.byId[id].kaumudiIndex===n) return id;
    }
    return null;
  }
  // Four more leaked machine-tagging markers alongside the SK-ref one above,
  // found by diffing this file's text against the source repo's own clean
  // base file (github.com/drdhaval2785/siddhantakaumudi, sk0.txt) -- same
  // bug, different delimiter punctuation, so it slipped past the earlier
  // fix. drdhaval2785's own readme documents "{$ {!verbnum verb!}+
  // verbmeaning$}" as his pipeline's internal tagging syntax for dhatu
  // (verbal root) citations, mechanically added by his step1.py when
  // producing the tagged sk1.txt from clean sk0.txt; this corpus's import
  // evidently pulled from that tagged file and never stripped the tags --
  // confirmed against sk0.txt directly, where the same passage reads plain
  // running text with no braces/dollar-signs/bangs. `<<...>>` (quoting
  // another sutra's headword, paired with an already-handled SK-ref number)
  // and `<!...!>` (marking a vartika, paired with a following
  // "(वार्तिकम्)") are this repo's own wrapper conventions for the same
  // underlying content, likewise never resolved at render time; `<ऽ...ऽ>`
  // (one occurrence, item 4.1.1) is normalized to this corpus's own
  // existing bracket convention for a quoted paribhasha (see item 1.1.50's
  // "[(परिभाषा - ) ...]"). Runs on the already-escaped text, like the SK
  // regexes below, except the two brace ones which contain no `<`/`&`.
  function stripLeakedMarkup(text){
    return text
      .replace(/\{!([^{}]*)!\}/g, '$1')
      .replace(/\{\$([\s\S]*?)\$\}/g, '$1')
      .replace(/&lt;!([\s\S]*?)!>/g, '$1')
      .replace(/&lt;&lt;([\s\S]*?)>>/g, '$1')
      .replace(/&lt;ऽ([\s\S]*?)ऽ>/g, '[(परिभाषा - )$1]');
  }
  function linkSkRefs(escaped){
    return stripLeakedMarkup(escaped)
      .replace(/&lt;\{SK(\d+)\}(?:&gt;|>)/g, function(_, n){
        var target=idByKaumudi(+n);
        return target
          ? '<button class="sk-ref" data-goto="'+esc(target)+'" title="सिद्धान्तकौमुद्याम् #'+n+' — '+esc(target)+'">कौमुदी-'+devnum(n)+'</button>'
          : '<span class="sk-ref sk-ref-plain">कौमुदी-'+devnum(n)+'</span>';
      })
      .replace(/&lt;\{(उ[^}]*)\}(?:&gt;|>)/g, '<span class="sk-ref sk-ref-plain">$1</span>')
      .replace(/&lt;\{([^}]*)\}(?:&gt;|>)/g, '$1');
  }
  function cardHTML(folder){
    var m=META[folder], row=state.sutras[state.idx], L=state.layers[folder];
    var isEn = m.lang==="en";
    var devCls = isEn ? "" : (state.script==="iast"?"":"deva");
    var col = (state.mode==="compare")?false:!!state.collapsed[folder];
    var body, hasText=false;
    if(!L||(!L.loaded&&L.loading)) body='<span class="dge-skel"></span><span class="dge-skel"></span><span class="dge-skel" style="width:70%"></span>';
    else if(L&&L.error) body='<span class="dge-more">could not load '+folder+'</span>';
    else { var it=L&&L.byId[row.id];
      if(it){ body=linkSkRefs(nl2br(esc(isEn ? it.sanskrit_text : tl(it.sanskrit_text)))); hasText=true; }
      else body='<span class="dge-more">— no '+m.sub+' on this sutra —</span>'; }
    var lic = (L&&L.byId[row.id])?('layer: '+m.sub+' · '+m.role+' · ref → sutrapatha/'+row.id):'';
    return '<article class="dge-card '+(col?'collapsed':'')+'" data-c="'+folder+'" style="--tag:'+m.tag+'">'
      +'<div class="dge-head" data-h="'+folder+'">'
      +'<span class="t '+(isEn?"":(state.script==="iast"?"":"deva"))+'">'+(isEn?m.t:tl(m.t))+'</span>'
      +'<span class="sub">'+m.sub+'</span><span class="who">'+m.who+'</span>'
      +(hasText?'<button class="dge-copy" data-copy="'+folder+'" title="Copy '+m.sub+' text" aria-label="Copy '+m.sub+' text">⧉</button>':'')
      +'<button class="dge-kebab" data-kebab="'+folder+'" title="More actions for '+m.sub+'" aria-label="More actions for '+m.sub+'">⋮</button>'
      +'<span class="caret">▾</span></div>'
      +'<div class="dge-body" style="font-size:'+state.font+'px">'
      +'<div class="'+devCls+'">'+body+'</div>'
      +(lic?'<span class="dge-lic">'+lic+'</span>':'')+'</div></article>';
  }
  function renderLayers(){
    var box=$("#dge-layers"); box.className="dge-layers "+state.mode;
    var active=ORDER.filter(function(k){return state.enabled[k];});
    if(!active.length){ box.innerHTML='<div class="dge-empty">No layers selected — tap a chip above.</div>'; return; }
    box.innerHTML=active.map(cardHTML).join("");
    // Kashika/Siddhanta-Kaumudi/etc. text cites other sutras constantly
    // ("कण्ड्वादिभ्यो यक् ३।१।२७"), and intellisense.js already knows how
    // to turn those into tappable links with a popover — it was just never
    // asked to scan this page's cards, so every citation rendered as inert
    // text no matter how many the commentary named.
    if (typeof window.dgeScanForEntities === 'function') {
      try { window.dgeScanForEntities(box); } catch (e) {}
    }
    if (typeof window.dgeScanForSutras === 'function') {
      try { window.dgeScanForSutras(box); } catch (e) {}
    }
    box.querySelectorAll(".dge-head").forEach(function(h){
      h.addEventListener("click",function(e){
        if(e.target.closest(".dge-copy,.dge-kebab")) return;
        if(state.mode==="compare") return;
        var k=h.dataset.h; state.collapsed[k]=!state.collapsed[k]; h.parentElement.classList.toggle("collapsed");
      });
    });
    box.querySelectorAll(".dge-copy").forEach(function(b){
      b.addEventListener("click",function(e){
        e.stopPropagation();
        var f=b.dataset.copy, L=state.layers[f], it=L&&L.byId[state.sutras[state.idx].id];
        if(it&&navigator.clipboard){ navigator.clipboard.writeText(it.sanskrit_text); b.textContent="✓"; setTimeout(function(){b.textContent="⧉";},900); }
      });
    });
    // Commentary contextual menu (critique #10's per-object-type interaction
    // model, applied to "tap a commentary"): About/Copy citation/Find
    // citations/Ask DGE AI, registered via the taxonomy-override mechanism
    // at boot (see registerContextualOverrides below) rather than
    // duplicating contextual-actions.js's own base 'commentary' actions,
    // whose handlers assume dge/index.html's shloka-card shape and don't
    // apply to this page's dge-card layers.
    box.querySelectorAll(".dge-kebab").forEach(function(b){
      b.addEventListener("click",function(e){
        e.stopPropagation();
        var folder=b.dataset.kebab, m=META[folder], row=state.sutras[state.idx];
        if(typeof window.dgeOpenContextualMenu!=="function"||!m||!row) return;
        window.dgeOpenContextualMenu("commentary",{
          folder:folder, sutraId:row.id, label:(m.lang==="en"?m.t:tl(m.t))+" · "+m.sub,
          granthaSlug:"vedanga/vyakarana/ashtadhyayi"
        });
      });
    });
  }
  function renderAll(){ renderHero(); renderLayers(); renderCommentaryNavigator(); }
  // ---- Commentary Navigator (DGE_UI_CONTRACT.md #2) ----------------------
  // Replaces the old flat .dge-chips pill row + "green=loaded from your
  // data / dashed=pending" legend, which exposed this app's own loading
  // implementation to the reader (critique #4) and conflated "available"
  // with "displayed" (critique #2) in one row of same-shaped pills
  // (critique #22). This renders a labeled list: a toggle dot per row
  // (filled=displayed, hollow=available-not-displayed, dashed=loading) plus
  // a plain-language summary line above it -- "5 of 7 commentaries shown"
  // instead of a color-key legend.
  function commentaryStatus(folder){
    var L=state.layers[folder];
    if(!L) return "not loaded";
    if(L.loading) return "loading…";
    if(L.error) return "could not load";
    var row=state.sutras[state.idx];
    return (row && L.byId[row.id]) ? "" : "no text on this sūtra";
  }
  function renderCommentaryNavigator(){
    var sum=$("#dge-cnSummary"), list=$("#dge-cnList");
    if(!sum||!list) return;
    var shown=ORDER.filter(function(k){return state.enabled[k];}).length;
    sum.innerHTML='<span><b>'+shown+' of '+ORDER.length+'</b> commentaries shown</span>'
      +'<span class="cn-tools"><button type="button" data-cn-action="expand" title="Expand every open commentary">⤢ Expand</button>'
      +'<button type="button" data-cn-action="collapse" title="Collapse every open commentary">⤡ Collapse</button></span>';
    list.innerHTML=ORDER.map(function(k){
      var m=META[k], L=state.layers[k], on=!!state.enabled[k];
      var pending=on&&L&&L.loading;
      var status=on?commentaryStatus(k):"tap to show";
      return '<button type="button" class="cn-row'+(on?' displayed':'')+(pending?' pending':'')+'" '
        +'role="listitem" data-c="'+k+'" aria-pressed="'+(on?'true':'false')+'" '
        +'aria-label="'+(on?'Hide ':'Show ')+esc(m.sub)+'">'
        +'<span class="cn-dot" aria-hidden="true"></span>'
        +'<span class="cn-label"><span class="t '+(state.script==="iast"?"":"deva")+'">'+(m.lang==="en"?m.t:tl(m.t))+'</span>'
        +'<span class="sub">'+esc(m.sub)+' · '+esc(m.who)+'</span></span>'
        +'<span class="cn-status">'+esc(status)+'</span>'
        +'</button>';
    }).join("");
  }
  function go(i){ if(i<0||i>=state.sutras.length) return; state.idx=i; renderAll(); window.scrollTo({top:0,behavior:"smooth"}); }
  // Steps through state.kaumudi.list (only the sutras with a confirmed
  // Kaumudi position) rather than state.sutras -- "next" here means "next
  // in Kaumudi's own reading order", which is not the same sutra state.idx+1
  // would give. Landing on a sutra with no confirmed position (most of
  // them) and pressing this jumps to the nearest end of the known list
  // rather than silently doing nothing.
  function goKaumudi(dir){
    var list=state.kaumudi.list; if(!list.length) return;
    var row=state.sutras[state.idx];
    var pos=row?list.indexOf(row.id):-1;
    var target;
    if(pos===-1) target = dir>0 ? list[0] : list[list.length-1];
    else { var ni=pos+dir; if(ni<0||ni>=list.length) return; target=list[ni]; }
    var it=state.byId[target]; if(!it) return;
    go(state.sutras.indexOf(it));
  }
  function goNav(dir){ if(state.navMode==="kaumudi") goKaumudi(dir); else go(state.idx+dir); }

  /* ---------- Gemini (BYOK) ---------- */
  function getKey(){ return LS.get("gkey",""); }
  function setKey(k){ LS.set("gkey",k); }
  // The default and the menu both come from js/gemini.js, which is the one
  // place model ids live. A model saved by an older build (this page used to
  // offer gemini-2.0-flash and friends, all of which now 404) is not honoured
  // -- it would fail every request with no way for the reader to tell why.
  function models(){
    var G = window.DGEGemini;
    return (G && G.MODELS && G.MODELS.length) ? G.MODELS
         : [{ id: "gemini-flash-latest", label: "Flash — fast, recommended" }];
  }
  function defaultModel(){
    var G = window.DGEGemini;
    return (G && G.DEFAULT_MODEL) || "gemini-flash-latest";
  }
  function getModel(){
    var m = LS.get("gmodel", "");
    var list = models();
    for (var i = 0; i < list.length; i++) if (list[i].id === m) return m;
    return defaultModel();
  }
  function fillModelSel(){
    var sel = $("#dge-modelSel"); if(!sel) return;
    var list = models();
    sel.innerHTML = "";
    list.forEach(function(m){
      var o = document.createElement("option");
      o.value = m.id; o.textContent = m.label || m.id;
      sel.appendChild(o);
    });
  }
  function buildPrompt(question, lang){
    var row=state.sutras[state.idx];
    var open=ORDER.filter(function(k){return state.enabled[k]&&state.layers[k]&&state.layers[k].byId[row.id];});
    var ctx=open.map(function(k){ return "### "+META[k].sub+" ("+META[k].who+")\n"+state.layers[k].byId[row.id].sanskrit_text; }).join("\n\n");
    if(!ctx) ctx="(no commentary layers are currently open)";
    var langLine={en:"Answer in clear English.",kn:"Answer in Kannada (ಕನ್ನಡ).",sa:"Answer in simple Sanskrit (संस्कृतम्)."}[lang]||"Answer in clear English.";
    return [
      "You are a precise Pāṇinian-grammar tutor for the sutra "+row.id+": “"+row.sanskrit_text+"”.",
      "Use ONLY the commentary passages below as your source. If they do not answer the question, say so plainly — do not invent.",
      "When you make a claim, quote the short Sanskrit phrase you rely on. Be concise and pedagogical.",
      langLine,
      "",
      "=== OPEN COMMENTARIES ===",
      ctx,
      "",
      "=== QUESTION ===",
      question
    ].join("\n");
  }
  function askGemini(prompt){
    var key=getKey(); if(!key) return Promise.reject(new Error("NO_KEY"));
    // Delegates network + error classification to the shared window.DGEGemini
    // client (js/gemini.js) so quota/permission/model errors read as plain
    // English with an actual next step instead of a raw API error dump, and
    // a quota/overload/missing-model failure gets one automatic retry on a
    // lighter model before giving up. Key/model still come from THIS page's
    // own LS wrapper (JSON-encoded under "dge.ash.*"), passed as per-call
    // overrides -- DGEGemini's own localStorage lookup is never used here.
    return window.DGEGemini.generate({
      prompt: prompt, apiKey: key, model: getModel(),
      generationConfig: { temperature: 0.3, maxOutputTokens: 800 }
    }).then(function(r){
      if(!r.ok) throw new Error(r.error.title+" — "+r.error.message+" "+r.error.action);
      var text = r.text || "(empty response)";
      return r.fellBack ? ("["+r.notice+"]\n\n"+text) : text;
    });
  }
  // Defaults to the language chosen in the main reader's onboarding popup
  // (dge/js/onboarding.js) so a visitor doesn't have to re-pick it here;
  // still freely overridable via the buttons below, which is why this is
  // only an initial value, not re-read on every question.
  var aiLang=(function(){
    var v; try{ v=localStorage.getItem("dge_lang_pref"); }catch(e){ v=null; }
    return (v==="kn"||v==="sa") ? v : "en";
  })();
  function runAI(question){
    var out=$("#dge-aiAns");
    out.className="dge-ans"; out.textContent="Thinking…";
    if(!getKey()){ out.innerHTML='No Gemini key yet. <a href="#" id="dge-openkey">Add your API key</a> (stored only in your browser). Get one free at aistudio.google.com/apikey.';
      var lk=$("#dge-openkey"); if(lk) lk.addEventListener("click",function(e){e.preventDefault();openSettings();}); return; }
    askGemini(buildPrompt(question,aiLang)).then(function(txt){
      out.className="dge-ans "+(aiLang==="en"?"":"deva"); out.textContent=txt;
    }).catch(function(e){
      out.className="dge-ans";
      out.textContent = e.message==="NO_KEY" ? "Add your Gemini key in settings." : ("Gemini error: "+e.message);
    });
  }

  /* ---------- settings modal ---------- */
  function openSettings(){ var m=$("#dge-settings"); if(m){ fillModelSel(); $("#dge-keyInput").value=getKey(); $("#dge-modelSel").value=getModel(); m.classList.add("open"); $("#dge-backdrop").classList.add("open"); } }
  function closeAll(){ $("#dge-drawer").classList.remove("open"); var s=$("#dge-settings"); if(s)s.classList.remove("open"); var c=$("#dge-chaptersModal"); if(c)c.classList.remove("open"); var pmm=$("#dge-prayogaModal"); if(pmm)pmm.classList.remove("open"); var mn=$("#dge-menuDrawer"); if(mn)mn.classList.remove("open"); $("#dge-backdrop").classList.remove("open"); }

  /* ---------- wire ---------- */
  // The sticky header wraps onto 2-3 rows on a narrow phone (its many
  // script/mode/font buttons), so its height ranges from ~59px on desktop
  // to ~190px on a small phone — a fixed CSS offset for .nav-top left it
  // either floating with a gap or hidden half under the header depending on
  // viewport. Measured and kept in sync instead.
  function syncHeaderOffset(){
    var h = $("header"); if(!h) return;
    document.documentElement.style.setProperty("--dge-header-h", h.getBoundingClientRect().height+"px");
  }

  function wire(){
    syncHeaderOffset();
    window.addEventListener("resize", syncHeaderOffset);
    // Commentary Navigator: tap a row to toggle it displayed/hidden (the
    // dge-chips flat pill row's old job, see renderCommentaryNavigator).
    var cnList=$("#dge-cnList");
    if(cnList) cnList.addEventListener("click",function(e){
      var row=e.target.closest(".cn-row"); if(!row) return;
      var k=row.dataset.c; state.enabled[k]=!state.enabled[k]; LS.set("enabled",state.enabled);
      renderCommentaryNavigator();
      if(state.enabled[k]){ renderLayers(); ensureLayer(k).then(function(){ renderLayers(); renderCommentaryNavigator(); }); }
      else renderLayers();
    });
    // Expand-all/Collapse-all: one shared handler for both homes critique #5
    // asks for -- the ☰ menu drawer's "Commentaries" section, and the tiny
    // affordance next to the navigator's own summary line -- rather than two
    // separate implementations of the same action.
    document.addEventListener("click",function(e){
      var b=e.target.closest("[data-cn-action]"); if(!b) return;
      if(b.dataset.cnAction==="expand"){ ORDER.forEach(function(k){state.collapsed[k]=false;}); renderLayers(); }
      else if(b.dataset.cnAction==="collapse" && state.mode!=="compare"){ ORDER.forEach(function(k){state.collapsed[k]=true;}); renderLayers(); }
    });
    $("#dge-modeSeg").addEventListener("click",function(e){ var b=e.target.closest("button"); if(!b)return;
      [].forEach.call(e.currentTarget.children,function(x){x.classList.remove("on");}); b.classList.add("on");
      state.mode=b.dataset.m; LS.set("mode",state.mode); renderLayers(); });
    $("#dge-scriptSeg").addEventListener("click",function(e){ var b=e.target.closest("button"); if(!b)return;
      [].forEach.call(e.currentTarget.children,function(x){x.classList.remove("on");}); b.classList.add("on");
      state.script=b.dataset.s; LS.set("script",state.script); renderAll(); });
    $("#dge-themeBtn").addEventListener("click",function(){ var d=document.body.classList.toggle("dark"); LS.set("dark",d); });
    $("#dge-fontUp").addEventListener("click",function(){ state.font=Math.min(26,state.font+1); LS.set("font",state.font); renderLayers(); });
    $("#dge-fontDn").addEventListener("click",function(){ state.font=Math.max(13,state.font-1); LS.set("font",state.font); renderLayers(); });
    $("#dge-prevBtn").addEventListener("click",function(){ goNav(-1); });
    $("#dge-nextBtn").addEventListener("click",function(){ goNav(1); });
    $("#dge-prevBtnTop").addEventListener("click",function(){ goNav(-1); });
    $("#dge-nextBtnTop").addEventListener("click",function(){ goNav(1); });
    var dn=$("#dge-dualnav");
    if(dn) dn.addEventListener("click",function(e){
      var b=e.target.closest("[data-nav]"); if(!b) return;
      switch(b.dataset.nav){
        case "ak-mode": setNavMode("ashtadhyayi"); break;
        case "sk-mode": setNavMode("kaumudi"); break;
        case "chapters": openChapters(); break;
      }
    });
    var chm=$("#dge-chaptersModal");
    if(chm) chm.addEventListener("click",function(e){
      if(e.target.id==="dge-chaptersClose"){ closeAll(); return; }
      var r=e.target.closest(".chp-row"); if(!r) return;
      var id=r.dataset.first;
      if(id && state.byId[id]){
        closeAll();
        if(state.navMode!=="kaumudi") setNavMode("kaumudi");
        go(state.sutras.indexOf(state.byId[id]));
      }
    });
    var pc=$("#dge-pcBtn"); if(pc) pc.addEventListener("click",function(){
      var pn=$("#dge-analysis"); if(!pn) return;
      var open=pn.classList.toggle("open"); pc.classList.toggle("on",open); });
    // Anuvritti / adhikara source references in the analysis panel jump to
    // the sutra they name. The panel is re-rendered per sutra, so delegate.
    var an=$("#dge-analysis"); if(an) an.addEventListener("click",function(e){
      var b=e.target.closest(".an-ref"); if(!b) return;
      var id=b.dataset.id;
      if(id && state.byId[id]){ $("#dge-analysis").classList.add("open"); go(state.sutras.indexOf(state.byId[id])); }
    });
    // Kaumudi self-citations inside the SK layer's text (linkSkRefs).
    var lay=$("#dge-layers"); if(lay) lay.addEventListener("click",function(e){
      var b=e.target.closest(".sk-ref[data-goto]"); if(!b) return;
      var id=b.dataset.goto;
      if(state.byId[id]) go(state.sutras.indexOf(state.byId[id]));
    });
    // "What explains this sutra" / corpus usage / suggest-a-correction used
    // to be three separate always-visible buttons in .heroactions, crowding
    // the sūtra before a reader reaches any commentary (critique #1/#18).
    // They're real, distinct capabilities, not duplicates of each other, so
    // per critique #10's per-object-type interaction model they now live
    // together in one sūtra contextual menu (⋯ More), registered as a
    // taxonomy override alongside the commentary one below.
    var more=$("#dge-sutraMoreBtn"); if(more) more.addEventListener("click",function(){
      var row=state.sutras[state.idx];
      if(typeof window.dgeOpenContextualMenu!=="function"||!row) return;
      window.dgeOpenContextualMenu("sutra",{sutraId:row.id,label:row.id,granthaSlug:"vedanga/vyakarana/ashtadhyayi"});
    });
    var pm=$("#dge-prayogaModal");
    if(pm) pm.addEventListener("click",function(e){
      if(e.target.id==="dge-prayogaClose"){ closeAll(); return; }
      if(e.target.id==="dge-prayogaSearch"){
        closeAll();
        var row=state.sutras[state.idx];
        if(row && window.DGEGlobalSearch && window.DGEGlobalSearch.open) window.DGEGlobalSearch.open(row.sanskrit_text);
        return;
      }
      var r=e.target.closest(".pry-row"); if(!r) return;
      var unit=(r.dataset.unit||"").split("#")[0];
      location.href="index.html?path="+encodeURIComponent(r.dataset.slug)
        +(unit?("&jumpVedicId="+encodeURIComponent(unit)):"");
    });
    // Jump box. It used to accept an exact "1.1.1" and nothing else, and to
    // do nothing at all -- no message, no shake -- for anything it did not
    // recognise, which reads as a dead control rather than a rejected input.
    // Now any separator works (1-1-1, 1 1 1, 1,1,1), a partial reference goes
    // to the start of that adhyaya or pada, and a miss says so.
    var jump=$("#dge-jump");
    // Devanagari digits are typed here too (the datalist is in Devanagari on
    // some keyboards); normalize both directions once.
    function asciiDigits(s){ return s.replace(/[\u0966-\u096f]/g,function(d){ return "\u0966\u0967\u0968\u0969\u096a\u096b\u096c\u096d\u096e\u096f".indexOf(d); }); }
    function findSutraMatch(raw){
      raw=asciiDigits((raw||"").trim());
      if(!raw) return null;
      // "sk 350" / "k350" / "\u0915 \u0969\u096b\u0966" / "\u0915\u094c\u092e\u0941\u0926\u0940 350" jumps by Siddhanta
      // Kaumudi position; "lsk 32"/"\u0932\u0918\u0941 32" by Laghu-Kaumudi position.
      var m=raw.match(/^(?:lsk|\u0932\u0918\u0941(?:\u0915\u094c\u092e\u0941\u0926\u0940)?)\s*[\.\-#]?\s*(\d{1,4})$/i);
      if(m){
        var ln=+m[1];
        for(var li=0;li<state.kaumudi.list.length;li++){
          var le=state.kaumudi.byId[state.kaumudi.list[li]];
          if(le && le.laghu===ln) return state.byId[state.kaumudi.list[li]];
        }
        return null;
      }
      m=raw.match(/^(?:sk|k|\u0915|\u0915\u094c\u092e\u0941\u0926\u0940)\s*[\.\-#]?\s*(\d{1,4})$/i);
      if(m){
        var kn=+m[1];
        for(var ki=0;ki<state.kaumudi.list.length;ki++){
          var keid=state.kaumudi.list[ki];
          if(state.kaumudi.byId[keid].kaumudiIndex===kn) return state.byId[keid];
        }
        return null;
      }
      var parts=raw.replace(/[\s,\-\u2013\u2014\u0964|]+/g,".").split(".").filter(Boolean);
      var bad=parts.some(function(x){ return !/^\d+$/.test(x); });
      if(bad||!parts.length) return null;
      var id=parts.join(".");
      if(state.byId[id]) return state.byId[id];
      // a prefix: first sutra of that adhyaya (1) or pada (1.1) -- but ONLY
      // if what's typed so far can't still become a longer valid id (e.g.
      // typing "1" toward "10" shouldn't jump to adhyaya 1's first sutra
      // and have that value fight the next keystroke; typing "1." toward
      // "1.1.1" is unambiguous, since a trailing separator means the
      // segment just typed is deliberately finished).
      if(!/[.\s,\-\u2013\u2014\u0964|]$/.test(raw)) return null;
      var pre=id+".";
      for(var i=0;i<state.sutras.length;i++){
        if(state.sutras[i].id.indexOf(pre)===0) return state.sutras[i];
      }
      return null;
    }
    function jumpTo(){
      var raw=(jump.value||"").trim();
      if(!raw) return;
      var hit=findSutraMatch(raw);
      if(hit){ jump.classList.remove("miss"); jump.value=hit.id; go(state.sutras.indexOf(hit)); }
      else { jump.classList.add("miss"); jump.title="No sutra "+raw; setTimeout(function(){ jump.classList.remove("miss"); },1200); }
    }
    if(jump){
      jump.addEventListener("change",jumpTo);
      // change alone does not fire when someone retypes the same reference
      jump.addEventListener("keydown",function(e){ if(e.key==="Enter"){ e.preventDefault(); jumpTo(); } });
      // Live navigation as a complete reference is typed, not only on
      // Enter/blur -- deliberately does NOT rewrite jump.value or flag
      // ".miss" the way explicit jumpTo() does: while still typing, "no
      // match yet" is normal, not an error, and normalizing the box's text
      // mid-keystroke would fight whatever the reader types next.
      var jumpDebounce = null;
      jump.addEventListener("input",function(){
        clearTimeout(jumpDebounce);
        jumpDebounce = setTimeout(function(){
          var hit=findSutraMatch(jump.value);
          if(hit) go(state.sutras.indexOf(hit));
        }, 220);
      });
    }
    document.addEventListener("keydown",function(e){
      if(/INPUT|TEXTAREA/.test((e.target.tagName||""))) return;
      if(e.key==="ArrowRight") goNav(1);
      else if(e.key==="ArrowLeft") goNav(-1);
    });
    // AI
    $("#dge-aiBtn").addEventListener("click",function(){ $("#dge-drawer").classList.add("open"); $("#dge-backdrop").classList.add("open"); });
    $("#dge-aiClose").addEventListener("click",closeAll);
    $("#dge-backdrop").addEventListener("click",closeAll);
    $("#dge-aiSend").addEventListener("click",function(){ var q=$("#dge-aiInput").value.trim(); if(q) runAI(q); });
    $("#dge-aiInput").addEventListener("keydown",function(e){ if(e.key==="Enter"){ var q=e.target.value.trim(); if(q) runAI(q);} });
    document.querySelectorAll("#dge-drawer [data-preset]").forEach(function(b){ b.addEventListener("click",function(){ runAI(b.dataset.preset); }); });
    document.querySelectorAll("#dge-drawer [data-lang]").forEach(function(b){
      b.classList.toggle("on", b.dataset.lang===aiLang);
      b.addEventListener("click",function(){
      aiLang=b.dataset.lang; document.querySelectorAll("#dge-drawer [data-lang]").forEach(function(x){x.classList.remove("on");}); b.classList.add("on"); }); });
    // menu drawer (view/script/size/theme/search/settings -- consolidated
    // 24 Aug 2026, see the header comment in ashtadhyayi.html)
    var menuBtn=$("#dge-menuBtn"); if(menuBtn) menuBtn.addEventListener("click",function(){ $("#dge-menuDrawer").classList.add("open"); $("#dge-backdrop").classList.add("open"); });
    var menuClose=$("#dge-menuClose"); if(menuClose) menuClose.addEventListener("click",closeAll);
    var menuSearch=$("#dge-menuSearchBtn"); if(menuSearch) menuSearch.addEventListener("click",function(){ closeAll(); if(window.DGEGlobalSearch) window.DGEGlobalSearch.open(); });
    // settings
    var gear=$("#dge-gear"); if(gear) gear.addEventListener("click",function(){ closeAll(); openSettings(); });
    var sv=$("#dge-keySave"); if(sv) sv.addEventListener("click",function(){ setKey($("#dge-keyInput").value.trim()); LS.set("gmodel",$("#dge-modelSel").value); closeAll(); });
    var cl=$("#dge-keyClear"); if(cl) cl.addEventListener("click",function(){ setKey(""); $("#dge-keyInput").value=""; });
    var sc=$("#dge-setClose"); if(sc) sc.addEventListener("click",closeAll);
    // Focus / reading mode (critique #30): collapses the page to the sūtra
    // and open commentaries only, for the hours-long study sessions this
    // app is actually for. Persisted like every other reader preference.
    var focusBtn=$("#dge-focusBtn"); if(focusBtn) focusBtn.addEventListener("click",function(){
      var on=document.body.classList.toggle("dge-focus");
      LS.set("focus",on); focusBtn.setAttribute("aria-pressed",on?"true":"false"); focusBtn.classList.toggle("on",on);
    });
    registerContextualOverrides();
  }

  function applyPrefs(){
    if(LS.get("dark",false)) document.body.classList.add("dark");
    if(LS.get("focus",false)){
      document.body.classList.add("dge-focus");
      var fb=$("#dge-focusBtn"); if(fb){ fb.setAttribute("aria-pressed","true"); fb.classList.add("on"); }
    }
    var ms=$("#dge-modeSeg"); if(ms) ms.querySelectorAll("button").forEach(function(b){ b.classList.toggle("on",b.dataset.m===state.mode); });
    var ss=$("#dge-scriptSeg"); if(ss) ss.querySelectorAll("button").forEach(function(b){ b.classList.toggle("on",b.dataset.s===state.script); });
  }

  // ---- Contextual actions (DGE_UI_CONTRACT.md #10): register the two
  // object types this page adds -- 'sutra' and a page-specific 'commentary'
  // action set -- via contextual-actions.js's runtime extension point
  // (dgeRegisterContextualActions), scoped to this page's own taxonomy path
  // so no other reader's commentary/shloka menus are affected. Base
  // 'commentary' actions in admin/config/contextual-actions.json assume
  // dge/index.html's shloka-card shape (their handlers call
  // openBhashyaPickerForShloka etc., which don't exist here) -- removed for
  // this taxonomy path and replaced with handlers that fit THIS page's own
  // dge-card/META shape, so nothing here duplicates or fights the shared
  // registry's defaults for other readers.
  function registerContextualOverrides(){
    if(typeof window.dgeRegisterContextualActions!=="function") return;
    window.dgeRegisterContextualActions({
      objectTypes:["sutra"], pathPrefixes:["vedanga/vyakarana/ashtadhyayi"],
      add:[
        {id:"usage", icon:"search", label:"Corpus usage (प्रयोगाः)", action:"dgeCtxAshtaSutraUsage"},
        {id:"copyText", icon:"copy", label:"Copy sūtra text", action:"dgeCtxAshtaSutraCopyText"},
        {id:"copyCitation", icon:"link", label:"Copy citation", action:"dgeCtxAshtaSutraCopyCitation"},
        {id:"correction", icon:"edit", label:"Suggest a correction", action:"dgeCtxAshtaSutraCorrection"}
      ]
    });
    window.dgeRegisterContextualActions({
      objectTypes:["commentary"], pathPrefixes:["vedanga/vyakarana/ashtadhyayi"],
      remove:["copy","askAcharya","references"],
      add:[
        {id:"about", icon:"book", label:"About this commentary", action:"dgeCtxAshtaCommentaryAbout"},
        {id:"copyCitation", icon:"copy", label:"Copy citation", action:"dgeCtxAshtaCommentaryCopyCitation"},
        {id:"citations", icon:"search", label:"Find citations", action:"dgeCtxAshtaCommentaryCitations"},
        {id:"askAI", icon:"acharya", label:"Ask DGE AI about this", action:"dgeCtxAshtaCommentaryAskAI"}
      ]
    });
  }

  function openAiDrawer(prefill){
    $("#dge-drawer").classList.add("open"); $("#dge-backdrop").classList.add("open");
    if(prefill){
      var inp=$("#dge-aiInput"); if(inp){ inp.value=prefill; inp.focus(); }
    }
  }

  // ---- sutra ⋮ menu handlers ----
  window.dgeCtxAshtaSutraUsage = function(){ openPrayoga(); };
  window.dgeCtxAshtaSutraCopyText = function(ctx){
    var row=state.byId[ctx&&ctx.sutraId] || state.sutras[state.idx];
    if(row && navigator.clipboard) navigator.clipboard.writeText(row.sanskrit_text);
  };
  window.dgeCtxAshtaSutraCopyCitation = function(ctx){
    var row=state.byId[ctx&&ctx.sutraId] || state.sutras[state.idx]; if(!row) return;
    var cite="Aṣṭādhyāyī "+row.id+" — \""+row.sanskrit_text+"\" ("+location.href.split("#")[0]+"#"+row.id+")";
    if(navigator.clipboard) navigator.clipboard.writeText(cite);
  };
  window.dgeCtxAshtaSutraCorrection = function(){ reportCorrection(); };

  // ---- commentary ⋮ menu handlers ----
  window.dgeCtxAshtaCommentaryAbout = function(ctx){
    var m=META[ctx&&ctx.folder]; if(!m) return;
    var titleEl=document.getElementById("dgeContextMenuTitle"), bodyEl=document.getElementById("dgeContextMenuBody");
    if(!titleEl||!bodyEl) return;
    titleEl.textContent=m.sub;
    bodyEl.innerHTML='<p style="font-size:13px;line-height:1.6;color:var(--ink);grid-column:1/-1">'
      +"<b>"+esc(m.sub)+"</b> ("+esc(m.t)+")<br>Author: "+esc(m.who)
      +"<br>Role: "+esc(m.role==="bhashya"?"bhāṣya (foundational commentary)":m.role==="tika"?"ṭīkā (running commentary)":m.role==="tippani"?"ṭippaṇī (gloss/annotation)":"translation")
      +(m.lang==="en"?"<br>Language: English":"")+"</p>";
    if(typeof window.openModal==="function") window.openModal("dgeContextMenu");
  };
  window.dgeCtxAshtaCommentaryCopyCitation = function(ctx){
    var m=META[ctx&&ctx.folder], row=state.byId[ctx&&ctx.sutraId]||state.sutras[state.idx];
    if(!m||!row) return;
    var cite=m.sub+" on Aṣṭādhyāyī "+row.id+" ("+m.who+")";
    if(navigator.clipboard) navigator.clipboard.writeText(cite);
  };
  window.dgeCtxAshtaCommentaryCitations = function(){ openPrayoga(); };
  window.dgeCtxAshtaCommentaryAskAI = function(ctx){
    var m=META[ctx&&ctx.folder], row=state.byId[ctx&&ctx.sutraId]||state.sutras[state.idx];
    var label=m?((m.lang==="en"?m.t:m.sub)):"this commentary";
    openAiDrawer("Explain this "+label+" passage on sūtra "+((row&&row.id)||"")+".");
  };
  // Deep-linking a specific sutra via #<code> (e.g. "1.1.1") — the target
  // every other page's "open this sutra in Ashtadhyayi" link already
  // builds (js/intellisense.js's per-step sutra popover), but this page
  // never read location.hash at all, so every such link landed on the
  // default first sutra regardless of which one was actually clicked.
  function hashId(){ return decodeURIComponent((location.hash||"").replace(/^#/,"").trim()); }
  function goToHash(){
    var h=hashId();
    if(h && state.byId[h]){ closeAll(); go(state.sutras.indexOf(state.byId[h])); }
  }
  function boot(){
    wire(); applyPrefs();
    loadLayerVisibility().then(loadSutrapatha).then(function(){
      if(!state.sutras.length){ $("#dge-hsutra").textContent="(no sutra data found)"; return; }
      var dl=$("#dge-sutralist");
      if(dl) dl.innerHTML = state.sutras.map(function(s){ return '<option value="'+s.id+'">'; }).join("");
      var h=hashId();
      if(h && state.byId[h]) state.idx=state.sutras.indexOf(state.byId[h]);
      renderAll();
      ORDER.forEach(function(k){ if(state.enabled[k]) ensureLayer(k).then(function(){ renderLayers(); renderCommentaryNavigator(); }); });
      window.addEventListener("hashchange",goToHash);
      loadKaumudiOrder();
    }).catch(function(e){ $("#dge-hsutra").textContent="Failed to load sutrapatha data."; console.error("[ashtadhyayi]",e); });
  }
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded",boot); else boot();
})();
