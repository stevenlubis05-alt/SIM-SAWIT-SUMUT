-- Jalankan pada database db_pusat_sumut di Neon untuk memastikan tabel tersedia.
SELECT current_database();

SELECT COUNT(*) AS total_data_kecamatan FROM sawit_kecamatan_pusat;
SELECT COUNT(*) AS total_data_kabupaten FROM sawit_kabupaten;
SELECT COUNT(*) AS total_data_harga FROM harga_tbs_kabupaten;

-- Sampel data kecamatan
SELECT kabupaten, kecamatan, tahun, luas_tm_ha, luas_total_ha,
       produksi_ton, harga_tbs_rp_kg, tingkat_harga, periode_harga, sumber_data
FROM sawit_kecamatan_pusat
ORDER BY kabupaten, tahun, kecamatan
LIMIT 30;

-- Rekap kecamatan dengan data luas dan produksi
SELECT kabupaten, tahun,
       COUNT(*) AS jumlah_kecamatan,
       COUNT(*) FILTER (
           WHERE COALESCE(luas_tm_ha, luas_total_ha) IS NOT NULL
             AND produksi_ton IS NOT NULL
       ) AS kecamatan_luas_dan_produksi
FROM sawit_kecamatan_pusat
GROUP BY kabupaten, tahun
ORDER BY kabupaten, tahun;

-- Rekap kabupaten
SELECT kabupaten, tahun, luas_ha, produksi_ton,
       ROUND(produksi_ton / NULLIF(luas_ha, 0), 2) AS produktivitas_ton_ha,
       sumber_data
FROM sawit_kabupaten
ORDER BY tahun DESC, produksi_ton DESC;

-- Rekap harga TBS
SELECT kabupaten, periode, harga_rp_kg, sumber_data
FROM harga_tbs_kabupaten
ORDER BY periode DESC, harga_rp_kg DESC;
