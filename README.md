# Cyber Security News Bot

Bot otomatis yang mengambil berita terbaru tentang cyber security dari berbagai sumber RSS feed, lalu mengirimkan notifikasi ke WhatsApp (pribadi dan grup) menggunakan GREEN API.

## Fitur

- Mengambil berita dari 6+ sumber cyber security terpercaya
- Mengirim sebagai **gambar + caption detail** (thumbnail artikel + judul, sumber, tanggal, kategori, ringkasan, link)
- Fallback ke teks biasa jika artikel tidak memiliki gambar
- Mendukung pengiriman ke **nomor pribadi dan grup WhatsApp**
- Berjalan otomatis setiap 30 menit via GitHub Actions
- Tracking artikel yang sudah dikirim (tidak ada duplikasi)
- Gratis: GitHub Actions + GREEN API Developer plan

## Sumber Berita

| Sumber | URL |
|--------|-----|
| The Hacker News | https://thehackernews.com |
| BleepingComputer | https://bleepingcomputer.com |
| Krebs on Security | https://krebsonsecurity.com |
| Dark Reading | https://darkreading.com |
| The CyberWire | https://thecyberwire.com |
| CISA Alerts | https://cisa.gov |

Sumber bisa ditambah/dihapus di `config/feeds.yaml`.

## Setup

### 1. Daftar GREEN API

1. Buka [console.green-api.com](https://console.green-api.com) dan buat akun
2. Buat instance baru (pilih plan **Developer** / gratis)
3. Scan QR code dengan WhatsApp di HP Anda
4. Catat **Instance ID** dan **API Token Instance**

### 2. Dapatkan Group ID (opsional)

Jika ingin kirim ke grup WhatsApp, jalankan script helper:

```bash
# Set credentials
export GREEN_API_INSTANCE_ID="your_instance_id"
export GREEN_API_TOKEN="your_api_token"

# Install dependencies
pip install -r requirements.txt

# Jalankan helper
python scripts/get_groups.py
```

Output akan menampilkan semua grup beserta ID-nya.

### 3. Setup GitHub Repository

1. Push kode ini ke repository GitHub (public)

2. Buka **Settings > Secrets and variables > Actions**

3. Tambahkan 3 secrets:

   | Secret Name | Value | Contoh |
   |-------------|-------|--------|
   | `GREEN_API_INSTANCE_ID` | Instance ID dari console | `1101234567` |
   | `GREEN_API_TOKEN` | API Token dari console | `abcdef123456...` |
   | `WA_RECIPIENTS` | Daftar penerima (satu per baris) | Lihat format di bawah |

4. Format `WA_RECIPIENTS` (satu per baris, campuran pribadi dan grup):

   ```
   6281234567890@c.us
   6289876543210@c.us
   120363194020948049@g.us
   ```

   - `@c.us` = nomor pribadi (format: kode negara + nomor tanpa +/0)
   - `@g.us` = grup WhatsApp (didapat dari `get_groups.py`)

### 4. Aktifkan Workflow

1. Buka tab **Actions** di repository
2. Klik **"I understand my workflows, go ahead and enable them"**
3. Bot akan berjalan otomatis setiap 30 menit
4. Untuk test manual: klik **"Cyber Security News Bot"** > **"Run workflow"**

## Struktur Proyek

```
.github/workflows/
  cybersec-news.yml       # GitHub Actions scheduled workflow
src/
  main.py                 # Entry point / orchestrator
  feed_fetcher.py         # Fetch & parse RSS feeds + extract thumbnails
  state_manager.py        # Track sent articles (anti-duplikasi)
  message_formatter.py    # Format artikel jadi caption WhatsApp
  whatsapp_sender.py      # Kirim pesan via GREEN API
scripts/
  get_groups.py           # Helper: dapatkan Group ID dari WhatsApp
config/
  feeds.yaml              # Daftar RSS feed sources
data/
  sent_articles.json      # State: artikel yang sudah terkirim
```

## Contoh Pesan WhatsApp

Pesan dikirim sebagai gambar (thumbnail artikel) dengan caption:

```
*Judul Artikel Lengkap*

Sumber: The Hacker News
Tanggal: 03 May 2026, 14:30 UTC
Kategori: Malware, Zero-Day, APT

Ringkasan detail artikel yang menjelaskan inti dari berita
cyber security ini, termasuk dampak dan konteks pentingnya...

Baca selengkapnya:
https://link-artikel.com/full-article
```

## Batasan GREEN API (Plan Developer / Gratis)

- Maksimal **3 chat unik per bulan** (pribadi atau grup)
- Unlimited pesan dalam 3 chat tersebut
- Reset setiap tanggal 1 tiap bulan
- Upgrade ke Business ($12/bulan) untuk unlimited chat

## Menambah Sumber Berita

Edit `config/feeds.yaml`:

```yaml
feeds:
  - name: "Nama Sumber"
    url: "https://example.com/rss-feed-url"
```

## Menjalankan Lokal

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export GREEN_API_INSTANCE_ID="your_instance_id"
export GREEN_API_TOKEN="your_api_token"
export WA_RECIPIENTS="6281234567890@c.us"

# Jalankan
cd src
python main.py
```

## Lisensi

MIT License
