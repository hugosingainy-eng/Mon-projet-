import { Alert, Platform } from 'react-native';

/** Demande de confirmation : Alert sur iOS/Android, boîte de dialogue du navigateur sur le web. */
export function confirmAction({ title, message, confirmLabel, onConfirm }: { title: string; message: string; confirmLabel: string; onConfirm: () => void }) {
  if (Platform.OS === 'web') {
    if (globalThis.confirm?.(`${title}\n\n${message}`)) onConfirm();
    return;
  }
  Alert.alert(title, message, [{ text: 'Annuler', style: 'cancel' }, { text: confirmLabel, style: 'destructive', onPress: onConfirm }]);
}
