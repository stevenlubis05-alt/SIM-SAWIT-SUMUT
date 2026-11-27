# 🌴 SIM-SAWIT SUMUT — Dashboard Streamlit

Dashboard interaktif untuk menampilkan dan menganalisis data kelapa sawit Sumatera Utara. Aplikasi membaca tiga tabel dari database pusat Neon PostgreSQL:

1. `sawit_kecamatan_pusat` — data luas, produksi, dan harga pada tingkat kecamatan.
2. `sawit_kabupaten` — rekap luas dan produksi pada tingkat kabupaten.
3. `harga_tbs_kabupaten` — harga TBS per kabupaten dan periode.

## Fitur

- Ringkasan KPI produksi, luas, produktivitas, dan jumlah kabupaten.
- Grafik perbandingan produksi, luas, produktivitas, dan harga TBS.
- Filter kabupaten dan tahun.
- Tabel interaktif dan unduhan CSV.
- Analisis kualitas: nilai kosong, perbedaan tahun harga dengan tahun produksi, dan penanda produktivitas di luar 10–30 ton/ha.
- Tampilan data referensi lokal saat Neon belum dikonfigurasi.

## Struktur folder

```text
SIM_SAWIT_SUMUT/
├── streamlit_app.py
├── requirements.txt
├── README.md
├── .gitignore
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml.example
├── data/
│   ├── kabupaten_referensi.csv
│   ├── kecamatan_referensi.csv
│   └── harga_tbs_referensi.csv
└── database/
    └── cek_database_pusat.sql
```

## A. Menjalankan di komputer (opsional untuk uji coba)

1. Ekstrak folder proyek.
2. Pastikan Python 3.10 atau lebih baru sudah terpasang.
3. Buka terminal pada folder `SIM_SAWIT_SUMUT`.
4. Instal pustaka:

   ```bash
   pip install -r requirements.txt
   ```

5. Untuk menjalankan tanpa Neon, aplikasi otomatis menggunakan CSV referensi di folder `data`.
6. Jalankan aplikasi:

   ```bash
   streamlit run streamlit_app.py
   ```

7. Browser akan membuka alamat lokal Streamlit (umumnya `http://localhost:8501`).

## B. Mengunggah proyek ke GitHub

1. Masuk ke [GitHub](https://github.com/) dan login.
2. Klik **New repository**.
3. Beri nama repository, misalnya `sim-sawit-sumut`.
4. Pilih **Public** atau **Private**, lalu klik **Create repository**.
5. Pada halaman repository, pilih **Add file → Upload files**.
6. Buka folder proyek di komputer. Unggah seluruh isi folder, termasuk folder `.streamlit`, `data`, dan `database`. Pastikan `streamlit_app.py` dan `requirements.txt` berada di root repository.
7. Klik **Commit changes**.

> Jangan unggah file `.streamlit/secrets.toml` atau connection string Neon ke GitHub. File rahasia lokal sudah dimasukkan ke `.gitignore`.

## C. Menghubungkan ke Neon

1. Buka project Neon dan masuk ke database pusat `db_pusat_sumut`.
2. Klik **Connect**, pilih database dan role yang benar, kemudian salin connection string PostgreSQL.
3. Pastikan database pusat memiliki tiga tabel yang disebut di atas. File `database/cek_database_pusat.sql` berisi query pemeriksaan.
4. Pastikan role database mempunyai izin `SELECT` pada ketiga tabel.
5. Jangan menaruh connection string langsung di dalam `streamlit_app.py`.

### Jika diuji secara lokal

1. Salin `.streamlit/secrets.toml.example` menjadi `.streamlit/secrets.toml`.
2. Ganti nilai contoh dengan connection string Neon milik Anda:

   ```toml
   NEON_CONNECTION_STRING = "postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require"
   ```

3. Jalankan kembali `streamlit run streamlit_app.py`.

### Jika di-deploy ke Streamlit Community Cloud

1. Buka [share.streamlit.io](https://share.streamlit.io/) dan login menggunakan GitHub.
2. Klik **Create app**.
3. Pilih repository `sim-sawit-sumut`, branch `main`, dan file utama `streamlit_app.py`.
4. Sebelum/ketika deploy, buka **Advanced settings** atau menu **App settings → Secrets** (label menu dapat berubah).
5. Tempel isi berikut dan ganti dengan connection string Neon Anda:

   ```toml
   NEON_CONNECTION_STRING = "postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require"
   ```

6. Simpan Secrets, lalu klik **Deploy** atau **Reboot app** jika aplikasi sudah dibuat.
7. Buka URL `*.streamlit.app` yang diberikan.

Panduan resmi: [Deploy app](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app) dan [Connect PostgreSQL](https://docs.streamlit.io/develop/tutorials/databases/postgresql).

## D. Cara membaca dashboard

- **Ringkasan:** indikator utama dihitung dari tahun terbaru yang tersedia pada tabel kabupaten.
- **Analisis Kabupaten:** pilih tahun dan wilayah untuk membandingkan luas, produksi, dan produktivitas.
- **Data Kecamatan:** telusuri data per kecamatan. `NULL` berarti belum tersedia, bukan nol.
- **Harga TBS:** bandingkan harga berdasarkan periode, dengan keterangan tingkat kabupaten.
- **Kualitas Data:** periksa kelengkapan, kecocokan tahun, dan anomali produktivitas.
- **Tentang Sistem:** lihat penjelasan dan status tabel.

## Catatan penting tentang data referensi bawaan

CSV pada folder `data` hanya berisi data referensi yang tercantum dalam bahan proyek:

- Data kabupaten: lima kabupaten pada tahun 2021 dan 2024.
- Langkat: 12 baris luas tanaman menghasilkan dan produksi tahun 2017.
- Labuhanbatu Selatan: lima baris luas kecamatan tahun 2020, tanpa angka produksi.
- Harga TBS: harga tingkat kabupaten periode November 2025.

Data tersebut **tidak memenuhi** syarat empat kecamatan dengan luas, produksi, dan harga pada tahun yang sama. Dashboard sengaja memperlihatkan kekurangan tersebut. Jangan menganggap data dari tahun atau tingkat wilayah berbeda sebagai satu observasi setara.

## Troubleshooting singkat

| Kendala | Yang perlu diperiksa |
|---|---|
| Dashboard memakai data referensi lokal | Connection string belum ditambahkan / salah, atau tabel Neon kosong/tidak ditemukan. |
| `relation does not exist` | Pastikan nama tabel dan schema sama. Default aplikasi membaca tabel pada schema `public`. |
| `password authentication failed` | Salin ulang connection string dari Neon dan pastikan role/password benar. |
| `permission denied` | Berikan izin `SELECT` pada tabel untuk role yang dipakai aplikasi. |
| Grafik kosong | Pastikan kolom numerik (luas, produksi, harga) terisi dengan tipe angka. |
| Perubahan data belum terlihat | Klik tombol **Muat ulang data** pada sidebar; cache aplikasi disegarkan. |

