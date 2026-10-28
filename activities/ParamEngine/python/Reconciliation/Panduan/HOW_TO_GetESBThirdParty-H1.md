# HOW TO — GetESBThirdParty-H1

## 1. Tujuan
Wizard CLI Python untuk **INSERT** dan **UPDATE** konfigurasi `ParamEngine.dbo.ParamGetESB`, dengan preview per field, backup tabel, transaksi SQL Server, verifikasi, dan pembuatan SQL deployment setelah COMMIT.

| Parameter | Nilai |
|---|---|
| Server | `172.18.246.102:1433` |
| Profil koneksi | `SERVERS['4']` pada `db_config.py` |
| Database | `ParamEngine` |
| Tabel | `dbo.ParamGetESB` |
| Activity | `GetESBThirdParty-H1` (otomatis) |
| Script | `activities/ParamEngine/python/GetESBThirdParty-H1.py` |
| Output SQL | `activities/ParamEngine/output/GetESBThirdParty-H1/` |

## 2. Persiapan
Pastikan `db_config.py` memiliki `SERVERS['4']` untuk server `172.18.246.102` dan kredensial yang valid, `db_connection.py` tersedia, dan login punya hak `SELECT`, `INSERT`, `UPDATE`, serta `CREATE TABLE` untuk membuat backup dengan `SELECT INTO`.

Dari root proyek `Synqra-1.0`:

```bash
./.venv/bin/python activities/ParamEngine/python/Reconciliation/GetESBThirdParty-H1.py
```

Jika Python venv sudah aktif:

```bash
python activities/ParamEngine/python/Reconciliation/GetESBThirdParty-H1.py
```

Wizard memeriksa koneksi dan keberadaan tabel `dbo.ParamGetESB` sebelum menampilkan menu.

## 3. INSERT — Konfigurasi baru

1. Pilih `1. INSERT`.
2. Isi `ProductId`, `Task`, `SelectQry`, `WhereQry`, `TargetDB`, `TargetTable`, dan `IsActive`.
3. `Activity` otomatis `GetESBThirdParty-H1` dan tidak diminta sebagai input.
4. Untuk `SelectQry` dan `WhereQry`, input bisa beberapa baris. Akhiri dengan satu baris berisi **`.SELESAI`**.
5. Periksa preview `NamaField = Nilai`.
6. Jawab `y` pada pertanyaan **Backup dan mulai transaksi?** untuk membuat backup dan menjalankan INSERT sementara.
7. Periksa hasil SELECT sebelum COMMIT.
8. Ketik **`COMMIT`** (huruf kapital) untuk menyimpan; input lain menyebabkan ROLLBACK.
9. File deployment `.sql` hanya dibuat setelah COMMIT berhasil.

### Contoh input AYOCONECT

```text
Pilih proses: 1
ProductId: AYOCONECT
Task: AYOCONECT-TVKABEL
Activity = GetESBThirdParty-H1 (otomatis)

SelectQry (akhiri input dengan satu baris berisi .SELESAI):
> ReconcileKey1, ReconcileKey2, ReconcileKey3, EntryDate, 'TV Kabel MyRepublic' AS FeatureName
> .SELESAI

WhereQry (akhiri input dengan satu baris berisi .SELESAI):
> ServiceId = '{dbo.FeatureService.ServiceId}'
> .SELESAI

TargetDB [ThirdPartyDataDBName]:
TargetTable [StagingESB]:
IsActive [1]:
```

**Penting:** `SelectQry` di atas sengaja dipersingkat untuk contoh. Pada konfigurasi asli, masukkan seluruh daftar kolom yang dibutuhkan, termasuk alias `FeatureName`. Tanda kutip satu dalam input CLI ditulis biasa, misalnya `'TV Kabel MyRepublic'`; script deployment akan meng-escape string SQL secara otomatis. `WhereQry` diperlakukan sebagai teks konfigurasi; placeholder `{dbo.FeatureService.ServiceId}` tidak di-resolve oleh wizard.

### Kolom otomatis

`InsertDate` dan `LastModified` **tidak diinput manual**. Pada INSERT, SQL yang dieksekusi adalah:

```sql
INSERT INTO dbo.ParamGetESB (
    ProductId, Task, Activity, SelectQry, WhereQry,
    TargetDB, TargetTable, IsActive, InsertDate, LastModified
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, GETDATE(), GETDATE());
```

## 4. UPDATE — Konfigurasi yang sudah ada

1. Pilih `2. UPDATE`.
2. Isi identitas record: `ProductId` dan `Task`; `Activity` otomatis `GetESBThirdParty-H1`.
3. Wizard menampilkan **DATA SEBELUM UPDATE** per field.
4. Jika tepat satu record ditemukan, jawab `y` untuk lanjut.
5. Pilih nomor field yang akan diubah. Field yang tersedia: `SelectQry`, `WhereQry`, `TargetDB`, `TargetTable`, `IsActive`.
6. Isi nilai baru, periksa preview, setujui backup, lalu periksa SELECT hasil sementara.
7. Ketik `COMMIT` untuk menyimpan atau input lain untuk ROLLBACK.

Pada UPDATE, `LastModified` diisi otomatis:

```sql
[LastModified] = GETDATE()
```

`InsertDate` tetap seperti semula. Field identitas `ProductId`, `Task`, dan `Activity` tidak dapat diubah lewat menu UPDATE.

## 5. Tampilan record

Wizard menampilkan data secara vertikal, **satu field per baris**:

```text
=== HASIL SEMENTARA (BELUM COMMIT) ===
ProductId     = AYOCONECT
Task          = AYOCONECT-TVKABEL
Activity      = GetESBThirdParty-H1
SelectQry     = ReconcileKey1, ReconcileKey2, ...
WhereQry      = ServiceId = '{dbo.FeatureService.ServiceId}'
TargetDB      = ThirdPartyDataDBName
TargetTable   = StagingESB
IsActive      = 1
InsertDate    = ...
LastModified  = ...
```

Nilai contoh bukan hasil query database aktual.

## 6. Backup dan transaksi

- Sebelum perubahan, wizard membuat salinan **seluruh tabel** `dbo.ParamGetESB` menjadi `dbo.ParamGetESB_Backup_YYYYMMDD_HHMMSS_mikrodetik`.
- Backup dibuat melalui **koneksi terpisah** dan tetap ada sekalipun transaksi perubahan di-ROLLBACK.
- INSERT ditolak jika kombinasi `ProductId + Task + Activity` sudah ada.
- UPDATE mensyaratkan tepat satu record.
- Perubahan diperiksa dengan SELECT sebelum konfirmasi COMMIT.
- Hanya input persis `COMMIT` yang menyimpan perubahan.

> Perhatikan kapasitas database: setiap backup menyalin seluruh isi tabel, bukan hanya record yang sedang diubah.

## 7. File SQL deployment

Setelah COMMIT, wizard menyimpan file `.sql` ke:

```text
activities/ParamEngine/output/GetESBThirdParty-H1/
```

File SQL memuat deklarasi parameter, validasi database/activity, backup tabel, INSERT/UPDATE, SELECT verifikasi, dan keputusan COMMIT/ROLLBACK.

### Jalankan di DBeaver

1. Buka file SQL hasil generator di DBeaver dengan koneksi SQL Server tujuan.
2. Pastikan target database `ParamEngine` dan review seluruh nilai `@Filter_*` / `@New_*`.
3. Default:

   ```sql
   DECLARE @ApproveCommit BIT = 0;
   ```

   Ini berarti **ROLLBACK**.
4. Setelah mendapat persetujuan deployment, ubah menjadi `1` untuk **COMMIT**.
5. Jalankan sebagai **SQL script**, karena file menggunakan pemisah batch `GO`.
6. Periksa SELECT verifikasi dan status deployment. Backup tetap tersimpan jika ROLLBACK.

**Catatan:** File deployment adalah script untuk lingkungan tujuan. Jika dijalankan pada database yang sudah berisi record INSERT yang sama, validasi duplikat akan menolaknya.

## 8. Masalah yang sering muncul

| Gejala | Pemeriksaan |
|---|---|
| Koneksi gagal | Periksa host `172.18.246.102`, profil `SERVERS['4']`, username/password, jaringan, dan izin SQL Server. |
| Tabel tidak ditemukan | Periksa database `ParamEngine`, nama `dbo.ParamGetESB`, dan izin login. |
| INSERT: record sudah ada | Gunakan UPDATE untuk identitas `ProductId + Task + Activity` yang sama. |
| UPDATE: record tidak ditemukan | Periksa `ProductId` dan `Task`; `Activity` otomatis ditetapkan. |
| Backup gagal | Periksa izin membuat tabel dan kapasitas database. |
| `IsActive` tidak valid | Isi `0` atau `1`. |
| Tidak muncul file deployment | File hanya dihasilkan setelah COMMIT berhasil. |
| Input multiline tidak selesai | Ketik `.SELESAI` pada satu baris tersendiri. |

## 9. Pemeriksaan setelah COMMIT

Jalankan SELECT ini di DBeaver:

```sql
SELECT ProductId, Task, Activity, SelectQry, WhereQry,
       TargetDB, TargetTable, IsActive, InsertDate, LastModified
FROM ParamEngine.dbo.ParamGetESB
WHERE ProductId = N'AYOCONECT'
  AND Task = N'AYOCONECT-TVKABEL'
  AND Activity = N'GetESBThirdParty-H1';
```

Dokumentasi ini dibuat berdasarkan perilaku script `GetESBThirdParty-H1.py` yang disediakan, bukan hasil pengujian langsung terhadap database.
