/* ==========================================================================
 * DGE · Shabdapatha module — browse/filter/search nominal declensions
 * (Issue 15/19's "Shabda derivations" ask), sourced from ashtadhyayi-com/data
 * (github.com/ashtadhyayi-com/data, used with credit per its README).
 * Mirrors dhatu.js's list/filter/expand shape so the two feel like one family.
 * ========================================================================== */
(function () {
  "use strict";
  // Page-relative to vyakarana/shabda.html (Phase 10: moved one directory
  // deeper than  -- ../ reaches data/).
  var URL = "../data/vedanga/vyakarana/shabdapatha/data.json";
  var PAGE_SIZE = 20;
  var VIBHAKTI = ["प्रथमा","द्वितीया","तृतीया","चतुर्थी","पञ्चमी","षष्ठी","सप्तमी","सम्बोधनम्"];

  var LS = {
    get:function(k,d){ try{ var v=localStorage.getItem("dge.shabda."+k); return v===null?d:JSON.parse(v);}catch(e){return d;} },
    set:function(k,v){ try{ localStorage.setItem("dge.shabda."+k, JSON.stringify(v)); }catch(e){} }
  };
  var state = { all:[], view:[], page:0, script: LS.get("script","devanagari"), linga: LS.get("linga",""), anta: LS.get("anta",""),
                adi:"", upadha:"", krt:"", vac:"", q:"", openId: LS.get("open",null), highlightCell:null,
                bookmarks: LS.get("bookmarks", {}) }; // DGE UI Contract "subantaWord" contextual action

  // Kṛt pratyaya display names for the प्रत्ययान्तः filter — keys are the
  // vidyut pratyaya identifiers tools/tag_shabda_pratyaya.py wrote into the
  // data's `krt` field.
  var KRT_NAME = { kta:"क्त", ktavatu:"क्तवतु", Satf:"शतृ", SAnac:"शानच्",
                   tavya:"तव्य", anIyar:"अनीयर्", yat:"यत्", Rvul:"ण्वुल्",
                   tfc:"तृच्", lyuw:"ल्युट्" };
  // Canonical varṇa order for the आदिः/उपधा dropdowns (SLP1 phonemes).
  var VARNA_ORDER = "aAiIuUfFxXeEoOkKgGNcCjJYwWqQRtTdDnpPbBmyrlvSzsh";

  // Stem-ending class of a headword (the "advanced filter" axis): the
  // written final sound — a matra, an explicit virama (halanta), or the
  // implicit अ of a bare consonant letter. Derived from the word itself,
  // no new data needed.
  var MATRA_ANTA = { "ा":"A","ि":"i","ी":"I","ु":"u","ू":"U","ृ":"f","ॄ":"F","े":"e","ै":"E","ो":"o","ौ":"O" };
  var INDEP_ANTA = { "अ":"a","आ":"A","इ":"i","ई":"I","उ":"u","ऊ":"U","ऋ":"f","ॠ":"F","ए":"e","ऐ":"E","ओ":"o","औ":"O" };
  function antaOf(word){
    var w=String(word||"").normalize("NFC").trim();
    if(!w) return "";
    var last=w[w.length-1];
    if(last==="्") return "H";                       // halanta
    if(MATRA_ANTA[last]) return MATRA_ANTA[last];
    if(INDEP_ANTA[last]) return INDEP_ANTA[last];
    if(last>="क" && last<="ह") return "a";           // bare consonant → implicit अ
    return "";
  }
  function totalPages(){ return Math.max(1, Math.ceil(state.view.length / PAGE_SIZE)); }

  function $(s,r){ return (r||document).querySelector(s); }
  function esc(s){ return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;"); }
  function tl(t){ if(!t) return t; if(state.script==="devanagari"||!window.Sanscript) return t;
    try{ return window.Sanscript.t(t,"devanagari",state.script);}catch(e){return t;} }
  function hashId(){ return decodeURIComponent((location.hash||"").replace(/^#/,"").trim()); }
  function setHash(id){ try{ if(("#"+id)!==location.hash) history.replaceState(null,"","#"+id); }catch(e){} }

  function recompute(){
    var q=state.q.trim().toLowerCase();
    state.view = state.all.filter(function(it){
      if(state.linga && it.linga!==state.linga) return false;
      if(state.anta && it._anta!==state.anta) return false;
      if(state.adi && it._adi!==state.adi) return false;
      if(state.upadha && it._up!==state.upadha) return false;
      if(state.krt && (","+(it.krt||"")+",").indexOf(","+state.krt+",")<0) return false;
      if(state.vac && it._vac!==state.vac) return false;
      if(q && it._hay.indexOf(q)<0) return false;
      return true;
    });
    // With a live query, an exact hit must come FIRST, not wherever the
    // alphabet happens to put it 100 pages in (the reported bug: searching
    // राम buried राम itself behind every -रा compound). Rank: the headword
    // itself (0) < headword prefix (1) < an exact inflected form (2) <
    // anywhere-in-text match (3); alphabetical within a rank.
    if(q){
      state.view.sort(function(a,b){
        var ra=qRank(a,q), rb=qRank(b,q);
        return ra!==rb ? ra-rb : a.word.localeCompare(b.word,"sa");
      });
    } else {
      state.view.sort(function(a,b){ return a.word.localeCompare(b.word,"sa"); });
    }
    $("#sh-count").textContent = state.view.length.toLocaleString()+" / "+state.all.length.toLocaleString();
  }
  function qRank(it,q){
    var w=(it.word||"").toLowerCase();
    if(w===q) return 0;
    if(w.indexOf(q)===0) return 1;
    if(it._fx.indexOf(";"+q+";")>=0) return 2;
    return 3;
  }

  function declTable(forms, highlightIdx){
    var cells=String(forms||"").split(";"); while(cells.length<24) cells.push("");
    var h='<div class="df-table"><table><thead><tr><th></th><th class="deva">एकवचनम्</th><th class="deva">द्विवचनम्</th><th class="deva">बहुवचनम्</th></tr></thead><tbody>';
    for(var v=0;v<8;v++){
      h+='<tr><th class="deva">'+VIBHAKTI[v]+'</th>';
      for(var n=0;n<3;n++){ var idx=v*3+n;
        var hl = (highlightIdx!=null && idx===highlightIdx);
        var has = !!(cells[idx]||"").trim();
        h+='<td class="deva'+(hl?" df-hl":"")+(has?" sst-cell-hint":"")+'"'+(has?' data-ci="'+idx+'" title="रूपसिद्धिः — tap for the derivation"':'')+(hl?' id="df-hl-cell"':'')+'>'+esc((cells[idx]||"").split("-").join(", "))+'</td>'; }
      h+='</tr>';
    }
    h+='</tbody></table></div>';
    return h;
  }

  // Reverse lookup: given an exact inflected surface form (e.g. परस्य,
  // clicked via the reader's word-tool selection), find which headword it
  // declines from and which of the 24 declTable cells it sits in. Scans
  // state.all's already-loaded `forms` field (24 `;`-separated cells, each
  // itself possibly `-`-separated variants) rather than needing any new
  // data or a server round-trip.
  function findFormLocation(surface){
    var target=String(surface||"").trim(); if(!target) return null;
    for(var i=0;i<state.all.length;i++){
      var cells=String(state.all[i].forms||"").split(";");
      for(var c=0;c<cells.length && c<24;c++){
        var variants=(cells[c]||"").split("-");
        for(var v=0;v<variants.length;v++){ if(variants[v].trim()===target) return { id:state.all[i].id, cellIndex:c }; }
      }
    }
    return null;
  }

  function bodyHTML(it){
    var devCls = state.script==="iast"?"":"deva";
    function kv(k,v){ return '<div class="kv"><div class="kk">'+k+'</div><div class="kvv '+devCls+'">'+v+'</div></div>'; }
    var h="";
    if(it.artha) h+=kv("अर्थः · meaning", esc(tl(it.artha)));
    if(it.artha_hin) h+=kv("हिन्दी", esc(it.artha_hin));
    if(it.artha_eng) h+=kv("English", esc(it.artha_eng));
    h+=kv("लिङ्गः · gender", esc(tl(it.linga_iast)));
    h+=declTable(it.forms, it.id===state.openId?state.highlightCell:null);
    h+='<div class="acts"><button class="btn" data-sh-more="'+esc(it.id)+'" title="More actions for this word" aria-label="More actions for '+esc(tl(it.word))+'">⋯ More</button></div>';
    return h;
  }
  function rowHTML(it){
    var devCls = state.script==="iast"?"":"deva";
    var open=(it.id===state.openId);
    var bookmarked = !!(state.bookmarks && state.bookmarks[it.id]);
    return '<article class="row '+(open?"open":"")+(bookmarked?" bookmarked":"")+'" id="s-'+esc(it.id)+'" data-id="'+esc(it.id)+'">'
      +'<div class="rhead">'
        +'<span class="rdha '+devCls+'">'+(bookmarked?'★ ':'')+esc(tl(it.word))+'</span>'
        +(it.artha?'<span class="rartha '+devCls+'">'+esc(tl(it.artha))+'</span>':'<span class="rartha"></span>')
        +'<span class="rgana '+devCls+'">'+esc(tl(it.linga_iast))+'</span>'
        +'<span class="rcaret">▸</span>'
      +'</div>'
      +'<div class="rbody">'+(open?bodyHTML(it):"")+'</div>'
    +'</article>';
  }
  // Real Prev/Next pagination (20 words a page) rather than the old
  // infinite-"show more" chunking -- easier to reason about on a phone
  // ("where am I, how many pages left") and cheaper to paint per tap,
  // since only one page's worth of rows (and their collapsed bodies) is
  // ever in the DOM at once.
  function setBtnDisabled(btn, disabled){ if(!btn) return; btn.disabled=disabled; btn.style.opacity=disabled?"0.4":"1"; btn.style.cursor=disabled?"default":"pointer"; }
  function render(){
    var box=$("#sh-list");
    box.innerHTML="";
    if(!state.view.length){
      box.innerHTML='<div class="empty">No words match these filters.</div>';
      $("#sh-pager").style.display="none";
      var pt0=$("#sh-pagerTop"); if(pt0) pt0.style.display="none";
      return;
    }
    var start=state.page*PAGE_SIZE, end=Math.min(start+PAGE_SIZE, state.view.length), html="";
    for(var i=start;i<end;i++) html+=rowHTML(state.view[i]);
    box.insertAdjacentHTML("beforeend", html);
    // Both pagers (top + bottom) mirror the same state; the top one exists
    // because on a phone the bottom pager is a full page-length scroll away.
    var info="Page "+(state.page+1)+" / "+totalPages()+" · "+state.view.length.toLocaleString()+" words";
    $("#sh-pager").style.display="flex";
    $("#sh-pageInfo").textContent = info;
    setBtnDisabled($("#sh-prev"), state.page<=0);
    setBtnDisabled($("#sh-next"), state.page>=totalPages()-1);
    var pt=$("#sh-pagerTop");
    if(pt){
      pt.style.display="flex";
      $("#sh-pageInfoTop").textContent = info;
      setBtnDisabled($("#sh-prevTop"), state.page<=0);
      setBtnDisabled($("#sh-nextTop"), state.page>=totalPages()-1);
    }
  }
  function rerender(){ recompute(); state.page=0; render(); }

  function toggleRow(id){
    var it=state.all.find(function(x){return x.id===id;}); if(!it) return;
    var el=$("#s-"+CSS.escape(id)); if(!el) return;
    var wasOpen=el.classList.contains("open");
    state.highlightCell=null; // a manual expand/collapse always clears any deep-link highlight
    if(state.openId && state.openId!==id){ var prev=$("#s-"+CSS.escape(state.openId)); if(prev){ prev.classList.remove("open"); var b=prev.querySelector(".rbody"); if(b)b.innerHTML=""; } }
    if(wasOpen){ el.classList.remove("open"); el.querySelector(".rbody").innerHTML=""; state.openId=null; LS.set("open",null); setHash(""); }
    else { el.classList.add("open"); el.querySelector(".rbody").innerHTML=bodyHTML(it); state.openId=id; LS.set("open",id); setHash(id); }
  }
  function syncLingaChips(){ document.querySelectorAll("[data-l]").forEach(function(c){ c.classList.toggle("on", c.dataset.l===state.linga); }); }
  function syncAntaChips(){ document.querySelectorAll("[data-a]").forEach(function(c){ c.classList.toggle("on", c.dataset.a===state.anta); }); }
  function syncKrtChips(){ document.querySelectorAll("[data-k]").forEach(function(c){ c.classList.toggle("on", c.dataset.k===state.krt); }); }
  function syncVacChips(){ document.querySelectorAll("[data-v]").forEach(function(c){ c.classList.toggle("on", c.dataset.v===state.vac); }); }

  // Advanced filter rows built from the loaded data itself (आदिः/उपधा
  // dropdowns list only phonemes that actually begin/underlie some word;
  // प्रत्ययान्तः chips only pratyayas the tagger actually found), so no
  // option is ever a dead end.
  function buildAdvancedFilters(){
    var host=$("#sh-adv"); if(!host) return;
    var S=window.DGESubantaSteps;
    var adis={}, ups={}, krts={};
    state.all.forEach(function(it){
      if(it._adi) adis[it._adi]=1;
      if(it._up) ups[it._up]=1;
      (it.krt||"").split(",").forEach(function(k){ if(k) krts[k]=1; });
    });
    function opts(set){
      return Object.keys(set).sort(function(a,b){ return VARNA_ORDER.indexOf(a)-VARNA_ORDER.indexOf(b); })
        .map(function(ph){ var d=S?S.deva(ph):ph; return '<option value="'+ph+'">'+d+'</option>'; }).join("");
    }
    var h='';
    if(S && Object.keys(adis).length){
      h+='<div class="frow"><span class="flab deva">आदिः</span>'
        +'<select class="chip" id="sh-adi"><option value="">सर्वे</option>'+opts(adis)+'</select>'
        +'<span class="flab deva" style="margin-left:10px">उपधा</span>'
        +'<select class="chip" id="sh-upadha"><option value="">सर्वे</option>'+opts(ups)+'</select></div>';
    }
    var kk=Object.keys(krts).sort();
    if(kk.length){
      h+='<div class="frow"><span class="flab deva">प्रत्ययान्तः</span>'
        +'<button class="chip" data-k="">सर्वे</button>'
        +kk.map(function(k){ return '<button class="chip deva" data-k="'+k+'">'+(KRT_NAME[k]||k)+'</button>'; }).join("")
        +'</div>';
    }
    h+='<div class="frow"><span class="flab deva">वचनम्</span>'
      +'<button class="chip" data-v="">सर्वे</button>'
      +'<button class="chip deva" data-v="ND">नित्यद्विवचनम्</button>'
      +'<button class="chip deva" data-v="NB">नित्यबहुवचनम्</button></div>';
    host.innerHTML=h;
    var adi=$("#sh-adi"), up=$("#sh-upadha");
    if(adi) adi.addEventListener("change",function(){ state.adi=adi.value; rerender(); });
    if(up) up.addEventListener("change",function(){ state.upadha=up.value; rerender(); });
    document.querySelectorAll("[data-k]").forEach(function(c){ c.addEventListener("click",function(){
      state.krt=c.dataset.k; syncKrtChips(); rerender(); }); });
    document.querySelectorAll("[data-v]").forEach(function(c){ c.addEventListener("click",function(){
      state.vac=c.dataset.v; syncVacChips(); rerender(); }); });
    syncKrtChips(); syncVacChips();
  }

  // Tap a declension cell -> its step-by-step subanta prakriyā, rendered by
  // js/subanta-steps.js (the same vidyut WASM engine rupasiddhi.html uses,
  // loaded lazily on the first tap). Tapping the same cell again closes it.
  function cellSteps(td){
    var S=window.DGESubantaSteps; if(!S) return;
    var row=td.closest("article.row"); if(!row) return;
    var it=state.all.find(function(x){return x.id===row.dataset.id;}); if(!it) return;
    var ci=parseInt(td.dataset.ci,10), vb=Math.floor(ci/3), vc=ci%3;
    var tableWrap=td.closest(".df-table"); if(!tableWrap) return;
    var panel=tableWrap.nextElementSibling;
    var already=panel && panel.classList.contains("sst-panel");
    if(already && panel.dataset.ci===String(ci)){ panel.remove(); td.classList.remove("sst-cell-on"); return; }
    if(already) panel.remove();
    tableWrap.querySelectorAll(".sst-cell-on").forEach(function(x){x.classList.remove("sst-cell-on");});
    td.classList.add("sst-cell-on");
    S.css();
    panel=document.createElement("div");
    panel.className="sst-panel"; panel.dataset.ci=String(ci);
    panel.innerHTML='<div class="sst-loading">रूपसिद्धिः सज्जीक्रियते… (loading the derivation engine on first use)</div>';
    tableWrap.insertAdjacentElement("afterend",panel);
    var expected=String(it.forms||"").split(";")[ci]||"";
    S.derive(it.word, it.linga, vb, vc).then(function(results){
      if(!panel.isConnected) return;
      panel.innerHTML=S.panelHtml(it.word, it.linga, vb, vc, results, expected);
    }).catch(function(){
      if(!panel.isConnected) return;
      panel.innerHTML='<p class="sst-note">Could not load the derivation engine (offline?) — the forms above are unaffected.</p>';
    });
  }

  function wire(){
    $("#sh-list").addEventListener("click",function(e){
      var td=e.target.closest("td[data-ci]");
      if(td){ cellSteps(td); return; }
      var mo=e.target.closest("[data-sh-more]");
      if(mo){ e.stopPropagation();
        var id=mo.getAttribute("data-sh-more"), it=state.all.find(function(x){return x.id===id;});
        if(it && typeof window.dgeOpenContextualMenu==="function"){
          window.dgeOpenContextualMenu("subantaWord", {id:id, label:tl(it.word)+(it.artha?" — "+tl(it.artha):"")});
        }
        return; }
      var h=e.target.closest(".rhead"); if(h) toggleRow(h.parentElement.dataset.id);
    });
    $("#sh-prev").addEventListener("click",function(){ if(state.page>0){ state.page--; render(); window.scrollTo({top:0,behavior:"smooth"}); } });
    $("#sh-next").addEventListener("click",function(){ if(state.page<totalPages()-1){ state.page++; render(); window.scrollTo({top:0,behavior:"smooth"}); } });
    $("#sh-toTop").addEventListener("click",function(){ window.scrollTo({top:0,behavior:"smooth"}); });
    $("#sh-toBottom").addEventListener("click",function(){ $("#sh-pager").scrollIntoView({behavior:"smooth",block:"end"}); });
    $("#sh-search").addEventListener("input",function(e){ state.q=e.target.value; rerender(); });
    document.querySelectorAll("[data-l]").forEach(function(c){ c.addEventListener("click",function(){
      state.linga=c.dataset.l; LS.set("linga",state.linga); syncLingaChips(); rerender(); }); });
    document.querySelectorAll("[data-a]").forEach(function(c){ c.addEventListener("click",function(){
      state.anta=c.dataset.a; LS.set("anta",state.anta); syncAntaChips(); rerender(); }); });
    var pv=$("#sh-prevTop"), nx=$("#sh-nextTop");
    if(pv) pv.addEventListener("click",function(){ if(state.page>0){ state.page--; render(); window.scrollTo({top:0,behavior:"smooth"}); } });
    if(nx) nx.addEventListener("click",function(){ if(state.page<totalPages()-1){ state.page++; render(); window.scrollTo({top:0,behavior:"smooth"}); } });
    $("#sh-scriptSeg").addEventListener("click",function(e){ var b=e.target.closest("button"); if(!b)return;
      [].forEach.call(e.currentTarget.children,function(x){x.classList.remove("on");}); b.classList.add("on");
      state.script=b.dataset.s; LS.set("script",state.script); rerender(); });
    $("#sh-theme").addEventListener("click",function(){ var d=document.body.classList.toggle("dark"); LS.set("dark",d); });
  }

  function openById(id){
    var it=state.all.find(function(x){return x.id===id;}); if(!it) return;
    state.openId=id; LS.set("open",id); state.linga=""; state.anta=""; state.q=""; $("#sh-search").value=""; LS.set("linga",""); LS.set("anta","");
    state.adi=""; state.upadha=""; state.krt=""; state.vac="";
    var _adi=$("#sh-adi"), _up=$("#sh-upadha"); if(_adi)_adi.value=""; if(_up)_up.value="";
    syncLingaChips(); syncAntaChips(); syncKrtChips(); syncVacChips(); recompute();
    var pos=state.view.findIndex(function(x){return x.id===id;});
    state.page = pos>=0 ? Math.floor(pos/PAGE_SIZE) : 0;
    render();
    var el=$("#s-"+CSS.escape(id));
    if(el){ el.scrollIntoView({behavior:"smooth",block:"center"}); setHash(id); }
    if(state.highlightCell!=null){
      var cell=$("#df-hl-cell");
      if(cell) setTimeout(function(){ cell.scrollIntoView({behavior:"smooth",block:"center"}); }, 250);
    }
  }

  // Deep link from the reader's word-tool: an exact inflected form (e.g.
  // परस्य) opens the headword it belongs to (पर) with that one cell
  // (षष्ठी एकवचनम्) highlighted, instead of a plain substring search.
  // Returns false (no navigation performed) when the surface form doesn't
  // match any stored cell exactly, so the caller can fall back to search.
  function openByForm(surface){
    var loc=findFormLocation(surface); if(!loc) return false;
    state.highlightCell=loc.cellIndex;
    openById(loc.id);
    return true;
  }

  // A form the Śabdapāṭha (fixed nominal stems) genuinely has no entry for
  // may still be a kṛdanta — a word DERIVED from a verb root (लभ्यः, from
  // लभ्+यत्) that is grammatically correct but lives in a different
  // database (tools/build_krt_form_index.py's reverse index over every
  // root's kṛt-pratyaya forms). Checked before giving up entirely; a
  // match redirects straight to the actual right page (krdanta.html)
  // instead of leaving the reader on a nominal-stem browser that was
  // never going to have this word.
  function tryKrtFallback(surface){
    var w=(surface||"").trim();
    if(!w){ tryCompoundFallback(surface); return; }
    var cp=w.codePointAt(0).toString(16).toLowerCase().padStart(4,"0");
    fetch("../data/vedanga/vyakarana/prakriya/krtindex/"+cp+".json").then(function(r){
      return r.ok ? r.json() : null;
    }).then(function(m){
      // The index lists EVERY root that writes this kṛdanta form (कृत्वा is
      // both 05.0007 "to injure" and 08.0010 "to do"). This page can only
      // navigate to one, so it goes to the root the library actually attests
      // most — dhatu_prayoga/root_weights.json, counted from forms that are
      // not ambiguous. Older single-record shape still accepted.
      var hit=m && m[w];
      if(!hit){ tryCompoundFallback(surface); return; }
      var list=Array.isArray(hit)?hit:[hit];
      if(!list.length){ tryCompoundFallback(surface); return; }
      if(list.length===1){ location.href="krdanta.html#"+list[0].c+":"+list[0].k; return; }
      fetch("../data/vedanga/vyakarana/dhatu_prayoga/root_weights.json",{cache:"force-cache"})
        .then(function(r){ return r.ok?r.json():null; })
        .then(function(d){
          var wt=(d&&d.weights)||{};
          list.sort(function(a,b){ return (wt[b.c]||0)-(wt[a.c]||0) || String(a.c).localeCompare(String(b.c)); });
          location.href="krdanta.html#"+list[0].c+":"+list[0].k;
        })
        .catch(function(){ location.href="krdanta.html#"+list[0].c+":"+list[0].k; });
    }).catch(function(){ tryCompoundFallback(surface); });
  }

  // A form matching no headword (exact) and no kṛdanta may still be an
  // honest SAMĀSA (compound) — Sanskrit compounds inflect only on their
  // final member (uttarapada), so a compound whose last member is an
  // ordinary listed pratipadika will end in one of that headword's own 24
  // already-loaded forms (e.g. जयीन्द्रज्योतिषे ends in ज्योतिष्'s चतुर्थी
  // एकवचन "ज्योतिषे" -- ज्योतिष् itself is @jyotiS1 in this very data).
  // Scans the same in-memory forms every headword already carries; no new
  // data, no network call, no WASM.
  //
  // False-positive guard: a short or common ending matches countless
  // unrelated words by pure chance (verified empirically against the whole
  // Raghavendra Vijaya sarga_1 corpus -- 3-character endings like तम्/कम्/
  // सन् falsely "matched" verb forms and kṛdantas that merely happen to end
  // in a common case suffix), so both the matched suffix and the leftover
  // (unrecognized) prefix must clear a minimum length -- COMPOUND_MIN_SUFFIX_LEN
  // keeps the match grammatically distinctive, COMPOUND_MIN_PREFIX_LEN keeps
  // it an actual compound prior member rather than a stray letter.
  // Among all qualifying hits the LONGEST suffix wins (most specific).
  var COMPOUND_MIN_SUFFIX_LEN = 4, COMPOUND_MIN_PREFIX_LEN = 2;
  // सर्वनाम (pronoun) headwords -- तद्/यद्/एतद्/किम्/अदस् -- are excluded
  // outright: their case endings (ताम्, तस्य, ...) coincide with ordinary
  // आ-/अ-stem noun endings, but Sanskrit compounds do not end in a bare
  // pronoun stem as the semantic final member, so a "match" here is always
  // a coincidence, not a real compound (also verified against the corpus --
  // यदीरिताम्/संभावयन्तेऽर्थिताम् were false "तद्" hits before this guard).
  function isPronounHeadword(it){ return (it.artha||"").indexOf("सर्वनाम")>=0; }
  function findCompoundFinalMatch(surface){
    var w=String(surface||"").trim(); if(!w) return null;
    var best=null;
    for(var i=0;i<state.all.length;i++){
      var it=state.all[i];
      if(isPronounHeadword(it)) continue;
      var cells=String(it.forms||"").split(";");
      for(var c=0;c<cells.length && c<24;c++){
        var variants=(cells[c]||"").split("-");
        for(var v=0;v<variants.length;v++){
          var form=variants[v].trim();
          if(!form || form.length<COMPOUND_MIN_SUFFIX_LEN) continue;
          if(w.length-form.length<COMPOUND_MIN_PREFIX_LEN) continue;
          if(w.slice(w.length-form.length)!==form) continue;
          if(!best || form.length>best.form.length){
            best={ id:it.id, word:it.word, artha:it.artha, linga_iast:it.linga_iast,
                   cellIndex:c, form:form, prefix:w.slice(0,w.length-form.length) };
          }
        }
      }
    }
    return best;
  }

  // Renders a compound-final match honestly distinct from an ordinary
  // headword hit: names the recognized final member, its vibhakti/vacana,
  // and flags the prior member as an unlisted/unanalyzed compound part
  // (e.g. a proper name) rather than pretending the whole surface is itself
  // a headword.
  function showCompoundMatch(surface, hit){
    $("#sh-search").value=surface||"";
    recompute(); state.page=0; render();
    var vib=VIBHAKTI[Math.floor(hit.cellIndex/3)], vac=["एकवचनम्","द्विवचनम्","बहुवचनम्"][hit.cellIndex%3];
    var box=$("#sh-list");
    box.insertAdjacentHTML("afterbegin",
      '<div class="empty">"'+esc(surface)+'" is not itself a listed headword, but looks like a '+
      '<b>समासः (compound)</b> ending in a recognized final member (उत्तरपदम्): '+
      '<b class="deva">'+esc(tl(hit.word))+'</b> — '+esc(vib)+' '+esc(vac)+
      ' (रूपम् "'+esc(tl(hit.form))+'"'+(hit.artha?", "+esc(tl(hit.artha)):"")+'). '+
      'The remaining part "<b class="deva">'+esc(tl(hit.prefix))+'</b>" is not separately analyzed here '+
      '(likely a proper name or an unlisted prior member) -- only the compound\'s final member is identified. '+
      '<a href="#" id="sh-open-final">View the full declension of '+esc(tl(hit.word))+'</a>, or '+
      '<a href="#" id="sh-report-missing">report this as missing</a>.</div>');
    var openLink=$("#sh-open-final");
    if(openLink) openLink.addEventListener("click",function(e){ e.preventDefault(); state.highlightCell=hit.cellIndex; openById(hit.id); });
    var rep=$("#sh-report-missing");
    if(rep) rep.addEventListener("click",function(e){
      e.preventDefault();
      if(typeof window.dgeReportMissingForm==="function"){ window.dgeReportMissingForm(surface,"shabda"); return; }
      var email=window.DGE_CONTACT_EMAIL||"sanatanavidyagurukulam@gmail.com";
      var subject=encodeURIComponent("[DGE-CONTENT-GAP] missing-form — "+surface);
      var lines=["Type: missing-form","Surface: "+surface,
        "Context: shabda (compound-final match: "+hit.word+", "+vib+" "+vac+")",
        "Page: "+location.href,"Timestamp: "+new Date().toISOString()];
      location.href="mailto:"+email+"?subject="+subject+"&body="+encodeURIComponent(lines.join("\n"));
    });
  }

  function tryCompoundFallback(surface){
    var hit=findCompoundFinalMatch(surface);
    if(hit){ showCompoundMatch(surface, hit); return; }
    showNotFound(surface);
  }

  // Previously this silently fell back to a plain substring search on the
  // unmatched text, which could (and did — reported live, with a
  // screenshot) match the query as a raw substring INSIDE an unrelated
  // word's own declension table and open THAT as if it were the answer.
  // An honest "not found" beats a confident-looking wrong one; the search
  // box is left populated so the reader can still search manually if they
  // want to, rather than being force-fed a guess.
  function showNotFound(surface){
    $("#sh-search").value=surface||"";
    recompute();
    state.page=0;
    render();
    var box=$("#sh-list");
    box.insertAdjacentHTML("afterbegin",
      '<div class="empty">No exact form found for "'+esc(surface||"")+'". '+
      'Showing the ordinary word list below — search manually, or '+
      '<a href="#" id="sh-report-missing">report this as missing</a>.</div>');
    var rep=$("#sh-report-missing");
    if(rep) rep.addEventListener("click",function(e){
      e.preventDefault();
      // shabda.html now loads modals.js (DGE UI Contract retrofit, 28 Aug
      // 2026), so window.dgeReportMissingForm is normally defined and used
      // below — this mailto fallback stays as a defensive path (matching
      // the same template tag/field shape by hand) in case that ever isn't
      // true. See modals.js's own copy for the full reasoning on why the
      // shape matters (a future scheduled process matching only this exact
      // tag+field format, everything else ignored or routed to a human).
      if(typeof window.dgeReportMissingForm==="function"){ window.dgeReportMissingForm(surface,"shabda"); return; }
      var email=window.DGE_CONTACT_EMAIL||"sanatanavidyagurukulam@gmail.com";
      var subject=encodeURIComponent("[DGE-CONTENT-GAP] missing-form — "+surface);
      var lines=["Type: missing-form","Surface: "+surface,"Context: shabda","Page: "+location.href,
        "Timestamp: "+new Date().toISOString()];
      location.href="mailto:"+email+"?subject="+subject+"&body="+encodeURIComponent(lines.join("\n"));
    });
  }

  /* DGE UI Contract retrofit (28 Aug 2026): a new "subantaWord" contextual-
     actions object type, same pattern as dhatu.js's "dhatuRoot" (which
     mirrors ashtadhyayi.js's "sutra"/"commentary" — see
     DGE_UI_CONTRACT.md). Copy citation/table text and a real bookmark —
     nothing here duplicates the per-cell derivation popover
     (subanta-steps.js's cellSteps()), which already owns that job. */
  function registerShabdaContextualActions(){
    if(typeof window.dgeRegisterContextualActions!=="function") return;
    window.dgeRegisterContextualActions({
      objectTypes:["subantaWord"],
      add:[
        {id:"bookmark", icon:"bookmark", label:"Bookmark this word", action:"dgeCtxShabdaBookmark"},
        {id:"copyCitation", icon:"copy", label:"Copy citation", action:"dgeCtxShabdaCopyCitation"},
        {id:"copyTable", icon:"copy", label:"Copy declension table", action:"dgeCtxShabdaCopyTable"}
      ]
    });
  }
  async function dgeCopyText(text, okMessage){
    try{
      if(navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(text);
      else { var ta=document.createElement("textarea"); ta.value=text; ta.style.position="fixed"; ta.style.left="-9999px";
        document.body.appendChild(ta); ta.select(); document.execCommand("copy"); document.body.removeChild(ta); }
      if(typeof window.showToast==="function") window.showToast(okMessage||"Copied.");
    } catch(e){ if(typeof window.showToast==="function") window.showToast("Could not copy — select and copy manually."); }
  }
  function shabdaCiteText(it){
    return tl(it.word)+" ("+tl(it.linga_iast)+(it.artha?", \""+tl(it.artha)+"\"":"")+
      ") — Śabdapāṭha, DGE ("+location.href.split("#")[0]+"#"+it.id+")";
  }
  window.dgeCtxShabdaCopyCitation = function(ctx){
    var it=state.all.find(function(x){return x.id===ctx.id;}); if(!it) return;
    dgeCopyText(shabdaCiteText(it), "Citation copied.");
  };
  window.dgeCtxShabdaCopyTable = function(ctx){
    var el=$("#s-"+CSS.escape(ctx.id)); var body=el&&el.querySelector(".rbody table");
    var it=state.all.find(function(x){return x.id===ctx.id;}); if(!it) return;
    var text=body?body.innerText.replace(/[ \t]+/g," ").trim():shabdaCiteText(it);
    dgeCopyText(shabdaCiteText(it)+"\n\n"+text, "Declension table copied.");
  };
  window.dgeCtxShabdaBookmark = function(ctx){
    var id=ctx.id; if(!id) return;
    state.bookmarks[id] = !state.bookmarks[id];
    LS.set("bookmarks", state.bookmarks);
    var row=$("#s-"+CSS.escape(id));
    if(row) row.classList.toggle("bookmarked", !!state.bookmarks[id]);
    if(typeof window.showToast==="function") window.showToast(state.bookmarks[id]?"Bookmarked.":"Bookmark removed.");
  };

  function boot(){
    if(LS.get("dark",false)) document.body.classList.add("dark");
    var ss=$("#sh-scriptSeg"); if(ss) ss.querySelectorAll("button").forEach(function(b){ b.classList.toggle("on",b.dataset.s===state.script); });
    syncLingaChips(); syncAntaChips(); wire();
    registerShabdaContextualActions();
    fetch(URL).then(function(r){ if(!r.ok) throw new Error(r.status); return r.json(); }).then(function(d){
      state.all=(d.items||[]).map(function(it){
        // forms included so a search for an inflected word (e.g. परस्य,
        // pasted in from the reader's "Shabda" word-tool) finds the
        // headword it declines from, not just an exact headword match.
        it._hay=((it.word||"")+" "+(it.artha||"")+" "+(it.artha_hin||"")+" "+(it.artha_eng||"")+" "+(it.forms||"")).toLowerCase();
        it._anta=antaOf(it.word);
        // ";"-bounded list of every exact inflected variant, for the exact-
        // form rank in qRank() ("रामस्य" typed should surface राम first).
        it._fx=";"+String(it.forms||"").split(/[;-]/).map(function(x){return x.trim().toLowerCase();}).join(";")+";";
        // Phoneme-level facets (SLP1 via subanta-steps.js's converter):
        // आदिः = first phoneme, उपधा = penultimate phoneme (1.1.65
        // अलोऽन्त्यात् पूर्व उपधा). Empty when the converter isn't loaded.
        var S=window.DGESubantaSteps;
        if(S){
          var slp=S.slp(it.word||"");
          it._adi=slp[0]||"";
          it._up=slp.length>1?slp[slp.length-2]:"";
          if(VARNA_ORDER.indexOf(it._adi)<0) it._adi="";
          if(VARNA_ORDER.indexOf(it._up)<0) it._up="";
        } else { it._adi=""; it._up=""; }
        // नित्य-वचन class from which columns of the 8×3 grid actually carry
        // forms: dual-only (उभ, दम्पति…) and plural-only (अप्, अष्टन्…).
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
      $("#sh-total").textContent = state.all.length.toLocaleString();
      buildAdvancedFilters();
      var sp=new URLSearchParams(location.search);
      var form0=sp.get("form"), q0=sp.get("q");
      if(form0 && openByForm(form0)) return; // exact-form deep link resolved; opened above
      if(form0){ tryKrtFallback(form0); return; } // may itself be async; renders its own state either way
      if(q0){ state.q=q0; $("#sh-search").value=q0; }
      recompute();
      var h0=hashId();
      if(h0 && state.all.some(function(x){return x.id===h0;})){ openById(h0); }
      else { state.page=0; render(); }
    }).catch(function(e){ $("#sh-list").innerHTML='<div class="empty">Failed to load shabdapatha data ('+e+'). Serve from the  folder.</div>'; });
  }
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded",boot); else boot();
  // 7 Sep 2026: read-only handles for js/shabda-gen.js (nearest listed paradigm, ending class).
  window.DGEShabda = { all: function(){ return state.all||[]; }, antaOf: antaOf };
})();
