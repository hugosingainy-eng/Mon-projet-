import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import path from "node:path";
import { after, before, test } from "node:test";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const PORT = 3700 + Math.floor(Math.random() * 200);
const BASE = `http://localhost:${PORT}`;
let server;

before(async () => {
  const env = { ...process.env, PORT: String(PORT), CONFIE_ALLOWED_ORIGINS: "https://app.example" };
  delete env.ANTHROPIC_API_KEY; delete env.ANTHROPIC_AUTH_TOKEN; delete env.YOUTUBE_API_KEY;
  server = spawn(process.execPath, ["server.js"], { cwd: ROOT, env, stdio: "ignore" });
  for (let i = 0; i < 50; i++) { try { await fetch(BASE + "/api/status"); return; } catch { await new Promise((r) => setTimeout(r, 100)); } }
  throw new Error("le serveur ne démarre pas");
});
after(() => server?.kill());

const post = (body, headers = {}) => fetch(BASE + "/api/chat", { method: "POST", headers: { "Content-Type": "application/json", ...headers }, body: typeof body === "string" ? body : JSON.stringify(body) });

test("sans clé, le serveur le dit clairement au lieu de planter", async () => {
  assert.deepEqual(await (await fetch(BASE + "/api/status")).json(), { ready: false, videos: false });
  const r = await post({ messages: [{ role: "user", content: "bonjour" }] });
  assert.equal(r.status, 503);
  assert.match((await r.json()).error, /ANTHROPIC_API_KEY/);
});

test("aucun fichier hors de l'application n'est servi", async () => {
  for (const p of ["/../server.js", "/..%2f..%2fpackage.json", "/%2e%2e/prompt.js", "/.env"]) {
    const r = await fetch(BASE + p);
    const text = await r.text();
    assert.ok(!text.includes("ANTHROPIC") && !text.includes("SYSTEM_PROMPT") && !text.includes('"scripts"'), `fuite via ${p}`);
  }
});

test("sans clé YouTube, aucune vidéo n'est inventée", async () => {
  assert.deepEqual(await (await fetch(BASE + "/api/videos?q=anxi%C3%A9t%C3%A9")).json(), { verified: false, videos: [] });
  assert.equal((await fetch(BASE + "/api/videos")).status, 400);
});

test("seules les origines web autorisées reçoivent l'en-tête CORS", async () => {
  const ok = await fetch(BASE + "/api/status", { headers: { Origin: "https://app.example" } });
  assert.equal(ok.headers.get("access-control-allow-origin"), "https://app.example");
  const ko = await fetch(BASE + "/api/status", { headers: { Origin: "https://evil.example" } });
  assert.equal(ko.headers.get("access-control-allow-origin"), null);
});

test("les méthodes inattendues sont refusées", async () => {
  assert.equal((await fetch(BASE + "/api/chat", { method: "DELETE" })).status, 405);
});
