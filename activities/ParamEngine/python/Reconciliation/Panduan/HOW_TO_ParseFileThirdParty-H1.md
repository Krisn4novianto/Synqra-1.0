# HOW TO — Wizard INSERT / UPDATE ParseFileThirdParty-H1 (Synqra 1.0)

## 1. Definisi
`ParseFileThirdParty-H1.py` adalah wizard CLI Python untuk konfigurasi dua tabel `ParamEngine.dbo.ParamParseFile` dan `ParamEngine.dbo.ParamParseFileMappingColumn`. Setiap proses memilih INSERT atau UPDATE secara eksplisit. Activity otomatis `ParseFileThirdParty-H1`.

## 2. Persiapan
Pastikan `db_config.py`, `db_connection.py`, `pyodbc`, driver ODBC SQL Server dan `SERVERS['2']` tersedia. Akun SQL Server memerlukan izin SELECT, INSERT, UPDATE dan CREATE TABLE untuk backup. Uji dahulu di development.

```bash
cd /Users/a2345/Documents/Synqra-1.0
./.venv/bin/python activities/ParamEngine/python/Reconciliation/ParseFileThirdParty-H1.py
```

## 3. Menu tabel
```text
1. ParamParseFile
2. ParamParseFileMappingColumn
3. Kedua tabel berurutan
0. Keluar
```
Setelah memilih tabel, pilih `1. INSERT`, `2. UPDATE` atau `0. Kembali`. Opsi 3 menjalankan wizard kedua tabel secara berurutan; setiap tabel memiliki backup, transaksi, dan konfirmasi COMMIT sendiri (bukan satu transaksi gabungan).

## 4. INSERT ParamParseFile
Isi `ProductId`, `Task`, `LocalPath`, `Filename`, `TargetDB`, `TargetTable`, `FieldFilename`, `FieldFiledate`, `LogActivityFilenameDateAdd`, `IsFixedCol`, `Delimiter`, `HeaderRowSkip`, `FooterRowSkip`, `TextQualifier`, `isActive`, `Note`, `CheckSum`, dan `FormatInterface`. `Activity` otomatis `ParseFileThirdParty-H1`; `InsertDate` dan `LastModified` diisi SQL Server melalui `GETDATE()`.

Contoh: ProductId `AYOCONECT`, Task `AYOCONECT-TVKABEL`, LocalPath `/ThirdParty/`, Filename `ayoconnect-{%d%m%Y}.csv`, TargetDB `ThirdPartyDataDBName`, TargetTable `dbo.ReportTVKabelInternet`, Delimiter `,`, FormatInterface `delimiter`. Wizard memeriksa duplikat kombinasi ProductId + Task + Activity.

## 5. INSERT ParamParseFileMappingColumn
Pilih jumlah record mapping yang akan diisi (misalnya `18`). Untuk setiap record, input manual `ProductId`, `Task`, `Col`, `FieldTargetName`, `FixedColSubstring`. `Activity` otomatis `ParseFileThirdParty-H1`, tanggal diisi `GETDATE()`.

Contoh mapping: `Col=1, FieldTargetName=TransactionID`; `Col=2, FieldTargetName=PartnerTransactionID`; `Col=3, FieldTargetName=ProductID`. Lanjutkan sampai jumlah mapping selesai. Semua mapping dalam satu batch masuk ke **satu transaksi**: satu kesalahan menyebabkan ROLLBACK seluruh batch.

## 6. UPDATE
Pilih tabel dan `2. UPDATE`, lalu isi kunci pencarian:
- ParamParseFile: ProductId + Task + Activity.
- ParamParseFileMappingColumn: ProductId + Task + Activity + Col.

Wizard melakukan SELECT data lama dan mensyaratkan tepat satu record. Setelah itu, pilih nomor kolom yang ingin diubah; kolom identitas tidak bisa diubah. UPDATE memakai CTE dengan `UPDLOCK, HOLDLOCK`, dan hanya field terpilih masuk `SET`. `LastModified` diperbarui otomatis.

## 7. Preview, backup, SELECT, COMMIT/ROLLBACK
Sebelum eksekusi, wizard menampilkan preview. Konfirmasi `y` membuat backup tabel bertimestamp secara terpisah. Setelah INSERT/UPDATE, wizard menampilkan SELECT hasil aktual **dalam transaksi yang belum COMMIT**. Ketik tepat `COMMIT` untuk menyimpan; input lain melakukan ROLLBACK. Backup tetap ada meskipun ROLLBACK.

## 8. SQL deployment SOP
Hanya setelah COMMIT Python berhasil, wizard menghasilkan SQL di `activities/ParamEngine/output/ParseFileThirdParty-H1/`. File memuat:
1. `DECLARE` parameter dan validasi database.
2. Backup tabel bertimestamp.
3. INSERT atau UPDATE CTE.
4. SELECT dan verifikasi dalam transaksi.
5. `@ApproveCommit BIT = 0` sebagai default ROLLBACK; ubah menjadi 1 hanya setelah review.
6. SELECT hasil akhir.

**Penting:** Script SQL deployment tidak otomatis dieksekusi. Backup `SELECT INTO` tidak menyalin semua indeks, constraint, dan trigger. Jika penulisan file SQL gagal setelah COMMIT, perubahan database tetap permanen.

## 9. Troubleshooting
- `SERVERS['2']` tidak tersedia: periksa `db_config.py`.
- UPDATE 0 atau banyak record: periksa ProductId, Task, Activity, dan Col.
- INSERT duplikat: gunakan UPDATE.
- Backup gagal: periksa permission CREATE TABLE dan ruang database.
- SQL tidak dibuat: pastikan COMMIT berhasil dan izin tulis folder output.

## 10. Checklist production
Pastikan server/database benar, target mapping dan nomor Col sesuai file CSV, hasil SELECT tepat, backup berhasil, perubahan sudah diverifikasi, dan deployment SQL telah direview sebelum mengubah `@ApproveCommit`.
