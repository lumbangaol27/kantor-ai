#!/usr/bin/env python3
"""Video animasi kartun: maskot bicara (mulut mengikuti suara), kedip, melambai, benda muncul memantul,
teks muncul kata per kata. Semua digambar lewat kode (Pillow + numpy), disusun ffmpeg. Gratis.

Dipakai oleh run_agents.py. Uji mandiri:  python make_video.py contoh.json keluar.mp4
Format adegan: [{"teks": "tulisan di layar", "narasi": "kalimat yang diucapkan"}, ...]
Jika suara gagal dibuat, mulut maskot tetap bergerak (simulasi) dan video tanpa suara.
"""
import json, math, pathlib, subprocess, sys, tempfile, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS, SR = 720, 1280, 24, 16000
VOICE = "id-ID-ArdiNeural"
PALETTE = [("#1b1f4b", "#4a3490"), ("#0f3a4a", "#1d7a84"), ("#4a1f3d", "#9a3f6c"),
           ("#3a2b12", "#a0722a"), ("#152b1f", "#2f7a4c")]
FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"]
_fc = {}


def font(size):
    if size not in _fc:
        for f in FONTS:
            if pathlib.Path(f).exists():
                _fc[size] = ImageFont.truetype(f, size)
                break
        else:
            _fc[size] = ImageFont.load_default(size)
    return _fc[size]


def hexrgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def out_back(x):
    x = max(0.0, min(1.0, x))
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def out_cubic(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


# ---------- latar ----------
def gradient(c1, c2):
    a, b = np.array(hexrgb(c1), float), np.array(hexrgb(c2), float)
    t = np.linspace(0, 1, H)[:, None]
    col = (a + (b - a) * t).astype(np.uint8)
    return Image.fromarray(np.repeat(col[:, None, :], W, axis=1), "RGB")


def bubbles(d, t, idx, tint):
    for k in range(7):
        sp = 14 + 9 * ((k * 5 + idx) % 4)
        r = 40 + 18 * ((k * 3 + idx) % 5)
        x = (k * 173 + idx * 61 + t * sp * 0.6) % (W + 2 * r) - r
        y = (H - ((k * 211 + t * sp) % (H + 2 * r))) + r - r
        d.ellipse((x - r, y - r, x + r, y + r), fill=tint)


# ---------- benda (props) ----------
def prop_image(kind):
    S = 2
    im = Image.new("RGBA", (400 * S, 400 * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    s = lambda *v: tuple(int(x * S) for x in v)
    if kind == "uang":
        for i, y in enumerate((300, 255, 210)):
            d.ellipse(s(110, y - 30, 290, y + 30), fill="#c8921a", outline="#8a5f0c", width=3 * S)
            d.rectangle(s(110, y - 6, 290, y + 0), fill="#c8921a")
        d.ellipse(s(110, 150, 290, 210), fill="#ffd34d", outline="#8a5f0c", width=4 * S)
        d.ellipse(s(135, 160, 265, 200), outline="#e0a72a", width=3 * S)
        t = "Rp"
        w = d.textlength(t, font=font(52 * S))
        d.text((200 * S - w / 2, 160 * S), t, font=font(52 * S), fill="#8a5f0c")
    elif kind == "toko":
        d.rectangle(s(90, 190, 310, 330), fill="#f5e6cc", outline="#8a6a3a", width=4 * S)
        for i in range(6):
            x0 = 80 + i * 40
            d.polygon([s(x0, 120), s(x0 + 40, 120), s(x0 + 46, 190), s(x0 - 6, 190)],
                      fill="#e24a4a" if i % 2 == 0 else "#ffffff")
        d.rectangle(s(130, 230, 190, 330), fill="#8a5a2a")
        d.rectangle(s(215, 225, 285, 285), fill="#9bd7ee", outline="#8a6a3a", width=3 * S)
    elif kind == "video":
        d.rounded_rectangle(s(120, 70, 280, 340), 26 * S, fill="#14172e", outline="#8f98d8", width=5 * S)
        d.rounded_rectangle(s(134, 100, 266, 300), 10 * S, fill="#5b6cf0")
        d.polygon([s(175, 160)[0:2], s(175, 240)[0:2], s(235, 200)[0:2]], fill="white")
        d.ellipse(s(188, 313, 212, 333), outline="#8f98d8", width=3 * S)
    else:  # ide / bohlam
        for a in range(-60, 61, 30):
            x1 = 200 + 150 * math.sin(math.radians(a))
            y1 = 170 - 150 * math.cos(math.radians(a))
            x2 = 200 + 120 * math.sin(math.radians(a))
            y2 = 170 - 120 * math.cos(math.radians(a))
            d.line(s(x2, y2, x1, y1), fill="#ffe27a", width=8 * S)
        d.ellipse(s(120, 100, 280, 260), fill="#ffe27a", outline="#d9a91c", width=4 * S)
        d.rounded_rectangle(s(160, 255, 240, 300), 10 * S, fill="#9aa0b8")
        d.rounded_rectangle(s(172, 300, 228, 330), 10 * S, fill="#6e7490")
    return im.resize((400, 400), Image.LANCZOS)


def pick_prop(text):
    t = text.lower()
    if any(k in t for k in ("uang", "rp", "modal", "untung", "harga", "gaji", "rugi", "duit", "bayar")):
        return "uang"
    if any(k in t for k in ("toko", "warung", "jual", "usaha", "pelanggan", "umkm")):
        return "toko"
    if any(k in t for k in ("video", "konten", "reels", "posting", "simpan", "ikuti", "follow")):
        return "video"
    return "ide"


# ---------- maskot ----------
def mascot(t, amp, hop, brow, wave_big):
    """Maskot 'Bubu' digambar 2x lalu diperkecil agar halus. Mengembalikan RGBA 380x440."""
    L = Image.new("RGBA", (760, 880), (0, 0, 0, 0))
    d = ImageDraw.Draw(L)
    bob = math.sin(t * 5) * 6 * (0.4 + amp)
    cx = 380
    top = 40 + bob
    # bayangan
    d.ellipse((190, 805, 570, 860), fill=(0, 0, 0, 60))
    # kaki
    d.rounded_rectangle((290, 730 + bob * .3, 355, 810), 26, fill="#3b3470")
    d.rounded_rectangle((405, 730 + bob * .3, 470, 810), 26, fill="#3b3470")
    # lengan kiri (tergantung) dan kanan (melambai)
    sway = math.sin(t * 4) * 14
    d.line((268, 520, 215 + sway, 700), fill="#6d5bd0", width=40)
    d.ellipse((190 + sway, 680, 240 + sway, 730), fill="#ffd36b")
    swing = math.sin(t * (9 if wave_big else 5)) * (36 if wave_big else 14)
    a = math.radians((-55 if wave_big else 72) + swing)
    ex, ey = 492 + 170 * math.cos(a), 520 + 170 * math.sin(a)
    d.line((492, 520, ex, ey), fill="#6d5bd0", width=40)
    d.ellipse((ex - 27, ey - 27, ex + 27, ey + 27), fill="#ffd36b")
    # badan
    d.rounded_rectangle((250, 440, 510, 770), 80, fill="#6d5bd0")
    d.ellipse((322, 580, 438, 720), fill="#8a7af0")
    # kepala
    d.ellipse((165, top, 595, top + 440), fill="#ffd36b", outline="#e0a93a", width=6)
    # jambul
    d.ellipse((330, top - 55, 400, top + 40), fill="#7a4a1e")
    d.ellipse((375, top - 40, 440, top + 40), fill="#7a4a1e")
    # pipi
    d.ellipse((205, top + 250, 285, top + 310), fill=(255, 140, 140, 150))
    d.ellipse((475, top + 250, 555, top + 310), fill=(255, 140, 140, 150))
    # mata
    blink = (t % 3.1) < 0.14
    oh = 0.12 if blink else 1.0
    for ex_ in (300, 460):
        ey_ = top + 190
        d.ellipse((ex_ - 50, ey_ - 56 * oh, ex_ + 50, ey_ + 56 * oh), fill="white", outline="#2a2550", width=5)
        if not blink:
            px, py = math.sin(t * .9) * 9, math.cos(t * .7) * 5
            d.ellipse((ex_ - 22 + px, ey_ - 26 + py, ex_ + 22 + px, ey_ + 22 + py), fill="#2a2550")
            d.ellipse((ex_ - 10 + px, ey_ - 20 + py, ex_ + 2 + px, ey_ - 8 + py), fill="white")
    # alis
    rb = -28 * brow
    d.line((250, top + 112 + rb, 350, top + 104 + rb * .6), fill="#7a4a1e", width=12)
    d.line((410, top + 104 + rb * .6, 510, top + 112 + rb), fill="#7a4a1e", width=12)
    # mulut
    my = top + 330
    if amp > 0.06:
        h = 14 + amp * 100
        w = 70 + amp * 40
        d.ellipse((cx - w, my - 10, cx + w, my - 10 + h * 1.6), fill="#7a1f2b", outline="#4a1018", width=5)
        d.ellipse((cx - w * .55, my - 10 + h * 1.6 * .55, cx + w * .55, my - 12 + h * 1.6), fill="#f08a96")
    else:
        d.arc((cx - 70, my - 40, cx + 70, my + 40), 20, 160, fill="#7a1f2b", width=9)
    im = L.resize((440, 510), Image.LANCZOS)
    return im


# ---------- teks ----------
def wrap(d, text, fnt, maxw):
    lines, cur = [], []
    for w in text.split():
        trial = " ".join(cur + [w])
        if d.textlength(trial, font=fnt) <= maxw or not cur:
            cur.append(w)
        else:
            lines.append(cur)
            cur = [w]
    if cur:
        lines.append(cur)
    return lines


def card_layout(text):
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    size = 58
    while True:
        fnt = font(size)
        lines = wrap(probe, text, fnt, 540)
        lh = int(size * 1.28)
        if len(lines) * lh + 56 <= 330 or size <= 36:
            return fnt, lines, lh
        size -= 4


# ---------- audio ----------
def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, **kw)


def tts(text, out):
    try:
        r = subprocess.run([sys.executable, "-m", "edge_tts", "--voice", VOICE, "--text", text,
                            "--write-media", str(out)], capture_output=True, text=True, timeout=60)
        return r.returncode == 0 and pathlib.Path(out).exists() and pathlib.Path(out).stat().st_size > 1000
    except Exception:
        return False


def decode(path):
    r = run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"])
    if r.returncode:
        raise RuntimeError("decode audio gagal")
    return np.frombuffer(r.stdout, dtype=np.int16)


def frame_amp(pcm, n_frames):
    spf = SR / FPS
    out = np.zeros(n_frames)
    for i in range(n_frames):
        seg = pcm[int(i * spf):int((i + 1) * spf)].astype(float)
        out[i] = math.sqrt(np.mean(seg ** 2)) if len(seg) else 0.0
    ref = np.percentile(out[out > 0], 90) if (out > 0).any() else 1.0
    out = np.clip(out / (ref * 1.1), 0, 1)
    sm = np.copy(out)
    for i in range(1, n_frames):
        sm[i] = max(out[i], sm[i - 1] * 0.55)
    return sm


# ---------- utama ----------
def make(scenes, out_path):
    """Kembalikan (jumlah_adegan, jumlah_adegan_bersuara)."""
    scenes = [s for s in scenes if str(s.get("teks", "")).strip()][:8]
    if not scenes:
        raise ValueError("Tidak ada adegan")
    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    voiced = 0
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        pcms, sims = [], []
        for i, s in enumerate(scenes):
            narasi = str(s.get("narasi") or s["teks"]).strip()
            a = td / f"a{i}.mp3"
            if tts(narasi, a):
                pcm = decode(a)
                pcm = np.concatenate([pcm, np.zeros(int(0.45 * SR), dtype=np.int16)])
                voiced += 1
                sims.append(False)
            else:
                dur = max(2.5, len(narasi.split()) * 0.42) + 0.45
                pcm = np.zeros(int(dur * SR), dtype=np.int16)
                sims.append(True)
            pcms.append(pcm)
        wav = td / "all.wav"
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes(np.concatenate(pcms).tobytes())

        bgs = [gradient(*PALETTE[i % len(PALETTE)]) for i in range(len(scenes))]
        props = {}
        cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
               "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "veryfast", "-crf", "27",
               "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "64k", "-shortest", "-movflags", "+faststart", str(out)]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            for i, s in enumerate(scenes):
                n = int(len(pcms[i]) / SR * FPS)
                amps = frame_amp(pcms[i], n) if not sims[i] else None
                words = str(s["teks"]).split()
                fnt, lines, lh = card_layout(str(s["teks"]))
                flat = [w for ln in lines for w in ln]
                kind = pick_prop(f"{s['teks']} {s.get('narasi', '')}")
                if kind not in props:
                    props[kind] = prop_image(kind)
                narasi_words = max(1, len(str(s.get("narasi") or s["teks"]).split()))
                tint = tuple(min(255, c + 16) for c in hexrgb(PALETTE[i % len(PALETTE)][0]))
                for f in range(n):
                    t = f / FPS
                    if sims[i]:
                        sp = t * (narasi_words / max(1.0, n / FPS - .45)) * 2.2
                        amp = 0.0 if t > n / FPS - .45 else abs(math.sin(sp * math.pi)) * (0.55 + 0.4 * math.sin(t * 3.1))
                    else:
                        amp = float(amps[f])
                    im = bgs[i].copy()
                    d = ImageDraw.Draw(im)
                    bubbles(d, t, i, tint)
                    # penanda kemajuan + label
                    seg = (W - 80) / len(scenes)
                    for k in range(len(scenes)):
                        d.rounded_rectangle((40 + k * seg + 3, 56, 40 + (k + 1) * seg - 3, 64), 4,
                                            fill=(255, 255, 255) if k <= i else (120, 120, 160))
                    d.text((40, 80), "Agent HQ", font=font(24), fill=(210, 215, 240))
                    # benda memantul masuk
                    sc = out_back(t / 0.55)
                    p = props[kind]
                    ps = max(8, int(350 * sc))
                    pim = p.resize((ps, ps), Image.LANCZOS)
                    im.paste(pim, (W // 2 - ps // 2, int(255 - ps / 2 + math.sin(t * 2.6) * 9)), pim)
                    # kartu teks
                    slide = (1 - out_cubic(t / 0.4)) * 90
                    shown = min(len(flat), int((t - 0.25) / max(0.001, (n / FPS - 1.0) * 0.55 / len(flat)) + 1) if t > .25 else 0)
                    ch = len(lines) * lh + 56
                    cy = 430 + slide
                    d.rounded_rectangle((60, cy + 8, 660, cy + ch + 8), 36, fill=(0, 0, 0))
                    d.rounded_rectangle((60, cy, 660, cy + ch), 36, fill=(255, 255, 255))
                    c = 0
                    for r, ln in enumerate(lines):
                        wtot = d.textlength(" ".join(ln), font=fnt)
                        x = (W - wtot) / 2
                        for w_ in ln:
                            if c < shown:
                                last = (c == shown - 1) and shown < len(flat)
                                d.text((x, cy + 28 + r * lh), w_, font=fnt, fill="#d6336c" if last else "#1b1f4b")
                            x += d.textlength(w_ + " ", font=fnt)
                            c += 1
                    # maskot melompat kecil di awal adegan
                    hop = max(0.0, 1 - t / 0.5)
                    m = mascot(t, amp, hop, 1.0 if (i == 0 and t < 1.6) else 0.0, i == len(scenes) - 1)
                    my = 775 - int(math.sin(min(1, t / 0.5) * math.pi) * 40 * (1 if t < .5 else 0))
                    im.paste(m, (W // 2 - 220, my), m)
                    proc.stdin.write(im.tobytes())
            proc.stdin.close()
            err = proc.stderr.read().decode()[-300:]
            if proc.wait():
                raise RuntimeError("ffmpeg gagal: " + err)
        except BrokenPipeError:
            raise RuntimeError("ffmpeg berhenti: " + proc.stderr.read().decode()[-300:])
    return len(scenes), voiced


if __name__ == "__main__":
    sc = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
    print(make(sc, sys.argv[2]))
