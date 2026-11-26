// Configuration Expo. La base est dans app.json ; l'aperçu en ligne (un seul fichier JavaScript)
// se construit avec CONFIE_PREVIEW=1.
module.exports = ({ config }) => {
  if (!process.env.CONFIE_PREVIEW) return config;
  return {
    ...config,
    plugins: config.plugins.map((p) => (p === 'expo-router' ? ['expo-router', { asyncRoutes: false }] : p)),
  };
};
