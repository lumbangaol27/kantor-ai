#!/usr/bin/env python3
"""Ubah daftar adegan jadi video vertikal 720x1280: slide teks + suara (edge-tts, gratis) + ffmpeg.

Dipakai oleh run_agents.py. Uji mandiri:  python make_video.py contoh.json keluar.mp4
Format adegan: [{"teks": "tulisan di layar", "narasi": "kalimat yang diucapkan"}, ...]
Jika suara gagal dibuat, adegan memakai jeda hening sesuai panjang kalimat.
"""
import json, pathlib, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFont

W, H = 720, 1280
VOICE = "id-ID-ArdiNeural"
PALETTE = [("#1b1f4b", "#3b2a7a"), ("#0f3a4a", "#1d6b73"), ("#4a1f3d", "#8a3a63"),
           ("#3a2b12", "#8a6420"), ("#152b1f", "#2f6b46")]
FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"]


def font(size):
    for f in FONTS:
        if pathlib.Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default(size)


def gradient(c1, c2):
    a = Image.new("RGB", (1, H))
    p1 = tuple(int(c1[i:i + 2], 16) for i in (1, 3, 5))
    p2 = tuple(int(c2[i:i + 2], 16) for i in (1, 3, 5))
    for y in range(H):
        t = y / (H - 1)
        a.putpixel((0, y), tuple(int(p1[k] + (p2[k] - p1[k]) * t) for k in range(3)))
    return a.resize((W, H))


def wrap(draw, text, fnt, maxw):
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if draw.textlength(trial, font=fnt) <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def slide(text, idx, total, path):
    c1, c2 = PALETTE[idx % len(PALETTE)]
    im = gradient(c1, c2)
    d = ImageDraw.Draw(im)
    size = 76
    while True:
        fnt = font(size)
        lines = wrap(d, text, fnt, W - 120)
        lh = int(size * 1.3)
        if len(lines) * lh <= H * 0.6 or size <= 40:
            break
        size -= 4
    y = (H - len(lines) * lh) // 2
    for ln in lines:
        w = d.textlength(ln, font=fnt)
        d.text(((W - w) / 2 + 3, y + 3), ln, font=fnt, fill=(0, 0, 0))
        d.text(((W - w) / 2, y), ln, font=fnt, fill=(255, 255, 255))
        y += lh
    # penanda kemajuan di atas
    seg = (W - 80) / total
    for i in range(total):
        d.rounded_rectangle((40 + i * seg + 3, 60, 40 + (i + 1) * seg - 3, 68), 4,
                            fill=(255, 255, 255) if i <= idx else (120, 120, 150))
    d.text((40, H - 90), "Agent HQ", font=font(28), fill=(200, 205, 230))
    im.save(path)


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def duration(path):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)])
    return float(r.stdout.strip())


def tts(text, out):
    try:
        r = subprocess.run([sys.executable, "-m", "edge_tts", "--voice", VOICE, "--text", text,
                            "--write-media", str(out)], capture_output=True, text=True, timeout=60)
        return r.returncode == 0 and pathlib.Path(out).exists() and pathlib.Path(out).stat().st_size > 1000
    except Exception:
        return False


def make(scenes, out_path):
    """Kembalikan (jumlah_adegan, jumlah_adegan_bersuara)."""
    scenes = [s for s in scenes if str(s.get("teks", "")).strip()][:10]
    if not scenes:
        raise ValueError("Tidak ada adegan")
    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    voiced = 0
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        segs = []
        for i, s in enumerate(scenes):
            img, aud, seg = td / f"s{i}.png", td / f"a{i}.mp3", td / f"v{i}.mp4"
            slide(str(s["teks"]).strip(), i, len(scenes), img)
            narasi = str(s.get("narasi") or s["teks"]).strip()
            if tts(narasi, aud):
                dur = duration(aud) + 0.5
                voiced += 1
                audio_in = ["-i", str(aud)]
            else:
                dur = max(2.5, len(narasi.split()) * 0.42)
                audio_in = ["-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono"]
            cmd = ["ffmpeg", "-y", "-loop", "1", "-framerate", "24", "-i", str(img), *audio_in,
                   "-t", f"{dur:.2f}", "-af", "aresample=24000,apad", "-ac", "1",
                   "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-pix_fmt", "yuv420p",
                   "-c:a", "aac", "-b:a", "64k", "-shortest", str(seg)]
            r = run(cmd)
            if r.returncode:
                raise RuntimeError("ffmpeg gagal: " + r.stderr[-300:])
            segs.append(seg)
        lst = td / "list.txt"
        lst.write_text("".join(f"file '{p}'\n" for p in segs))
        r = run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
                 "-movflags", "+faststart", str(out)])
        if r.returncode:
            raise RuntimeError("ffmpeg gabung gagal: " + r.stderr[-300:])
    return len(scenes), voiced


if __name__ == "__main__":
    sc = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
    print(make(sc, sys.argv[2]))
