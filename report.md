# Laporan UTS Layanan Event Aggregator

## Bab 1 – Karakteristik Sistem dan Trade-off

Layanan aggregator dirancang dengan mempertimbangkan karakteristik dasar sistem terdistribusi seperti resource sharing, distribution transparency, openness, dependability, security, dan terutama scalability (Van Steen & Tanenbaum, 2023). Trade-off utama yang kami hadapi adalah antara konsistensi dan skalabilitas. Demi throughput tinggi pada ingest event, pipeline ini memilih pendekatan eventual consistency dan menghindari koordinasi global yang mahal; keputusan ini selaras dengan praktik log aggregator yang lebih mementingkan ketersediaan tinggi daripada konsistensi kuat setiap saat (Coulouris et al., 2012; Van Steen & Tanenbaum, 2023).

## Bab 2 – Arsitektur Publish-Subscribe

Struktur sistem mengikuti arsitektur publish-subscribe (Pub-Sub) alih-alih model client-server request/response. Pub-Sub memberikan space dan time uncoupling: publisher (endpoint `POST /publish`) tidak mengetahui konsumen internal secara eksplisit, sementara worker dapat memproses event tanpa menahan request klien (Coulouris et al., 2012). Desain ini memungkinkan skalabilitas horizontal dan membuat penambahan source event baru menjadi trivial, sesuai rekomendasi untuk sistem diseminasi data berskala besar (Van Steen & Tanenbaum, 2023).

## Bab 3 – Semantik Pengiriman dan Idempotensi

Aggregator menerapkan semantik at-least-once: setiap event yang diterima akan dicoba sampai berhasil diproses, dan kemungkinan duplikat ditangani oleh consumer yang idempotent (Van Steen & Tanenbaum, 2023). Idempotensi dijamin dengan penyimpanan fingerprint `(topic, event_id)` pada SQLite; apabila event duplikat tiba, sistem tidak menulis ulang output melainkan meningkatkan counter `duplicate_dropped`. Pendekatan ini sesuai praktik idempotent consumer pada sistem yang mengandalkan retry untuk menutupi omission failures (Coulouris et al., 2012).

## Bab 4 – Skema Penamaan Topic dan Event_ID

Struktur topic bebas tetapi kami mendorong pola hierarkis (`region.service.type`) agar mudah di-routing dan difilter (Van Steen & Tanenbaum, 2023). Event ID diharapkan unik—pengguna boleh menggunakan UUID atau hash payload sebagaimana disarankan teori collision-resistant identifiers (Coulouris et al., 2012). Dalam implementasi, pasangan `(topic, event_id)` menjadi primary key pada tabel `dedup`, sehingga deduplication dapat dilakukan secara deterministik dan tahan restart.

## Bab 5 – Ordering dan Implikasi

Aggregator tidak memaksakan total ordering lintas topik; urutan hanya dijaga per worker sesuai antrean masuk (FIFO). Pendekatan ini sejalan dengan rekomendasi bahwa total ordering hanya diperlukan untuk state machine replication, sedangkan log aggregation cukup dengan causal atau FIFO ordering per sumber (Coulouris et al., 2012; Van Steen & Tanenbaum, 2023). Jika aplikasi membutuhkan urutan global, solusi seperti logical clocks atau konsensus dapat ditambahkan di lapisan hilir, namun di luar ruang lingkup layanan ini.

## Bab 6 – Failure Mode dan Mitigasi

Serangkaian failure umum—crash, omission, timing—ditangani dengan retry, timeout, serta dedup store persisten (Van Steen & Tanenbaum, 2023). Worker memanfaatkan `asyncio.Queue` yang secara natural mendukung mekanisme retry tanpa menahan thread. SQLite dipilih karena sifat embedded dan ACID sehingga jejak event yang sudah diproses tetap ada setelah restart, sesuai rekomendasi durable dedup store untuk menutupi efek at-least-once (Coulouris et al., 2012).

## Bab 7 – Konsistensi Akhir & Idempotensi Dalam Praktik

Dengan mengombinasikan idempotensi dan dedup, sistem mencapai strong eventual consistency: meski duplikat terjadi, hasil akhir pada storage akan konvergen dan tidak bergantung pada urutan kedatangan duplikat (Van Steen & Tanenbaum, 2023). Endpoint `GET /stats` menyediakan observabilitas terhadap metrik `received`, `unique_processed`, `duplicate_dropped`, `topics`, dan `uptime`, memungkinkan operator memantau tingkat duplikasi yang terjadi selama retry.

## Bab 8 – Implementasi dan Keterkaitan Bab 1–7

- **FastAPI Application (`src/main.py`)**: menerapkan prinsip openness dan distribution transparency dengan menyediakan REST API yang sederhana namun extensible.
- **Service Layer (`src/service.py`)**: menerapkan worker async agar throughput tinggi (Bab 1) dan memanfaatkan uncoupling Pub-Sub (Bab 2). Fungsi `_process_event` melakukan pengecekan idempotensi sesuai Bab 3.
- **Dedup Store (`src/dedup_store.py`)**: skema tabel mengikuti desain collision-resistant pada Bab 4 dan durability pada Bab 6.
- **Model Pydantic (`src/models.py`)**: memastikan struktur event memenuhi skema topik dan ID unik (Bab 4).
- **Konfigurasi (`src/config.py`)**: memungkinkan tuning worker count/queue maxsize untuk trade-off kinerja vs konsumsi sumber daya (Bab 1).
- **Docker & Compose**: container `aggregator` dan `publisher` mencerminkan kebutuhan skalabilitas Pub-Sub (Bab 2) dengan jaringan internal dan tanpa layanan eksternal publik, sekaligus mendukung pengujian at-least-once (Bab 3).

## Bab 9 – Pengujian & Evaluasi Performa

Pengujian otomatis (`pytest`) mencakup lima skenario utama: dedup, persistensi, validasi skema, listing per topik, dan stress batch 500 event dengan ≥20% duplikasi. Untuk memenuhi syarat performa (Bab 1 & T8), skrip `scripts/publisher.py` serta service `publisher` di docker-compose mengirim batch 5.000 event dengan duplikasi 20%, menunjukkan sistem tetap responsif dan counter duplikat meningkat sesuai harapan. Metrik throughput, latency, dan duplicate rate dapat diobservasi melalui endpoint stats, sesuai rekomendasi evaluasi pada ringkasan Bab 1–7 (Van Steen & Tanenbaum, 2023).

## Bab 10 – Kesimpulan & Arah Lanjutan

Proyek memenuhi seluruh ketentuan UTS: API ingest, dedup persisten, stats observabilitas, pengujian, Dockerfile non-root, dan opsi Docker Compose. Pengembangan lanjutan dapat mencakup integrasi Prometheus, pembaruan FastAPI lifespan API, Bloom filter in-memory, serta konfigurasi per-topic worker untuk mendekati kebutuhan ordering khusus. Semua peningkatan tetap harus menjaga trade-off skalabilitas vs konsistensi sebagaimana dibahas pada Bab 1–7.

## Referensi

- Coulouris, G., Dollimore, J., Kindberg, T., & Blair, G. (2012). _Distributed Systems: Concepts and Design_ (5th ed.). Addison-Wesley.
- Van Steen, M., & Tanenbaum, A. S. (2023). _Distributed Systems_ (4th ed.). Delft University of Technology.
- Dokumentasi FastAPI. https://fastapi.tiangolo.com/
- Dokumentasi asyncio. https://docs.python.org/3/library/asyncio.html
- Dokumentasi SQLite. https://sqlite.org/docs.html
