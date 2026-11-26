// Parcours complet de Confie dans les conditions réelles de l'aperçu en ligne :
// la version publiée (mobile/dist-preview), dans un cadre isolé, sur un écran d'iPhone, AU DOIGT.
// Chaque étape est ce qu'une personne fait vraiment. Lancer avec : npm run parcours
//
// Deux passes : cadre normal, puis cadre où le stockage du navigateur est bloqué.

import { createRequire } from "node:module";
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const DIR = path.join(ROOT, "mobile/dist-preview");
const SHOTS = process.env.PARCOURS_SHOTS || "";

export async function parcours({ quiet = false } = {}) {
  if (!fs.existsSync(path.join(DIR, "preview.html"))) return { ok: false, failures: ["l'aperçu n'est pas construit (npm run preview:build)"], steps: 0 };
  const { chromium, devices } = createRequire(import.meta.url)("playwright");

  // La page publiée est enveloppée comme le fait la plateforme, puis chargée dans un cadre isolé.
  const frameHtml = `<!doctype html><html><head><meta charset=utf8><meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover"><style>body{margin:0;font:14px system-ui}[hidden]{display:none!important}</style></head><body>${fs.readFileSync(path.join(DIR, "preview.html"), "utf8")}</body></html>`;
  const host = (sandbox) => `<!doctype html><html><head><meta name=viewport content="width=device-width,initial-scale=1"></head><body style="margin:0"><iframe id="f" sandbox="${sandbox}" src="/frame.html" style="border:0;width:100vw;height:100vh;display:block"></iframe></body></html>`;
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, "http://x");
    if (url.pathname === "/host") { res.writeHead(200, { "Content-Type": "text/html" }); return res.end(host(url.searchParams.get("s"))); }
    if (url.pathname === "/app.js") { res.writeHead(200, { "Content-Type": "text/javascript", "Access-Control-Allow-Origin": "*" }); return res.end(fs.readFileSync(path.join(DIR, "app.js"))); }
    if (path.extname(url.pathname) && url.pathname !== "/frame.html") { res.writeHead(404); return res.end(); }
    res.writeHead(200, { "Content-Type": "text/html" }); res.end(frameHtml); // toute autre adresse : l'app
  });
  await new Promise((r) => server.listen(0, r));
  const base = `http://localhost:${server.address().port}`;

  const browser = await chromium.launch();
  const failures = [];
  let steps = 0;

  for (const [label, sandbox] of [["cadre normal", "allow-scripts allow-same-origin allow-popups"], ["stockage bloqué", "allow-scripts allow-popups"]]) {
    const ctx = await browser.newContext({ ...devices["iPhone 13"], locale: "fr-FR" });
    const page = await ctx.newPage();
    const crashes = [];
    page.on("pageerror", (e) => crashes.push(e.message.slice(0, 140)));
    // Claude simulé, comme le fournit la page hôte de l'aperçu. confirm() bloqué, comme dans l'aperçu.
    await ctx.addInitScript(() => {
      window.confirm = () => false;
      window.open = () => null;
      window.__inputs = [];
      window.claude = { use: async (n) => (n === "sample" ? async (input, opts) => { window.__inputs.push(input); opts?.onText?.({ text: "Je t'entends." }); await new Promise((r) => setTimeout(r, 120)); const text = "Je t'entends. Raconte-moi ce qui pèse le plus.\n\n[[video: gérer le stress psychologue]]"; opts?.onText?.({ text }); return { text, truncated: false }; } : null) };
    });
    await page.goto(`${base}/host?s=${encodeURIComponent(sandbox)}`);
    const f = page.frameLocator("#f");
    const tid = (id) => f.locator(`[data-testid="${id}"]`).last(); // le dernier = l'écran au premier plan
    const count = (id) => f.locator(`[data-testid="${id}"]`).count();
    const txt = (t, exact = true) => f.getByText(t, { exact });
    const tap = (loc) => loc.first().tap({ timeout: 6000 });
    const see = (loc) => loc.first().waitFor({ state: "visible", timeout: 6000 });
    const inView = async (loc) => { const b = await loc.first().boundingBox(); return !!b && b.y >= 0 && b.y < 844; };
    const tabTo = (name) => tap(f.getByRole("tab", { name }));
    let n = 0;
    const step = async (name, fn) => {
      steps++; n++;
      try { await fn(); } catch (e) { failures.push(`[${label}] ${name} — ${String(e.message).split("\n")[0].slice(0, 150)}`); }
      if (SHOTS) await page.screenshot({ path: `${SHOTS}/p-${label.replace(/\W+/g, "")}-${String(n).padStart(2, "0")}.png` }).catch(() => {});
    };

    await step("ouvrir l'app et toucher Commencer", async () => { await tap(txt("Commencer")); await see(tid("onboarding")); });
    await step("saisir son prénom", async () => { await f.getByPlaceholder("Ton prénom ou un surnom").fill("Léa"); await tap(txt("Continuer")); await see(txt("De quoi aimerais-tu parler ?")); });
    await step("choisir des sujets", async () => { await tap(txt("Stress et anxiété")); await tap(txt("Continuer")); await see(txt("Comment préfères-tu qu'on te parle ?")); });
    await step("cocher PLUSIEURS façons de parler", async () => {
      await tap(tid("style-franche")); await tap(tid("style-positive")); await tap(tid("style-ecoute"));
      await tap(tid("style-ecoute")); // et pouvoir décocher
      await tap(txt("Sans filtre"));
    });
    await step("étape suivante : elle s'affiche depuis le haut, avec son titre", async () => {
      await tap(txt("Continuer")); await see(txt("En général, tu préfères…"));
      if (!(await inView(txt("En général, tu préfères…")))) throw new Error("le titre de l'étape est hors de l'écran (page restée défilée)");
      await tap(txt("Trouve des solutions"));
    });
    await step("réglages : activer la mémoire", async () => { await tap(txt("Continuer")); await see(txt("Quelques réglages")); await tap(f.getByLabel("Mémoire")); await tap(txt("Continuer")); await see(txt("Avant de commencer")); });
    await step("accepter et entrer", async () => { await tap(f.getByLabel("J'ai compris et j'accepte")); await tap(txt("Entrer")); await see(tid("home")); await see(txt("Léa")); });

    await step("écrire dans la carte d'accueil et recevoir une réponse", async () => {
      await tid("home-input").fill("Je suis stressée par mon travail"); await tap(tid("home-send"));
      await see(tid("chat")); await see(tid("chat").getByText(/Raconte-moi ce qui pèse/));
      const input = await f.locator("body").evaluate(() => JSON.stringify(window.__inputs.at(-1)));
      if (!/franc et direct/i.test(input) || !/positif et motivant/i.test(input)) throw new Error("les styles cochés ne sont pas tous transmis à l'IA");
      if (/coute d'abord/i.test(input)) throw new Error("un style décoché est quand même transmis");
      if (!/TROUVE DES SOLUTIONS/.test(input)) throw new Error("le mode choisi n'est pas transmis");
    });
    await step("la vidéo proposée est un vrai lien YouTube", async () => {
      const link = tid("chat").locator('a[href^="https://www.youtube.com/results"]');
      await see(link);
      if ((await link.first().getAttribute("target")) !== "_blank") throw new Error("le lien ne s'ouvre pas dans un nouvel onglet");
    });
    await step("envoyer un deuxième message", async () => { await tid("composer").fill("Et je dors mal"); await tap(tid("send")); await f.locator('[data-testid="ai-message"]').nth(1).waitFor({ timeout: 6000 }); });
    await step("changer de mode en cours de conversation", async () => { await tap(tid("mode-pill")); await tap(txt("Rassure-moi")); await see(tid("chat").getByText(/Rassure-moi/)); });
    await step("ouvrir le mode vocal puis revenir à l'écrit", async () => {
      await tid("composer").fill(""); await tap(tid("voice"));
      await see(f.getByText(/Écrire/).last()); await f.getByText(/Écrire/).last().tap({ timeout: 6000 });
      await f.locator('[data-testid="composer"]').last().waitFor({ state: "visible", timeout: 6000 });
      if ((await f.locator('[data-testid="composer"]').count()) > 1) throw new Error("deux écrans de conversation sont empilés après le retour à l'écrit");
    });
    await step("supprimer la conversation (confirmation intégrée)", async () => {
      await f.getByLabel("Options de la conversation").last().tap({ timeout: 6000 }); await tap(txt("Supprimer la conversation"));
      await see(tid("confirm")); await tap(tid("confirm-yes")); await see(tid("home"));
      if ((await count("home")) > 1) throw new Error("deux accueils sont empilés après la suppression");
      if (await tid("home").getByText(/Reprendre :/).count()) throw new Error("la conversation supprimée est encore proposée");
    });

    await step("noter son humeur depuis l'accueil", async () => { await tap(tid("home-mood-4")); await see(tid("mood")); await tap(tid("mood-save")); await see(tid("home").getByText(/Aujourd'hui : plutôt bien/)); });
    await step("journal : écrire et enregistrer une page", async () => {
      await tabTo("Journal"); await tap(tid("journal-write")); await see(tid("journal-editor"));
      await tid("journal-text").fill("Aujourd'hui j'ai osé demander de l'aide."); await tap(tid("journal-save"));
      await see(tid("journal").getByText(/osé demander de l'aide/));
    });
    await step("exercices : ouvrir une fiche et lancer le guidage", async () => {
      await tabTo("Exercices"); await tap(tid("exercise-coherence")); await see(tid("exercise"));
      await tap(tid("exercise").getByText(/Commencer/)); await see(tid("exercise").getByText(/Inspire|Expire/));
    });
    await step("progrès : l'humeur notée apparaît", async () => { await page.goBack().catch(() => {}); await tabTo("Progrès"); await see(tid("progress").getByText(/Humeur/)); });
    await step("profil : cocher plusieurs styles", async () => {
      await tabTo("Profil"); await tap(tid("profile").getByText("Style", { exact: true }));
      await tap(tid("style-analyse")); await tap(txt("Terminé"));
      await see(tid("profile").getByText(/Analyse et solutions/));
      await see(tid("profile").getByText(/Franche et directe/));
    });
    await step("mémoire : ajouter une information", async () => {
      await tap(tid("profile").getByText("Ce que mon IA retient")); await see(tid("memory"));
      await tid("memory").locator('input[type="text"], input:not([type]), textarea').first().fill("Je préfère qu'on me tutoie"); await tap(tid("memory").getByText("Ajouter", { exact: true }));
      await see(tid("memory").getByText("Je préfère qu'on me tutoie"));
    });
    await step("vidéos : choisir un thème donne un vrai lien", async () => {
      await page.goBack().catch(() => {}); await tabTo("Accueil"); await tap(tid("home").getByText("Vidéos", { exact: true })); await see(tid("videos"));
      await tap(tid("videos").getByText("Anxiété", { exact: true })); await see(tid("videos").locator('a[href^="https://www.youtube.com/"]'));
    });
    await step("aide urgente : les numéros sont lisibles", async () => { await page.goBack().catch(() => {}); await tap(f.getByLabel("Aide urgente").first()); await see(tid("help").getByText(/^3114 ·/)); await tap(tid("help").getByText("Fermer", { exact: true }).or(f.getByText("Fermer", { exact: true }).last())); });
    await step("confidentialité : exporter puis tout supprimer", async () => {
      await tabTo("Profil"); await tap(tid("profile").getByText("Confidentialité et données", { exact: true })); await see(tid("privacy"));
      await tap(tid("export")); await see(tid("privacy").getByText(/Tes données sont prêtes|téléchargement a été lancé/));
      await tap(tid("delete-all")); await see(tid("confirm")); await tap(tid("confirm-yes")); await see(tid("welcome"));
    });
    await step("aucun écran n'a planté", async () => {
      if (await tid("crash").count()) throw new Error("l'écran d'erreur s'est affiché");
      const real = crashes.filter((c) => !/ResizeObserver/.test(c));
      if (real.length) throw new Error(real[0]);
    });
    await ctx.close();
  }

  await browser.close();
  server.close();
  if (!quiet) console.log(failures.length ? `Parcours : ${failures.length} échec(s) sur ${steps} étapes\n` + failures.map((x) => "  ❌ " + x).join("\n") : `Parcours : ${steps} étapes réussies, au doigt, dans les deux cadres`);
  return { ok: failures.length === 0, failures, steps };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const r = await parcours();
  process.exit(r.ok ? 0 : 1);
}
