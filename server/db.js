// Base de données SQLite (module natif node:sqlite, aucune dépendance native à compiler).
import { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import path from 'node:path';
import { config } from './config.js';

fs.mkdirSync(config.dataDir, { recursive: true });
export const db = new DatabaseSync(path.join(config.dataDir, 'agence.db'));

db.exec(`
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS missions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  query TEXT NOT NULL,
  city TEXT NOT NULL,
  max_results INTEGER NOT NULL DEFAULT 20,
  status TEXT NOT NULL DEFAULT 'en_attente',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  finished_at TEXT
);

CREATE TABLE IF NOT EXISTS leads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  mission_id INTEGER REFERENCES missions(id) ON DELETE CASCADE,
  place_id TEXT UNIQUE,
  name TEXT NOT NULL,
  category TEXT,
  address TEXT,
  phone TEXT,
  email TEXT,
  website TEXT,
  maps_url TEXT,
  rating REAL,
  reviews_count INTEGER,
  raw JSON,
  segment TEXT,              -- 'sans_site' | 'mauvais_site' | 'bon_site'
  audit JSON,
  audit_score INTEGER,
  site_slug TEXT,
  card_html TEXT,
  email_subject TEXT,
  email_body TEXT,
  status TEXT NOT NULL DEFAULT 'nouveau',
  boss_notes TEXT,
  sent_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS agent_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  mission_id INTEGER,
  lead_id INTEGER,
  from_agent TEXT NOT NULL,
  to_agent TEXT NOT NULL,
  kind TEXT NOT NULL,         -- 'livraison' | 'validation' | 'rejet' | 'info' | 'erreur'
  content TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT
);
`);

export function logMessage({ missionId = null, leadId = null, from, to, kind, content }) {
  db.prepare(
    `INSERT INTO agent_messages (mission_id, lead_id, from_agent, to_agent, kind, content)
     VALUES (?, ?, ?, ?, ?, ?)`
  ).run(missionId, leadId, from, to, kind, String(content));
}

export function updateLead(id, fields) {
  const keys = Object.keys(fields);
  if (!keys.length) return;
  const sets = keys.map((k) => `${k} = ?`).join(', ');
  const values = keys.map((k) => {
    const v = fields[k];
    return v !== null && typeof v === 'object' ? JSON.stringify(v) : v ?? null;
  });
  db.prepare(`UPDATE leads SET ${sets}, updated_at = datetime('now') WHERE id = ?`).run(...values, id);
}

export function getLead(id) {
  const lead = db.prepare('SELECT * FROM leads WHERE id = ?').get(id);
  if (!lead) return null;
  for (const k of ['raw', 'audit']) {
    if (lead[k]) {
      try { lead[k] = JSON.parse(lead[k]); } catch { /* garder la chaîne */ }
    }
  }
  return lead;
}

export function getSetting(key, fallback = null) {
  const row = db.prepare('SELECT value FROM settings WHERE key = ?').get(key);
  return row ? row.value : fallback;
}

export function setSetting(key, value) {
  db.prepare(
    'INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value'
  ).run(key, value == null ? null : String(value));
}
