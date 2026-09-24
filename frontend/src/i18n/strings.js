/**
 * Every phrase the interface shows, in the three languages it speaks.
 *
 * The three versions of a phrase sit together on one line, so a missing or
 * stale translation is obvious while reading rather than something you find
 * by comparing three files. A key with no translation for the chosen language
 * falls back to English — never to a blank space or the key itself.
 *
 * WHAT IS NOT HERE
 * ----------------
 * Text the SERVER writes: the robot's answers, the traffic agent's alerts and
 * its reasons. Those are generated from measured figures in app/services, and
 * translating them means translating there — not restating them here, where
 * the two copies would drift apart and the interface would start claiming
 * things the system did not say.
 *
 * Hindi and Telugu were written for this app rather than taken from a
 * standard glossary. If a term reads oddly to a native speaker, it is a bug
 * worth reporting.
 */

export const STRINGS = {
  /* ------------------------------------------------------------ navigation */
  'nav.dashboard': { en: 'Dashboard', hi: 'डैशबोर्ड', te: 'డాష్‌బోర్డ్' },
  'nav.liveTraffic': { en: 'Live Traffic', hi: 'लाइव ट्रैफ़िक', te: 'ప్రత్యక్ష ట్రాఫిక్' },
  'nav.analytics': { en: 'Analytics', hi: 'विश्लेषण', te: 'విశ్లేషణలు' },
  'nav.lab': { en: 'Traffic Analysis Lab', hi: 'ट्रैफ़िक विश्लेषण लैब', te: 'ట్రాఫిక్ విశ్లేషణ ల్యాబ్' },
  'nav.benchmark': { en: 'Benchmark', hi: 'बेंचमार्क', te: 'బెంచ్‌మార్క్' },
  'nav.alerts': { en: 'Alerts', hi: 'अलर्ट', te: 'హెచ్చరికలు' },
  'nav.history': { en: 'History', hi: 'इतिहास', te: 'చరిత్ర' },
  'nav.settings': { en: 'Settings', hi: 'सेटिंग्स', te: 'సెట్టింగ్‌లు' },
  'nav.logout': { en: 'Logout', hi: 'लॉग आउट', te: 'లాగ్ అవుట్' },
  'nav.yourJourneys': { en: 'Your journeys', hi: 'आपकी यात्राएँ', te: 'మీ ప్రయాణాలు' },
  'nav.adminConsole': { en: 'Admin console', hi: 'एडमिन कंसोल', te: 'అడ్మిన్ కన్సోల్' },

  /* --------------------------------------------------------------- navbar */
  'navbar.signOut': { en: 'Sign out', hi: 'साइन आउट', te: 'సైన్ అవుట్' },
  'navbar.notifications': { en: 'Notifications', hi: 'सूचनाएँ', te: 'నోటిఫికేషన్‌లు' },
  'navbar.caughtUp': { en: "You're all caught up", hi: 'कुछ भी नया नहीं है', te: 'కొత్తవి ఏమీ లేవు' },

  /* ---------------------------------------------------------------- login */
  'login.signIn': { en: 'Sign In', hi: 'साइन इन', te: 'సైన్ ఇన్' },
  'login.registerAsUser': { en: 'Register as User', hi: 'उपयोगकर्ता पंजीकरण', te: 'వినియోగదారుగా నమోదు' },
  'login.adminAccess': { en: 'Admin Access', hi: 'एडमिन एक्सेस', te: 'అడ్మిన్ యాక్సెస్' },
  'login.adminNote': {
    en: 'For the traffic control room. Admin accounts are issued by whoever runs the Q Route server, so there is no admin sign-up.',
    hi: 'यह ट्रैफ़िक कंट्रोल रूम के लिए है। एडमिन खाते Q Route सर्वर चलाने वाले द्वारा ही बनाए जाते हैं, इसलिए एडमिन पंजीकरण उपलब्ध नहीं है।',
    te: 'ఇది ట్రాఫిక్ కంట్రోల్ రూమ్ కోసం. అడ్మిన్ ఖాతాలను Q Route సర్వర్ నడిపే వారే ఇస్తారు, అందుకే అడ్మిన్ నమోదు ఉండదు.',
  },
  'login.signInAsAdmin': { en: 'Sign in as admin', hi: 'एडमिन के रूप में साइन इन करें', te: 'అడ్మిన్‌గా సైన్ ఇన్ చేయండి' },
  'login.notAdmin': { en: 'This account does not have admin access. Use the Sign In tab.', hi: 'इस खाते के पास एडमिन एक्सेस नहीं है। साइन इन टैब का उपयोग करें।', te: 'ఈ ఖాతాకు అడ్మిన్ యాక్సెస్ లేదు. సైన్ ఇన్ ట్యాబ్ వాడండి.' },
  'login.serverUnreachable': { en: 'Cannot reach the Q Route server. Is the backend running?', hi: 'Q Route सर्वर तक नहीं पहुँच सके। क्या बैकएंड चल रहा है?', te: 'Q Route సర్వర్‌ను చేరుకోలేకపోయాం. బ్యాకెండ్ నడుస్తోందా?' },
  'login.enterName': { en: 'Please enter your name.', hi: 'कृपया अपना नाम दर्ज करें।', te: 'దయచేసి మీ పేరు నమోదు చేయండి.' },
  'login.validEmail': { en: 'Enter a valid email address.', hi: 'मान्य ईमेल पता दर्ज करें।', te: 'సరైన ఇమెయిల్ చిరునామా నమోదు చేయండి.' },
  'login.enterPassword': { en: 'Enter your password.', hi: 'अपना पासवर्ड दर्ज करें।', te: 'మీ పాస్‌వర్డ్ నమోదు చేయండి.' },
  'login.passwordsDiffer': { en: 'The two passwords do not match.', hi: 'दोनों पासवर्ड मेल नहीं खाते।', te: 'రెండు పాస్‌వర్డ్‌లు సరిపోలడం లేదు.' },
  'login.passwordTooShort': { en: 'Use a password of at least {n} characters.', hi: 'कम से कम {n} अक्षरों का पासवर्ड चुनें।', te: 'కనీసం {n} అక్షరాల పాస్‌వర్డ్ వాడండి.' },
  'login.offlineNoAdmin': { en: 'Admin access needs the server; offline mode has no admins.', hi: 'एडमिन एक्सेस के लिए सर्वर चाहिए; ऑफ़लाइन मोड में एडमिन नहीं होते।', te: 'అడ్మిన్ యాక్సెస్‌కు సర్వర్ కావాలి; ఆఫ్‌లైన్ మోడ్‌లో అడ్మిన్‌లు ఉండరు.' },

  /* ------------------------------------------------------- the sign-in form */
  'auth.fullName': { en: 'Full Name', hi: 'पूरा नाम', te: 'పూర్తి పేరు' },
  'auth.emailAddress': { en: 'Email Address', hi: 'ईमेल पता', te: 'ఇమెయిల్ చిరునామా' },
  'auth.password': { en: 'Password', hi: 'पासवर्ड', te: 'పాస్‌వర్డ్' },
  'auth.confirmPassword': { en: 'Confirm Password', hi: 'पासवर्ड की पुष्टि करें', te: 'పాస్‌వర్డ్ నిర్ధారించండి' },
  'auth.namePlaceholder': { en: 'e.g. Your Name', hi: 'उदा. आपका नाम', te: 'ఉదా. మీ పేరు' },
  'auth.passwordMin': { en: 'At least {n} characters', hi: 'कम से कम {n} अक्षर', te: 'కనీసం {n} అక్షరాలు' },
  'auth.passwordAgain': { en: 'Type the password again', hi: 'पासवर्ड फिर से लिखें', te: 'పాస్‌వర్డ్ మళ్లీ టైప్ చేయండి' },
  'auth.yourPassword': { en: 'Your password', hi: 'आपका पासवर्ड', te: 'మీ పాస్‌వర్డ్' },
  'auth.createAccount': { en: 'Create Account', hi: 'खाता बनाएँ', te: 'ఖాతా సృష్టించు' },
  'auth.processing': { en: 'Processing…', hi: 'प्रक्रिया जारी…', te: 'ప్రాసెస్ అవుతోంది…' },
  'auth.noAccount': { en: "Don't have an account?", hi: 'खाता नहीं है?', te: 'ఖాతా లేదా?' },
  'auth.haveAccount': { en: 'Already have an account?', hi: 'पहले से खाता है?', te: 'ఇప్పటికే ఖాతా ఉందా?' },
  'auth.registerLink': { en: 'Register', hi: 'पंजीकरण करें', te: 'నమోదు చేసుకోండి' },
  'auth.notAdmin': { en: 'Not an admin?', hi: 'एडमिन नहीं हैं?', te: 'అడ్మిన్ కాదా?' },
  'auth.signInAsUser': { en: 'Sign in as a user', hi: 'उपयोगकर्ता के रूप में साइन इन करें', te: 'వినియోగదారుగా సైన్ ఇన్ చేయండి' },
  'auth.msgIdle': { en: 'Hi there! 👋', hi: 'नमस्ते! 👋', te: 'హాయ్! 👋' },
  'auth.msgName': { en: 'What is your full name? 🖋️', hi: 'आपका पूरा नाम क्या है? 🖋️', te: 'మీ పూర్తి పేరు ఏమిటి? 🖋️' },
  'auth.msgEmail': { en: 'Enter your email address 📧', hi: 'अपना ईमेल पता दर्ज करें 📧', te: 'మీ ఇమెయిల్ చిరునామా నమోదు చేయండి 📧' },
  'auth.msgPassword': { en: 'Turning around! Your password is 100% private 🙈🔒', hi: 'मैं मुड़ गया! आपका पासवर्ड पूरी तरह निजी है 🙈🔒', te: 'నేను అటు తిరిగాను! మీ పాస్‌వర్డ్ పూర్తిగా గోప్యం 🙈🔒' },
  'auth.msgWelcomeBack': { en: 'Welcome back! Good to see you 😊', hi: 'वापसी पर स्वागत है! आपसे मिलकर अच्छा लगा 😊', te: 'తిరిగి స్వాగతం! మిమ్మల్ని చూడటం సంతోషం 😊' },
  'auth.msgConfirm': { en: 'Once more, so a typo cannot lock you out 🔁', hi: 'एक बार और, ताकि टाइपिंग की गलती आपको बाहर न कर दे 🔁', te: 'మరోసారి, టైపింగ్ పొరపాటు మిమ్మల్ని బయట ఉంచకుండా 🔁' },
  'auth.msgAdmin': { en: 'Admin access. Accounts are issued, not registered 🛡️', hi: 'एडमिन एक्सेस। खाते जारी किए जाते हैं, पंजीकृत नहीं 🛡️', te: 'అడ్మిన్ యాక్సెస్. ఖాతాలు ఇవ్వబడతాయి, నమోదు కావు 🛡️' },

  /* ------------------------------------------------------ settings, shared */
  'settings.title': { en: 'Settings', hi: 'सेटिंग्स', te: 'సెట్టింగ్‌లు' },
  'settings.language': { en: 'Language', hi: 'भाषा', te: 'భాష' },
  'settings.interfaceLanguage': { en: 'Interface language', hi: 'इंटरफ़ेस की भाषा', te: 'ఇంటర్‌ఫేస్ భాష' },
  'settings.languageHint': {
    en: 'Menus, buttons and your own pages. Traffic alerts and the assistant still answer in English — those sentences are written by the server from measured figures.',
    hi: 'मेन्यू, बटन और आपके पृष्ठ। ट्रैफ़िक अलर्ट और सहायक अभी भी अंग्रेज़ी में उत्तर देते हैं — वे वाक्य सर्वर मापे गए आँकड़ों से बनाता है।',
    te: 'మెనూలు, బటన్లు, మీ పేజీలు. ట్రాఫిక్ హెచ్చరికలు, సహాయకుడు ఇంకా ఇంగ్లిష్‌లోనే సమాధానమిస్తాయి — ఆ వాక్యాలను సర్వర్ కొలిచిన అంకెల నుండి రాస్తుంది.',
  },
  'settings.appearance': { en: 'Appearance', hi: 'रूप-रंग', te: 'రూపం' },
  'settings.darkMode': { en: 'Dark mode', hi: 'डार्क मोड', te: 'డార్క్ మోడ్' },
  'settings.darkHint': { en: 'Stored in this browser.', hi: 'इसी ब्राउज़र में सहेजा जाता है।', te: 'ఈ బ్రౌజర్‌లోనే భద్రపరచబడుతుంది.' },
  'settings.saved': { en: 'Saved.', hi: 'सहेजा गया।', te: 'భద్రపరచబడింది.' },
  'settings.savedToAccount': { en: 'Saved to your account.', hi: 'आपके खाते में सहेजा गया।', te: 'మీ ఖాతాలో భద్రపరచబడింది.' },

  /* ------------------------------------------------------- admin settings */
  'adminSettings.subtitle': { en: 'Preferences are stored in this browser only.', hi: 'ये प्राथमिकताएँ केवल इसी ब्राउज़र में सहेजी जाती हैं।', te: 'ఈ ప్రాధాన్యతలు ఈ బ్రౌజర్‌లో మాత్రమే భద్రపరచబడతాయి.' },
  'adminSettings.darkHint': { en: 'The interface is designed dark-first.', hi: 'यह इंटरफ़ेस पहले डार्क के लिए बनाया गया है।', te: 'ఈ ఇంటర్‌ఫేస్ ముందుగా డార్క్ కోసం రూపొందించబడింది.' },
  'adminSettings.mapStyle': { en: 'Map style', hi: 'मानचित्र शैली', te: 'మ్యాప్ శైలి' },
  'adminSettings.optimization': { en: 'Optimization', hi: 'ऑप्टिमाइज़ेशन', te: 'ఆప్టిమైజేషన్' },
  'adminSettings.preferredAlgorithm': { en: 'Preferred algorithm', hi: 'पसंदीदा एल्गोरिद्म', te: 'ఇష్టపడే అల్గారిథమ్' },
  'adminSettings.avoidTolls': { en: 'Avoid toll roads', hi: 'टोल सड़कों से बचें', te: 'టోల్ రోడ్లను తప్పించు' },
  'adminSettings.avoidHighways': { en: 'Avoid highways', hi: 'हाईवे से बचें', te: 'హైవేలను తప్పించు' },
  'adminSettings.sensitivity': { en: 'Sensitivity', hi: 'संवेदनशीलता', te: 'సున్నితత్వం' },
  'adminSettings.congestionSensitivity': { en: 'Congestion sensitivity', hi: 'भीड़ के प्रति संवेदनशीलता', te: 'రద్దీ పట్ల సున్నితత్వం' },
  'adminSettings.congestionHint': { en: 'How strongly congestion is weighted relative to time and distance.', hi: 'समय और दूरी की तुलना में भीड़ को कितना महत्व दिया जाए।', te: 'సమయం, దూరంతో పోలిస్తే రద్దీకి ఎంత ప్రాధాన్యం ఇవ్వాలి.' },
  'adminSettings.alertThreshold': { en: 'Alert threshold', hi: 'अलर्ट सीमा', te: 'హెచ్చరిక పరిమితి' },
  'adminSettings.alertHint': { en: 'Only alert when an alternative saves at least this much time.', hi: 'तभी अलर्ट करें जब कोई विकल्प कम से कम इतना समय बचाए।', te: 'ప్రత్యామ్నాయం కనీసం ఇంత సమయం ఆదా చేస్తేనే హెచ్చరించు.' },
  'adminSettings.notifications': { en: 'Notifications', hi: 'सूचनाएँ', te: 'నోటిఫికేషన్‌లు' },
  'adminSettings.predictiveAlerts': { en: 'Predictive alerts', hi: 'पूर्वानुमान अलर्ट', te: 'ముందస్తు అంచనా హెచ్చరికలు' },
  'adminSettings.predictiveHint': { en: 'Forecast congestion before it happens.', hi: 'भीड़ होने से पहले उसका पूर्वानुमान।', te: 'రద్దీ జరగకముందే అంచనా.' },
  'adminSettings.incidentAlerts': { en: 'Incident alerts', hi: 'घटना अलर्ट', te: 'ఘటన హెచ్చరికలు' },
  'adminSettings.incidentHint': { en: 'Accidents, closures and waterlogging.', hi: 'दुर्घटनाएँ, बंद सड़कें और जलभराव।', te: 'ప్రమాదాలు, మూసివేతలు, నీటి నిల్వ.' },
  'adminSettings.routeChange': { en: 'Route change suggestions', hi: 'मार्ग बदलने के सुझाव', te: 'మార్గం మార్చమనే సూచనలు' },
  'adminSettings.routeChangeHint': { en: 'Notify when a better route appears.', hi: 'बेहतर मार्ग मिलने पर सूचित करें।', te: 'మెరుగైన మార్గం దొరికితే తెలియజేయి.' },
  'adminSettings.session': { en: 'Session', hi: 'सत्र', te: 'సెషన్' },
  'adminSettings.sessionHint': { en: 'Clear the current routes, traffic simulation and alerts.', hi: 'मौजूदा मार्ग, ट्रैफ़िक सिमुलेशन और अलर्ट हटाएँ।', te: 'ప్రస్తుత మార్గాలు, ట్రాఫిక్ అనుకరణ, హెచ్చరికలను తొలగించు.' },
  'adminSettings.resetScenario': { en: 'Reset Scenario', hi: 'परिदृश्य रीसेट करें', te: 'సన్నివేశాన్ని రీసెట్ చేయి' },

  /* -------------------------------------------------------- user settings */
  'userSettings.subtitleAccount': { en: 'Saved to your account, on every device you sign in from.', hi: 'आपके खाते में सहेजा जाता है, हर उस डिवाइस पर जहाँ आप साइन इन करते हैं।', te: 'మీ ఖాతాలో భద్రపరచబడుతుంది, మీరు సైన్ ఇన్ చేసే ప్రతి పరికరంలో.' },
  'userSettings.subtitleOffline': { en: 'Offline demo account: nothing here is saved to a server.', hi: 'ऑफ़लाइन डेमो खाता: यहाँ कुछ भी सर्वर पर सहेजा नहीं जाता।', te: 'ఆఫ్‌లైన్ డెమో ఖాతా: ఇక్కడ ఏదీ సర్వర్‌లో భద్రపరచబడదు.' },
  'userSettings.profile': { en: 'Profile', hi: 'प्रोफ़ाइल', te: 'ప్రొఫైల్' },
  'userSettings.name': { en: 'Name', hi: 'नाम', te: 'పేరు' },
  'userSettings.email': { en: 'Email', hi: 'ईमेल', te: 'ఇమెయిల్' },
  'userSettings.emailHintGoogle': { en: 'Signed in with Google. Email cannot be changed here.', hi: 'Google से साइन इन किया है। ईमेल यहाँ नहीं बदला जा सकता।', te: 'Googleతో సైన్ ఇన్ చేశారు. ఇమెయిల్ ఇక్కడ మార్చలేరు.' },
  'userSettings.emailHint': { en: 'Your sign-in email. Email cannot be changed here.', hi: 'आपका साइन-इन ईमेल। ईमेल यहाँ नहीं बदला जा सकता।', te: 'మీ సైన్-ఇన్ ఇమెయిల్. ఇమెయిల్ ఇక్కడ మార్చలేరు.' },
  'userSettings.saveName': { en: 'Save name', hi: 'नाम सहेजें', te: 'పేరు భద్రపరచు' },
  'userSettings.nameEmpty': { en: 'Your name cannot be empty.', hi: 'नाम खाली नहीं हो सकता।', te: 'పేరు ఖాళీగా ఉండకూడదు.' },
  'userSettings.password': { en: 'Password', hi: 'पासवर्ड', te: 'పాస్‌వర్డ్' },
  'userSettings.currentPassword': { en: 'Current password', hi: 'वर्तमान पासवर्ड', te: 'ప్రస్తుత పాస్‌వర్డ్' },
  'userSettings.newPassword': { en: 'New password', hi: 'नया पासवर्ड', te: 'కొత్త పాస్‌వర్డ్' },
  'userSettings.newPasswordAgain': { en: 'New password, again', hi: 'नया पासवर्ड, फिर से', te: 'కొత్త పాస్‌వర్డ్, మళ్లీ' },
  'userSettings.changePassword': { en: 'Change password', hi: 'पासवर्ड बदलें', te: 'పాస్‌వర్డ్ మార్చు' },
  'userSettings.passwordChanged': { en: 'Password changed.', hi: 'पासवर्ड बदल दिया गया।', te: 'పాస్‌వర్డ్ మార్చబడింది.' },
  'userSettings.passwordShort': { en: 'Use at least 8 characters.', hi: 'कम से कम 8 अक्षर रखें।', te: 'కనీసం 8 అక్షరాలు వాడండి.' },
  'userSettings.passwordsDiffer': { en: 'The new passwords do not match.', hi: 'नए पासवर्ड मेल नहीं खाते।', te: 'కొత్త పాస్‌వర్డ్‌లు సరిపోలడం లేదు.' },
  'userSettings.googleNoPassword': { en: 'You sign in with Google, so there is no Q Route password to change.', hi: 'आप Google से साइन इन करते हैं, इसलिए बदलने के लिए कोई Q Route पासवर्ड नहीं है।', te: 'మీరు Googleతో సైన్ ఇన్ చేస్తారు, కాబట్టి మార్చడానికి Q Route పాస్‌వర్డ్ లేదు.' },
  'userSettings.noPassword': { en: 'This account has no password set.', hi: 'इस खाते के लिए कोई पासवर्ड सेट नहीं है।', te: 'ఈ ఖాతాకు పాస్‌వర్డ్ సెట్ చేయలేదు.' },
  'userSettings.offlineNoPassword': { en: 'Offline demo accounts have no password.', hi: 'ऑफ़लाइन डेमो खातों का कोई पासवर्ड नहीं होता।', te: 'ఆఫ్‌లైన్ డెమో ఖాతాలకు పాస్‌వర్డ్ ఉండదు.' },
  'userSettings.routePreferences': { en: 'Route preferences', hi: 'मार्ग प्राथमिकताएँ', te: 'మార్గ ప్రాధాన్యతలు' },
  'userSettings.defaultVehicle': { en: 'Default vehicle', hi: 'डिफ़ॉल्ट वाहन', te: 'డిఫాల్ట్ వాహనం' },
  'userSettings.vehicleHint': { en: 'Routes avoid roads your vehicle may not use.', hi: 'मार्ग उन सड़कों से बचते हैं जिन पर आपका वाहन नहीं चल सकता।', te: 'మీ వాహనం వెళ్లలేని రోడ్లను మార్గాలు తప్పిస్తాయి.' },
  'userSettings.defaultRoutePreference': { en: 'Default route preference', hi: 'डिफ़ॉल्ट मार्ग प्राथमिकता', te: 'డిఫాల్ట్ మార్గ ప్రాధాన్యత' },
  'userSettings.autoOpen': { en: 'Open the assistant for route alerts', hi: 'मार्ग अलर्ट पर सहायक खोलें', te: 'మార్గ హెచ్చరికలకు సహాయకుడిని తెరువు' },
  'userSettings.autoOpenHint': { en: 'When a faster route appears, Q Route AI opens and tells you. Off: a red badge on the robot instead.', hi: 'तेज़ मार्ग मिलने पर Q Route AI खुलकर बताता है। बंद होने पर रोबोट पर लाल निशान दिखता है।', te: 'వేగవంతమైన మార్గం దొరికితే Q Route AI తెరుచుకుని చెబుతుంది. ఆఫ్ చేస్తే రోబోట్‌పై ఎరుపు గుర్తు మాత్రమే.' },
  'userSettings.signedInAs': { en: 'Signed in as', hi: 'साइन इन हैं:', te: 'సైన్ ఇన్ అయినది:' },

  /* ---------------------------------------------------------- route planner */
  'planner.title': { en: 'Route Planner', hi: 'मार्ग योजनाकार', te: 'మార్గ ప్రణాళిక' },
  'planner.roadNetwork': { en: 'Road network', hi: 'सड़क नेटवर्क', te: 'రహదారి నెట్‌వర్క్' },
  'planner.startLocation': { en: 'Start location', hi: 'प्रारंभ स्थान', te: 'ప్రారంభ స్థలం' },
  'planner.destination': { en: 'Destination', hi: 'गंतव्य', te: 'గమ్యం' },
  'planner.routePreference': { en: 'Route preference', hi: 'मार्ग प्राथमिकता', te: 'మార్గ ప్రాధాన్యత' },
  'planner.algorithm': { en: 'Algorithm', hi: 'एल्गोरिद्म', te: 'అల్గారిథమ్' },
  'planner.objective': { en: 'Optimization objective', hi: 'ऑप्टिमाइज़ेशन उद्देश्य', te: 'ఆప్టిమైజేషన్ లక్ష్యం' },
  'planner.optimizeRoute': { en: 'Optimize Route', hi: 'मार्ग ऑप्टिमाइज़ करें', te: 'మార్గాన్ని ఆప్టిమైజ్ చేయి' },
  'planner.optimizing': { en: 'Optimizing…', hi: 'ऑप्टिमाइज़ हो रहा है…', te: 'ఆప్టిమైజ్ అవుతోంది…' },
  'planner.findBestRoute': { en: 'Find best route', hi: 'सर्वोत्तम मार्ग खोजें', te: 'ఉత్తమ మార్గం కనుగొను' },
  'planner.finding': { en: 'Finding the best route…', hi: 'सर्वोत्तम मार्ग खोजा जा रहा है…', te: 'ఉత్తమ మార్గం వెతుకుతోంది…' },
  'planner.chooseBoth': { en: 'Choose a start and a destination.', hi: 'प्रारंभ स्थान और गंतव्य चुनें।', te: 'ప్రారంభ స్థలం, గమ్యం ఎంచుకోండి.' },
  'planner.mustDiffer': { en: 'Start and destination must differ.', hi: 'प्रारंभ और गंतव्य अलग होने चाहिए।', te: 'ప్రారంభం, గమ్యం వేర్వేరుగా ఉండాలి.' },
  'planner.endTripFirst': { en: 'End the current trip to plan a new one.', hi: 'नई योजना के लिए पहले मौजूदा यात्रा समाप्त करें।', te: 'కొత్తది ప్లాన్ చేయడానికి ప్రస్తుత ప్రయాణాన్ని ముగించండి.' },

  /* ------------------------------------------------------------- the trip */
  'trip.yourTrip': { en: 'Your trip', hi: 'आपकी यात्रा', te: 'మీ ప్రయాణం' },
  'trip.recommended': { en: 'Recommended route', hi: 'अनुशंसित मार्ग', te: 'సిఫార్సు చేసిన మార్గం' },
  'trip.complete': { en: 'Trip complete', hi: 'यात्रा पूरी हुई', te: 'ప్రయాణం పూర్తయింది' },
  'trip.rerouted': { en: 'Rerouted', hi: 'मार्ग बदला', te: 'మార్గం మారింది' },
  'trip.eta': { en: 'ETA', hi: 'अनुमानित समय', te: 'అంచనా సమయం' },
  'trip.etaLeft': { en: 'ETA left', hi: 'शेष समय', te: 'మిగిలిన సమయం' },
  'trip.distance': { en: 'Distance', hi: 'दूरी', te: 'దూరం' },
  'trip.trafficNow': { en: 'Traffic now', hi: 'अभी ट्रैफ़िक', te: 'ఇప్పుడు ట్రాఫిక్' },
  'trip.predicted': { en: 'Predicted', hi: 'पूर्वानुमान', te: 'అంచనా' },
  'trip.timeSaved': { en: 'Time saved', hi: 'बचा समय', te: 'ఆదా అయిన సమయం' },
  'trip.measured': { en: 'measured on the road graph', hi: 'सड़क ग्राफ़ पर मापा गया', te: 'రహదారి గ్రాఫ్‌పై కొలిచినది' },
  'trip.onRoadAhead': { en: 'on the road ahead', hi: 'आगे की सड़क पर', te: 'ముందున్న రహదారిపై' },
  'trip.alongRoute': { en: 'along the route', hi: 'मार्ग भर में', te: 'మార్గం పొడవునా' },
  'trip.newRouteFromSwitch': { en: 'new route, from the switch', hi: 'नया मार्ग, बदलाव के बाद से', te: 'కొత్త మార్గం, మార్పు నుండి' },
  'trip.lstmForecast': { en: 'LSTM forecast', hi: 'LSTM पूर्वानुमान', te: 'LSTM అంచనా' },
  'trip.forecastUnavailable': { en: 'forecast unavailable', hi: 'पूर्वानुमान उपलब्ध नहीं', te: 'అంచనా అందుబాటులో లేదు' },
  'trip.reading': { en: 'reading…', hi: 'पढ़ा जा रहा है…', te: 'చదువుతోంది…' },
  'trip.startsWithNavigation': { en: 'starts with navigation', hi: 'नेविगेशन शुरू होने पर', te: 'నావిగేషన్ మొదలైనప్పుడు' },
  'trip.noSwitchYet': { en: 'no switch yet', hi: 'अभी कोई बदलाव नहीं', te: 'ఇంకా మార్పు లేదు' },
  'trip.vsStaying': { en: 'vs staying on the jammed road', hi: 'जाम वाली सड़क पर बने रहने की तुलना में', te: 'రద్దీ రోడ్డుపైనే ఉండటంతో పోలిస్తే' },
  'trip.startNavigation': { en: 'Start navigation', hi: 'नेविगेशन शुरू करें', te: 'నావిగేషన్ ప్రారంభించు' },
  'trip.pause': { en: 'Pause', hi: 'रोकें', te: 'ఆపు' },
  'trip.resume': { en: 'Resume', hi: 'जारी रखें', te: 'కొనసాగించు' },
  'trip.endTrip': { en: 'End trip', hi: 'यात्रा समाप्त करें', te: 'ప్రయాణం ముగించు' },
  'trip.viewInHistory': { en: 'View in history', hi: 'इतिहास में देखें', te: 'చరిత్రలో చూడండి' },
  'trip.planAnother': { en: 'Plan another trip', hi: 'दूसरी यात्रा की योजना', te: 'మరో ప్రయాణం ప్లాన్ చేయి' },
  'trip.note': {
    en: 'The car drives this route on the map at demo speed. The traffic agent watches the road ahead and tells you if a better one appears.',
    hi: 'गाड़ी इस मार्ग पर मानचित्र में डेमो गति से चलती है। ट्रैफ़िक एजेंट आगे की सड़क देखता रहता है और बेहतर मार्ग मिलने पर बताता है।',
    te: 'కారు ఈ మార్గంలో మ్యాప్‌పై డెమో వేగంతో నడుస్తుంది. ట్రాఫిక్ ఏజెంట్ ముందున్న రోడ్డును గమనిస్తూ మెరుగైన మార్గం ఉంటే చెబుతుంది.',
  },
  'trip.empty': {
    en: 'Plan a route and it appears here: ETA, distance, traffic now and predicted, and any time saved by switching on the way.',
    hi: 'मार्ग की योजना बनाइए और वह यहाँ दिखेगा: अनुमानित समय, दूरी, अभी और आगे का ट्रैफ़िक, तथा रास्ते में मार्ग बदलने से बचा समय।',
    te: 'మార్గాన్ని ప్లాన్ చేస్తే ఇక్కడ కనిపిస్తుంది: అంచనా సమయం, దూరం, ఇప్పటి మరియు ముందస్తు ట్రాఫిక్, దారిలో మార్గం మార్చడం వల్ల ఆదా అయిన సమయం.',
  },
  'trip.navigating': { en: 'Navigating', hi: 'नेविगेट हो रहा है', te: 'నావిగేట్ అవుతోంది' },
  'trip.paused': { en: 'Paused', hi: 'रुका हुआ', te: 'ఆపివేయబడింది' },
  'trip.waitingDecision': { en: 'Waiting for your decision', hi: 'आपके निर्णय की प्रतीक्षा', te: 'మీ నిర్ణయం కోసం ఎదురుచూస్తోంది' },
  'trip.left': { en: '{v} left', hi: '{v} शेष', te: '{v} మిగిలింది' },
  'trip.simulatedDrive': { en: 'Simulated drive', hi: 'अनुकरणीय ड्राइव', te: 'అనుకరణ డ్రైవ్' },
  'trip.speed': { en: '{n}× speed', hi: '{n}× गति', te: '{n}× వేగం' },
  'trip.whereTo': { en: 'Where to?', hi: 'कहाँ जाना है?', te: 'ఎక్కడికి?' },
  'trip.whereToHint': { en: 'Choose a start and a destination, then find the best route.', hi: 'प्रारंभ स्थान और गंतव्य चुनें, फिर सर्वोत्तम मार्ग खोजें।', te: 'ప్రారంభ స్థలం, గమ్యం ఎంచుకుని ఉత్తమ మార్గం కనుగొనండి.' },

  /* ------------------------------------------------------- recommendation */
  'recommend.title': { en: 'Faster route available', hi: 'तेज़ मार्ग उपलब्ध है', te: 'వేగవంతమైన మార్గం అందుబాటులో ఉంది' },
  'recommend.currentRoute': { en: 'Current route', hi: 'वर्तमान मार्ग', te: 'ప్రస్తుత మార్గం' },
  'recommend.alternative': { en: 'Alternative', hi: 'विकल्प', te: 'ప్రత్యామ్నాయం' },
  'recommend.youSave': { en: 'You save', hi: 'आप बचाएँगे', te: 'మీరు ఆదా చేస్తారు' },
  'recommend.switch': { en: 'Switch route', hi: 'मार्ग बदलें', te: 'మార్గం మార్చు' },
  'recommend.keep': { en: 'Keep current route', hi: 'वर्तमान मार्ग रखें', te: 'ప్రస్తుత మార్గమే ఉంచు' },
  'recommend.foot': {
    en: 'Found by the traffic agent on the road ahead; figures are measured on the road graph.',
    hi: 'आगे की सड़क पर ट्रैफ़िक एजेंट ने पाया; आँकड़े सड़क ग्राफ़ पर मापे गए हैं।',
    te: 'ముందున్న రోడ్డుపై ట్రాఫిక్ ఏజెంట్ కనుగొన్నది; అంకెలు రహదారి గ్రాఫ్‌పై కొలిచినవి.',
  },

  /* ----------------------------------------------------------- trip history */
  'history.title': { en: 'Trip History', hi: 'यात्रा इतिहास', te: 'ప్రయాణ చరిత్ర' },
  'history.subtitle': { en: 'Journeys you drove, and what switching route saved.', hi: 'आपकी की गई यात्राएँ और मार्ग बदलने से हुई बचत।', te: 'మీరు చేసిన ప్రయాణాలు, మార్గం మార్చడం వల్ల ఆదా అయినది.' },
  'history.search': { en: 'Search places…', hi: 'स्थान खोजें…', te: 'ప్రదేశాలను వెతకండి…' },
  'history.trips': { en: 'Trips', hi: 'यात्राएँ', te: 'ప్రయాణాలు' },
  'history.reroutedCount': { en: 'Rerouted', hi: 'मार्ग बदले', te: 'మార్గం మారినవి' },
  'history.from': { en: 'From', hi: 'से', te: 'నుండి' },
  'history.to': { en: 'To', hi: 'तक', te: 'వరకు' },
  'history.date': { en: 'Date', hi: 'दिनांक', te: 'తేదీ' },
  'history.route': { en: 'Route', hi: 'मार्ग', te: 'మార్గం' },
  'history.plannedEta': { en: 'Planned ETA', hi: 'नियोजित समय', te: 'ప్రణాళిక సమయం' },
  'history.trafficAtStart': { en: 'Traffic at start', hi: 'शुरू में ट्रैफ़िक', te: 'ప్రారంభంలో ట్రాఫిక్' },
  'history.vehicle': { en: 'Vehicle', hi: 'वाहन', te: 'వాహనం' },
  'history.wasRerouted': { en: 'Rerouted', hi: 'मार्ग बदला गया', te: 'మార్గం మార్చారా' },
  'history.yes': { en: 'Yes', hi: 'हाँ', te: 'అవును' },
  'history.no': { en: 'No', hi: 'नहीं', te: 'లేదు' },
  'history.switches': { en: '{n} switches', hi: '{n} बदलाव', te: '{n} మార్పులు' },
  'history.oneSwitch': { en: '1 switch', hi: '1 बदलाव', te: '1 మార్పు' },
  'history.kept': { en: '{n} kept', hi: '{n} बार वही रखा', te: '{n} సార్లు అలాగే ఉంచారు' },
  'history.originalEta': { en: 'Original ETA', hi: 'मूल अनुमानित समय', te: 'అసలు అంచనా సమయం' },
  'history.optimizedEta': { en: 'Optimized ETA', hi: 'अनुकूलित समय', te: 'మెరుగైన అంచనా సమయం' },
  'history.completed': { en: 'Completed', hi: 'पूर्ण', te: 'పూర్తయింది' },
  'history.inProgress': { en: 'In progress', hi: 'जारी है', te: 'జరుగుతోంది' },
  'history.endedEarly': { en: 'Ended early', hi: 'जल्दी समाप्त', te: 'ముందే ముగిసింది' },
  'history.routeOptimized': { en: 'Route optimized', hi: 'मार्ग अनुकूलित', te: 'మార్గం మెరుగుపరచబడింది' },
  'history.noTrips': { en: 'No trips yet', hi: 'अभी कोई यात्रा नहीं', te: 'ఇంకా ప్రయాణాలు లేవు' },
  'history.noMatching': { en: 'No matching trips', hi: 'कोई मेल खाती यात्रा नहीं', te: 'సరిపోలే ప్రయాణాలు లేవు' },
  'history.noMatchingHint': { en: 'Try a different place name.', hi: 'कोई दूसरा स्थान नाम आज़माएँ।', te: 'వేరే ప్రదేశం పేరు ప్రయత్నించండి.' },
  'history.goToDashboard': { en: 'Go to the dashboard', hi: 'डैशबोर्ड पर जाएँ', te: 'డాష్‌బోర్డ్‌కు వెళ్లండి' },

  /* ---------------------------------------------- objectives and vehicles
     Keyed by the id the backend uses. A vehicle the server adds later has no
     key here and keeps the server's own English label, which is a missing
     translation rather than a broken page. */
  'mode.balanced': { en: 'Balanced', hi: 'संतुलित', te: 'సమతుల్యం' },
  'mode.fastest': { en: 'Fastest', hi: 'सबसे तेज़', te: 'అత్యంత వేగం' },
  'mode.shortest': { en: 'Shortest', hi: 'सबसे छोटा', te: 'అత్యంత దగ్గర' },
  'mode.low_congestion': { en: 'Low Congestion', hi: 'कम भीड़', te: 'తక్కువ రద్దీ' },
  'vehicle.car': { en: 'Car', hi: 'कार', te: 'కారు' },
  'vehicle.two_wheeler': { en: 'Two-wheeler', hi: 'दोपहिया', te: 'ద్విచక్ర వాహనం' },
  'vehicle.auto_rickshaw': { en: 'Auto-rickshaw', hi: 'ऑटो रिक्शा', te: 'ఆటో రిక్షా' },
  'vehicle.bus': { en: 'Bus', hi: 'बस', te: 'బస్సు' },
  'vehicle.truck': { en: 'Truck', hi: 'ट्रक', te: 'ట్రక్కు' },
  'vehicle.bicycle': { en: 'Bicycle', hi: 'साइकिल', te: 'సైకిల్' },
  'vehicle.yours': { en: 'Your vehicle', hi: 'आपका वाहन', te: 'మీ వాహనం' },


  /* ----------------------------------------------------------- map controls */
  'map.recenter': { en: 'Recenter', hi: 'फिर से केंद्र में', te: 'మళ్లీ మధ్యలోకి' },
  'map.following': { en: 'Following', hi: 'साथ चल रहा है', te: 'అనుసరిస్తోంది' },

  /* ------------------------------------------------------------ map legend */
  'legend.congestion': { en: 'Traffic Congestion', hi: 'ट्रैफ़िक भीड़', te: 'ట్రాఫిక్ రద్దీ' },
  'legend.routePaths': { en: 'Route Paths', hi: 'मार्ग रेखाएँ', te: 'మార్గ రేఖలు' },
  'legend.recommended': { en: 'Recommended', hi: 'अनुशंसित', te: 'సిఫార్సు చేసినది' },
  'legend.alternative': { en: 'Alternative', hi: 'विकल्प', te: 'ప్రత్యామ్నాయం' },

  /* ------------------------------------------------------- traffic levels */
  'traffic.low': { en: 'Low', hi: 'कम', te: 'తక్కువ' },
  'traffic.moderate': { en: 'Moderate', hi: 'मध्यम', te: 'మధ్యస్థం' },
  'traffic.heavy': { en: 'Heavy', hi: 'अधिक', te: 'ఎక్కువ' },
  'traffic.severe': { en: 'Severe', hi: 'गंभीर', te: 'తీవ్రం' },

  /* --------------------------------------------------------------- sos */
  'sos.open': { en: 'Emergency', hi: 'आपातकाल', te: 'అత్యవసరం' },
  'sos.title': { en: 'Emergency help', hi: 'आपातकालीन सहायता', te: 'అత్యవసర సహాయం' },
  'sos.subtitle': {
    en: 'Tap a number to call. Your phone places the call.',
    hi: 'कॉल करने के लिए नंबर दबाएँ। कॉल आपका फ़ोन करेगा।',
    te: 'కాల్ చేయడానికి నంబర్‌ను నొక్కండి. కాల్ మీ ఫోన్ చేస్తుంది.',
  },
  'sos.all': { en: 'All emergencies', hi: 'सभी आपात स्थितियाँ', te: 'అన్ని అత్యవసరాలు' },
  'sos.police': { en: 'Police', hi: 'पुलिस', te: 'పోలీస్' },
  'sos.ambulance': { en: 'Ambulance', hi: 'एम्बुलेंस', te: 'అంబులెన్స్' },
  'sos.locating': { en: 'Finding your location…', hi: 'आपका स्थान पता किया जा रहा है…', te: 'మీ స్థానాన్ని కనుగొంటున్నాం…' },
  'sos.location': { en: 'Read this out to the operator', hi: 'यह ऑपरेटर को बताएँ', te: 'దీన్ని ఆపరేటర్‌కు చెప్పండి' },
  'sos.locationDenied': {
    en: 'Location is off, so it cannot be shown here.',
    hi: 'स्थान बंद है, इसलिए यहाँ नहीं दिखाया जा सकता।',
    te: 'స్థానం ఆఫ్‌లో ఉంది, కాబట్టి ఇక్కడ చూపలేము.',
  },
  'sos.copy': { en: 'Copy', hi: 'कॉपी करें', te: 'కాపీ చేయి' },
  'sos.copied': { en: 'Copied', hi: 'कॉपी हो गया', te: 'కాపీ అయింది' },
  'sos.close': { en: 'Close', hi: 'बंद करें', te: 'మూసివేయి' },

  /* ------------------------------------------------------------- units */
  'units.min': { en: '{n} min', hi: '{n} मिनट', te: '{n} నిమి' },
  'units.hourMin': { en: '{h} h {m} min', hi: '{h} घं {m} मि', te: '{h} గం {m} నిమి' },
  'units.km': { en: '{n} km', hi: '{n} किमी', te: '{n} కి.మీ' },
}
