# HOW TO / SOP — RekonParam.py (satu file)

## 1. Persiapan
Simpan `RekonParam.py` ke `activities/RekonParam/python/RekonParam.py` di dalam repository yang memiliki `db_config.py`, `db_connection.py`, dan `activities/RekonParam/common.py`. Pastikan profil server `172.18.135.205` atau `localhost` ada di `db_config.SERVERS` dan akun database memiliki izin yang diperlukan. Uji di localhost sebelum produksi.

## 2. Jalankan
Dari root repository:

```bash
./.venv/bin/python activities/RekonParam/python/RekonParam.py
```

Windows:

```powershell
.\.venv\Scripts\python.exe activities\RekonParam\python\RekonParam.py
```

## 3. Pilih server dan operasi
Pilih profil server dari daftar (password koneksi diambil dari `db_config.py`). Pilih `INSERT` atau `UPDATE`, lalu tabel `ParamFitur` atau `ParamJoin`.

- **INSERT ParamFitur**: pilih preset; lihat preview.
- **INSERT ParamJoin**: pilih ParamFitur existing; isi kolom ParamJoin.
- **UPDATE ParamFitur**: filter record, pilih record dan field yang akan diubah.
- **UPDATE ParamJoin**: filter record, pilih record, lalu edit kolom yang diperlukan.

## 4. Backup, preview, dan transaksi
Periksa preview dan ketik `YA` untuk menjalankan perubahan sementara. Program membuat snapshot JSON **sebelum** perubahan SQL pada operasi terkait. Lihat hasil aktual sebelum commit. Ketik **`COMMIT`** untuk menyimpan, atau masukkan nilai lain untuk **`ROLLBACK`**.

Backup disimpan di `output/RekonParam/backup/`. Snapshot memuat data terkait dan mungkin berisi informasi sensitif termasuk nilai `DBPass` terenkripsi; lindungi folder backup dan jangan commit ke Git.

## 5. Deployment SQL
Script deployment dibuat di `output/RekonParam/` **hanya setelah COMMIT berhasil**. Script default menggunakan `ROLLBACK` dan harus direview sebelum dijalankan di target. Deployment ParamFitur baru mungkin memerlukan penyediaan password secara aman pada target; jangan menyisipkan password ke berkas SQL.

## 6. Restore dan penanganan error
Snapshot JSON **bukan** file backup native SQL Server `.bak`, dan belum tersedia restore otomatis. Pemulihan dilakukan melalui prosedur DBA dengan memeriksa snapshot, kondisi data saat ini, constraint, dan trigger. Jika transaksi gagal sebelum COMMIT, lakukan/konfirmasi ROLLBACK. Jika error setelah COMMIT, data sudah tersimpan dan memerlukan penanganan tersendiri.

## 7. Pemeriksaan sebelum produksi
Uji INSERT + ROLLBACK, INSERT + COMMIT, UPDATE + ROLLBACK, UPDATE + COMMIT pada localhost. Verifikasi snapshot, hasil SQL, dan deployment script. Pengujian langsung terhadap database asli belum dilakukan di sini.
