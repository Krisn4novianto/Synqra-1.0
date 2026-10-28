# Panduan GetDdhist-H1

## Lokasi
`activities/ParamEngine/python/Settlement/python/GetDdhist-H1.py`

## Menjalankan
Dari root `Synqra-1.0` jalankan:
```bash
./.venv/bin/python "activities/ParamEngine/python/Settlement/GetDdhist-H1.py"
```

## Alur
1. Pilih server: **1** untuk Server 102 (`172.18.246.102`) atau **2** untuk Lokal. Profil koneksi diambil dari `db_config.py` dan koneksi dari `db_connection.py` di root project.
2. Pilih **INSERT**, **UPDATE**, atau **Keluar**.
3. Untuk INSERT, masukkan `ProductId` dan `Task`, lalu isi/periksa field template.
4. Untuk UPDATE, pilih kolom filter dari daftar, masukkan nilainya, pastikan hasil filter tepat satu record, lalu pilih kolom yang akan diubah (`ALL` untuk semua kolom non-filter). UPDATE tidak meminta `ProductId`/`Task` secara otomatis.
5. Periksa preview dan ketik `LANJUT` untuk melanjutkan ke backup. Setelah perubahan dijalankan, ketik `COMMIT` untuk menyimpan; input lain akan melakukan rollback.

## Target
Database `ParamEngine`, tabel `dbo.ParamGetDDHIST`. Script memeriksa schema, membuat backup tabel, memverifikasi hasil, dan menghasilkan file SQL deployment di folder `output`.


### Jika filter UPDATE menemukan beberapa record

Jika filter awal cocok dengan lebih dari satu record, wizard akan menampilkan daftar identitas key (`ProductId`, `Task`, `Activity`, atau key sesuai activity). Pilih nomor record yang benar. Wizard kemudian menggunakan seluruh kolom key untuk memastikan UPDATE hanya menargetkan satu record. Jika hasilnya terlalu banyak, batasi filter terlebih dahulu.


### Pilihan menu

Pada prompt `Pilih menu (0/1/2):`, masukkan `1` untuk INSERT, `2` untuk UPDATE, atau `0` untuk keluar. Tidak ada pilihan default; tekan Enter saja tidak akan otomatis memilih INSERT.
