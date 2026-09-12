window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['transliteration.js'] = 'v1.5 (DGE_DEVANAGARI_ALIAS_SCRIPTS: hindi/marathi script-picker entries are no-ops here, same as devanagari itself -- no distinct Sanscript scheme for either. On top of v1.4\'s Vedic accent handling)';

// Vedic accent marks and the nasal sign have no direct equivalent in the
// target scripts, so Sanscript passes them through untouched — they then
// land on Latin/Kannada/Telugu letters as missing-glyph boxes (visible as
// "NO GLYPH" rectangles). Handled explicitly here instead:
//   - IAST gets the scholarly roman convention: combining acute for
//     svarita, combining grave for anudatta. This matches how VedaWeb's
//     own IAST renders the same text (agním, hy àgne), and both combine
//     correctly with Latin letters in any normal font.
//   - Other Indic scripts have no widely-supported Vedic accent
//     convention in Unicode, so the marks are dropped rather than shown
//     as boxes. The accented Devanagari remains available by switching
//     back to Sanskrit — accent information is never lost from the data.
//   - The nasal sign ꣳ (U+A8F3) becomes a plain anusvāra before
//     conversion, which every script renders properly.
const DGE_VEDIC_MARKS = /[\u0951\u0952\u1CD0-\u1CFF]/g;

function dgePrepareForScript(text, script) {
    let t = text.replace(/\uA8F3/g, '\u0902'); // ꣳ -> ं
    if (script === 'iast') {
        t = t.replace(/\u0951/g, '\u0301')     // svarita  -> combining acute
             .replace(/\u0952/g, '\u0300');    // anudatta -> combining grave
        return t.replace(/[\u1CD0-\u1CFF]/g, '');
    }
    return t.replace(DGE_VEDIC_MARKS, '');
}

// 'hindi'/'marathi' are Devanagari-script script-picker entries (see
// config.js's SCRIPT_OPTIONS) -- no-ops here, same as 'devanagari' itself,
// since there's no distinct Sanscript scheme for either.
const DGE_DEVANAGARI_ALIAS_SCRIPTS = ['devanagari', 'hindi', 'marathi'];

window.applyTransliteration = function(htmlText, script) {
    if (DGE_DEVANAGARI_ALIAS_SCRIPTS.includes(script) || !htmlText) {
        return htmlText;
    }
    
    if (typeof window.Sanscript === 'undefined') {
        console.error("[Transliteration] Fatal error: Sanscript engine missing from global window. Check that the @indic-transliteration/sanscript <script> tag in index.html <head> loaded successfully (see Network tab for a 404) and that it appears BEFORE js/transliteration.js in the document.");
        return htmlText; 
    }
    
    try {
        const parts = htmlText.split(/(<[^>]+>)/g);
        
        for (let i = 0; i < parts.length; i++) {
            if (!parts[i].startsWith('<')) {
                let cleanText = parts[i].replace(/[\u200B-\u200D\uFEFF]/g, '');
                
                if (cleanText.trim().length > 0) {
                    parts[i] = window.Sanscript.t(dgePrepareForScript(cleanText, script), 'devanagari', script);
                }
            }
        }
        return parts.join('');
    } catch (e) {
        console.error("[Transliteration] Exception occurred during parsing:", e);
        return htmlText;
    }
};

window.applyScript = function(code) {
    console.log(`[Transliteration] Applying script classes for UI: ${code}`);
    window.activeScript = code;
    
    document.querySelectorAll('#displayPopup .pop-item[data-script]').forEach(el => {
        if (el.dataset.script) {
            el.classList.toggle('active', el.dataset.script === code);
        }
    });
    
    if (!DGE_DEVANAGARI_ALIAS_SCRIPTS.includes(code)) {
        document.body.classList.add('non-devanagari');
    } else {
        document.body.classList.remove('non-devanagari');
    }
};

window.setScript = function(code, el) {
    window.applyScript(code);
    localStorage.setItem('app_script', code);
    
    if (typeof window.showToast === 'function') {
        window.showToast("आचार्यः ग्रन्थं सज्जीकुर्वन् अस्ति... (Translating script)");
    }
    
    setTimeout(() => {
        if (typeof window.renderStotraChrome === 'function') {
            window.renderStotraChrome();
        }

        if (typeof window.renderList === 'function') {
            window.renderList();
        }
        
        if (window.activeId && typeof window.wrapReadingCardWordsForSync === 'function') {
            window.wrapReadingCardWordsForSync(window.activeId);   // renderList() above rebuilt the active card
        }

        // The library browser builds its labels in the active script too,
        // so it needs rebuilding if it happens to be open — otherwise it
        // sits there in the previous script until manually reopened.
        // (openModal sets style.display rather than adding a class.)
        const libModal = document.getElementById('libraryModal');
        if (libModal && libModal.style.display === 'flex' &&
            typeof window.openLibraryModal === 'function') {
            window.openLibraryModal();
        }
        
        // Display popup deliberately stays open — script, size, theme and view
        // are often changed together, so closing after each one was fiddly.
    }, 50);
};

console.log("[Init] transliteration.js loaded successfully.");
