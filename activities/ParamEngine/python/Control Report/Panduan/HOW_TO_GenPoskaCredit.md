# HOW_TO — GenPoskaCredit

## Penempatan
`/Users/a2345/Documents/Synqra-1.0/activities/ParamEngine/python/Control Report/GenPoskaCredit.py`

`fungsi activity di masing-masing file Python` harus berada di folder yang sama. `db_config.py` dan `db_connection.py` tetap di root proyek.

## Running
Dari direktori `Synqra-1.0`:

```bash
./.venv/bin/python "activities/ParamEngine/python/Control Report/GenPoskaCredit.py"
```

## Penggunaan
1. Pilih `1` untuk INSERT atau `2` untuk UPDATE.
2. Isi `ProductId` dan `Task` secara manual. Activity otomatis mengikuti nama script.
3. Tinjau nilai template. Pilih `y` untuk mengubah field tertentu.
4. Cek preview field per baris.
5. Ketik `LANJUT` untuk backup tabel dan mulai transaksi.
6. Periksa hasil SELECT sementara. Ketik `COMMIT` untuk menyimpan; selain itu ROLLBACK.
7. File deployment SQL dibuat setelah COMMIT di `activities/ParamEngine/python/output/GenPoskaCredit/`.

## Catatan
`InsertDate` otomatis `GETDATE()` saat INSERT; `LastModified` otomatis `GETDATE()` saat INSERT maupun UPDATE. Periksa `Filename`, `SPName`, dan placeholder SQL sebelum commit. Belum diuji terhadap database live.

## Input identitas
`ProductId` dan `Task` wajib diketik manual setiap menjalankan wizard, baik INSERT maupun UPDATE. Tidak ada nilai default dari template SQL.
