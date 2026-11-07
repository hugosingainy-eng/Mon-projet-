// Accès à Claude pour tous les agents.
// - Sorties JSON garanties par un schéma (structured outputs).
// - Streaming pour les longues réponses (génération de sites).
// - Repli automatique côté serveur si une requête est refusée (fallbacks "default").
import Anthropic from '@anthropic-ai/sdk';
import { config, demoMode } from './config.js';

let client = null;
function getClient() {
  if (!client) client = new Anthropic({ apiKey: config.anthropicKey });
  return client;
}

export function aiAvailable() {
  return !demoMode.ai;
}

/**
 * Appelle Claude et renvoie un objet JSON conforme à `schema`.
 * @param {object} p
 * @param {string} p.system     Rôle de l'agent
 * @param {string} p.prompt     Tâche
 * @param {object} p.schema     JSON Schema de la réponse attendue
 * @param {'low'|'medium'|'high'|'xhigh'|'max'} [p.effort]
 * @param {number} [p.maxTokens]
 */
export async function askJson({ system, prompt, schema, effort = 'medium', maxTokens = 32000 }) {
  const stream = getClient().beta.messages.stream({
    model: config.model,
    max_tokens: maxTokens,
    betas: ['server-side-fallback-2026-07-01'],
    fallbacks: 'default',
    system,
    output_config: {
      effort,
      format: { type: 'json_schema', schema },
    },
    messages: [{ role: 'user', content: prompt }],
  });

  const message = await stream.finalMessage();

  if (message.stop_reason === 'refusal') {
    const why = message.stop_details?.explanation || 'requête refusée par le modèle';
    throw new Error(`Refus du modèle : ${why}`);
  }
  if (message.stop_reason === 'max_tokens') {
    throw new Error('Réponse tronquée (max_tokens atteint).');
  }

  const text = message.content
    .filter((b) => b.type === 'text')
    .map((b) => b.text)
    .join('');
  try {
    return JSON.parse(text);
  } catch {
    throw new Error('Réponse JSON invalide du modèle.');
  }
}

/**
 * Recherche sur le web avec les outils serveur de Claude (web_search + web_fetch).
 * Renvoie le dernier objet JSON écrit par le modèle dans sa réponse finale.
 */
export async function askWeb({ system, prompt, maxSearches = 6, maxFetches = 6, effort = 'medium' }) {
  const tools = [
    { type: 'web_search_20260209', name: 'web_search', max_uses: maxSearches, user_location: { type: 'approximate', country: 'FR' } },
    { type: 'web_fetch_20260209', name: 'web_fetch', max_uses: maxFetches },
  ];
  const messages = [{ role: 'user', content: prompt }];
  let message;
  // pause_turn : le serveur a mis la recherche en pause, on la relance telle quelle (5 fois max).
  for (let i = 0; i < 6; i++) {
    message = await getClient().beta.messages.stream({
      model: config.model,
      max_tokens: 32000,
      betas: ['server-side-fallback-2026-07-01'],
      fallbacks: 'default',
      system,
      tools,
      output_config: { effort },
      messages,
    }).finalMessage();
    if (message.stop_reason !== 'pause_turn') break;
    messages.splice(1, messages.length - 1, { role: 'assistant', content: message.content });
  }
  if (message.stop_reason === 'refusal') throw new Error('Recherche refusée par le modèle.');

  const text = message.content.filter((b) => b.type === 'text').map((b) => b.text).join('\n');
  const blocks = text.match(/\{[\s\S]*\}/g) || [];
  for (const candidate of blocks.reverse()) {
    try { return JSON.parse(candidate); } catch { /* bloc suivant */ }
  }
  throw new Error('La recherche web n’a pas renvoyé de résultat exploitable.');
}

// Petit utilitaire : objet JSON Schema strict.
export function obj(properties, required = Object.keys(properties)) {
  return { type: 'object', properties, required, additionalProperties: false };
}
