# Synqra

**Synqra adalah asisten otomatis untuk membangun SQL konfigurasi database dan activity Data Engineering/ETL untuk Rekonsiliasi Enterprise 4 dan SOR.** Developer memilih database, memasukkan value yang sesuai kebutuhan, lalu Synqra membentuk script mengikuti template kolom dan urutan query yang telah ditetapkan. Tujuannya mengurangi pekerjaan berulang, menjaga konsistensi konfigurasi, dan memudahkan developer baru memahami alur tanpa harus mengetik ulang query panjang.

Nama **Synqra** menggambarkan sinkronisasi konfigurasi: mengenali konteks database, menggunakan konfigurasi yang sudah ada bila tersedia, membuat konfigurasi yang belum ada, menghubungkan ID antar-activity, dan menghasilkan file SQL yang siap direview. Synqra bukan alat yang bebas mengarang query dan bukan pengganti review atau approval production.

> **Prinsip utama:** template dan susunan kolom tetap; value yang disesuaikan. IP server, DBName, DBUser, password, FTPAddress, FTPUser, FTPPass, path, filter, dan value bisnis dimasukkan manual sesuai kebutuhan activity. Password disisipkan ke SQL sebagai argumen fungsi `dbo.fnEncrypt`; enkripsi dilakukan SQL Server saat script dijalankan, bukan oleh Python.

## 1. Apa yang dilakukan Synqra?

- **Database-first:** pilih database terlebih dahulu, lalu pilih atau buat activity di dalam konteks database itu.
- **Input-driven:** value tidak dikunci pada satu produk. Nama database, produk, dan activity ditentukan oleh developer saat menjalankan generator; tidak ada produk yang dikunci sebagai tujuan Synqra.
- **Template-driven:** kolom, urutan `INSERT`, dan pola SQL mengikuti template yang disediakan. Developer fokus mengisi value yang benar.
- **Reuse before create:** jika record `ParamFitur` sudah ada, Synqra menggunakan record existing dan mengambil ID yang benar; INSERT awal dilewati.
- **Activity terpisah:** setiap activity menghasilkan file SQL sendiri agar bisa direview, dijalankan, dan ditelusuri secara terpisah.
- **No hidden execution:** generator menulis file SQL, bukan otomatis menjalankannya. Eksekusi production tetap mengikuti akses dan approval.
- **Secure-by-consciousness:** password diminta secara tersembunyi di terminal. File hasil SQL dapat memuat password plaintext sebagai argumen `dbo.fnEncrypt`, sehingga harus diperlakukan sebagai file sensitif.

## 2. Struktur project

```text
Synqra/
├── .idea
├── .venv 
├── .env
├── db_config.py
├── db_connection.py
├── requirements.txt
├── README.md
├── How To Setup Config.md
├── docs
│   └── Synqra Architecture Process Flowchart.png
│    
├── activities/ 
│   ├── DataFlowParam/
│   │   ├── ParamServer.py
│   │   └── HOW_TO_DataFlowParam.md
│   │  
│   ├── DataSourceDistributor/
│   │   ├── output
│   │   └── python/
│   │       ├── GetDDHIST.py
│   │       ├── GetESBRevamp.py
│   │       ├── GetFTPReport.py
│   │       ├── ParseFile.py
│   │       ├── HOW_TO_GetDDHIST.md
│   │       ├── HOW_TO_GetESBRevamp.md
│   │       ├── HOW_TO_GetFTPReport.md
│   │       └── HOW_TO_ParseFile.md  
│   │                 
│   ├── OtomasiMCS/
│   │   └── python/
│   │       ├── OtomasiMCS.py
│   │       └── HOW_TO_OtomasiMCS.md
│   │  
│   ├── ParamEngine/
│   │   └── python/
│   │       ├── Control Report
│   │       │   ├── Panduan
│   │       │   │   ├── HOW_TO_ControlReportGeneratedTime.py
│   │       │   │   ├── HOW_TO_FlaggingCategories-H1.py
│   │       │   │   ├── HOW_TO_GenPoskaCredit.py
│   │       │   │   ├── HOW_TO_GenPoskaCreditLainnya.py
│   │       │   │   ├── HOW_TO_GenPoskaDebit.py
│   │       │   │   ├── HOW_TO_GenPoskaDebitLainnya.py
│   │       │   │   ├── HOW_TO_GetDdhist-H1.py
│   │       │   │   ├── HOW_TO_GetDdmast-H1.py
│   │       │   │   ├── HOW_TO_UpdateControlReport-H1.py
│   │       │   │   └── HOW_TO_UpdateDraftControlReport-H1.py
│   │       │   │ 
│   │       │   ├── ControlReportGeneratedTime.py
│   │       │   ├── FlaggingCategories-H1.py
│   │       │   ├── GenPoskaCredit.py
│   │       │   ├── GenPoskaCreditLainnya.py
│   │       │   ├── GenPoskaDebit.py
│   │       │   ├── GenPoskaDebitLainnya.py
│   │       │   ├── GetDdhist-H1.py
│   │       │   ├── GetDdmast-H1.py
│   │       │   ├── UpdateControlReport-H1.py
│   │       │   └── UpdateDraftControlReport-H1.py
│   │       │ 
│   │       ├── GenerateTemplateActivityReconciliation
│   │       │   ├── GenerateTemplateActivityReconciliation.py 
│   │       │   └── HOW_TO_GenerateTemplateActivityReconciliation.md
│   │       │ 
│   │       ├── ParamCriteria
│   │       │   ├── HOW_TO_ParamCriteria.md
│   │       │   └── ParamCriteria.py
│   │       │ 
│   │       ├── Reconciliation
│   │       │   ├── Panduan
│   │       │   ├── GetESBThirdParty-H1.py
│   │       │   ├── GetFTPThirdParty-H1.py
│   │       │   ├── GetMasterBRI-H1.py
│   │       │   ├── GetMasterThirdParty-H1.py
│   │       │   ├── ParseFileThirdParty-H1.py
│   │       │   ├── Reconcile-H1.py
│   │       │   ├── ReconcileSummary-H1.py
│   │       │   ├── UpdateESB-H1.py
│   │       │   ├── UpdateMasterBRI-H1.py
│   │       │   └── UpdateThresholdValue-H1.py 
│   │       │ 
│   │       └── Settlement
│   │           ├── Panduan
│   │           ├── FlaggingCategories-H1.py
│   │           ├── GetDdhist-H1.py
│   │           ├── GetDdmast-H1.py
│   │           └── GetThirdPartyDataSettlement-H1.py
│   │       
│   ├── RekonEnterpriseAPI
│   │   └── python/
│   │       ├── Flow Design.png
│   │       ├── HOW_TO_RekonEnterpriseAPI.md
│   │       └── RekonEnterpriseAPI.py
│   │
│   ├── RekonParam/  
│   │   └── python/   
│   │       ├── HOW_TOP_RekonParam.md    
│   │       └── RekonParam.py      
│   │       
│   ├── GenerateScriptDeploy
│   │   ├── output
│   │   ├── GenerateScriptDeploy-DataFlowParam.py
│   │   ├── GenerateScriptDeploy-DataSourceDistributor.py
│   │   ├── GenerateScriptDeploy-Enterprise4.py
│   │   ├── GenerateScriptDeploy-OtomasiMCS.py
│   │   ├── GenerateScriptDeploy-ParamEngine.py
│   │   ├── GenerateScriptDeploy-RekonParam.py  
│   │   └── HOW_T0_GenerateScriptDeploy.md
└── output/                          
```

Folder database berisi activity yang relevan dengan database itu. Di dalam database, setiap activity disimpan sebagai file terpisah. Nama database dan activity ditentukan melalui input developer; generator tidak mengunci satu produk sebagai tujuan.

## 3. Persiapan environment

Gunakan Python 3.10+ dan pastikan akses database sesuai environment kerja.

### macOS / Linux

```bash
cd Synqra
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

### Windows PowerShell

```powershell
cd Synqra
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Pastikan ODBC Driver SQL Server tersedia jika menggunakan fitur koneksi Python. Jangan commit `.env` atau konfigurasi yang memuat credential.

## 4. Menjalankan Synqra

```bash
python main.py
```

Menu utama:

1. **Pilih Database → Activity Builder** — memilih database dan membuka workflow yang didukung.
2. **Tes koneksi / lihat database** — menguji konfigurasi koneksi Python.
3. **Generate SQL DataSourceDistributor** — wizard input manual untuk menghasilkan file `ParamFitur`, `GetDDHIST`, `GetFTPReport`, `ParseFile`, dan `TarikESBRevamp` secara terpisah.
4. **Generate SQL DataFlowParam (contoh)** — generator contoh untuk konfigurasi Summary Subscription/Redemption yang sudah ada di repository. Nama produk pada contoh bukan tujuan umum Synqra.
5. **INSERT RekonEnterpriseAPI** — wizard input per kolom, cek existing, transaksi, verifikasi, COMMIT/ROLLBACK, dan SQL output.\n0. Keluar.

Untuk menjalankan generator DataSourceDistributor langsung:

```bash
python -m activities.DataSourceDistributor.generate_sql
```

## 5. Alur standar: ParamFitur menjadi titik awal

```text
Pilih database
    ↓
Input manual identitas server + DBName + user + password
    ↓
Cek ParamFitur menggunakan key yang sesuai
    ├── Sudah ada → jangan INSERT ulang → ambil IDFitur existing
    └── Belum ada → buat INSERT ParamFitur → ambil IDFitur
    ↓
Generate satu file SQL untuk setiap activity yang diperlukan
    ↓
Review value + kondisi IF NOT EXISTS + relasi ID
    ↓
Jalankan file secara terpisah sesuai urutan dan approval
    ↓
Verifikasi record di database
```

`ParamFitur` adalah titik awal untuk workflow DataSourceDistributor yang didokumentasikan di sini. Akan tetapi, skema database berbeda bisa memakai nama tabel dan key berbeda; jangan mengasumsikan `IDFitur`, `FiturID`, dan `IdServer` adalah ID yang sama.

### Jika ParamFitur sudah tersedia

1. Pastikan `IPServer` dan `DBName` yang dicari benar.
2. Gunakan ID dari record existing yang cocok.
3. Lewati INSERT `ParamFitur`.
4. Generate/jalankan hanya konfigurasi activity yang belum tersedia.
5. Jangan menganggap activity lanjutan sudah ada hanya karena `ParamFitur` tersedia.

### Jika ParamFitur belum tersedia

1. Isi server, database, user, password, dan tipe database secara manual.
2. Review `00_paramfitur.sql`.
3. Script memakai `dbo.fnEncrypt(password, IPServer + 'BR!')` untuk value `DBPass`.
4. Jalankan script sesuai prosedur, lalu pastikan record dan `IDFitur` berhasil tersedia.
5. Lanjutkan ke file SQL activity terkait.

## 6. DataSourceDistributor: panduan developer baru

Panduan lengkap ada di [`activities/DataSourceDistributor/README.md`](activities/DataSourceDistributor/README.md).

Generator menulis file ke `activities/DataSourceDistributor/<DBName>/generated/`:

- `00_paramfitur.sql`
- `01_getddhist.sql`
- `02_getftpreport.sql`
- `03_parsefile.sql`
- `04_getesb.sql`
- `05_parsefile_cek_log_activity.sql`
- `06_parsefile_mapping_column.sql`
- `07_tarik_esb_revamp.sql`

Setiap file memiliki `USE [DataSourceDistributor]`, mencari `IDFitur` dari `ParamFitur`, dan menggunakan pengecekan duplikasi yang sesuai dengan konfigurasi activity. Input FTP password akan muncul di output SQL sebagai argumen `dbo.fnEncrypt(FTPPass, FTPAddress + 'BR!')`. Ini sesuai pola SQL yang diminta: Python tidak mengenkripsi password; fungsi SQL Server yang melakukannya saat query dijalankan.

Generator menyiapkan konfigurasi `ParamFitur`, `ParamDDHIST`, `ParamFTP`, `ParamParseFile`, `ParamESB`, `ParamParseFileCekLogActivity`, `ParamParseFileMappingColumn`, dan `ParamESBRevamp` secara terpisah. Konfigurasi bisnis seperti `FieldSelect`, `WhereCondition`, rekening, table destination, path, filename, log module/submodule/entity, dan status harus diisi dengan value yang sesuai requirement. Review sintaks SQL expression sebelum menjalankan.

## 7. Database lain

### DataFlowParam

Folder `activities/DataFlowParam/<NamaActivity>/` disiapkan untuk template DataFlowParam per activity. Tambahkan template yang sudah divalidasi terhadap schema aktual dan gunakan input manual untuk value yang berubah.

### OtomasiMCS

Folder `activities/OtomasiMCS/BRImoASDP/` merupakan template contoh `ParamFitur` OtomasiMCS. Alur ini menggunakan skema berbeda dari DataSourceDistributor. Perhatikan perbedaan `FiturID` dan `IDFitur` serta konfigurasi lanjutan seperti `ParamQryPembukuanRekonESB`.

### RekonParam

Activity Python tersedia di `activities/RekonParam/`. Ikuti wizard dan panduan lokal untuk activity RekonParam. Jangan menggunakan asumsi struktur DataSourceDistributor pada database ini.

## 8. Password dan enkripsi

Synqra meminta password melalui input tersembunyi di terminal. Untuk DataSourceDistributor, SQL hasil generate mengikuti pola:

```sql
DBPass = dbo.fnEncrypt(N'<DBPass yang diinput>', N'<IPServer>' + N'BR!')
```

Untuk FTP:

```sql
FTPPass = dbo.fnEncrypt(N'<FTPPass yang diinput>', N'<FTPAddress>' + N'BR!')
```

Python tidak mencoba meniru algoritma enkripsi SQL Server. Fungsi `dbo.fnEncrypt` baru dipanggil ketika SQL hasil generate dijalankan. Karena itu file SQL yang dihasilkan tetap mengandung password plaintext di dalam argumen fungsi dan wajib diperlakukan sebagai secret: jangan commit, jangan kirim ke kanal publik, batasi akses, dan hapus sesuai kebijakan internal.

## 9. Checklist sebelum menjalankan SQL

- [ ] Database tujuan benar (`DataSourceDistributor`, `DataFlowParam`, `OtomasiMCS`, atau `RekonParam`).
- [ ] IPServer, DBName, DBUser, dan password sudah divalidasi.
- [ ] Record `ParamFitur` existing dicek dengan key yang benar.
- [ ] `IDFitur` diambil dari record yang tepat, bukan diketik/di-hardcode dari database lain.
- [ ] Semua value bisnis, ekspresi `FieldSelect`, `WhereCondition`, rekening, path, filename, dan status sudah direview.
- [ ] `IF NOT EXISTS` memakai key activity yang benar.
- [ ] File SQL output disimpan secara aman.
- [ ] Ada approval sebelum menjalankan ke production.
- [ ] Setelah eksekusi, record dan relasi ID diverifikasi.

## 10. Troubleshooting

**`ModuleNotFoundError`** — aktifkan virtual environment, jalankan `pip install -r requirements.txt`, lalu jalankan perintah dari root repository.

**Koneksi SQL Server gagal** — cek VPN/jaringan, ODBC Driver, server, port, user, permission, dan konfigurasi `.env`. Generator SQL yang hanya menulis file tidak membutuhkan koneksi aktif.

**SQL masih berisi placeholder atau value kosong** — jangan jalankan. Lengkapi input dan generate ulang.

**Record tidak dibuat** — periksa key `IF NOT EXISTS`, permission, nama kolom, tipe data, dan apakah record existing memang cocok dengan kondisi pencarian.

**Password tidak terlihat saat diketik** — ini perilaku normal karena input password disembunyikan. Di file SQL, password akan berada di dalam argumen `dbo.fnEncrypt`, sehingga file output harus dijaga.

---

**Synqra — input manual yang terarah, SQL konsisten, konfigurasi lebih mudah ditelusuri.**


## Dokumentasi per activity
Lihat `HowTo.md` di root dan `HowTo.md` pada setiap folder activity. Generator dan file SQL tiap tahap sengaja dipisahkan mengikuti dependency; jangan gabungkan seluruh konfigurasi menjadi satu SQL monolitik.


## 11. INSERT RekonEnterpriseAPI

Wizard ada di `activities/RekonEnterpriseAPI/python/InsertRekonEnterpriseAPI.py`. Dari root project jalankan:

```bash
python3 activities/RekonEnterpriseAPI/python/InsertRekonEnterpriseAPI.py
```

Atau jalankan `python3 main.py` lalu pilih menu 5. Nilai dimasukkan satu kolom per prompt, bukan daftar kolom yang dipisahkan koma. Wizard membaca skema dari database `RekonEnterpriseAPI`, mengecek record existing berdasarkan kondisi `WHERE`, melakukan INSERT sementara, menampilkan hasil, lalu meminta `COMMIT` atau `ROLLBACK`. File SQL disimpan ke `activities/RekonEnterpriseAPI/generated/` dan tidak dieksekusi otomatis. Detail lengkap ada di `activities/RekonEnterpriseAPI/HowTo.md`.

Pada wizard ini, `DBPass` disimpan tanpa enkripsi sesuai kebutuhan tahap ini. File output dapat berisi credential plaintext dan harus dijaga sebagai file sensitif.
