import { Modal, Pressable, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { MODES, type ModeId } from '@/content/modes';
import { MAX_WIDTH, radius, space, useColors } from '@/theme';
import { Icon, Row, Txt } from '@/ui';

export function Sheet({ visible, onClose, title, children }: { visible: boolean; onClose: () => void; title?: string; children: React.ReactNode }) {
  const c = useColors();
  const insets = useSafeAreaInsets();
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose} statusBarTranslucent>
      <Pressable accessibilityLabel="Fermer" onPress={onClose} style={{ flex: 1, backgroundColor: c.overlay, justifyContent: 'flex-end' }}>
        <Pressable
          onPress={(e) => e.stopPropagation()}
          style={{ backgroundColor: c.bg, borderTopLeftRadius: radius.lg + 6, borderTopRightRadius: radius.lg + 6, padding: space.xl, paddingBottom: Math.max(insets.bottom, space.xl), width: '100%', maxWidth: MAX_WIDTH, alignSelf: 'center', maxHeight: '86%' }}>
          <View style={{ alignSelf: 'center', width: 36, height: 4, borderRadius: 2, backgroundColor: c.line, marginBottom: space.lg }} />
          {title ? <Txt variant="heading" style={{ marginBottom: space.sm }}>{title}</Txt> : null}
          {children}
        </Pressable>
      </Pressable>
    </Modal>
  );
}

export function ModeSheet({ visible, value, onPick, onClose }: { visible: boolean; value: ModeId; onPick: (m: ModeId) => void; onClose: () => void }) {
  const c = useColors();
  return (
    <Sheet visible={visible} onClose={onClose} title="Comment veux-tu que je t'aide ?">
      {MODES.map((m) => (
        <Row key={m.id} title={m.label} hint={m.hint} onPress={() => { onPick(m.id); onClose(); }} right={value === m.id ? <Icon name="check" size={20} color={c.primary} /> : <View style={{ width: 20 }} />} />
      ))}
    </Sheet>
  );
}
