import React from 'react';
import { Linking, Platform, Pressable, type PressableProps, type StyleProp, type ViewStyle } from 'react-native';

/**
 * Lien vers un site extérieur. Sur le web, c'est un vrai lien (<a target="_blank">) : les ouvertures
 * par script sont bloquées dans certains environnements, alors qu'un vrai lien fonctionne partout.
 */
export function ExternalLink({ url, label, style, children, testID }: { url: string; label: string; style?: StyleProp<ViewStyle>; children: React.ReactNode; testID?: string }) {
  const safe = /^https:\/\//.test(url) ? url : 'https://www.youtube.com';
  const web = Platform.OS === 'web' ? ({ href: safe, hrefAttrs: { target: '_blank', rel: 'noopener noreferrer' } } as unknown as PressableProps) : {};
  return (
    <Pressable
      testID={testID}
      accessibilityRole="link"
      accessibilityLabel={label}
      onPress={Platform.OS === 'web' ? undefined : () => { Linking.openURL(safe).catch(() => {}); }}
      style={({ pressed }) => [style, pressed && { opacity: 0.7 }]}
      {...web}>
      {children}
    </Pressable>
  );
}

/** Propriétés à étaler sur un Pressable existant pour en faire un lien extérieur sûr. */
export function linkProps(url: string): PressableProps {
  const safe = /^https:\/\//.test(url) ? url : 'https://www.youtube.com';
  if (Platform.OS === 'web') return { href: safe, hrefAttrs: { target: '_blank', rel: 'noopener noreferrer' } } as unknown as PressableProps;
  return { onPress: () => { Linking.openURL(safe).catch(() => {}); } };
}
