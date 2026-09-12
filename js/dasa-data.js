/* ==========================================================================
 * DGE · dasa-data.js — shared data adapter for the Dāsa Sāhitya "views".
 *
 * The guru-data.js analogue for the Haridāsa-composition browser: ONE module
 * fetched by every selectable view (dge/dasa-sahitya/views/view1..3.html) so
 * the three layouts render the SAME real corpus (15,863 compositions across
 * 152 composer files) their own way. Lifted from the canonical
 * dge/dasa-sahitya/index.html so a view can never drift from the real page:
 * manifest + lazy per-composer load, the script/stanza fallbacks
 * (transliteration coverage is only ~8%), word-tap → Kosha, composer → the
 * real guru-paramparā people.json sheet, and the contextual-actions menu.
 *
 * Depth-independent: data + people paths resolve from THIS script's own src,
 * and window.KOSHA_DATA_BASE is set here (before kosha.js loads) so the
 * viewer never has to hardcode a depth-specific path.
 * ========================================================================== */
(function () {
  "use strict";

  var SELF = (document.currentScript && document.currentScript.src) || "";
  // .../dge/js/dasa-data.js  ->  .../dge/
  var DGE_ROOT = SELF ? SELF.replace(/js\/dasa-data\.js.*$/, "") : "../";
  var BASE = DGE_ROOT + "data/DvaitaVedanta/Itara/DasaSahitya";
  var PEOPLE_URL = DGE_ROOT + "guru-parampara/data/people.json";
  // kosha.js resolves this against the page URL if it's relative, but an
  // absolute (script-derived) base is depth-proof; set it before kosha.js.
  try { if (!window.KOSHA_DATA_BASE) window.KOSHA_DATA_BASE = DGE_ROOT + "data/kosha"; } catch (e) {}

  var FORM_LABELS = {pada:"Pada",suladi:"Suladi",ugabhoga:"Ugabhoga",devaranama:"Devaranama",
    aarati:"Aarati",mangala:"Mangala",kolu:"Kolu",shobhane:"Shobhane",laali:"Laali",
    dashavatara:"Dashavatara",sampradaya:"Sampradaya",kavya:"Kavya",
    mundige:"Mundige",dandaka:"Dandaka",mixed:"Mixed",other:"Other"};

  var state = { manifest:null, records:[], loaded:{} };

  function esc(s){ return (s||"").replace(/[&<>]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;'}[c];}); }
  function escAttr(s){ return esc(s).replace(/"/g,'&quot;'); }

  function prefGet(k,d){ try{ var v=JSON.parse(localStorage.getItem('dasa_'+k)); return v==null?d:v; }catch(e){return d;} }
  function prefSet(k,v){ try{ localStorage.setItem('dasa_'+k,JSON.stringify(v)); }catch(e){} }
  function compStateGet(id){ return prefGet('compstate_'+id, {fav:false,status:null,doubt:false}); }
  function compStateSet(id,patch){ var s=compStateGet(id); Object.assign(s,patch); prefSet('compstate_'+id,s); return s; }

  // Wrap every non-whitespace run in a tappable span (word-tap -> Kosha) while
  // escaping the line. White-space:pre-wrap on the container keeps line breaks.
  function tokenizeLine(line){
    return (line||"").replace(/(\S+)/g,function(w){ return '<span class="dasa-word" data-w="'+escAttr(w)+'">'+esc(w)+'</span>'; });
  }

  // ----- loading -----------------------------------------------------------
  var _manifestPromise = null;
  function load(){
    if(_manifestPromise) return _manifestPromise;
    _manifestPromise = fetch(BASE+"/index.json",{cache:"no-store"}).then(function(r){
      if(!r.ok) throw new Error("index.json "+r.status); return r.json();
    }).then(function(m){ state.manifest=m; return m; });
    return _manifestPromise;
  }
  function loadComposer(slug){
    if(state.loaded[slug]==="ok") return Promise.resolve();
    var entry=(state.manifest.composers||[]).find(function(c){return c.slug===slug;});
    if(!entry) return Promise.resolve();
    return fetch(BASE+"/"+entry.file,{cache:"no-store"}).then(function(r){ return r.json(); }).then(function(data){
      var recs=(data.items||data.compositions||[]).map(function(r){ r._slug=slug; return r; });
      state.records=state.records.filter(function(r){return r._slug!==slug;}).concat(recs);
      state.loaded[slug]="ok";
    }).catch(function(){ state.loaded[slug]="err"; });
  }
  function loadAll(onProgress){
    var comps=state.manifest.composers||[];
    return comps.reduce(function(p,c){
      return p.then(function(){ return loadComposer(c.slug); }).then(function(){ if(onProgress) onProgress(); });
    }, Promise.resolve());
  }

  // ----- record helpers ----------------------------------------------------
  function scriptTitle(r, script){
    var t=r.title||{};
    if(script==="iast") return t.iast||t.latin||t.kn||"(untitled)";
    if(script==="devanagari") return t.devanagari||t.kn||t.latin||"(untitled)";
    return t.kn||t.latin||"(untitled)";
  }
  function firstLine(r){ var k=(r.text&&r.text.kannada)||[]; return (k[0]&&k[0][0])||""; }
  function stanzasFor(r, script){
    var T=r.text||{};
    if(script==="iast" && (T.iast||[]).some(function(s){return s.length;})) return T.iast;
    if(script==="devanagari" && (T.devanagari||[]).some(function(s){return s.length;})) return T.devanagari;
    return T.kannada||[];
  }
  function matches(r, f){
    if(f.form && f.form!=="all" && r.form!==f.form) return false;
    if(f.q){
      var q=f.q.toLowerCase();
      var hay=[scriptTitle(r,f.script),r.composer,r.deity,(r.title&&r.title.iast),firstLine(r),(r.tags||[]).join(" ")].join(" ").toLowerCase();
      if(hay.indexOf(q)<0) return false;
    }
    return true;
  }
  function groupKey(r, group, script){
    if(group==="deity") return r.deity||"—";
    if(group==="form") return FORM_LABELS[r.form]||r.form;
    if(group==="alpha"){ var t=scriptTitle(r,script); return (t[0]||"#").toUpperCase(); }
    return r.composer||"—";
  }

  // ----- composition contextual menu + ctx handlers ------------------------
  function toast(m){ if(typeof window.dgeDasaToast==="function"){ window.dgeDasaToast(m); }
    else if(typeof window.showToast==="function"){ window.showToast(m); } }
  function openCompositionMenu(rec, script){
    if(typeof window.dgeOpenContextualMenu!=="function"){ toast('Actions menu is not available yet.'); return; }
    window.dgeOpenContextualMenu('composition',{id:rec.id,rec:rec,label:scriptTitle(rec,script||'kn')});
  }
  function compCitation(rec){ return scriptTitle(rec,'kn')+' — '+(rec.composer||'ದಾಸ ಸಾಹಿತ್ಯ')+' · DGE Dāsa Sāhitya ('+rec.id+')'; }
  function copyToClipboard(text){
    try{
      if(navigator.clipboard && window.isSecureContext){ navigator.clipboard.writeText(text); }
      else{ var ta=document.createElement('textarea'); ta.value=text; ta.style.position='fixed'; ta.style.left='-9999px';
        document.body.appendChild(ta); ta.select(); document.execCommand('copy'); document.body.removeChild(ta); }
      toast('Copied.');
    }catch(e){ toast('Could not copy — select and copy manually.'); }
  }
  var _onChange=null; // views register a re-render callback so state changes reflect
  window.dgeCtxCompFavorite=function(ctx){ var w=compStateGet(ctx.id).fav; compStateSet(ctx.id,{fav:!w}); toast(w?'Removed from favorites.':'Added to favorites.'); if(_onChange)_onChange(); };
  window.dgeCtxCompPractice=function(ctx){ var c=compStateGet(ctx.id).status, n=c==='practice'?null:'practice'; compStateSet(ctx.id,{status:n}); toast(n?'Marked needs practice.':'Cleared status.'); if(_onChange)_onChange(); };
  window.dgeCtxCompCompleted=function(ctx){ var c=compStateGet(ctx.id).status, n=c==='done'?null:'done'; compStateSet(ctx.id,{status:n}); toast(n?'Marked completed.':'Cleared status.'); if(_onChange)_onChange(); };
  window.dgeCtxCompDoubt=function(ctx){ var w=compStateGet(ctx.id).doubt; compStateSet(ctx.id,{doubt:!w}); toast(w?'Doubt cleared.':'Marked doubt.'); if(_onChange)_onChange(); };
  window.dgeCtxCompPlay=function(){ toast('No audio recording is linked to this composition yet.'); };
  window.dgeCtxShowCompReferences=function(ctx){
    var card=document.querySelector('[data-cid="'+CSS.escape(ctx.id)+'"]');
    var ref=card && card.querySelector('.dge-entity-ref, .dge-sutra-ref');
    if(ref){ ref.click(); return; } toast('No recognized cross-references in this composition yet.');
  };
  window.dgeCtxCompShare=function(ctx){
    var rec=ctx.rec; if(!rec) return;
    var text=compCitation(rec), url=location.href.split('#')[0]+'#'+encodeURIComponent(rec.id);
    if(navigator.share){ navigator.share({title:scriptTitle(rec,'kn'),text:text,url:url}).catch(function(){}); return; }
    copyToClipboard(text+'\n'+url);
  };

  // ----- composer profile sheet (real people.json fields only) -------------
  var peoplePromise=null;
  function loadPeople(){
    if(!peoplePromise) peoplePromise=fetch(PEOPLE_URL,{cache:'no-store'})
      .then(function(r){ return r.ok?r.json():null; }).then(function(d){ return (d&&d.people)||[]; }).catch(function(){ return []; });
    return peoplePromise;
  }
  function normName(s){ return (s||'').normalize('NFKD').replace(/[̀-ͯ]/g,'').toLowerCase().replace(/[^a-z]/g,''); }
  function normComposer(s){ return normName(s).replace(/dasaru$/,'dasa'); }
  function matchPerson(people,composer){
    var key=normComposer(composer); if(!key) return null;
    return people.find(function(p){ return normComposer(p.name)===key || normComposer(p.id)===key; }) || null;
  }
  function ensureComposerSheetEl(onWorks){
    var el=document.getElementById('dasaComposerSheet'); if(el) return el;
    el=document.createElement('div'); el.className='modal-overlay'; el.id='dasaComposerSheet';
    el.innerHTML='<div class="modal-content"><div class="modal-header-sticky">'+
      '<h4 id="dasaComposerSheetTitle" style="margin:0;color:var(--accent-red);font-size:15px;"></h4>'+
      '<button class="btn-sm" onclick="window.closeModal(\'dasaComposerSheet\')">✖ Close</button></div>'+
      '<div class="modal-body" id="dasaComposerSheetBody"></div></div>';
    document.body.appendChild(el);
    el.addEventListener('click',function(e){ if(e.target===el && typeof window.closeModal==='function') window.closeModal('dasaComposerSheet'); });
    el.addEventListener('click',function(e){
      var btn=e.target.closest('[data-works-slug]'); if(!btn) return;
      if(typeof window.closeModal==='function') window.closeModal('dasaComposerSheet');
      if(onWorks) onWorks(btn.dataset.worksSlug, btn.dataset.worksName);
    });
    return el;
  }
  function openComposerSheet(composer, slug, onWorks){
    if(!composer){ toast('No composer on this composition.'); return; }
    ensureComposerSheetEl(onWorks);
    var titleEl=document.getElementById('dasaComposerSheetTitle'), bodyEl=document.getElementById('dasaComposerSheetBody');
    titleEl.textContent=composer; bodyEl.innerHTML='<p class="tl">Loading…</p>';
    if(typeof window.openModal==='function') window.openModal('dasaComposerSheet');
    var manifestEntry=(state.manifest.composers||[]).find(function(c){return c.slug===slug;});
    var worksCount=manifestEntry?manifestEntry.count:'—';
    loadPeople().then(function(people){
      var p=matchPerson(people,composer), html='';
      if(p){
        html+='<div class="composer-badges">'+
          (p.period?'<span class="badge">'+esc(p.period)+'</span>':'')+
          (p.matha?'<span class="badge">'+esc(p.matha)+' matha</span>':'')+
          (p.confidence?'<span class="badge">confidence: '+esc(p.confidence)+'</span>':'')+'</div>';
        if(p.titles && p.titles.length) html+='<p class="tl"><b>Titles:</b> '+p.titles.map(esc).join(', ')+'</p>';
        html+='<p class="composer-note">This is the real guru-paramparā record for this composer — only the fields DGE currently has are shown.</p>';
      }else{
        html+='<p class="composer-note">No linked guru-paramparā profile found yet for "'+esc(composer)+'".</p>';
      }
      html+='<button type="button" class="btn-sm" style="margin-top:12px;width:100%;padding:10px;" data-works-slug="'+escAttr(slug||'')+'" data-works-name="'+escAttr(composer)+'">📖 See this composer\'s works ('+worksCount+')</button>';
      bodyEl.innerHTML=html;
    });
  }

  // Delegated click handler for a view's list container: word -> Kosha,
  // composer-link -> sheet, .card-actions-btn -> composition menu. The view
  // passes its records lookup + script + onWorks/onChange callbacks.
  function attachListActions(listEl, opts){
    opts=opts||{}; if(opts.onChange) _onChange=opts.onChange;
    listEl.addEventListener('click',function(e){
      var actBtn=e.target.closest('.card-actions-btn');
      if(actBtn){ e.preventDefault(); e.stopPropagation();
        var rec=state.records.find(function(r){return r.id===actBtn.dataset.cid;});
        if(rec) openCompositionMenu(rec, opts.script&&opts.script()); return; }
      var compBtn=e.target.closest('.composer-link');
      if(compBtn){ e.preventDefault(); e.stopPropagation();
        openComposerSheet(compBtn.dataset.composer, compBtn.dataset.slug, opts.onWorks); return; }
      var wordEl=e.target.closest('.dasa-word');
      if(wordEl){
        var sel=window.getSelection(); if(sel && sel.toString().trim().length>0) return;
        if(typeof window.dgeOpenKosha==='function') window.dgeOpenKosha(wordEl.dataset.w);
        else toast('Kosha lookup is not available yet.');
      }
    });
  }

  window.DGE_DASA = {
    load: load, loadComposer: loadComposer, loadAll: loadAll,
    get manifest(){ return state.manifest; },
    get records(){ return state.records; },
    get loaded(){ return state.loaded; },
    FORM_LABELS: FORM_LABELS,
    esc: esc, escAttr: escAttr, tokenizeLine: tokenizeLine,
    scriptTitle: scriptTitle, firstLine: firstLine, stanzasFor: stanzasFor,
    matches: matches, groupKey: groupKey,
    compStateGet: compStateGet, compStateSet: compStateSet,
    prefGet: prefGet, prefSet: prefSet,
    openCompositionMenu: openCompositionMenu, openComposerSheet: openComposerSheet,
    attachListActions: attachListActions,
    setOnChange: function(fn){ _onChange=fn; },
    base: BASE, dgeRoot: DGE_ROOT
  };
})();
