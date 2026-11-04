#!/usr/bin/env python3
"""Shift malam kantor AI: agen bekerja berurutan, hasilnya ditulis ke docs/status.json.

Pakai:  GEMINI_API_KEY=... python run_agents.py
Uji tanpa API:  python run_agents.py --demo
"""
import json, os, sys, time, pathlib, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta

ROOT = pathlib.Path(__file__).parent
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
DEMO = "--demo" in sys.argv
KEY = os.environ.get("GEMINI_API_KEY", "")
WIB = timezone(timedelta(hours=7))
OUT = ROOT / "docs" / "status.json"

SYSTEM = ("Kamu {name}, {role} di kantor AI. Kerja ringkas, konkret, bahasa Indonesia. "
          "Jangan mengarang angka atau data yang tidak diberikan.")

DEMO_TEXT = {
    "gilang": "(contoh) Hook menang: angka konkret di kalimat pertama, pertanyaan yang menyentil, before-after. Hook kalah: sapaan panjang, basa-basi, klaim tanpa bukti.",
    "dion": "(contoh) 1. Modal 500 ribu jadi apa? 2. 3 kesalahan harga jual. 3. Cara cek untung rugi 1 menit. 4. Warung vs online. 5. Kemasan murah laku.",
    "mila": "(contoh) Terpilih: 1) 3 kesalahan harga jual yang bikin rugi. 2) Cek untung rugi 1 menit. 3) Modal 500 ribu jadi apa?",
    "ale": "(contoh) Adegan 1: teks '3 kesalahan harga jual'. Adegan 2: kesalahan pertama. Adegan 3: kesalahan kedua. Adegan 4: ajakan simpan.",
    "zaki": "KEPUTUSAN: SETUJU\n(contoh) Hook jelas, satu ide per adegan, durasi pas.",
    "bima": "(contoh) Hari 1 19.30 caption + 5 hashtag. Hari 2 12.00. Hari 3 19.30.",
}


def now():
    return datetime.now(WIB)


_CANDS = None


def candidates():
    """Daftar model untuk dicoba berurutan. Model lama sering dihentikan atau lambat, jadi tidak ditulis mati."""
    global _CANDS
    if _CANDS is not None:
        return _CANDS
    names = []
    try:
        req = urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
                                     headers={"x-goog-api-key": KEY})
        with urllib.request.urlopen(req, timeout=60) as r:
            ms = json.load(r).get("models", [])
        names = [m["name"].split("/")[-1] for m in ms if "generateContent" in m.get("supportedGenerationMethods", [])]
        print("Model tersedia:", ", ".join(names))
    except Exception as e:
        print("Gagal membaca daftar model:", e)
    text = [n for n in names if not any(x in n for x in ("image", "tts", "live", "audio", "embedding", "robotics", "computer"))]
    flash = sorted([n for n in text if "flash" in n and "lite" not in n and "preview" not in n and "exp" not in n], reverse=True)
    lite = sorted([n for n in text if "flash" in n and "lite" in n and "preview" not in n and "exp" not in n], reverse=True)
    order = [os.environ.get("GEMINI_MODEL", ""), "gemini-flash-latest", "gemini-flash-lite-latest"] + lite + flash
    _CANDS = []
    for n in order:
        if n and n not in _CANDS and (not names or n in names):
            _CANDS.append(n)
    if not _CANDS:
        raise RuntimeError("Tidak ada model yang tersedia untuk API key ini")
    print("Urutan model dicoba:", ", ".join(_CANDS))
    return _CANDS


def call(model, system, user, thinking_off):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    gen = {"maxOutputTokens": 2048, "temperature": 0.7}
    if thinking_off:
        gen["thinkingConfig"] = {"thinkingBudget": 0}
    body = json.dumps({"systemInstruction": {"parts": [{"text": system}]},
                       "contents": [{"role": "user", "parts": [{"text": user}]}],
                       "generationConfig": gen}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "x-goog-api-key": KEY})
    with urllib.request.urlopen(req, timeout=75) as r:
        d = json.load(r)
    return "".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"]).strip()


def ask(system, user):
    if DEMO:
        time.sleep(0.2)
        return None
    errors = []
    for model in list(candidates())[:4]:
        thinking_off = True
        for n in range(3):
            t0 = time.time()
            try:
                text = call(model, system, user, thinking_off)
                if text:
                    print(f"OK model={model} {time.time() - t0:.0f}s")
                    return text
                errors.append(f"{model}: jawaban kosong")
                break
            except urllib.error.HTTPError as e:
                msg = e.read()[:300].decode("utf-8", "replace")
                print(f"{model}: HTTP {e.code} {msg[:160]!r}")
                if e.code == 400 and thinking_off:
                    thinking_off = False
                    continue
                if e.code == 429 and n < 2:
                    time.sleep(25 * (n + 1))
                    continue
                errors.append(f"{model}: HTTP {e.code} {msg[:120]}")
                break
            except (TimeoutError, urllib.error.URLError, ConnectionError) as e:
                print(f"{model}: {e} ({time.time() - t0:.0f}s)")
                errors.append(f"{model}: {e}")
                break
    raise RuntimeError("Semua model gagal. " + " | ".join(errors)[:500])


def save(state):
    state["updated"] = now().isoformat(timespec="seconds")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    if not DEMO and not KEY:
        sys.exit("GEMINI_API_KEY belum diisi. Untuk uji tanpa API: python run_agents.py --demo")
    perf = ROOT / "data" / "performa.txt"
    perf_text = perf.read_text(encoding="utf-8")[:4000] if perf.exists() else "(tidak ada data performa)"

    agents = [{"id": a["id"], "name": a["name"], "role": a["role"], "room": a["room"],
               "state": "menunggu", "last_task": "Belum masuk shift", "output": ""} for a in CFG["agents"]]
    byid = {a["id"]: a for a in agents}
    state = {"demo": DEMO, "niche": CFG["niche"], "shift": CFG["shift"], "agents": agents, "log": []}
    save(state)

    context, approved = [], {}
    for cfg in CFG["agents"]:
        a = byid[cfg["id"]]
        gate = cfg.get("needs_approval_from")
        if gate and approved.get(gate) is False:
            a["last_task"] = f"Menunggu revisi dari {gate.capitalize()}"
            state["log"].append({"t": now().strftime("%H:%M"), "agent": a["id"], "text": a["last_task"]})
            continue
        a["state"], a["last_task"] = "kerja", cfg["task"][:90]
        save(state)
        prompt = (f"Niche: {CFG['niche']}\n\nData performa:\n{perf_text}\n\n"
                  f"Hasil rekan sebelumnya:\n{chr(10).join(context) or '(belum ada)'}\n\nTugasmu: {cfg['task']}")
        try:
            text = ask(SYSTEM.format(name=a["name"], role=a["role"]), prompt) or DEMO_TEXT[a["id"]]
        except Exception as e:  # tampilkan error di dashboard, hentikan shift
            a["state"], a["output"] = "error", str(e)
            state["log"].append({"t": now().strftime("%H:%M"), "agent": a["id"], "text": f"Gagal: {e}"[:140]})
            save(state)
            sys.exit(1)
        a["state"], a["output"] = "selesai", text
        if a["id"] == "zaki":
            approved["zaki"] = text.upper().lstrip().startswith("KEPUTUSAN: SETUJU")
        state["log"].append({"t": now().strftime("%H:%M"), "agent": a["id"], "text": text.splitlines()[0][:140]})
        context.append(f"[{a['name']} - {a['role']}]\n{text[:1500]}")
        save(state)
        if not DEMO:
            time.sleep(7)  # jaga batas kecepatan paket gratis

    day = now().strftime("%Y-%m-%d")
    hasil = ROOT / "docs" / "hasil"
    hasil.mkdir(exist_ok=True)
    (hasil / f"{day}.md").write_text(
        "\n\n".join(f"## {a['name']} ({a['role']})\n\n{a['output']}" for a in agents if a["output"]),
        encoding="utf-8")
    print("Shift selesai:", OUT)


if __name__ == "__main__":
    main()
