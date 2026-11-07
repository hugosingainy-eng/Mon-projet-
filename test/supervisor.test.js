// Tests des contrôles automatiques du Boss (sans clé API : pas d'appel IA).
import { test } from 'node:test';
import assert from 'node:assert/strict';

process.env.ANTHROPIC_API_KEY = '';
process.env.DATA_DIR = process.env.DATA_DIR || '/tmp/agence-test-data';
const boss = await import('../server/agents/supervisor.js');
const { extractEmails } = await import('../server/services/siteAudit.js');

const lead = { name: 'Le Fournil de Marie', category: 'Boulangerie', phone: '06 10 45 67 80', address: '1 rue X, Lyon', segment: 'sans_site' };

test('le Boss écarte les établissements fermés et les franchises', () => {
  assert.equal(boss.reviewProspect({ name: 'A', phone: '1', business_status: 'CLOSED_PERMANENTLY', reviews_count: 10 }).approved, false);
  assert.equal(boss.reviewProspect({ name: 'McDonald\'s Lyon', phone: '1', reviews_count: 300 }).approved, false);
  assert.equal(boss.reviewProspect({ name: 'Boulangerie Paul', phone: '1', reviews_count: 2 }).approved, false);
  assert.equal(boss.reviewProspect({ name: 'Chez Léa', phone: '1', reviews_count: 40 }).approved, true);
});

test('le Boss refuse un email sans lien vers le site et renvoie un retour', async () => {
  const body = 'Bonjour, ' + 'je vous écris au sujet de Le Fournil de Marie. '.repeat(10);
  const v = await boss.reviewEmail(lead, { subject: 'Votre site', body }, 'http://x/sites/a/');
  assert.equal(v.approved, false);
  assert.match(v.feedback, /lien vers l'aperçu/);
});

test('le Boss refuse un site sans téléphone ni viewport', async () => {
  const html = `<html><head><title>Le Fournil de Marie</title></head><body>${'Le Fournil de Marie '.repeat(200)}</body></html>`;
  const v = await boss.reviewSite(lead, { html, photos: [] });
  assert.equal(v.approved, false);
  assert.match(v.feedback, /viewport/);
  assert.match(v.feedback, /téléphone/);
});

test('le Boss valide un email correct', async () => {
  const url = 'http://x/sites/a/';
  const body = `Bonjour,\n\nJ'ai découvert Le Fournil de Marie sur Google Maps. ${'Vos avis sont excellents et votre travail mérite un site. '.repeat(6)}\n\nAperçu : ${url}\n\nBien à vous`;
  const v = await boss.reviewEmail(lead, { subject: 'Un site pour Le Fournil de Marie', body }, url);
  assert.equal(v.approved, true, v.feedback);
});

test("extraction des emails d'un site", () => {
  const e = extractEmails('<a href="mailto:contact@boulangerie.fr">x</a> info@boulangerie.fr logo@2x.png');
  assert.deepEqual(e.sort(), ['contact@boulangerie.fr', 'info@boulangerie.fr']);
});
