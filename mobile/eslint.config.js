// https://docs.expo.dev/guides/using-eslint/
const { defineConfig } = require('eslint/config');
const expoConfig = require('eslint-config-expo/flat');

module.exports = defineConfig([
  expoConfig,
  {
    ignores: ['dist/*'],
  },
  {
    // L'interface est en français : les apostrophes dans le texte sont normales.
    rules: { 'react/no-unescaped-entities': 'off' },
  },
]);
