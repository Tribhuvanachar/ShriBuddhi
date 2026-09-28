// js/path-labels.js — one Devanagari name per taxonomy path segment.
//
// Lived inside js/library.js until 28 Sep 2026, when library.html (the room
// the vandana opens into) needed the same names. Copying the table would have
// meant two lists to keep in step, and the one that is not looked at is the
// one that goes stale; library.js now reads it from here, so the drawer and
// the library page cannot disagree about what a folder is called.
window.DGE_PATH_LABELS = {
  // Added 28 Sep 2026: these three showed as auto-labelled English on
  // library.html ('Krishnacharitra Manjari'), which is what an unlabelled
  // folder falls back to.
  krishnacharitra_manjari: 'श्रीकृष्णचरित्रमञ्जरी',
  tirtha_prabandha: 'तीर्थप्रबन्धः', vedavyasa_gadya: 'श्रीवेदव्यासगद्यम्',
  yukti_mallika: 'युक्तिमल्लिका', sangraha_ramayana: 'सङ्ग्रहरामायणम्',
  vedas: 'वेदाः', stotras: 'स्तोत्राणि', puranas: 'पुराणानि',
  itihasas: 'इतिहासाः', smritis: 'स्मृतयः', sutras: 'सूत्राणि',
  dharmashastra: 'धर्मशास्त्रम्', pancharatra_agama: 'पाञ्चरात्रागमः',
  sarvamoola_grantha: 'सर्वमूलग्रन्थाः', dasakuta: 'दासकूटः',
  vyasakuta: 'व्यासकूटः', DasaSahitya: 'दाससाहित्यम्',
  koshas: 'कोशाः', ancillary: 'अङ्गानि',

  // The branches of the recommended DGE taxonomy (DGE_Shastra_Taxonomy.md).
  // Listed whether or not the corpus has been moved onto it yet: the Library
  // Manager can regroup the tree onto these names without the folders moving
  // (see the "moves" map in admin/config/library-overrides.json, and
  // tools/restructure_taxonomy.py), and an unlabelled segment falls back to
  // ASCII, which would leave a Sanskrit tree with English branch headings.
  vedanga: 'वेदाङ्गानि',
  shiksha: 'शिक्षा', chandas: 'छन्दः', nirukta: 'निरुक्तम्',
  jyotisha: 'ज्योतिषम्', kalpa: 'कल्पः', pratishakhya: 'प्रातिशाख्यानि',
  vyakarana: 'व्याकरणम्',
  ashtadhyayi: 'अष्टाध्यायी', dhatupatha: 'धातुपाठः', vritti: 'वृत्तिः',

  darshana: 'दर्शनानि', vedanta: 'वेदान्तः',
  dvaita: 'द्वैतम्', advaita: 'अद्वैतम्', vishishtadvaita: 'विशिष्टाद्वैतम्',
  // Stale pre-23-Aug-2026 top-level path some not-yet-rebuilt search index
  // shards still carry (see global-search.js's siddhantaOf() comment) --
  // labelled here too so an admin viewing one of those hits still gets a
  // real Devanagari name instead of the auto-labeller's bare "Dvaitavedanta".
  dvaitavedanta: 'द्वैतवेदान्तः',
  nyaya: 'न्यायः', vaisheshika: 'वैशेषिकम्', sankhya: 'साङ्ख्यम्',
  yoga: 'योगः', mimamsa: 'मीमांसा',
  // 23 Aug 2026 restructure (origin/main): the separate top-level
  // dvaitavedanta/ tree moved to sit beside SarvaMula here (admin-only,
  // see the visibility flag on its taxonomy/library.json entries --
  // dgeIsHiddenGrantha below). SetuTila is an empty placeholder for a
  // second Sarvamula edition. PascalCase matches the actual folder names
  // on disk post-rename -- confirmed directly, not assumed.
  SarvaMula: 'सर्वमूलग्रन्थाः',
  // The V1 restructure's own segments (11 Sep 2026). Without these the
  // breadcrumb reads "Itara > Kavya" in Latin beside Devanagari on
  // either side of it.
  Itara: 'इतराणि', Kavya: 'काव्यम्', Stotra: 'स्तोत्राणि', DasaSahitya: 'दाससाहित्यम्',
  // 20 Sep 2026: the shelves named after their source websites are NOT
  // listed here any more. Labelling them publicly meant shipping the names
  // in a file every page loads, to label a breadcrumb no public page shows
  // -- those works have no public path and reach a reader only through an
  // opaque id. js/private-names.js supplies the labels in the private
  // checkout, where an admin does browse the real paths; it does not publish.
  Tattvavada: 'तत्त्ववादः', SetuTila: 'सेतुतिला',
  sarvadarshana_sangraha: 'सर्वदर्शनसङ्ग्रहः',

  // 23 Aug: upaveda/shastra, added per the project lead's own framework
  // (not this session's invention) -- Ayurveda and Dhanurveda under the
  // Upavedas, Natya/Kama/Niti-shastra and Buddhist literature under a
  // Shastra catch-all. See PENDING.md for what's still open (Tantra,
  // Gandharvaveda/Sthapatyaveda have no sourced content yet).
  upaveda: 'उपवेदाः', ayurveda: 'आयुर्वेदः', dhanurveda: 'धनुर्वेदः',
  gandharvaveda: 'गान्धर्ववेदः', sthapatyaveda: 'स्थापत्यवेदः',
  nighantu: 'निघण्टवः', rasashastra: 'रसशास्त्रम्',
  shastra: 'शास्त्राणि', natya_shastra: 'नाट्यशास्त्रम्',
  kama_shastra: 'कामशास्त्रम्', niti_shastra: 'नीतिशास्त्रम्', subhashita: 'सुभाषितम्',
  artha_shastra: 'अर्थशास्त्रम्', hitopadesha: 'हितोपदेशः',
  chanakya_niti: 'चाणक्यनीतिः', chanakya_sutra: 'चाणक्यसूत्रम्', kamandakiya_nitisara: 'कामन्दकीयनीतिसारः',
  bauddha_sahitya: 'बौद्धसाहित्यम्', sutra: 'सूत्रम्',
  pramana: 'प्रमाणम्', avadana: 'अवदानम्',
  krishi_shastra: 'कृषिशास्त्रम्', shainika_shastra: 'श्यैनिकशास्त्रम्',
  ratna_pariksha: 'रत्नपरीक्षा',

  // 23 Aug: Tantra/Saiva-Sakta cluster, deferred every earlier batch
  // until explicitly requested. shaiva_agama/shakta_agama moved here
  // from under agama.pancharatra (a Vaishnava-specific term that never
  // fit) -- see PENDING.md for that reparenting.
  pashupata: 'पाशुपतम्', pratyabhijna: 'प्रत्यभिज्ञा',
  shaiva_siddhanta: 'शैवसिद्धान्तः', shaiva_agama: 'शैवागमः',
  shakta_agama: 'शाक्तागमः', natha_sampradaya: 'नाथसम्प्रदायः',

  itihasa: 'इतिहासाः', purana: 'पुराणानि',
  ramayana: 'रामायणम्', ananda_ramayana: 'आनन्दरामायणम्',
  adbhuta_ramayana: 'अद्भुतरामायणम्',
  // Not a category anyone would claim: a holding place for material whose
  // home is not settled. Named plainly so it reads as temporary.
  misc: 'अन्यत्',
  smriti_dharma: 'स्मृतिधर्मशास्त्राणि', smriti: 'स्मृतयः',
  kavya_alankara: 'काव्यालङ्कारौ', kavya: 'काव्यम्',
  kosha: 'कोशाः', stotra: 'स्तोत्राणि',
  agama: 'आगमाः', pancharatra: 'पाञ्चरात्रम्',
  pancharatra_samhitas: 'पाञ्चरात्रसंहिताः', shaiva_agama: 'शैवागमः',
  shakta_agama: 'शाक्तागमः', vaikhanasa_agama: 'वैखानसागमः',
  nitishastra: 'नीतिशास्त्रम्', upaveda: 'उपवेदाः',
  ayurveda: 'आयुर्वेदः', kamashastra: 'कामशास्त्रम्', nighantu: 'निघण्टुः',

  rigveda: 'ऋग्वेदः', yajurveda: 'यजुर्वेदः',
  samaveda: 'सामवेदः', atharvaveda: 'अथर्ववेदः',

  krishna_yajurveda: 'कृष्णयजुर्वेदः', shukla_yajurveda: 'शुक्लयजुर्वेदः',

  shakala_shakha: 'शाकलशाखा', bashkala_shakha: 'बाष्कलशाखा',
  shaunaka_shakha: 'शौनकशाखा', paippalada_shakha: 'पैप्पलादशाखा',
  kauthuma_shakha: 'कौथुमशाखा', ranayaniya_shakha: 'राणायनीयशाखा',
  jaiminiya_shakha: 'जैमिनीयशाखा', taittiriya_shakha: 'तैत्तिरीयशाखा',
  maitrayani_shakha: 'मैत्रायणीशाखा', katha_shakha: 'कठशाखा',
  vajasaneyi_madhyandina_shakha: 'वाजसनेयिमाध्यन्दिनशाखा',
  vajasaneyi_kanva_shakha: 'वाजसनेयिकाण्वशाखा',

  samhita: 'संहिता', brahmana: 'ब्राह्मणम्', brahmanas: 'ब्राह्मणानि',
  aranyaka: 'आरण्यकम्', aranyakas: 'आरण्यकानि',
  upanishad: 'उपनिषत्', upanishads: 'उपनिषदः',
  mula: 'मूलम्', tika: 'टीका', tippani: 'टिप्पणी',
  purvarchika: 'पूर्वार्चिकः', uttararchika: 'उत्तरार्चिकः',
  taittiriya_brahmana: 'तैत्तिरीयब्राह्मणम्',
  shatapatha_brahmana: 'शतपथब्राह्मणम्',
  // Advaita Sharada import groups (2 Sep 2026)
  sutra_prasthana_tikas: 'सूत्रप्रस्थानटीकाः',
  upanishad_prasthana_tikas: 'उपनिषत्प्रस्थानटीकाः',
  gita_prasthana_tikas: 'गीताप्रस्थानटीकाः',
  prakarana_granthas: 'प्रकरणग्रन्थाः',
  siddhi_granthas: 'सिद्धिग्रन्थाः',
  shankara_bhashya_extra: 'अपराणि शाङ्करभाष्याणि',
  stotrani: 'स्तोत्राणि',
  taittiriya_aranyaka: 'तैत्तिरीयारण्यकम्',
  // Sri Ramanuja Meghamala import groups (2 Sep 2026)
  // (the three *_prasthana keys it shares are already defined below)
  rahasya_granthas: 'रहस्यग्रन्थाः',
  guruparampara: 'गुरुपरम्परा',
  divya_prabandham: 'दिव्यप्रबन्धम्',
  bhagavad_vishayam: 'भगवद्विषयम्',
  reference_granthas: 'सन्दर्भग्रन्थाः',
  divya_desha_vaibhavam: 'दिव्यदेशवैभवम्',
  smritayah: 'स्मृतयः',
  puranani: 'पुराणानि',
  agamah: 'आगमाः',

  // Mahabharata parvas
  adi_parva: 'आदिपर्व', sabha_parva: 'सभापर्व', vana_parva: 'वनपर्व', virata_parva: 'विराटपर्व',
  udyoga_parva: 'उद्योगपर्व', bhishma_parva: 'भीष्मपर्व', drona_parva: 'द्रोणपर्व', karna_parva: 'कर्णपर्व',
  shalya_parva: 'शल्यपर्व', sauptika_parva: 'सौप्तिकपर्व', stri_parva: 'स्त्रीपर्व', shanti_parva: 'शान्तिपर्व',
  anushasana_parva: 'अनुशासनपर्व', ashvamedhika_parva: 'अश्वमेधिकपर्व', ashramavasika_parva: 'आश्रमवासिकपर्व', mausala_parva: 'मौसलपर्व',
  mahaprasthanika_parva: 'महाप्रस्थानिकपर्व', svargarohana_parva: 'स्वर्गारोहणपर्व',
  // Ramayana kandas
  bala_kanda: 'बालकाण्डम्', ayodhya_kanda: 'अयोध्याकाण्डम्', aranya_kanda: 'अरण्यकाण्डम्', kishkindha_kanda: 'किष्किन्धाकाण्डम्',
  sundara_kanda: 'सुन्दरकाण्डम्', yuddha_kanda: 'युद्धकाण्डम्', uttara_kanda: 'उत्तरकाण्डम्',
  // Itihasa/Kavya misc
  mahabharata: 'महाभारतम्', mahabharata_kannada: 'महाभारतम् (कन्नड)', harivamsha: 'हरिवंशः', harivamsha_khila: 'हरिवंशखिलम्',
  bhagavad_gita: 'भगवद्गीता', purushasuktam: 'पुरुषसूक्तम्', yamaka_bharata: 'यमकभारतम्', raghavendra_vijaya: 'राघवेन्द्रविजयः',
  sumadhva_vijaya: 'सुमध्वविजयः', kiratarjuniya: 'किरातार्जुनीयम्', kumarasambhava: 'कुमारसम्भवः', raghuvamsha: 'रघुवंशः',
  shishupalavadha: 'शिशुपालवधः',
  // Puranas
  maha_purana: 'महापुराणानि', upa_purana: 'उपपुराणानि', upapuranas: 'उपपुराणानि',
  bhagavata_purana: 'भागवतपुराणम्', bhagavata_purana_madhva: 'भागवतपुराणम् (माध्वम्)', bhavishya_purana: 'भविष्यपुराणम्', brahmanda_purana: 'ब्रह्माण्डपुराणम्',
  brahma_purana: 'ब्रह्मपुराणम्', agni_purana: 'अग्निपुराणम्', varaha_purana: 'वराहपुराणम्', vayu_purana: 'वायुपुराणम्',
  brahmavaivarta_purana: 'ब्रह्मवैवर्तपुराणम्', garuda_purana: 'गरुडपुराणम्', kurma_purana: 'कूर्मपुराणम्', linga_purana: 'लिङ्गपुराणम्',
  markandeya_purana: 'मार्कण्डेयपुराणम्', narada_purana: 'नारदपुराणम्', padma_purana: 'पद्मपुराणम्', shiva_purana: 'शिवपुराणम्',
  skanda_purana: 'स्कन्दपुराणम्', vamana_purana: 'वामनपुराणम्', vishnu_purana: 'विष्णुपुराणम्',
  vishnu_dharmottara_purana: 'विष्णुधर्मोत्तरपुराणम्', devi_bhagavata_purana: 'देवीभागवतपुराणम्', kalika_purana: 'कालिकापुराणम्',
  narasimha_purana: 'नृसिंहपुराणम्', brihannaradiya_purana: 'बृहन्नारदीयपुराणम्', saura_purana: 'सौरपुराणम्',
  ganesha_purana: 'गणेशपुराणम्', sanatkumara_purana: 'सनत्कुमारपुराणम्', nandi_purana: 'नन्दिपुराणम्', adi_purana: 'आदिपुराणम्',
  rudra_samhita: 'रुद्रसंहिता',
  // Dvaita Tatparya Nirnaya corpus (prasthanas, bhashyas)
  gita_prasthana: 'गीताप्रस्थानम्', sutra_prasthana: 'सूत्रप्रस्थानम्', upanishad_prasthana: 'उपनिषत्प्रस्थानम्', itihasa_prasthana: 'इतिहासप्रस्थानम्',
  purana_prasthana: 'पुराणप्रस्थानम्', sruti_prasthana: 'श्रुतिप्रस्थानम्', gita_bhashya: 'गीताभाष्यम्', gita_tatparya_nirnaya: 'गीतातात्पर्यनिर्णयः',
  itihasa_purana_tatparya_nirnaya: 'इतिहासपुराणतात्पर्यनिर्णयः', bhagavata_tatparya_nirnaya: 'भागवततात्पर्यनिर्णयः', mahabharata_tatparya_nirnaya: 'महाभारततात्पर्यनिर्णयः', rig_bhashya: 'ऋग्भाष्यम्',
  anubhashya: 'अणुभाष्यम्', anuvyakhyana: 'अनुव्याख्यानम्', anuvyakhyana_sudha: 'अनुव्याख्यानसुधा',
  brahma_sutra_bhashya: 'ब्रह्मसूत्रभाष्यम्', brahmasutra_bhashya: 'ब्रह्मसूत्रभाष्यम्', brahma_sutra: 'ब्रह्मसूत्रम्',
  nyaya_vivarana: 'न्यायविवरणम्', upanishad_bhashya: 'उपनिषद्भाष्यम्', aitareya_upanishad: 'ऐतरेयोपनिषत्', aitareyopanishad_bhashya: 'ऐतरेयोपनिषद्भाष्यम्',
  brihadaranyakopanishad_bhashya: 'बृहदारण्यकोपनिषद्भाष्यम्', brihadaranyakopanishadbhashyam: 'बृहदारण्यकोपनिषद्भाष्यम्', chandogyopanishad_bhashya: 'छान्दोग्योपनिषद्भाष्यम्', ishavasyopanishad_bhashya: 'ईशावास्योपनिषद्भाष्यम्',
  kathopanishad_bhashya: 'कठोपनिषद्भाष्यम्', kenopanishad_bhashya: 'केनोपनिषद्भाष्यम्', mandukyopanishad_bhashya: 'माण्डूक्योपनिषद्भाष्यम्', mandukyopanishadbhashyam: 'माण्डूक्योपनिषद्भाष्यम्',
  mundakopanishad_bhashya: 'मुण्डकोपनिषद्भाष्यम्', mundakopanishadbhashyam: 'मुण्डकोपनिषद्भाष्यम्', prashnopanishad_bhashya: 'प्रश्नोपनिषद्भाष्यम्', taittiriyopanishad_bhashya: 'तैत्तिरीयोपनिषद्भाष्यम्',
  shatprashnopanishadbhashyam: 'षट्प्रश्नोपनिषद्भाष्यम्', nrisimhatapaniya_upanishad: 'नृसिंहतापनीयोपनिषत्', vaishnava_upanishads_group: 'वैष्णवोपनिषदः',
  // Madhva's Dasha Prakarana + ancillary works
  dasha_prakarana_granthas: 'दशप्रकरणग्रन्थाः', karma_nirnaya: 'कर्मनिर्णयः', katha_lakshana: 'कथालक्षणम्', mayavada_khandana: 'मायावादखण्डनम्',
  pramana_lakshana: 'प्रमाणलक्षणम्', prapancha_mithyatvanumana_khandana: 'प्रपञ्चमिथ्यात्वानुमानखण्डनम्', tattva_sankhyana: 'तत्त्वसंख्यानम्', tattva_viveka: 'तत्त्वविवेकः',
  tattvodyota: 'तत्त्वोद्योतः', upadhi_khandana: 'उपाधिखण्डनम्', vishnu_tattva_vinirnaya: 'विष्णुतत्त्वविनिर्णयः', achara_and_ancillary_granthas: 'आचारादिग्रन्थाः',
  sutra_and_bhashya: 'सूत्रभाष्यम्', independent_dharmasutras: 'स्वतन्त्रधर्मसूत्राणि',
  // Post-Madhva acharyas and their works
  jayanti_nirnaya: 'जयन्तीनिर्णयः', kanduka_stuti: 'कन्दुकस्तुतिः', krishnamrita_maharnava: 'कृष्णामृतमहार्णवः', nakha_stuti: 'नखस्तुतिः',
  sadachara_smriti: 'सदाचारस्मृतिः', tantrasara_sangraha: 'तन्त्रसारसङ्ग्रहः', yati_pranava_kalpa: 'यतिप्रणवकल्पः', dvadasha_stotra: 'द्वादशस्तोत्रम्',
  vagvajra: 'वाग्वज्रः', karmavijaya: 'कर्मविजयः', later_acharyas: 'उत्तराचार्याः', raghavendra_tirtha: 'राघवेन्द्रतीर्थः',
  vadiraja_tirtha: 'वादिराजतीर्थः', vyasatirtha: 'व्यासतीर्थः', vijayadasa: 'विजयदासः', purandaradasa: 'पुरन्दरदासः',
  kanakadasa: 'कनकदासः', jagannathadasa: 'जगन्नाथदासः', gopaladasa: 'गोपालदासः', mahipatidasa: 'महीपतिदासः',
  prasannavenkatadasa: 'प्रसन्नवेङ्कटदासः', nyayamrita: 'न्यायामृतम्', tarka_tandava: 'तर्कताण्डवः', madhvamukhalankara: 'मध्वमुखालङ्कारः',
  madhvasiddhantasara: 'मध्वसिद्धान्तसारः', sarvasiddhantasarasaravivecanam: 'सर्वसिद्धान्तसारसारविवेचनम्', shrimanmadhvasiddhantasaroddhara: 'श्रीमन्मध्वसिद्धान्तसारोद्धारः', shrimannyayasudhamandanam: 'श्रीमन्न्यायसुधामण्डनम्',
  shrivijayindravijayavaibhavam: 'श्रीविजयीन्द्रविजयवैभवम्', dvaita_dyumani: 'द्वैतद्युमणिः', bhedaparanyeva_khalu_brahmasutrani: 'भेदपराण्येव खलु ब्रह्मसूत्राणि', bhedojjivana: 'भेदोज्जीवनम्',
  bhagavato_nirdoshatvalakshanam: 'भागवतनिर्दोषत्वलक्षणम्', candrikamandanam: 'चन्द्रिकामण्डनम्', tatparya_chandrika: 'तात्पर्यचन्द्रिका',
  tantradipika: 'तन्त्रदीपिका', vadavali: 'वादावली', yukti_mallika: 'युक्तिमल्लिका', nyasa_paddhati: 'न्यासपद्धतिः',
  // Vedanta/general Vedantic terms
  omkara_vada: 'ओंकारवादः', vyutpattivada: 'व्युत्पत्तिवादः', shabda_khanda: 'शब्दखण्डः', tithi_nirnaya: 'तिथिनिर्णयः',
  shaktivada: 'शक्तिवादः', samanya_nirukti: 'सामान्यनिरुक्तिः',
  // Nyaya/Vaisheshika (classical + Navya)
  navya_nyaya: 'नव्यन्यायः', nyaya_bhushana: 'न्यायभूषणम्', nyaya_kusumanjali: 'न्यायकुसुमाञ्जलिः', nyaya_manjari: 'न्यायमञ्जरी',
  nyaya_ratnamala: 'न्यायरत्नमाला', nyaya_sutra: 'न्यायसूत्रम्', vaisheshika_sutra: 'वैशेषिकसूत्रम्', prachina_nyaya: 'प्राचीनन्यायः',
  prashastapada_bhashya: 'प्रशस्तपादभाष्यम्', tarkasangraha: 'तर्कसङ्ग्रहः', tarkabhasha: 'तर्कभाषा', karikavali: 'कारिकावली',
  bhasha_pariccheda: 'भाषापरिच्छेदः', siddhanta_lakshana: 'सिद्धान्तलक्षणम्', padarthasangraha: 'पदार्थसङ्ग्रहः', pramana_paddhati: 'प्रमाणपद्धतिः',
  prakarana_panchika: 'प्रकरणपञ्चिका', prakarana: 'प्रकरणम्', pramukha_prakarana: 'प्रमुखप्रकरणानि', vyaptyanugama: 'व्याप्त्यनुगमः',
  pakshata: 'पक्षता', badha: 'बाधः', badha_vibhajaka: 'बाधविभाजकः', avacchedakata_nirukti: 'अवच्छेदकतानिरुक्तिः',
  avayava: 'अवयवः', anumana_khanda: 'अनुमानखण्डः', chaturdashalakshani: 'चतुर्दशलक्षणी', panchalakshani: 'पञ्चलक्षणी',
  satpratipaksha: 'सत्प्रतिपक्षः', savyabhichara: 'सव्यभिचारः', vyadhikarana: 'व्यधिकरणम्', upamana_khanda: 'उपमानखण्डः',
  pratyaksha_khanda: 'प्रत्यक्षखण्डः', vadas: 'वादाः', tattvacintamani: 'तत्त्वचिन्तामणिः',
  // Mimamsa
  mimamsa_nyaya_prakasha: 'मीमांसान्यायप्रकाशः', mimamsa_paribhasha: 'मीमांसापरिभाषा', mimamsa_sutra: 'मीमांसासूत्रम्', tantravarttika: 'तन्त्रवार्त्तिकम्',
  tuptika: 'टुप्टीका', shlokavarttika: 'श्लोकवार्त्तिकम्', shastra_dipika: 'शास्त्रदीपिका', bhatta_dipika: 'भट्टदीपिका',
  bhatta_rahasya: 'भट्टरहस्यम्', arthasangraha: 'अर्थसङ्ग्रहः', bhatta: 'भाट्टम्', prabhakara: 'प्राभाकरम्',
  brihati: 'बृहती',
  // Vedic Kalpa-sutra schools (Grihya/Shrauta/Dharma-sutra)
  apastamba: 'आपस्तम्बः', ashvalayana: 'आश्वलायनः', baudhayana: 'बौधायनः', bharadvaja: 'भारद्वाजः',
  drahyayana: 'द्राह्यायणः', gobhila: 'गोभिलः', hiranyakeshin: 'हिरण्यकेशी', katyayana: 'कात्यायनः',
  kaushika: 'कौशिकः', kauthuma: 'कौथुमः', khadira: 'खादिरः', latyayana: 'लाट्यायनः',
  manava: 'मानवः', paraskara: 'पारस्करः', shankhayana: 'शाङ्खायनः', vadhula: 'वाधूलः',
  vaikhanasa: 'वैखानसः', vaitana: 'वैतानः', varaha: 'वाराहः', kathaka: 'काठकः',
  satyashadha: 'सत्याषाढः', kapisthala_shakha: 'कपिष्ठलशाखा', jaiminiya: 'जैमिनीयः', jaiminiya_nyayamala: 'जैमिनीयन्यायमाला',
  // Vedic shiksha/pratishakhya
  atharvaveda_shiksha: 'अथर्ववेदशिक्षा', rigveda_shikshas: 'ऋग्वेदशिक्षाः', samaveda_shikshas: 'सामवेदशिक्षाः', krishna_yajurveda_shikshas: 'कृष्णयजुर्वेदशिक्षाः',
  shukla_yajurveda_shikshas: 'शुक्लयजुर्वेदशिक्षाः', yajurveda_shikshas: 'यजुर्वेदशिक्षाः', samaveda_pratishakhya: 'सामवेदप्रातिशाख्यम्', purvabhaga: 'पूर्वभागः',
  // Vyakarana
  mahabhashya_patanjali: 'महाभाष्यम् (पतञ्जलिः)', siddhanta_kaumudi: 'सिद्धान्तकौमुदी',
  // Chandas
  vrittaratnakara: 'वृत्तरत्नाकरः',
  // Agama restructure (25 Aug 2026) -- Vaishnava/Shaiva/Shakta/Kashmir Saiva/
  // Natha-Hathayoga split, see PENDING.md
  vaishnava_agama: 'वैष्णवागमः', shakta_tantra: 'शाक्ततन्त्रम्', shakta_shaiva: 'शाक्तशैवम्',
  kashmir_shaivism: 'कश्मीरशैवम्', spanda: 'स्पन्दः', trika: 'त्रिकम्', krama: 'क्रमः',
  shiva_sutra: 'शिवसूत्राणि', shiva_sutra_vartika: 'शिवसूत्रवार्त्तिकम्',
  natha_hathayoga: 'नाथहठयोगौ', natha: 'नाथसम्प्रदायः', hathayoga: 'हठयोगः',
  yamunacharya: 'यामुनाचार्यः', samvitsiddhi: 'संवित्सिद्धिः', shaiva_tantra: 'शैवतन्त्रम्',
  mahacina_tantra: 'महाचीनतन्त्रम्', matrikabheda_tantra: 'मातृकाभेदतन्त्रम्',
  todala_tantra: 'तोडलतन्त्रम्', uddamareshvara_tantra: 'उड्डामरेश्वरतन्त्रम्',
  devikalottara_agama: 'देवीकालोत्तरागमः', shakta_vijnana: 'शाक्तविज्ञानम्',
  vatulanatha_sutras: 'वातूलनाथसूत्राणि', mrigendra_tantra: 'मृगेन्द्रतन्त्रम्',
  pashupata_sutra: 'पाशुपतसूत्रम्', ganakarika: 'गणकारिका', spanda_karika: 'स्पन्दकारिका',
  tantraloka: 'तन्त्रालोकः', tantrasara: 'तन्त्रसारः', amaraughashasana: 'अमरौघशासनम्',
  gorakshashataka: 'गोरक्षशतकम्', gheranda_samhita: 'घेरण्डसंहिता', hathayogapradipika: 'हठयोगप्रदीपिका',
  // Pancharatra Ratnatraya/Pramukha/Anya regroup (25 Aug 2026)
  ratnatraya: 'रत्नत्रयम्', pramukha_samhitas: 'प्रमुखाः पाञ्चरात्रसंहिताः', anya_samhitas: 'अन्याः उपलब्धाः संहिताः',
  // Advaita corpus + misc
  shankara_bhashya: 'शङ्करभाष्यम्', badhanta: 'बाधान्तः', brahmasutranyayasamgraha: 'ब्रह्मसूत्रन्यायसंग्रहः',
  // Dasa Sahitya composers (25 Aug 2026 taxonomy integration) --
  // Devanagari transliteration of each composer's own Kannada name in
  // data/Tattvavada/Itara/DasaSahitya/index.json (generated with indic_transliteration,
  // the same library tools/Tattvavada/Itara/DasaSahitya/*.py uses for the compositions
  // themselves), plus hand-attested Devanagari for the major composers
  // whose index.json name is Latin (Purandara/Vijaya/Kanaka Dasaru etc.).
  // A handful of singleton, likely-mis-attributed 'composer' entries
  // (a title filed as a composer name, one URL-garbled slug, the honest
  // 'untitled' bucket) are left out on purpose rather than guessed --
  // see data/dasa_sahitya_local/ARCHITECTURE.md.
  composers: 'दाससाहित्यरचयितारः',
  acalanamdadasa: 'अचलानंददास', aihole_vemkatesa: 'ऐहॊळॆ वॆंकटेश', ambabayi: 'अंबाबायि', anamtadrisaru: 'अनंताद्रीशरु', anyadasaru: 'अन्यदासरु',
  askihala_govimda: 'अस्किहाळ गोविंद', asuri_ramasvamiayyamgar: 'असूरि रामस्वामिअय्यंगार्', badannayyacaryaru: 'बडण्णय्याचार्यरु', bagepalli_sesadasaru: 'बागेपल्लि शेषदासरु', belle_dasappayya: 'बॆळ्ळॆ दासप्पय्य',
  beluru_vaikumthadasaru: 'बेलूरु वैकुंठदासरु', beteraya_diksitaru: 'बेटॆराय दीक्षितरु', bhatakala_appayya: 'भटकळ अप्पय्य', bhavatarakaru: 'भावतरकरु', bhimasamkara: 'भीमाशंकर',
  bhupati_vithalaru: 'भूपति विठलरु', bolara_vasudevayya: 'बोळारा वासुदेवय्य', cannapattanada_ahobaladasaru: 'चन्नपट्टणद अहोबलदासरु', cidanamda_avadhutaru: 'चिदानंद अवधूतरु', dhanvanthri: 'धन्वन्तरिः',
  durga: 'दुर्गा', galagaliavvanavaru: 'गलगलिअव्वनवरु', gopala_dasaru: 'गोपालदासरु', gopalaryaru: 'गोपालार्यरु', gopativithalaru: 'गोपतिविठलरु',
  govimdadasa: 'गोविंददास', gumdamma: 'गुंडम्म', gurugovimdavithalaru: 'गुरुगोविंदविठलरु', guruimdiresaru: 'गुरुइंदिरेशरु', gurujagannathadasaru: 'गुरुजगन्नाथदासरु',
  gurupranesavithalaru: 'गुरुप्राणेशविठलरु', gururamalimga: 'गुरुरामलिंग', gururamavithala: 'गुरुरामविठल', gurutamdevaradagopalavithalaru: 'गुरुतंदॆवरदगोपालविठलरु', guruvijayaviththalaru: 'गुरुविजयविठ्ठलरु',
  hanumesavithala: 'हनुमेशविठल', harapanahalli_bheemavva: 'हरपनहळ्ळि भीमव्वा', hasanmukha_vithalaru: 'हसन्मुख विठलरु', helavanakatte_giriyamma: 'हॆळवनकट्टॆ गिरियम्मा', henneramgadasaru: 'हॆन्नॆरंगदासरु',
  hosakere_cidambarayyanavaru: 'हॊसकॆरॆ चिदंबरय्यनवरु', imdiresaru: 'इंदिरेशरु', jagannatha_dasaru: 'जगन्नाथदासरु', jakkappayyanavaru: 'जक्कप्पय्यनवरु', jayesavithala: 'जयेशविठल',
  jnanabodakaru: 'ज्ञानबोदकरु', kadarumdalagi_hanumayya: 'कदरुंडलगि हनुमय्य', kadarumdalagisaru: 'कदरुंडलगीशरु', kakhamdaki_sri_krsnadasaru: 'काखंडकि श्री कृष्णदासरु', kakhamdaki_sri_mahipatirayaru: 'काखंडकि श्री महिपतिरायरु',
  kalasada_sumdaramma: 'कळसद सुंदरम्म', kamalapativiththalaru: 'कमलपतिविठ्ठलरु', kanaka_dasaru: 'कनकदासरु', karki_kesavadasa: 'कर्कि केशवदास', karpara_naraharidasaru: 'कार्पर नरहरिदासरु',
  kavi_laksmisa: 'कवि लक्ष्मीश', kavi_paramadevadasaru: 'कवि परमदेवदासरु', keladi_vemkanna_kavi: 'कॆळदि वॆंकण्ण कवि', kesavaviththalaru: 'केशवविठ्ठलरु', kosala_purisara: 'कोसल पुरीशर',
  krsnavithaladasaru: 'कृष्णविठलदासरु', laksminarayanarayaru: 'लक्ष्मीनारयणरायरु', mahanithivithala: 'महानिथिविठल', mahipathi_dasaru: 'महीपतिदासरु', malige_ramgasvamidasaru: 'मळिगॆ रंगस्वामिदासरु',
  mohana_dasaru: 'मोहनदासरु', muddumohanavithaladasaru: 'मुद्दुमोहनविठलदासरु', namjanagudu_tirumalamba: 'नंजनगूडु तिरुमलांबा', narasimha: 'नरसिंह', narasimhavithalaru: 'नरसिंहविठलरु',
  narayanadasaru: 'नारायणदासरु', nidaguruki_jivubayi: 'निडगुरुकि जीवूबायि', orabayi_laksmidevamma: 'ओरबायि लक्ष्मीदेवम्म', pamduramga: 'पांडुरंग', parisistam: 'परिशिष्टं',
  pavamje_laksminarnappayya: 'पावंजॆ लक्ष्मीनार्णप्पय्य', pradyumnatirtharu: 'प्रद्युम्नतीर्थरु', pranesha_dasaru: 'प्राणेशदासरु', prasanna_srinivasadasaru: 'प्रसन्न श्रीनिवासदासरु', prasanna_venkata_dasaru: 'प्रसन्नवेङ्कटदासरु',
  purandara_dasaru: 'पुरन्दरदासरु', radhabayi: 'राधाबायि', raghavendra: 'राघवेन्द्रः', raghuramavithaladasaru: 'रघुरामविठलदासरु', rajagopaladasaru: 'राजगोपालदासरु',
  ramadasaru: 'रामदासरु', ramapativithalaru: 'रमापतिविठलरु', ramgadasaru: 'रंगदासरु', ramgesavithaladasaru: 'रंगेशविठलदासरु', rukmamgadaru: 'रुक्मांगदरु',
  sadanamdaru: 'सदानंदरु', samasarmaru: 'शामशर्मरु', samasumdara_vithala: 'शामसुंदर विठल', samkarabhatta_agnihotri: 'शंकरभट्ट अग्निहोत्रि', sampattayyamgar: 'संपत्तय्यंगार्',
  samtibayi: 'शांतिबायि', saraguru_vemkatavaradaryaru: 'सरगूरु वॆंकटवरदार्यरु', sarasabayi: 'सरसाबायि', sarasvati_bayi: 'सरस्वति बायि', shyama_sundara_dasaru: 'श्यामसुन्दरदासरु',
  siddhagurutripuramtaka: 'सिद्धगुरुत्रिपुरांतक', sirigovimdavithala: 'सिरिगोविंदविठल', sirigurutamdevaradavithalaru: 'सिरिगुरुतंदॆवरदविठलरु', sirivatsamkitaru: 'सिरिवत्सांकितरु', sirivithalaru: 'सिरिविठलरु',
  sivaramaru: 'शिवरामरु', sridavithalaru: 'श्रीदविठलरु', srinidhivithalaru: 'श्रीनिधिविठलरु', sripadarajaru: 'श्रीपादराजरु', sripati: 'श्रीपति',
  srisa_kesavadasaru: 'श्रीश केशवदासरु', srisapranesavithalaru: 'श्रीशप्राणेशविठलरु', tamde_muddumohana_vithalaru: 'तंदॆ मुद्दुमोहन विठलरु', tamde_srinarahari: 'तंदॆ श्रीनरहरि', tamdevaradagopalavithalaru: 'तंदॆवरदगोपालविठलरु',
  timmappadasaru: 'तिम्मप्पदासरु', tulasiramadasaru: 'तुळसीरामदासरु', tupaki_vemkataramanacarya: 'तुपाकि वॆंकटरमणाचार्य', uragadrivasavithaladasaru: 'उरगाद्रिवासविठलदासरु', vadirajaru: 'वादिराजरु',
  varadesavithala: 'वरदेशविठल', varahatimmappa: 'वरहतिम्मप्प', varavaniramarayadasaru: 'वरावाणिरामरायदासरु', vemkatadasaru: 'वॆंकटदासरु', vemkatavaradaryaru: 'वॆंकटवरदार्यरु',
  vemkatesavitthala: 'वॆंकटेशविट्ठल', vemkatrav: 'वॆंकट्राव्', venugopaladasaru: 'वेणुगोपालदासरु', vidyakamtayatigalu: 'विद्याकांतयतिगळु', vidyaprasannatirtharu: 'विद्याप्रसन्नतीर्थरु',
  vidyaratnakaratirtharu: 'विद्यारत्नाकरतीर्थरु', vijaya_dasaru: 'विजयदासरु', vijaya_ramacamdravithala: 'विजय रामचंद्रविठल', vijayimdratirtharu: 'विजयींद्रतीर्थरु', viranarayana: 'वीरनारायण',
  visvapati: 'विश्वपति', visvemdratirtha: 'विश्वॆंद्रतीर्थ', vyasarayaru: 'व्यासरायरु', vyasatatvajnadasaru: 'व्यासतत्वज्ञदासरु', vyasaviththalaru: 'व्यासविठ्ठलरु',
  yadugiriyamma: 'यदुगिरियम्म',

  // 25 Aug 2026 -- systematic sweep of the taxonomy-folder-label gap
  // (project lead's own count: ~1055 English names in the library tree).
  // Scoped with a script cross-checked against the real filesystem (many
  // taxonomy.json entries have no folder on disk, and a chunk of the raw
  // count was metadata keys like Tattvavada/Itara/DasaSahitya's label/data/forms, not real
  // tree nodes -- both excluded). The Dvaita Vedanta commentary sub-folders
  // account for the largest single slice (~554 real folders); all but 33 of
  // those are already absorbed into the stitched multi-tab reader
  // (dgeFoldLayerEntries, layer_manifest.json) and never render as a separate
  // tree label at all -- the 33 real holdouts are included below, read
  // directly off each folder's own data.json content rather than guessed
  // from its slug. A handful of Tattvavada/Itara/DasaSahitya/composers/* entries are left
  // unlabeled on purpose, same call as the earlier composer batch (a title
  // filed as a composer name, a URL-garbled slug, the honest 'untitled'
  // bucket) -- see PENDING.md.
  // Agama -- Kashmir Shaivism / Pashupata
  tika_nirnaya: 'निर्णयः',
  bhashya_kaundinya: 'भाष्यम् (कौण्डिन्यः)',
  // Pancharatra samhitas
  naradiya_samhita: 'नारदीयसंहिता', parashara_samhita: 'पराशरसंहिता',
  vasishtha_samhita: 'वसिष्ठसंहिता', ahirbudhnya_samhita: 'अहिर्बुध्न्यसंहिता',
  hayagriva_samhita: 'हयग्रीवसंहिता', ishvara_samhita: 'ईश्वरसंहिता',
  lakshmi_tantra: 'लक्ष्मीतन्त्रम्', padma_samhita: 'पद्मसंहिता',
  parama_samhita: 'परमसंहिता', prakasha_samhita: 'प्रकाशसंहिता',
  vishnu_samhita: 'विष्णुसंहिता', vishvaksena_samhita: 'विष्वक्सेनसंहिता',
  jayakhya_samhita: 'जयाख्यसंहिता', paushkara_samhita: 'पौष्करसंहिता',
  sattvata_samhita: 'सात्त्वतसंहिता',
  // Mimamsa
  tika_kashika: 'काशिका', tika_nyayaratnakara: 'न्यायरत्नाकरः',
  tika_dipashikha: 'दीपशिखा', tika_rijuvimala: 'ऋजुविमला',
  shabara_bhashya: 'शाबरभाष्यम्',
  // Nyaya
  tika_dinakari: 'दिनकरी', tika_ramarudri: 'रामरुद्री',
  tika_siddhanta_muktavali: 'सिद्धान्तमुक्तावली',
  aloka: 'आलोकः', didhiti: 'दीधितिः', gadadhari: 'गादाधरी',
  jagadishi: 'जागदीशी', mathuri: 'माथुरी',
  bhashya_vatsyayana: 'भाष्यम् (वात्स्यायनः)',
  tatparya_parishuddhi: 'तात्पर्यपरिशुद्धिः', tatparya_tika: 'तात्पर्यटीका',
  varttika_uddyotakara: 'वार्त्तिकम् (उद्द्योतकरः)',
  tika_bhaskarodaya: 'भास्करोदयः', tika_nilakanthi: 'नीलकण्ठी',
  tika_nyayabodhini: 'न्यायबोधिनी', tika_padakritya: 'पदकृत्यम्',
  tika_sarvasva: 'सर्वस्वम्', tika_makaranda: 'मकरन्दः', tika_prakasha: 'प्रकाशः',
  // Sankhya
  sutra_and_karika: 'सूत्रकारिके', samkhya_karika: 'सांख्यकारिका',
  tika_gaudapada: 'गौडपादभाष्यम्', tika_tattva_kaumudi: 'तत्त्वकौमुदी',
  // Advaita
  bhashya: 'भाष्यम्', brihadaranyaka_upanishad: 'बृहदारण्यकोपनिषत्',
  // Vishishtadvaita
  ahobila_yati_34: 'अहोबिलयतिः ३४',
  adhikarana_saravali_padayojana: 'अधिकरणसारावलीपदयोजना',
  pada_yojana_bhumika: 'पदयोजनाभूमिका',
  appayya_dikshita: 'अप्पय्यदीक्षितः', naya_mayukha_malika: 'न्यायमयूखमालिका',
  deshikacharya: 'देशिकाचार्यः', adhikarana_ratnamala: 'अधिकरणरत्नमाला',
  devanathan: 'देवनाथन्', shribhashya_bhavaprakasha: 'श्रीभाष्यभावप्रकाशः',
  kumara_varada: 'कुमारवरदः', adhikarana_saravali_vyakhya: 'अधिकरणसारावलीव्याख्या',
  lakshmipuram_srinivasacharya: 'लक्ष्मीपुरम् श्रीनिवासाचार्यः',
  bhushanam: 'भूषणम्', nayasangatimalika: 'न्यायसङ्गतिमाला',
  nyaya_kalapa_sangraha: 'न्यायकलापसङ्ग्रहः',
  mukkur_yatindra: 'मुक्कूर् यतीन्द्रः', brahmasutrartha_padyamalika: 'ब्रह्मसूत्रार्थपद्यमालिका',
  perukkaranai_chakravarti: 'पेरुक्करणै चक्रवर्ती',
  sri_bhashya_sariraka_mimamsa_bhashya: 'श्रीभाष्यशारीरकमीमांसाभाष्यम्',
  rajagopala: 'राजगोपालः', ramabhadracharya: 'रामभद्राचार्यः',
  nitya_grantha_vivrti: 'नित्यग्रन्थविवृतिः',
  ramanuja_bhashya: 'रामानुजभाष्यम्', gadya_traya: 'गद्यत्रयम्',
  nitya_grantha: 'नित्यग्रन्थः', sharanagati_gadyam: 'शरणागतिगद्यम्',
  sri_bhashya: 'श्रीभाष्यम्', vedanta_dipa: 'वेदान्तदीपः', vedanta_sara: 'वेदान्तसारः',
  vedartha_sangraha: 'वेदार्थसङ्ग्रहः', ramanuja_tatacharya: 'रामानुजताताचार्यः',
  rangaramanuja: 'रङ्गरामानुजः', bhava_prakashika: 'भावप्रकाशिका',
  sharirika_shastrartha_dipika: 'शारीरकशास्त्रार्थदीपिका',
  vishaya_vakya_dipika: 'विषयवाक्यदीपिका', seneshvara: 'सेनेश्वरः',
  sudarshana_suri: 'सुदर्शनसूरिः', shruta_pradipika: 'श्रुतप्रदीपिका',
  shruta_prakashika: 'श्रुतप्रकाशिका',
  uttamur_viraraghavachariar: 'उत्तमूर् वीरराघवाचार्यः',
  bhashyartha_darpana: 'भाष्यार्थदर्पणः', shruta_prakashika_edition: 'श्रुतप्रकाशिका-संस्करणम्',
  vedanta_desika: 'वेदान्तदेशिकः', adhikarana_saravali: 'अधिकरणसारावली',
  // Yoga
  yoga_sutra: 'योगसूत्रम्', bhashya_vyasa: 'भाष्यम् (व्यासः)',
  tika_tattva_vaisharadi: 'तत्त्ववैशारदी',
  // Dasa Sahitya remainder
  narasimha_jagannatha_dasaru: 'नरसिंह जगन्नाथदासरु',
  sri_kapila_devara_stotra: 'श्री कपिलदेवर स्तोत्र',
  sri_mukhya_prana_devara_stotra: 'श्री मुख्यप्राणदेवर स्तोत्र',
  sri_narasimha_devara: 'श्री नरसिंहदेवर',
  sri_parvathi_devi_sthothra: 'श्री पार्वतीदेवि स्तोत्र',
  tulasi_devi_purandara_dasaru: 'तुळसीदेवि पुरन्दरदासरु',
  vayudevara_avathara_traya: 'वायुदेवर अवतारत्रय',
  harikathamrutasara: 'हरिकथामृतसारः',
  bhattasangraha: 'भट्टसङ्ग्रहः', bhavabodha: 'भावबोधः',
  gurvarthadipika: 'गुर्वर्थदीपिका', nyayamuktavali: 'न्यायमुक्तावली',
  parimala: 'परिमलः', sripadaraja: 'श्रीपादराजः',
  rukminisha_vijaya: 'रुक्मिणीशविजयः', svapna_vrindavana_akhyana: 'स्वप्नवृन्दावनाख्यानम्',
  yuktimallika: 'युक्तिमल्लिका', vijayendra_tirtha: 'विजयेन्द्रतीर्थः',
  vishnu_tirtha: 'विष्णुतीर्थः', vyasatatvajna_tirtha: 'व्यासतत्त्वज्ञतीर्थः',
  chandrika: 'चन्द्रिका', mandaramanjari: 'मन्दारमञ्जरी',
  tarkatandava: 'तर्कताण्डवः', tatparyachandrika: 'तात्पर्यचन्द्रिका',
  // Itihasa
  translation_ganguli: 'अनुवादः (गङ्गूली)',
  bhavishya_parva: 'भविष्यपर्व', harivamsha_parva: 'हरिवंशपर्व',
  vishnu_parva: 'विष्णुपर्व', saartha: 'सार्थः',
  // Purana
  brahma_parva: 'ब्रह्मपर्व', madhyama_parva: 'मध्यमपर्व',
  pratisarga_parva: 'प्रतिसर्गपर्व', uttara_parva: 'उत्तरपर्व',
  adhyatma_ramayana: 'अध्यात्मरामायणम्',
  lalitopakhyana_lalita_sahasranama: 'ललितोपाख्यानम् ललितासहस्रनाम',
  brahma_khanda: 'ब्रह्मखण्डः', ganesha_khanda: 'गणेशखण्डः',
  krishna_janma_khanda: 'कृष्णजन्मखण्डः', prakriti_khanda: 'प्रकृतिखण्डः',
  purva_khanda: 'पूर्वखण्डः', uttara_khanda_pretakalpa: 'उत्तरखण्डः (प्रेतकल्पः)',
  purva_bhaga: 'पूर्वभागः', uttara_bhaga: 'उत्तरभागः',
  devi_mahatmya_durga_saptashati: 'देवीमाहात्म्यम् (दुर्गासप्तशती)',
  matsya_purana: 'मत्स्यपुराणम्',
  uttarabhaga: 'उत्तरभागः', purana_mula: 'पुराणमूलम्',
  bhumi_khanda: 'भूमिखण्डः', kriya_yoga_sara_khanda: 'क्रियायोगसारखण्डः',
  patala_khanda: 'पातालखण्डः', srishti_khanda: 'सृष्टिखण्डः',
  svarga_khanda: 'स्वर्गखण्डः', uttara_khanda: 'उत्तरखण्डः',
  kailasa_samhita: 'कैलाससंहिता', kotirudra_samhita: 'कोटिरुद्रसंहिता',
  kumara_khanda: 'कुमारखण्डः', parvati_khanda: 'पार्वतीखण्डः',
  sati_khanda: 'सतीखण्डः', yuddha_khanda: 'युद्धखण्डः',
  shatarudra_samhita: 'शतरुद्रसंहिता', uma_samhita: 'उमासंहिता',
  vayaviya_samhita: 'वायवीयसंहिता', vidyeshvara_samhita: 'विद्येश्वरसंहिता',
  avantya_khanda: 'अवन्त्यखण्डः', kashi_khanda: 'काशीखण्डः',
  maheshvara_khanda: 'माहेश्वरखण्डः', nagara_khanda: 'नागरखण्डः',
  prabhasa_khanda: 'प्रभासखण्डः', revakhanda: 'रेवाखण्डः',
  vaishnava_khanda: 'वैष्णवखण्डः', saromahatmya: 'सरोमाहात्म्यम्',
  // Shastra -- Bauddha
  avadanashataka: 'अवदानशतकम्', divyavadana: 'दिव्यावदानम्',
  sanghabhedavastu: 'सङ्घभेदवस्तु', nyayabindu: 'न्यायबिन्दुः',
  abhidharma_kosha: 'अभिधर्मकोशः', tika_sphutartha: 'स्फुटार्था',
  ashtasahasrika_prajnaparamita: 'अष्टसाहस्रिका प्रज्ञापारमिता',
  bodhicaryavatara: 'बोधिचर्यावतारः', mula_madhyamaka_karika: 'मूलमध्यमककारिका',
  tika_prasannapada: 'प्रसन्नपदा', shikshasamuccaya: 'शिक्षासमुच्चयः',
  vimshatika: 'विंशतिका', lankavatara_sutra: 'लङ्कावतारसूत्रम्',
  saddharma_pundarika_sutra: 'सद्धर्मपुण्डरीकसूत्रम्',
  // Shastra -- Ratna Pariksha
  agastiya: 'आगस्त्यम्', ratnadipika: 'रत्नदीपिका',
  // Smriti/Dharmashastra
  chaturvarga_chintamani: 'चतुर्वर्गचिन्तामणिः', dayabhaga: 'दायभागः',
  dharma_sindhu: 'धर्मसिन्धुः', grihastha_ratnakara: 'गृहस्थरत्नाकरः',
  kalpataru: 'कल्पतरुः', mitakshara: 'मिताक्षरा',
  nirnaya_sindhu: 'निर्णयसिन्धुः', smriti_chandrika: 'स्मृतिचन्द्रिका',
  angiras_smriti: 'आङ्गिरस्स्मृतिः', atri_smriti: 'अत्रिस्मृतिः',
  brihaspati_smriti: 'बृहस्पतिस्मृतिः', daksha_smriti: 'दक्षस्मृतिः',
  harita_smriti: 'हारीतस्मृतिः', katyayana_smriti: 'कात्यायनस्मृतिः',
  likhita_smriti: 'लिखितस्मृतिः', manu_smriti: 'मनुस्मृतिः',
  narada_smriti: 'नारदस्मृतिः', parashara_smriti: 'पराशरस्मृतिः',
  pracetas_smriti: 'प्रचेतस्स्मृतिः', samvarta_smriti: 'संवर्तस्मृतिः',
  shankha_smriti: 'शङ्खस्मृतिः', shatatapa_smriti: 'शातातपस्मृतिः',
  ushanas_smriti: 'उशनस्स्मृतिः', vishnu_smriti: 'विष्णुस्मृतिः',
  yajnavalkya_smriti: 'याज्ञवल्क्यस्मृतिः', yama_smriti: 'यमस्मृतिः',
  // Stotra
  PrahladaKrutaNarasimha: 'प्रह्लादकृतनृसिंहस्तोत्रम्',
  // Upaveda
  madhava_nidana: 'माधवनिदानम्', bhavaprakasha_nighantu: 'भावप्रकाशनिघण्टुः',
  vahata_ashtanganighantu: 'वाहटाष्टाङ्गनिघण्टुः', sharngadhara_samhita: 'शार्ङ्गधरसंहिता',
  susruta_samhita_sutrasthana: 'सुश्रुतसंहिता (सूत्रस्थानम्)',
  kamasutra: 'कामसूत्रम्', pancashayaka: 'पञ्चसायकः', smaradipika: 'स्मरदीपिका',
  // Two Kamasutra digitizations kept side by side (28 Aug 2026 consolidation,
  // see core.js DGE_LEGACY_SLUGS) -- GRETIL plaintext (7 adhikaranas/36
  // adhyayas) vs DCS treebank (953 units), neither superseding the other.
  mula_gretil: 'मूलम् (GRETIL)', mula_dcs: 'मूलम् (DCS)',
  // Vedanga -- Kalpa
  gautama_dharmasutra: 'गौतमधर्मसूत्रम्', vasishtha_dharmasutra: 'वसिष्ठधर्मसूत्रम्',
  dharmasutra: 'धर्मसूत्रम्', shulbasutra: 'शुल्बसूत्रम्',
  grihyasutra: 'गृह्यसूत्रम्', shrautasutra: 'श्रौतसूत्रम्',
  // Vedanga -- Shiksha
  manduki_shiksha: 'माण्डूकीशिक्षा', paniniya_shiksha: 'पाणिनीयशिक्षा',
  rigveda_pratishakhya: 'ऋग्वेदप्रातिशाख्यम्', pushpasutra: 'पुष्पसूत्रम्',
  rik_tantra: 'ऋक्तन्त्रम्', shaunakiya_chaturadhyayika: 'शौनकीयचतुरध्यायिका',
  taittiriya_pratishakhya: 'तैत्तिरीयप्रातिशाख्यम्',
  vajasaneyi_pratishakhya: 'वाजसनेयिप्रातिशाख्यम्',
  apishali_shiksha: 'आपिशलिशिक्षा', shaishiriya_shiksha: 'शैशिरीयशिक्षा',
  shodashasloki_shiksha: 'षोडशश्लोकीशिक्षा', swarankusha_shiksha: 'स्वराङ्कुशशिक्षा',
  gautami_shiksha: 'गौतमीशिक्षा', lomashi_shiksha: 'लोमशीशिक्षा',
  naradiya_shiksha: 'नारदीयशिक्षा',
  aranya_shiksha: 'आरण्यशिक्षा', bharadwaja_shiksha: 'भारद्वाजशिक्षा',
  kauhaliya_shiksha: 'कौहलीयशिक्षा', sarvamammata_shiksha: 'सर्वसम्मतशिक्षा',
  shambhu_shiksha: 'शम्भुशिक्षा', siddhanta_shiksha: 'सिद्धान्तशिक्षा',
  vyasa_shiksha: 'व्यासशिक्षा', amoghanandini_shiksha: 'अमोघानन्दिनीशिक्षा',
  awasannirnaya_shiksha: 'अवसाननिर्णयशिक्षा', hastaswaraprakriya_shiksha: 'हस्तस्वरप्रक्रियाशिक्षा',
  katyayani_shiksha: 'कात्यायनीशिक्षा', keshavi_shiksha: 'केशवीशिक्षा',
  kramakarika_shiksha: 'क्रमकारिकाशिक्षा', kramasandhana_shiksha: 'क्रमसन्धानशिक्षा',
  laghu_amoghanandini_shiksha: 'लघ्वामोघानन्दिनीशिक्षा', madhyandini_shiksha: 'माध्यन्दिनीशिक्षा',
  manahswar_shiksha: 'मनस्वरशिक्षा', mandavya_shiksha: 'माण्डव्यशिक्षा',
  parashari_shiksha: 'पाराशरीशिक्षा',
  swarabhaktilakshanaparishishta_shiksha: 'स्वरभक्तिलक्षणपरिशिष्टशिक्षा',
  swarashtaka_shiksha: 'स्वराष्टकशिक्षा', varnaratnapradipika_shiksha: 'वर्णरत्नप्रदीपिकाशिक्षा',
  vasishthi_shiksha: 'वासिष्ठीशिक्षा', yajnavalkya_shiksha: 'याज्ञवल्क्यशिक्षा',
  yajurvidhana_shiksha: 'यजुर्विधानशिक्षा',
  // Vedanga -- Vyakarana
  aindra_school: 'ऐन्द्रं व्याकरणम्', balamanorama: 'बालमनोरमा',
  kashika: 'काशिका', kaumudi_order: 'कौमुदीक्रमः', nyasa: 'न्यासः',
  sutrapatha: 'सूत्रपाठः', tattvabodhini: 'तत्त्वबोधिनी', vasu: 'वासुः',
  chandra_vyakarana: 'चान्द्रव्याकरणम्', haima_shabdanushasana: 'हैमशब्दानुशासनम्',
  jainendra_vyakarana: 'जैनेन्द्रव्याकरणम्', katantra_vyakarana: 'कातन्त्रव्याकरणम्',
  mugdhabodha_vyakarana: 'मुग्धबोधव्याकरणम्', sarasvata_vyakarana: 'सारस्वतव्याकरणम्',
  shabdapatha: 'शब्दपाठः', shakatayana_vyakarana: 'शाकटायनव्याकरणम्',
  // Vedas -- Brahmanas/Aranyakas/Upanishads/Samhitas
  gopatha_brahmana: 'गोपथब्राह्मणम्', mandukya_upanishad: 'माण्डूक्योपनिषत्',
  mundaka_upanishad: 'मुण्डकोपनिषत्', prashna_upanishad: 'प्रश्नोपनिषत्',
  advayataraka_upanishad: 'अद्वयतारकोपनिषत्', avyakta_upanishad: 'अव्यक्तोपनिषत्',
  dattatreya_upanishad: 'दत्तात्रेयोपनिषत्', gopalatapani_upanishad: 'गोपालतापनीयोपनिषत्',
  hayagriva_upanishad: 'हयग्रीवोपनिषत्', kalisantarana_upanishad: 'कलिसन्तरणोपनिषत्',
  krishna_upanishad: 'कृष्णोपनिषत्', mahanarayana_upanishad: 'महानारायणोपनिषत्',
  narayana_upanishad: 'नारायणोपनिषत्',
  purva_tapaniya: 'पूर्वतापनीया', uttara_tapaniya: 'उत्तरतापनीया',
  ramarahasya_upanishad: 'रामरहस्योपनिषत्', ramatapaniya_upanishad: 'रामतापनीयोपनिषत्',
  tarasara_upanishad: 'तारसारोपनिषत्', vasudeva_upanishad: 'वासुदेवोपनिषत्',
  aitareya_aranyaka: 'ऐतरेयारण्यकम्', kausitaki_shankhayana_aranyaka: 'कौषीतकिशाङ्खायनारण्यकम्',
  aitareya_brahmana: 'ऐतरेयब्राह्मणम्', kausitaki_shankhayana_brahmana: 'कौषीतकिशाङ्खायनब्राह्मणम्',
  kausitaki_upanishad: 'कौषीतक्युपनिषत्',
  jaiminiya_talavakara_aranyaka: 'जैमिनीयतलवकारारण्यकम्',
  jaiminiya_arsheya_brahmana: 'जैमिनीयार्षेयब्राह्मणम्', jaiminiya_brahmana: 'जैमिनीयब्राह्मणम्',
  jaiminiya_upanishad_brahmana: 'जैमिनीयोपनिषद्ब्राह्मणम्', kena_upanishad: 'केनोपनिषत्',
  arsheya_brahmana: 'आर्षेयब्राह्मणम्', chandogya_upanishad_brahmana: 'छान्दोग्योपनिषद्ब्राह्मणम्',
  devatadhyaya_brahmana: 'देवताध्यायब्राह्मणम्', panchavimsha_tandya_brahmana: 'पञ्चविंशब्राह्मणम् (ताण्ड्यम्)',
  samavidhana_brahmana: 'सामविधानब्राह्मणम्', samhitopanishad_brahmana: 'संहितोपनिषद्ब्राह्मणम्',
  shadvimsha_brahmana: 'षड्विंशब्राह्मणम्', vamsha_brahmana: 'वंशब्राह्मणम्',
  chandogya_upanishad: 'छान्दोग्योपनिषत्',
  ashtanga_nighantu: 'अष्टाङ्गनिघण्टुः', bija_nighantu: 'बीजनिघण्टुः',
  dhanvantari_nighantu: 'धन्वन्तरिनिघण्टुः', kaiyadeva_nighantu: 'कैयदेवनिघण्टुः',
  madanapala_nighantu: 'मदनपालनिघण्टुः', nighantushesha: 'निघण्टुशेषः',
  raja_nighantu: 'राजनिघण्टुः',
  rasadhyaya: 'रसाध्यायः', rasahridaya_tantra: 'रसहृदयतन्त्रम्',
  rasakamadhenu: 'रसकामधेनुः', rasamanjari: 'रसमञ्जरी',
  rasaprakashasudhakara: 'रसप्रकाशसुधाकरः', rasaratnakara: 'रसरत्नाकरः',
  rasaratnasamuccaya: 'रसरत्नसमुच्चयः', tika_bodhini: 'बोधिनी', tika_dipika: 'दीपिका',
  rasarnava: 'रसार्णवः', rasarnavakalpa: 'रसार्णवकल्पः',
  rasasanketakalika: 'रससङ्केतकलिका', rasatarangini: 'रसतरङ्गिणी',
  rasendracintamani: 'रसेन्द्रचिन्तामणिः', rasendracudamani: 'रसेन्द्रचूडामणिः',
  rasendrasarasangraha: 'रसेन्द्रसारसङ्ग्रहः',
  ashtanga_hridaya_samhita: 'अष्टाङ्गहृदयसंहिता',
  tika_hemadri: 'हेमाद्रिः', tika_indu: 'इन्दुः',
  tika_padarthacandrika: 'पदार्थचन्द्रिका', tika_sarvangasundara: 'सर्वाङ्गसुन्दरा',
  ashtanga_sangraha: 'अष्टाङ्गसङ्ग्रहः', bhavaprakasha: 'भावप्रकाशः',
  caraka_samhita: 'चरकसंहिता', tika_ayurvedadipika: 'आयुर्वेददीपिका',
  tika_tattvapradipika: 'तत्त्वप्रदीपिका', nadi_pariksha: 'नाडीपरीक्षा',
  sushruta_samhita: 'सुश्रुतसंहिता', tika_nibandhasangraha: 'निबन्धसङ्ग्रहः',
  yogaratnakara: 'योगरत्नाकरः',
  katha_kapisthala_brahmana: 'काठकपिष्ठलब्राह्मणम्', kapisthala_katha_samhita: 'काठकपिष्ठलसंहिता',
  kathaka_brahmana: 'काठकब्राह्मणम्', katha_samhita: 'काठकसंहिता',
  katha_upanishad: 'कठोपनिषत्',
  maitrayani_brahmana: 'मैत्रायणीब्राह्मणम्', maitrayani_samhita: 'मैत्रायणीसंहिता',
  maitrayaniya_upanishad: 'मैत्रायणीयोपनिषत्', taittiriya_upanishad: 'तैत्तिरीयोपनिषत्',
  shatapatha_brahmana_kanva: 'शतपथब्राह्मणम् (काण्वम्)',
  brihadaranyaka_upanishad_kanva: 'बृहदारण्यकोपनिषत् (काण्वम्)',
  isha_upanishad_kanva: 'ईशोपनिषत् (काण्वम्)',
  shatapatha_brahmana_madhyandina: 'शतपथब्राह्मणम् (माध्यन्दिनम्)',
  brihadaranyaka_upanishad_madhyandina: 'बृहदारण्यकोपनिषत् (माध्यन्दिनम्)',
  isha_upanishad: 'ईशोपनिषत्',
  // Dvaita Vedanta -- the 33 visible (not stitched-tab-folded) leftovers,
  // read directly off each folder's own data.json (sanskrit_text/section
  // fields) rather than guessed from the slug.
  tika_jayatirtha: 'जयतीर्थः',
  tika_arjuna_uvaca: 'अर्जुन उवाच',
  tika_mandopakarini: 'मन्दोपाकारिणी',
  tika_padarthadipikodbodhika: 'पदार्थदीपिकोद्बोधिका',
  tika_iti_shrimadvedangamuni: 'श्रीमद्वेदाङ्गमुनिः',
  tika_iti_shrinarayanapanditacarya: 'श्रीनारायणपण्डिताचार्यः',
  tika_shrichalarisheshacarya: 'श्रीछलारिशेषाचार्यः',
  tika_prakashika: 'भावप्रकाशिका', tika_kiranavali: 'किरणावली',
  tika_nyayasudha: 'श्रीमन्न्यायसुधा',
  tika_abhimanyadhikaranam: 'अभिमान्यधिकरणम्',
  tika_akashadhikaranam: 'आकाशाधिकरणम्',
  tika_anandamayadhikaranam: 'आनन्दमयाधिकरणम्',
  tika_antasthatvadhikaranam: 'अन्तस्थत्वाधिकरणम्',
  tika_antimapranadhikaranam: 'अन्तिमप्राणाधिकरणम्',
  tika_anumanikadhikaranam: 'आनुमानिकाधिकरणम्',
  tika_arambhanadhikaranam: 'आरम्भणाधिकरणम्',
  tika_asadadhikaranam: 'असदधिकरणम्',
  tika_atmadhikaranam: 'आत्माधिकरणम्',
  tika_bhoktradhikaranam: 'भोक्त्रधिकरणम्',
  tika_brahmadhikaranam: 'ब्रह्माधिकरणम्',
  tika_gayatryadhikaranam: 'गायत्र्यधिकरणम्',
  tika_ikshatyadhikaranam: 'ईक्षत्यधिकरणम्',
  tika_itaravyapadeshadhikaranam: 'इतरव्यपदेशाधिकरणम्',
  tika_janmadhikaranam: 'जन्माधिकरणम्',
  tika_jijnasadhikaranam: 'जिज्ञासाधिकरणम्',
  tika_napratikadhikaranam: 'न प्रतीकाधिकरणम्',
  tika_naprayojanadhikaranam: 'न प्रयोजनाधिकरणम्',
  tika_navilakshanatvadhikaranam: 'न विलक्षणत्वाधिकरणम्',
  tika_pranadhikaranam: 'प्राणाधिकरणम्',
  tika_samanvayadhikaranam: 'समन्वयाधिकरणम्',
  tika_sarvadharmopapattyadhikaranam: 'सर्वधर्मोपपत्त्यधिकरणम्',
  tika_shabdamulatvadhikaranam: 'शब्दमूलत्वाधिकरणम्',
  tika_shastrayonitvadhikaranam: 'शास्त्रयोनित्वाधिकरणम्',
  tika_tadadhigamadhikaranam: 'तदधिगमाधिकरणम्',
  tika_vaishamyanairghrinyadhikaranam: 'वैषम्यनैर्घृण्याधिकरणम्',
};
