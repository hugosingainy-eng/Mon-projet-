# Outils vidéo de l'équipe Mièdaou

Deux scripts qui font le travail mécanique du monteur. Les agents décident quoi faire ; ces scripts le réalisent.

| Script | Rôle |
|---|---|
| `preparer_video.py` | Vidéo brute → planche d'images, piste son, transcription française hors ligne avec temps, sous-titres `.srt` |
| `habiller_video.py` | Vidéo + feuille d'habillage JSON → vidéo 1080 x 1920 habillée style TikTok (titres animés, bandeaux, sous-titres karaoké, zooms, incrustations, carton final) |

## Installation (une fois)
```bash
# ffmpeg doit être installé (avec libass, présent dans les paquets courants)
pip install sherpa-onnx numpy pillow
```
Le premier lancement de la transcription télécharge le modèle Whisper small (environ 650 Mo) dans `~/.cache/miedaou/asr`.

## Utilisation
```bash
python3 outils/preparer_video.py ma-video.mp4 demo/ma-video/preparation
# ... les agents écrivent demo/ma-video/habillage.json ...
python3 outils/habiller_video.py demo/ma-video/habillage.json
```
Ou simplement, dans Claude Code : `/traiter-video ma-video.mp4`.

Exemple complet de feuille : `demo/video-offre-20-ans/habillage.json`.

## Limites connues
- Temps des mots estimés (répartis dans chaque passage parlé) : relire `transcription-corrigee.json`.
- La transcription se trompe sur les noms propres (« Mièdaou ») et quand la musique couvre la voix.
- Pas d'ajout de musique ni d'effets sonores : on garde la piste d'origine (normalisée à -14 LUFS).
- Une vidéo d'origine propre (fichier de la caméra, sans texte incrusté) donne un bien meilleur résultat qu'un enregistrement d'écran.

## Polices
`polices/` : Montserrat (instance ExtraBold) et Poppins, licence SIL Open Font License (`OFL-*.txt`), issues de github.com/google/fonts.
