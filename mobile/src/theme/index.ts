import { Platform, useColorScheme } from 'react-native';

import { useSettings } from '@/store/settings';

// Palette imposée par la direction artistique. Le vert sauge est la couleur centrale.
export const palette = {
  sageLight: '#E7EDE4',
  sage: '#A8B9A1',
  forest: '#30483C',
  cream: '#F6F3EC',
  softWhite: '#FCFBF8',
  grey: '#8C918B',
  accent: '#C6A77B',
} as const;

const light = {
  bg: palette.cream,
  surface: palette.softWhite,
  surfaceAlt: palette.sageLight,
  line: '#E6E2D7',
  text: palette.forest,
  textSoft: '#5E6B62',
  textMuted: palette.grey,
  primary: palette.forest,
  onPrimary: palette.softWhite,
  sage: palette.sage,
  sageLight: palette.sageLight,
  accent: palette.accent,
  // Le rouge est évité : les alertes utilisent un brun terre, lisible sans être agressif.
  warn: '#9A6A4F',
  overlay: 'rgba(48,72,60,0.28)',
};

const dark: Colors = {
  bg: '#171D19',
  surface: '#1F2722',
  surfaceAlt: '#27322B',
  line: '#2E3A32',
  text: '#E9EEE6',
  textSoft: '#B5C0B4',
  textMuted: '#8C968C',
  primary: palette.sage,
  onPrimary: '#16201A',
  sage: palette.sage,
  sageLight: '#2B3830',
  accent: palette.accent,
  warn: '#D2A283',
  overlay: 'rgba(0,0,0,0.5)',
};

export type Colors = Record<keyof typeof light, string>;

export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32, xxxl: 48 } as const;
export const radius = { sm: 10, md: 16, lg: 22, pill: 999 } as const;

export const fonts = {
  serif: 'Fraunces_400Regular',
  serifMedium: 'Fraunces_500Medium',
  sans: 'DMSans_400Regular',
  sansMedium: 'DMSans_500Medium',
} as const;

export const type = {
  display: { fontFamily: fonts.serif, fontSize: 34, lineHeight: 42, letterSpacing: -0.3 },
  title: { fontFamily: fonts.serif, fontSize: 26, lineHeight: 33, letterSpacing: -0.2 },
  heading: { fontFamily: fonts.serifMedium, fontSize: 20, lineHeight: 27 },
  body: { fontFamily: fonts.sans, fontSize: 16.5, lineHeight: 26 },
  bodyMedium: { fontFamily: fonts.sansMedium, fontSize: 16.5, lineHeight: 26 },
  small: { fontFamily: fonts.sans, fontSize: 14.5, lineHeight: 21 },
  smallMedium: { fontFamily: fonts.sansMedium, fontSize: 14.5, lineHeight: 21 },
  caption: { fontFamily: fonts.sans, fontSize: 12.5, lineHeight: 17, letterSpacing: 0.2 },
} as const;

export type TypeVariant = keyof typeof type;

// Ombre unique et discrète, pour les rares éléments qui flottent.
export const shadow = Platform.select({
  web: { boxShadow: '0 1px 2px rgba(48,72,60,0.04), 0 10px 30px rgba(48,72,60,0.07)' } as object,
  default: {
    shadowColor: '#30483C',
    shadowOpacity: 0.08,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 8 },
    elevation: 2,
  },
})!;

export const HIT = 44; // taille minimale d'une zone tactile
export const MAX_WIDTH = 560;

export function useColors(): Colors {
  const system = useColorScheme();
  const pref = useSettings((s) => s.appearance);
  const scheme = pref === 'system' ? system : pref;
  return scheme === 'dark' ? dark : light;
}

export function useIsDark(): boolean {
  const system = useColorScheme();
  const pref = useSettings((s) => s.appearance);
  return (pref === 'system' ? system : pref) === 'dark';
}
