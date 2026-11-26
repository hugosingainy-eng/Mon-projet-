const $ = (id) => document.getElementById(id);
const KEY = "confie.v1";

const STARTERS = [
  "Je viens de vivre une rupture",
  "Je doute de mon couple",
  "Je me sens seul·e",
  "Je n'arrive pas à l'oublier",
  "J'ai une question intime",
];

// ——— État ———
// profile : { name, mode, memory }   messages : [{ role, content }]
let profile = null;
let messages = [];
let busy = false;

function load() {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY));
    if (saved?.profile) {
      profile = { mode: "ecoute", ...saved.profile };
      messages = Array.isArray(saved.messages) ? saved.messages : [];
    }
  } catch { /* stockage indisponible : on fonctionne sans mémoire */ }
}

function save() {
  try {
    if (!profile) return localStorage.removeItem(KEY);
    // Sans mémoire, on ne garde que les réglages : jamais la conversation.
    const data = profile.memory ? { profile, messages } : { profile: { ...profile, name: "" }, messages: [] };
    localStorage.setItem(KEY, JSON.stringify(data));
  } catch { /* idem */ }
}

// ——— Rendu ———
const esc = (s) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const inline = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/(^|[\s(])\*(?!\s)(.+?)\*/g, "$1<em>$2</em>");

// Markdown minimal : paragraphes, listes, gras, italique.
function renderText(text) {
  const html = [];
  let list = null;
  const closeList = () => { if (list) { html.push(`</${list}>`); list = null; } };
  for (const block of text.trim().split(/\n{2,}/)) {
    const para = [];
    const flush = () => { if (para.length) { html.push(`<p>${para.join("<br>")}</p>`); para.length = 0; } };
    for (const line of block.split("\n")) {
      const ul = line.match(/^\s*[-•*]\s+(.*)/);
      const ol = line.match(/^\s*\d+[.)]\s+(.*)/);
      if (ul || ol) {
        flush();
        const tag = ul ? "ul" : "ol";
        if (list !== tag) { closeList(); html.push(`<${tag}>`); list = tag; }
        html.push(`<li>${inline((ul || ol)[1])}</li>`);
      } else {
        closeList();
        para.push(inline(line.replace(/^#+\s*/, "")));
      }
    }
    flush();
  }
  closeList();
  return html.join("");
}

// Sépare le texte des suggestions de vidéos ([[video: mots-clés]]).
function splitVideos(raw) {
  const videos = [];
  let text = raw.replace(/\[\[\s*video\s*:\s*([^\]\n]+?)\s*\]\]/gi, (_, q) => { videos.push(q); return ""; });
  text = text.replace(/\[\[[^\]]*$/, ""); // balise encore en cours d'écriture
  return { text, videos };
}

function renderAi(el, raw) {
  const { text, videos } = splitVideos(raw);
  let html = renderText(text);
  if (videos.length) {
    html += `<div class="videos">${videos.map((q) => `
      <a class="video" target="_blank" rel="noopener noreferrer" href="https://www.youtube.com/results?search_query=${encodeURIComponent(q)}">
        <span class="play"><svg viewBox="0 0 12 12"><path d="M2 1l9 5-9 5z"/></svg></span>
        <span>${esc(q)}<small>Voir des vidéos sur YouTube</small></span>
      </a>`).join("")}</div>`;
  }
  el.innerHTML = html;
}

function addBubble(role, content) {
  const el = document.createElement("div");
  el.className = `msg ${role === "user" ? "user" : role === "assistant" ? "ai" : "note"}`;
  if (role === "user") el.textContent = content;
  else if (role === "assistant") renderAi(el, content);
  else el.textContent = content;
  $("messages").append(el);
  scrollDown();
  return el;
}

function scrollDown() {
  const box = $("messages");
  box.scrollTop = box.scrollHeight;
}

function greeting() {
  const hour = new Date().getHours();
  const hello = hour >= 18 || hour < 5 ? "Bonsoir" : "Bonjour";
  const who = profile.name ? ` ${profile.name}` : "";
  return messages.length
    ? `Contente de te retrouver${who}. On reprend où tu veux.`
    : `${hello}${who}. Ici, tu peux tout dire, rien ne me choque et rien ne sort d'ici. Qu'est-ce qui t'amène ?`;
}

function showChat() {
  $("welcome").hidden = true;
  $("chat").hidden = false;
  $("messages").replaceChildren();
  for (const m of messages) addBubble(m.role, m.content);
  addBubble("assistant", greeting());
  renderStarters();
  $("input").focus({ preventScroll: true });
}

function renderStarters() {
  const box = $("starters");
  box.hidden = messages.length > 0;
  if (box.hidden) return;
  box.replaceChildren(...STARTERS.map((label, i) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = label;
    b.style.animationDelay = `${0.15 + i * 0.06}s`;
    b.onclick = () => send(label);
    return b;
  }));
}

// ——— Envoi ———
async function send(text) {
  text = text.trim();
  if (!text || busy) return;
  busy = true;
  $("send").disabled = true;
  $("starters").hidden = true;

  messages.push({ role: "user", content: text });
  save();
  addBubble("user", text);

  const bubble = addBubble("assistant", "");
  bubble.innerHTML = `<span class="breath" aria-label="Confie écrit"><i></i><i></i><i></i></span>`;

  let reply = "";
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages, name: profile.name, mode: profile.mode }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.error || "");
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      reply += decoder.decode(value, { stream: true });
      const nearBottom = $("messages").scrollHeight - $("messages").scrollTop - $("messages").clientHeight < 80;
      renderAi(bubble, reply);
      if (nearBottom) scrollDown();
    }
    if (!reply.trim()) throw new Error("");
    messages.push({ role: "assistant", content: reply });
    save();
  } catch (err) {
    if (reply.trim()) {
      // Réponse coupée en route : on garde ce qui est arrivé.
      messages.push({ role: "assistant", content: reply });
    } else {
      bubble.remove();
      messages.pop(); // le message n'est pas parti : on le rend à la personne
      $("input").value = text;
      resize();
    }
    save();
    addBubble("note", err.message || "Je n'arrive pas à te répondre pour le moment. Vérifie ta connexion et réessaie.");
  } finally {
    busy = false;
    updateSend();
  }
}

// ——— Saisie ———
function resize() {
  const t = $("input");
  t.style.height = "auto";
  t.style.height = Math.min(t.scrollHeight, 160) + "px";
}
function updateSend() {
  $("send").disabled = busy || !$("input").value.trim();
}

$("input").addEventListener("input", () => { resize(); updateSend(); });
$("input").addEventListener("keydown", (e) => {
  const touch = matchMedia("(pointer: coarse)").matches; // sur mobile, Entrée = retour à la ligne
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing && !touch) {
    e.preventDefault();
    $("composer").requestSubmit();
  }
});
$("composer").addEventListener("submit", (e) => {
  e.preventDefault();
  const text = $("input").value;
  if (!text.trim() || busy) return;
  $("input").value = "";
  resize();
  send(text);
});

// ——— Accueil ———
$("welcome-form").addEventListener("submit", (e) => {
  e.preventDefault();
  profile = {
    name: $("name-input").value.trim(),
    mode: document.querySelector('input[name="mode"]:checked').value,
    memory: $("memory-input").checked,
  };
  save();
  showChat();
});

// ——— Réglages ———
$("settings-btn").onclick = () => {
  $("set-name").value = profile.name;
  document.querySelector(`input[name="set-mode"][value="${profile.mode}"]`).checked = true;
  $("set-memory").checked = profile.memory;
  $("settings").showModal();
};
$("settings").addEventListener("close", () => {
  if (!profile) return;
  profile.name = $("set-name").value.trim();
  profile.mode = document.querySelector('input[name="set-mode"]:checked').value;
  profile.memory = $("set-memory").checked;
  save();
});
$("erase").onclick = () => {
  if (!confirm("Effacer toute la conversation et tes réglages de cet appareil ?")) return;
  profile = null;
  messages = [];
  save();
  $("settings").close();
  $("chat").hidden = true;
  $("welcome-form").reset();
  $("welcome").hidden = false;
};

$("help-btn").onclick = () => $("help").showModal();
for (const d of document.querySelectorAll("dialog")) {
  d.addEventListener("click", (e) => { if (e.target === d) d.close(); }); // clic à côté = fermer
}

// ——— Démarrage ———
load();
if (profile) showChat();
else $("welcome").hidden = false;
