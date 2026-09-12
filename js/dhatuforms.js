/* ==========================================================================
 * DGE · रूपाणि (dhatuforms.html) — full lakara paradigm tables for a root's
 * secondary conjugations (सन्/णिच्/यङ्/यङ्लुक्) and शुद्ध कर्मणि, sourced from
 * ashtadhyayi-com/data (github.com/ashtadhyayi-com/data, used with credit
 * per its README). शुद्ध कर्तरि is NOT shown here: प्रक्रिया already derives
 * it live from vidyut-prakriya with its full step-by-step derivation — see
 * tools/build_dhatu_forms.py for why duplicating it here would be a real risk,
 * not just extra bytes.
 * ========================================================================== */
(function () {
  "use strict";
  // Page-relative to vyakarana/dhatuforms.html (Phase 10: moved one
  // directory deeper than  -- ../ reaches data/).
  var DHATU_URL = "../data/vedanga/vyakarana/dhatupatha/data.json";
  var FORMS_URL = "../data/vedanga/vyakarana/dhatuforms/";
  var LEXICON_URL = "../data/vedanga/vyakarana/dhatu_lexicon/data.json";
  var LEX_LANGS = ["English","Kannada","Telugu","Tamil","Malayalam","Hindi","Bengali","German","French","Russian","Chinese"];
  var GANA={1:"भ्वादि",2:"अदादि",3:"जुहोत्यादि",4:"दिवादि",5:"स्वादि",6:"तुदादि",7:"रुधादि",8:"तनादि",9:"क्र्यादि",10:"चुरादि"};

  // display order; each entry is [ganaKey, padaKey, label]
  var VOICE_ORDER = [
    ["shuddha","karmani","शुद्ध कर्मणि"],
    ["san","kartari","सन् कर्तरि (desiderative)"],
    ["san","karmani","सन् कर्मणि"],
    ["nich","kartari","णिच् कर्तरि (causative)"],
    ["nich","karmani","णिच् कर्मणि"],
    ["yang","kartari","यङ् कर्तरि (intensive)"],
    ["yang","karmani","यङ् कर्मणि"],
    ["yangluk","kartari","यङ्लुक् कर्तरि"],
    ["yangluk","karmani","यङ्लुक् कर्मणि"]
  ];
  // lakara key pairs: [p-prefixed key, a-prefixed key, Devanagari label]
  var LAKARAS = [
    ["plat","alat","लट्"], ["plit","alit","लिट्"], ["plut","alut","लुट्"],
    ["plrut","alrut","लृट्"], ["plot","alot","लोट्"], ["plang","alang","लङ्"],
    ["pvidhiling","avidhiling","विधिलिङ्"], ["pashirling","aashirling","आशीर्लिङ्"],
    ["plung","alung","लुङ्"], ["plrung","alrung","लृङ्"]
  ];
  var PERSONS=["प्रथमः","मध्यमः","उत्तमः"], NUMS=["एकवचनम्","द्विवचनम्","बहुवचनम्"];

  function $(s,r){ return (r||document).querySelector(s); }
  function esc(s){ return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;"); }
  function hashId(){ return decodeURIComponent((location.hash||"").replace(/^#/,"").trim()); }

  function lakaraKey(pair, forms){ return (forms[pair[0]]!==undefined) ? pair[0] : (forms[pair[1]]!==undefined ? pair[1] : null); }

  function lexiconHtml(entry){
    if(!entry) return "";
    var m=entry.meanings||{};
    var rows=LEX_LANGS.filter(function(l){ return m[l] && m[l]!=="(uncertain)"; })
      .map(function(l){ return '<div class="lex-row"><b>'+esc(l)+'</b><span>'+esc(m[l])+'</span></div>'; }).join("");
    if(!rows) return "";
    var sources=entry.sources_used||[];
    var tag=sources.length?"AI-interpreted (Gemini), grounded in real sources below":"AI-generated (Gemini), unreviewed";
    var h='<div class="lex-head">🌐 बहुभाषा अर्थाः · Multilingual Meanings <span class="lex-ai-tag">'+esc(tag)+'</span></div>'
      +'<div class="lex-langs">'+rows+'</div>';
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
    return '<div class="lex" style="margin-bottom:16px">'+h+'</div>';
  }

  function renderTable(formString){
    var cells = String(formString||"").split(";");
    while(cells.length<9) cells.push("");
    var h='<div class="df-table"><table><thead><tr><th></th><th class="deva">एकवचनम्</th><th class="deva">द्विवचनम्</th><th class="deva">बहुवचनम्</th></tr></thead><tbody>';
    for(var p=0;p<3;p++){
      h+='<tr><th class="deva">'+PERSONS[p]+'</th>';
      for(var n=0;n<3;n++){
        var idx=p*3+n;
        h+='<td class="deva">'+esc((cells[idx]||"").split(",").join(", "))+'</td>';
      }
      h+='</tr>';
    }
    h+='</tbody></table></div>';
    return h;
  }

  function boot(){
    var themeBtn=$("#themeBtn");
    if(localStorage.getItem("dge_vyakarana_dark")==="1") document.body.classList.add("dark");
    if(themeBtn) themeBtn.addEventListener("click",function(){
      var dark=document.body.classList.toggle("dark");
      localStorage.setItem("dge_vyakarana_dark", dark?"1":"0");
    });

    var code=hashId();
    var root=$("#root");
    if(!code){ root.innerHTML='<div class="df-empty">कोई धातु चयनित नहीं — <a href="dhatu.html">धातुपाठः</a> से एक धातु खोलें।</div>'; return; }

    Promise.all([
      fetch(FORMS_URL+code+".json").then(function(r){ if(!r.ok) throw new Error(r.status); return r.json(); }),
      fetch(DHATU_URL).then(function(r){ return r.ok?r.json():null; }).catch(function(){return null;}),
      fetch(LEXICON_URL).then(function(r){ return r.ok?r.json():null; }).catch(function(){return null;})
    ]).then(function(res){
      var data=res[0], dhatuIdx=res[1], lexIdx=res[2];
      var info = dhatuIdx && (dhatuIdx.items||[]).find(function(x){return x.id===code;});
      var lexEntry = lexIdx && (lexIdx.items||[]).find(function(x){return x.id===code;});
      var voices = VOICE_ORDER.filter(function(v){ return data.forms[v[0]] && data.forms[v[0]][v[1]]; });

      var h='<div class="df-head">'
        +'<div class="crumbs deva" style="margin:0 0 6px">DGE › व्याकरणम् › <a href="dhatu.html#'+code+'" style="color:var(--accent)">धातुपाठः</a> › <b>रूपाणि</b></div>'
        +'<h1 class="deva">'+esc(info?info.dhatu:code)+' <span style="font-size:14px;color:var(--muted);font-weight:400">('+code+')</span></h1>'
        +'<div class="sub deva">'+(info?esc(info.artha)+' · गणः '+info.gana+' — '+esc(GANA[info.gana]||""):"")+'</div>'
        +'</div>'
        +lexiconHtml(lexEntry);

      if(!voices.length){
        h+='<div class="df-empty">इस धातु के लिए सन्/णिच्/यङ्/यङ्लुक् रूप उपलब्ध नहीं (सभी 2229 मूल धातुओं में से 1782 के ही यङ्/यङ्लुक् रूप स्रोत में हैं)।</div>';
        root.innerHTML=h; return;
      }

      var vtabs='<div class="df-tabs">'+voices.map(function(v,i){return '<button class="df-tab'+(i===0?" on":"")+'" data-gana="'+v[0]+'" data-pada="'+v[1]+'">'+v[2]+'</button>';}).join("")+'</div>';
      var body='<div id="df-body"></div>';
      root.innerHTML = h + vtabs + body;

      function showVoice(ganaKey,padaKey){
        document.querySelectorAll(".df-tab").forEach(function(t){ t.classList.toggle("on", t.dataset.gana===ganaKey && t.dataset.pada===padaKey); });
        var forms = data.forms[ganaKey][padaKey];
        var avail = LAKARAS.filter(function(pair){ return lakaraKey(pair,forms); });
        var lakTabs='<div class="df-lak">'+avail.map(function(pair,i){
          return '<button class="df-lakbtn'+(i===0?" on":"")+'" data-lak="'+lakaraKey(pair,forms)+'">'+pair[2]+'</button>';
        }).join("")+'</div>';
        var b=$("#df-body");
        b.innerHTML = lakTabs + '<div id="df-tablewrap">'+(avail.length?renderTable(forms[lakaraKey(avail[0],forms)]):'<div class="df-empty">no forms</div>')+'</div>';
        b.querySelectorAll(".df-lakbtn").forEach(function(btn){
          btn.addEventListener("click",function(){
            b.querySelectorAll(".df-lakbtn").forEach(function(x){x.classList.remove("on");});
            btn.classList.add("on");
            $("#df-tablewrap").innerHTML = renderTable(forms[btn.dataset.lak]);
          });
        });
      }
      showVoice(voices[0][0], voices[0][1]);
      root.querySelector(".df-tabs").addEventListener("click",function(e){
        var t=e.target.closest(".df-tab"); if(!t) return;
        showVoice(t.dataset.gana, t.dataset.pada);
      });

      var note=document.createElement("p");
      note.className="df-note";
      note.textContent="रूपाणि (सन्/णिच्/यङ्/यङ्लुक्, शुद्ध कर्मणि) — शुद्ध कर्तरि के लिए देखें प्रक्रिया (चरणबद्ध व्युत्पत्ति)।";
      root.appendChild(note);
    }).catch(function(e){
      root.innerHTML='<div class="df-empty">इस धातु के रूप लोड नहीं हो सके ('+e+')।  फ़ोल्डर से सर्व करें।</div>';
    });
  }

  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded",boot); else boot();
})();
