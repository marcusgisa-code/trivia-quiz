// Wissensbasis für den Hilfe-Chat. Jeder Abschnitt ist ein eigenständiger
// "Chunk", aus dem retrieve.js die passendsten Abschnitte zu einer Frage
// auswählt. Inhalte sind aus der Spiellogik in index.html und aus
// datenschutz.html / impressum.html abgeleitet – bei Regeländerungen hier
// mitpflegen.

export const KNOWLEDGE = [
  {
    id: "ueberblick",
    title: "Was ist Das Quiz und wie starte ich?",
    keywords: ["start", "starten", "falsch", "eingegeben", "tippfehler", "korrigieren", "anmelden", "anmeldung", "name", "postleitzahl", "plz", "spielen", "kostenlos", "app", "download", "installieren", "registrieren", "konto", "account", "login"],
    text:
      "Das Quiz ist ein kostenloses Wissensquiz, das direkt im Browser läuft – ohne Download, ohne Konto und ohne Passwort. " +
      "Zum Start gibst du einen frei wählbaren Namen (max. 12 Zeichen) und deine Postleitzahl ein, wählst einen Spielmodus und tippst auf „Spiel starten“. " +
      "Name und PLZ werden nur für die Highscore-Listen verwendet; eine Identitätsprüfung gibt es nicht. " +
      "Beide Angaben gibst du bei jedem Spielstart neu ein – einen Tippfehler korrigierst du also einfach beim nächsten Start. Bereits gespeicherte Highscore-Einträge lassen sich per E-Mail an findezwergle@icloud.com ändern oder löschen.",
  },
  {
    id: "modus-neu",
    title: "Spielmodus „Neues Spielprinzip“",
    keywords: ["neu", "neues", "spielprinzip", "aufdecken", "antwortoption", "tempo", "bonus", "multiplikator", "punkte", "wert", "abzug", "sekunden", "timer", "zeit", "schnell"],
    text:
      "Im Neuen Spielprinzip siehst du zuerst nur eine Antwortoption. Mit „Zeig mir die nächste Antwortoption“ deckst du weitere auf, insgesamt bis zu drei. " +
      "Je weniger Optionen du aufdeckst, desto mehr ist die Frage wert: Wert = Schwierigkeit (Leicht 1, Mittel 2, Schwer 3) × 10 × Multiplikator. " +
      "Der Multiplikator ist 3 bei einer sichtbaren Option, 2 bei zwei und 1 bei drei. Eine leichte Frage bringt also 30, 20 oder 10 Punkte, eine schwere 90, 60 oder 30. " +
      "Der Timer zählt hoch: In den ersten 10 Sekunden gibt es keinen Abzug, ab Sekunde 11 wird pro Sekunde 1 Punkt abgezogen. " +
      "Fällt der Wert dadurch unter 0, zählt die Frage als falsch. Eine falsche Antwort beendet das Spiel.",
  },
  {
    id: "modus-klassisch",
    title: "Spielmodus „Klassisch“",
    keywords: ["klassisch", "klassik", "serie", "folge", "countdown", "25", "sekunden", "zeit", "abgelaufen", "einzelspieler", "score", "solo", "punkte"],
    text:
      "Im Modus Klassisch werden alle drei Antwortoptionen gezeigt. Du hast pro Frage 25 Sekunden; läuft die Zeit ab, zählt das wie eine falsche Antwort. " +
      "Ziel ist eine möglichst lange Serie richtiger Antworten – eine falsche Antwort beendet das Spiel. Dein Ergebnis ist die Anzahl richtiger Antworten in Folge. " +
      "Zusätzlich gibt es im Klassisch-Modus (ohne KI-Fragen) einen Einzelspieler-Score: Pro richtiger Frage gibt es (Schwierigkeit × verbleibende Sekunden) / 2 Punkte, gerundet. " +
      "Schnell antworten lohnt sich also. Dafür gibt es eine eigene Highscore-Liste „Klassisch Einzelspieler Score“.",
  },
  {
    id: "modus-ki",
    title: "Spielmodus „Klassisch mit KI-Fragen“",
    keywords: ["ki", "ki-fragen", "künstliche", "intelligenz", "ai", "generiert", "klassisch"],
    text:
      "„Klassisch mit KI-Fragen“ funktioniert wie der Modus Klassisch (25 Sekunden pro Frage, ein Fehler beendet das Spiel, gleiche Joker), " +
      "verwendet aber neue, mit künstlicher Intelligenz erstellte Fragen. Der Modus hat eine eigene Highscore-Liste. Einen Einzelspieler-Score gibt es hier nicht.",
  },
  {
    id: "schwierigkeit",
    title: "Schwierigkeitsgrade und Reihenfolge der Fragen",
    keywords: ["schwierigkeit", "schwierigkeitsgrad", "leicht", "mittel", "schwer", "schwerer", "schwieriger", "länger", "steigt", "steigend", "einfacher", "level", "niveau", "reihenfolge", "steigend", "fragen", "wiederholung", "wiederholen", "gleich", "doppelt", "anzahl", "pool"],
    text:
      "Es gibt drei Schwierigkeitsgrade: Leicht, Mittel und Schwer. Eine Runde beginnt mit einer leichten Frage, danach folgen zwei mittlere und eine schwere; " +
      "anschließend wird der Schwierigkeitsgrad zufällig gewählt. Der Fragenpool umfasst rund 1.700 Fragen. " +
      "Pro Postleitzahl wird gespeichert, welche Fragen schon gespielt wurden, damit sich Fragen erst wiederholen, wenn alle einmal dran waren.",
  },
  {
    id: "joker",
    title: "Joker: Überspringen und 50:50",
    keywords: ["joker", "überspringen", "skip", "50:50", "fifty", "streichen", "antwort", "zusätzlich", "bonus", "bekommen", "verdienen", "mehr"],
    text:
      "Es gibt zwei Joker-Arten, von denen du zu Beginn jeweils 3 hast. " +
      "Der Joker „Frage überspringen“ ersetzt die aktuelle Frage durch eine neue. Der 50:50-Joker „Antwort streichen“ entfernt eine falsche Antwortoption; " +
      "im Neuen Spielprinzip steht er erst zur Verfügung, wenn alle drei Antwortoptionen aufgedeckt sind. " +
      "Nachschub: Alle 5 richtigen Antworten gibt es einen zusätzlichen Überspringen-Joker, und alle 3 richtig beantworteten schweren Fragen einen zusätzlichen 50:50-Joker.",
  },
  {
    id: "highscore",
    title: "Highscores und Bestenlisten",
    keywords: ["highscore", "bestenliste", "rangliste", "top", "platz", "liste", "ranking", "punkte", "gespeichert", "löschen", "ändern", "name"],
    text:
      "Über den Button „Highscore“ auf der Startseite siehst du die Top 10 – getrennt nach vier Listen: Neues Spielprinzip, Klassisch, Klassisch mit KI-Fragen und Klassisch Einzelspieler Score. " +
      "Angezeigt werden Name, Ort (aus der PLZ abgeleitet) und Punkte. " +
      "Möchtest du einen Eintrag ändern oder löschen lassen, schreib eine E-Mail an findezwergle@icloud.com.",
  },
  {
    id: "teilen-sound",
    title: "Ergebnis teilen und Ton",
    keywords: ["teilen", "share", "whatsapp", "facebook", "link", "kopieren", "freunde", "ton", "sound", "stumm", "leise", "mute", "lautstärke"],
    text:
      "Nach dem Spielende kannst du dein Ergebnis teilen – per WhatsApp, Facebook oder indem du den Link kopierst. " +
      "Die Soundeffekte schaltest du im Spiel über den Lautsprecher-Button oben ein oder aus.",
  },
  {
    id: "probleme",
    title: "Technische Probleme",
    keywords: ["problem", "fehler", "lädt", "laden", "geht", "funktioniert", "hängt", "bug", "langsam", "browser", "handy", "smartphone", "tablet", "neu", "internet"],
    text:
      "Werden keine Fragen geladen oder hängt das Spiel, lade die Seite neu und prüfe deine Internetverbindung. Das Quiz braucht eine aktive Verbindung, weil die Fragen online abgerufen werden. " +
      "Es läuft in aktuellen Browsern auf Smartphone, Tablet und Computer. " +
      "Besteht das Problem weiter, beschreib es bitte per E-Mail an findezwergle@icloud.com.",
  },
  {
    id: "datenschutz",
    title: "Datenschutz",
    keywords: ["datenschutz", "daten", "dsgvo", "privatsphäre", "gespeichert", "speichern", "firebase", "google", "cloudflare", "anthropic", "claude", "chat", "chatbot", "löschen", "auskunft"],
    text:
      "Gespeichert werden Name, PLZ, Ort, Punktestände, Anzahl Spiele, Zeitstempel und bereits gespielte Fragen-IDs (bei Google Firebase), damit die Highscores funktionieren. " +
      "Die Fragen kommen über einen Cloudflare Worker. Nachrichten an diesen Hilfe-Chat werden zur Beantwortung an Anthropic (Claude) übermittelt – bitte keine persönlichen Daten in den Chat schreiben. " +
      "Alle Details stehen in der Datenschutzerklärung (Link unten auf der Startseite). Für Auskunft oder Löschung: findezwergle@icloud.com.",
  },
  {
    id: "kontakt",
    title: "Kontakt und Impressum",
    keywords: ["kontakt", "impressum", "betreiber", "wer", "macht", "entwickler", "email", "e-mail", "mail", "feedback", "vorschlag", "frage", "einreichen", "fehler", "falsche", "antwort", "melden"],
    text:
      "Das Quiz wird von Marcus Gisa aus Leonberg betrieben (siehe Impressum, Link unten auf der Startseite). " +
      "Feedback, Fragenvorschläge oder Hinweise auf eine fehlerhafte Quizfrage bitte per E-Mail an findezwergle@icloud.com.",
  },
];
