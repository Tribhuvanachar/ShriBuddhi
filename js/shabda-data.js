/* ==========================================================================
 * DGE · shabda-data.js — shared data adapter for the Śabdapāṭha "views".
 *
 * The guru-data.js analogue for the nominal-declension browser: ONE module
 * fetched by every selectable view (dge/vyakarana/shabda/view1..3.html) so
 * the three layouts render the SAME real corpus
 * (dge/data/vedanga/vyakarana/shabdapatha/data.json, 9,007 stems) their own
 * way — never from inline mock data. The correctness-critical logic
 * (transliteration, the 8×3 declension table, exact reverse-form lookup,
 * per-cell रूपसिद्धिः derivation) lives here once, lifted verbatim from the
 * canonical dge/js/shabda.js, so a view can never drift from the real page.
 *
 * Depth-independent: the data URL is resolved relative to THIS script's own
 * location (document.currentScript.src), not the loading page, so the same
 * module works from dge/vyakarana/shabda.html (../data) and from the deeper
 * dge/vyakarana/shabda/view1.html (../../data) with no per-page edits.
 *
 * Requires js/subanta-steps.js to be loaded BEFORE load() runs (for the
 * आदिः/उपधा phoneme facets and the रूपसिद्धिः engine); degrades gracefully
 * (empty _adi/_up, no derivation) if it isn't.
 * ========================================================================== */
(function () {
  "use strict";

  // ----- resolve the corpus URL from this script's own src -----------------
  var SELF = (document.currentScript && document.currentScript.src) || "";
  // .../dge/js/shabda-data.js  ->  .../dge/data/vedanga/vyakarana/shabdapatha/data.json
  var DATA_URL = SELF
    ? SELF.replace(/\/js\/shabda-data\.js.*$/, "/data/vedanga/vyakarana/shabdapatha/data.json")
    : "../data/vedanga/vyakarana/shabdapatha/data.json";

  var VIBHAKTI = ["प्रथमा","द्वितीया","तृतीया","चतुर्थी","पञ्चमी","षष्ठी","सप्तमी","सम्बोधनम्"];
  var VACANA   = ["एकवचनम्","द्विवचनम्","बहुवचनम्"];
  // Gender code -> Devanāgarī label (the data's linga_iast is already
  // Devanāgarī but a view may want the short label; keep both available).
  var LINGA_LABEL = { P:"पुंल्लिङ्गम्", S:"स्त्रीलिङ्गम्", N:"नपुंसकलिङ्गम्", A:"अव्ययम्" };
  var LINGA_SHORT = { P:"पुं", S:"स्त्री", N:"नपुं", A:"अव्य" };

  // Kṛt-pratyaya display names (keys = vidyut identifiers in the data's `krt`).
  var KRT_NAME = { kta:"क्त", ktavatu:"क्तवतु", Satf:"शतृ", SAnac:"शानच्",
                   tavya:"तव्य", anIyar:"अनीयर्", yat:"यत्", Rvul:"ण्वुल्",
                   tfc:"तृच्", lyuw:"ल्युट्" };
  var VARNA_ORDER = "aAiIuUfFxXeEoOkKgGNcCjJYwWqQRtTdDnpPbBmyrlvSzsh";

  var MATRA_ANTA = { "ा":"A","ि":"i","ी":"I","ु":"u","ू":"U","ृ":"f","ॄ":"F","े":"e","ै":"E","ो":"o","ौ":"O" };
  var INDEP_ANTA = { "अ":"a","आ":"A","इ":"i","ई":"I","उ":"u","ऊ":"U","ऋ":"f","ॠ":"F","ए":"e","ऐ":"E","ओ":"o","औ":"O" };
  function antaOf(word){
    var w=String(word||"").normalize("NFC").trim();
    if(!w) return "";
    var last=w[w.length-1];
    if(last==="्") return "H";
    if(MATRA_ANTA[last]) return MATRA_ANTA[last];
    if(INDEP_ANTA[last]) return INDEP_ANTA[last];
    if(last>="क" && last<="ह") return "a";
    return "";
  }

  function esc(s){ return String(s==null?"":s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }

  // Transliterate Devanāgarī -> the requested script (Sanscript). Devanāgarī
  // passes through unchanged; degrades to Devanāgarī if Sanscript is absent
  // (the CDN is on the production block list, so this fallback is normal).
  function tl(text, script){
    if(!text) return text;
    if(!script || script==="devanagari" || !window.Sanscript) return text;
    try { return window.Sanscript.t(text, "devanagari", script); } catch(e){ return text; }
  }

  // The 8×3 (विभक्ति × वचन) declension table for a `;`-joined forms string.
  // `script` transliterates the cells; `highlightIdx` marks one cell (deep
  // link / reverse lookup); tappable cells carry data-ci for रूपसिद्धिः.
  function declTable(forms, opts){
    opts = opts || {};
    var script = opts.script || "devanagari";
    var highlightIdx = (opts.highlightIdx==null) ? null : opts.highlightIdx;
    var cells = String(forms||"").split(";"); while(cells.length<24) cells.push("");
    var deva = script==="devanagari" ? "deva" : "";
    var h='<div class="df-table"><table><thead><tr><th></th>'
        + '<th class="deva">एकवचनम्</th><th class="deva">द्विवचनम्</th><th class="deva">बहुवचनम्</th></tr></thead><tbody>';
    for(var v=0;v<8;v++){
      h+='<tr><th class="deva">'+VIBHAKTI[v]+'</th>';
      for(var n=0;n<3;n++){
        var idx=v*3+n;
        var hl = (highlightIdx!=null && idx===highlightIdx);
        var raw=(cells[idx]||"").trim();
        var has=!!raw;
        var shown = has ? esc(raw.split("-").map(function(x){return tl(x.trim(),script);}).join(", ")) : "";
        h+='<td class="'+deva+(hl?" df-hl":"")+(has?" sst-cell-hint":"")+'"'
          + (has?' data-ci="'+idx+'" title="रूपसिद्धिः — tap for the derivation"':'')
          + (hl?' id="df-hl-cell"':'') + '>'+shown+'</td>';
      }
      h+='</tr>';
    }
    h+='</tbody></table></div>';
    return h;
  }

  // Reverse lookup: an exact inflected surface form -> {id, cellIndex}.
  function findFormLocation(items, surface){
    var target=String(surface||"").trim(); if(!target) return null;
    for(var i=0;i<items.length;i++){
      var cells=String(items[i].forms||"").split(";");
      for(var c=0;c<cells.length && c<24;c++){
        var variants=(cells[c]||"").split("-");
        for(var v=0;v<variants.length;v++){ if(variants[v].trim()===target) return { id:items[i].id, cellIndex:c }; }
      }
    }
    return null;
  }

  // Tap a declension cell -> its step-by-step subanta prakriyā, rendered by
  // js/subanta-steps.js (same vidyut WASM engine rupasiddhi.html uses).
  // `td` is the clicked cell; `item` its headword record. Toggles closed if
  // the same cell is tapped again. No-op (returns false) if the engine or
  // the cell's data-ci is missing.
  function cellSteps(td, item){
    var S=window.DGESubantaSteps; if(!S || !td || !item) return false;
    var ci=parseInt(td.dataset.ci,10); if(isNaN(ci)) return false;
    var vb=Math.floor(ci/3), vc=ci%3;
    var tableWrap=td.closest(".df-table"); if(!tableWrap) return false;
    var panel=tableWrap.nextElementSibling;
    var already=panel && panel.classList.contains("sst-panel");
    if(already && panel.dataset.ci===String(ci)){ panel.remove(); td.classList.remove("sst-cell-on"); return true; }
    if(already) panel.remove();
    tableWrap.querySelectorAll(".sst-cell-on").forEach(function(x){x.classList.remove("sst-cell-on");});
    td.classList.add("sst-cell-on");
    S.css();
    panel=document.createElement("div");
    panel.className="sst-panel"; panel.dataset.ci=String(ci);
    panel.innerHTML='<div class="sst-loading">रूपसिद्धिः सज्जीक्रियते… (loading the derivation engine on first use)</div>';
    tableWrap.insertAdjacentElement("afterend",panel);
    var expected=String(item.forms||"").split(";")[ci]||"";
    S.derive(item.word, item.linga, vb, vc).then(function(results){
      if(!panel.isConnected) return;
      panel.innerHTML=S.panelHtml(item.word, item.linga, vb, vc, results, expected);
    }).catch(function(){
      if(!panel.isConnected) return;
      panel.innerHTML='<p class="sst-note">Could not load the derivation engine (offline?) — the forms above are unaffected.</p>';
    });
    return true;
  }

  // Which facet values actually occur (so no filter option is a dead end):
  // {lingas, antas, adis, ups, krts} — each an ordered array.
  function facets(items){
    var linga={}, anta={}, adis={}, ups={}, krts={};
    items.forEach(function(it){
      if(it.linga) linga[it.linga]=1;
      if(it._anta) anta[it._anta]=1;
      if(it._adi) adis[it._adi]=1;
      if(it._up) ups[it._up]=1;
      (it.krt||"").split(",").forEach(function(k){ if(k) krts[k]=1; });
    });
    function byVarna(set){ return Object.keys(set).sort(function(a,b){ return VARNA_ORDER.indexOf(a)-VARNA_ORDER.indexOf(b); }); }
    return {
      lingas: Object.keys(linga).sort(function(a,b){ return "PSNA".indexOf(a)-"PSNA".indexOf(b); }),
      antas: byVarna(anta), adis: byVarna(adis), ups: byVarna(ups),
      krts: Object.keys(krts).sort()
    };
  }

  // ----- the one cached load() ---------------------------------------------
  var _promise = null;
  function load(){
    if(_promise) return _promise;
    _promise = fetch(DATA_URL).then(function(r){
      if(!r.ok) throw new Error("HTTP "+r.status);
      return r.json();
    }).then(function(d){
      var S=window.DGESubantaSteps;
      var items=(d.items||[]).map(function(it){
        it._hay=((it.word||"")+" "+(it.artha||"")+" "+(it.artha_hin||"")+" "+(it.artha_eng||"")+" "+(it.forms||"")).toLowerCase();
        it._anta=antaOf(it.word);
        it._fx=";"+String(it.forms||"").split(/[;-]/).map(function(x){return x.trim().toLowerCase();}).join(";")+";";
        if(S){
          var slp=S.slp(it.word||"");
          it._adi=slp[0]||"";
          it._up=slp.length>1?slp[slp.length-2]:"";
          if(VARNA_ORDER.indexOf(it._adi)<0) it._adi="";
          if(VARNA_ORDER.indexOf(it._up)<0) it._up="";
        } else { it._adi=""; it._up=""; }
        var cells=String(it.forms||"").split(";"); while(cells.length<24) cells.push("");
        var eka=false,dvi=false,bahu=false;
        for(var v=0;v<8;v++){
          if(cells[v*3].trim()) eka=true;
          if(cells[v*3+1].trim()) dvi=true;
          if(cells[v*3+2].trim()) bahu=true;
        }
        it._vac = (!eka&&!bahu&&dvi) ? "ND" : (!eka&&!dvi&&bahu) ? "NB" : "";
        return it;
      });
      return { items:items, count:items.length, source:d.source||"", schema:d.schema||"" };
    });
    return _promise;
  }

  window.DGE_SHABDA = {
    load: load,
    esc: esc,
    tl: tl,
    antaOf: antaOf,
    declTable: declTable,
    findFormLocation: findFormLocation,
    cellSteps: cellSteps,
    facets: facets,
    VIBHAKTI: VIBHAKTI,
    VACANA: VACANA,
    LINGA_LABEL: LINGA_LABEL,
    LINGA_SHORT: LINGA_SHORT,
    KRT_NAME: KRT_NAME,
    VARNA_ORDER: VARNA_ORDER,
    dataUrl: DATA_URL
  };
})();
