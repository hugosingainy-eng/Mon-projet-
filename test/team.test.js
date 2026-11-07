// Tests des sous-agents : délégation avec correction, priorité, analyse du prospect.
import { test } from 'node:test';
import assert from 'node:assert/strict';

process.env.ANTHROPIC_API_KEY = '';
process.env.DATA_DIR = process.env.DATA_DIR || '/tmp/agence-test-data';
const { delegate, activity } = await import('../server/team.js');
const { priorityScore } = await import('../server/agents/prospector.js');
const { analyzeProspect, accentFor } = await import('../server/agents/copywriter.js');

test('le chef renvoie le travail au sous-agent avec la correction', async () => {
  const seen = [];
  const result = await delegate({
    ctx: null, chef: 'Chef', helper: 'Aide', task: 'écris un mot de 5 lettres',
    run: async (fb) => { seen.push(fb); return fb ? 'bravo' : 'ok'; },
    check: (r) => (r.length === 5 ? null : 'il faut 5 lettres'),
  });
  assert.equal(result, 'bravo');
  assert.deepEqual(seen, ['', 'il faut 5 lettres']);
  assert.deepEqual(activity(), {}, "plus aucun sous-agent n'est marqué actif");
});

test('le Qualificateur met en tête les entreprises sans site et bien notées', () => {
  const hot = priorityScore({ website: '', rating: 4.8, reviews_count: 150, phone: '06', photos: [1, 2, 3] });
  const cold = priorityScore({ website: 'https://x.fr', rating: 3.9, reviews_count: 4, phone: '' });
  assert.equal(hot, 100);
  assert.ok(cold < 20);
});

test("l'Analyste prospect choisit un vrai avis positif", () => {
  const i = analyzeProspect({
    rating: 4.7, reviews_count: 80, segment: 'sans_site',
    raw: { reviews: [{ rating: 2, text: 'Bof, service lent et accueil froid ce jour-là.' }, { rating: 5, text: 'Le meilleur pain du quartier, toujours un sourire !' }] },
  });
  assert.equal(i.bestReview.rating, 5);
  assert.ok(i.facts.some((f) => f.includes('aucun site')));
});

test('le Designer carte adapte la couleur au métier', () => {
  assert.equal(accentFor('Plombier'), '#1f5f99');
  assert.equal(accentFor('Notaire'), '#b4532a');
});
