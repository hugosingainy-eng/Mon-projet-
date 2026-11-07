// Règles d'envoi automatique : plafond quotidien, horaires de bureau, compteur du jour.
// Envoyer trop d'emails d'un coup (ou la nuit) abîme la réputation de votre adresse :
// les emails finiraient en spam.
import { getSetting, setSetting } from './db.js';
import { smtpConfigured } from './services/mailer.js';

export const DEFAULTS = {
  send_limit: 30,          // emails automatiques max par jour
  send_start: 9,           // heure de Paris
  send_end: 18,
  send_weekdays_only: 'true',
  daily_report: 'true',
  report_hour: 8,
};

export function setting(key) {
  return getSetting(key, DEFAULTS[key] != null ? String(DEFAULTS[key]) : null);
}

/** Date et heure à Paris (le serveur peut être en UTC). */
export function parisNow(d = new Date()) {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-US', {
      timeZone: 'Europe/Paris', year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', weekday: 'short', hourCycle: 'h23',
    }).formatToParts(d).map((p) => [p.type, p.value])
  );
  return {
    ymd: `${parts.year}-${parts.month}-${parts.day}`,
    hour: Number(parts.hour),
    minute: Number(parts.minute),
    weekend: parts.weekday === 'Sat' || parts.weekday === 'Sun',
  };
}

export function sendsToday() {
  return getSetting('sends_day') === parisNow().ymd ? Number(getSetting('sends_count') || 0) : 0;
}

export function recordSend() {
  const today = parisNow().ymd;
  const n = getSetting('sends_day') === today ? Number(getSetting('sends_count') || 0) : 0;
  setSetting('sends_day', today);
  setSetting('sends_count', n + 1);
}

export function sendWindowOpen(now = parisNow()) {
  if (setting('send_weekdays_only') === 'true' && now.weekend) return false;
  return now.hour >= Number(setting('send_start')) && now.hour < Number(setting('send_end'));
}

/** Peut-on envoyer un email automatiquement maintenant ? */
export function canAutoSend() {
  if (getSetting('auto_send') !== 'true') return { ok: false, reason: 'envoi automatique désactivé' };
  if (!smtpConfigured()) return { ok: false, reason: 'SMTP non configuré' };
  if (!sendWindowOpen()) return { ok: false, reason: `hors horaires d'envoi (${setting('send_start')}h-${setting('send_end')}h${setting('send_weekdays_only') === 'true' ? ', en semaine' : ''})` };
  const limit = Number(setting('send_limit'));
  if (sendsToday() >= limit) return { ok: false, reason: `plafond du jour atteint (${limit} emails)` };
  return { ok: true, remaining: limit - sendsToday() };
}
