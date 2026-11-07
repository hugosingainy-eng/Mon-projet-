// Tests du pilote automatique : heure de Paris, horaires d'envoi, plafond, découpage des listes.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

process.env.ANTHROPIC_API_KEY = '';
process.env.DATA_DIR = fs.mkdtempSync(path.join(os.tmpdir(), 'agence-autopilot-'));
const { parisNow, sendWindowOpen, canAutoSend, recordSend, sendsToday } = await import('../server/sendPolicy.js');
const { setSetting } = await import('../server/db.js');
const { parseList, createAutopilot, getAutopilot } = await import('../server/autopilot.js');

test("l'heure de Paris tient compte de l'heure d'été et d'hiver", () => {
  assert.equal(parisNow(new Date('2026-07-01T10:00:00Z')).hour, 12); // été : UTC+2
  assert.equal(parisNow(new Date('2026-12-01T10:00:00Z')).hour, 11); // hiver : UTC+1
  assert.equal(parisNow(new Date('2026-12-05T10:00:00Z')).weekend, true); // samedi
});

test("pas d'envoi la nuit ni le week-end", () => {
  setSetting('send_start', 9); setSetting('send_end', 18); setSetting('send_weekdays_only', 'true');
  assert.equal(sendWindowOpen({ hour: 10, weekend: false }), true);
  assert.equal(sendWindowOpen({ hour: 3, weekend: false }), false);
  assert.equal(sendWindowOpen({ hour: 10, weekend: true }), false);
  setSetting('send_weekdays_only', 'false');
  assert.equal(sendWindowOpen({ hour: 10, weekend: true }), true);
});

test('le plafond quotidien bloque les envois automatiques', () => {
  setSetting('auto_send', 'false');
  assert.match(canAutoSend().reason, /désactivé/);
  setSetting('send_limit', 2);
  recordSend(); recordSend();
  assert.equal(sendsToday(), 2);
});

test('les listes de métiers et de villes sont nettoyées', () => {
  assert.deepEqual(parseList('boulangerie, plombier;\n coiffeur,, plombier'), ['boulangerie', 'plombier', 'coiffeur']);
});

test('un programme démarre tout de suite et borne ses réglages', () => {
  const id = createAutopilot({ queries: ['plombier'], cities: ['Lyon'], intervalMinutes: 1, resultsPerRun: 500, dailyLimit: 0 });
  const a = getAutopilot(id);
  assert.equal(a.interval_minutes, 5);
  assert.equal(a.results_per_run, 60);
  assert.equal(a.daily_limit, 1);
  assert.ok(new Date(a.next_run_at) <= new Date());
  assert.throws(() => createAutopilot({ queries: [], cities: ['Lyon'] }), /au moins un métier/);
});

test('après la limite du jour, reprise juste après minuit (heure de Paris)', async () => {
  const { nextParisMidnight } = await import('../server/autopilot.js');
  const next = new Date(nextParisMidnight(new Date('2026-12-01T21:30:00Z'))); // 22h30 à Paris
  assert.equal(parisNow(next).hour, 0);
  assert.equal(parisNow(next).ymd, '2026-12-02');
});
