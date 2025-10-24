# Event Aggregator Service

Layanan agregator berbasis FastAPI yang menerima event JSON, melakukan deduplikasi berdasarkan `(topic, event_id)`, lalu menyajikan daftar event unik dan statistik layanan. Pipeline menggunakan `asyncio.Queue` dengan penyimpanan dedup berbasis SQLite agar tetap idempotent meskipun layanan direstart.

## Fitur

- `POST /publish` menerima event tunggal maupun batch, memvalidasi skema, lalu memasukkan ke antrean.
- Worker asinkron menjamin _at-least-once delivery_ sambil membuang duplikat dengan cek idempotensi.
- `GET /events?topic=...` mengembalikan event unik yang telah diproses (dapat difilter per topik).
- `GET /stats` menampilkan metrik `received`, `unique_processed`, `duplicate_dropped`, `topics`, dan `uptime`.
- Dedup store SQLite menjaga state idempotensi tetap tersimpan setelah restart/container crash.
- Dockerfile menyiapkan image minimal berbasis `python:3.11-slim` dengan user non-root.
- Suite pytest (async) menguji dedup, persistensi, validasi skema, konsistensi stats, dan stress batch.

## Prasyarat

- Python 3.11+
- `pip` atau Poetry untuk instalasi dependensi (`requirements.txt`)
- Docker & Docker Compose (opsional, untuk menjalankan image/container)

## Pengembangan Lokal

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
python -m src.main
```

Antarmuka interaktif tersedia di `http://localhost:8080/docs`.

### Variabel Lingkungan

- `DEDUP_DB_PATH` (default `data/dedup.sqlite`): lokasi file SQLite dedup.
- `WORKER_COUNT` (default `2`): jumlah worker asinkron.
- `QUEUE_MAXSIZE` (default `0` = tanpa batas): kapasitas antrean internal.

## Menjalankan Pengujian

```powershell
pytest -q
```

## Penggunaan Docker

```powershell
docker build -t uts-aggregator .
docker run -p 8080:8080 -v ${PWD}\data:/app/data uts-aggregator
```

Mount direktori `data/` agar database SQLite bertahan antara restart container.

## Docker Compose (Opsional)

```powershell
docker compose up --build
```

File `docker-compose.yml` menyertakan dua service:

- `aggregator`: layanan FastAPI utama.
- `publisher`: kontainer Python sederhana yang otomatis mengirim batch 5 dan 5000 event (±20% duplikat) melalui skrip `scripts/publisher.py`.

## Skrip Bantu

- `scripts/publisher.py` → kirim batch event untuk demo/stress test. Contoh: `python scripts/publisher.py --counts 5 5000 --duplicates-ratio 0.2`.
- `scripts/curl-demo.ps1` → menjalankan serangkaian perintah `curl` (publish, stats, events) untuk verifikasi cepat.

## Struktur Proyek

```
src/
  config.py        # util konfigurasi & environment
  dedup_store.py   # penyimpanan dedup SQLite persisten
  main.py          # factory & entrypoint FastAPI
  models.py        # model Pydantic untuk event & stats
  service.py       # worker asyncio & statistik layanan
tests/
  test_aggregator.py
scripts/
  publisher.py     # generator batch event demo
  curl-demo.ps1    # contoh uji cepat memakai curl
```

## Catatan Ordering

Aggregator memastikan idempotensi, namun tidak menjamin _global ordering_ lintas topik. Event diproses per worker sesuai urutan masuk. Jika butuh ordering total, jalankan satu worker saja atau buat kanal khusus per topik.

## Demo Video

Tambahkan link YouTube demo di sini setelah rekaman selesai.
