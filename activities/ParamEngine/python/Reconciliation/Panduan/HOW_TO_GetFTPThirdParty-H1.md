# HOW TO — Wizard INSERT / UPDATE GetFTPThirdParty-H1 (Synqra 1.0)

**Database:** `ParamEngine`  
**Tabel:** `dbo.ParamFTP`  
**Activity:** `GetFTPThirdParty-H1`  
**Script:** `GetFTPThirdParty_H1.py`

## 1. Definisi

`GetFTPThirdParty_H1.py` adalah wizard CLI Python untuk menambahkan (INSERT) atau mengubah (UPDATE) **satu record konfigurasi per proses** pada `ParamEngine.dbo.ParamFTP`. Operator memilih aksi di awal. UPDATE menggunakan filter pencarian dan Common Table Expression (CTE). Wizard menampilkan data lama, preview, membuat backup tabel, menjalankan perubahan dalam transaksi, memperlihatkan SELECT hasil aktual sebelum COMMIT, lalu meminta keputusan COMMIT atau ROLLBACK.

> Ini alat konfigurasi FTP/SFTP, bukan proses transfer file dan bukan backup penuh database. Uji pada database development sebelum production.

## 2. Kegunaan

- **INSERT:** membuat konfigurasi baru; jika kombinasi `ProductId + Task + Activity` sudah ada, proses dibatalkan (tidak otomatis UPDATE).
- **UPDATE:** memilih kolom tertentu dari **tepat satu record** hasil filter; 0 atau lebih dari 1 record membatalkan proses.
- **CTE:** menentukan record target untuk UPDATE.
- **SELECT:** memeriksa data lama dan nilai aktual setelah perubahan, sebelum COMMIT.
- **BACKUP:** membuat salinan `dbo.ParamFTP` sebelum perubahan.
- **COMMIT:** menyimpan perubahan permanen, lalu membuat SQL deployment.
- **ROLLBACK:** membatalkan perubahan transaksi; backup terpisah tetap tersimpan.

## 3. Persiapan developer baru

1. Buka terminal pada root proyek `Synqra-1.0`.
2. Siapkan Python, `.venv`, `pyodbc`, ODBC Driver SQL Server, dan koneksi SQL Server.
3. Pastikan `db_config.py`, `db_connection.py`, dan script wizard ada di lokasi sesuai.
4. Periksa `SERVERS['2']` di `db_config.py`: versi script ini menggunakan **server key 2** dan tidak menampilkan menu pilih server.
5. Pastikan akun SQL Server mempunyai izin SELECT, INSERT, UPDATE, dan izin membuat tabel backup dengan `SELECT INTO` pada `ParamEngine`.
6. Gunakan credential testing untuk latihan; jangan memakai password production dalam dokumentasi.

Contoh struktur:

```text
Synqra-1.0/
├── db_config.py
├── db_connection.py
├── .venv/
└── activities/
    └── ParamEngine/
        ├── python/
        │   └── GetFTPThirdParty_H1.py
        └── output/
            └── GetFTPThirdParty-H1/
```

Jalankan dari root proyek (Mac):

```bash
cd /Users/a2345/Documents/Synqra-1.0
./.venv/bin/python activities/ParamEngine/python/Reconciliation/GetFTPThirdParty-H1.py
```

## 4. Alur proses

**Jalankan wizard → pilih INSERT/UPDATE → isi konfigurasi atau filter → cek record → preview → konfirmasi `y` → backup → eksekusi transaksi → SELECT hasil aktual → ketik COMMIT atau ROLLBACK → SQL deployment dibuat hanya setelah COMMIT.**

Menu utama:

```text
GETFTPTHIRDPARTY-H1 | ParamEngine.dbo.ParamFTP
1. INSERT
2. UPDATE
0. Keluar
Pilih proses:
```

Ketik **nomor** `1`, `2`, atau `0`, bukan teks INSERT/UPDATE.

## 5. Contoh INSERT — dbo.ParamFTP

1. Pilih `1. INSERT`.
2. Isi nilai konfigurasi pada prompt (contoh dummy):

```text
ProductId: AYOCONECT
Task: AYOCONECT-TVKABEL
Activity [GetFTPThirdParty-H1]:
Action [GET]:
FTPType [SFTP]:
FTPAddress: sftp.example.com
FTPPort [22]:
FTPUser: user_testing
FTPPass: ********
FTPPassPhrase:
FTPisPassive [0]:
FTPencryption:
UseProxy [0]:
FTPPath: AYOCONECT/Source
LocalPath: ThirdParty
Filename: ayoconnect-{%d%m%Y}.csv
FilenameDownload:
LogActivityFilenameDateAdd [0]:
isActive [1]:
Note:
Script:
```

3. Tekan Enter untuk menggunakan nilai default pada prompt yang memiliki default. Password diketik tersembunyi.
4. Wizard mengecek duplikasi berdasarkan `ProductId`, `Task`, dan `Activity`. Jika sudah ada, INSERT dibatalkan; gunakan UPDATE bila memang ingin mengubahnya.
5. Periksa ringkasan `Perubahan` (password disamarkan). Ketik `y` pada `Buat backup dan mulai transaksi? (y/n)`.
6. Wizard membuat backup dan menjalankan INSERT dalam transaksi, kemudian menampilkan `HASIL AKTUAL DALAM TRANSAKSI (BELUM COMMIT)`.
7. Ketik **`COMMIT`** untuk menyimpan atau Enter/`ROLLBACK` untuk membatalkan.

Contoh SELECT pengecekan identitas:

```sql
SELECT *
FROM ParamEngine.dbo.ParamFTP
WHERE ProductId = 'AYOCONECT'
  AND Task = 'AYOCONECT-TVKABEL'
  AND Activity = 'GetFTPThirdParty-H1';
```

`FTPPass` dienkripsi dengan `dbo.fnEncrypt` dan suffix kunci `BR!` yang terkait `FTPAddress`.

## 6. Contoh UPDATE — dbo.ParamFTP

### Langkah 1 — Pilih UPDATE

Pilih `2. UPDATE` dari menu utama.

### Langkah 2 — Pilih filter

```text
Filter UPDATE (bisa beberapa field):
1. ProductId
2. Task
3. Activity
4. FTPAddress
5. FTPUser
6. Filename
7. isActive
Nomor filter (contoh 1,2,3): 1,2,3
Nilai ProductId: AYOCONECT
Nilai Task: AYOCONECT-TVKABEL
Nilai Activity: GetFTPThirdParty-H1
```

Jika `Activity` tidak dipilih sebagai filter, wizard menambahkan `Activity = 'GetFTPThirdParty-H1'` secara otomatis. Wizard menampilkan `SELECT DATA SEBELUM UPDATE`; **hasil harus tepat satu record**. Jika tidak, proses dihentikan.

### Langkah 3 — Pilih field yang diubah

Ketik `y` saat diminta melanjutkan. Wizard menampilkan daftar field yang bisa diubah, dengan nomor berdasarkan urutan daftar pada terminal. Contoh:

```text
Lanjut pilih field UPDATE? (y/n): y
Nomor field (pisahkan koma): 11,13
Nilai baru FTPPath: AYOCONECT/Source/New
Nilai baru Filename: ayoconnect-new-{%d%m%Y}.csv
```

Nomor **11 dan 13** pada daftar field UPDATE script saat ini masing-masing adalah `FTPPath` dan `Filename`; selalu cek menu yang muncul. `ProductId`, `Task`, dan `Activity` tidak bisa diubah melalui menu UPDATE. Kolom yang tidak dipilih **tidak masuk SET UPDATE**.

### Langkah 4 — Preview dan backup

Periksa ringkasan `Perubahan`, lalu ketik `y` pada prompt `Buat backup dan mulai transaksi? (y/n)`. Backup tabel dibuat sebelum mutasi.

### Langkah 5 — UPDATE dengan CTE

Ilustrasi konsep SQL (bukan script deployment lengkap):

```sql
BEGIN TRANSACTION;

;WITH TargetRows AS (
    SELECT *
    FROM ParamEngine.dbo.ParamFTP WITH (UPDLOCK, HOLDLOCK)
    WHERE ProductId = 'AYOCONECT'
      AND Task = 'AYOCONECT-TVKABEL'
      AND Activity = 'GetFTPThirdParty-H1'
)
UPDATE TargetRows
SET FTPPath = 'AYOCONECT/Source/New',
    Filename = 'ayoconnect-new-{%d%m%Y}.csv',
    LastModified = GETDATE();

SELECT ProductId, Task, Activity, FTPPath, Filename, LastModified
FROM ParamEngine.dbo.ParamFTP
WHERE ProductId = 'AYOCONECT'
  AND Task = 'AYOCONECT-TVKABEL'
  AND Activity = 'GetFTPThirdParty-H1';

-- Setelah verifikasi, pilih salah satu:
-- COMMIT TRANSACTION;
ROLLBACK TRANSACTION;
```

Wizard menggunakan parameter SQL untuk input dan mengecek bahwa filter menghasilkan tepat satu record.

### Langkah 6 — SELECT hasil sementara

Wizard menampilkan `HASIL AKTUAL DALAM TRANSAKSI (BELUM COMMIT)` pada koneksi yang sama. Periksa semua nilai; `FTPPass` dan `FTPPassPhrase` tidak ditampilkan.

### Langkah 7 — COMMIT atau ROLLBACK

```text
Ketik COMMIT untuk simpan, lainnya ROLLBACK [ROLLBACK]:
```

Ketik **`COMMIT`** persis dengan huruf kapital untuk menyimpan. Enter atau nilai lainnya memicu ROLLBACK. Setelah COMMIT, wizard membuat file SQL deployment.

## 7. Arti input khusus

| Input | Arti |
|---|---|
| `1` pada menu utama | INSERT |
| `2` pada menu utama | UPDATE |
| `0` | Keluar |
| `1,2,3` pada filter | Kombinasi beberapa kondisi pencarian |
| `11,13` pada field UPDATE | Pilih field bernomor 11 dan 13 pada menu aktual |
| Enter pada prompt dengan default | Gunakan default |
| `0` atau `1` | Nilai untuk kolom binary |
| `y` | Setuju melanjutkan |
| `n` | Batalkan |
| `COMMIT` | Simpan transaksi permanen |
| Enter atau `ROLLBACK` | Batalkan transaksi |
| `FTPPass` | Input password tersembunyi |

**Perhatian:** Pada UPDATE, kolom dipilih melalui nomor terlebih dahulu; Enter kosong saat diminta nilai baru tidak berarti otomatis skip field yang telah dipilih. Jangan memasukkan password sungguhan dalam dokumentasi.

## 8. Backup, transaksi, dan deployment

- Setelah konfirmasi `y`, wizard membuat backup tabel `dbo.ParamFTP` menggunakan `SELECT * INTO` dan nama bertimestamp `ParamFTP_Backup_<timestamp>`.
- Backup memakai koneksi terpisah dan disimpan sebelum mutasi, sehingga tetap ada setelah ROLLBACK terhadap perubahan utama.
- `SELECT INTO` menyalin data dan struktur kolom dasar, tetapi tidak otomatis menyalin indeks, constraint, trigger, atau permission.
- INSERT/UPDATE berjalan pada koneksi `autocommit=False`; SELECT hasil mutasi pada koneksi sama menampilkan nilai sebelum COMMIT.
- Jika memilih ROLLBACK, perubahan dibatalkan dan **SQL deployment tidak dibuat**.
- Setelah COMMIT, SQL deployment ditulis ke `activities/ParamEngine/output/GetFTPThirdParty-H1/` dengan nama `GetFTPThirdParty-H1_yyyy-mm-dd.sql` (timestamp tambahan bila nama sudah ada).
- SQL deployment tidak otomatis dijalankan. Script default menggunakan `ROLLBACK TRANSACTION` untuk keselamatan; perlu review sebelum diubah menjadi COMMIT.
- **File deployment dapat berisi password sebagai argumen plaintext `dbo.fnEncrypt`.** Batasi akses file dan jangan commit ke repository.
- Jika penulisan file gagal setelah COMMIT, perubahan di database tetap sudah permanen. Verifikasi langsung di SQL Server.

## 9. Lanjut proses berikutnya

Versi script ini menjalankan **satu aksi per eksekusi**, kemudian keluar. Untuk memproses record lain, jalankan ulang:

```bash
./.venv/bin/python activities/ParamEngine/python/GetFTPThirdParty_H1.py
```

## 10. Troubleshooting

| Gejala | Penyebab / tindakan |
|---|---|
| `KeyError: '2'` | Key server `2` tidak ada di `db_config.py` |
| `Filter harus menghasilkan tepat satu record` | Filter menghasilkan 0 atau lebih dari 1 record; persempit filter |
| `Record sudah ada. Pilih UPDATE.` | Kombinasi identitas sudah ada; gunakan UPDATE |
| `FTPPass wajib diisi` | Password wajib untuk INSERT |
| `FTPisPassive harus 0 atau 1` | Input hanya boleh `0` atau `1` |
| Backup gagal | Periksa izin `CREATE TABLE`, ruang database, dan koneksi |
| SELECT menunjukkan nilai baru tetapi setelah ROLLBACK kembali lama | Normal; perubahan belum permanen |
| File deployment tidak dibuat setelah ROLLBACK | Normal; file hanya dibuat setelah COMMIT |
| File deployment gagal setelah COMMIT | Database sudah berubah; periksa log dan status di SQL Server |

## 11. Checklist sebelum production

- [ ] Pastikan `SERVERS['2']` mengarah ke server yang benar.
- [ ] Pastikan database `ParamEngine` dan `dbo.ParamFTP` tersedia.
- [ ] Pastikan activity adalah `GetFTPThirdParty-H1`.
- [ ] Pilih INSERT atau UPDATE secara sadar.
- [ ] Pada UPDATE, filter harus menghasilkan tepat satu record.
- [ ] Periksa SELECT data lama dan kolom yang akan diubah.
- [ ] Pastikan backup dibuat sebelum perubahan.
- [ ] Verifikasi SELECT hasil aktual sebelum COMMIT.
- [ ] Jika ragu, pilih ROLLBACK.
- [ ] Lindungi credential dan file SQL deployment.
- [ ] Uji pada development/localhost terlebih dahulu.

> **Catatan:** Panduan disesuaikan dengan implementasi `GetFTPThirdParty_H1.py` yang tersedia. Perilaku SQL tetap perlu diuji terhadap skema, constraint, trigger, permission, dan fungsi enkripsi pada database tujuan.
