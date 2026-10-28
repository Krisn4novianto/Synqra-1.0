# HOW_TO — UpdateThresholdValue-H1

## Target

- Server: `172.18.246.102:1433`, profil `SERVERS['4']` dari `db_config.py`.
- Database: `ParamEngine`, tabel `dbo.ParamSPExecutor`.
- Activity otomatis: `UpdateThresholdValue-H1`.
- `InsertDate` dan `LastModified` diisi `GETDATE()` saat INSERT; UPDATE hanya mengubah `LastModified`.
- Identitas record: `ProductId`, `Task`, `Activity`, `OrderExecute`.

## Menjalankan

Dari root proyek `Synqra-1.0`:

```bash
./.venv/bin/python activities/ParamEngine/python/Reconciliation/UpdateThresholdValue-H1.py
```

## INSERT

1. Pilih `1. INSERT batch`.
2. Isi `ProductId` dan `Task` (default `AYOCONECT` / `AYOCONECT-TVKABEL`).
3. Pilih semua template atau masukkan nomor `OrderExecute` tertentu.
4. Untuk tiap record, gunakan template lalu edit field tertentu, atau input seluruh field.
5. Tinjau preview `NamaKolom = Nilai`.
6. Ketik `y` untuk backup tabel dan menjalankan INSERT dalam transaksi.
7. Tinjau SELECT verifikasi setiap record. Ketik `COMMIT` untuk menyimpan; input lain melakukan `ROLLBACK`.
8. SQL deployment dihasilkan **hanya setelah COMMIT**, di `activities/ParamEngine/output/UpdateThresholdValue-H1/`.

## UPDATE

1. Pilih `2. UPDATE`.
2. Isi identitas record, termasuk `OrderExecute`.
3. Tinjau data lama, pilih nomor field yang diubah, dan isi nilai baru.
4. Backup, SELECT verifikasi, dan keputusan `COMMIT` / `ROLLBACK` seperti INSERT.

## Deployment SQL (DBeaver)

1. Buka SQL hasil wizard, periksa server/database, semua nilai parameter, dan backup.
2. Default `@ApproveCommit = 0` (**ROLLBACK**). Ubah menjadi `1` hanya setelah persetujuan.
3. Jalankan script dengan SQL Server script execution (mendukung `GO`).
4. Verifikasi SELECT hasil akhir dan keberadaan backup.

## Perhatian

- Backup merupakan snapshot **seluruh tabel** dan tetap ada walau perubahan di-ROLLBACK.
- Jangan menjalankan INSERT batch apabila salah satu identitas record sudah ada; gunakan UPDATE untuk record tersebut.
- Teks `StoredProcedureName`, `Source1Where`, dan ekspresi rekonsiliasi disimpan sebagai data; wizard **tidak mengeksekusi** stored procedure/ekspresi tersebut.
- Template contoh perlu diverifikasi terhadap skema tabel dan kebutuhan rekonsiliasi aktual sebelum COMMIT.
- Wizard menggunakan konfigurasi password yang sudah tersedia pada `db_config.py`, tidak menyimpan kredensial di script ini.
