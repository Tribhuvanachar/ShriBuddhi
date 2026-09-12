/* ==========================================================================
 * DGE · Dhātupāṭha module (Stage 1)  v1.0.0
 *   Browse/filter/sort the Pāṇinīya Dhātupāṭha (Vidyut, MIT).
 *   Filters: gaṇa (1–10), pada (P/A/U), free-text (धातु / artha / roman).
 *   Multi-script (Sanscript), deep-linkable per root (#code), prefs persisted.
 *   Stage-2 hook: a प्रक्रिया button per root, wired to a placeholder that the
 *   derivation engine (vidyut-prakriya) will fill in.  Touches no other module.
 * ========================================================================== */
(function () {
  "use strict";
  // Page-relative to vyakarana/dhatu.html (Phase 10: moved one directory
  // deeper than  -- ../ reaches data/).
  var URL = "../data/vedanga/vyakarana/dhatupatha/data.json";
  var GANA = {1:"भ्वादि",2:"अदादि",3:"जुहोत्यादि",4:"दिवादि",5:"स्वादि",6:"तुदादि",7:"रुधादि",8:"तनादि",9:"क्र्यादि",10:"चुरादि"};
  var CHUNK = 250;

  var LS = {
    get:function(k,d){ try{ var v=localStorage.getItem("dge.dhatu."+k); return v===null?d:JSON.parse(v);}catch(e){return d;} },
    set:function(k,v){ try{ localStorage.setItem("dge.dhatu."+k, JSON.stringify(v)); }catch(e){} }
  };
  var state = {
    all:[], view:[], shown:0,
    script: LS.get("script","devanagari"),
    font: LS.get("font",18),
    gana: LS.get("gana",0),      // 0 = all
    pada: LS.get("pada",""),     // "" = all
    set: LS.get("set",""),       // "" = all | "seṭ" | "aniṭ" | "veṭ"
    karma: LS.get("karma",""),   // "" = all | "सकर्मक" | "अकर्मक" | "द्विकर्मक"
    sort: LS.get("sort","code"),
    q:"", openId: LS.get("open",null),
    vset: null,  // map of codes that have dhātuvṛtti entries (Mādhavīya/Kṣīra/Dhātupradīpa)
    lex: null,   // map of code -> dhatu_lexicon entry (AI multilingual meanings + pedagogy)
    bookmarks: LS.get("bookmarks", {}) // map of code -> true, DGE UI Contract "dhatuRoot" contextual action
  };
  var LEX_LANGS = ["English","Kannada","Telugu","Tamil","Malayalam","Hindi","Bengali","German","French","Russian","Chinese"];

  function $(s,r){ return (r||document).querySelector(s); }
  function esc(s){ return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;"); }
  function tl(t){ if(!t) return t; if(state.script==="devanagari"||!window.Sanscript) return t;
    try{ return window.Sanscript.t(t,"devanagari",state.script);}catch(e){return t;} }
  function iast(t){ try{ return window.Sanscript?window.Sanscript.t(t,"devanagari","iast"):"";}catch(e){return "";} }
  function padaClass(c){ return c==="P"?"var(--p)":c==="A"?"var(--a)":c==="U"?"var(--u)":"var(--muted)"; }
  function hashId(){ return decodeURIComponent((location.hash||"").replace(/^#/,"").trim()); }
  function setHash(id){ try{ if(("#"+id)!==location.hash) history.replaceState(null,"","#"+id); }catch(e){} }

  /* ---------- filter + sort ---------- */
  function recompute(){
    var q=state.q.trim().toLowerCase();
    state.view = state.all.filter(function(it){
      if(state.gana && it.gana!==state.gana) return false;
      if(state.pada && it.pada_code!==state.pada) return false;
      if(state.set && it.set!==state.set) return false;
      if(state.karma && it.karma!==state.karma) return false;
      if(q && it._hay.indexOf(q)<0) return false;
      return true;
    });
    var s=state.sort;
    state.view.sort(function(a,b){
      if(s==="usage"){ var ua=(state.usage&&state.usage[a.id]||[0])[0], ub=(state.usage&&state.usage[b.id]||[0])[0]; if(ua!==ub) return ub-ua; return a.id.localeCompare(b.id); }
      if(s==="dhatu") return a.dhatu.localeCompare(b.dhatu,"sa");
      if(s==="gana"){ if(a.gana!==b.gana) return a.gana-b.gana; return a.id.localeCompare(b.id); }
      return a.id.localeCompare(b.id); // code order
    });
    state.shown=0;
    $("#dh-count").textContent = state.view.length.toLocaleString()+" / "+state.all.length.toLocaleString();
  }

  /* ---------- render ---------- */
  function rowHTML(it){
    var devCls = state.script==="iast"?"":"deva";
    var open = (it.id===state.openId);
    var bookmarked = !!(state.bookmarks && state.bookmarks[it.id]);
    var pill = it.pada_code, pdev = tl(it.pada);
    return '<article class="row '+(open?"open":"")+(bookmarked?" bookmarked":"")+'" id="d-'+it.id+'" data-id="'+it.id+'" style="--tag:'+padaClass(it.pada_code)+'">'
      +'<div class="rhead">'
        +'<span class="rcode">'+(bookmarked?'★ ':'')+it.id+'</span>'
        +'<span class="rdha '+devCls+'">'+esc(tl(it.dhatu))+'</span>'
        +'<span class="rartha '+devCls+'">'+esc(tl(it.artha))+'</span>'
        +'<span class="rpada" style="background:'+padaClass(pill)+'" title="'+it.pada_iast+'">'+esc(pdev)+'</span>'
        +'<span class="rgana '+devCls+'">'+it.gana+' · '+esc(tl(GANA[it.gana]||""))+'</span>'
        +usagePill(it.id)
        +'<span class="rcaret">▸</span>'
      +'</div>'
      +'<div class="rbody">'+ (open?bodyHTML(it):"") +'</div>'
    +'</article>';
  }
  // 7 Sep 2026: corpus usage (tools/build_dhatu_prayoga_index.py → dhatu_prayoga/manifest.json).
  // 10 Sep 2026 the shape became [certain, shared, attested cells]: `certain` is
  // occurrences of forms only THIS root can write, `shared` occurrences of a
  // homograph several roots can. The pill and the sort show certain alone --
  // adding the two would be double-counting, since the same कृत्वा is in the
  // shared column of both 05.0007 and 08.0010.
  function usagePill(id){
    var u=state.usage&&state.usage[id];
    if(!u) return '';
    var certain=u[0]|0, shared=u[1]|0, cells=u[2]|0;
    var t=certain.toLocaleString()+' occurrences of forms only this root can write, across '+cells+' forms';
    if(shared) t+=' — plus '+shared.toLocaleString()+' on forms another root can write too, which cannot be attributed either way';
    return '<span class="rusage'+(certain===0&&shared?' rusage-shared':'')+'" title="'+t+' — open the row for examples">'+
      certain.toLocaleString()+'×'+(shared?'<sup title="shared with another root">~</sup>':'')+'</span>';
  }
  function bodyHTML(it){
    var devCls = state.script==="iast"?"":"deva";
    function kv(k,v){ return '<div class="kv"><div class="kk">'+k+'</div><div class="kvv '+devCls+'">'+v+'</div></div>'; }
    var h="";
    h+=kv("धातु · root", '<b>'+esc(tl(it.dhatu))+'</b> <span style="color:var(--muted)">('+esc(it.dhatu_slp)+')</span> · '+esc(iast(it.dhatu)));
    if(it.meanings && it.meanings.length){
      h+=kv("अर्थाः · meanings <span style='font-size:10px;color:var(--muted)'>("+it.meanings.length+")</span>",
            it.meanings.map(function(m){return '<span class="'+devCls+'">'+esc(tl(m))+'</span>';}).join(" &nbsp;·&nbsp; ")
            +' <span style="font-size:10.5px;color:var(--muted)">— traditional dhātupāṭha</span>');
    } else {
      h+=kv("अर्थः · meaning", esc(tl(it.artha)));
    }
    h+=kv("गणः · class", it.gana+" — "+esc(tl(GANA[it.gana]||"")));
    h+=kv("पदम् · voice", esc(tl(it.pada))+" ("+it.pada_iast+")"+(it.pada_trad?' · <span class="'+devCls+'">'+esc(tl(it.pada_trad))+'</span>':''));
    if(it.set) h+=kv("सेट्/अनिट् · iṭ", '<b>'+(it.set==="seṭ"?"सेट् (seṭ)":it.set==="aniṭ"?"अनिट् (aniṭ)":it.set==="veṭ"?"वेट् (veṭ)":esc(it.set))+'</b>');
    if(it.karma) h+=kv("कर्म · transitivity", '<b>'+esc(it.karma)+'</b>');
    if(it.anunasika_it) h+=kv("इत् · marker", "anunāsika it (nasal marker present in upadeśa)");
    h+='<div class="acts">'
      +'<a class="btn ai" href="prakriya.html#'+it.id+'">⚙ प्रक्रिया · तिङन्त</a>'
      +'<a class="btn" href="krdanta.html#'+it.id+'">कृदन्त forms</a>'
      +'<a class="btn" href="dhatuforms.html#'+it.id+'" title="सन्/णिच्/यङ्/यङ्लुक् व शुद्ध कर्मणि — full lakara tables">रूपाणि · सन्/णिच्/यङ्</a>'
      +'<a class="btn ai" href="rupasiddhi.html#'+it.id+'" title="उपसर्ग-योजना, सनादि, सर्वे 11 लकाराः, कृदन्त-declensions — every form derived live, step by step">✨ रूपसिद्धिः · उपसर्गैः</a>'
      +'<a class="btn" href="ashtadhyayi.html" title="open the sūtra reader">↔ अष्टाध्यायी</a>'
      +'<button class="btn" data-corpus-search="'+esc(it.dhatu)+'" title="Find every place this root appears across the DGE corpus">🔍 corpus occurrences</button>'
      +((state.usage&&state.usage[it.id])?'<a class="btn ai" href="prakriya.html#'+it.id+'" title="Every attested form of this root with example verses (धातुप्रयोगसूची)">📚 प्रयोगाः · '+state.usage[it.id][0].toLocaleString()+' in '+(state.usage[it.id][2]|0)+' forms</a>':'')
      +'<button class="btn" data-dh-more="'+it.id+'" title="More actions for this root" aria-label="More actions for '+esc(tl(it.dhatu))+'">⋯ More</button>'
      +'</div>';
    if(state.vset && state.vset[it.id]){
      h+='<div class="vrit" data-vrit="'+it.id+'"><button class="btn vrit-btn">📜 वृत्तयः · Mādhavīya · Kṣīra · Dhātupradīpa ›</button></div>';
    }
    if(state.lex && state.lex[it.id]){
      h+='<div class="lex" data-lex="'+it.id+'"><button class="btn lex-btn">🌐 बहुभाषा अर्थाः · AI Multilingual Meanings ›</button></div>';
    }
    return h;
  }
  function render(reset){
    var box=$("#dh-list");
    if(reset){ box.innerHTML=""; state.shown=0; }
    if(!state.view.length){ box.innerHTML='<div class="empty">No roots match these filters.</div>'; $("#dh-more").style.display="none"; return; }
    var end=Math.min(state.shown+CHUNK, state.view.length);
    var html="";
    for(var i=state.shown;i<end;i++) html+=rowHTML(state.view[i]);
    box.insertAdjacentHTML("beforeend", html);
    state.shown=end;
    $("#dh-more").style.display = state.shown<state.view.length ? "block" : "none";
    $("#dh-more").textContent = "show more ▾  ("+(state.view.length-state.shown).toLocaleString()+" left)";
  }
  function rerender(){ recompute(); render(true); }

  /* ---------- interactions ---------- */
  function toggleRow(id){
    var it=state.all.find(function(x){return x.id===id;}); if(!it) return;
    var el=$("#d-"+CSS.escape(id)); if(!el) return;
    var wasOpen=el.classList.contains("open");
    // close previous
    if(state.openId && state.openId!==id){ var prev=$("#d-"+CSS.escape(state.openId)); if(prev){ prev.classList.remove("open"); var b=prev.querySelector(".rbody"); if(b)b.innerHTML=""; } }
    if(wasOpen){ el.classList.remove("open"); el.querySelector(".rbody").innerHTML=""; state.openId=null; LS.set("open",null); setHash(""); }
    else { el.classList.add("open"); el.querySelector(".rbody").innerHTML=bodyHTML(it); state.openId=id; LS.set("open",id); setHash(id); }
  }

  function buildGanaChips(){
    var wrap=$("#dh-ganaChips"), html='<button class="chip" data-g="0">सर्वे · all</button>';
    for(var g=1;g<=10;g++) html+='<button class="chip" data-g="'+g+'">'+g+' '+GANA[g]+'</button>';
    wrap.innerHTML=html; syncGanaChips();
    wrap.addEventListener("click",function(e){ var c=e.target.closest(".chip"); if(!c)return;
      state.gana=parseInt(c.dataset.g,10); LS.set("gana",state.gana); syncGanaChips(); rerender(); });
  }
  function syncGanaChips(){ document.querySelectorAll("#dh-ganaChips .chip").forEach(function(c){ c.classList.toggle("on", parseInt(c.dataset.g,10)===state.gana); }); }
  function syncSetChips(){ document.querySelectorAll("[data-set]").forEach(function(c){ c.classList.toggle("on", c.dataset.set===state.set); }); }
  function syncKarmaChips(){ document.querySelectorAll("[data-karma]").forEach(function(c){ c.classList.toggle("on", c.dataset.karma===state.karma); }); }
  function syncPadaChips(){ document.querySelectorAll("[data-p]").forEach(function(c){
    var on=(c.dataset.p===state.pada);
    c.classList.toggle("on", on && c.dataset.p==="");
    c.classList.toggle("pon", on && c.dataset.p==="P");
    c.classList.toggle("aon", on && c.dataset.p==="A");
    c.classList.toggle("uon", on && c.dataset.p==="U");
  }); }

  function wire(){
    $("#dh-list").addEventListener("click",function(e){
      var mb=e.target.closest(".vrit-btn");
      if(mb){ e.stopPropagation(); loadVrittis(mb.closest(".vrit")); return; }
      var vt=e.target.closest(".vrit-tab");
      if(vt){ e.stopPropagation(); showVritti(vt.closest(".vrit"), vt.dataset.v); return; }
      var lb=e.target.closest(".lex-btn");
      if(lb){ e.stopPropagation(); showLexicon(lb.closest(".lex")); return; }
      var cs=e.target.closest("[data-corpus-search]");
      // "Search Library" is exactly what the reader's own global
      // search already answers for any word — reused rather than building a
      // second occurrence index that would drift from it (same reasoning as
      // the [data-occur] popover in intellisense.js).
      if(cs){ e.stopPropagation();
        if(typeof window.DGEGlobalSearch === "object" && window.DGEGlobalSearch.open) window.DGEGlobalSearch.open(cs.dataset.corpusSearch);
        return; }
      var mo=e.target.closest("[data-dh-more]");
      if(mo){ e.stopPropagation();
        var id=mo.getAttribute("data-dh-more"), it=state.all.find(function(x){return x.id===id;});
        if(it && typeof window.dgeOpenContextualMenu==="function"){
          window.dgeOpenContextualMenu("dhatuRoot", {id:id, label:tl(it.dhatu)+" — "+tl(it.artha)});
        }
        return; }
      if(e.target.closest(".acts")) return; // let derivation/reader links navigate
      var h=e.target.closest(".rhead"); if(h) toggleRow(h.parentElement.dataset.id);
    });
    $("#dh-more").addEventListener("click",function(){ render(false); });
    $("#dh-search").addEventListener("input",function(e){ state.q=e.target.value; rerender(); });
    document.querySelectorAll("[data-p]").forEach(function(c){ c.addEventListener("click",function(){
      state.pada=c.dataset.p; LS.set("pada",state.pada); syncPadaChips(); rerender(); }); });
    document.querySelectorAll("[data-set]").forEach(function(c){ c.addEventListener("click",function(){
      state.set=c.dataset.set; LS.set("set",state.set); syncSetChips(); rerender(); }); });
    document.querySelectorAll("[data-karma]").forEach(function(c){ c.addEventListener("click",function(){
      state.karma=c.dataset.karma; LS.set("karma",state.karma); syncKarmaChips(); rerender(); }); });
    $("#dh-sort").addEventListener("change",function(e){ state.sort=e.target.value; LS.set("sort",state.sort); rerender(); });
    $("#dh-scriptSeg").addEventListener("click",function(e){ var b=e.target.closest("button"); if(!b)return;
      [].forEach.call(e.currentTarget.children,function(x){x.classList.remove("on");}); b.classList.add("on");
      state.script=b.dataset.s; LS.set("script",state.script); rerender(); });
    $("#dh-fontUp").addEventListener("click",function(){ state.font=Math.min(26,state.font+1); LS.set("font",state.font); applyFont(); });
    $("#dh-fontDn").addEventListener("click",function(){ state.font=Math.max(14,state.font-1); LS.set("font",state.font); applyFont(); });
    $("#dh-theme").addEventListener("click",function(){ var d=document.body.classList.toggle("dark"); LS.set("dark",d); });
    window.addEventListener("hashchange",function(){ var id=hashId(); if(id && id!==state.openId) openById(id); });

    var srcT=$("#dh-srcToggle"), srcD=$("#dh-srcDetails");
    if(srcT&&srcD) srcT.addEventListener("click",function(){
      var open=srcD.hidden; srcD.hidden=!open; srcT.setAttribute("aria-expanded",String(open));
    });
    var fT=$("#dh-filtersToggle"), fBox=$("#dh-filters");
    if(fT&&fBox){
      var collapsed=LS.get("filtersCollapsed",false);
      fBox.classList.toggle("collapsed",collapsed);
      fT.textContent=collapsed?"▸":"▾"; fT.setAttribute("aria-expanded",String(!collapsed));
      fT.addEventListener("click",function(){
        collapsed=!collapsed; LS.set("filtersCollapsed",collapsed);
        fBox.classList.toggle("collapsed",collapsed);
        fT.textContent=collapsed?"▸":"▾"; fT.setAttribute("aria-expanded",String(!collapsed));
      });
    }
  }
  function applyFont(){ $("#dh-list").style.setProperty("font-size", state.font+"px"); }
  var _vcache={};
  function loadVrittis(box){
    if(!box || box.dataset.loaded) return;
    var code=box.dataset.vrit; box.dataset.loaded="1";
    box.innerHTML='<div class="mdhv-head">📜 वृत्तयः · dhātuvṛttis <span class="mdhv-lic">GPL · samsaadhanii/scl</span></div><div class="vrit-tabs"></div><div class="mdhv-text">loading…</div>';
    fetch("../data/vedanga/vyakarana/vritti/"+code+".json").then(function(r){if(!r.ok)throw 0;return r.json();}).then(function(d){
      _vcache[code]=d;
      var tabs=$(".vrit-tabs",box);
      tabs.innerHTML=d.vrittis.map(function(v,i){ return '<button class="vrit-tab'+(i===0?" on":"")+'" data-v="'+v.source+'">'+esc(v.name)+'</button>'; }).join("");
      showVritti(box, d.vrittis[0].source);
    }).catch(function(){ $(".mdhv-text",box).textContent="(could not load vṛtti text)"; });
  }
  // The source text is one continuous run with no line breaks at all —
  // confirmed against माधवीयधातुवृत्तिः on भू, 93,758 characters and not a
  // single \n — so it rendered as one dense, "incomprehensible" slab no
  // matter how short or long the excerpt actually was. Break after every
  // sentence-ending danda/double-danda into its own paragraph; .mdhv-text
  // already has white-space:pre-wrap; scrolling in its fixed-height box
  // handles a genuinely long excerpt (भू's) without needing to truncate or
  // guess at which part of the commentary is "relevant".
  function paragraphize(text){
    // [।॥]+ (not a single character) so "। ।" / "।।" — a double daṇḍa spelled
    // as two singles, common in this OCR'd source — breaks once, not into a
    // sentence followed by an orphan line holding just a lone daṇḍa.
    return String(text||"").replace(/([।॥][।॥\s]*)/g, "$1\n\n").trim();
  }
  // Node category letters (tools/build_vritti_nodes.py): r = this dhatu's
  // own forms present, s = sutra citations, m = named acharya opinions,
  // g = general discussion. "Relevant" for the default filter = contains r.
  var VCAT = { r:"रूपाणि", s:"सूत्रनिर्देशः", m:"आचार्यमतम्", g:"सामान्यचर्चा" };
  function showVritti(box, source){
    var code=box.dataset.vrit, d=_vcache[code]; if(!d) return;
    var v=d.vrittis.filter(function(x){return x.source===source;})[0]; if(!v) return;
    box.querySelectorAll(".vrit-tab").forEach(function(t){ t.classList.toggle("on",t.dataset.v===source); });
    var devCls = state.script==="iast"?"":"deva";
    var el=$(".mdhv-text",box); el.className="mdhv-text "+devCls;
    var author = v.author?('<div class="mdhv-author">['+esc(v.author)+']</div>'):"";
    if(!(v.nodes&&v.nodes.length)){
      el.innerHTML = author + esc(paragraphize(tl(v.text||"")));
    } else {
      // Long vrittis arrive pre-noded: offset-bounded chunks of the
      // untouched original text, each classified. Default to the
      // dhatu-relevant sections when the full text is genuinely long
      // (भू's Madhaviya entry is 94 KB, much of it general shastra
      // digression); सर्वम् is one tap away and says what it adds.
      var mode = box.dataset.vmode || ((v.text||"").length>5000 ? "rel" : "all");
      box.dataset.vmode = mode;
      var shown=0;
      var cards = v.nodes.map(function(n){
        var cats=n[2]||"g";
        if(mode==="rel" && cats.indexOf("r")===-1) return "";
        shown++;
        var tags=cats.split("").map(function(c){ return VCAT[c]?'<span class="vrit-tag vrit-tag-'+c+'">'+VCAT[c]+'</span>':""; }).join("");
        return '<div class="vrit-node">'+
          '<div class="vrit-tags">'+tags+'</div>'+
          esc(paragraphize(tl(v.text.slice(n[0],n[1]))))+'</div>';
      }).join("");
      var hidden = v.nodes.length - shown;
      el.innerHTML = author +
        '<div class="vrit-modes">'+
        '<button class="vrit-mode'+(mode==="rel"?" on":"")+'" data-vmode="rel">धातुविशिष्टम्</button>'+
        '<button class="vrit-mode'+(mode==="all"?" on":"")+'" data-vmode="all">सर्वम् · full text</button>'+
        (mode==="rel"&&hidden>0?'<span class="vrit-hidden">'+hidden+' general sections folded</span>':"")+
        '</div>' + cards;
      el.querySelectorAll(".vrit-mode").forEach(function(b){
        b.addEventListener("click",function(e){
          e.stopPropagation();
          box.dataset.vmode=b.dataset.vmode;
          showVritti(box, source);
        });
      });
    }
    if (typeof window.dgeScanForEntities === "function") {
      try { window.dgeScanForEntities(el); } catch (e) {}
    }
    if (typeof window.dgeScanForSutras === "function") {
      try { window.dgeScanForSutras(el); } catch (e) {}
    }
  }

  // Already fully in memory (state.lex, loaded once at boot) -- unlike
  // vṛttis there's no per-code file to fetch, just a reveal.
  function showLexicon(box){
    if(!box || box.dataset.loaded) return;
    box.dataset.loaded="1";
    var entry=state.lex[box.dataset.lex]; if(!entry) return;
    var m=entry.meanings||{};
    var rows=LEX_LANGS.filter(function(l){ return m[l] && m[l]!=="(uncertain)"; })
      .map(function(l){ return '<div class="lex-row"><b>'+esc(l)+'</b><span>'+esc(m[l])+'</span></div>'; }).join("");
    var sources=entry.sources_used||[];
    var tag=sources.length?"AI-interpreted (Gemini), grounded in real sources below":"AI-generated (Gemini), unreviewed";
    var h='<div class="lex-head">🌐 बहुभाषा अर्थाः · Multilingual Meanings <span class="lex-ai-tag">'+esc(tag)+'</span></div>'
      +'<div class="lex-langs">'+(rows||'<div class="lex-row"><span class="muted">no confident equivalents generated</span></div>')+'</div>';
    var ped=entry.pedagogy;
    if(ped && (ped.concept || (ped.scenarios||[]).length)){
      h+='<div class="lex-pedagogy">'+(ped.concept?'<p>'+esc(ped.concept)+'</p>':'');
      (ped.scenarios||[]).forEach(function(s){
        h+='<div class="lex-scenario"><b class="deva">'+esc(s.form)+'</b>'
          +(s.grammar_trigger?' <span class="muted">('+esc(s.grammar_trigger)+')</span>':'')
          +' — '+esc(s.meaning)
          +(s.example_sanskrit?'<div class="lex-example deva">'+esc(s.example_sanskrit)+'</div>':'')
          +(s.example_english?'<div class="lex-example-en">'+esc(s.example_english)+'</div>':'')
          +'</div>';
      });
      h+='</div>';
    }
    if(sources.length){
      h+='<div class="lex-sources muted">grounded in: '+sources.map(esc).join(" · ")+'</div>';
    }
    box.innerHTML=h;
  }

  /* DGE UI Contract retrofit (28 Aug 2026): a new "dhatuRoot" contextual-
     actions object type, the same pattern ashtadhyayi.js uses for "sutra"/
     "commentary" (window.dgeRegisterContextualActions, see
     DGE_UI_CONTRACT.md Part IV §3) -- actions with no existing home only:
     copy citation/entry text and a real localStorage-backed bookmark.
     Deliberately does NOT duplicate the derivation links, corpus-occurrence
     search, or vṛtti/lexicon reveal buttons already sitting inline in
     .acts — those already have a canonical home (critique #29's "one
     canonical home per action" rule). */
  function registerDhatuContextualActions(){
    if(typeof window.dgeRegisterContextualActions!=="function") return;
    window.dgeRegisterContextualActions({
      objectTypes:["dhatuRoot"],
      add:[
        {id:"bookmark", icon:"bookmark", label:"Bookmark this root", action:"dgeCtxDhatuBookmark"},
        {id:"copyCitation", icon:"copy", label:"Copy citation", action:"dgeCtxDhatuCopyCitation"},
        {id:"copyEntry", icon:"copy", label:"Copy full entry", action:"dgeCtxDhatuCopyEntry"}
      ]
    });
  }
  function dhatuCiteText(it){
    return "√"+tl(it.dhatu)+" ("+it.gana+". "+tl(GANA[it.gana]||"")+" gaṇa, "+tl(it.pada)+
      (it.set?", "+it.set:"")+") — \""+tl(it.artha)+"\" — Pāṇinīya Dhātupāṭha, DGE ("+
      location.href.split("#")[0]+"#"+it.id+")";
  }
  async function dgeCopyText(text, okMessage){
    try{
      if(navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(text);
      else { var ta=document.createElement("textarea"); ta.value=text; ta.style.position="fixed"; ta.style.left="-9999px";
        document.body.appendChild(ta); ta.select(); document.execCommand("copy"); document.body.removeChild(ta); }
      if(typeof window.showToast==="function") window.showToast(okMessage||"Copied.");
    } catch(e){ if(typeof window.showToast==="function") window.showToast("Could not copy — select and copy manually."); }
  }
  window.dgeCtxDhatuCopyCitation = function(ctx){
    var it=state.all.find(function(x){return x.id===ctx.id;}); if(!it) return;
    dgeCopyText(dhatuCiteText(it), "Citation copied.");
  };
  window.dgeCtxDhatuCopyEntry = function(ctx){
    var el=$("#d-"+CSS.escape(ctx.id)); var body=el&&el.querySelector(".rbody");
    var it=state.all.find(function(x){return x.id===ctx.id;}); if(!it) return;
    var text=(body&&body.textContent.trim())?body.textContent.replace(/\s+/g," ").trim():dhatuCiteText(it);
    dgeCopyText(text, "Entry copied.");
  };
  window.dgeCtxDhatuBookmark = function(ctx){
    var id=ctx.id; if(!id) return;
    state.bookmarks[id] = !state.bookmarks[id];
    LS.set("bookmarks", state.bookmarks);
    var row=$("#d-"+CSS.escape(id));
    if(row){
      row.classList.toggle("bookmarked", !!state.bookmarks[id]);
      var codeEl=row.querySelector(".rcode");
      if(codeEl) codeEl.textContent=(state.bookmarks[id]?"★ ":"")+id;
    }
    if(typeof window.showToast==="function") window.showToast(state.bookmarks[id]?"Bookmarked.":"Bookmark removed.");
  };

  function openById(id){
    var it=state.all.find(function(x){return x.id===id;}); if(!it) return;
    // set the open target BEFORE rendering so only this row renders open
    state.openId=id; LS.set("open",id);
    // clear filters so the target is guaranteed in view
    state.gana=0; state.pada=""; state.q=""; $("#dh-search").value=""; LS.set("gana",0); LS.set("pada","");
    syncGanaChips(); syncPadaChips(); recompute();
    var pos=state.view.findIndex(function(x){return x.id===id;});
    render(true);
    while(state.shown<=pos && state.shown<state.view.length) render(false);
    var el=$("#d-"+CSS.escape(id));
    if(el){ el.scrollIntoView({behavior:"smooth",block:"center"}); setHash(id); }
  }

  function boot(){
    if(LS.get("dark",false)) document.body.classList.add("dark");
    var ss=$("#dh-scriptSeg"); if(ss) ss.querySelectorAll("button").forEach(function(b){ b.classList.toggle("on",b.dataset.s===state.script); });
    $("#dh-sort").value=state.sort;
    buildGanaChips(); syncPadaChips(); syncSetChips(); syncKarmaChips(); wire(); applyFont();
    registerDhatuContextualActions();
    fetch("../data/vedanga/vyakarana/vritti/index.json").then(function(r){return r.ok?r.json():null;}).then(function(idx){
      state.vset={}; if(idx) (idx.available||[]).forEach(function(c){ state.vset[c]=1; });
      // if a row is already open, re-render its body so the vṛtti toggle appears
      if(state.openId){ var el=$("#d-"+CSS.escape(state.openId)); var it=state.all.find(function(x){return x.id===state.openId;});
        if(el&&it){ var b=el.querySelector(".rbody"); if(b) b.innerHTML=bodyHTML(it); } }
    }).catch(function(){ state.vset={}; });
    fetch("../data/vedanga/vyakarana/dhatu_prayoga/manifest.json").then(function(r){return r.ok?r.json():null;}).then(function(m){
      state.usage=(m&&m.byDhatu)||{};
      if(state.all.length){ recompute(); render(true); }
    }).catch(function(){ state.usage={}; });
    fetch("../data/vedanga/vyakarana/dhatu_lexicon/data.json").then(function(r){return r.ok?r.json():null;}).then(function(d){
      state.lex={}; if(d) (d.items||[]).forEach(function(it){ state.lex[it.id]=it; });
      if(state.openId){ var el=$("#d-"+CSS.escape(state.openId)); var it=state.all.find(function(x){return x.id===state.openId;});
        if(el&&it){ var b=el.querySelector(".rbody"); if(b) b.innerHTML=bodyHTML(it); } }
    }).catch(function(){ state.lex={}; });
    fetch(URL).then(function(r){ if(!r.ok) throw new Error(r.status); return r.json(); }).then(function(d){
      state.all=(d.items||[]).map(function(it){
        it._hay=((it.dhatu||"")+" "+(it.artha||"")+" "+((it.meanings||[]).join(" "))+" "+(it.dhatu_slp||"")+" "+iast(it.dhatu)+" "+iast(it.artha)+" "+it.id).toLowerCase();
        return it;
      });
      $("#dh-total").textContent = state.all.length.toLocaleString();
      var q0=new URLSearchParams(location.search).get("q");
      if(q0){ state.q=q0; $("#dh-search").value=q0; }
      recompute();
      var h0=hashId();
      if(h0 && state.all.some(function(x){return x.id===h0;})){ openById(h0); }
      else { render(true); }
    }).catch(function(e){ $("#dh-list").innerHTML='<div class="empty">Failed to load dhātupāṭha data ('+e+'). Serve from the  folder.</div>'; });
  }
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded",boot); else boot();
})();
