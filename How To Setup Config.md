# Synqra — Panduan Setup Python dari Nol

Panduan ini digunakan untuk menyiapkan environment Python sebelum menjalankan activity Synqra. Langkah dibedakan untuk **Windows** dan **macOS/Linux**.

Developer tidak perlu menjalankan `main.py` jika file Python activity memiliki entrypoint mandiri. Jalankan file activity sesuai panduan pada folder database masing-masing.

## 1. Persiapan sebelum memulai

Pastikan kamu sudah memiliki:

- Source code project Synqra.
- Python dengan versi yang kompatibel dengan dependency project.
- Terminal: PowerShell/Command Prompt pada Windows atau Terminal pada macOS/Linux.
- Akses jaringan untuk mengunduh dependency jika belum tersedia.
- Akses database dan konfigurasi koneksi yang diperlukan oleh activity yang akan dijalankan.

> **Penting:** Jika project memiliki file `.python-version`, `pyproject.toml`, atau dokumentasi versi Python, ikuti versi yang ditentukan di sana. Jangan langsung mengganti versi Python project ke versi terbaru tanpa memastikan kompatibilitasnya.

## 2. Setup awal — Windows

### Langkah 1 — Periksa apakah Python sudah terpasang

Buka **PowerShell** atau **Command Prompt**, kemudian jalankan:

```powershell
py --version
```

Untuk melihat versi Python yang terpasang:

```powershell
py -0p
```

Jika perintah `py` tidak dikenali, coba:

```powershell
python --version
```

Jika Python belum tersedia, lanjut ke langkah berikutnya.

### Langkah 2 — Instal Python

1. Buka https://www.python.org/downloads/windows/
2. Unduh versi Python yang kompatibel dengan project Synqra.
3. Jalankan installer.
4. Jika tersedia, aktifkan opsi **Add Python to PATH**.
5. Selesaikan instalasi.
6. Tutup dan buka kembali terminal.

Verifikasi instalasi:

```powershell
py --version
python --version
```

Jika salah satu perintah menampilkan versi Python yang sesuai, lanjutkan.

### Langkah 3 — Masuk ke root project

Gunakan terminal untuk berpindah ke folder utama Synqra, yaitu folder yang berisi `requirements.txt` dan direktori `activities`.

Contoh:

```powershell
cd "C:\path\ke\project\Synqra"
```

Sesuaikan path dengan lokasi project di komputer masing-masing.

Periksa isi folder:

```powershell
dir
```

Pastikan file `requirements.txt` ditemukan:

```powershell
Test-Path requirements.txt
```

Hasil yang diharapkan:

```text
True
```

Jika hasilnya `False`, periksa kembali lokasi folder project.

### Langkah 4 — Buat virtual environment

Jalankan:

```powershell
py -m venv .venv
```

Virtual environment `.venv` berfungsi memisahkan dependency Synqra dari package Python project lain di komputer.

Folder `.venv` cukup dibuat sekali untuk setiap checkout project. Jika folder tersebut sudah ada dan masih berfungsi, tidak perlu membuatnya kembali.

### Langkah 5 — Aktifkan virtual environment

**PowerShell:**

```powershell
.\.venv\Scripts\Activate.ps1
```

**Command Prompt (CMD):**

```bat
.venv\Scripts\activate.bat
```

Jika aktivasi berhasil, biasanya nama `(.venv)` muncul di awal prompt terminal.

Jika PowerShell menolak menjalankan script karena Execution Policy, kamu bisa menggunakan CMD sebagai alternatif. Jika memang diizinkan oleh kebijakan komputer, alternatif untuk sesi PowerShell saat ini adalah:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Pengaturan `Process` hanya berlaku untuk sesi PowerShell tersebut.

### Langkah 6 — Periksa Python yang digunakan

Setelah environment aktif, jalankan:

```powershell
python --version
python -m pip --version
where.exe python
```

Pastikan interpreter dan `pip` mengarah ke folder `.venv`, bukan Python global.

### Langkah 7 — Instal dependency

Perbarui `pip` di dalam virtual environment:

```powershell
python -m pip install --upgrade pip
```

Kemudian instal dependency project:

```powershell
python -m pip install -r requirements.txt
```

Tunggu hingga proses instalasi selesai. Jika tidak ada error, lanjutkan ke pengujian activity.

### Langkah 8 — Jalankan file activity

Contoh menjalankan beberapa activity dari root project:

```powershell
python activities\RekonEnterpriseAPI\python\InsertRekonEnterpriseAPI.py

python activities\DataSourceDistributor\python\GetDDHIST.py
python activities\DataSourceDistributor\python\GetESBRevamp.py
python activities\DataSourceDistributor\python\GetFTPReport.py
```

Gunakan file yang memang tersedia di project. Nama file di atas adalah contoh; sesuaikan dengan struktur source code aktual dan panduan activity masing-masing.

---

## 3. Setup awal — macOS

### Langkah 1 — Periksa instalasi Python

Buka **Terminal**, kemudian jalankan:

```bash
python3 --version
which python3
python3 -m pip --version
```

Jika Python sudah terpasang, pastikan versinya kompatibel dengan project.

Jika belum, unduh installer dari https://www.python.org/downloads/macos/ atau gunakan pengelola package yang sesuai dengan lingkungan kerja kamu.

Untuk komputer yang menggunakan Homebrew, instalasi Python dapat dilakukan dengan:

```bash
brew install python
```

Perintah tersebut memerlukan Homebrew yang sudah terpasang. Setelah instalasi, verifikasi kembali:

```bash
python3 --version
which python3
```

Jika project mensyaratkan versi Python tertentu, pastikan interpreter yang dipakai benar-benar menggunakan versi tersebut.

### Langkah 2 — Masuk ke root project

Contoh:

```bash
cd "/path/ke/project/Synqra"
```

Periksa file dan folder project:

```bash
ls
```

Pastikan `requirements.txt` berada di direktori saat ini.

### Langkah 3 — Buat virtual environment

```bash
python3 -m venv .venv
```

Jika `.venv` sudah tersedia dan ingin digunakan kembali, kamu dapat melewati langkah pembuatan environment.

### Langkah 4 — Aktifkan virtual environment

```bash
source .venv/bin/activate
```

Jika berhasil, prompt terminal biasanya menampilkan `(.venv)`.

### Langkah 5 — Periksa interpreter

```bash
python --version
python -m pip --version
which python
```

Pastikan `python` dan `pip` mengarah ke environment `.venv`.

**Catatan untuk pengguna macOS:** Perintah `python3` sebelum aktivasi dapat mengarah ke Python Homebrew atau instalasi lain. Setelah `.venv` aktif, gunakan `python` agar perintah mengarah ke interpreter dalam environment project.

### Langkah 6 — Instal dependency

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Jika proses instalasi berhasil, dependency yang didefinisikan dalam `requirements.txt` siap digunakan.

### Langkah 7 — Jalankan file activity

Jalankan perintah dari root project:

```bash
python activities/RekonEnterpriseAPI/python/InsertRekonEnterpriseAPI.py

python activities/DataSourceDistributor/python/GetDDHIST.py
python activities/DataSourceDistributor/python/GetESBRevamp.py
python activities/DataSourceDistributor/python/GetFTPReport.py
```

Sesuaikan nama file dengan activity yang ingin dijalankan.

---

## 4. Setup awal — Linux

Langkah Linux berikut menggunakan Ubuntu/Debian sebagai contoh. Untuk distribusi lain, sesuaikan perintah instalasi package dengan package manager yang digunakan.

### Langkah 1 — Periksa Python

```bash
python3 --version
which python3
```

Jika Python belum terpasang, jalankan:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip
```

Kemudian verifikasi:

```bash
python3 --version
python3 -m pip --version
```

Pastikan versi Python sesuai dengan kebutuhan project. Jangan menggunakan `sudo pip install` untuk memasang dependency project.

### Langkah 2 — Masuk ke root project

```bash
cd "/path/ke/project/Synqra"
ls
```

Pastikan kamu berada di folder yang berisi `requirements.txt` dan direktori `activities`.

### Langkah 3 — Buat virtual environment

```bash
python3 -m venv .venv
```

Jika pembuatan environment gagal karena modul `venv` belum tersedia, pastikan package `python3-venv` sudah terpasang. Pada beberapa versi distribusi, package tersebut mungkin perlu disesuaikan dengan versi Python yang digunakan.

### Langkah 4 — Aktifkan environment

```bash
source .venv/bin/activate
```

### Langkah 5 — Verifikasi dan instal dependency

```bash
python --version
python -m pip --version
which python

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Pastikan interpreter dan `pip` berasal dari `.venv`.

### Langkah 6 — Jalankan activity

```bash
python activities/RekonEnterpriseAPI/python/InsertRekonEnterpriseAPI.py

python activities/DataSourceDistributor/python/GetDDHIST.py
python activities/DataSourceDistributor/python/GetESBRevamp.py
python activities/DataSourceDistributor/python/GetFTPReport.py
```

Gunakan path relatif dari root project dan pastikan file yang dipanggil tersedia.

---

## 5. Menjalankan activity berikutnya

Setelah setup awal berhasil, kamu tidak perlu mengulang seluruh proses setiap kali ingin menjalankan activity.

Urutan yang perlu dilakukan:

1. Buka terminal.
2. Masuk ke root project Synqra.
3. Aktifkan virtual environment.
4. Jalankan file activity yang diperlukan.
5. Periksa hasil eksekusi dan pastikan konfigurasi database sudah benar.

### Perintah aktivasi berdasarkan sistem operasi

| Sistem operasi | Perintah aktivasi |
|---|---|
| Windows PowerShell | `.\.venv\Scripts\Activate.ps1` |
| Windows CMD | `.venv\Scripts\activate.bat` |
| macOS | `source .venv/bin/activate` |
| Linux | `source .venv/bin/activate` |

Untuk keluar dari virtual environment setelah selesai bekerja:

```bash
deactivate
```

Perintah tersebut dapat digunakan di PowerShell, CMD, macOS, maupun Linux setelah environment aktif.

---

## 6. Panduan activity Synqra

Setelah environment siap, pilih panduan sesuai database atau activity yang ingin dijalankan:

- `activities/DataSourceDistributor/HowTo.md`
- `activities/RekonEnterpriseAPI/HowTo.md`
- `activities/OtomasiMCS/HowTo.md`
- `activities/RekonParam/HowTo.md`
- `activities/DataFlowParam/HowTo.md`

Panduan tersebut menjelaskan kebutuhan konfigurasi, input, dan cara menjalankan masing-masing activity.

**Catatan khusus:**

- `RekonParam.py` membutuhkan konfigurasi activity. Ikuti panduan RekonParam sebelum menjalankannya.
- `OtomasiMCS.py` membutuhkan file `.common`. Pastikan file tersebut tersedia dan konfigurasi sudah sesuai dengan lingkungan kerja.
- Jangan mengasumsikan semua activity mempunyai cara input atau konfigurasi yang sama.

---

## 7. Troubleshooting

### Python tidak ditemukan

Periksa instalasi Python dan PATH. Pada Windows, coba `py --version`; pada macOS/Linux, coba `python3 --version`.

### Virtual environment tidak aktif

Aktifkan kembali `.venv` dengan perintah yang sesuai dengan sistem operasi. Jika folder `.venv` belum ada, buat terlebih dahulu menggunakan interpreter Python yang benar.

### `No module named ...`

Pastikan environment aktif, kemudian instal ulang dependency:

```bash
python -m pip install -r requirements.txt
```

Jika modul tersebut tidak tercantum dalam `requirements.txt`, periksa dokumentasi activity sebelum memasang package tambahan.

### `requirements.txt` tidak ditemukan

Pastikan terminal berada di root project, bukan di dalam folder activity.

### Koneksi database gagal

Periksa konfigurasi host, port, nama database, kredensial, VPN atau jaringan kantor, serta izin akses database. Setup Python yang berhasil tidak otomatis berarti koneksi database berhasil.

### Error driver database

Beberapa activity mungkin membutuhkan driver atau library sistem tambahan, misalnya driver ODBC untuk SQL Server. Instal sesuai kebutuhan activity dan sistem operasi; pemasangan package Python saja belum tentu cukup.

### File `.common` atau konfigurasi tidak ditemukan

Ikuti panduan activity terkait. Jangan membuat konfigurasi pengganti dengan nilai tebakan, terutama untuk host, password, dan parameter database.

---

## 8. Checklist sebelum menjalankan activity

- [ ] Python dengan versi yang kompatibel sudah terpasang.
- [ ] Terminal berada di root project Synqra.
- [ ] Virtual environment `.venv` sudah dibuat.
- [ ] Virtual environment sudah aktif.
- [ ] Interpreter dan `pip` mengarah ke `.venv`.
- [ ] Dependency dari `requirements.txt` sudah terpasang.
- [ ] File activity yang akan dijalankan tersedia.
- [ ] Konfigurasi activity dan akses database sudah siap.
- [ ] Panduan activity terkait sudah dibaca.

**Prinsip utama:** Setup environment dilakukan sekali per environment project. Untuk eksekusi berikutnya, cukup aktifkan `.venv`, pastikan konfigurasi siap, lalu jalankan file activity yang dibutuhkan. Jangan menjalankan `main.py` kecuali memang diperlukan oleh workflow tertentu.
