import React from 'react';
import { Modal, Pressable, View } from 'react-native';
import { create } from 'zustand';

import { MAX_WIDTH, radius, space, useColors } from '@/theme';

import { Button, Txt } from './index';

// Confirmation intégrée à l'app. On n'utilise pas la boîte de dialogue du navigateur :
// certains environnements (aperçu en ligne, vues intégrées) la bloquent sans rien afficher.
type Request = { title: string; message: string; confirmLabel: string; onConfirm: () => void };
const useConfirm = create<{ request: Request | null; ask: (r: Request) => void; close: () => void }>((set) => ({
  request: null,
  ask: (request) => set({ request }),
  close: () => set({ request: null }),
}));

export function confirmAction(request: Request) {
  useConfirm.getState().ask(request);
}

/** À placer une fois à la racine de l'app. */
export function ConfirmHost() {
  const c = useColors();
  const { request, close } = useConfirm();
  return (
    <Modal visible={!!request} transparent animationType="fade" onRequestClose={close} statusBarTranslucent>
      <Pressable accessibilityLabel="Annuler" onPress={close} style={{ flex: 1, backgroundColor: c.overlay, alignItems: 'center', justifyContent: 'center', padding: space.xl }}>
        <Pressable testID="confirm" onPress={(e) => e.stopPropagation()} accessibilityRole="alert" style={{ width: '100%', maxWidth: MAX_WIDTH - 120, backgroundColor: c.bg, borderRadius: radius.lg, padding: space.xl, gap: space.md }}>
          <Txt variant="heading">{request?.title}</Txt>
          <Txt variant="small" color="textSoft">{request?.message}</Txt>
          <View style={{ gap: space.sm, marginTop: space.sm }}>
            <Button testID="confirm-yes" label={request?.confirmLabel ?? 'Confirmer'} onPress={() => { const run = request?.onConfirm; close(); run?.(); }} style={{ backgroundColor: c.warn }} />
            <Button testID="confirm-no" label="Annuler" kind="quiet" small onPress={close} />
          </View>
        </Pressable>
      </Pressable>
    </Modal>
  );
}
