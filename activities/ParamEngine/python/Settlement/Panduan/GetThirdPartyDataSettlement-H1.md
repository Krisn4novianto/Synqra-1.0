# Panduan GetThirdPartyDataSettlement-H1

## Lokasi
`activities/ParamEngine/python/Settlement/python/GetThirdPartyDataSettlement-H1.py`

## Menjalankan
```bash
./.venv/bin/python "activities/ParamEngine/python/Settlement/GetThirdPartyDataSettlement-H1.py"
```

## Alur
1. Pilih Server 102 atau Lokal. Profil koneksi dibaca dari `db_config.py`; fungsi koneksi menggunakan `db_connection.py`.
2. Pilih **INSERT**, **UPDATE**, atau **Keluar**.
3. INSERT meminta `ProductId` dan `Task` serta menyediakan template field untuk diperiksa/diedit.
4. UPDATE meminta pilihan kolom filter, nilai filter, lalu memastikan filter mengarah ke tepat satu record. Pilih kolom yang ingin diperbarui atau `ALL` untuk semua kolom non-filter.
5. Tinjau preview. Ketik `LANJUT` untuk membuat backup dan menjalankan transaksi; ketik `COMMIT` untuk menyimpan, atau jawaban lain untuk rollback.

## Target
Database `ParamEngine`, tabel `dbo.ParamDataFlow`. Script membuat backup tabel, memverifikasi perubahan, dan membuat SQL deployment di folder `output`.


### Jika filter UPDATE menemukan beberapa record

Jika filter awal cocok dengan lebih dari satu record, wizard akan menampilkan daftar identitas key (`ProductId`, `Task`, `Activity`, atau key sesuai activity). Pilih nomor record yang benar. Wizard kemudian menggunakan seluruh kolom key untuk memastikan UPDATE hanya menargetkan satu record. Jika hasilnya terlalu banyak, batasi filter terlebih dahulu.


### Pilihan menu

Pada prompt `Pilih menu (0/1/2):`, masukkan `1` untuk INSERT, `2` untuk UPDATE, atau `0` untuk keluar. Tidak ada pilihan default; tekan Enter saja tidak akan otomatis memilih INSERT.
