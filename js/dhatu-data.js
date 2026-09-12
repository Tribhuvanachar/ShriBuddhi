/* ==========================================================================
 * DGE · dhatu-data.js — shared data adapter for the Dhātu "page" + "dialogue"
 * views (the single-root conjugation explorer / modal).
 *
 * The guru-data.js analogue for verb roots: ONE module fetched by every
 * selectable view (dge/vyakarana/dhatu/{view1..3}.html and the dialogue
 * chooser) so each layout renders the SAME real, precomputed corpus their own
 * way — never a client-side re-derivation. All data is committed (₹0):
 *   - prakriya/<gaṇa>/<code>.json : {code,dhatu,artha,gana,pada,forms,steps,krt}
 *       forms["<Lakara>.<P><V>"] = the 3×3 tiṅanta grid (P/V 0-2)
 *       steps[key] = [{t, s:[[sūtraCode, formAfterThatStep?], ...]}]  (the real
 *         ~20-step prakriyā; a sūtra code opens in intellisense.js)
 *       krt = [{t, k, s:[...]}]  (kṛdanta forms)
 *   - dhatupatha/data.json : 2229 roots' meta (dhatu, artha, gaṇa, pada, seṭ, karma)
 *   - dhatu_lexicon/data.json : multilingual meanings + pedagogy per root
 *   - dhatuforms/<code>.json : ṇic / san / yaṅ / yaṅluk / śuddha secondary paradigms
 *
 * Nothing is generated here: the vidyut precompute is the single source of
 * truth (a client re-derivation would drift — see tools/build_prakriya.py).
 * Depth-independent: all URLs resolve from THIS script's own src.
 * ========================================================================== */
(function () {
  "use strict";

  var SELF = (document.currentScript && document.currentScript.src) || "";
  var VBASE = SELF ? SELF.replace(/js\/dhatu-data\.js.*$/, "data/vedanga/vyakarana/") : "../data/vedanga/vyakarana/";

  function esc(s){ return String(s==null?"":s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }

  var LAKARA = { Lat:"लट्", Lit:"लिट्", Lut:"लुट्", Lrt:"लृट्", Lot:"लोट्", Lan:"लङ्", VidhiLin:"विधिलिङ्", Lun:"लुङ्" };
  var LAKARA_EN = { Lat:"present", Lit:"perfect", Lut:"periphrastic future", Lrt:"future", Lot:"imperative", Lan:"imperfect", VidhiLin:"optative", Lun:"aorist" };
  var LAKARA_ORDER = ["Lat","Lit","Lut","Lrt","Lot","Lan","VidhiLin","Lun"];
  var PURUSHA = ["प्रथमपुरुषः","मध्यमपुरुषः","उत्तमपुरुषः"];
  var PURUSHA_EN = ["3rd","2nd","1st"];
  var VACANA = ["एकवचनम्","द्विवचनम्","बहुवचनम्"];
  var VACANA_EN = ["sing.","dual","plural"];
  var KRT = { kta:"क्त", ktavatu:"क्तवतु", ktvA:"क्त्वा", tumun:"तुमुन्", Satf:"शतृ", SAnac:"शानच्",
              tavya:"तव्य", anIyar:"अनीयर्", yat:"यत्", Rvul:"ण्वुल्", tfc:"तृच्", lyuw:"ल्युट्" };
  var KRT_EN = { kta:"past passive participle", ktavatu:"past active participle", ktvA:"absolutive",
              tumun:"infinitive", Satf:"present participle, parasmaipada", SAnac:"present participle, ātmanepada",
              tavya:"gerundive", anIyar:"gerundive", yat:"gerundive", Rvul:"agent noun", tfc:"agent noun", lyuw:"action noun" };
  var GANA = {1:"भ्वादिः",2:"अदादिः",3:"जुहोत्यादिः",4:"दिवादिः",5:"स्वादिः",6:"तुदादिः",7:"रुधादिः",8:"तनादिः",9:"क्र्यादिः",10:"चुरादिः"};
  var SECONDARY = { shuddha:"शुद्धः", nich:"णिजन्तः (causative)", san:"सन्नन्तः (desiderative)", yang:"यङन्तः (intensive)", yangluk:"यङ्लुगन्तः" };

  function u(rel){ return VBASE + rel; }
  function fetchJSON(url){ return fetch(url,{cache:"force-cache"}).then(function(r){ if(!r.ok) throw new Error(url+" "+r.status); return r.json(); }); }

  // ----- per-root conjugation (prakriya precompute) ------------------------
  var _rootCache = {};
  function loadRoot(code){
    code=String(code||"").trim();
    if(!/^\d{2}\.\d{4}$/.test(code)) return Promise.reject(new Error("bad root code: "+code));
    if(_rootCache[code]) return _rootCache[code];
    var gana=code.split(".")[0];
    _rootCache[code]=fetchJSON(u("prakriya/"+gana+"/"+code+".json"));
    return _rootCache[code];
  }
  var _manifestPromise=null;
  function loadManifest(){ if(!_manifestPromise) _manifestPromise=fetchJSON(u("prakriya/manifest.json")).catch(function(){return {};}); return _manifestPromise; }

  // ----- root list + meta (dhatupatha) -------------------------------------
  var _dpPromise=null;
  function loadDhatupatha(){
    if(_dpPromise) return _dpPromise;
    _dpPromise=fetchJSON(u("dhatupatha/data.json")).then(function(d){
      var items=d.items||d||[]; var byId={};
      items.forEach(function(it){ byId[it.id]=it; });
      return { items:items, byId:byId, count:items.length };
    });
    return _dpPromise;
  }
  // ----- multilingual meanings (lexicon, one file, index by id) ------------
  var _lxPromise=null;
  function loadLexiconIndex(){
    if(_lxPromise) return _lxPromise;
    _lxPromise=fetchJSON(u("dhatu_lexicon/data.json")).then(function(d){
      var items=d.items||d||[]; var byId={}; items.forEach(function(it){ byId[it.id]=it; }); return byId;
    }).catch(function(){ return {}; });
    return _lxPromise;
  }
  function lexiconFor(code){ return loadLexiconIndex().then(function(idx){ return idx[code]||null; }); }
  // ----- secondary paradigms (ṇic/san/yaṅ…) --------------------------------
  function loadDhatuforms(code){ return fetchJSON(u("dhatuforms/"+code+".json")).catch(function(){ return null; }); }

  // ----- pure data accessors over a loaded root `d` ------------------------
  function availableLakaras(d){
    return LAKARA_ORDER.filter(function(l){ return Object.keys(d.forms||{}).some(function(k){ return k.indexOf(l+".")===0; }); });
  }
  function hasSteps(d, lakara){ return d.steps && Object.prototype.hasOwnProperty.call(d.steps, lakara+".00"); }
  // 3×3 grid for a lakāra: rows = puruṣa (0-2), cols = vacana (0-2).
  function gridFor(d, lakara){
    var g=[];
    for(var p=0;p<3;p++){ var row=[]; for(var v=0;v<3;v++){ var key=lakara+"."+p+v; var f=(d.forms||{})[key];
      row.push({ key:key, p:p, v:v, forms:(f&&f.length)?f:null, hasSteps:!!(d.steps&&d.steps[key]) }); } g.push(row); }
    return g;
  }
  function stepsFor(d, key){ return (d.steps||{})[key] || null; }  // -> [{t, s:[...]}]
  function meta(d){ return { code:d.code, dhatu:d.dhatu, artha:d.artha||"", gana:d.gana, ganaName:GANA[d.gana]||"", pada:d.pada||"" }; }
  function krtList(d){ return d.krt||[]; }

  /* Canonical step renderer (delta-encoded steps -> HTML). Emits
     .dge-sutra-ref spans that the loaded intellisense.js resolves into
     sūtra popovers — views should use this for the prakriyā ladder so refs
     stay tappable, then style .pk-steps/.pk-code/.pk-result themselves. */
  function stepsHtml(steps){
    var last="";
    var items=(steps||[]).map(function(st){
      var code=st[0], changed=st.length>1; if(changed) last=st[1];
      var isSutra=/^[1-8]\.[1-4]\.\d{1,3}$/.test(code);
      return '<li class="'+(changed?'pk-step-changed':'pk-step-same')+'">'+
        (isSutra
          ? '<span class="dge-sutra-ref pk-code" data-sutra="'+esc(code)+'" role="button" tabindex="0">'+esc(code)+'</span>'
          : '<span class="pk-code pk-code-plain">'+esc(code)+'</span>')+
        '<span class="pk-result deva">'+esc(last)+'</span>'+
        (changed?'':'<span class="pk-step-note">no visible change — this rule marks the form for a later step</span>')+
        '</li>';
    }).join("");
    var anySame=(steps||[]).some(function(st){ return st.length<=1; });
    return '<div class="pk-steps-block">'+
      (anySame?'<label class="pk-steps-toggle"><input type="checkbox" class="pk-all-steps"> Show every step, including ones with no visible change</label>':'')+
      '<ol class="pk-steps pk-main-only">'+items+'</ol></div>';
  }

  window.DGE_DHATU = {
    loadRoot: loadRoot, loadManifest: loadManifest,
    loadDhatupatha: loadDhatupatha, lexiconFor: lexiconFor, loadDhatuforms: loadDhatuforms,
    availableLakaras: availableLakaras, hasSteps: hasSteps, gridFor: gridFor, stepsFor: stepsFor,
    meta: meta, krtList: krtList, stepsHtml: stepsHtml, esc: esc,
    LAKARA: LAKARA, LAKARA_EN: LAKARA_EN, LAKARA_ORDER: LAKARA_ORDER,
    PURUSHA: PURUSHA, PURUSHA_EN: PURUSHA_EN, VACANA: VACANA, VACANA_EN: VACANA_EN,
    KRT: KRT, KRT_EN: KRT_EN, GANA: GANA, SECONDARY: SECONDARY,
    base: VBASE
  };
})();
