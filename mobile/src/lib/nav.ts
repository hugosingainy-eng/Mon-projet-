import { router } from 'expo-router';

/**
 * Revenir à l'accueil sans empiler un deuxième accueil par-dessus le premier
 * (sinon le bouton retour ramène sur des écrans fantômes).
 */
export function goHome() {
  try {
    router.dismissTo('/(tabs)');
  } catch {
    router.replace('/(tabs)');
  }
}

/** Repartir de zéro (après suppression des données) : on vide la pile d'écrans. */
export function restart() {
  try { if (router.canDismiss()) router.dismissAll(); } catch { /* rien à fermer */ }
  router.replace('/bienvenue');
}

/** Fin de l'onboarding : l'accueil devient le seul écran de la pile. */
export function enterApp() {
  try { if (router.canDismiss()) router.dismissAll(); } catch { /* rien à fermer */ }
  router.replace('/(tabs)');
}
