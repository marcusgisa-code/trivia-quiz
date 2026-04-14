const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Content-Type': 'application/json; charset=utf-8',
};

export default {
  async fetch(request, env) {
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: CORS_HEADERS });
    }

    const url = new URL(request.url);
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
