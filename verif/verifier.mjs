// Vérification de Confie : chaque demande du propriétaire du projet est confrontée à
// l'application réelle, sur un téléphone simulé. Lancer avec : npm run verif
//
// Règle : toute nouvelle demande s'ajoute à la liste EXIGENCES, avec ses mots et un test qui
// prouve qu'elle est faite. Trois résultats possibles, jamais maquillés :
//   ✅ fait et vérifié   🟡 partiel (la raison est écrite)   ❌ pas fait

import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const read = (f) => fs.readFileSync(path.join(ROOT, f), "utf8");
const exists = (f) => fs.existsSync(path.join(ROOT, f));
const PORT = 3900 + Math.floor(Math.random() * 90);
const BASE = `http://localhost:${PORT}`;

const hook = process.argv.includes("--hook");
if (hook) {
  // Appelé automatiquement à la fin de chaque réponse de Claude. Ne boucle pas sur lui-même.
  try { if (JSON.parse(fs.readFileSync(0, "utf8")).stop_hook_active) process.exit(0); } catch {}
}

const { SYSTEM_PROMPT, MODES, STYLES } = await import(path.join(ROOT, "prompt.js"));
const theme = read("mobile/src/theme/index.ts");
const sql = read("supabase/migrations/0001_init.sql");
const readme = read("README.md");

const need = (cond, msg) => { if (!cond) throw new Error(msg); };
const promptHas = (...words) => words.forEach((w) => need(SYSTEM_PROMPT.toLowerCase().includes(w.toLowerCase()), `les consignes de l'IA ne contiennent pas « ${w} »`));
class Partiel extends Error {}
// Attend qu'un élément soit réellement à l'écran (les écrans apparaissent en fondu).
const see = async (loc, msg) => { try { await loc.first().waitFor({ state: "visible", timeout: 5000 }); } catch { throw new Error(msg); } };

const REPLY = "Je t'entends, Léa. Ça fait beaucoup à porter.\n\nQu'est-ce qui pèse le plus ce soir ?\n\n[[retenir: Léa prépare un concours en juin]]\n[[exercice: coherence]]\n[[video: gérer le stress avant un examen psychologue]]";
const MODE_LABELS = ["Écoute-moi", "Aide-moi à comprendre", "Sois honnête", "Rassure-moi", "Trouve des solutions", "Challenge-moi", "Motive-moi"];
const TOPIC_LABELS = ["Amour et relations", "Moral et émotions", "Stress et anxiété", "Confiance en soi", "Motivation", "Solitude", "Autre sujet"];

const persisted = (state) => JSON.stringify({ state, version: 1 });
const SETTINGS = { onboarded: true, consentAt: 1, name: "Léa", topics: [], style: "douce", frankness: 2, defaultMode: "ecoute", memory: "on", prefersVoice: false, notifications: false, appearance: "light", voiceId: null, voiceRate: 1, showTranscript: true, shareJournalWithAi: false };

/** Ouvre l'app. `settings` = personne déjà inscrite (null = première visite). */
async function open(browser, { settings = SETTINGS, reply = REPLY, width = 390, height = 844, offline = false, route = "/" } = {}) {
  const ctx = await browser.newContext({ viewport: { width, height }, locale: "fr-FR" });
  const page = await ctx.newPage();
  const sent = [];
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  if (settings) await page.addInitScript((v) => { if (!localStorage.getItem("confie.settings")) localStorage.setItem("confie.settings", v); }, persisted(settings));
  await page.route("**/api/chat", async (r) => {
    sent.push(JSON.parse(r.request().postData()));
    if (offline) return r.abort("internetdisconnected");
    await new Promise((x) => setTimeout(x, 150));
    r.fulfill({ status: 200, contentType: "text/plain; charset=utf-8", body: typeof reply === "function" ? reply(sent.length) : reply });
  });
  await page.goto(BASE + route);
  await page.waitForSelector(settings ? "[data-testid=home]" : "[data-testid=welcome]", { timeout: 20000 }).catch(() => {});
  return { page, sent, errors, close: () => ctx.close() };
}
const tid = (page, id) => page.locator(`[data-testid="${id}"]`);
const startChat = async (page) => { await tid(page, "start-chat").click(); await tid(page, "chat").waitFor(); };
const say = async (page, text) => {
  const before = await tid(page, "ai-message").count();
  await tid(page, "composer").fill(text);
  await tid(page, "send").click();
  await page.waitForFunction((n) => document.querySelectorAll('[data-testid="ai-message"]').length > n, before, { timeout: 10000 });
};
const tab = (page, name) => page.getByRole("tab", { name }).click();
const noOverflow = async (page, where) => need(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${where} déborde sur le côté`);
const stored = (page, key) => page.evaluate((k) => JSON.parse(localStorage.getItem(k) || "{}").state ?? {}, key);
const session = async (browser, opts, fn) => { const s = await open(browser, opts); try { return await fn(s); } finally { await s.close(); } };

// ——— La liste des demandes ———
const EXIGENCES = [
  // Message 1 — l'idée de départ
  { demande: "Psy IA", test: () => promptHas("espace d'écoute", "Tu es une IA") },
  { demande: "Ce ne sera pas un psychologue amour : un psychologue pour tous, avec des cases pour que le client ait le choix de parler d'amour ou d'autres sujets", test: (b) => session(b, {}, async ({ page, sent }) => {
      for (const l of TOPIC_LABELS) await see(page.getByText(l, { exact: true }), `la case « ${l} » manque sur l'accueil`);
      await page.getByText("Amour et relations", { exact: true }).click();
      await tid(page, "chat").waitFor();
      await say(page, "bonjour");
      need(sent[0].context.topic === "amour", "le sujet choisi n'est pas transmis à l'IA");
      promptHas("solitude", "anxiété", "confiance");
    }) },
  { demande: "Les gens seront plus à l'aise et pourront poser tout ce qu'il faut sans avoir honte", test: (b) => session(b, { settings: null }, async ({ page }) => {
      promptHas("Aucun sujet n'est honteux");
      await see(page.getByText(/Tu peux tout dire/), "la promesse « Tu peux tout dire » n'est pas sur l'écran de bienvenue");
    }) },
  { demande: "Peut mieux comprendre et écoute mieux / Écoute attentivement", test: () => promptHas("reformuler", "Une seule question à la fois", "avec ses mots") },
  { demande: "Plus franc ou plus gentil", test: (b) => session(b, {}, async ({ page, sent }) => {
      need(STYLES.douce && STYLES.franche, "styles doux et franc absents des consignes");
      await tab(page, "Profil");
      await tid(page, "profile").getByText("Style", { exact: true }).click();
      await see(page.getByText("Franche et directe"), "le choix « Franche et directe » n'est pas dans le profil");
      await see(page.getByText("Douce et bienveillante"), "le choix « Douce et bienveillante » n'est pas dans le profil");
      await page.getByText("Franche et directe").last().click();
      await page.waitForFunction(() => JSON.parse(localStorage.getItem("confie.settings")).state.style === "franche");
      await tab(page, "Accueil"); await startChat(page); await say(page, "bonjour");
      need(sent[0].context.style === "franche", "le style choisi n'est pas transmis à l'IA");
      need([1, 2, 3].includes(sent[0].context.frankness), "le niveau de franchise n'est pas transmis");
    }) },
  { demande: "Positif", test: () => { promptHas("Reste positif"); need(STYLES.positive, "style positif absent"); } },
  { demande: "Aide. Solution. Apporter des vraies solutions qui existent vraiment et qui marchent", test: () => promptHas("approches reconnues", "communication non violente", "Gottman", "N'invente jamais", "Ne promets jamais") },
  { demande: "Répond", test: async (b) => {
      await session(b, {}, async ({ page }) => { await startChat(page); await say(page, "bonjour"); await see(tid(page, "chat").getByText(/Je t'entends/), "la réponse ne s'affiche pas"); });
      const { ready } = await (await fetch(BASE + "/api/status")).json();
      if (!ready) throw new Partiel("l'IA répond dans l'aperçu en ligne (lien du README, non vérifié depuis la page publiée) ; sur le serveur, il faut encore une clé API Anthropic");
    } },
  { demande: "Écoute à n'importe quelle heure 24/24", test: () => { throw new Partiel("l'app n'est pas encore hébergée en ligne : il faut un hébergeur pour le serveur"); } },
  { demande: "Mémoire ou non", test: async (b) => {
      await session(b, {}, async ({ page, sent }) => {
        await startChat(page); await say(page, "je révise");
        need(Array.isArray(sent[0].context.memory), "mémoire activée : la liste n'est pas transmise");
        await see(page.getByText(/Retenu : Léa prépare un concours/), "le souvenir retenu n'est pas signalé");
        await page.goto(BASE + "/memoire"); await tid(page, "memory").waitFor();
        await see(page.getByText("Léa prépare un concours en juin"), "le souvenir n'apparaît pas dans « Ce que mon IA retient »");
      });
      await session(b, { settings: { ...SETTINGS, memory: "off" } }, async ({ page, sent }) => {
        await startChat(page); await say(page, "secret");
        need(sent[0].context.memory === null, "mémoire désactivée : des souvenirs partent quand même");
        need(((await stored(page, "confie.memory")).items ?? []).length === 0, "mémoire désactivée : un souvenir a été enregistré");
      });
    } },
  { demande: "Tisse un lien personnel", test: (b) => session(b, {}, async ({ page, sent }) => {
      await see(page.getByText(/Léa/).first(), "l'accueil n'utilise pas le prénom");
      await startChat(page); await say(page, "bonjour"); need(sent[0].context.name === "Léa", "le prénom n'est pas transmis à l'IA");
      await page.goto(BASE + "/"); await tid(page, "home").waitFor();
      await see(page.getByText(/Reprendre : bonjour/), "au retour, la conversation précédente n'est pas proposée");
    }) },
  { demande: "Confier", test: (b) => session(b, {}, async ({ page, sent }) => {
      await startChat(page);
      await page.getByText("J'ai besoin de vider mon sac").click();
      await tid(page, "ai-message").first().waitFor();
      need(sent[0].messages.at(-1).content.includes("vider mon sac"), "les phrases pour démarrer n'envoient rien");
    }) },
  { demande: "Aider avec des vidéos YouTube (vérifier qu'elles existent, ne pas en inventer)", test: async (b) => {
      promptHas("[[video:", "jamais un lien ni un titre");
      await session(b, {}, async ({ page }) => {
        await startChat(page); await say(page, "bonjour");
        await see(page.getByText("gérer le stress avant un examen psychologue"), "aucune proposition de vidéo dans la réponse");
        need(!(await tid(page, "chat").innerText()).includes("[["), "une balise apparaît en clair");
        await page.goto(BASE + "/videos"); await tid(page, "videos").waitFor();
        for (const c of ["Anxiété", "Ruptures", "Sommeil", "Solitude"]) await see(page.getByText(c, { exact: true }).first(), `catégorie « ${c} » absente`);
      });
      const { videos } = await (await fetch(BASE + "/api/status")).json();
      if (!videos) throw new Partiel("sans clé YouTube sur le serveur, l'app ouvre une recherche YouTube au lieu de proposer des vidéos vérifiées");
    } },

  // Message 2 et brief — le design
  { demande: "Minimaliste, apaisant, vert sauge central, fond crème, coins arrondis, ombres légères, typographie élégante (palette #E7EDE4 #A8B9A1 #30483C #F6F3EC #FCFBF8 #8C918B #C6A77B)", test: (b) => session(b, {}, async ({ page }) => {
      for (const hex of ["#E7EDE4", "#A8B9A1", "#30483C", "#F6F3EC", "#FCFBF8", "#8C918B", "#C6A77B"]) need(theme.includes(hex), `la couleur ${hex} n'est pas dans le thème`);
      need(theme.includes("Fraunces") && theme.includes("DMSans"), "typographies absentes du thème");
      const bg = await tid(page, "home").evaluate((el) => getComputedStyle(el).backgroundColor);
      need(bg === "rgb(246, 243, 236)", `le fond n'est pas crème (${bg})`);
      const hard = fs.readdirSync(path.join(ROOT, "mobile/src/app"), { recursive: true }).filter((f) => f.endsWith(".tsx")).filter((f) => /#[0-9A-Fa-f]{6}\b/.test(read("mobile/src/app/" + f)));
      need(hard.length === 0, `couleurs en dur hors du thème : ${hard.join(", ")}`);
    }) },
  { demande: "Mode clair / sombre", test: (b) => session(b, { settings: { ...SETTINGS, appearance: "dark" } }, async ({ page }) => {
      const bg = await tid(page, "home").evaluate((el) => getComputedStyle(el).backgroundColor);
      need(bg === "rgb(23, 29, 25)", `le thème sombre ne s'applique pas (${bg})`);
    }) },
  { demande: "Excellente ergonomie mobile, y compris sur petit écran", test: (b) => session(b, { width: 320, height: 568 }, async ({ page }) => {
      await noOverflow(page, "l'accueil");
      for (const [name, id] of [["Journal", "journal"], ["Exercices", "exercises"], ["Progrès", "progress"], ["Profil", "profile"]]) { await tab(page, name); await tid(page, id).waitFor(); await noOverflow(page, `l'onglet ${name}`); }
      await tab(page, "Accueil"); await startChat(page); await noOverflow(page, "le chat");
    }) },
  { demande: "Pour les designs, les photos, tout : aide-toi de tous tes connecteurs et de Claude Design pour trouver de belles images", test: () => {
      need(exists("mobile/src/ui/Botanical.tsx"), "illustration d'accueil absente");
      throw new Partiel("une illustration a été générée avec Canva comme référence, puis redessinée en vectoriel ; les connecteurs CoDesign et Higgsfield exigent une connexion du propriétaire et l'image Canva en haute définition ne peut pas être téléchargée d'ici");
    } },

  { demande: "Je veux une interface comme ça (références : carte verte « comment tu te sens », visages d'humeur, raccourcis, cartes illustrées, plantes)", test: (b) => session(b, {}, async ({ page, sent }) => {
      for (let n = 1; n <= 5; n++) await see(tid(page, `home-mood-${n}`), `le visage d'humeur ${n} manque sur l'accueil`);
      for (const w of ["Prends un moment pour toi", "À voix haute", "Pour toi", "Respirer en paix", "Écrire pour soi"]) await see(tid(page, "home").getByText(w, { exact: true }), `l'accueil ne contient pas « ${w} »`);
      need((await tid(page, "home").locator("svg").count()) >= 12, "les illustrations ne s'affichent pas");
      for (const [name, id, title] of [["Journal", "journal", "Rien que pour toi"], ["Exercices", "exercises", "À ton rythme"], ["Progrès", "progress", "Pas à pas"], ["Profil", "profile", "Ton espace"]]) {
        await tab(page, name); await see(tid(page, id).getByText(title, { exact: true }), `l'onglet ${name} n'a pas la carte verte illustrée`);
        need((await tid(page, id).locator("svg").count()) >= 1, `pas d'illustration sur l'onglet ${name}`);
      }
      await tab(page, "Accueil");
      await tid(page, "home-mood-4").click(); await tid(page, "mood").waitFor();
      await tid(page, "mood-save").click(); await tid(page, "home").waitFor();
      need(((await stored(page, "confie.wellbeing")).moods ?? [])[0]?.mood === 4, "le visage choisi sur l'accueil n'est pas repris dans le point d'humeur");
      await tid(page, "home-input").fill("Je me sens perdue"); await tid(page, "home-send").click();
      await tid(page, "ai-message").first().waitFor({ timeout: 8000 });
      need(sent[0].messages[0].content === "Je me sens perdue", "ce qu'on écrit dans la carte verte n'ouvre pas la conversation");
    }) },

  // Message 3 — la question du mode
  { demande: "Comment veux-tu que je t'aide aujourd'hui ? Écoute-moi / Aide-moi à comprendre / Sois honnête / Trouve des solutions / Rassure-moi / Challenge-moi (+ Motive-moi), modifiable à tout moment", test: (b) => session(b, {}, async ({ page, sent }) => {
      need(Object.keys(MODES).length === 7, "il n'y a pas sept modes dans les consignes");
      await startChat(page);
      const q = tid(page, "mode-question");
      await see(q.getByText(/Comment veux-tu que je t'aide aujourd'hui/), "la question n'est pas posée au début de la conversation");
      for (const l of MODE_LABELS) await see(q.getByText(l, { exact: true }), `« ${l} » manque`);
      await q.getByText("Challenge-moi", { exact: true }).click(); await say(page, "bonjour");
      need(sent[0].context.mode === "challenge", "le mode choisi n'est pas transmis à l'IA");
      await tid(page, "mode-pill").click(); await page.getByText("Rassure-moi", { exact: true }).click(); await say(page, "encore");
      need(sent[1].context.mode === "rassure", "changer de mode en cours de conversation n'a pas d'effet");
    }) },

  // Message 4 — la vérification
  { demande: "Une vérification qui vérifie à chaque fois si tu as écouté et fait tout ce que je t'ai demandé", test: () => {
      need(read(".claude/settings.json").includes("verif/verifier.mjs"), "le crochet de fin de réponse n'est pas installé");
      need(read("CLAUDE.md").includes("npm run verif"), "la règle n'est pas dans CLAUDE.md");
    } },

  // Message 5 — le lien
  { demande: "Envoie un lien de l'application", test: () => {
      need(/https:\/\/claude\.ai\/artifact\/\S+/.test(readme), "aucun lien vers l'application dans le README");
      throw new Partiel("un lien d'aperçu privé existe (README) ; ce n'est pas encore une app hébergée ni publiée sur les stores");
    } },

  // Brief — écrans
  { demande: "Welcome screen : Commencer, présentation courte, informations sur l'IA et la confidentialité", test: (b) => session(b, { settings: null }, async ({ page }) => {
      await see(page.getByText("Commencer", { exact: true }), "bouton Commencer absent");
      await see(page.getByText(/intelligence artificielle/), "information « c'est une IA » absente");
      await see(page.getByText(/restent sur ton téléphone/), "information de confidentialité absente");
    }) },
  { demande: "Onboarding court, questions passables : prénom, sujets, préférence de communication, franchise, écouter ou solutions, mémoire, notifications, écrit ou vocal", test: (b) => session(b, { settings: null }, async ({ page }) => {
      await page.getByText("Commencer", { exact: true }).click(); await tid(page, "onboarding").waitFor();
      const seen = [];
      for (let i = 0; i < 5; i++) { seen.push(await tid(page, "onboarding").innerText()); await page.getByText("Passer", { exact: true }).click(); await page.waitForTimeout(250); }
      seen.push(await tid(page, "onboarding").innerText());
      const all = seen.join("\n");
      for (const w of ["appelle", "De quoi aimerais-tu parler", "Niveau de franchise", "Écoute-moi", "Trouve des solutions", "Mémoire", "Rappels", "Conversation vocale", "ne remplace ni un psychologue"]) need(all.includes(w), `l'onboarding ne propose pas « ${w} »`);
      await page.getByLabel("J'ai compris et j'accepte").click();
      await page.getByText("Entrer", { exact: true }).click(); await tid(page, "home").waitFor();
      const s = await stored(page, "confie.settings");
      need(s.memory === "off", "la mémoire est activée sans choix explicite");
      need(typeof s.consentAt === "number", "le consentement n'est pas enregistré");
    }) },
  { demande: "Home : « Bonjour, comment tu te sens aujourd'hui ? », « Je suis là pour t'écouter », Commencer une conversation, check-in, journal, exercices, vidéos, progrès", test: (b) => session(b, {}, async ({ page }) => {
      // Les blocs de l'accueil apparaissent en fondu l'un après l'autre : on attend chacun.
      await see(tid(page, "home").getByText(/^(Bonjour|Bonsoir)$/), "l'accueil ne salue pas la personne");
      for (const w of [/Comment tu te sens aujourd'hui/, /Tu peux prendre ton temps/, /Je suis là pour t'écouter/, /Commencer une conversation/, /^Vidéos$/]) await see(tid(page, "home").getByText(w), `l'accueil ne contient pas « ${w.source} »`);
      await see(tid(page, "checkin"), "check-in émotionnel absent");
      for (const n of ["Journal", "Exercices", "Progrès", "Profil"]) await see(page.getByRole("tab", { name: n }), `onglet ${n} absent`);
    }) },
  { demande: "Chat : streaming, indicateur de génération, historique, nouveau chat, renommer, supprimer, reprendre, suggestions, gestion des erreurs", test: (b) => session(b, {}, async ({ page }) => {
      await startChat(page);
      await tid(page, "composer").fill("premier message"); await tid(page, "send").click();
      await tid(page, "thinking").waitFor({ timeout: 3000 }); await tid(page, "ai-message").first().waitFor();
      await page.getByLabel("Options de la conversation").click(); await page.getByText("Renommer", { exact: true }).click();
      await page.locator("input").last().fill("Mon titre"); await page.getByText("Enregistrer", { exact: true }).click();
      await page.goto(BASE + "/conversations"); await tid(page, "conversations").waitFor();
      await see(page.getByText("Mon titre"), "renommer ne fonctionne pas ou l'historique est vide");
      await page.getByText("Mon titre").click(); await tid(page, "chat").waitFor();
      await see(page.getByText("premier message"), "reprendre une conversation ne recharge pas les messages");
      page.once("dialog", (d) => d.accept());
      await page.getByLabel("Options de la conversation").click(); await page.getByText("Supprimer la conversation").click();
      await tid(page, "home").waitFor();
      need(Object.keys((await stored(page, "confie.chats")).chats ?? {}).length === 0, "supprimer ne supprime pas la conversation");
    }) },
  { demande: "Une personne qui n'a pas Internet : le message n'est pas perdu et on peut réessayer", test: (b) => session(b, { offline: true }, async ({ page }) => {
      await startChat(page); await tid(page, "composer").fill("tu es là ?"); await tid(page, "send").click();
      await page.getByText(/Pas de connexion/).waitFor({ timeout: 8000 });
      await see(tid(page, "chat").getByText("tu es là ?"), "le message disparaît en cas de coupure");
      await see(page.getByText("Réessayer", { exact: true }), "pas de bouton Réessayer");
    }) },
  { demande: "Conversation temporaire : ni enregistrée ni mémorisée", test: (b) => session(b, {}, async ({ page, sent }) => {
      await page.goto(BASE + "/conversations"); await tid(page, "conversations").waitFor();
      await page.getByText("Conversation temporaire", { exact: true }).click(); await tid(page, "chat").waitFor();
      await say(page, "ne garde rien");
      need(sent[0].context.memory === null, "une conversation temporaire transmet la mémoire");
      need(!JSON.stringify(await stored(page, "confie.chats")).includes("ne garde rien"), "une conversation temporaire est enregistrée");
      need(((await stored(page, "confie.memory")).items ?? []).length === 0, "une conversation temporaire alimente la mémoire");
    }) },
  { demande: "Mode vocal : Je t'écoute / Je réfléchis / Je te réponds, interruption, mute, quitter, transcription, retour à l'écrit", test: async (b) => {
      const src = ["app/voix.tsx", "lib/voice.ts", "features/voice/useVoiceConversation.ts", "features/voice/Orb.tsx"].map((f) => read("mobile/src/" + f)).join("\n").replace(/[’\\]/g, (c) => (c === "’" ? "'" : ""));
      for (const w of ["Je t'écoute", "Je réfléchis", "Je te réponds", "voice-mute", "voice-interrupt", "voice-quit", "voice-write"]) need(src.includes(w), `le mode vocal ne contient pas « ${w} »`);
      await session(b, {}, async ({ page, errors }) => {
        await startChat(page); await tid(page, "voice").click();
        await page.locator('[data-testid="voice"]').last().waitFor({ timeout: 8000 });
        await see(page.locator('[data-testid="voice"]').last().getByText(/Écrire/), "pas de retour vers l'écrit depuis le mode vocal");
        need(errors.length === 0, `erreur à l'ouverture du mode vocal : ${errors[0]}`);
      });
      throw new Partiel("l'écran s'ouvre et gère l'absence de micro, mais la conversation à voix haute n'a pas pu être essayée sans vrai micro ni téléphone");
    } },
  { demande: "Mood tracker : humeur, émotions, intensité, stress, énergie, sommeil facultatif, commentaire ; visualisations simples, sans diagnostic", test: (b) => session(b, {}, async ({ page }) => {
      await tid(page, "checkin").click(); await tid(page, "mood").waitFor();
      await tid(page, "mood-4").click();
      for (const w of ["Stress", "Énergie", "Intensité", "ommeil"]) await see(tid(page, "mood").getByText(new RegExp(w)), `le point d'humeur ne propose pas « ${w} »`);
      await tid(page, "mood-save").click(); await tid(page, "home").waitFor();
      const moods = (await stored(page, "confie.wellbeing")).moods ?? [];
      need(moods.length === 1 && moods[0].mood === 4, "l'humeur n'est pas enregistrée");
      await tab(page, "Progrès"); await tid(page, "progress").waitFor();
      need((await tid(page, "progress").innerText()).includes("pas une évaluation médicale"), "la mention « pas un diagnostic » manque dans les progrès");
    }) },
  { demande: "Journal émotionnel : texte libre, questions guidées, émotions, dates, historique, suppression, non partagé avec l'IA par défaut", test: (b) => session(b, {}, async ({ page, sent }) => {
      await tab(page, "Journal"); await tid(page, "journal").waitFor();
      await page.goto(BASE + "/ecrire"); await tid(page, "journal-editor").waitFor();
      await tid(page, "journal-text").fill("Aujourd'hui j'ai osé lui parler.");
      await tid(page, "journal-save").click();
      await page.waitForFunction(() => (JSON.parse(localStorage.getItem("confie.wellbeing") || "{}").state?.journal ?? []).length === 1, null, { timeout: 5000 });
      const j = (await stored(page, "confie.wellbeing")).journal[0];
      need(j.shareWithAi === false, "une page de journal est partagée avec l'IA par défaut");
      need(sent.length === 0, "écrire dans le journal envoie quelque chose à l'IA");
    }) },
  { demande: "Exercices : respiration, ancrage, relaxation, stress, pensées répétitives, réflexion, communication, confiance, sommeil, objectifs — avec objectif, explication, instructions, durée, limites", test: async (b) => {
      const { EXERCISES } = await import(path.join(ROOT, "mobile/src/content/exercises.ts"));
      need(EXERCISES.length === 13, `13 exercices attendus, ${EXERCISES.length} trouvés`);
      for (const c of ["Respiration", "Ancrage", "Relaxation", "Stress", "Pensées répétitives", "Réflexion", "Communication", "Confiance en soi", "Sommeil", "Objectifs"]) need(EXERCISES.some((e) => e.category === c), `aucune fiche dans « ${c} »`);
      for (const e of EXERCISES) need(e.goal && e.why && e.steps.length >= 3 && e.minutes > 0 && e.source, `fiche incomplète : ${e.id}`);
      await session(b, {}, async ({ page }) => {
        await page.goto(BASE + "/exercice/coherence"); await tid(page, "exercise").waitFor();
        need((await tid(page, "exercise").innerText()).length > 200, "la fiche d'exercice est vide");
      });
    } },
  { demande: "Profil & réglages : préférences, franchise, notifications, voix, langue, apparence, mémoire, confidentialité, export, suppression des données", test: (b) => session(b, {}, async ({ page }) => {
      await tab(page, "Profil"); const t = await tid(page, "profile").innerText();
      for (const w of ["ranchise", "Mémoire", "Voix", "Langue", "Sombre", "Confidentialité"]) need(t.includes(w), `le profil ne contient pas « ${w} »`);
      await page.goto(BASE + "/confidentialite"); await tid(page, "privacy").waitFor();
      await see(tid(page, "export"), "export des données absent");
      page.once("dialog", (d) => d.accept());
      await tid(page, "delete-all").click(); await tid(page, "welcome").waitFor({ timeout: 8000 });
      await page.waitForTimeout(400);
      const left = await page.evaluate(() => Object.keys(localStorage).filter((k) => k.startsWith("confie.")).map((k) => localStorage.getItem(k)).join(""));
      need(!left.includes("Léa"), "après suppression, des données personnelles restent sur l'appareil");
    }) },
  { demande: "Page « Ce que mon IA retient » : consultable, modifiable, supprimable ; « Oublie cette information », « Supprime tout », « Désactive ta mémoire »", test: (b) => session(b, { reply: (n) => (n === 1 ? REPLY : "C'est fait.\n[[oublier: tout]]\n[[memoire: off]]") }, async ({ page }) => {
      promptHas("[[oublier: identifiant]]", "[[oublier: tout]]", "[[memoire: off]]", "Qu'est-ce que tu sais de moi");
      await startChat(page); await say(page, "je révise");
      need(((await stored(page, "confie.memory")).items ?? []).length === 1, "le souvenir n'est pas enregistré");
      await say(page, "Supprime tout ce que tu retiens et désactive ta mémoire");
      need(((await stored(page, "confie.memory")).items ?? []).length === 0, "« supprime tout » ne vide pas la mémoire");
      need((await stored(page, "confie.settings")).memory === "off", "« désactive ta mémoire » ne la désactive pas");
    }) },

  // Brief — sécurité
  { demande: "Sécurité psychologique : crise, numéros réels, ne pas prétendre être psy ni avoir prévenu les secours, pas de dépendance", test: (b) => session(b, { reply: "Je suis là. Est-ce que tu penses au suicide ?\n\n[[urgence]]" }, async ({ page }) => {
      promptHas("3114", "3919", "119", "ni psychologue", "N'invente jamais de numéro", "ne laisse jamais croire que tu as prévenu les secours", "Tu ne prétends pas aimer", "seul soutien");
      await startChat(page); await say(page, "je n'en peux plus");
      await page.getByLabel("Voir les numéros d'aide").click(); await tid(page, "help").waitFor();
      for (const n of ["3114", "112", "3919", "119"]) await see(tid(page, "help").getByText(new RegExp(`^${n} ·`)), `le ${n} n'est pas dans l'aide urgente`);
    }) },
  { demande: "Sécurité technique : pas de clé dans l'app, RLS sur toutes les tables, pas de contenu sensible dans les logs", test: () => {
      const dist = path.join(ROOT, "mobile/dist");
      const js = fs.readdirSync(dist, { recursive: true }).filter((f) => String(f).endsWith(".js")).map((f) => fs.readFileSync(path.join(dist, String(f)), "utf8")).join("");
      need(!/sk-ant-|ANTHROPIC_API_KEY|YOUTUBE_API_KEY|service_role/.test(js), "un secret ou son nom apparaît dans l'application");
      const tables = [...sql.matchAll(/create table public\.(\w+)/g)].map((m) => m[1]);
      for (const t of tables) need(sql.includes(`alter table public.${t} enable row level security`), `RLS non activée sur ${t}`);
      need(tables.length >= 9, "tables manquantes dans le schéma");
      need(!/console\.(log|error)\([^)]*(messages|body|content)/.test(read("server.js")), "le serveur journalise du contenu de conversation");
    } },
  { demande: "Backend Supabase : Auth, PostgreSQL, Row Level Security", test: () => { throw new Partiel("schéma et règles de sécurité écrits, écran de connexion prêt, mais aucun projet Supabase n'est relié : rien n'a été exécuté sur une vraie base et la synchronisation n'est pas faite"); } },
  { demande: "Utilisable sur iOS et Android", test: () => { throw new Partiel("le code est commun aux trois plateformes et compile, mais seule la version web a été testée ; aucun essai sur iPhone ou Android"); } },
  { demande: "Monétisation freemium transparente, sans paywall en moment de détresse", test: () => { throw new Partiel(exists("docs/RECHERCHE-VOIX-COUTS.md") ? "modèle et coûts étudiés dans docs/RECHERCHE-VOIX-COUTS.md ; aucun paiement n'est branché dans l'app" : "aucun paiement branché ; l'étude des coûts n'est pas terminée"); } },
  { demande: "Préparation App Store / Google Play, politique de confidentialité, conditions d'utilisation", test: () => {
      need(exists("docs/legal/CONFIDENTIALITE.md") && exists("docs/legal/CONDITIONS.md"), "brouillons juridiques absents");
      throw new Partiel("brouillons juridiques écrits (à valider par un juriste) ; pas de compte développeur, donc aucune fiche de store ni build signé");
    } },
  { demande: "Documentation : README, Architecture, Design-system, ROADMAP, TASKS, CHANGELOG, SECURITY, ENVIRONMENT, Testing, Product decisions", test: () => {
      for (const f of ["README.md", "ROADMAP.md", "TASKS.md", "CHANGELOG.md", "docs/ARCHITECTURE.md", "docs/DESIGN-SYSTEM.md", "docs/SECURITY.md", "docs/ENVIRONMENT.md", "docs/TESTING.md", "docs/DECISIONS.md"]) need(exists(f) && read(f).length > 400, `document manquant ou vide : ${f}`);
    } },
];

// ——— Exécution ———
let chromium;
try { ({ chromium } = createRequire(import.meta.url)("playwright")); } catch {
  console.error("Vérification impossible ici : le navigateur de test (Playwright) n'est pas installé.");
  process.exit(hook ? 0 : 1);
}
if (!exists("mobile/dist/index.html")) {
  console.error("Vérification impossible : l'application n'est pas construite. Lance d'abord : npm run build");
  process.exit(hook ? 0 : 1);
}

const env = { ...process.env, PORT: String(PORT) };
const server = spawn(process.execPath, ["server.js"], { cwd: ROOT, env, stdio: "ignore" });
for (let i = 0; i < 50; i++) { try { await fetch(BASE + "/api/status"); break; } catch { await new Promise((r) => setTimeout(r, 100)); } }

const browser = await chromium.launch();
const run = async (e) => {
  try { await e.test(browser); return { e, status: "ok" }; }
  catch (err) { return { e, status: err instanceof Partiel ? "partiel" : "ko", why: String(err.message).split("\n")[0] }; }
};
const results = [];
for (let i = 0; i < EXIGENCES.length; i += 4) results.push(...(await Promise.all(EXIGENCES.slice(i, i + 4).map(run))));
await browser.close();
server.kill();

const count = (s) => results.filter((r) => r.status === s).length;
const lines = results.map((r) => r.status === "ok" ? `✅ ${r.e.demande}` : r.status === "partiel" ? `🟡 ${r.e.demande}\n     partiel : ${r.why}` : `❌ ${r.e.demande}\n     pas fait : ${r.why}`);
const out = `Vérification des demandes — ${count("ok")} faites, ${count("partiel")} partielles, ${count("ko")} pas faites\n\n${lines.join("\n")}\n`;
if (count("ko") && hook) { console.error(out + "\nCorrige les ❌ avant de dire que c'est terminé."); process.exit(2); }
console.log(out);
process.exit(count("ko") ? 1 : 0);
