# HOW_TO — DataFlowParam (Server 205 / Localhost)

## Persiapan

Tempatkan `DataFlowParam_SOP_Backup.py` di `activities/DataSourceDistributor/python/` (atau lokasi activity yang digunakan proyek). Pastikan `db_config.py` dan `db_connection.py` ada di root proyek. Script akan mencari kedua modul tersebut pada direktori induk secara otomatis.

Pastikan akun SQL Server mempunyai izin `SELECT`, `INSERT`, `UPDATE`, dan `CREATE TABLE` pada database `DataFlowParam`, termasuk akses ke tabel `dbo.ParamServer`, `dbo.ParamFitur`, `dbo.ParamFiturCekLogActivity`, serta fungsi `dbo.fnEncrypt`. SQL Server juga harus mendukung `SELECT INTO`.

Jalankan dari root proyek:

```bash
./.venv/bin/python activities/DataSourceDistributor/python/DataFlowParam_SOP_Backup.py
```

## Alur wizard

1. **Tahap 1 — Koneksi:** pilih Server 205 (`172.18.135.205:1433`) atau Localhost. Wizard terhubung langsung ke `DataFlowParam` dan memverifikasi tabel.
2. **Menu utama:** pilih INSERT/UPDATE `ParamServer`, `ParamFitur`, `ParamFiturCekLogActivity`, INSERT berantai, atau UPDATE berantai.
3. **Pencarian UPDATE:** pilih satu/beberapa kolom, isi filter (gunakan `NULL` untuk SQL NULL), lalu pilih record. UPDATE mensyaratkan primary key atau unique key yang bisa diverifikasi.
4. **Input:** isi kolom yang akan ditambahkan atau diubah. `ENTER` melewati kolom atau mempertahankan nilai saat UPDATE; password tidak ditampilkan. Untuk perubahan `IPServer` pada `ParamServer`, isi juga `DBPass` baru agar enkripsi memakai IP baru.
5. **Preview:** periksa seluruh data sebelum backup. Jika batal, tidak dibuat backup baru.
6. **Backup dan DML:** setelah disetujui, wizard membuat snapshot kondisi lama, menyimpannya secara permanen, lalu menjalankan INSERT/UPDATE pada transaksi terpisah.
7. **Verifikasi dan konfirmasi:** pilih COMMIT untuk menyimpan perubahan atau ROLLBACK untuk membatalkan DML. Backup yang telah di-COMMIT tetap ada.
8. **Deployment:** setelah COMMIT, wizard menyimpan file SQL deployment untuk dijalankan pada database tujuan.

## Backup database

Backup **benar-benar dibuat pada SQL Server**, di database `DataFlowParam`, menggunakan `SELECT * INTO`. Nama tabel contohnya:

- `dbo.ParamServer_Backup_20261028_145000_123456_ab12cd`
- `dbo.ParamFitur_Backup_20261028_145000_123456_ab12cd`
- `dbo.ParamFiturCekLogActivity_Backup_20261028_145000_123456_ab12cd`

Operasi satu tabel membuat backup tabel target saja. INSERT berantai membuat backup ketiga tabel. UPDATE berantai membuat backup tabel yang benar-benar diubah. Backup menyimpan **data asli sebelum perubahan**, tidak menggandakan data pada tabel utama, dan tetap ada setelah ROLLBACK DML. Jika pembuatan backup gagal, operasi utama tidak dijalankan.

Periksa backup dengan:

```sql
USE [DataFlowParam];
SELECT name, create_date
FROM sys.tables
WHERE name LIKE '%[_]Backup[_]%'
ORDER BY create_date DESC;
```

**Penting:** Snapshot `SELECT INTO` tidak menyalin indeks, constraint, trigger, permission, dan bukan file `.bak`. Pemulihan data dari snapshot harus dilakukan secara terkontrol setelah memeriksa relasi dan perubahan lain.

## SQL deployment dan password

File deployment disimpan di:

`activities/DataSourceDistributor/python/output/01_Reconciliation/DataFlowParam/`

Nama file contohnya `ParamServer_INSERT_YYYYMMDD_HHMMSS_ffffff.sql`, `CHAIN_INSERT_YYYYMMDD_HHMMSS_ffffff.sql`, atau `CHAIN_UPDATE_YYYYMMDD_HHMMSS_ffffff.sql`.

Deployment menjalankan backup pada transaksi tersendiri sebelum transaksi DML, serta menggunakan `TRY/CATCH`, COMMIT, dan ROLLBACK. **Password asli tidak ditulis ke file SQL.** Untuk INSERT/UPDATE `ParamServer` yang menyentuh `DBPass`, gunakan SQLCMD mode dan suplai `$(DBPASS)` secara aman. Untuk INSERT berantai dengan beberapa server baru, suplai variabel `$(DBPASS_1)`, `$(DBPASS_2)`, dan seterusnya sesuai urutan server baru yang unik pada script.

## Batasan dan pengujian

- Jalankan dan uji terlebih dahulu di development. Struktur tabel aktual menentukan kolom wajib dan relasi yang tersedia.
- Operasi berantai menggunakan identitas `IdServer` dan `IDFitur`; deployment meresolusi identitas sesuai data di lingkungan tujuan.
- Deployment INSERT berantai membuat `ParamFitur` baru; jangan menjalankan ulang tanpa memeriksa potensi duplikasi.
- Pencarian UPDATE menampilkan maksimal 100 record; gunakan filter spesifik.
- Backup dibuat sebelum DML tetapi tidak menjamin konsistensi lintas sesi jika ada penulis lain yang aktif bersamaan; gunakan maintenance window atau koordinasi transaksi pada sistem produksi.
- Jika COMMIT berhasil tetapi penyimpanan SQL gagal, perubahan database tetap tersimpan; periksa pesan terminal.
