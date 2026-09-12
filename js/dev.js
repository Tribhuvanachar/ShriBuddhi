// DGE Module: dev.js
window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['dev.js'] = 'v2.2 (Auto-enables for super admins, not just ?dev=true)';

document.addEventListener('DOMContentLoaded', () => {
    const urlParams = new URLSearchParams(window.location.search);
    if(urlParams.get('dev') === 'true' || localStorage.getItem('is_superadmin') === 'true') {

        let html = "<div style='margin-bottom:8px; padding-bottom:8px; border-bottom:1px dashed rgba(0,255,0,0.3);'>";
        html += "<strong style='color:#FFF;'>🛠️ DGE DEVELOPMENT LOG</strong><br/>";

        if(window.DGE_VERSIONS) {
            html += "<strong style='color:#0FF;'>[MODULES LOADED]</strong><br/>";
            const expectedScripts = ['config.js','state.js','dev.js','utils.js','modals.js','transliteration.js','audio.js','filter.js','search.js','markers.js','notes.js','snippets.js','actions.js','voice.js','screenshot.js','ai.js','render.js','core.js'];
            expectedScripts.forEach(script => {
                if (window.DGE_VERSIONS[script]) {
                    html += `✔️ ${script}: <span style="color:#FF0;">${window.DGE_VERSIONS[script]}</span><br/>`;
                } else {
                    html += `❌ <span style="color:red;">${script}: NOT LOADED (missing or 404 — check the Network tab and its cache-bust ?v= version)</span><br/>`;
                }
            });
        }

        // Grouped function-readiness checks. A ❌ here means either that
        // file failed to load, or an earlier line in it threw before
        // reaching this assignment — check [ERR] lines above for why.
        const groups = {
            'Core / Rendering': ['initApp', 'renderList', 'renderStotraChrome', 'togglePopup', 'openModal', 'closeModal', 'copyShlokaText'],
            'Persistence (nsKey bug class)': ['nsKey', 'loadPersistedState', 'dgeSaveMarks', 'dgeSaveNotes'],
            'Audio Engine': ['playShloka', 'togglePlay', 'resolveAudioSrc', 'cacheAllAudio', 'onSeekSliderInput', 'toggleSeekPrecision'],
            'Reading-Along Sync': ['wrapReadingCardWordsForSync', 'updateReadingCardSyncHighlight'],
            'Marks (Favorite/Status/Doubt)': ['toggleFavorite', 'toggleDoubt', 'openStatusPicker', 'setStatus'],
            'Notes': ['openNote', 'saveNote', 'addNoteEntry', 'shareNoteEntry', 'deleteNoteEntry', 'copyNoteEntry'],
            'Snippets': ['saveSnippet', 'playSnippet', 'deleteSnippet', 'downloadSnippetAudio', 'downloadFullShlokaAudio'],
            'Unified Actions Sheet': ['openActionsSheet', 'renderActionsSheetContent'],
            'Sharing': ['shareShlokaAudio', 'shareShlokaTextOnly', 'shareShlokaScreenshot', 'downloadShlokaScreenshot'],
            'Theme & Appearance': ['applyTheme', 'setTheme', 'applyFontSize'],
            'Feature Flags': ['dgeGetEffectiveFeatureFlags', 'applyFeatureFlags', 'resetFeatureFlagsToDefault'],
            'Ask Acharya': ['askAcharya', 'sendAcharyaFollowUp', 'renderAcharyaQueryButtons', 'dgeGetEffectiveQueryTypes', 'openKeyModal', 'saveAllApiKeys'],
            'Voice Search': ['startSearchVoiceInput', 'startFollowUpVoiceInput'],
            'Filter & Search': ['toggleFilterCriterion', 'clearAllFilterCriteria', 'toggleSingleTrackMode', 'getFilteredIds', 'handleSearch']
        };

        Object.entries(groups).forEach(([groupName, funcs]) => {
            html += `<br/><strong style='color:#0FF;'>[${groupName.toUpperCase()}]</strong><br/>`;
            funcs.forEach(func => {
                html += (typeof window[func] === 'function') ? `✔️ ${func}() is ready.<br/>` : `❌ <span style='color:red;'>${func}() is MISSING.</span><br/>`;
            });
        });

        html += "</div>";

        // Feed this diagnostic block into the ONE shared log panel (created
        // by utils.js) instead of spawning a second, uncontrolled overlay.
        if (window.DGE_DEV_LOG && typeof window.DGE_DEV_LOG.appendHTML === 'function') {
            window.DGE_DEV_LOG.appendHTML(html);
        } else {
            console.warn('[dev.js] Shared dev log panel unavailable — skipping diagnostics UI.');
        }
    }
});
