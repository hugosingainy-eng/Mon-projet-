import http from "node:http";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import Anthropic from "@anthropic-ai/sdk";
import { SYSTEM_PROMPT, MODES, TONES, personalContext } from "./prompt.js";

const PORT = process.env.PORT || 3000;
const MODEL = process.env.CONFIE_MODEL || "claude-opus-5-5";
const PUBLIC_DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), "public");

const MAX_BODY_BYTES = 200_000;
const MAX_MESSAGES = 40; // derniers messages envoyés au modèle
const MAX_MESSAGE_CHARS = 6_000;
const RATE_LIMIT = { windowMs: 60_000, max: 12 }; // messages par minute et par adresse

const hasCredentials = Boolean(process.env.ANTHROPIC_API_KEY || process.env.ANTHROPIC_AUTH_TOKEN);
const client = hasCredentials ? new Anthropic() : null;

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".webmanifest": "application/manifest+json",
};

const hits = new Map();
function rateLimited(ip) {
  const now = Date.now();
  const recent = (hits.get(ip) ?? []).filter((t) => now - t < RATE_LIMIT.windowMs);
  recent.push(now);
  hits.set(ip, recent);
  return recent.length > RATE_LIMIT.max;
}
setInterval(() => {
  const now = Date.now();
  for (const [ip, times] of hits) {
    if (times.every((t) => now - t >= RATE_LIMIT.windowMs)) hits.delete(ip);
  }
}, RATE_LIMIT.windowMs).unref();

function sendJson(res, status, body) {
  res.writeHead(status, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify(body));
}

async function readJson(req) {
  const chunks = [];
  let size = 0;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > MAX_BODY_BYTES) throw Object.assign(new Error("too large"), { status: 413 });
    chunks.push(chunk);
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch {
    throw Object.assign(new Error("bad json"), { status: 400 });
  }
}

// Ne garde que des messages texte valides, alternés, commençant par la personne.
function cleanMessages(raw) {
  if (!Array.isArray(raw)) return [];
  const out = [];
  for (const m of raw.slice(-MAX_MESSAGES)) {
    if (!m || (m.role !== "user" && m.role !== "assistant")) continue;
    if (typeof m.content !== "string" || !m.content.trim()) continue;
    const content = m.content.slice(0, MAX_MESSAGE_CHARS);
    const last = out.at(-1);
    if (last && last.role === m.role) last.content += "\n\n" + content;
    else out.push({ role: m.role, content });
  }
  while (out.length && out[0].role !== "user") out.shift();
  return out;
}

async function handleChat(req, res) {
  if (!client) {
    return sendJson(res, 503, {
      error: "Confie n'est pas encore branchée à son IA : il manque la clé ANTHROPIC_API_KEY sur le serveur.",
    });
  }
  const ip = req.socket.remoteAddress ?? "?";
  if (rateLimited(ip)) {
    return sendJson(res, 429, { error: "Doucement, je suis toujours là. Réessaie dans une minute." });
  }

  const body = await readJson(req);
  const messages = cleanMessages(body.messages);
  if (!messages.length || messages.at(-1).role !== "user") {
    return sendJson(res, 400, { error: "Message manquant." });
  }
  const name = typeof body.name === "string" ? body.name.replace(/[^\p{L}\p{M} '-]/gu, "").trim().slice(0, 40) : "";
  const mode = Object.hasOwn(MODES, body.mode) ? body.mode : "ecoute";
  const tone = Object.hasOwn(TONES, body.tone) ? body.tone : "gentil";

  const stream = client.beta.messages.stream({
    model: MODEL,
    max_tokens: 16000,
    output_config: { effort: "medium" },
    // Si le modèle principal décline une demande, l'API la relance sur un modèle de secours.
    betas: ["server-side-fallback-2026-07-01"],
    fallbacks: "default",
    system: [
      { type: "text", text: SYSTEM_PROMPT, cache_control: { type: "ephemeral" } },
      { type: "text", text: personalContext({ mode, tone, name }) },
    ],
    messages,
  });
  req.on("close", () => stream.abort());

  let started = false;
  const start = () => {
    if (started) return;
    started = true;
    res.writeHead(200, {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "no-store",
      "X-Accel-Buffering": "no",
    });
  };

  try {
    for await (const event of stream) {
      if (event.type === "content_block_delta" && event.delta.type === "text_delta") {
        start();
        res.write(event.delta.text);
      }
    }
    const final = await stream.finalMessage();
    if (final.stop_reason === "refusal") {
      start();
      res.write(
        (started ? "\n\n" : "") +
          "Je ne peux pas aller plus loin sur ce point précis. Mais je suis là : dis-moi ce que tu ressens, et on avance ensemble.",
      );
    }
    start();
    res.end();
  } catch (err) {
    if (res.writableEnded || req.destroyed) return;
    let status = 502;
    let message = "Je n'arrive pas à te répondre pour le moment. Réessaie dans un instant.";
    if (err instanceof Anthropic.AuthenticationError) {
      status = 503;
      message = "La clé d'accès à l'IA n'est pas valide. Vérifie ANTHROPIC_API_KEY sur le serveur.";
    } else if (err instanceof Anthropic.RateLimitError) {
      status = 429;
      message = "Beaucoup de monde se confie en ce moment. Réessaie dans une minute.";
    } else if (err instanceof Anthropic.APIUserAbortError) {
      return;
    }
    console.error("[chat]", err?.status ?? "", err?.message ?? err);
    if (started) res.end("\n\n" + message);
    else sendJson(res, status, { error: message });
  }
}

async function serveStatic(req, res, pathname) {
  const rel = pathname === "/" ? "index.html" : decodeURIComponent(pathname).replace(/^\/+/, "");
  const file = path.join(PUBLIC_DIR, rel);
  if (!file.startsWith(PUBLIC_DIR + path.sep)) return sendJson(res, 403, { error: "Interdit." });
  try {
    const data = await fs.readFile(file);
    res.writeHead(200, {
      "Content-Type": MIME[path.extname(file)] ?? "application/octet-stream",
      "Cache-Control": "no-cache",
    });
    res.end(data);
  } catch {
    sendJson(res, 404, { error: "Introuvable." });
  }
}

const server = http.createServer(async (req, res) => {
  try {
    const { pathname } = new URL(req.url, "http://localhost");
    if (pathname === "/api/chat" && req.method === "POST") return await handleChat(req, res);
    if (pathname === "/api/status" && req.method === "GET") return sendJson(res, 200, { ready: hasCredentials });
    if (req.method === "GET" || req.method === "HEAD") return await serveStatic(req, res, pathname);
    sendJson(res, 405, { error: "Méthode non autorisée." });
  } catch (err) {
    if (!res.headersSent) sendJson(res, err.status ?? 500, { error: "Une erreur est survenue." });
    else res.end();
  }
});

server.listen(PORT, () => {
  console.log(`Confie est ouverte sur http://localhost:${PORT}`);
  if (!hasCredentials) console.log("⚠ ANTHROPIC_API_KEY manquante : l'interface s'affiche, mais l'IA ne répondra pas.");
});
