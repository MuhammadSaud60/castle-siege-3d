// Castle Siege 3D - leaderboard API (Phase 4)
// Tiny Express server: submit a score, fetch the top 10. No auth, but every
// submission is validated and rate limited. The store is PostgreSQL when
// DATABASE_URL is set and reachable, otherwise a local JSON file
// (server/data/scores.json). The JSON fallback keeps the API working if the
// free database is ever down or deleted; it is not durable across Render
// restarts on the free tier, the Postgres store is the durable one.

import express from 'express';
import cors from 'cors';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import pg from 'pg';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT || 3001);
const FILE_STORE = path.join(__dirname, 'data', 'scores.json');
const MAX_ROWS = 200;

const ALLOWED_ORIGINS = new Set(
  (process.env.CORS_ORIGINS ||
    'https://castle-siege-3d.onrender.com,http://localhost:5173,http://localhost:4173,http://127.0.0.1:5173,http://127.0.0.1:4173')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean),
);

const app = express();
app.disable('x-powered-by');
app.use((req, res, next) => {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  next();
});
app.use(
  cors({
    origin(origin, cb) {
      // Same-origin / curl / health checks send no Origin header.
      if (!origin || ALLOWED_ORIGINS.has(origin)) return cb(null, true);
      return cb(new Error('Origin not allowed'));
    },
  }),
);
app.use(express.json({ limit: '10kb' }));

// ---------------------------------------------------------------------------
// Score validation and sanitising
// ---------------------------------------------------------------------------
function cleanName(raw) {
  let name = String(raw ?? '').trim().replace(/[\u0000-\u001f\u007f]/g, '');
  name = name.replace(/[<>&"'`\\/]/g, '').replace(/\s+/g, ' ');
  if (name.length > 20) name = name.slice(0, 20).trim();
  return name || 'Anonymous';
}

function cleanInt(raw, max) {
  const n = Number(raw);
  if (!Number.isInteger(n) || n < 0 || n > max) return null;
  return n;
}

function validateScore(body) {
  if (!body || typeof body !== 'object') return { error: 'Score must be a JSON object' };
  const name = cleanName(body.name);
  const waves = cleanInt(body.waves, 100);
  const kills = cleanInt(body.kills, 100000);
  const gold = cleanInt(body.gold, 10000000);
  if (waves === null) return { error: 'waves must be an integer from 0 to 100' };
  if (kills === null) return { error: 'kills must be an integer from 0 to 100000' };
  if (gold === null) return { error: 'gold must be an integer from 0 to 10000000' };
  return { score: { name, waves, kills, gold } };
}

function compareScores(a, b) {
  if (b.waves !== a.waves) return b.waves - a.waves;
  if (b.kills !== a.kills) return b.kills - a.kills;
  if (b.gold !== a.gold) return b.gold - a.gold;
  return new Date(a.created_at) - new Date(b.created_at);
}

// ---------------------------------------------------------------------------
// Store: Postgres when available, JSON file fallback
// ---------------------------------------------------------------------------
let pgPool = null;
let storeKind = 'file';

async function initPostgres() {
  if (!process.env.DATABASE_URL) return false;
  try {
    pgPool = new pg.Pool({
      connectionString: process.env.DATABASE_URL,
      connectionTimeoutMillis: 5000,
      max: 3,
      ssl: { rejectUnauthorized: false },
    });
    await pgPool.query(
      'CREATE TABLE IF NOT EXISTS scores (' +
        'id SERIAL PRIMARY KEY, ' +
        'name TEXT NOT NULL, ' +
        'waves INTEGER NOT NULL, ' +
        'kills INTEGER NOT NULL, ' +
        'gold INTEGER NOT NULL, ' +
        'created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())',
    );
    storeKind = 'postgres';
    console.log('Leaderboard store: postgres');
    return true;
  } catch (err) {
    console.log('Postgres unavailable, using JSON file store:', err.message);
    try {
      await pgPool?.end().catch(() => {});
    } catch {}
    pgPool = null;
    return false;
  }
}

function readFileScores() {
  try {
    const raw = fs.readFileSync(FILE_STORE, 'utf8');
    const rows = JSON.parse(raw);
    return Array.isArray(rows) ? rows : [];
  } catch {
    return [];
  }
}

function writeFileScores(rows) {
  fs.mkdirSync(path.dirname(FILE_STORE), { recursive: true });
  fs.writeFileSync(FILE_STORE, JSON.stringify(rows, null, 2) + '\n', 'utf8');
}

async function getTopScores(limit) {
  if (pgPool) {
    const { rows } = await pgPool.query(
      'SELECT name, waves, kills, gold, created_at FROM scores ' +
        'ORDER BY waves DESC, kills DESC, gold DESC, created_at ASC LIMIT $1',
      [limit],
    );
    return rows;
  }
  return readFileScores().sort(compareScores).slice(0, limit);
}

async function addScore(score) {
  const row = { ...score, created_at: new Date().toISOString() };
  if (pgPool) {
    const { rows } = await pgPool.query(
      'INSERT INTO scores (name, waves, kills, gold, created_at) ' +
        'VALUES ($1, $2, $3, $4, $5) RETURNING name, waves, kills, gold, created_at',
      [row.name, row.waves, row.kills, row.gold, row.created_at],
    );
    // Keep the table small: drop everything outside the top 200.
    await pgPool.query(
      'DELETE FROM scores WHERE id NOT IN ' +
        '(SELECT id FROM scores ORDER BY waves DESC, kills DESC, gold DESC, created_at ASC LIMIT $1)',
      [MAX_ROWS],
    );
    const top = await getTopScores(MAX_ROWS);
    const rank = top.findIndex(
      (r) =>
        r.name === row.name &&
        r.waves === row.waves &&
        r.kills === row.kills &&
        r.gold === row.gold,
    );
    return { score: rows[0], rank: rank >= 0 ? rank + 1 : null };
  }
  const rows = readFileScores();
  const entry = { id: Date.now(), ...row };
  rows.push(entry);
  rows.sort(compareScores);
  const trimmed = rows.slice(0, MAX_ROWS);
  writeFileScores(trimmed);
  const rank = trimmed.indexOf(entry);
  return { score: row, rank: rank >= 0 ? rank + 1 : null };
}

// ---------------------------------------------------------------------------
// Rate limit: 10 score submissions per IP per minute
// ---------------------------------------------------------------------------
const submissions = new Map(); // ip -> [timestamps]

function rateLimited(ip) {
  const now = Date.now();
  const windowStart = now - 60_000;
  const times = (submissions.get(ip) || []).filter((t) => t > windowStart);
  if (times.length >= 10) return true;
  times.push(now);
  submissions.set(ip, times);
  return false;
}

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------
app.get('/health', (req, res) => {
  res.json({ ok: true, store: storeKind, time: new Date().toISOString() });
});

app.get('/', (req, res) => {
  res.type('text').send('Castle Siege 3D leaderboard API. GET /health, GET /api/scores, POST /api/scores.');
});

app.get('/api/scores', async (req, res) => {
  const limit = Math.min(Math.max(parseInt(req.query.limit, 10) || 10, 1), 50);
  try {
    const rows = await getTopScores(limit);
    res.json({
      scores: rows.map((r, i) => ({
        rank: i + 1,
        name: r.name,
        waves: r.waves,
        kills: r.kills,
        gold: r.gold,
        created_at: r.created_at,
      })),
    });
  } catch (err) {
    console.error('GET /api/scores failed:', err.message);
    res.status(500).json({ error: 'Could not load the leaderboard' });
  }
});

app.post('/api/scores', async (req, res) => {
  const ip = req.ip || req.socket?.remoteAddress || 'unknown';
  if (rateLimited(ip)) {
    return res.status(429).json({ error: 'Too many submissions, try again in a minute' });
  }
  const { score, error } = validateScore(req.body);
  if (error) return res.status(400).json({ error });
  try {
    const result = await addScore(score);
    res.status(201).json({ rank: result.rank, score: result.score });
  } catch (err) {
    console.error('POST /api/scores failed:', err.message);
    res.status(500).json({ error: 'Could not save the score' });
  }
});

app.use((err, req, res, next) => {
  if (err && err.message === 'Origin not allowed') {
    return res.status(403).json({ error: 'Origin not allowed' });
  }
  if (err && err.type === 'entity.parse.failed') {
    return res.status(400).json({ error: 'Body must be valid JSON' });
  }
  return next(err);
});

initPostgres().then(() => {
  app.listen(PORT, () => {
    console.log(`Castle Siege 3D leaderboard API listening on port ${PORT} (store: ${storeKind})`);
  });
});
