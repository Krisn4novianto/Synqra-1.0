# HOW_TO — ParseFile Wizard (Server 205 / Localhost)

## Lokasi file
Simpan `ParseFile.py` di `activities/DataSourceDistributor/python/ParseFile.py`.

## Menjalankan
Dari root proyek:

```bash
./.venv/bin/python activities/DataSourceDistributor/python/ParseFile.py
```

Script menggunakan `db_config.py` dan `db_connection.py` pada root proyek. Koneksi hanya Server 205 (`172.18.135.205`) dan Localhost (`localhost`), langsung ke database `DataSourceDistributor`.

## Menu
1. **INSERT KONFIGURASI BARU** — pilih/buat `ParamFitur`, buat `ParamParseFile` atau gunakan existing, lalu kelola mapping.
2. **UPDATE KONFIGURASI** — pilih/buat/ubah `ParamFitur`, pilih dan ubah `ParamParseFile` atau gunakan existing, kemudian tambah/ubah mapping.
0. **KELUAR**.

Wizard menggunakan enam tahap: koneksi, menu, ParamFitur, ParamParseFile, mapping, preview dan transaksi.

## Hubungan tabel
- `ParamFitur.IDFitur` dipilih berdasarkan DBName dan IPServer atau dibuat otomatis saat INSERT.
- `ParamParseFile.IDFitur` otomatis memakai IDFitur tersebut.
- `ParamParseFileMappingColumn.IDParamParseFile` otomatis memakai ID record ParamParseFile yang dipilih/dibuat.
- REPLACE dilakukan sebagai UPDATE record existing, bukan DELETE/INSERT.

## Input dan navigasi
Masukkan angka pilihan. `B` atau `0` pada menu pemilihan berarti batal dan kembali ke menu utama, dengan ROLLBACK. Saat UPDATE, Enter melewati kolom; `NULL` mengosongkan kolom nullable. Gunakan `SELESAI PILIH KOLOM` untuk mengakhiri pemilihan kolom.

## Transaksi
Seluruh INSERT/UPDATE dalam satu transaksi pada koneksi live. Hasil SELECT aktual diperlihatkan sebelum COMMIT. Ketik `COMMIT` persis untuk menyimpan; selain itu transaksi di-ROLLBACK.

## Deployment SQL
Setelah COMMIT, file `ParseFile_YYYY-MM-DD_HHMMSS_microseconds.sql` dibuat di `output/01_Reconciliation/ParseFile/`. Nama unik mencegah overwrite. SQL melakukan backup ketiga tabel dengan `SELECT INTO` sebelum transaksi deployment. SQL tidak memuat password baru: jika membuat ParamFitur, deployment memerlukan SQLCMD variable `DBPASS` yang harus disediakan secara aman saat menjalankan script. **Jangan menyimpan password ke repository atau membagikannya.**

**Penting:** Backup tabel otomatis pada script SQL deployment, **bukan** backup tabel live sebelum COMMIT wizard. Pastikan backup live terpisah sesuai SOP lingkungan Anda sebelum menjalankan wizard. `SELECT INTO` tidak menyalin index, constraint, trigger, atau permission.

## Validasi
Sintaks Python diperiksa dengan `py_compile`; koneksi dan perubahan database belum diuji langsung. Uji di lingkungan development terlebih dahulu. Periksa kolom, constraint, dan natural key pada database target deployment sebelum menjalankan SQL.

## Backup Data

Saat operator memilih INSERT atau UPDATE, **sebelum perubahan data apa pun**, wizard
membuat tiga tabel backup langsung pada SQL Server yang dipilih:

- `dbo.ParamFitur_Backup_YYYYMMDD_HHMMSS_microseconds`
- `dbo.ParamParseFile_Backup_YYYYMMDD_HHMMSS_microseconds`
- `dbo.ParamParseFileMappingColumn_Backup_YYYYMMDD_HHMMSS_microseconds`

Backup dibuat dengan `SELECT * INTO` melalui koneksi SQL Server terpisah yang
menggunakan `autocommit=True`. Karena itu backup **tetap tersimpan saat wizard
melakukan ROLLBACK**. Jika backup gagal, wizard membatalkan perubahan konfigurasi.
Backup tetap tersimpan juga setelah COMMIT. Pastikan user SQL memiliki izin
`CREATE TABLE` dan izin yang diperlukan pada schema `dbo`, serta kapasitas disk
mencukupi. `SELECT INTO` hanya menyalin struktur kolom dan data, tidak menyalin
index, constraint, trigger, maupun permission. Backup tidak otomatis dihapus.

File SQL deployment juga tetap membuat backup tersendiri ketika dijalankan pada
environment tujuan.
