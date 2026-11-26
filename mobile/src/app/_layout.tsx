import { Figtree_400Regular } from '@expo-google-fonts/figtree/400Regular';
import { Figtree_500Medium } from '@expo-google-fonts/figtree/500Medium';
import { Figtree_600SemiBold } from '@expo-google-fonts/figtree/600SemiBold';
import { Fraunces_600SemiBold } from '@expo-google-fonts/fraunces/600SemiBold';
import { useFonts } from 'expo-font';
import { Stack } from 'expo-router/stack';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useState } from 'react';
import { View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { useHydrated } from '@/lib/hydration';
import { space, useColors, useIsDark } from '@/theme';
import { Button, Txt } from '@/ui';
import { ConfirmHost } from '@/ui/confirm';

SplashScreen.preventAutoHideAsync().catch(() => {});

export default function RootLayout() {
  const [fontsLoaded, fontError] = useFonts({ Fraunces_600SemiBold, Figtree_400Regular, Figtree_500Medium, Figtree_600SemiBold });
  const hydrated = useHydrated();
  const c = useColors();
  const dark = useIsDark();
  // Les polices ne doivent jamais bloquer l'ouverture : passé un court délai, on affiche l'app quand même.
  const [fontsLate, setFontsLate] = useState(false);
  useEffect(() => { const t = setTimeout(() => setFontsLate(true), 2000); return () => clearTimeout(t); }, []);
  const ready = (fontsLoaded || !!fontError || fontsLate) && hydrated;

  useEffect(() => { if (ready) SplashScreen.hideAsync().catch(() => {}); }, [ready]);
  if (!ready) return <View style={{ flex: 1, backgroundColor: c.bg }} />;

  return (
    <SafeAreaProvider>
      <StatusBar style={dark ? 'light' : 'dark'} />
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: c.bg }, animation: 'fade', animationDuration: 260 }}>
        <Stack.Screen name="aide" options={{ presentation: 'modal', animation: 'slide_from_bottom' }} />
        <Stack.Screen name="voix" options={{ presentation: 'fullScreenModal', animation: 'fade' }} />
        <Stack.Screen name="humeur" options={{ presentation: 'modal', animation: 'slide_from_bottom' }} />
      </Stack>
      <ConfirmHost />
    </SafeAreaProvider>
  );
}

// Si un écran plante, on l'explique et on propose de repartir, au lieu de laisser une page vide.
export function ErrorBoundary({ error, retry }: { error: Error; retry: () => void }) {
  const c = useColors();
  return (
    <View testID="crash" style={{ flex: 1, backgroundColor: c.bg, alignItems: 'center', justifyContent: 'center', padding: space.xl, gap: space.lg }}>
      <Txt variant="title" center>Quelque chose s'est mal passé</Txt>
      <Txt color="textSoft" center>Cet écran n'a pas pu s'afficher. Tes données ne sont pas perdues.</Txt>
      <Button label="Réessayer" onPress={retry} />
      <Txt variant="caption" color="textMuted" center selectable>{String(error?.message ?? error).slice(0, 200)}</Txt>
    </View>
  );
}
