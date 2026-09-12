/* ==========================================================================
 * DGE · ashtadhyayi-data.js — shared data adapter for the Aṣṭādhyāyī "views".
 *
 * The guru-data.js / shabda-data.js analogue for the Pāṇinian sūtra reader:
 * ONE module fetched by every selectable view
 * (dge/vyakarana/ashtadhyayi/view1..3.html) so the three layouts render the
 * SAME real corpus their own way — never from inline mock data. The data
 * layer is lifted from the canonical dge/js/ashtadhyayi.js (loadSutrapatha /
 * loadKaumudiOrder / ensureLayer / kaumudiOf / chapterOf / tl / iast), so a
 * view can never drift from the real page.
 *
 * Depth-independent: BASE is resolved from THIS script's own location
 * (document.currentScript.src), so it works from any page depth with no edit.
 *
 * Reuses window.Sanscript for transliteration if present (degrades to
 * Devanāgarī when the CDN is blocked). No Gemini/paid call anywhere here.
 * ========================================================================== */
(function () {
  "use strict";

  var SELF = (document.currentScript && document.currentScript.src) || "";
  var BASE = SELF
    ? SELF.replace(/\/js\/ashtadhyayi-data\.js.*$/, "/data/vedanga/vyakarana/ashtadhyayi/")
    : "../data/vedanga/vyakarana/ashtadhyayi/";

  // Commentary/translation layers. `dir` is the on-disk folder (mahabhashya
  // lives in mahabhashya_patanjali/); everything else matches its key.
  var META = {
    kashika:          {t:"काशिकावृत्तिः", sub:"Kāśikā-vṛtti", who:"Vāmana–Jayāditya", tag:"var(--k)", role:"tika", dir:"kashika"},
    siddhanta_kaumudi:{t:"सिद्धान्तकौमुदी", sub:"Siddhānta-Kaumudī", who:"Bhaṭṭoji Dīkṣita", tag:"var(--sk)", role:"tika", dir:"siddhanta_kaumudi"},
    mahabhashya:      {t:"महाभाष्यम्", sub:"Mahā-bhāṣya", who:"Patañjali", tag:"var(--mb)", role:"bhashya", dir:"mahabhashya_patanjali"},
    balamanorama:     {t:"बालमनोरमा", sub:"Bāla-manoramā", who:"Vāsudeva Dīkṣita", tag:"var(--b)", role:"tippani", dir:"balamanorama"},
    tattvabodhini:    {t:"तत्त्वबोधिनी", sub:"Tattva-bodhinī", who:"Jñānendra Sarasvatī", tag:"var(--t)", role:"tippani", dir:"tattvabodhini"},
    nyasa:            {t:"न्यासः", sub:"Kāśikāvivaraṇapañjikā", who:"Jinendrabuddhi", tag:"var(--n)", role:"tippani", dir:"nyasa"},
    vasu:             {t:"Vasu · English", sub:"S.C. Vasu (1891)", who:"Śrīśa Chandra Vasu", tag:"var(--vs)", role:"translation", lang:"en", dir:"vasu"},
    vasu_kaumudi:     {t:"Vasu · SK English", sub:"S.C. Vasu, Siddhānta-Kaumudī tr. (1905-07)", who:"Śrīśa Chandra Vasu", tag:"var(--vs)", role:"translation", lang:"en", dir:"vasu_kaumudi"}
  };
  var ORDER = ["kashika","siddhanta_kaumudi","mahabhashya","balamanorama","tattvabodhini","nyasa","vasu","vasu_kaumudi"];

  function esc(s){ return String(s==null?"":s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }
  function tl(t, script){ if(!t) return t; if(!script||script==="devanagari"||!window.Sanscript) return t;
    try{ return window.Sanscript.t(t,"devanagari",script);}catch(e){return t;} }
  function iast(t){ try{ return window.Sanscript?window.Sanscript.t(t,"devanagari","iast"):"";}catch(e){return "";} }
  function devnum(n){ var m={0:"०",1:"१",2:"२",3:"३",4:"४",5:"५",6:"६",7:"७",8:"८",9:"९"};
    return String(n==null?"":n).replace(/[0-9]/g,function(d){return m[d];}); }
  function fetchJSON(u){ return fetch(u).then(function(r){ if(!r.ok) throw new Error(u+" "+r.status); return r.json(); }); }

  var _db = null, _promise = null;
  var _layers = {}; // folderKey -> {loaded,loading,byId,promise,error}

  function load(){
    if(_promise) return _promise;
    _promise = Promise.all([
      fetchJSON(BASE+"sutrapatha/data.json"),
      fetchJSON(BASE+"kaumudi_order/data.json").catch(function(){ return {items:[],chapters:[]}; })
    ]).then(function(res){
      var sp = res[0], ko = res[1];
      var sutras = sp.items || [];
      var byId = {}, anuvrittiInto = {}, adhikaraInto = {};
      sutras.forEach(function(it){ byId[it.id]=it; });
      sutras.forEach(function(it){
        (it.anuvritti||[]).forEach(function(a){
          if(!a.from) return;
          (anuvrittiInto[a.from]=anuvrittiInto[a.from]||[]).push(it.id);
        });
        (it.adhikara_refs||[]).forEach(function(r){
          if(!r[1] || r[1]===it.id) return;
          (adhikaraInto[r[1]]=adhikaraInto[r[1]]||[]).push(it.id);
        });
      });
      var kById = {};
      (ko.items||[]).forEach(function(it){ kById[it.id]=it; });
      var kList = (ko.items||[]).slice().sort(function(a,b){ return a.kaumudiIndex-b.kaumudiIndex; }).map(function(it){ return it.id; });
      var chapters = ko.chapters || [];
      // first sūtra id (in SK order) for each 1-based chapter number
      var firstOfChapter = {};
      kList.forEach(function(id){
        var e=kById[id]; if(e && e.chapter && !(e.chapter in firstOfChapter)) firstOfChapter[e.chapter]=id;
      });
      _db = {
        sutras: sutras,
        byId: byId,
        akOrder: sutras.map(function(it){ return it.id; }),   // Aṣṭādhyāyī (traditional) order
        skOrder: kList,                                        // Siddhānta-Kaumudī reading order
        kaumudi: { byId:kById, list:kList, chapters:chapters, firstOfChapter:firstOfChapter },
        anuvrittiInto: anuvrittiInto,
        adhikaraInto: adhikaraInto,
        count: sutras.length,
        source: sp.source||"", licence: sp.licence||""
      };
      return _db;
    });
    return _promise;
  }

  // Lazy per-layer fetch. `folder` is a META key (e.g. "kashika"); resolves to
  // {byId:{id -> {id, reference, sanskrit_text, ...}}}; commentary body text
  // lives in each item's sanskrit_text (English layers too). Never rejects —
  // a failed/empty layer resolves with an empty byId + .error set.
  function ensureLayer(folder){
    var L=_layers[folder];
    if(L && (L.loaded||L.loading)) return L.promise;
    L=_layers[folder]={loaded:false,loading:true,byId:{},error:null};
    var dir=(META[folder] && META[folder].dir) || folder;
    L.promise=fetchJSON(BASE+dir+"/data.json").then(function(d){
      (d.items||[]).forEach(function(it){ L.byId[it.id]=it; });
      L.loaded=true; L.loading=false; return L;
    }).catch(function(e){ L.loading=false; L.error=e; L.loaded=true; return L; });
    return L.promise;
  }

  function kaumudiOf(id){ return (_db && _db.kaumudi.byId[id]) || null; }
  function chapterOf(entry){ if(!_db||!entry||!entry.chapter) return null; return _db.kaumudi.chapters[entry.chapter-1]||null; }
  function firstIdOfChapter(chapterNum){ return (_db && _db.kaumudi.firstOfChapter[chapterNum]) || null; }

  window.DGE_ASHTA = {
    load: load,
    ensureLayer: ensureLayer,
    META: META,
    ORDER: ORDER,
    kaumudiOf: kaumudiOf,
    chapterOf: chapterOf,
    firstIdOfChapter: firstIdOfChapter,
    tl: tl,
    iast: iast,
    esc: esc,
    devnum: devnum,
    base: BASE
  };
})();
