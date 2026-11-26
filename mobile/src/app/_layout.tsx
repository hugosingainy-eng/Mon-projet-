import { DMSans_400Regular, DMSans_500Medium } from '@expo-google-fonts/dm-sans';
import { Fraunces_400Regular, Fraunces_500Medium } from '@expo-google-fonts/fraunces';
import { useFonts } from 'expo-font';
import { Stack } from 'expo-router/stack';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import { View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { useHydrated } from '@/lib/hydration';
import { useColors, useIsDark } from '@/theme';

SplashScreen.preventAutoHideAsync().catch(() => {});

export default function RootLayout() {
  const [fontsLoaded, fontError] = useFonts({ Fraunces_400Regular, Fraunces_500Medium, DMSans_400Regular, DMSans_500Medium });
  const hydrated = useHydrated();
  const c = useColors();
  const dark = useIsDark();
  const ready = (fontsLoaded || !!fontError) && hydrated;

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
    </SafeAreaProvider>
  );
}
