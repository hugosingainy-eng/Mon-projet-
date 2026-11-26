import assert from "node:assert/strict";
import { test } from "node:test";

import { parseReply, splitSentences, speakable } from "../mobile/src/lib/tags.ts";

test("les balises sont retirées du texte et interprétées", () => {
  const p = parseReply("Je t'entends.\n\n[[retenir: Aime la randonnée]]\n[[video: gérer l'anxiété]]\n[[exercice: coherence]]\n[[urgence]]");
  assert.equal(p.text, "Je t'entends.");
  assert.deepEqual(p.remember, ["Aime la randonnée"]);
  assert.deepEqual(p.videos, ["gérer l'anxiété"]);
  assert.deepEqual(p.exercises, ["coherence"]);
  assert.equal(p.crisis, true);
});

test("oubli et désactivation de la mémoire", () => {
  const p = parseReply("C'est noté.\n[[oublier: ab12cd]]\n[[oublier: tout]]\n[[memoire: off]]");
  assert.deepEqual(p.forget, ["ab12cd", "tout"]);
  assert.equal(p.memoryOff, true);
});

test("une balise en cours d'écriture n'apparaît jamais à l'écran", () => {
  assert.equal(parseReply("Bonjour [[vid").text, "Bonjour");
  assert.equal(parseReply("Bonjour [").text, "Bonjour");
  assert.equal(parseReply("Bonjour [[video: sommeil").text, "Bonjour");
});

test("un texte sans balise reste intact", () => {
  const p = parseReply("Simple réponse, avec [un crochet] dedans.");
  assert.equal(p.text, "Simple réponse, avec [un crochet] dedans.");
  assert.equal(p.crisis, false);
});

test("découpage en phrases pour la lecture à voix haute", () => {
  const { ready, rest } = splitSentences("Bonjour Léa. Comment tu te sens ? Je réfl");
  assert.deepEqual(ready, ["Bonjour Léa.", "Comment tu te sens ?"]);
  assert.equal(rest, "Je réfl");
  assert.equal(speakable("**Respire** doucement"), "Respire doucement");
});
