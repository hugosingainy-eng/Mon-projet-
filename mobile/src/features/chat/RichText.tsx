import React from 'react';
import { Text, View } from 'react-native';

import { fonts, space, type, useColors } from '@/theme';

// Rendu léger : paragraphes, listes, gras et italique. Suffisant pour une conversation.
function inline(text: string, key: string) {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*\s][^*]*\*)/g).filter(Boolean);
  return parts.map((p, i) => {
    if (p.startsWith('**')) return <Text key={`${key}-${i}`} style={{ fontFamily: fonts.sansBold }}>{p.slice(2, -2)}</Text>;
    if (p.startsWith('*')) return <Text key={`${key}-${i}`} style={{ fontStyle: 'italic' }}>{p.slice(1, -1)}</Text>;
    return p;
  });
}

export function RichText({ text, color }: { text: string; color?: string }) {
  const c = useColors();
  const style = [type.body, { color: color ?? c.text }];
  const blocks = text.trim().split(/\n{2,}/);
  return (
    <View style={{ gap: space.md }}>
      {blocks.map((block, b) => {
        const lines = block.split('\n');
        const isList = lines.every((l) => /^\s*([-•*]|\d+[.)])\s+/.test(l));
        if (isList) {
          return (
            <View key={b} style={{ gap: space.sm }}>
              {lines.map((l, i) => {
                const m = l.match(/^\s*([-•*]|\d+[.)])\s+(.*)$/)!;
                const marker = /\d/.test(m[1]) ? m[1].replace(')', '.') : '•';
                return (
                  <View key={i} style={{ flexDirection: 'row', gap: space.sm }}>
                    <Text style={[style, { color: c.sage, minWidth: 16 }]}>{marker}</Text>
                    <Text style={[style, { flex: 1 }]}>{inline(m[2], `${b}-${i}`)}</Text>
                  </View>
                );
              })}
            </View>
          );
        }
        return <Text key={b} style={style}>{inline(block.replace(/^#+\s*/gm, ''), String(b))}</Text>;
      })}
    </View>
  );
}
