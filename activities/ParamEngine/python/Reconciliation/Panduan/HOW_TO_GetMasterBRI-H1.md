# HOW TO — GetMasterBRI-H1

## 1. Tujuan dan konfigurasi

Wizard untuk **INSERT / UPDATE** `ParamEngine.dbo.ParamGetMasterBRI` menggunakan koneksi `SERVERS['4']` pada `db_config.py` (host `172.18.246.102:1433`).

- **Activity:** `GetMasterBRI-H1` (otomatis, tidak ditanyakan saat INSERT/UPDATE).
- **Identitas record:** `ProductId`, `Task`, `Activity`.
- **Kolom yang diinput:** `ProductId`, `Task`, `SelectQry`, `WhereQry`, `TargetDB`, `TargetTable`, `isActive`, `SourceDBLocation`.
- **InsertDate:** otomatis `GETDATE()` saat INSERT; tidak diubah saat UPDATE.
- **LastModified:** otomatis `GETDATE()` saat INSERT dan UPDATE.
- **Default:** `TargetDB=ReconciliationDBName`, `TargetTable=MasterBRI`, `isActive=1`, `SourceDBLocation=source`.
- **Output SQL:** `activities/ParamEngine/output/GetMasterBRI-H1/`.

## 2. Cara menjalankan

Simpan `GetMasterBRI-H1.py` ke `activities/ParamEngine/python/`, kemudian dari root proyek:

```bash
./.venv/bin/python activities/ParamEngine/python/Reconciliation/GetMasterBRI-H1.py
```

Pastikan `db_connection.py` dan `db_config.py` tersedia serta kredensial profil server `4` valid. Akun SQL Server perlu izin `SELECT`, `INSERT`, `UPDATE`, dan pembuatan tabel backup (`SELECT INTO`).

## 3. INSERT konfigurasi AYOCONECT-TVKABEL

Pilih **1. INSERT**, lalu isi:

```text
ProductId          = AYOCONECT
Task               = AYOCONECT-TVKABEL
Activity           = GetMasterBRI-H1        (otomatis)
SelectQry          = [paste daftar SELECT lengkap]
WhereQry           = ServiceId = '{dbo.FeatureService.ServiceId}' and CreditAccountNumber = '{dbo.FeatureService.NominalAccount}' and FlagValidation is NULL
TargetDB           = ReconciliationDBName   (default)
TargetTable        = MasterBRI              (default)
isActive           = 1                      (default)
SourceDBLocation   = source                 (default)
```

Untuk `SelectQry` dan `WhereQry`, wizard menyediakan input multiline. Paste teks SQL **tanpa** pembungkus `N'...'` dari query INSERT, kemudian ketik `.SELESAI` pada baris tersendiri. **Tanda petik tunggal dalam ekspresi SQL cukup satu**, contohnya:

```sql
'AYOCONECT-TVKABEL' AS FeatureId,
TRY_CONVERT(DECIMAL(20,2), DebetAmountTransaction) AS DebetAmountTransaction,
'H1' AS ReconciliationWindow,
'{dbo.Feature.ReconModel}' AS ReconciliationType,
DATEADD(DAY,0,CONVERT(DATETIME,CONVERT(DATE,GETDATE())) + CAST('{dbo.FeatureTime.ResolutionCutOff}' AS DATETIME)) AS ResolutionCutOff,
TRY_CONVERT(TIME,'{dbo.FeatureTime.TransactionTimeCutOff}') AS TransactionTimeCutOff,
'TV Kabel MyRepublic' AS FeatureName
```

Contoh ini hanya potongan dari `SelectQry` yang diberikan. Paste **seluruh** daftar kolom asli untuk konfigurasi lengkap. Wizard menyimpan ekspresi sebagai teks, bukan mengeksekusinya sebagai SELECT saat konfigurasi.

### Preview

```text
=== PREVIEW INSERT ===
ProductId          = AYOCONECT
Task               = AYOCONECT-TVKABEL
Activity           = GetMasterBRI-H1
SelectQry          = 'AYOCONECT-TVKABEL' AS FeatureId, ...
WhereQry           = ServiceId = '{dbo.FeatureService.ServiceId}' and ...
TargetDB           = ReconciliationDBName
TargetTable        = MasterBRI
isActive           = 1
SourceDBLocation   = source
```

Setelah preview, ketik `y` untuk backup dan menjalankan INSERT sementara. Periksa hasil `SELECT` yang ditampilkan per field. Ketik **`COMMIT`** (huruf besar) untuk menyimpan. Input lain akan `ROLLBACK`.

## 4. UPDATE

Pilih **2. UPDATE**. Isi `ProductId` dan `Task`; `Activity` diisi otomatis. Wizard akan menampilkan data lama, lalu kamu memilih nomor kolom yang hendak diperbarui. Setelah preview perubahan, backup, dan SELECT verifikasi, ketik `COMMIT` untuk menyimpan.

Kolom identitas tidak dapat diubah melalui menu UPDATE. `InsertDate` tetap seperti semula, sedangkan `LastModified` diatur otomatis oleh SQL Server.

## 5. Backup dan SQL deployment

Sebelum perubahan, wizard membuat salinan tabel dengan nama `dbo.ParamGetMasterBRI_Backup_YYYYMMDD_HHMMSS_microseconds`. Backup menggunakan koneksi terpisah dan tetap ada meskipun transaksi perubahan di-ROLLBACK.

Setelah COMMIT berhasil, wizard menghasilkan file `.sql` dalam folder output. SQL deployment berisi deklarasi parameter, backup, validasi record, INSERT/UPDATE, SELECT sebelum COMMIT, dan SELECT hasil akhir. Secara default:

```sql
DECLARE @ApproveCommit BIT = 0;
```

Artinya deployment **ROLLBACK** secara default. Setelah review dan persetujuan, ubah ke `1` untuk COMMIT. Jalankan script pada database `ParamEngine` menggunakan DBeaver/SQL Server client yang mendukung pemisah batch `GO`.

## 6. Catatan penting

- Gunakan profil koneksi server `4`, jangan menggunakan password server lain.
- Pastikan struktur aktual tabel memiliki kolom `SourceDBLocation` dan `isActive`.
- Jangan menjalankan INSERT ulang untuk kombinasi `ProductId + Task + Activity` yang sama; pilih UPDATE.
- Tidak ada perubahan database sampai kamu menjalankan wizard dan mengonfirmasi `COMMIT`.
- Script sudah lolos pemeriksaan sintaks Python, tetapi belum diuji langsung terhadap server database.
