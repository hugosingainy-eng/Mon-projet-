import { Tabs } from 'expo-router/js-tabs';
import { Pressable, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { MAX_WIDTH, space, type, useColors } from '@/theme';
import { Icon, type IconName } from '@/ui';

const TABS: { name: string; label: string; icon: IconName }[] = [
  { name: 'index', label: 'Accueil', icon: 'home' },
  { name: 'journal', label: 'Journal', icon: 'journal' },
  { name: 'exercices', label: 'Exercices', icon: 'breathe' },
  { name: 'progres', label: 'Progrès', icon: 'progress' },
  { name: 'profil', label: 'Profil', icon: 'profile' },
];

export default function TabsLayout() {
  const c = useColors();
  const insets = useSafeAreaInsets();
  return (
    <Tabs
      screenOptions={{ headerShown: false, sceneStyle: { backgroundColor: c.bg } }}
      tabBar={({ state, navigateToTab }) => (
        <View style={{ backgroundColor: c.bg, borderTopWidth: 1, borderTopColor: c.line, paddingBottom: Math.max(insets.bottom, space.sm) }}>
          <View style={{ flexDirection: 'row', width: '100%', maxWidth: MAX_WIDTH, alignSelf: 'center' }} accessibilityRole="tablist">
            {state.routes.map((route, i) => {
              const tab = TABS.find((t) => t.name === route.name);
              if (!tab) return null;
              const focused = state.index === i;
              return (
                <Pressable
                  key={route.key}
                  accessibilityRole="tab"
                  accessibilityLabel={tab.label}
                  accessibilityState={{ selected: focused }}
                  onPress={() => navigateToTab(route.key)}
                  style={{ flex: 1, alignItems: 'center', paddingTop: space.sm, paddingBottom: space.xs, gap: 2 }}>
                  <View style={{ width: 52, height: 30, borderRadius: 15, alignItems: 'center', justifyContent: 'center', backgroundColor: focused ? c.surfaceAlt : 'transparent' }}>
                    <Icon name={tab.icon} size={22} color={focused ? c.primary : c.textMuted} strokeWidth={focused ? 1.9 : 1.5} />
                  </View>
                  <Text style={[type.caption, { color: focused ? c.primary : c.textMuted }]}>{tab.label}</Text>
                </Pressable>
              );
            })}
          </View>
        </View>
      )}>
      {TABS.map((t) => <Tabs.Screen key={t.name} name={t.name} />)}
    </Tabs>
  );
}
