# HOW_TO — GetDDHIST (Server 205 / Localhost)

## 1. Persiapan

Tempatkan `GetDDHIST.py` di `activities/DataSourceDistributor/python/`. Pastikan `db_config.py` dan `db_connection.py` tersedia di root proyek dan koneksi yang diizinkan telah dikonfigurasi:

- **Server 205:** `172.18.135.205:1433`
- **Localhost:** `localhost:1433` (atau `127.0.0.1` / `::1`)
- **Database target:** `DataSourceDistributor`
- **Tabel utama:** `dbo.ParamFitur` dan `dbo.ParamDDHIST`
- **Fungsi enkripsi:** `dbo.fnEncrypt`

Akun SQL Server memerlukan izin membaca dan mengubah tabel utama, menjalankan fungsi enkripsi, serta membuat tabel backup menggunakan `SELECT INTO` pada schema `dbo`. Pastikan dependensi Python dan koneksi SQL Server telah terpasang.

Jalankan dari root proyek:

```bash
./.venv/bin/python activities/DataSourceDistributor/python/GetDDHIST.py
```

Jika virtual environment berbeda, sesuaikan perintah Python.

## 2. Alur wizard (6 tahap)

1. **Pilih koneksi:** Server 205 atau Localhost dari `db_config.py`. Program memverifikasi database dan kedua tabel; tidak memindai database lain.
2. **Pilih operasi:** `1. INSERT KONFIGURASI BARU`, `2. UPDATE KONFIGURASI`, atau `0. KELUAR`.
3. **Pilih record dan ParamFitur:** INSERT dapat memilih ParamFitur lama berdasarkan `DBName` atau menyiapkan ParamFitur baru. UPDATE memilih `ParamFitur` atau `ParamDDHIST`, lalu menentukan record target.
4. **Isi konfigurasi:** Isi field ParamDDHIST; Enter mempertahankan nilai lama/default, `~` mengisi `NULL`, dan `B` membatalkan input. `isActive` hanya menerima `0` atau `1`.
5. **Preview dan backup:** Tinjau preview awal. Pada INSERT/UPDATE ParamDDHIST, pilih `1=Backup dan lanjut` untuk membuat snapshot kedua tabel. Setelah IDFitur di-resolve, wizard menampilkan preview transaksi berikutnya sebelum DML ParamDDHIST.
6. **Verifikasi dan COMMIT/ROLLBACK:** Program memverifikasi hasil aktual sebelum COMMIT. Pilih `1=COMMIT`, `2=ROLLBACK/ulang`, atau `0=ROLLBACK/kembali`.

**Catatan:** Untuk INSERT dengan ParamFitur baru, password `DBPass` diminta saat proses resolusi ParamFitur di dalam transaksi, bukan pada formulir identitas awal.

## 3. SOP backup otomatis di database

Backup dilakukan **langsung pada SQL Server yang dipilih**, di database `DataSourceDistributor`, dengan `SELECT * INTO` ke tabel terpisah. Backup menyimpan **data sebelum perubahan**, bukan hasil INSERT/UPDATE.

| Operasi | Snapshot yang dibuat |
|---|---|
| INSERT ParamDDHIST (ParamFitur lama/baru) | `dbo.ParamFitur` dan `dbo.ParamDDHIST` |
| UPDATE ParamDDHIST | `dbo.ParamFitur` dan `dbo.ParamDDHIST` |
| UPDATE ParamFitur | `dbo.ParamFitur` |

Contoh nama tabel:

```text
dbo.ParamFitur_Backup_20261028_143000_123456_a1b2c3
dbo.ParamDDHIST_Backup_20261028_143000_123456_a1b2c3
```

Nama aktual menggunakan timestamp dan token acak. Backup dibuat dalam transaksi terpisah dan **di-COMMIT sebelum transaksi DML**. Jika backup gagal, perubahan tidak dilanjutkan. Jika DML di-ROLLBACK, snapshot yang sudah berhasil dibuat tetap ada. Snapshot tidak menambah baris ke tabel utama.

**Perhatikan urutan konfirmasi:** Membatalkan sebelum konfirmasi backup tidak membuat backup. Namun, pada operasi ParamDDHIST, jika pengguna sudah memilih `Backup dan lanjut`, snapshot tetap tersimpan meskipun kemudian membatalkan pada preview transaksi kedua atau memilih ROLLBACK. Untuk UPDATE ParamFitur, backup dibuat setelah konfirmasi `Backup dan UPDATE`.

`SELECT INTO` hanya menyalin data dan struktur kolom yang dihasilkan query, bukan indeks, constraint, trigger, atau permission. Snapshot ini **bukan** pengganti SQL Server `BACKUP DATABASE (.bak)`.

## 4. Verifikasi tabel backup dan data

Jalankan pada database yang sesuai:

```sql
USE [DataSourceDistributor];
GO
SELECT name, create_date
FROM sys.tables
WHERE schema_id = SCHEMA_ID(N'dbo')
  AND (name LIKE N'ParamFitur[_]Backup[_]%'
       OR name LIKE N'ParamDDHIST[_]Backup[_]%')
ORDER BY create_date DESC;
```

Untuk melihat isi snapshot, gunakan **nama tabel backup yang benar-benar muncul** pada hasil query, misalnya:

```sql
SELECT TOP (20) *
FROM dbo.[ParamDDHIST_Backup_20261028_143000_123456_a1b2c3];
```

Jangan menjalankan pemulihan dengan `TRUNCATE`, `DELETE`, atau `INSERT` massal tanpa rencana restore yang diverifikasi. Periksa relasi `IDFitur`, data terkini, dan dampak terhadap tabel lain sebelum memulihkan.

## 5. Enkripsi dan perlindungan password

- `DBPass` dienkripsi oleh SQL Server dengan `dbo.fnEncrypt(password, IPServer + 'BR!')`.
- Password disembunyikan pada preview dan tidak ditulis dalam file SQL deployment sebagai plaintext.
- Saat SQL deployment perlu membuat ParamFitur atau mengganti DBPass, gunakan variabel SQLCMD `$(DBPASS)` dan berikan nilainya melalui mekanisme rahasia yang disetujui tim.
- **Perhatian kode saat ini:** UPDATE `IPServer` tidak otomatis mewajibkan perubahan `DBPass`. Karena `IPServer` menjadi bagian dari salt enkripsi, lakukan perubahan keduanya secara bersamaan agar kredensial tetap dapat digunakan. Sebaiknya validasi wajib tersebut ditambahkan pada script Python.

## 6. SQL deployment setelah COMMIT

Setelah COMMIT berhasil, program menulis SQL deployment ke:

```text
activities/DataSourceDistributor/python/output/01_Reconciliation/GetDDHIST/
```

Contoh nama file:

```text
GetDDHIST_INSERT_YYYYMMDD_HHMMSS_microseconds.sql
GetDDHIST_UPDATE_YYYYMMDD_HHMMSS_microseconds.sql
GetDDHIST_UPDATE_ParamFitur_YYYYMMDD_HHMMSS_microseconds.sql
```

File deployment juga membuat backup sebelum transaksi DML, memeriksa jumlah record, lalu melakukan COMMIT atau ROLLBACK jika terjadi kesalahan. **Backup live dan backup deployment adalah proses terpisah**: menjalankan file deployment di server tujuan akan membuat snapshot baru di server tersebut.

Jalankan deployment melalui SQLCMD mode jika memerlukan variabel `DBPASS`. Jangan menyimpan password asli dalam file `.sql`, shell history, log, atau version control.

**Perhatian kode saat ini:** Generator `deployment()` untuk INSERT memuat cabang pembuatan ParamFitur jika target tidak memiliki record yang cocok, bahkan ketika wizard asal memilih ParamFitur lama. Karena itu, deployment INSERT dapat membutuhkan `$(DBPASS)` pada lingkungan tujuan yang belum memiliki ParamFitur tersebut. Pastikan keberadaan ParamFitur target dan nilai SQLCMD sebelum eksekusi.

## 7. Batasan, pemeriksaan, dan troubleshooting

- Kunci logis ParamDDHIST yang dipakai wizard adalah kombinasi `IDFitur`, `LogActivityModul`, dan `LogActivityEntity`. UPDATE hanya boleh menargetkan tepat satu record.
- Proses backup menyalin seluruh isi tabel terkait, sehingga waktu eksekusi dan kebutuhan ruang penyimpanan meningkat seiring ukuran tabel.
- Backup yang dibuat setiap operasi tidak dibersihkan otomatis. Tetapkan kebijakan retensi dan penghapusan backup melalui prosedur DBA.
- Bila COMMIT berhasil tetapi pembuatan file deployment gagal, perubahan database **tetap tersimpan**. Periksa izin folder output dan buat ulang deployment dengan pengawasan.
- Pada script ini, preview transaksi kedua terjadi **setelah** backup dan kemungkinan INSERT ParamFitur baru dalam transaksi yang belum di-COMMIT.
- Jika terjadi kesalahan koneksi, izin `CREATE TABLE`, fungsi `dbo.fnEncrypt`, atau struktur kolom, hentikan operasi dan periksa error sebelum mencoba lagi.
- Uji INSERT, UPDATE, COMMIT, ROLLBACK, backup, serta file deployment di lingkungan development sebelum production.

Dokumentasi ini mengikuti perilaku script `GetDDHIST.py` yang diberikan, bukan hasil uji koneksi langsung ke SQL Server.
