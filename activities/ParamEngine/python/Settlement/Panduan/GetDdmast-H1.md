# Panduan GetDdmast-H1

## Lokasi
`activities/ParamEngine/python/Settlement/python/GetDdmast-H1.py`

## Menjalankan
```bash
./.venv/bin/python "activities/ParamEngine/python/Settlement/GetDdmast-H1.py"
```

## Alur
1. Pilih server **1** (Server 102) atau **2** (Lokal), berdasarkan profil `db_config.py`.
2. Pilih **INSERT**, **UPDATE**, atau **Keluar**.
3. INSERT meminta `ProductId` dan `Task`, lalu menawarkan template field.
4. UPDATE menampilkan daftar kolom filter; pilih kolom dan nilai filter hingga tepat satu record ditemukan. Berikutnya pilih field yang diubah, atau `ALL` untuk semua field non-filter.
5. Ketik `LANJUT` setelah preview untuk membuat backup dan memproses perubahan. Ketik `COMMIT` untuk menyimpan; selain itu transaksi di-rollback.

## Target
Database `ParamEngine`, tabel `dbo.ParamGetDDMAST`. File SQL deployment ditulis ke folder `output` di bawah direktori Settlement.


### Jika filter UPDATE menemukan beberapa record

Jika filter awal cocok dengan lebih dari satu record, wizard akan menampilkan daftar identitas key (`ProductId`, `Task`, `Activity`, atau key sesuai activity). Pilih nomor record yang benar. Wizard kemudian menggunakan seluruh kolom key untuk memastikan UPDATE hanya menargetkan satu record. Jika hasilnya terlalu banyak, batasi filter terlebih dahulu.


### Pilihan menu

Pada prompt `Pilih menu (0/1/2):`, masukkan `1` untuk INSERT, `2` untuk UPDATE, atau `0` untuk keluar. Tidak ada pilihan default; tekan Enter saja tidak akan otomatis memilih INSERT.
