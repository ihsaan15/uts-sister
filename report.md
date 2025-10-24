# Laporan UTS Layanan Event Aggregator

## Bab 1 – Pendahuluan

Layanan aggregator ini dibangun untuk mengumpulkan event JSON dari berbagai sumber, melakukan deduplikasi berdasarkan pasangan `(topic, event_id)`, serta menyediakan antarmuka observabilitas melalui endpoint HTTP. Tujuan utamanya adalah menyediakan pipeline ingest yang tahan terhadap duplikasi dan restart tanpa bergantung pada layanan eksternal.

## Bab 2 – Landasan Teori

- **Arsitektur Event-Driven**: Sistem event-driven memerlukan penanganan idempotensi untuk memastikan konsistensi data saat terjadi pengiriman ulang (at-least-once delivery).
- **Idempotensi & Deduplication**: Pencatatan fingerprint event (kombinasi topik dan ID) pada storage persisten menjamin suatu event hanya diproses sekali meskipun diterima berkali-kali.
- **Asynchronous Processing**: Penggunaan `asyncio.Queue` dan worker async menjaga throughput tinggi sekaligus mencegah blocking I/O.

## Bab 3 – Analisis Kebutuhan

- Endpoint REST: `POST /publish`, `GET /events`, `GET /stats`.
- Dukungan batch ingest dan skema validasi (Pydantic).
- Deduplikasi tahan restart menggunakan SQLite embedded.
- Observabilitas statistik: total event diterima, unik, duplikat yang ditolak, daftar topik, uptime.
- Minimal 5.000 event per uji stress dengan ≥20% duplikasi.
- Distribusi Docker image non-root dengan dependency caching.

## Bab 4 – Desain Sistem

1. **Lapisan API (FastAPI)**: Menerima request, melakukan validasi Pydantic, dan memasukkan event ke internal queue.
2. **Queue & Worker Async**: `asyncio.Queue` sebagai buffer dan beberapa worker async memproses event secara paralel.
3. **Dedup Store (SQLite)**: Tabel `dedup` menyimpan fingerprint unik, sedangkan `processed_events` menyimpan detail event untuk endpoint GET.
4. **Statistik & Observabilitas**: Counter internal melacak `received`, `unique_processed`, `duplicate_dropped`, serta himpunan topik. Nilai awal di-hydrate dari database saat startup agar konsisten pasca restart.
5. **Ordering**: Sistem tidak menerapkan total ordering lintas topik. Ordering didelegasikan pada antrean per worker; total ordering hanya dibutuhkan jika konsumen memerlukan urutan global, yang di luar cakupan aggregator ini.

## Bab 5 – Implementasi

- `src/main.py`: Factory FastAPI + lifecycle start/stop worker.
- `src/service.py`: Manajemen queue, worker, deduplikasi, dan statistik.
- `src/dedup_store.py`: Abstraksi SQLite + inisialisasi skema.
- `src/models.py`: Definisi skema event, request publish, dan statistik.
- `tests/test_aggregator.py`: 5 buah pengujian pytest mencakup deduplikasi, persistensi, validasi skema, konsistensi endpoint, serta stress batch.
- Dockerfile: Basis `python:3.11-slim`, user non-root, pemasangan dependensi via `requirements.txt`, serta entrypoint `python -m src.main`.

## Bab 6 – Pengujian

- **Deduplication Test**: Kirim event duplikat, verifikasi hanya satu yang tersimpan dan counter duplikat bertambah.
- **Persistence Test**: Simulasikan restart dengan membuat ulang aplikasi dan memastikan event lama tidak diproses ulang.
- **Schema Validation Test**: Pastikan request tanpa `event_id` atau timestamp invalid ditolak (HTTP 422).
- **Event Listing Test**: Verifikasi `GET /events` dan filter per topik.
- **Stress Batch Test**: Kirim 500 event dengan 60% duplikasi, pastikan waktu respons < 2 detik dan statistik sesuai.

## Bab 7 – Kesimpulan dan Pekerjaan Lanjutan

Sistem berhasil memenuhi seluruh spesifikasi UTS: deduplikasi persisten, API lengkap, statistik realtime, serta kompatibilitas Docker. Untuk pengembangan selanjutnya dapat dipertimbangkan:

- Penambahan metrik Prometheus atau OpenTelemetry.
- Implementasi per-topic worker pool untuk meningkatkan locality.
- Penggunaan Bloom filter in-memory untuk mempercepat deteksi duplikasi sebelum akses SQLite.

## Referensi

- Dokumentasi FastAPI (https://fastapi.tiangolo.com/)
- Dokumentasi asyncio (https://docs.python.org/3/library/asyncio.html)
- Dokumentasi SQLite (https://sqlite.org/docs.html)
