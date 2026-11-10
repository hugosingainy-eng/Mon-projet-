"""Planche de démonstration : profil TikTok @miedaou avant / après, tel que les agents le géreraient.
Entrées : capture du profil (argument 1), maquette « après » produite au préalable (argument 2).
Sortie : demo/profil-tiktok-avant-apres.jpg"""
import sys
from PIL import Image, ImageDraw, ImageFont
SRC, APRES = sys.argv[1], sys.argv[2]
P = 'outils/polices/'
M = lambda s: ImageFont.truetype(P + 'Montserrat-ExtraBold.ttf', s)
PS = lambda s: ImageFont.truetype(P + 'Poppins-SemiBold.ttf', s)
LB = lambda s: ImageFont.truetype('/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf', s)
EM = ImageFont.truetype('/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf', 109)
BLEU = (0, 0x70, 0xA0); ROUGE = (0xD8, 0x34, 0x34); VERT = (0x1F, 0x8A, 0x4C); INK = (30, 42, 51); CASSE = (0xFA, 0xF7, 0xF2)

def emoji(ch, size):
    im = Image.new('RGBA', (136, 128), (0, 0, 0, 0)); ImageDraw.Draw(im).text((0, 0), ch, font=EM, embedded_color=True)
    im = im.crop(im.getbbox()); return im.resize((size, int(size * im.height / im.width)), Image.LANCZOS)

orig = Image.open(SRC).convert('RGB'); A = Image.open(APRES).convert('RGB'); W, H = orig.size
d = ImageDraw.Draw(A)
d.rectangle((44, 1020, 90, 1060), fill='white'); e = emoji('🔗', 38); A.paste(e, (48, 1022), e)
cols = [(0, 390), (395, 784), (788, 1179)]; g0 = 1325
tile = orig.crop((788, 1767, 1179, 2284)).copy(); td = ImageDraw.Draw(tile)
lh = 60; by = int(tile.height * 0.40)
td.rounded_rectangle((18, by, tile.width - 18, by + lh * 2 + 24), 18, fill=BLEU)
for i, l in enumerate(['REMISE', 'EN ÉTAT']):
    td.text((tile.width // 2, by + 12 + lh * i + lh // 2), l, font=M(46), fill='white', anchor='mm')
td.rounded_rectangle((14, 14, 190, 66), 10, fill=(254, 44, 85)); td.text((102, 40), 'Épinglé', font=LB(32), fill='white', anchor='mm')
A.paste(tile, (cols[1][0], g0))

def badge(dr, x, y, n, c):
    dr.ellipse((x - 34, y - 34, x + 34, y + 34), fill=c, outline='white', width=5); dr.text((x, y), str(n), font=M(40), fill='white', anchor='mm')
def boite(dr, b, c, n, bx, by):
    dr.rounded_rectangle(b, 16, outline=c, width=9); badge(dr, bx, by, n, c)

B = orig.copy(); db = ImageDraw.Draw(B)
boite(db, (30, 325, 470, 440), ROUGE, 1, 470, 330)
boite(db, (30, 845, 1000, 975), ROUGE, 2, 1000, 850)
db.rounded_rectangle((30, 985, 560, 1000), 6, fill=ROUGE); badge(db, 600, 993, 3, ROUGE)
boite(db, (6, 1252, 1173, 1757), ROUGE, 4, 1140, 1290)
boite(db, (6, 1767, 1173, 2284), ROUGE, 6, 1140, 1805)
boite(db, (6, 2295, 388, 2550), ROUGE, 5, 360, 2330)
db.line((40, 2320, 350, 2530), fill=ROUGE, width=10); db.line((350, 2320, 40, 2530), fill=ROUGE, width=10)
da = ImageDraw.Draw(A)
boite(da, (30, 330, 830, 440), VERT, 1, 830, 335)
boite(da, (30, 845, 1000, 1015), VERT, 2, 1000, 850)
boite(da, (30, 1018, 800, 1065), VERT, 3, 800, 1030)
boite(da, (6, 1330, 1173, 1840), VERT, 4, 1140, 1370)
boite(da, (6, 1848, 1173, 2370), VERT, 6, 1140, 1890)
boite(da, (6, 2375, 388, 2550), VERT, 5, 360, 2410)

gap = 70; CW = W * 2 + gap * 3; top = 470
C = Image.new('RGB', (CW, top + H + 1700), CASSE); dc = ImageDraw.Draw(C)
dc.text((gap, 60), "Profil TikTok @miedaou géré par les agents", font=M(84), fill=INK)
dc.text((gap, 175), "Démo : ce que l'équipe enlève et ajoute, d'après l'audit du profil et les bios proposées. Rien n'est publié.", font=PS(42), fill=(80, 90, 100))
for i, (im, lab, c) in enumerate([(B, "AVANT  ·  aujourd'hui  ·  28/100", ROUGE), (A, "APRÈS  ·  géré par les agents  ·  74/100 estimé", VERT)]):
    x = gap + i * (W + gap)
    dc.rounded_rectangle((x, 270, x + W, 380), 24, fill=c)
    dc.text((x + W // 2, 325), lab, font=M(46), fill='white', anchor='mm')
    dc.rounded_rectangle((x - 12, top - 12, x + W + 12, top + H + 12), 40, fill=(40, 40, 48))
    C.paste(im, (x, top))
L = [(1, "Nom « Mièdaou » seul : personne ne le trouve en cherchant « ménage 974 ».", "Nom « Mièdaou | Ménage & aide 974 » (mots recherchés).", "Bios et profils"),
     (2, "Bio = liste de services : ni avantage, ni devis, ni téléphone.", "Offre 20 ans : 50 € offerts*, ménage -50 %*, devis gratuit, 0262 30 36 37.", "Bios et profils + Conversion devis"),
     (3, "Aucun lien : le visiteur ne peut pas demander de devis.", "Compte professionnel + lien miedaou.fr suivi (UTM 20ans).", "Bios et profils + Analyste"),
     (4, "Rien d'épinglé : la grille commence par la dernière vidéo publiée.", "3 épinglées : l'offre 20 ans (agir), la remise en état (preuve), les coulisses 37,8 K (équipe).", "Stratège contenu + Bios"),
     (5, "Jeu concours encore en vue (à vérifier s'il est clos).", "Marqué « Concours terminé », ou archivé.", "Directeur artistique"),
     (6, "Couvertures sans titre lisible, grille mélangée.", "Couvertures aux couleurs Mièdaou, 4 mots max : on comprend chaque vidéo en miniature.", "Directeur artistique")]
y = top + H + gap + 40
dc.text((gap, y), "ENLEVÉ", font=M(52), fill=ROUGE); dc.text((gap + 1120, y), "AJOUTÉ", font=M(52), fill=VERT); dc.text((gap + 2040, y), "AGENT", font=M(52), fill=INK)
y += 95
def wrap(t, f, w):
    out = []; cur = ''
    for m in t.split():
        if f.getlength(cur + ' ' + m) > w and cur: out.append(cur); cur = m
        else: cur = (cur + ' ' + m).strip()
    return out + [cur]
for n, a, b, ag in L:
    fa = PS(36); la = wrap(a, fa, 960); lb = wrap(b, fa, 860); lg = wrap(ag, PS(32), 340)
    h = max(len(la), len(lb), len(lg)) * 48 + 30
    badge(dc, gap + 30, y + 28, n, INK)
    for i, l in enumerate(la): dc.text((gap + 90, y + i * 48), l, font=fa, fill=(150, 40, 40))
    for i, l in enumerate(lb): dc.text((gap + 1120, y + i * 48), l, font=fa, fill=(20, 100, 55))
    for i, l in enumerate(lg): dc.text((gap + 2040, y + i * 48 + 4), l, font=PS(32), fill=INK)
    y += h; dc.line((gap, y - 14, CW - gap, y - 14), fill=(225, 220, 212), width=3)
y += 20
dc.text((gap, y), "Inchangé volontairement : les chiffres (7 488 abonnés, 22,7 K j'aime), la photo de profil et la fonction Abonnement. Aucun chiffre n'est inventé.", font=PS(34), fill=(80, 90, 100))
dc.text((gap, y + 56), "Ensuite : 1 vidéo par jour (calendrier 30 jours), réponses aux commentaires dans l'heure, bilan chaque lundi vers l'objectif 10 000 abonnés.", font=PS(34), fill=(80, 90, 100))
C = C.crop((0, 0, CW, y + 150)); C.save('demo/profil-tiktok-avant-apres.jpg', quality=90)
A.save('demo/profil-tiktok-apres.jpg', quality=92)
print(C.size)
