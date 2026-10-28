# Synqra — OtomasiMCS Activity How-To

## 1. Tujuan

Panduan ini menjelaskan cara menjalankan activity `OtomasiMCS`, mulai dari persiapan Python, pengisian konfigurasi tiga tabel, validasi terhadap database, hingga menghasilkan file SQL deployment.

Activity ini menyiapkan konfigurasi untuk tiga tabel:

1. `dbo.ParamFitur`
2. `dbo.ParamQryPembukuanRekonESB`
3. `dbo.ParamFiturCekLogActivity`

**Penting:** Python hanya membaca database untuk validasi. Python tidak menjalankan `INSERT`, `UPDATE`, atau `COMMIT` terhadap konfigurasi. Perubahan baru dilakukan jika file SQL hasil generate dijalankan secara terpisah.

## 2. Persiapan Environment

Jalankan seluruh perintah dari root repository `Synqra Version 1`.

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Pastikan VPN, driver ODBC SQL Server, dan akses database tersedia.

## 3. Menjalankan Activity

Jalankan perintah berikut dari root proyek:

```bash
./.venv/bin/python activities/OtomasiMCS/python/OtomasiMCS.py
```

Ganti `<nama_file>` dengan nama file Python activity yang sebenarnya, tanpa ekstensi `.py`.

Alternatifnya, jalankan file secara langsung menggunakan path yang sesuai dengan struktur repository.

**Catatan:** nama file entry point belum dapat dipastikan dari kode yang tersedia. Gunakan nama file yang berisi fungsi `run()` dan blok `if __name__ == "__main__"` tersebut.

## 4. Alur Penggunaan

### Langkah 1 — Kumpulkan konfigurasi ParamFitur

Program meminta nilai untuk `dbo.ParamFitur`.

| Input | Penjelasan |
|---|---|
| `IDFitur` | ID fitur yang ditentukan secara manual. Harus berupa integer. |
| `Modul` | Nama modul konfigurasi. |
| `Name` | Nama fitur. |
| `FiturID` | Identitas fitur sesuai konfigurasi target. |
| `SettlementTarget` | Target settlement. |
| `MaxCount` | Batas jumlah sesuai konfigurasi. |
| `IPServer` | IP server yang digunakan pada konfigurasi fitur. |
| `DBName` | Nama database sumber. |
| `DBUser` | Username database sumber. |
| `DBPass` | Password database sumber. Input password tidak ditampilkan di terminal. |
| `SourceTable` | Tabel sumber data. |
| `WhereCondition` | Kondisi filter sumber data. |
| `DateCol` | Kolom tanggal. |
| `StatusCol` | Kolom status. |
| `MakerCol` | Kolom maker. |
| `CheckerCol` | Kolom checker. |
| `SignerCol` | Kolom signer. |
| `OldestDataDate` | Batas tanggal data tertua. |
| `SchStart` | Awal jadwal. |
| `SchEnd` | Akhir jadwal. |
| `StatusValueApproved` | Nilai status approved. |
| `isOtomasiMCS` | Flag otomasi, hanya `0` atau `1`. |
| `StatusValuePrepareSendSettlement` | Status persiapan pengiriman settlement. |
| `StatusValueDoneSendSettlement` | Status setelah pengiriman settlement selesai. |
| `isSendSettlement` | Flag pengiriman settlement, hanya `0` atau `1`. |

Masukkan nilai sesuai konfigurasi target yang telah disetujui. Jangan menggunakan contoh konfigurasi sebagai nilai produksi tanpa verifikasi.

### Langkah 2 — Kumpulkan konfigurasi ParamQryPembukuanRekonESB

Program kemudian meminta nilai konfigurasi untuk `dbo.ParamQryPembukuanRekonESB`.

Kolom yang diminta meliputi:

- `IdTrans`
- `AppName`
- `TranCode`
- `BranchCode`
- `TellerId`
- `SupervisorId`
- `Bucket1` sampai `Bucket20`
- `ThirdPartyName`
- `TellerRemark1`
- `TellerRemark2`
- `DefaultCurrency`
- `AlternateCurrency1` sampai `AlternateCurrency3`
- `Seq`
- `DateTrans`

Isi seluruh kolom berdasarkan template rekonsiliasi yang sudah divalidasi.

**Perhatian:** program memperlakukan nilai dari input tabel ini sebagai teks SQL. Jika nilai membutuhkan ekspresi SQL, pastikan penulisannya benar dan tinjau hasil SQL sebelum deployment.

### Langkah 3 — Kumpulkan konfigurasi ParamFiturCekLogActivity

Program meminta konfigurasi untuk `dbo.ParamFiturCekLogActivity`.

| Input | Penjelasan |
|---|---|
| `LogActivityModul` | Modul untuk pencatatan aktivitas. |
| `LogActivitySubModul` | Submodul; boleh dikosongkan. |
| `LogActivityEntity` | Entitas aktivitas. |
| `LogActivityDateAdd` | Nilai tanggal sesuai schema target. |
| `IsActive` | Status aktif, hanya `0` atau `1`. |

Input opsional yang dikosongkan akan diubah menjadi SQL `NULL` pada skrip yang dihasilkan.

### Langkah 4 — Validasi database

Program memvalidasi konfigurasi dengan koneksi yang ditentukan pada implementasi, yaitu `SERVERS["2"]`, ke database `OtomasiMCS`.

Pemeriksaan meliputi:

- Apakah `IDFitur` sudah digunakan.
- Apakah kombinasi `Modul`, `Name`, dan `FiturID` sudah ada.
- Apakah konfigurasi pada `ParamQryPembukuanRekonESB` ditemukan untuk ID tersebut.
- Apakah konfigurasi terkait ditemukan pada `ParamFiturCekLogActivity`.

Jika `IDFitur` sudah digunakan oleh fitur lain, proses pembuatan SQL dibatalkan untuk mencegah benturan ID.

Periksa hasil validasi sebelum melanjutkan.

### Langkah 5 — Periksa ringkasan konfigurasi

Program menampilkan ringkasan, termasuk:

- `Modul`
- `Name`
- `FiturID`
- `IDFitur` input
- `IPServer`
- Jumlah tabel konfigurasi target

Pastikan semua identitas fitur sesuai dengan kebutuhan sebelum menyetujui pembuatan file.

### Langkah 6 — Setujui pembuatan SQL

Program menampilkan prompt:

```text
Buat file SQL dari bahan input ini? [y/N]:
```

Masukkan `y` atau `yes` untuk menyetujui pembuatan file SQL.

Masukkan nilai lain atau tekan Enter untuk membatalkan.

Menyetujui prompt ini **hanya membuat file SQL**. Database tidak berubah pada tahap ini.

### Langkah 7 — Review file SQL deployment

Skrip yang dihasilkan mencakup konfigurasi ketiga tabel dengan pemeriksaan `IF NOT EXISTS` sesuai template implementasi.

Sebelum menjalankannya:

1. Pastikan database tujuan `OtomasiMCS` benar.
2. Periksa `IDFitur`, identitas fitur, dan IP server.
3. Periksa seluruh nilai pada tiga tabel.
4. Pastikan record yang sudah ada tidak akan dilewati ketika seharusnya diperbarui.
5. Periksa keamanan file karena skrip memuat password sumber sebagai input literal yang kemudian dienkripsi melalui `dbo.fnEncrypt`.
6. Jalankan hanya setelah review dan persetujuan sesuai prosedur deployment.

Lokasi output mengikuti konfigurasi `finish_activity`, dengan folder dasar `output/03_Settlement_MCS`.

## 5. Perilaku terhadap Konfigurasi Existing

Skrip yang dihasilkan menggunakan pola insert bersyarat, bukan mekanisme update otomatis.

Artinya:

- Jika natural key `ParamFitur` belum ada, skrip mencoba melakukan insert.
- Jika natural key sudah ada, insert `ParamFitur` dilewati.
- Jika konfigurasi rekonsiliasi berdasarkan `IDFitur` sudah ada, insert dilewati.
- Jika konfigurasi log berdasarkan `IDFitur`, `LogActivityModul`, dan `LogActivityEntity` sudah ada, insert dilewati.

**Penting:** record existing yang nilainya berbeda tidak otomatis diperbarui. Review hasil validasi dan skrip dengan cermat sebelum deployment.

## 6. Troubleshooting

| Kendala | Pemeriksaan |
|---|---|
| Koneksi database gagal | Periksa VPN, konfigurasi `SERVERS["2"]`, driver ODBC, dan izin akses. |
| `IDFitur` tidak valid | Pastikan input berupa integer. |
| `IDFitur` sudah digunakan fitur lain | Tentukan ID yang benar dan lakukan validasi ulang. |
| SQL tidak dibuat | Periksa input, hasil validasi, dan persetujuan pembuatan file. |
| Konfigurasi existing dilewati | Periksa kondisi `IF NOT EXISTS` dan bandingkan nilai existing dengan target. |
| File SQL gagal dijalankan | Periksa schema tabel, constraint, fungsi `dbo.fnEncrypt`, dan nilai input. |

## 7. Checklist Developer

- [ ] Environment Python aktif.
- [ ] Koneksi database tersedia.
- [ ] `IDFitur` dan identitas fitur sudah diverifikasi.
- [ ] Input ketiga tabel sudah lengkap.
- [ ] Hasil validasi database sudah diperiksa.
- [ ] File SQL sudah ditinjau.
- [ ] Password dan informasi sensitif dilindungi.
- [ ] Deployment dilakukan secara terpisah setelah persetujuan.

**Prinsip utama:** OtomasiMCS menggunakan input manual, validasi read-only, dan SQL deployment yang ditinjau sebelum dijalankan. Jangan menganggap pembuatan file SQL sama dengan perubahan database.
