# HOW_TO — ParamCriteria

## Lokasi
Simpan activity ini tetap di folder `ParamCriteria` di dalam project Synqra. Script ini **standalone** dan tidak membutuhkan `settlement_engine.py`.

## Menjalankan
Jalankan dari root project Synqra:

```bash
./.venv/bin/python activities/ParamEngine/python/ParamCriteria/ParamCriteria.py
```

Sesuaikan path di atas bila folder `ParamCriteria` berada di lokasi lain pada project.

## Fitur
- Memakai koneksi pusat project melalui `db_config.py` dan `db_connection.py`.
- Pilihan server melalui menu terminal.
- INSERT satu atau banyak relasi berdasarkan template dependency ParamCriteria.
- UPDATE: pilih kolom filter, tentukan record target, lalu pilih satu atau beberapa kolom yang akan diubah. Kolom yang tidak dipilih tidak disentuh.
- Preview sebelum backup/transaksi, backup tabel, verifikasi, `COMMIT` atau `ROLLBACK`.
- Membuat SQL deployment di folder `output/ParamCriteria` setelah transaksi berhasil.

## Input khusus
- Enter: menggunakan nilai default bila tersedia.
- `.NULL`: SQL NULL.
- `.EMPTY`: string kosong.
- Untuk UPDATE, masukkan nomor kolom filter dipisah koma, lalu nomor kolom yang ingin diubah dipisah koma atau `ALL`.
- Ketik `LANJUT` untuk melanjutkan ke backup dan transaksi; ketik `COMMIT` untuk menyimpan. Input lain akan melakukan rollback.

## Tabel target
Database `ParamEngine`, tabel `dbo.ParamCriteria`. Kolom identitas default terdiri dari `ProductId`, `Task`, `Activity`, `LogActivityProductId`, `LogActivityTask`, dan `LogActivityActivity`.
