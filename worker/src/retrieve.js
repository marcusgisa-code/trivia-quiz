// Einfaches Retrieval (das "R" in RAG): Wählt aus der Wissensbasis die
// Abschnitte aus, die am besten zur Frage passen. Bewusst ohne Embeddings –
// lexikalischer Abgleich über Schlüsselwörter, Titel und Text reicht für
// eine kleine Hilfe-Wissensbasis und kostet nichts.

import { KNOWLEDGE } from "./knowledge.js";

const STOPWORDS = new Set([
  "der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem", "einer",
  "und", "oder", "aber", "ich", "du", "er", "sie", "es", "wir", "ihr", "man", "mein", "meine",
  "ist", "sind", "bin", "bist", "war", "wird", "werden", "kann", "kannst", "muss", "wie", "was",
  "wo", "wann", "warum", "wieso", "weshalb", "welche", "welcher", "welches", "mit", "von", "zu",
  "zum", "zur", "im", "in", "an", "auf", "für", "bei", "nach", "aus", "über", "nicht", "kein",
  "keine", "auch", "noch", "schon", "denn", "dann", "mal", "bitte", "hallo", "hi", "danke", "gibt",
  "es", "habe", "hab", "hat", "haben", "spiel", "spiele", "spielen", "quiz", "mir", "mich", "dir", "dich", "so", "da", "als", "wenn",
]);

function tokenize(text) {
  return text
    .toLowerCase()
    .replace(/[^a-zäöüß0-9:\s-]/g, " ")
    .split(/[\s-]+/)
    .filter(t => t.length > 1 && !STOPWORDS.has(t));
}

// Grobes Stemming: "joker" trifft "jokern", "highscores" trifft "highscore".
function matches(token, word) {
  if (token === word) return true;
  const min = Math.min(token.length, word.length);
  return min >= 4 && (token.startsWith(word) || word.startsWith(token));
}

function scoreChunk(tokens, chunk) {
  const keywordTokens = chunk.keywords.flatMap(tokenize);
  const titleTokens = tokenize(chunk.title);
  const textTokens = tokenize(chunk.text);
  let score = 0;
  for (const t of tokens) {
    if (keywordTokens.some(k => matches(t, k))) score += 3;
    if (titleTokens.some(k => matches(t, k))) score += 2;
    if (textTokens.some(k => matches(t, k))) score += 1;
  }
  return score;
}

/**
 * Liefert die k relevantesten Abschnitte. "ueberblick" wird immer
 * mitgeschickt, damit der Bot den Grundkontext des Spiels kennt.
 */
export function retrieve(query, k = 3) {
  const tokens = tokenize(query);
  const ranked = KNOWLEDGE
    .map(chunk => ({ chunk, score: scoreChunk(tokens, chunk) }))
    .filter(r => r.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, k)
    .map(r => r.chunk);

  if (!ranked.some(c => c.id === "ueberblick")) {
    ranked.push(KNOWLEDGE.find(c => c.id === "ueberblick"));
  }
  return ranked;
}
