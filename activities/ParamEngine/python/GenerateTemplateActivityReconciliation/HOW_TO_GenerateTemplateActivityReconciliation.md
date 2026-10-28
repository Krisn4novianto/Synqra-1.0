# Generate Template Activity Reconciliation

## Tujuan
Menjalankan `LogActivity.dbo.sp_GenerateTemplateActivityReconciliation` melalui Python, meminta parameter `@ProductId` dan `@ActivityGroup`, menampilkan hasil untuk pemeriksaan, lalu menunggu keputusan `COMMIT` atau `ROLLBACK`.

## Prasyarat
- Project Synqra mempunyai `db_config.py` dan `db_connection.py` di root.
- `db_config.py` menyediakan `SERVERS`.
- `db_connection.py` menyediakan `connect_sqlserver(cfg, database)`.
- Stored procedure `dbo.sp_GenerateTemplateActivityReconciliation` tersedia di database `LogActivity`.
- Akun SQL Server memiliki izin execute procedure dan baca/tulis tabel target.

## Menjalankan
Jalankan dari root `Synqra-1.0`:

```bash
./.venv/bin/python activities/ParamEngine/python/GenerateTemplateActivityReconciliation/GenerateTemplateActivityReconciliation.py
```

Atau sesuaikan path dengan lokasi folder script.

## Alur
1. Pilih server yang tersedia dari `db_config.py`.
2. Masukkan `@ProductId` (maksimal 9 karakter).
3. Masukkan `@ActivityGroup` (maksimal 255 karakter).
4. Ketik `RUN` untuk menjalankan prosedur.
5. Script menjalankan prosedur di dalam transaksi Python yang belum di-commit.
6. Hasil untuk ProductId dan ActivityGroup ditampilkan, dengan penanda record baru dan record yang sudah ada.
7. Ketik `COMMIT` untuk menyimpan atau `ROLLBACK` untuk membatalkan. Selain `COMMIT`, transaksi akan di-rollback.

## Catatan
Script ini mengasumsikan stored procedure berada di database `LogActivity`, sesuai nama tabel target dan definisi yang diberikan. Pastikan prosedur memang dibuat di database tersebut. Script tidak mengubah definisi stored procedure.
