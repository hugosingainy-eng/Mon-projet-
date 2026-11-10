#!/usr/bin/env python3
"""Habille une vidéo aux couleurs de Mièdaou, style TikTok, à partir d'une feuille d'habillage JSON.

Ce que l'outil sait faire (codes de marque/bibliotheque-animations.md) :
  - recadrer en 1080 x 1920, 30 images/s
  - zooms progressifs ou « coup de poing » (MOV-1, MOV-2)
  - titres animés : accroche qui frappe (TIT-1), bandeau orange qui glisse (TIT-2),
    mot géant (SUB-3), mention légale, pastille de série (TIT-5), étiquette (TIT-6),
    machine à écrire (TIT-3)
  - sous-titres mot par mot, mot prononcé en orange (SUB-1)
  - vignette tirée d'une image de la vidéo (ex. l'affiche de l'offre) incrustée plus tôt
  - prolongation de la dernière image et carton final (GFX-5)
  - barre de progression (GFX-1)

Usage :
  python3 outils/habiller_video.py feuille.json

Dépendances : ffmpeg (avec libass), Pillow. Polices : outils/polices/.

Dans les textes, *mot* passe le mot en orange et ~mot~ en or.
Exemple de feuille : demo/video-offre-20-ans/habillage.json
"""

import json
import os
import re
import subprocess
import sys
import tempfile

ICI = os.path.dirname(os.path.abspath(__file__))
POLICES = os.path.join(ICI, "polices")
W, H = 1080, 1920

# Couleurs de marque (charte graphique) au format ASS &HAABBGGRR
def ass(hexa, alpha=0):
    hexa = hexa.lstrip("#")
    r, g, b = hexa[0:2], hexa[2:4], hexa[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()

BLEU, BLEU_NUIT, ORANGE, OR, BLANC, NOIR, ANTHRACITE = (
    "#0070A0", "#00557A", "#E89838", "#F8C860", "#FFFFFF", "#000000", "#1E2A33")

# libass met à l'échelle la hauteur totale de la police (ascendante + descendante) :
# à taille égale, les lettres sortent environ 30 % plus petites qu'en PAO.
# Les tailles de ce fichier et des feuilles sont des tailles « PAO » (hauteur de capitale ≈ 0,7 x taille),
# converties ici. Mesuré sur le rendu : hauteur de capitale Montserrat ExtraBold ≈ 0,5 x taille ASS.
ECHELLE_ASS = 1.4

TITRE = "Montserrat ExtraBold"
TEXTE = "Poppins SemiBold"

STYLES = {
    #  nom        police  taille couleur   contour   épaisseur ombre
    "accroche": (TITRE, 112, BLANC, NOIR, 10, 3),
    "geant":    (TITRE, 190, ORANGE, NOIR, 11, 4),
    "bandeau":  (TITRE, 78, BLANC, ORANGE, 0, 0),
    "mention":  (TEXTE, 40, BLANC, NOIR, 5, 3),
    "pastille": (TITRE, 52, BLANC, ORANGE, 0, 0),
    "etiquette": (TITRE, 56, BLANC, BLEU, 0, 0),
    "sous":     (TEXTE, 74, BLANC, NOIR, 8, 2),
    "carton":   (TITRE, 124, BLANC, BLEU, 0, 0),
    "carton_petit": (TEXTE, 62, BLANC, BLEU, 0, 0),
}
FOND_BANDEAU = {"bandeau": ORANGE, "pastille": ORANGE, "etiquette": BLEU}


def police_pil(nom, taille):
    from PIL import ImageFont
    f = {"Montserrat ExtraBold": "Montserrat-ExtraBold.ttf",
         "Poppins SemiBold": "Poppins-SemiBold.ttf"}[nom]
    return ImageFont.truetype(os.path.join(POLICES, f), taille)


def largeur_texte(texte, style, taille=None):
    nom, taille = STYLES[style][0], taille or STYLES[style][1]
    brut = re.sub(r"[*~]", "", texte)
    return max(police_pil(nom, taille).getlength(l) for l in brut.split("\\N"))


def tc(t):
    t = max(0, t)
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def couleurs(texte, base):
    texte = re.sub(r"\*([^*]+)\*", lambda m: "{\\c" + ass(ORANGE) + "}" + m.group(1) + "{\\c" + base + "}", texte)
    texte = re.sub(r"~([^~]+)~", lambda m: "{\\c" + ass(OR) + "}" + m.group(1) + "{\\c" + base + "}", texte)
    return texte


def rect_arrondi(x, y, w, h, r):
    """Chemin de dessin ASS d'un rectangle à coins arrondis."""
    k = r * 0.55
    return (f"m {x+r} {y} l {x+w-r} {y} b {x+w-r+k} {y} {x+w} {y+r-k} {x+w} {y+r} "
            f"l {x+w} {y+h-r} b {x+w} {y+h-r+k} {x+w-r+k} {y+h} {x+w-r} {y+h} "
            f"l {x+r} {y+h} b {x+r-k} {y+h} {x} {y+h-r+k} {x} {y+h-r} "
            f"l {x} {y+r} b {x} {y+r-k} {x+r-k} {y} {x+r} {y}")


def entree(anim, x, y, debut_ms=0):
    if anim == "pop":
        return "{\\fscx135\\fscy135\\t(0,130,\\fscx100\\fscy100)\\fad(60,120)}"
    if anim == "glisse":
        return f"{{\\move({x - W},{y},{x},{y},0,260)\\fad(0,120)}}"
    if anim == "fondu":
        return "{\\fad(180,180)}"
    if anim == "pulse":
        return ("{\\fad(100,0)\\t(0,300,\\fscx108\\fscy108)\\t(300,600,\\fscx100\\fscy100)"
                "\\t(600,900,\\fscx108\\fscy108)\\t(900,1200,\\fscx100\\fscy100)"
                "\\t(1200,1500,\\fscx108\\fscy108)\\t(1500,1800,\\fscx100\\fscy100)}")
    return ""


def evenements_titre(t):
    style = t.get("style", "accroche")
    x, y = t.get("x", W // 2), t["y"]
    anim = t.get("anim", "pop")
    d0, d1 = t["debut"], t["fin"]
    base = ass(t["couleur"]) if t.get("couleur") else ass(STYLES[style][2])
    fs = f"\\fs{round(t['taille'] * ECHELLE_ASS)}" if t.get("taille") else ""
    if t.get("couleur"):
        fs += f"\\c{base}"
    lignes = []
    if style in FOND_BANDEAU and not t.get("sans_fond"):
        taille = t.get("taille") or STYLES[style][1]
        n = t["texte"].count("\\N") + 1
        bw = int(t.get("largeur_fond") or largeur_texte(t["texte"], style, taille) + taille * 1.1)
        bh = int(t.get("hauteur_fond") or taille * 1.35 * n + taille * 0.35)
        dessin = rect_arrondi(-bw // 2, -bh // 2, bw, bh, min(28, bh // 2))
        mouv = (f"\\move({x - W},{y},{x},{y},0,260)" if anim == "glisse" else f"\\pos({x},{y})")
        anim_fond = "\\fscx135\\fscy135\\t(0,130,\\fscx100\\fscy100)" if anim == "pop" else ""
        if t.get("couleur_fond"):
            FOND_BANDEAU[style + "_" + str(id(t))] = t["couleur_fond"]
        lignes.append(f"Dialogue: 1,{tc(d0)},{tc(d1)},fond,,0,0,0,,"
                      f"{{\\an7{mouv}{anim_fond}\\1c{ass(t.get('couleur_fond') or FOND_BANDEAU[style])}\\bord0\\shad3\\4c{ass(NOIR, 0x90)}\\p1\\fad(0,120)}}{dessin}{{\\p0}}")
    if anim == "machine":
        brut = t["texte"]
        n = len(brut)
        duree = min(d1 - d0 - 0.3, n / t.get("vitesse", 22))
        for i in range(1, n + 1):
            a = d0 + duree * (i - 1) / n
            b = d0 + duree * i / n if i < n else d1
            lignes.append(f"Dialogue: 2,{tc(a)},{tc(b)},{style},,0,0,0,,{{\\an5\\pos({x},{y}){fs}}}{couleurs(brut[:i], base)}")
        return lignes
    pos = "" if anim == "glisse" else f"\\pos({x},{y})"
    lignes.append(f"Dialogue: 2,{tc(d0)},{tc(d1)},{style},,0,0,0,,{{\\an5{pos}{fs}}}"
                  f"{entree(anim, x, y)}{couleurs(t['texte'], base)}")
    return lignes


def groupes(mots, maxi=3):
    g, out = [], []
    for m in mots:
        g.append(m)
        if len(g) >= maxi or re.search(r"[.,!?…;:]$", m["mot"]):
            out.append(g)
            g = []
    if g:
        out.append(g)
    return out


def evenements_sous_titres(st, masques):
    data = json.load(open(st["fichier"], encoding="utf-8"))
    y = st.get("y", 1250)
    xs = st.get("x", W // 2)
    fs = f"\\fs{round(st['taille'] * ECHELLE_ASS)}" if st.get("taille") else ""
    cles = [c.lower() for c in st.get("mots_cles", [])]
    decal = st.get("decalage", 0)
    lignes = []

    def cache(a, b):
        return any(a < m1 and b > m0 for m0, m1 in masques)

    for seg in data["segments"]:
        for g in groupes(seg["mots"], st.get("mots_par_ligne", 3)):
            for i, actif in enumerate(g):
                a = actif["debut"] + decal
                b = (g[i + 1]["debut"] if i + 1 < len(g) else actif["fin"]) + decal
                if cache(a, b) or b <= a:
                    continue
                parts = []
                for j, m in enumerate(g):
                    mot = m["mot"]
                    propre = re.sub(r"[^\wÀ-ÿ€%]", "", mot.lower())
                    if j == i:
                        parts.append(f"{{\\c{ass(ORANGE)}\\fscx112\\fscy112}}{mot.upper()}{{\\c{ass(BLANC)}\\fscx100\\fscy100}}")
                    elif any(c in propre for c in cles):
                        parts.append(f"{{\\c{ass(OR)}}}{mot.upper()}{{\\c{ass(BLANC)}}}")
                    else:
                        parts.append(mot.upper())
                pop = "{\\fscx92\\fscy92\\t(0,90,\\fscx100\\fscy100)}" if i == 0 else ""
                lignes.append(f"Dialogue: 3,{tc(a)},{tc(b)},sous,,0,0,0,,{{\\an5\\pos({xs},{y}){fs}}}{pop}{' '.join(parts)}")
    return lignes


def evenements_carton(c, debut, fin):
    lignes = [f"Dialogue: 0,{tc(debut)},{tc(fin)},fond,,0,0,0,,"
              f"{{\\an7\\pos(0,0)\\1c{ass(BLEU)}\\bord0\\shad0\\p1\\fad(150,0)}}m 0 0 l {W} 0 {W} {H} 0 {H}{{\\p0}}"]
    y = c.get("y_depart", 820)
    for l in c["lignes"]:
        style = l.get("style", "carton")
        anim = l.get("anim", "pop")
        cx = c.get("x", W // 2)
        lignes.append(f"Dialogue: 4,{tc(debut + l.get('retard', 0))},{tc(fin)},{style},,0,0,0,,"
                      f"{{\\an5\\pos({cx},{y})" + (f"\\fs{round(l['taille'] * ECHELLE_ASS)}" if l.get("taille") else "") + f"}}{entree(anim, cx, y)}{couleurs(l['texte'], ass(STYLES[style][2]))}")
        y += l.get("espace", 130)
    return lignes


def ecrire_ass(f, chemin, duree_totale):
    entete = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: fond,Arial,20,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
"""
    for nom, (pol, taille, coul, cont, ep, omb) in STYLES.items():
        contour = ass(cont) if ep else ass(NOIR)
        entete += (f"Style: {nom},{pol},{round(taille * ECHELLE_ASS)},{ass(coul)},{ass(coul)},{contour},{ass(NOIR, 0x80)},"
                   f"0,0,0,0,100,100,0,0,1,{ep},{omb},5,40,40,0,1\n")
    ev = ["", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    masques = [(t["debut"], t["fin"]) for t in f.get("titres", []) if t.get("masque_sous_titres")]
    masques += [tuple(m) for m in f.get("sous_titres", {}).get("masquer", [])]
    carton = f.get("carton_final")
    if carton:
        masques.append((duree_totale - carton["duree"], duree_totale + 1))
    for t in f.get("titres", []):
        ev += evenements_titre(t)
    if f.get("sous_titres"):
        ev += evenements_sous_titres(f["sous_titres"], masques)
    if f.get("barre_progression"):
        fin_barre = duree_totale - (carton["duree"] if carton else 0)
        ev.append(f"Dialogue: 5,{tc(0)},{tc(fin_barre)},fond,,0,0,0,,"
                  f"{{\\an7\\pos(0,{f['barre_progression'].get('y', 200)})\\1c{ass(ORANGE)}\\bord0\\shad0\\fscx0"
                  f"\\t(0,{int(fin_barre*1000)},\\fscx100)\\p1}}m 0 0 l {W} 0 {W} 12 0 12{{\\p0}}")
    if carton:
        ev += evenements_carton(carton, duree_totale - carton["duree"], duree_totale)
    open(chemin, "w", encoding="utf-8").write(entete + "\n".join(ev) + "\n")


def expr_zoom(zooms):
    """Facteur de zoom en fonction du temps t, sous forme d'expression ffmpeg."""
    e = "1"
    for z in reversed(zooms):
        a, b, z0, z1 = z["debut"], z["fin"], z.get("de", 1.0), z.get("a", 1.12)
        if z.get("type") == "coup":
            r = min(0.12, b - a)
            val = f"if(lt(t,{a}+{r}),{z0}+({z1}-{z0})*(t-{a})/{r},{z1})"
        else:
            val = f"{z0}+({z1}-{z0})*(t-{a})/({b}-{a})"
        e = f"if(between(t,{a},{b}),{val},{e})"
    return e


def expr_centre(zooms, axe, defaut):
    """Point fixe du zoom (en pixels de sortie) en fonction du temps."""
    e = str(defaut)
    for z in reversed(zooms):
        if "centre" in z:
            e = f"if(between(t,{z['debut']},{z['fin']}),{z['centre'][axe]},{e})"
    return e


def duree_source(src):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", src], capture_output=True, text=True, check=True).stdout
    return float(out)


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    feuille = os.path.abspath(sys.argv[1])
    base = os.path.dirname(feuille)
    f = json.load(open(feuille, encoding="utf-8"))
    chem = lambda p: p if os.path.isabs(p) else os.path.normpath(os.path.join(base, p))
    src = chem(f["source"])
    sortie = chem(f["sortie"])
    if f.get("sous_titres"):
        f["sous_titres"]["fichier"] = chem(f["sous_titres"]["fichier"])
    deb_src = f.get("debut_source", 0)
    fin_src = f.get("fin_source", duree_source(src)) - deb_src
    prolong = f.get("prolongation", 0)
    carton = f.get("carton_final")
    total = fin_src + prolong + (carton["duree"] if carton else 0)

    tmp = tempfile.mkdtemp(prefix="habillage-")
    ass_path = os.path.join(tmp, "habillage.ass")
    ecrire_ass(f, ass_path, total)

    entrees = ["-i", src]
    vignettes = f.get("vignettes", [])
    for i, v in enumerate(vignettes):
        img = os.path.join(tmp, f"vignette{i}.png")
        if v.get("image"):
            img = chem(v["image"])
        else:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(v["image_a"]), "-i", src,
                            "-frames:v", "1", img], check=True)
        entrees += ["-loop", "1", "-framerate", "30", "-t", str(total), "-i", img]

    z = expr_zoom(f.get("zooms", []))
    zx = expr_centre(f.get("zooms", []), 0, W // 2)
    zy = expr_centre(f.get("zooms", []), 1, H // 2)
    cadre = f.get("recadrage", {})
    cy = cadre.get("centre_y", 0.5)
    pre = f"crop={f['prerecadrage']}," if f.get("prerecadrage") else ""
    filtres = [
        f"[0:v]trim={deb_src}:{deb_src + fin_src},setpts=PTS-STARTPTS,fps=30,{pre}"
        f"scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H}:(iw-{W})/2:(ih-{H})*{cy},"
        f"scale=w='trunc({W}*({z})/2)*2':h='trunc({H}*({z})/2)*2':eval=frame,"
        f"crop={W}:{H}:'({zx})*(iw/{W}-1)':'({zy})*(ih/{H}-1)',setsar=1,"
        f"tpad=stop_mode=clone:stop_duration={prolong + (carton['duree'] if carton else 0)}[v0]"
    ]
    cur = "v0"
    for i, v in enumerate(vignettes):
        lw = v.get("largeur", 420)
        recad = v.get("recadrage")
        crop = f"crop={recad},"if recad else ""
        bord = v.get("bord", 8)
        zp = ""
        if v.get("zoom"):
            # Zoom animé dans la vignette : clés [temps, zoom, centre_x, centre_y] (centre en fraction de l'image).
            def piece(k):
                e = str(v["zoom"][-1][k])
                for a, b in reversed(list(zip(v["zoom"], v["zoom"][1:]))):
                    e = (f"if(between(T,{a[0]},{b[0]}),{a[k]}+({b[k]}-{a[k]})*(T-{a[0]})/({b[0]}-{a[0]}),{e})")
                return f"if(lt(T,{v['zoom'][0][0]}),{v['zoom'][0][k]},{e})"
            Z, CX, CY = (piece(k).replace("T", "(in/30)") for k in (1, 2, 3))
            lw0 = v.get("largeur", W)
            zp = (f"scale=iw*2:-2,zoompan=z='{Z}':x='max(0,min(iw-iw/zoom,({CX})*iw-iw/zoom/2))':"
                  f"y='max(0,min(ih-ih/zoom,({CY})*ih-ih/zoom/2))':d=1:fps=30:s={lw0}x{{H_VIGNETTE}},")
        if v.get("plein_ecran"):
            fond = v.get("fond", BLEU).lstrip("#")
            if zp:
                from PIL import Image
                src_img = chem(v["image"]) if v.get("image") else os.path.join(tmp, f"vignette{i}.png")
                with Image.open(src_img) as im0:
                    cw, ch = im0.size
                if v.get("recadrage"):
                    cw, ch = (int(x) for x in v["recadrage"].split(":")[:2])
                hv = int(round(v["largeur"] * ch / cw / 2) * 2)
                filtres.append(f"[{i+1}:v]{crop}{zp.replace('{H_VIGNETTE}', str(hv))}pad={W}:{H}:{v.get('x', 0)}:{v.get('y', 0)}"
                               f":color=0x{fond},format=rgba[vg{i}]")
            elif v.get("largeur"):
                filtres.append(f"[{i+1}:v]{crop}scale={v['largeur']}:-2,pad={W}:{H}:{v.get('x', 0)}:{v.get('y', 0)}"
                               f":color=0x{fond},format=rgba[vg{i}]")
            else:
                filtres.append(f"[{i+1}:v]{crop}scale={W}:-2,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x{fond},"
                               f"format=rgba[vg{i}]")
            pos = "x=0:y=0"
        else:
            filtres.append(f"[{i+1}:v]{crop}scale={lw}:-2,pad=iw+{2*bord}:ih+{2*bord}:{bord}:{bord}:color=white,"
                           f"format=rgba,fade=in:st={v['debut']}:d=0.15:alpha=1[vg{i}]")
            pos = f"x={v.get('x', 600)}:y={v.get('y', 300)}"
        filtres.append(f"[{cur}][vg{i}]overlay={pos}:"
                       f"enable='between(t,{v['debut']},{v['fin']})'[v{i+1}]")
        cur = f"v{i+1}"
    fontsdir = POLICES.replace(":", "\\:")
    filtres.append(f"[{cur}]subtitles='{ass_path}':fontsdir='{fontsdir}'[vs]")
    cur = "vs"
    logo = f.get("logo")
    if logo and carton:                  # par-dessus le fond bleu du carton final
        n = len(vignettes) + 1
        entrees += ["-loop", "1", "-t", str(total), "-i", chem(logo["image"])]
        lw = logo.get("largeur", 560)
        d0 = total - carton["duree"]
        filtres.append(f"[{n}:v]scale={lw}:-2,pad=iw+60:ih+50:30:25:color=white,format=rgba[lg]")
        filtres.append(f"[{cur}][lg]overlay=x=(W-w)/2:y={logo.get('y', 380)}:enable='gte(t,{d0 + 0.1})'[vl]")
        cur = "vl"
    filtres.append(f"[{cur}]format=yuv420p[vout]")
    norm = "loudnorm=I=-14:TP=-1.5:LRA=11," if f.get("normaliser_son", True) else ""
    filtres.append(f"[0:a]atrim={deb_src}:{deb_src + fin_src},asetpts=PTS-STARTPTS,{norm}aresample=48000,apad=whole_dur={total},"
                   f"afade=t=out:st={max(0, total - 0.8)}:d=0.8[aout]")

    cmd = ["ffmpeg", "-v", "error", "-y", *entrees, "-filter_complex", ";".join(filtres),
           "-map", "[vout]", "-map", "[aout]", "-t", str(total),
           "-c:v", "libx264", "-preset", "medium", "-b:v", f.get("debit", "12M"),
           "-minrate", f.get("debit", "12M"), "-maxrate", f.get("debit", "12M"), "-bufsize", "24M",
           "-x264-params", "nal-hrd=cbr", "-r", "30",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", sortie]
    os.makedirs(os.path.dirname(sortie), exist_ok=True)
    subprocess.run(cmd, check=True)
    print(f"{sortie}  ({total:.1f} s)")


if __name__ == "__main__":
    main()
