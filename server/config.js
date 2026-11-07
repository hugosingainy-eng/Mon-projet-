// Configuration centrale, lue depuis les variables d'environnement (.env).
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

// Mini-chargeur .env (évite une dépendance supplémentaire).
const envFile = path.join(root, '.env');
if (fs.existsSync(envFile)) {
  for (const line of fs.readFileSync(envFile, 'utf8').split('\n')) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (m && process.env[m[1]] === undefined) {
      process.env[m[1]] = m[2].replace(/^['"]|['"]$/g, '');
    }
  }
}

const env = process.env;

export const config = {
  root,
  port: Number(env.PORT || 3000),
  publicUrl: (env.PUBLIC_URL || `http://localhost:${env.PORT || 3000}`).replace(/\/$/, ''),
  dataDir: env.DATA_DIR || path.join(root, 'data'),

  // Accès privé (une seule personne : vous)
  adminPassword: env.ADMIN_PASSWORD || '',
  sessionSecret: env.SESSION_SECRET || 'changez-moi-' + Math.random().toString(36).slice(2),

  // IA (Claude)
  anthropicKey: env.ANTHROPIC_API_KEY || '',
  model: env.CLAUDE_MODEL || 'claude-opus-5-5',

  // Google
  googleMapsKey: env.GOOGLE_MAPS_API_KEY || '',
  pageSpeedKey: env.PAGESPEED_API_KEY || env.GOOGLE_MAPS_API_KEY || '',
  // Recherche Google « normale » (résultats web) via serper.dev
  serperKey: env.SERPER_API_KEY || '',

  // Email (SMTP)
  smtp: {
    host: env.SMTP_HOST || '',
    port: Number(env.SMTP_PORT || 587),
    secure: env.SMTP_SECURE === 'true',
    user: env.SMTP_USER || '',
    pass: env.SMTP_PASS || '',
    from: env.MAIL_FROM || env.SMTP_USER || '',
  },

  // Votre identité commerciale (utilisée dans les emails et la carte numérique)
  sender: {
    name: env.SENDER_NAME || 'Votre Nom',
    company: env.SENDER_COMPANY || 'Votre Agence Web',
    phone: env.SENDER_PHONE || '',
    email: env.SENDER_EMAIL || env.SMTP_USER || '',
    website: env.SENDER_WEBSITE || '',
    offer: env.SENDER_OFFER || 'Création de site vitrine professionnel, livré en 7 jours',
  },

  // Règles du Boss
  maxRevisions: Number(env.MAX_REVISIONS || 3),
  badSiteThreshold: Number(env.BAD_SITE_THRESHOLD || 55),
};

export const demoMode = {
  get google() { return !config.googleMapsKey; },
  get ai() { return !config.anthropicKey; },
};
