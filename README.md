# Kantor AI (Agent HQ) gratis

Tim agen AI yang kerja otomatis tiap malam, dengan denah kantor yang bisa dibuka di HP.
Alur shift: Gilang (analisis) -> Dion & Mila (ide) -> Ale (naskah) -> Zaki (review) -> Rara (editor video) -> Bima (antrean posting).

Semua gratis: Gemini API (paket gratis), GitHub Actions, GitHub Pages.

## Pasang dari HP (tanpa komputer)

1. Buat API key gratis di https://aistudio.google.com/apikey
2. Di GitHub buat repo baru (mis. `kantor-ai`), lalu upload semua file di folder ini (Add file > Upload files). Pastikan folder `.github/workflows` ikut terunggah; jika tidak, buat file `shift-malam.yml` lewat Add file > Create new file dengan path `.github/workflows/shift-malam.yml`.
3. Settings > Secrets and variables > Actions > New repository secret. Nama: `GEMINI_API_KEY`, isi: key tadi.
4. Settings > Pages > Source: Deploy from a branch, branch `main`, folder `/docs`.
5. Tab Actions > Shift Malam > Run workflow untuk tes pertama. Jadwal otomatis: tiap 19.00 WIB.
6. Buka `https://USERNAME.github.io/kantor-ai/` untuk melihat kantornya.

## Sesuaikan

- `config.json`: niche, nama agen, tugas tiap agen. Menambah agen = menambah satu blok (ruang yang tersedia di denah: konten, brainstorm, kreatif, brain, sosmed, mess).
- `data/performa.txt`: tempel data performa konten (judul/hook, views). Tanpa data, Gilang hanya memberi asumsi umum dan menyebutnya jelas.
- Hasil tiap malam tersimpan di `docs/hasil/TANGGAL.md`.

## Uji tanpa API

`python run_agents.py --demo` mengisi status contoh (dashboard menampilkan lencana "Data contoh").

## Video otomatis

Setelah Zaki setuju, Rara mengubah naskah Ale menjadi video kartun vertikal 720x1280: maskot "Bubu" bicara dengan mulut mengikuti suara (suara Indonesia gratis lewat edge-tts), berkedip dan melambai, benda (uang, toko, ponsel, bohlam) muncul memantul, dan teks tersorot kata per kata. Semua digambar lewat kode (`make_video.py`, Pillow + numpy) dan disusun ffmpeg. Hasilnya `docs/video/terbaru.mp4`, bisa diputar di dashboard (ketuk Rara). Satu video per shift, ditimpa video berikutnya, jadi unduh dulu kalau mau disimpan. Jika suara gagal dibuat, video tetap jadi (mulut tetap bergerak) tanpa suara, dan dashboard menyebutnya.

## Batasan

- Animasi sederhana ala kartun explainer (satu maskot), bukan animasi studio. Agen tidak memposting sendiri; antrean dari Bima kamu posting manual atau sambungkan ke alat lain.
- Batas kecepatan paket gratis Gemini bisa berubah; skrip sudah memberi jeda dan mencoba ulang saat kena limit.
- Jadwal GitHub Actions bisa telat beberapa menit.
