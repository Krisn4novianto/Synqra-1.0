# HOW_TO — GetESBRevamp (Server 205 / Localhost)

## 1. Persiapan

Tempatkan `GetESBRevamp.py` di `activities/DataSourceDistributor/python/`. Pastikan `db_config.py` dan `db_connection.py` berada di root proyek. Koneksi SQL Server harus mempunyai akses ke database `DataSourceDistributor`, tabel `dbo.ParamFitur` dan `dbo.ParamESBRevamp`, serta fungsi `dbo.fnEncrypt`.

Akun SQL Server juga membutuhkan izin untuk membaca tabel, menjalankan INSERT/UPDATE, dan **membuat tabel snapshot backup** (`SELECT INTO`, termasuk izin `CREATE TABLE` dan izin skema yang sesuai). Pastikan kapasitas penyimpanan database mencukupi karena setiap eksekusi membuat tabel backup baru.

Jalankan dari root proyek:

```bash
./.venv/bin/python activities/DataSourceDistributor/python/GetESBRevamp.py
```

## 2. Alur wizard (6 tahap)

1. **Tahap 1 — Koneksi:** pilih **Server 205** (`172.18.135.205:1433`) atau **Localhost**. Script memverifikasi database `DataSourceDistributor` dan keberadaan kedua tabel.
2. **Tahap 2 — Menu:** pilih `1. INSERT`, `2. UPDATE`, atau `0. KELUAR`. Untuk UPDATE, pilih tabel `ParamFitur` atau `ParamESBRevamp`.
3. **Tahap 3 — Pilih record:** INSERT dapat memakai ParamFitur yang sudah ada (pencarian `DBName`) atau membuat ParamFitur baru. UPDATE ParamESBRevamp dapat dicari berdasarkan `LogActivityModul`, `LogActivitySubModul`, `LogActivityEntity`, atau `IDFitur`.
4. **Tahap 4 — Input:** isi `FieldSelect`, `WhereCondition`, `TableDestination`, `LogActivityModul`, `LogActivitySubModul`, `LogActivityEntity`, `isActive`, `Note`, dan `SchStart`. Untuk `FieldSelect`, pilih `T` (template), `K` (manual), atau `L` (pertahankan nilai lama saat UPDATE).
5. **Tahap 5 — Preview:** periksa data sebelum/sesudah. Pilih **`1. BACKUP + JALANKAN PERUBAHAN`** untuk membuat backup dan memulai transaksi DML. Memilih kembali/ulangi pada tahap ini **tidak membuat backup**.
6. **Tahap 6 — Verifikasi:** wizard melakukan SELECT hasil aktual **sebelum COMMIT**. Pilih `1. COMMIT`, `2. ROLLBACK & ULANGI`, atau `0. ROLLBACK & KEMBALI`.

`B` membatalkan input dan kembali ke menu; `~` mengosongkan field opsional. Password dimasukkan melalui input tersembunyi dan tidak ditampilkan dalam preview.

## 3. SOP backup otomatis di SQL Server

Fungsi `backup_snapshot(conn, tables)` menjalankan `SELECT * INTO` pada **database yang sedang dipilih** sebelum INSERT/UPDATE. Snapshot di-COMMIT secara terpisah sebelum transaksi perubahan dimulai.

| Operasi | Snapshot yang dibuat |
|---|---|
| INSERT ParamESBRevamp (ParamFitur lama atau baru) | `ParamFitur` dan `ParamESBRevamp` |
| UPDATE ParamESBRevamp | `ParamFitur` dan `ParamESBRevamp` |
| UPDATE ParamFitur | `ParamFitur` saja |

Contoh nama snapshot: `dbo.ParamFitur_Backup_YYYYMMDD_HHMMSS_microseconds_random` dan `dbo.ParamESBRevamp_Backup_YYYYMMDD_HHMMSS_microseconds_random`.

- **COMMIT:** perubahan pada tabel utama tersimpan; snapshot tetap menyimpan kondisi sebelumnya.
- **ROLLBACK:** perubahan DML dibatalkan; snapshot yang sudah di-COMMIT tetap tersedia.
- **Backup gagal:** wizard menghentikan operasi sebelum menjalankan DML.
- **Tidak ada duplikasi ke tabel utama karena backup:** snapshot adalah tabel terpisah. Script memeriksa keunikan pasangan `LogActivityModul` + `LogActivitySubModul`, tetapi proteksi menyeluruh terhadap duplikat tetap sebaiknya didukung constraint database.
- **Catatan:** snapshot menyalin seluruh isi tabel, bukan hanya record yang diedit; tidak menyalin indeks, constraint, trigger, permission, dan bukan pengganti `BACKUP DATABASE` (`.bak`). Backup baru akan menambah penggunaan ruang database.

Untuk melihat tabel snapshot yang tersedia:

```sql
USE [DataSourceDistributor];
SELECT name, create_date
FROM sys.tables
WHERE schema_id = SCHEMA_ID('dbo')
  AND (name LIKE 'ParamFitur[_]Backup[_]%'
       OR name LIKE 'ParamESBRevamp[_]Backup[_]%')
ORDER BY create_date DESC;
```

Untuk memeriksa isi snapshot, gunakan nama tabel aktual hasil query di atas:

```sql
SELECT TOP (100) * FROM dbo.[ParamESBRevamp_Backup_NAMA_AKTUAL];
```

## 4. Enkripsi password

`DBPass` dienkripsi di SQL Server menggunakan `dbo.fnEncrypt(password, IPServer + 'BR!')`. Jika `IPServer` pada ParamFitur diubah, `DBPass` harus diisi ulang agar enkripsi menggunakan kunci yang sesuai. Jangan menaruh password asli pada file `.sql` atau version control.

## 5. SQL deployment setelah COMMIT

Setelah COMMIT, wizard membuat file SQL di:

`activities/DataSourceDistributor/python/output/01_Reconciliation/GetESBRevamp/`

Pola nama file:

- `GetESBRevamp_INSERT_YYYYMMDD_HHMMSS_microseconds.sql`
- `GetESBRevamp_UPDATE_YYYYMMDD_HHMMSS_microseconds.sql`
- `GetESBRevamp_UPDATE_ParamFitur_YYYYMMDD_HHMMSS_microseconds.sql`

File deployment juga membuat snapshot backup **sebelum transaksi DML** dan memakai COMMIT/ROLLBACK. Bila deployment membuat ParamFitur baru atau mengganti DBPass, gunakan **SQLCMD mode** dengan variabel `DBPASS` yang diberikan secara aman. Jika hanya menggunakan ParamFitur lama tanpa mengganti password, variabel tersebut tidak diperlukan.

**Penting:** File deployment adalah skrip untuk lingkungan target; menjalankannya lagi pada database yang sama bukan bagian dari COMMIT wizard dan dapat menyebabkan operasi tambahan atau penolakan karena record sudah ada. Tinjau target dan isinya sebelum eksekusi.

## 6. Contoh skenario

**INSERT:** pilih server → INSERT → cari/buat ParamFitur → isi konfigurasi ParamESBRevamp → preview → `BACKUP + JALANKAN PERUBAHAN` → verifikasi → COMMIT. Backup menyimpan data sebelum INSERT.

**UPDATE ParamESBRevamp:** pilih server → UPDATE → ParamESBRevamp → cari record → pilih IDFitur → edit field → preview → backup → UPDATE → verifikasi → COMMIT atau ROLLBACK.

**UPDATE ParamFitur:** pilih server → UPDATE → ParamFitur → cari berdasarkan DBName → pilih field → preview → backup ParamFitur → UPDATE → verifikasi → COMMIT atau ROLLBACK.

## 7. Batasan dan pengujian

- Kombinasi `LogActivityModul` + `LogActivitySubModul` harus unik untuk menentukan record UPDATE. Jika `LogActivitySubModul` bernilai `NULL`, periksa perilaku pencarian karena perbandingan SQL `= NULL` tidak cocok dengan record.
- Backup dibuat **setelah konfirmasi eksekusi**, tetapi **sebelum DML**. Jika pengguna memilih ROLLBACK pada tahap verifikasi, backup tetap tersimpan.
- Script melakukan pemeriksaan perubahan sejak preview pada beberapa kolom, tetapi tidak menggantikan constraint unik dan pengujian concurrency di database.
- Tinjau dan uji skrip deployment di development, termasuk permission `SELECT INTO`, SQLCMD, enkripsi, serta hasil COMMIT/ROLLBACK sebelum digunakan di production.
