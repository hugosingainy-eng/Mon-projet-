import { useEffect, useState } from 'react';

import { supabase } from '@/lib/supabase';

/** E-mail du compte connecté, ou null. Reste à null si Supabase n'est pas configuré. */
export function useAccountEmail(): string | null {
  const [email, setEmail] = useState<string | null>(null);
  useEffect(() => {
    if (!supabase) return;
    let alive = true;
    supabase.auth.getSession().then(({ data }) => { if (alive) setEmail(data.session?.user.email ?? null); }).catch(() => {});
    const { data } = supabase.auth.onAuthStateChange((_event, session) => setEmail(session?.user.email ?? null));
    return () => { alive = false; data.subscription.unsubscribe(); };
  }, []);
  return email;
}

/** Déconnexion sur cet appareil uniquement. */
export async function signOutLocally() {
  try { await supabase?.auth.signOut({ scope: 'local' }); } catch { /* la session locale est déjà absente */ }
}
