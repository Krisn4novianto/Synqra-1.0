# HOW_TO — GetFTPReport (Server 205 / Localhost)

Dokumentasi ini mengikuti `GetFTPReport_SOP_Backup.py` versi terbaru. Komentar SOP di dalam script tetap menjadi acuan teknis.

## 1. Persiapan

Tempatkan script di `activities/DataSourceDistributor/python/`. Jika ingin menjalankannya dengan nama `GetFTPReport.py`, ganti nama file `GetFTPReport_SOP_Backup.py` menjadi `GetFTPReport.py` terlebih dahulu.

Pastikan `db_config.py` dan `db_connection.py` tersedia di root proyek. Akun SQL Server harus dapat mengakses database `DataSourceDistributor`, membaca dan mengubah `dbo.ParamFitur` serta `dbo.ParamFTP`, menjalankan `dbo.fnEncrypt`, dan **membuat tabel backup** dengan `SELECT INTO` pada schema `dbo`.

Dari root proyek:

```bash
./.venv/bin/python activities/DataSourceDistributor/python/GetFTPReport.py
```

Atau jalankan nama file aslinya jika belum diganti:

```bash
./.venv/bin/python activities/DataSourceDistributor/python/GetFTPReport_SOP_Backup.py
```

## 2. Alur wizard — enam tahap

1. **Tahap 1 — Koneksi.** Pilih **Server 205** (`172.18.135.205:1433`) atau **Localhost** sesuai `db_config.py`. Program memverifikasi bahwa koneksi mengarah ke `DataSourceDistributor` dan kedua tabel tersedia.
2. **Tahap 2 — Menu utama.** Pilih `1. INSERT KONFIGURASI BARU`, `2. UPDATE KONFIGURASI`, atau `0. KELUAR`. Untuk UPDATE, pilih tabel `ParamFitur` atau `ParamFTP`.
3. **Tahap 3 — Cari atau pilih record.** INSERT dapat menggunakan `ParamFitur` yang sudah ada berdasarkan `DBName` atau membuat record baru. UPDATE ParamFTP mencari record menurut modul, alamat FTP, nama file, atau DBName terkait, lalu memilih ParamFitur yang dipakai.
4. **Tahap 4 — Isi konfigurasi.** Isi field ParamFTP atau field ParamFitur yang akan diubah. Saat UPDATE ParamFTP, Enter pada `FTPPass` mempertahankan password lama. Jika `FTPAddress` berubah, isi `FTPPass` baru agar enkripsi sesuai. Saat UPDATE ParamFitur, perubahan `IPServer` mengharuskan pengisian `DBPass` baru.
5. **Tahap 5 — Preview dan persetujuan eksekusi.** Periksa data lama dan perubahan yang direncanakan. Password tidak ditampilkan. Pilih jalankan, ulangi input, atau kembali. **Backup belum dibuat jika eksekusi belum disetujui.**
6. **Tahap 6 — Backup, transaksi, verifikasi.** Setelah pengguna memilih jalankan, wizard membuat backup kondisi sebelum perubahan; lalu menjalankan INSERT/UPDATE dalam transaksi, menampilkan hasil SELECT aktual, dan meminta keputusan `COMMIT` atau `ROLLBACK`.

`B` pada prompt non-password membatalkan input. `~` pada field opsional berarti mengosongkan nilai. Password dimasukkan melalui prompt tersembunyi.

## 3. SOP backup otomatis di SQL Server

Backup **berjalan langsung pada database `DataSourceDistributor`**, sebelum transaksi perubahan dimulai. Snapshot dibuat sebagai tabel baru dengan pola:

```sql
-- Contoh nama, bukan nama tetap:
dbo.ParamFitur_Backup_YYYYMMDD_HHMMSS_mikrodetik_<id>
dbo.ParamFTP_Backup_YYYYMMDD_HHMMSS_mikrodetik_<id>
```

| Operasi | Tabel yang disalin sebelum perubahan |
| --- | --- |
| INSERT ParamFTP (ParamFitur lama maupun baru) | `dbo.ParamFitur`, `dbo.ParamFTP` |
| UPDATE ParamFTP | `dbo.ParamFitur`, `dbo.ParamFTP` |
| UPDATE ParamFitur | `dbo.ParamFitur` |

Urutan pelaksanaan:

1. Operator memeriksa preview dan menyetujui **JALANKAN PERUBAHAN**.
2. Wizard menjalankan `SELECT * INTO` untuk membuat snapshot **data lama**, dan memeriksa jumlah record snapshot terhadap sumber.
3. Bila backup gagal, operasi INSERT/UPDATE **dibatalkan**. Periksa kemungkinan tabel snapshot parsial yang sudah terbuat.
4. Setelah backup berhasil, wizard memulai transaksi INSERT/UPDATE pada tabel utama.
5. Wizard memverifikasi hasil SELECT aktual sebelum COMMIT.
6. Pilihan **COMMIT** menyimpan perubahan utama; pilihan **ROLLBACK** membatalkannya. Snapshot backup **tetap tersimpan** dalam kedua kasus.

**Penting:** Snapshot adalah salinan seluruh baris pada tabel terkait sebelum perubahan, **bukan** data hasil INSERT/UPDATE dan **bukan** tambahan baris pada tabel utama. Pembuatan backup berulang akan menghasilkan tabel snapshot baru dan menggunakan ruang penyimpanan database. `SELECT INTO` tidak menyalin indeks, constraint, trigger, atau permission; ini juga bukan backup database `.bak`. Pengembalian data dari snapshot perlu prosedur restore yang direncanakan dan diuji tersendiri.

## 4. Enkripsi dan pengamanan password

- `DBPass`: `dbo.fnEncrypt(password, IPServer + 'BR!')`.
- `FTPPass`: `dbo.fnEncrypt(password, FTPAddress + 'BR!')`.
- Password disembunyikan dari preview dan SELECT yang ditampilkan.
- SQL deployment menggunakan variabel SQLCMD `$(DBPASS)` atau `$(FTPPASS)` **hanya bila diperlukan**; password asli tidak ditulis ke file SQL.
- Perlakukan tabel backup sebagai data sensitif: snapshot dapat berisi ciphertext password dan data konfigurasi internal. Batasi akses dan tetapkan kebijakan retensi.

## 5. SQL deployment setelah COMMIT

Setelah COMMIT berhasil, wizard mencoba membuat file SQL deployment untuk **INSERT/UPDATE ParamFTP dan UPDATE ParamFitur** di:

```text
activities/DataSourceDistributor/python/output/01_Reconciliation/GetFTPReport/
```

Nama file menggunakan pola:

```text
GetFTPReport_<AKSI>_YYYYMMDD_HHMMSS_mikrodetik.sql
```

Script deployment juga membuat snapshot backup sebelum perubahan, lalu menjalankan transaksi dan verifikasi. Jika perlu membuat/mengganti password, jalankan dalam **SQLCMD mode** dan sediakan variabel `DBPASS` dan/atau `FTPPASS` dengan cara aman. Jangan memasukkan password asli ke version control atau membagikan command line yang memaparkan rahasia.

**Perhatikan:** COMMIT ke database live sudah permanen meskipun penulisan file deployment setelahnya gagal; kegagalan pembuatan file tidak otomatis membatalkan COMMIT.

## 6. Pemeriksaan setelah eksekusi

Untuk memeriksa tabel snapshot terbaru pada database yang dipilih:

```sql
USE [DataSourceDistributor];
SELECT name, create_date
FROM sys.tables
WHERE schema_id = SCHEMA_ID('dbo')
  AND (name LIKE 'ParamFitur[_]Backup[_]%'
       OR name LIKE 'ParamFTP[_]Backup[_]%')
ORDER BY create_date DESC;
```

Untuk memeriksa jumlah record pada snapshot tertentu, gunakan nama tabel aktual dari hasil query di atas:

```sql
SELECT COUNT_BIG(*) AS JumlahBackup
FROM dbo.[ParamFTP_Backup_NAMA_AKTUAL];
```

Jangan menjalankan file deployment kembali ke database yang sudah diubah tanpa meninjau target dan dampaknya; file deployment adalah artefak untuk penerapan konfigurasi pada target yang sesuai.

## 7. Batasan dan SOP operasional

- UPDATE ParamFTP hanya dijalankan jika kombinasi `LogActivityModul` dan `LogActivitySubModul` mengidentifikasi tepat satu record.
- Validasi aplikasi mengurangi risiko duplikasi, tetapi perlindungan menyeluruh terhadap transaksi paralel juga bergantung pada constraint dan konfigurasi database.
- Snapshot `SELECT INTO` merupakan salinan data pada saat eksekusi, bukan pengganti backup database atau jaminan konsistensi lintas tabel ketika ada transaksi lain yang berjalan.
- Tabel snapshot yang sudah dibuat tetap ada setelah ROLLBACK. Bersihkan hanya berdasarkan SOP retensi yang disetujui; jangan hapus secara otomatis tanpa kebutuhan bisnis.
- Uji pada **development** sebelum produksi: izin membuat tabel, struktur kolom, enkripsi, validasi hasil, jalur COMMIT/ROLLBACK, dan deployment SQLCMD.
