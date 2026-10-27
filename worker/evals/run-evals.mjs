// Lässt das Testset gegen den Hilfe-Chat laufen und prüft die Antworten
// automatisch auf Pflicht- und Verbotsbegriffe. Die vollständigen Antworten
// landen in evals/results-<Zeitstempel>.json zur manuellen Durchsicht –
// die Stichwortprüfung ist nur ein grober Filter, kein Urteil über Qualität.
//
// Aufruf (Worker lokal mit `npx wrangler dev` gestartet):
//   npm run eval
// Gegen den deployten Worker:
//   CHAT_URL=https://trivia-quiz-api.marcus-gisa1.workers.dev/chat npm run eval
//
// Jeder Lauf ruft Claude 25-mal auf (mit Haiku 4.5 grob 5–10 Cent).

import { readFile, writeFile } from "node:fs/promises";

const CHAT_URL = process.env.CHAT_URL || "http://127.0.0.1:8787/chat";
const cases = JSON.parse(await readFile(new URL("./testset.json", import.meta.url), "utf8"));

const lower = s => s.toLowerCase();

function check(testCase, reply) {
  const text = lower(reply);
  const missingAll =
    testCase.mustContainAny.length > 0 && !testCase.mustContainAny.some(w => text.includes(lower(w)));
  const forbidden = testCase.mustNotContain.filter(w => text.includes(lower(w)));
  const problems = [];
  if (missingAll) problems.push(`erwartet einen von: ${testCase.mustContainAny.join(" | ")}`);
  if (forbidden.length) problems.push(`verboten enthalten: ${forbidden.join(" | ")}`);
  return problems;
}

const results = [];
let passed = 0;

for (const testCase of cases) {
  let reply = "";
  let problems;
  try {
    const res = await fetch(CHAT_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: [{ role: "user", content: testCase.question }] }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${data.error}`);
    reply = data.reply;
    problems = check(testCase, reply);
  } catch (error) {
    problems = [`Fehler: ${error.message}`];
  }

  const ok = problems.length === 0;
  if (ok) passed += 1;
  results.push({ ...testCase, reply, ok, problems });
  console.log(`${ok ? "✅" : "❌"} [${testCase.category}] ${testCase.id}${ok ? "" : " – " + problems.join("; ")}`);
}

const stamp = new Date().toISOString().replace(/[:.]/g, "-");
const file = new URL(`./results-${stamp}.json`, import.meta.url);
await writeFile(file, JSON.stringify(results, null, 2));

console.log(`\n${passed}/${cases.length} bestanden. Alle Antworten: ${file.pathname}`);
