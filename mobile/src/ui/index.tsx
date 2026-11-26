import * as Haptics from 'expo-haptics';
import { router } from 'expo-router';
import React from 'react';
import {
  Platform, Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View,
  type PressableProps, type StyleProp, type TextInputProps, type TextProps, type TextStyle, type ViewStyle,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { HIT, MAX_WIDTH, radius, shadow, space, type, useColors, type Colors, type TypeVariant } from '@/theme';

import { Icon, type IconName } from './Icon';

export { Icon, type IconName };

const tap = () => { if (Platform.OS !== 'web') Haptics.selectionAsync().catch(() => {}); };

// ——— Texte ———
type TxtProps = TextProps & { variant?: TypeVariant; color?: keyof Colors; center?: boolean };
export function Txt({ variant = 'body', color = 'text', center, style, ...rest }: TxtProps) {
  const c = useColors();
  return <Text {...rest} style={[type[variant], { color: c[color] }, center && { textAlign: 'center' }, style]} />;
}

// ——— Écran ———
type ScreenProps = {
  children: React.ReactNode;
  scroll?: boolean;
  padded?: boolean;
  edges?: ('top' | 'bottom')[];
  style?: StyleProp<ViewStyle>;
  footer?: React.ReactNode;
  testID?: string;
};
export function Screen({ children, scroll = true, padded = true, edges = ['top', 'bottom'], style, footer, testID }: ScreenProps) {
  const c = useColors();
  const insets = useSafeAreaInsets();
  const pad = {
    paddingTop: edges.includes('top') ? insets.top : 0,
    paddingBottom: edges.includes('bottom') && !footer ? insets.bottom : 0,
  };
  const inner = [styles.inner, padded && { paddingHorizontal: space.xl }, style];
  return (
    <View style={[styles.fill, { backgroundColor: c.bg }, pad]} testID={testID}>
      {scroll ? (
        <ScrollView contentContainerStyle={[inner, { paddingBottom: space.xxxl }]} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
          {children}
        </ScrollView>
      ) : (
        <View style={[styles.fill, inner]}>{children}</View>
      )}
      {footer ? <View style={[styles.inner, { paddingHorizontal: space.xl, paddingTop: space.md, paddingBottom: Math.max(insets.bottom, space.lg) }]}>{footer}</View> : null}
    </View>
  );
}

// ——— En-tête de page secondaire ———
export function Header({ title, right, onBack }: { title?: string; right?: React.ReactNode; onBack?: () => void }) {
  return (
    <View style={styles.header}>
      <IconButton name="back" label="Retour" onPress={onBack ?? (() => (router.canGoBack() ? router.back() : router.replace('/')))} />
      {title ? <Txt variant="smallMedium" color="textSoft" numberOfLines={1} style={styles.headerTitle}>{title}</Txt> : <View style={styles.fill} />}
      <View style={styles.headerRight}>{right}</View>
    </View>
  );
}

// ——— Boutons ———
type ButtonProps = Omit<PressableProps, 'style'> & {
  label: string;
  kind?: 'primary' | 'soft' | 'ghost' | 'quiet';
  icon?: IconName;
  style?: StyleProp<ViewStyle>;
  small?: boolean;
};
export function Button({ label, kind = 'primary', icon, style, small, disabled, onPress, ...rest }: ButtonProps) {
  const c = useColors();
  const bg = { primary: c.primary, soft: c.surfaceAlt, ghost: 'transparent', quiet: 'transparent' }[kind];
  const fg = kind === 'primary' ? c.onPrimary : kind === 'quiet' ? c.textSoft : c.text;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: !!disabled }}
      disabled={disabled}
      onPress={(e) => { tap(); onPress?.(e); }}
      style={({ pressed }) => [
        styles.button,
        small && styles.buttonSmall,
        { backgroundColor: bg, opacity: disabled ? 0.4 : pressed ? 0.85 : 1 },
        kind === 'ghost' && { borderWidth: 1, borderColor: c.line },
        style,
      ]}
      {...rest}>
      {icon ? <Icon name={icon} size={18} color={fg} /> : null}
      <Text style={[small ? type.smallMedium : type.bodyMedium, { color: fg }]}>{label}</Text>
    </Pressable>
  );
}

export function IconButton({ name, label, onPress, color, filled, size = 22, testID }: { name: IconName; label: string; onPress?: () => void; color?: string; filled?: boolean; size?: number; testID?: string }) {
  const c = useColors();
  return (
    <Pressable
      testID={testID}
      accessibilityRole="button"
      accessibilityLabel={label}
      hitSlop={6}
      onPress={() => { tap(); onPress?.(); }}
      style={({ pressed }) => [styles.iconButton, filled && { backgroundColor: c.surface }, pressed && { opacity: 0.6 }]}>
      <Icon name={name} size={size} color={color ?? c.textSoft} />
    </Pressable>
  );
}

// ——— Puce de choix ———
export function Chip({ label, selected, onPress, style }: { label: string; selected?: boolean; onPress?: () => void; style?: StyleProp<ViewStyle> }) {
  const c = useColors();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected: !!selected }}
      accessibilityLabel={label}
      onPress={() => { tap(); onPress?.(); }}
      style={({ pressed }) => [
        styles.chip,
        { borderColor: selected ? c.sage : c.line, backgroundColor: selected ? c.surfaceAlt : 'transparent', opacity: pressed ? 0.7 : 1 },
        style,
      ]}>
      <Text style={[type.small, { color: selected ? c.text : c.textSoft }]}>{label}</Text>
    </Pressable>
  );
}

export function ChipGroup({ children, style }: { children: React.ReactNode; style?: StyleProp<ViewStyle> }) {
  return <View style={[styles.chipGroup, style]}>{children}</View>;
}

// ——— Carte et ligne ———
export function Card({ children, style, onPress, flat, label }: { children: React.ReactNode; style?: StyleProp<ViewStyle>; onPress?: () => void; flat?: boolean; label?: string }) {
  const c = useColors();
  const base = [styles.card, { backgroundColor: c.surface }, !flat && shadow, style];
  if (!onPress) return <View style={base}>{children}</View>;
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={() => { tap(); onPress(); }} style={({ pressed }) => [base, pressed && { opacity: 0.85 }]}>
      {children}
    </Pressable>
  );
}

export function Row({ title, hint, icon, right, onPress, danger, testID }: { title: string; hint?: string; icon?: IconName; right?: React.ReactNode; onPress?: () => void; danger?: boolean; testID?: string }) {
  const c = useColors();
  const body = (
    <View style={styles.row}>
      {icon ? <Icon name={icon} size={20} color={danger ? c.warn : c.textSoft} /> : null}
      <View style={styles.fill}>
        <Txt variant="bodyMedium" style={danger ? { color: c.warn } : undefined}>{title}</Txt>
        {hint ? <Txt variant="small" color="textMuted">{hint}</Txt> : null}
      </View>
      {right ?? (onPress ? <Icon name="chevron" size={18} color={c.textMuted} /> : null)}
    </View>
  );
  if (!onPress) return body;
  return (
    <Pressable testID={testID} accessibilityRole="button" accessibilityLabel={title} onPress={() => { tap(); onPress(); }} style={({ pressed }) => pressed && { opacity: 0.6 }}>
      {body}
    </Pressable>
  );
}

export function Divider() {
  const c = useColors();
  return <View style={{ height: StyleSheet.hairlineWidth, backgroundColor: c.line }} />;
}

export function Toggle({ value, onChange, label }: { value: boolean; onChange: (v: boolean) => void; label: string }) {
  const c = useColors();
  return (
    <Switch
      accessibilityLabel={label}
      value={value}
      onValueChange={(v) => { tap(); onChange(v); }}
      trackColor={{ false: c.line, true: c.sage }}
      thumbColor={c.surface}
      {...(Platform.OS === 'web' ? ({ activeThumbColor: c.surface } as object) : {})}
    />
  );
}

// ——— Champ de saisie ———
export function Field({ label, style, multiline, ...rest }: TextInputProps & { label?: string }) {
  const c = useColors();
  const [focused, setFocused] = React.useState(false);
  return (
    <View style={{ gap: space.sm }}>
      {label ? <Txt variant="small" color="textSoft">{label}</Txt> : null}
      <TextInput
        accessibilityLabel={label ?? rest.placeholder}
        placeholderTextColor={c.textMuted}
        multiline={multiline}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        style={[
          type.body,
          styles.field,
          { color: c.text, backgroundColor: c.surface, borderColor: focused ? c.sage : c.line },
          multiline && { minHeight: 140, textAlignVertical: 'top', paddingTop: space.lg },
          Platform.OS === 'web' && ({ outlineStyle: 'none' } as unknown as TextStyle),
          style,
        ]}
        {...rest}
      />
    </View>
  );
}

// ——— Échelle de 1 à 5 ———
export function Scale({ value, onChange, label, low, high }: { value: number; onChange: (v: number) => void; label: string; low: string; high: string }) {
  const c = useColors();
  return (
    <View style={{ gap: space.sm }}>
      <Txt variant="smallMedium">{label}</Txt>
      <View style={styles.scale} accessibilityRole="adjustable" accessibilityLabel={label} accessibilityValue={{ min: 1, max: 5, now: value }}>
        {[1, 2, 3, 4, 5].map((n) => (
          <Pressable key={n} accessibilityLabel={`${label} ${n} sur 5`} onPress={() => { tap(); onChange(n); }} style={styles.scaleHit}>
            <View style={[styles.scaleDot, { backgroundColor: n <= value ? c.sage : c.line, transform: [{ scale: n === value ? 1.25 : 1 }] }]} />
          </Pressable>
        ))}
      </View>
      <View style={styles.scaleLabels}>
        <Txt variant="caption" color="textMuted">{low}</Txt>
        <Txt variant="caption" color="textMuted">{high}</Txt>
      </View>
    </View>
  );
}

export function SectionTitle({ children, action, onAction }: { children: string; action?: string; onAction?: () => void }) {
  return (
    <View style={styles.sectionTitle}>
      <Txt variant="heading">{children}</Txt>
      {action ? <Pressable accessibilityRole="button" accessibilityLabel={action} hitSlop={10} onPress={onAction}><Txt variant="small" color="textSoft">{action}</Txt></Pressable> : null}
    </View>
  );
}

export function Empty({ title, text }: { title: string; text: string }) {
  return (
    <View style={styles.empty}>
      <Icon name="leaf" size={30} />
      <Txt variant="heading" center>{title}</Txt>
      <Txt variant="small" color="textSoft" center style={{ maxWidth: 280 }}>{text}</Txt>
    </View>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
  inner: { width: '100%', maxWidth: MAX_WIDTH, alignSelf: 'center' },
  header: { flexDirection: 'row', alignItems: 'center', height: 52, marginHorizontal: -space.sm, gap: space.xs },
  headerTitle: { flex: 1, textAlign: 'center' },
  headerRight: { minWidth: HIT, alignItems: 'flex-end', flexDirection: 'row', justifyContent: 'flex-end' },
  button: { minHeight: 54, paddingHorizontal: space.xl, borderRadius: radius.pill, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: space.sm },
  buttonSmall: { minHeight: HIT, paddingHorizontal: space.lg },
  iconButton: { width: HIT, height: HIT, borderRadius: HIT / 2, alignItems: 'center', justifyContent: 'center' },
  chip: { minHeight: 40, paddingHorizontal: space.lg, borderRadius: radius.pill, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  chipGroup: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm },
  card: { borderRadius: radius.lg, padding: space.xl },
  row: { flexDirection: 'row', alignItems: 'center', gap: space.lg, minHeight: 60, paddingVertical: space.md },
  field: { borderWidth: 1, borderRadius: radius.md, paddingHorizontal: space.lg, minHeight: 54 },
  scale: { flexDirection: 'row', justifyContent: 'space-between' },
  scaleHit: { width: HIT, height: HIT, alignItems: 'center', justifyContent: 'center' },
  scaleDot: { width: 18, height: 18, borderRadius: 9 },
  scaleLabels: { flexDirection: 'row', justifyContent: 'space-between' },
  sectionTitle: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between', marginTop: space.xxl, marginBottom: space.md },
  empty: { alignItems: 'center', gap: space.md, paddingVertical: space.xxxl },
});
