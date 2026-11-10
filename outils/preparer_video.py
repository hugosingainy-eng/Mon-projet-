#!/usr/bin/env python3
"""Prépare une vidéo brute pour l'équipe d'agents Mièdaou.

Produit, dans le dossier de sortie :
  infos.json            durée, résolution, images/s, volume moyen
  planche.jpg           une image par seconde, en mosaïque (pour que les agents « voient » la vidéo)
  images/               les images une par une
  audio.wav             piste son mono 16 kHz
  transcription.txt     le texte dit dans la vidéo
  transcription.json    segments et mots avec leurs temps (approximatifs)
  sous-titres.srt       sous-titres prêts à corriger

Usage :
  python3 outils/preparer_video.py chemin/video.mov demo/ma-video
  python3 outils/preparer_video.py chemin/video.mov demo/ma-video --sans-transcription

La transcription fonctionne hors ligne (Whisper small, via sherpa-onnx).
Au premier lancement, les modèles (environ 650 Mo) sont téléchargés depuis les
publications GitHub de sherpa-onnx dans ~/.cache/miedaou/asr (ou $MIEDAOU_ASR_DIR).
Dépendances : ffmpeg, et `pip install sherpa-onnx numpy`.

Les temps des mots sont estimés : le texte de chaque passage parlé est réparti
selon la longueur des mots. Relire et corriger `transcription.json` avant le
rendu final si un sous-titre tombe à côté.
"""

import argparse
import json
import math
import os
import re
import subprocess
import sys
import tarfile
import urllib.request
import wave

RELEASES = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
WHISPER = "sherpa-onnx-whisper-small"
VAD = "silero_vad.onnx"


def run(cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def infos(video):
    out = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
               "stream=width,height,r_frame_rate:format=duration", "-of", "json", video]).stdout
    d = json.loads(out)
    st = d["streams"][0]
    num, den = st["r_frame_rate"].split("/")
    vol = subprocess.run(["ffmpeg", "-i", video, "-af", "volumedetect", "-vn", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    m = re.search(r"mean_volume: (-?[\d.]+) dB", vol)
    return {
        "duree_s": round(float(d["format"]["duration"]), 2),
        "largeur": st["width"], "hauteur": st["height"],
        "images_par_seconde": round(int(num) / int(den), 2),
        "volume_moyen_db": float(m.group(1)) if m else None,
    }


def planche(video, out, duree):
    img = os.path.join(out, "images")
    os.makedirs(img, exist_ok=True)
    run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vf", "fps=1,scale=360:-2",
         os.path.join(img, "s%03d.jpg")])
    n = max(1, math.ceil(duree))
    cols = min(8, n)
    rows = math.ceil(n / cols)
    run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(img, "s%03d.jpg"),
         "-vf", f"tile={cols}x{rows}:padding=6:color=white", "-frames:v", "1",
         os.path.join(out, "planche.jpg")])


def audio(video, out):
    wav = os.path.join(out, "audio.wav")
    run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vn", "-ac", "1", "-ar", "16000", wav])
    return wav


def modeles():
    base = os.path.expanduser(os.environ.get("MIEDAOU_ASR_DIR", "~/.cache/miedaou/asr"))
    os.makedirs(base, exist_ok=True)
    wdir = os.path.join(base, WHISPER)
    if not os.path.isdir(wdir):
        arc = os.path.join(base, WHISPER + ".tar.bz2")
        print(f"Téléchargement du modèle de transcription (environ 640 Mo) vers {base}...", file=sys.stderr)
        urllib.request.urlretrieve(RELEASES + WHISPER + ".tar.bz2", arc)
        with tarfile.open(arc) as t:
            t.extractall(base, filter="data")
        os.remove(arc)
    vad = os.path.join(base, VAD)
    if not os.path.isfile(vad):
        urllib.request.urlretrieve(RELEASES + VAD, vad)
    return wdir, vad


def lire_wav(path):
    import numpy as np
    with wave.open(path) as w:
        sr = w.getframerate()
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    return sr, a


def transcrire(wav, langue="fr"):
    import sherpa_onnx
    wdir, vad_path = modeles()
    rec = sherpa_onnx.OfflineRecognizer.from_whisper(
        encoder=os.path.join(wdir, "small-encoder.onnx"),
        decoder=os.path.join(wdir, "small-decoder.onnx"),
        tokens=os.path.join(wdir, "small-tokens.txt"),
        language=langue, task="transcribe", num_threads=os.cpu_count() or 2)
    sr, a = lire_wav(wav)

    cfg = sherpa_onnx.VadModelConfig()
    cfg.silero_vad.model = vad_path
    cfg.silero_vad.min_silence_duration = 0.25
    cfg.silero_vad.min_speech_duration = 0.25
    cfg.silero_vad.max_speech_duration = 8
    cfg.sample_rate = sr
    vad = sherpa_onnx.VoiceActivityDetector(cfg, buffer_size_in_seconds=max(60, len(a) / sr + 5))
    win = cfg.silero_vad.window_size
    spans = []
    for i in range(0, len(a), win):
        vad.accept_waveform(a[i:i + win])
        while not vad.empty():
            seg = vad.front
            spans.append((seg.start, seg.start + len(seg.samples)))
            vad.pop()
    vad.flush()
    while not vad.empty():
        seg = vad.front
        spans.append((seg.start, seg.start + len(seg.samples)))
        vad.pop()
    if not spans:                       # musique forte : on traite tout d'un bloc
        spans = [(0, len(a))]

    segments = []
    for s0, s1 in spans:
        st = rec.create_stream()
        st.accept_waveform(sr, a[s0:s1])
        rec.decode_stream(st)
        texte = st.result.text.strip()
        if not texte:
            continue
        t0, t1 = s0 / sr, s1 / sr
        mots = texte.split()
        poids = [len(m) + 1 for m in mots]
        tot = sum(poids)
        clock, liste = t0, []
        for m, p in zip(mots, poids):
            d = (t1 - t0) * p / tot
            liste.append({"mot": m, "debut": round(clock, 2), "fin": round(clock + d, 2)})
            clock += d
        segments.append({"debut": round(t0, 2), "fin": round(t1, 2), "texte": texte, "mots": liste})
    return segments


def srt(segments, path, par=4):
    def tc(t):
        h, r = divmod(t, 3600)
        m, s = divmod(r, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s % 1) * 1000)):03d}"
    n, lignes = 0, []
    for seg in segments:
        mots = seg["mots"]
        for i in range(0, len(mots), par):
            g = mots[i:i + par]
            n += 1
            lignes += [str(n), f"{tc(g[0]['debut'])} --> {tc(g[-1]['fin'])}",
                       " ".join(w["mot"] for w in g), ""]
    open(path, "w", encoding="utf-8").write("\n".join(lignes))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("video")
    ap.add_argument("sortie")
    ap.add_argument("--langue", default="fr")
    ap.add_argument("--sans-transcription", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.sortie, exist_ok=True)

    inf = infos(a.video)
    json.dump(inf, open(os.path.join(a.sortie, "infos.json"), "w"), indent=2, ensure_ascii=False)
    planche(a.video, a.sortie, inf["duree_s"])
    wav = audio(a.video, a.sortie)
    print(json.dumps(inf, ensure_ascii=False))

    if a.sans_transcription:
        return
    segs = transcrire(wav, a.langue)
    json.dump({"segments": segs, "note": "Temps des mots estimés ; à corriger si besoin."},
              open(os.path.join(a.sortie, "transcription.json"), "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)
    open(os.path.join(a.sortie, "transcription.txt"), "w", encoding="utf-8").write(
        "\n".join(f"[{s['debut']:5.1f}-{s['fin']:5.1f}] {s['texte']}" for s in segs) + "\n")
    srt(segs, os.path.join(a.sortie, "sous-titres.srt"))
    for s in segs:
        print(f"[{s['debut']:5.1f}-{s['fin']:5.1f}] {s['texte']}")


if __name__ == "__main__":
    main()
