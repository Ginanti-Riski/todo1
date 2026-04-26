# Maria Todo App 💜
**FastAPI + PostgreSQL — Deploy ke Render (Gratis)**

---

## 📁 Struktur Project

```
maria-todo/
├── main.py              ← Backend FastAPI
├── requirements.txt     ← Dependencies Python
├── render.yaml          ← Config deploy otomatis
└── templates/
    └── index.html       ← Frontend mobile-first
```

---

## 🚀 Cara Deploy ke Render (step by step)

### 1. Upload ke GitHub
1. Buka **github.com** → New Repository → nama: `maria-todo`
2. Di folder project ini, jalankan:
   ```bash
   git init
   git add .
   git commit -m "first commit"
   git branch -M main
   git remote add origin https://github.com/USERNAME/maria-todo.git
   git push -u origin main
   ```

### 2. Deploy di Render
1. Buka **render.com** → Sign Up dengan GitHub (gratis)
2. Klik **"New +"** → pilih **"Blueprint"**
3. Connect ke repo `maria-todo`
4. Render akan baca `render.yaml` dan otomatis buat:
   - Web Service (FastAPI)
   - PostgreSQL Database
5. Klik **"Apply"** → tunggu ~3 menit

### 3. Selesai! 🎉
URL app kamu akan seperti: `https://maria-todo.onrender.com`

---

## ⚙️ Environment Variables (opsional, kalau mau email)

Di Render Dashboard → Web Service → Environment:
| Key | Value |
|-----|-------|
| `SMTP_USER` | email Gmail kamu |
| `SMTP_PASS` | App Password Gmail |
| `NOTIFY_EMAIL` | email tujuan notifikasi |

**Cara buat Gmail App Password:**
Gmail → Settings → Security → 2-Step Verification → App Passwords

---

## 🔧 Jalankan Lokal

```bash
# Install dependencies
pip install -r requirements.txt

# Jalankan (pakai SQLite lokal, tidak perlu PostgreSQL)
python main.py

# Buka browser: http://localhost:8000
```

---

## 📱 Fitur

- ✅ **Mobile-first** — nyaman di iPhone & Android
- ✅ **Auto pindah ke "Now"** — kalau tanggal sudah tiba, kartu otomatis pindah
- ✅ **Dark mode** — toggle dari topbar
- ✅ **Email notifikasi** — H-1 sebelum jadwal
- ✅ **Kanban board** — drag & drop status
- ✅ **Bottom navigation** — seperti app native

---

## 💡 Logika Tanggal

| Kondisi | Status |
|---------|--------|
| `scheduled_date > hari ini` | **Future** (jadwal mendatang) |
| `scheduled_date == hari ini` | **Now** (langsung muncul hari ini) |
| `scheduled_date < hari ini` | **Now** (sudah lewat, otomatis dipindah) |
| Selesai diklik | **Completed** |

Scheduler berjalan setiap pukul 08.00 untuk:
1. Memindahkan kartu Future → Now yang sudah tiba tanggalnya
2. Kirim email/notifikasi untuk kartu **besok**
