import { Redirect } from 'expo-router';

// Adresse inconnue (lien ancien, aperçu ouvert sous un autre chemin) : on revient à l'accueil.
export default function NotFound() {
  return <Redirect href="/" />;
}
