# Panduan FlaggingCategories-H1

## Lokasi
`activities/ParamEngine/python/Settlement/python/FlaggingCategories-H1.py`

## Menjalankan
```bash
./.venv/bin/python "activities/ParamEngine/python/Settlement/FlaggingCategories-H1.py"
```

## Alur
1. Pilih Server 102 atau Lokal. Profil koneksi dibaca dari `db_config.py` di root project.
2. Pilih **INSERT**, **UPDATE**, atau **Keluar**.
3. INSERT meminta `ProductId` dan `Task`, lalu meminta jumlah tahap `OrderExecute` dan menyiapkan template Stored Procedure untuk tiap tahap.
4. UPDATE menampilkan kolom filter; pilih kolom dan nilai filter sampai tepat satu record ditemukan, lalu pilih field yang akan diubah atau `ALL` untuk semua kolom non-filter.
5. Periksa preview dan ketik `LANJUT` untuk backup. Ketik `COMMIT` untuk menyimpan; selain itu perubahan di-rollback.

## Target
Database `ParamEngine`, tabel `dbo.ParamSPExecutor`. Hasil SQL deployment disimpan di folder `output`.


### Jika filter UPDATE menemukan beberapa record

Jika filter awal cocok dengan lebih dari satu record, wizard akan menampilkan daftar identitas key (`ProductId`, `Task`, `Activity`, atau key sesuai activity). Pilih nomor record yang benar. Wizard kemudian menggunakan seluruh kolom key untuk memastikan UPDATE hanya menargetkan satu record. Jika hasilnya terlalu banyak, batasi filter terlebih dahulu.


### Pilihan menu

Pada prompt `Pilih menu (0/1/2):`, masukkan `1` untuk INSERT, `2` untuk UPDATE, atau `0` untuk keluar. Tidak ada pilihan default; tekan Enter saja tidak akan otomatis memilih INSERT.
