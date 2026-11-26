// Vérification de Confie : chaque demande du propriétaire du projet, mot pour mot,
// est confrontée à l'application réelle. Lancer avec : npm run verif
//
// Règle : toute nouvelle demande s'ajoute à la liste EXIGENCES ci-dessous, avec ses mots
// exacts et un test qui prouve qu'elle est faite. Rien n'est « terminé » tant que ce script
// n'affiche pas tout en vert (ou en « partiel » avec la raison écrite noir sur blanc).

import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const read = (f) => fs.readFileSync(path.join(ROOT, f), "utf8");
const PORT = 3900 + Math.floor(Math.random() * 90);
const URL_ = `http://localhost:${PORT}/`;

const { SYSTEM_PROMPT, MODES, TONES, personalContext } = await import(path.join(ROOT, "prompt.js"));
const css = read("public/style.css");
const html = read("public/index.html");
const readme = read("README.md");

const need = (cond, msg) => { if (!cond) throw new Error(msg); };
const promptHas = (...words) => words.forEach((w) => need(SYSTEM_PROMPT.toLowerCase().includes(w.toLowerCase()), `les consignes de l'IA ne contiennent pas « ${w} »`));
class Partiel extends Error {}

const REPONSE = "Je t'entends, Léa.\n\n[[video: communication non violente couple]]";
const MODE_LABELS = ["Écoute-moi", "Aide-moi à comprendre", "Sois honnête", "Trouve des solutions", "Rassure-moi", "Challenge-moi"];

// Ouvre l'app sur un téléphone simulé, avec une fausse réponse d'IA, et note ce qui est envoyé.
async function session(browser, fn) {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const sent = [];
  await page.route("**/api/chat", (r) => {
    sent.push(JSON.parse(r.request().postData()));
    r.fulfill({ status: 200, contentType: "text/plain; charset=utf-8", body: REPONSE });
  });
  await page.goto(URL_);
  try { return await fn(page, sent); } finally { await page.close(); }
}
async function start(page, { name = "Léa", mode = "ecoute", tone = "gentil", memory = true } = {}) {
  await page.fill("#name-input", name);
  await page.check(`input[name=mode][value=${mode}]`, { force: true });
  await page.check(`input[name=tone][value=${tone}]`, { force: true });
  await page.setChecked("#memory-input", memory);
  await page.click("#welcome-form button[type=submit]");
}
async function say(page, text) {
  await page.fill("#input", text);
  await page.click("#send");
  await page.waitForSelector(".msg.ai:nth-of-type(n+3)");
}

// ——— La liste des demandes ———
// demande : les mots exacts du propriétaire.  test(browser) : lève une erreur si ce n'est pas fait.
const EXIGENCES = [
  { demande: "Psy ia / amour / amoureuse", test: () => promptHas("amour", "relations", "rupture", "couple") },
  { demande: "les gens seront plus à l'aise et pourront poser tout ce qu'il faut sans avoir honte", test: async (b) => {
      promptHas("Aucun sujet n'est honteux", "sans jugement");
      await session(b, async (p) => { await start(p); need((await p.innerText(".msg.ai")).includes("tu peux tout dire"), "l'accueil ne dit pas qu'on peut tout dire"); });
    } },
  { demande: "Peut mieux comprendre et écoute mieux / Écoute attentivement", test: () => promptHas("reformule", "une seule question à la fois", "Souviens-toi") },
  { demande: "Plus franc ou plus gentil", test: async (b) => {
      need(TONES.gentil && TONES.franc, "les deux tons n'existent pas dans les consignes");
      await session(b, async (p, sent) => {
        need(await p.isVisible("text=Plus gentil") && await p.isVisible("text=Plus franc"), "le choix « Plus gentil / Plus franc » n'est pas à l'écran");
        await start(p, { tone: "franc" }); await say(p, "bonjour");
        need(sent[0].tone === "franc", "le ton choisi n'est pas transmis à l'IA");
      });
    } },
  { demande: "Positif", test: () => promptHas("Reste positif", "espoir") },
  { demande: "Aide. Solution. Apporter des vraies solutions qui existent vraiment et qui marchent", test: () => promptHas("une chose concrète", "communication non violente", "Gottman", "attachement", "N'invente jamais") },
  { demande: "Répond", test: async () => {
      const { ready } = await (await fetch(URL_ + "api/status")).json();
      if (!ready && !/claude\.ai\/\S+/.test(readme)) throw new Partiel("l'IA ne répond pas encore : pas de clé API sur le serveur et pas de lien en ligne");
    } },
  { demande: "Écoute à n'importe quelle heure 24/24", test: () => {
      if (!/claude\.ai\/\S+|https:\/\/\S+\.(app|com|fr)\/?\s/.test(readme.replace(/console\.anthropic\.com|nodejs\.org/g, ""))) throw new Partiel("l'app n'est pas encore en ligne : aucun lien public dans le README");
    } },
  { demande: "Mémoire ou non", test: async (b) => {
      await session(b, async (p) => {
        await start(p, { memory: true }); await say(p, "je me souviens");
        await p.reload();
        need((await p.locator(".msg.user").count()) === 1, "avec la mémoire activée, la conversation n'est pas retrouvée au retour");
      });
      await session(b, async (p) => {
        await start(p, { memory: false }); await say(p, "secret");
        const stored = await p.evaluate(() => localStorage.getItem("confie.v1") || "");
        need(!stored.includes("secret") && !stored.includes("Léa"), "avec la mémoire désactivée, quelque chose est quand même gardé");
      });
    } },
  { demande: "Tisse un lien personnel", test: async (b) => {
      need(personalContext({ name: "Léa" }).includes("Léa"), "le prénom n'arrive pas dans les consignes de l'IA");
      await session(b, async (p, sent) => {
        await start(p); need((await p.innerText(".msg.ai")).includes("Léa"), "l'accueil n'utilise pas le prénom");
        await say(p, "bonjour"); need(sent[0].name === "Léa", "le prénom n'est pas transmis à l'IA");
        await p.reload(); need((await p.innerText(".msg.ai >> nth=-1")).includes("retrouver"), "au retour, la personne n'est pas reconnue");
      });
    } },
  { demande: "Confier", test: async (b) => session(b, async (p, sent) => {
      await start(p); need(await p.isVisible("#input"), "pas de zone pour écrire");
      await p.click("#starters button >> nth=0"); await p.waitForSelector(".msg.user");
      need(sent.length === 1, "les phrases pour démarrer n'envoient rien");
    }) },
  { demande: "Aider avec des vidéos YouTube", test: async (b) => {
      promptHas("[[video:");
      await session(b, async (p) => {
        await start(p); await say(p, "bonjour");
        const href = await p.getAttribute(".video", "href");
        need(href?.startsWith("https://www.youtube.com/results?search_query="), "pas de bouton YouTube dans la réponse");
        need(!(await p.innerText(".msg.ai >> nth=-1")).includes("[["), "la balise vidéo apparaît en clair");
      });
      throw new Partiel("le bouton ouvre une recherche YouTube, pas une vidéo précise (il faudrait une clé YouTube pour proposer de vraies vidéos vérifiées)");
    } },
  { demande: "Comment veux-tu que je t'aide aujourd'hui ? Écoute-moi / Aide-moi à comprendre / Sois honnête / Trouve des solutions / Rassure-moi / Challenge-moi", test: async (b) => {
      need(Object.keys(MODES).length === 6, "il n'y a pas six modes dans les consignes");
      await session(b, async (p, sent) => {
        need(await p.isVisible("text=Comment veux-tu que je t'aide aujourd'hui"), "la question n'est pas sur l'accueil");
        for (const l of MODE_LABELS) need(await p.isVisible(`#welcome >> text=${l}`), `« ${l} » manque sur l'accueil`);
        await start(p, { mode: "challenge" }); await say(p, "bonjour");
        need(sent[0].mode === "challenge", "le mode choisi n'est pas transmis à l'IA");
        await p.reload(); // « aujourd'hui » : reposée à chaque visite
        need(await p.isVisible("#modes"), "la question n'est pas reposée au retour");
        for (const l of MODE_LABELS) need(await p.isVisible(`#modes >> text=${l}`), `« ${l} » manque au retour`);
        await p.click("#modes >> text=Rassure-moi"); await say(p, "encore");
        need(sent[1].mode === "rassure", "changer de mode au retour n'a pas d'effet");
      });
    } },
  { demande: "Minimalist UI, calming aesthetic, soft sage green palette, warm cream background, gentle rounded corners, subtle shadows, elegant typography…", test: async (b) => {
      need(/--sage:\s*#8FA68E/i.test(css) && /--cream:\s*#F7F2E8/i.test(css), "la palette vert sauge / crème a changé");
      need(css.includes("Fraunces") && html.includes("Fraunces"), "la typographie élégante n'est pas chargée");
      need(/--radius:\s*2\dpx/.test(css) && css.includes("--shadow"), "coins arrondis ou ombres douces manquants");
      await session(b, async (p) => {
        const bg = await p.evaluate(() => getComputedStyle(document.body).backgroundColor);
        need(bg === "rgb(247, 242, 232)", `le fond n'est pas crème (${bg})`);
        for (const step of [null, () => start(p)]) {
          if (step) await step();
          need(await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth), "la page déborde sur le côté sur téléphone");
        }
      });
    } },
  { demande: "Envoie un lien de l'application", test: () => {
      if (!/https:\/\/claude\.ai\/\S+/.test(readme)) throw new Partiel("aucun lien vers l'application dans le README");
    } },
  { demande: "(ajout de sécurité, non demandé) Numéros d'urgence et rappel que ce n'est pas un psy", test: async (b) => {
      promptHas("3114", "3919", "pas un psychologue");
      await session(b, async (p) => { await start(p); await p.click("#help-btn"); need(await p.isVisible("#help >> text=3114"), "le 3114 n'est pas dans l'aide urgente"); });
    } },
];

// ——— Exécution ———
const hook = process.argv.includes("--hook");
if (hook) {
  // Appelé automatiquement à la fin de chaque réponse de Claude. Ne boucle pas sur lui-même.
  try { if (JSON.parse(fs.readFileSync(0, "utf8")).stop_hook_active) process.exit(0); } catch {}
}

let chromium;
try { ({ chromium } = createRequire(import.meta.url)("playwright")); } catch {
  console.error("Vérification impossible ici : le navigateur de test (Playwright) n'est pas installé.");
  process.exit(hook ? 0 : 1);
}

const env = { ...process.env, PORT: String(PORT) };
const server = spawn(process.execPath, ["server.js"], { cwd: ROOT, env, stdio: "ignore" });
for (let i = 0; i < 50; i++) { try { await fetch(URL_ + "api/status"); break; } catch { await new Promise((r) => setTimeout(r, 100)); } }

const browser = await chromium.launch();
const lines = [];
let ko = 0, partiel = 0;
for (const e of EXIGENCES) {
  try { await e.test(browser); lines.push(`✅ ${e.demande}`); }
  catch (err) {
    if (err instanceof Partiel) { partiel++; lines.push(`🟡 ${e.demande}\n     partiel : ${err.message}`); }
    else { ko++; lines.push(`❌ ${e.demande}\n     pas fait : ${String(err.message).split("\n")[0]}`); }
  }
}
await browser.close();
server.kill();

const out = `Vérification des demandes — ${EXIGENCES.length - ko - partiel} faites, ${partiel} partielles, ${ko} pas faites\n\n${lines.join("\n")}\n`;
if (ko && hook) { console.error(out + "\nCorrige les ❌ avant de dire que c'est terminé."); process.exit(2); }
console.log(out);
process.exit(ko ? 1 : 0);
