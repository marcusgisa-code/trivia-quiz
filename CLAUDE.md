# CLAUDE.md — Trivia Quiz Projekt

## Projektübersicht

Web-basiertes Trivia-Quiz, gebaut mit Vanilla HTML/CSS/JS (Single-File-Architektur).

- **Live-URL:** https://marcusgisa-code.github.io/trivia-quiz/
- **Repo:** GitHub — marcusgisa-code/trivia-quiz
- **Hosting:** GitHub Pages (main branch → root)

---

## Architektur

### Dateien

```
/Quiz
├── index.html          ← Einzige Quelldatei — alle UI, CSS und JS hier
├── worker/
│   ├── src/index.js    ← Cloudflare Worker (Fragen-API + Routing)
│   ├── src/chat.js     ← Route /chat: Hilfe-Chat via Claude (Haiku 4.5)
│   ├── src/knowledge.js← Wissensbasis des Hilfe-Chats (bei Regeländerungen mitpflegen!)
│   ├── src/retrieve.js ← Auswahl passender Wissens-Abschnitte (einfaches RAG)
│   ├── evals/          ← Testset (25 Fragen) + run-evals.mjs
│   ├── package.json    ← Abhängigkeit @anthropic-ai/sdk
│   └── wrangler.toml   ← KV namespace id: 7c3d06bdc2eb447ba5c66099ff3c3916
├── Fragenpool/         ← Lokale CSV-Sicherung (nicht öffentlich ausgeliefert)
├── Versionen/          ← Ältere Snapshots
└── mockups/            ← Design-Referenzfiles
```

### Fragen-Backend

- **Cloudflare Worker** unter `marcus-gisa1.workers.dev`
- Fragen liegen in **Cloudflare KV** (`QUESTIONS_KV`) — 1736 Fragen
- Worker gibt zufällige Batches zurück (Fisher-Yates), max. 50 pro Request
- Schützt den vollständigen Fragenpool vor Bulk-Download
- CSV-Format: `ID;Frage;AO1;AO2;AO3;AOCorrect;Level` (Semikolon-getrennt)
- Level: 1 = Leicht, 2 = Mittel, 3 = Schwer

### Hilfe-Chat (KI)

- Button „Hilfe“ unten rechts, Chat-Panel als drittes `<script>` am Ende von `index.html`
- Sichtbar auf Startseite, Highscore und nach Game Over – **nicht** während einer laufenden Frage und nicht im Edit Mode (MutationObserver auf `screen-quiz`, `screen-edit`, `game-over-card`)
- Browser schickt den Verlauf (max. 10 Nachrichten) an `POST /chat`; der Worker wählt passende Abschnitte aus `knowledge.js` und ruft Claude (`claude-haiku-4-5`, max. 400 Tokens) auf
- Guardrails im Systemprompt (`chat.js`): nur auf Basis der Hilfetexte antworten, keine Quiz-Lösungen, kein Off-Topic, keine persönlichen Daten, Prompt-Injection ignorieren
- API-Schlüssel als Worker-Secret `ANTHROPIC_API_KEY` (nie im Code); lokal in `worker/.dev.vars` (gitignored)
- Schutz vor Kosten: Origin-Prüfung, 20 Nachrichten/Stunde pro IP (best effort, pro Worker-Instanz) und Ausgabenlimit in der Anthropic-Konsole
- Lokal testen: `index.html?chat=local` schickt den Chat an `wrangler dev` (Port 8787)

### Score-Speicherung

- **Firebase Firestore** (SDK v11.6.0 via CDN)
- Collection: `scores`
- Felder: `username`, `score`, `ort`, `timestamp`
- `window.saveScore(username, score, ort)` — im Firebase `<script type="module">` gesetzt
- `window.loadHighscores()` — Top 10, nach Score absteigend

---

## Wichtige Implementierungsdetails

### Script-Struktur in index.html

Zwei Script-Blöcke:
1. `<script type="module">` — Firebase-Import + `window.saveScore` / `window.loadHighscores`
2. `<script>` (classic) — gesamte Quiz-Logik

Da das Module-Script deferred läuft, sind `window.saveScore` / `window.loadHighscores` erst zur Laufzeit verfügbar — nicht beim initialen Parsen.

### Screens

- `screen-welcome` — Anmeldung (Name + Ort, beide required)
- `screen-quiz` — Spielscreen mit Topbar + Fragen
- `screen-highscore` — Top 10 aus Firestore

### Topbar (Quiz-Screen)

Basiert auf Mockup Variant C:
- Links: `.tb-player` Pill — Avatar-Kreis (erster Buchstabe Username) + Name + Punkte
- Mitte: `.tb-chips` — drei Chips: Frage-Nr., Niveau (gold), Wert (gold)
- Rechts: `.tb-timer` — Kreis mit Sekunden-Countdown + "Sek" Label

### Spiellogik

- `startGame()` — async, lädt Fragen selbst wenn `state.questions` leer
- `loadQuestionsFromAPI()` — stiller Prefetch beim Welcome-Screen-Load, blockiert Start-Button nicht
- Timer läuft pro Frage; bei Ablauf: falsche Antwort
- Game Over: ein falsches Antwort = Ende (kein Leben-System)

---

## Bekannte Fallstricke

- **Curly Quotes in HTML-Attributen** zerstören `getElementById` (Safari wirft `null is not an object`). Immer ASCII-Anführungszeichen `"` verwenden, nie `"` / `"`.
- **wrangler.toml** darf nicht in git committed werden wenn sensible IDs drin sind — KV-Namespace-ID ist aber public unkritisch.
- `worker/.wrangler/` und `worker/node_modules/` sind in `.gitignore`.

---

## Deploy

### GitHub Pages

```bash
git add index.html
git commit -m "..."
git push
```

### Cloudflare Worker

```bash
cd worker
npm install            # einmalig bzw. nach Änderungen an package.json
npx wrangler deploy
```

### Hilfe-Chat einrichten / testen

```bash
cd worker
npx wrangler secret put ANTHROPIC_API_KEY   # Schlüssel aus console.anthropic.com einfügen

# Lokal: worker/.dev.vars anlegen mit
#   ANTHROPIC_API_KEY=sk-ant-...
#   CHAT_RATE_LIMIT=100
npx wrangler dev                            # danach index.html?chat=local öffnen
npm run eval                                # Testset gegen den lokalen Worker (≈ 5–10 Cent)
CHAT_URL=https://trivia-quiz-api.marcus-gisa1.workers.dev/chat npm run eval   # gegen live
```

### Fragen-Upload zu KV

```bash
cd worker
npx wrangler kv key put --namespace-id=7c3d06bdc2eb447ba5c66099ff3c3916 "questions" --path=../Fragenpool/fragen.json
```

---

## Arbeitsregeln

- **Einzige Quelldatei:** `index.html` — keine separate JS/CSS-Datei anlegen
- **Bestehende Funktionalität erhalten** bei jeder Änderung
- **Fertigen Code zurückgeben** — kein Pseudo-Code, keine Platzhalter
- Änderungen direkt pushen nach Absprache
