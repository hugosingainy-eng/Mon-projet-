import { router } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';

import { hasSupabase } from '@/lib/config';
import { supabase } from '@/lib/supabase';
import { space } from '@/theme';
import { Button, Field, Header, Screen, Txt } from '@/ui';

const goBack = () => (router.canGoBack() ? router.back() : router.replace('/'));

// Messages calmes, en français, à partir des erreurs renvoyées par Supabase.
function friendly(error: { message?: string; code?: string; status?: number }): string {
  const m = `${error.code ?? ''} ${error.message ?? ''}`.toLowerCase();
  if (m.includes('invalid login') || m.includes('invalid_credentials')) return 'L\'adresse e-mail ou le mot de passe ne correspond pas.';
  if (m.includes('not confirmed')) return 'Ton adresse n\'est pas encore confirmée. Regarde dans ta boîte mail.';
  if (m.includes('already registered') || m.includes('user_already_exists')) return 'Un compte existe déjà avec cette adresse. Essaie de te connecter.';
  if (m.includes('password')) return 'Ce mot de passe n\'est pas accepté. Choisis-en un plus long ou moins courant.';
  if (m.includes('email')) return 'Cette adresse e-mail ne semble pas valide.';
  if (error.status === 429 || m.includes('rate limit')) return 'Trop d\'essais d\'affilée. Attends un peu avant de réessayer.';
  if (m.includes('network') || m.includes('fetch')) return 'Pas de connexion pour le moment. Réessaie quand le réseau revient.';
  return 'Ça n\'a pas fonctionné cette fois. Réessaie dans un instant.';
}

export default function SignIn() {
  const [creating, setCreating] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  if (!hasSupabase || !supabase) {
    return (
      <Screen testID="signin">
        <Header title="Compte" />
        <View style={{ gap: space.md, marginTop: space.xxl }}>
          <Txt variant="title">Les comptes arrivent bientôt</Txt>
          <Txt color="textSoft">
            La connexion n'est pas encore configurée dans cette version. En attendant, tu peux utiliser Confie sans compte : tout reste sur ton téléphone.
          </Txt>
        </View>
        <Button label="Retour" kind="soft" onPress={goBack} style={{ marginTop: space.xxl }} />
      </Screen>
    );
  }
  const auth = supabase.auth;

  const submit = async () => {
    const mail = email.trim();
    setError(null);
    setInfo(null);
    if (!/^\S+@\S+\.\S+$/.test(mail)) return setError('Vérifie ton adresse e-mail.');
    if (password.length < 8 && creating) return setError('Choisis un mot de passe d\'au moins 8 caractères.');
    if (!password) return setError('Saisis ton mot de passe.');
    setBusy(true);
    try {
      if (creating) {
        const { data, error: e } = await auth.signUp({ email: mail, password });
        if (e) setError(friendly(e));
        else if (data.session) goBack();
        else setInfo('Ton compte est créé. Ouvre l\'e-mail que nous venons de t\'envoyer pour confirmer ton adresse, puis connecte-toi.');
      } else {
        const { error: e } = await auth.signInWithPassword({ email: mail, password });
        if (e) setError(friendly(e));
        else goBack();
      }
    } catch (e) {
      setError(friendly(e as Error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen testID="signin">
      <Header title="Compte" />
      <View style={{ gap: space.md, marginTop: space.lg }}>
        <Txt variant="title">{creating ? 'Créer un compte' : 'Te connecter'}</Txt>
        <Txt color="textSoft">
          Le compte est facultatif. Pour l'instant, il sert seulement à t'identifier : tes conversations et ton journal restent sur ton téléphone.
        </Txt>
      </View>

      <View style={{ gap: space.lg, marginTop: space.xl }}>
        <Field label="Adresse e-mail" value={email} onChangeText={setEmail} keyboardType="email-address" autoCapitalize="none" autoCorrect={false} autoComplete="email" textContentType="emailAddress" placeholder="toi@exemple.fr" testID="signin-email" />
        <Field label="Mot de passe" value={password} onChangeText={setPassword} secureTextEntry autoCapitalize="none" autoCorrect={false} autoComplete={creating ? 'new-password' : 'current-password'} textContentType={creating ? 'newPassword' : 'password'} placeholder={creating ? '8 caractères au minimum' : undefined} onSubmitEditing={submit} returnKeyType="go" testID="signin-password" />
        {error ? <Txt variant="small" color="warn" accessibilityLiveRegion="polite">{error}</Txt> : null}
        {info ? <Txt variant="small" color="textSoft" accessibilityLiveRegion="polite">{info}</Txt> : null}
      </View>

      <View style={{ gap: space.xs, marginTop: space.xl }}>
        <Button label={busy ? 'Un instant…' : creating ? 'Créer mon compte' : 'Me connecter'} disabled={busy} onPress={submit} testID="signin-submit" />
        <Button label={creating ? 'J\'ai déjà un compte' : 'Créer un compte'} kind="quiet" small disabled={busy} onPress={() => { setCreating(!creating); setError(null); setInfo(null); }} />
      </View>
    </Screen>
  );
}
