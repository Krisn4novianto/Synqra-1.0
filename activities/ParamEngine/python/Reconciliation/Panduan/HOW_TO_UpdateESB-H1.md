# HOW TO — UpdateESB-H1

## Tujuan
Wizard konfigurasi `ParamEngine.dbo.ParamRecon` untuk activity `UpdateESB-H1`. Profil koneksi `SERVERS["4"]`, host `172.18.246.102`, database `ParamEngine`.

## Instalasi
Simpan `UpdateESB-H1.py` di `activities/ParamEngine/python/` pada root proyek Synqra-1.0. Pastikan `db_config.py` berisi kredensial profil server `4` dan `db_connection.py` tersedia. Jalankan dari root proyek:

```bash
./.venv/bin/python activities/ParamEngine/python/Reconciliation/UpdateESB-H1.py
```

## INSERT
1. Pilih `1. INSERT`.
2. Isi `ProductId`, `Task`, dan parameter lainnya. `Activity` otomatis `UpdateESB-H1`. Tekan Enter untuk memakai nilai default yang ditawarkan.
3. Untuk field panjang seperti `Source1Where` atau `SPExecute`, masukkan teks dan akhiri dengan baris `.SELESAI` (atau langsung `.SELESAI` untuk memakai default).
4. Periksa **PREVIEW INSERT**, ditampilkan `NamaField = Nilai` per baris.
5. Ketik `y` untuk membuat backup seluruh tabel dan mulai transaksi.
6. Periksa hasil `SELECT` sementara, lalu ketik persis `COMMIT` untuk menyimpan. Selain itu proses di-ROLLBACK.
7. Setelah COMMIT, wizard menghasilkan SQL deployment pada `activities/ParamEngine/output/UpdateESB-H1/`.

## UPDATE
1. Pilih `2. UPDATE`.
2. Isi kunci `ProductId`, `Task`, `Activity` otomatis; `OrderExecute` juga wajib diisi.
3. Periksa data lama. Pilih nomor field yang ingin diubah (dipisahkan koma).
4. Periksa preview perubahan, lakukan backup, verifikasi sementara, dan COMMIT/ROLLBACK.
5. `LastModified` otomatis diperbarui dengan `GETDATE()`.

## Kolom waktu
`InsertDate` dan `LastModified` **tidak ditanyakan** pada INSERT; keduanya diisi `GETDATE()` oleh SQL Server. UPDATE mempertahankan `InsertDate` lama dan hanya mengubah `LastModified = GETDATE()`.

## SQL deployment via DBeaver
1. Buka SQL deployment hasil COMMIT dan review target, filter, serta nilainya.
2. Backup deployment otomatis dibuat sebagai tabel `dbo.ParamRecon_Backup_...`.
3. Default `DECLARE @ApproveCommit BIT = 0` berarti **ROLLBACK**. Untuk menyimpan saat deployment, ubah ke `1` setelah review dan persetujuan.
4. Jalankan seluruh script pada koneksi database `ParamEngine`, periksa hasil verifikasi sebelum COMMIT.
5. SQL deployment mereproduksi perubahan, jadi **jangan jalankan INSERT deployment pada database yang sudah menerima INSERT wizard yang sama**: pemeriksaan duplikat akan menolaknya. Deployment dimaksudkan untuk lingkungan target lain.

## Catatan
- `Source1Where`, `Source2UpdateData1..10`, `SPExecute`, dan ekspresi lain disimpan sebagai **teks konfigurasi**, bukan dieksekusi saat wizard berjalan.
- SQL deployment dihasilkan **hanya setelah COMMIT** dan file diberi izin `0600` jika didukung OS.
- Wizard belum diuji terhadap database live; pastikan nama kolom, tipe data, dan izin tabel sesuai skema aktual.
