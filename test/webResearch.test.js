// Tests de la recherche web : sites cachés et emails (Google simulé, aucune vraie requête).
import { test } from 'node:test';
import assert from 'node:assert/strict';

process.env.ANTHROPIC_API_KEY = '';
process.env.SERPER_API_KEY = 'test-key';
process.env.DATA_DIR = process.env.DATA_DIR || '/tmp/agence-test-data';
const web = await import('../server/services/webResearch.js');
const boss = await import('../server/agents/supervisor.js');

const lead = {
  name: 'Boulangerie Dupuis', category: 'Boulangerie', phone: '04 78 12 34 56',
  address: '12 rue Victor Hugo, 69002 Lyon', website: '',
};

test('trouve les emails, même masqués', () => {
  const found = web.findEmailsInText('Écrivez à contact [at] boulangerie-dupuis.fr ou <a href="mailto:Pain@Dupuis.fr">ici</a>, logo@2x.png');
  assert.deepEqual(found.sort(), ['contact@boulangerie-dupuis.fr', 'pain@dupuis.fr']);
});

test('écarte les emails des plateformes et les no-reply', () => {
  assert.equal(web.isPlatformEmail('contact@pagesjaunes.fr'), true);
  assert.equal(web.isPlatformEmail('noreply@boulangerie-dupuis.fr'), true);
  assert.equal(web.isPlatformEmail('contact@boulangerie-dupuis.fr'), false);
});

test('un email au nom de l’entreprise vu avec son téléphone est très fiable', () => {
  const strong = web.scoreEmail('contact@boulangerie-dupuis.fr', lead, { pageHasPhone: true, pageHasName: true });
  const weak = web.scoreEmail('jean.martin@gmail.com', lead, {});
  assert.ok(strong >= 60, `strong=${strong}`);
  assert.ok(weak < 35, `weak=${weak}`);
});

test('annuaires et réseaux sociaux ne comptent pas comme un site', () => {
  assert.equal(web.isDirectory('https://www.pagesjaunes.fr/pros/123'), true);
  assert.equal(web.isDirectory('https://www.facebook.com/dupuis'), true);
  assert.equal(web.isDirectory('https://www.boulangerie-dupuis.fr/'), false);
});

test('le domaine doit accepter les emails (MX)', async () => {
  assert.equal(await web.domainAcceptsMail('a@ok.fr', async () => [{ exchange: 'mx.ok.fr' }]), true);
  assert.equal(await web.domainAcceptsMail('a@ko.fr', async () => { throw new Error('ENOTFOUND'); }), false);
});

// ----- Google simulé -----
const PAGES = {
  'https://www.boulangerie-dupuis.fr/': '<h1>Boulangerie Dupuis</h1> 12 rue Victor Hugo Lyon — Tél. 04 78 12 34 56',
  'https://www.pagesjaunes.fr/pros/dupuis': 'Boulangerie Dupuis Lyon 04 78 12 34 56 contact@pagesjaunes.fr',
  'https://www.boulangerie-dupuis.fr/contact': 'Boulangerie Dupuis — écrivez-nous : bonjour (at) boulangerie-dupuis.fr — 04 78 12 34 56',
  'https://autre-boulangerie.fr/': 'Boulangerie Martin, Paris, 01 00 00 00 00 contact@autre-boulangerie.fr',
};
function mockFetch() {
  globalThis.fetch = async (url, opts = {}) => {
    if (String(url).includes('google.serper.dev')) {
      const q = JSON.parse(opts.body).q;
      const organic = q.includes('@') || q.includes('email')
        ? [{ title: 'Contact - Boulangerie Dupuis', link: 'https://www.boulangerie-dupuis.fr/contact', snippet: 'bonjour (at) boulangerie-dupuis.fr' },
           { title: 'Autre', link: 'https://autre-boulangerie.fr/', snippet: '' }]
        : [{ title: 'Boulangerie Dupuis - Pages Jaunes', link: 'https://www.pagesjaunes.fr/pros/dupuis', snippet: '' },
           { title: 'Boulangerie Dupuis Lyon', link: 'https://www.facebook.com/boulangeriedupuis', snippet: 'Boulangerie Dupuis à Lyon' },
           { title: 'Boulangerie Dupuis | Accueil', link: 'https://www.boulangerie-dupuis.fr/', snippet: '' },
           { title: 'Autre', link: 'https://autre-boulangerie.fr/', snippet: '' }];
      return new Response(JSON.stringify({ organic }), { status: 200 });
    }
    const html = PAGES[url];
    return html ? new Response(html, { status: 200 }) : new Response('not found', { status: 404 });
  };
}

test('Vérificateur de site : trouve le site caché, ignore annuaires et homonymes', async () => {
  mockFetch();
  const r = await web.findWebsite(lead);
  assert.equal(r.website, 'https://www.boulangerie-dupuis.fr/');
  assert.ok(r.score >= 70);
  assert.ok(r.social.some((u) => u.includes('facebook.com')));
  assert.equal(boss.reviewWebsiteCheck(lead, r).approved, true);
});

test('Détective email : trouve l’email sur Google et pas celui de l’annuaire', async () => {
  mockFetch();
  const r = await web.findEmail({ ...lead, website: 'https://www.boulangerie-dupuis.fr/' });
  assert.equal(r.email, 'bonjour@boulangerie-dupuis.fr');
  assert.ok(r.score >= 60, `score=${r.score}`);
  assert.ok(!r.alternatives.some((a) => a.email === 'contact@pagesjaunes.fr'));
});

test('le Boss refuse un email sans serveur mail ou peu fiable', () => {
  const v = boss.reviewContact(lead, { email: 'x@inconnu.fr', score: 20, mxOk: false, source: 'web' });
  assert.equal(v.approved, false);
  assert.match(v.feedback, /MX/);
  assert.match(v.feedback, /preuves/);
});

test('le Boss accepte honnêtement « aucun email trouvé »', () => {
  assert.equal(boss.reviewContact(lead, { email: null, log: [] }).approved, true);
});
