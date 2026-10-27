import { handleChat } from './chat.js';

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Content-Type': 'application/json; charset=utf-8',
};

// Der Hilfe-Chat kostet pro Anfrage Geld – deshalb nur von der eigenen Seite
// (und lokal zum Testen) zulassen. Anfragen ohne Origin-Header (z. B. das
// Testskript) sind erlaubt; ein echter Schutz ist das nicht, nur eine Hürde.
const CHAT_ORIGINS = [
  /^https:\/\/marcusgisa-code\.github\.io$/,
  /^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/,
];

function json(data, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: CORS_HEADERS });
}

export default {
  async fetch(request, env) {
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: CORS_HEADERS });
    }

    const url = new URL(request.url);

    if (url.pathname === '/chat') {
      if (request.method !== 'POST') return json({ error: 'Method not allowed' }, 405);
      const origin = request.headers.get('Origin');
      if (origin && !CHAT_ORIGINS.some(re => re.test(origin))) {
        return json({ error: 'Forbidden' }, 403);
      }
      return handleChat(request, env, json);
    }

    const all = url.searchParams.get('all') === '1';
    const count = all ? Infinity : Math.min(parseInt(url.searchParams.get('count') || '20'), 50);
    const level = url.searchParams.get('level'); // optional filter

    const raw = await env.QUESTIONS_KV.get('questions', 'json');
    if (!raw) {
      return new Response(JSON.stringify({ error: 'No questions found' }), {
        status: 500,
        headers: CORS_HEADERS,
      });
    }

    let pool = raw;
    if (level) {
      pool = pool.filter(q => String(q.level) === level);
    }

    if (all) {
      // Deterministic sort by ID for full-pool browsing
      pool.sort((a, b) => a.id - b.id);
    } else {
      // Fisher-Yates shuffle for random quiz batches
      for (let i = pool.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [pool[i], pool[j]] = [pool[j], pool[i]];
      }
    }

    const result = all ? pool : pool.slice(0, count);

    return new Response(JSON.stringify(result), { headers: CORS_HEADERS });
  },
};
