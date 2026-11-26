// Construit l'aperçu en ligne de Confie : une page + un fichier JavaScript, publiables tels quels.
// Dans cet aperçu, l'IA passe par le pont `window.confieBridge` (Claude fourni par la page hôte)
// au lieu du serveur. Les consignes sont les mêmes que celles du serveur (prompt.js).
// Usage : npm run preview:build
import { execSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const MOBILE = path.join(ROOT, "mobile");
const OUT = path.join(MOBILE, "dist-preview");

execSync("npx expo export -p web --output-dir dist-preview", { cwd: MOBILE, stdio: "inherit", env: { ...process.env, CONFIE_PREVIEW: "1" } });

const jsDir = path.join(OUT, "_expo/static/js/web");
const entries = fs.readdirSync(jsDir).filter((f) => f.endsWith(".js"));
if (entries.length !== 1) throw new Error(`un seul fichier JavaScript attendu, ${entries.length} trouvés`);
fs.copyFileSync(path.join(jsDir, entries[0]), path.join(OUT, "app.js"));

const font = (pkg, weight, name) => {
  const file = path.join(MOBILE, "node_modules/@expo-google-fonts", pkg, weight, `${name}.ttf`);
  return `@font-face{font-family:"${name}";src:url(data:font/ttf;base64,${fs.readFileSync(file).toString("base64")}) format("truetype");font-display:swap}`;
};
const fonts = [
  font("fraunces", "600SemiBold", "Fraunces_600SemiBold"),
  font("figtree", "400Regular", "Figtree_400Regular"),
  font("figtree", "500Medium", "Figtree_500Medium"),
  font("figtree", "600SemiBold", "Figtree_600SemiBold"),
].join("\n");

const prompt = fs.readFileSync(path.join(ROOT, "prompt.js"), "utf8").replace(/^export /gm, "");

const bridge = `(() => {
${prompt}
  const fail = (message) => Object.assign(new Error(message), { name: "BridgeError" });
  window.confieBridge = async (body, onText, signal) => {
    const sample = await window.claude?.use("sample");
    if (!sample) throw fail("indisponible");
    const turns = (body.messages || []).filter((m) => m && typeof m.content === "string" && m.content.trim());
    while (turns.length && turns[0].role !== "user") turns.shift();
    if (!turns.length) throw fail("vide");
    const instructions = SYSTEM_PROMPT + "\\n\\n" + personalContext(body.context);
    const input = turns.map((m, i) => ({
      role: m.role === "assistant" ? "assistant" : "user",
      content: i === 0 ? "<consignes>\\n" + instructions + "\\n</consignes>\\n\\nLa conversation commence. Premier message de la personne :\\n\\n" + m.content : m.content,
    }));
    const res = await sample(input, { onText: ({ text }) => onText(text), signal, cache: false });
    if (!res.text || !res.text.trim()) throw fail("vide");
    return res.text;
  };
})();`.replace(/<\/script/gi, "<\\/script");

const html = `<title>Confie</title>
<meta name="claude:viewport-fit-sides" content="cover">
<style>
${fonts}
:root { --bg: #F6F3EC; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg: #171D19; color-scheme: dark } }
:root[data-theme="dark"] { --bg: #171D19; color-scheme: dark }
html, body { height: 100%; }
body { overflow: hidden; background: var(--bg); }
#root { display: flex; height: 100%; flex: 1; }
</style>
<div id="root"></div>
<script>
${bridge}
</script>
<script src="app.js" defer></script>
`;
fs.writeFileSync(path.join(OUT, "preview.html"), html);
console.log(`Aperçu prêt : ${path.relative(ROOT, OUT)}/preview.html (${(html.length / 1024).toFixed(0)} Ko) + app.js (${(fs.statSync(path.join(OUT, "app.js")).size / 1e6).toFixed(1)} Mo)`);
