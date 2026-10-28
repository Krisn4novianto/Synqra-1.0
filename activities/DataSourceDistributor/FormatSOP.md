USE [DataSourceDistributor];
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
GO

/*==============================================================================
  GETDDHIST - PARAMDDHIST CONFIGURATION DEPLOYMENT

  TUJUAN:
      Insert konfigurasi GetDDHIST ke tabel dbo.ParamDDHIST.

  URUTAN DEPLOYMENT:
      1. Validasi konfigurasi target.
      2. Backup tabel sebelum melakukan perubahan.
      3. Insert parameter yang belum tersedia.
      4. Verifikasi hasil perubahan.
      5. Commit jika seluruh validasi berhasil.

  PERINGATAN:
      Script dapat berisi kredensial terenkripsi menggunakan dbo.fnEncrypt.
      Batasi akses file deployment.
==============================================================================*/


/*==============================================================================
  TAHAP 1 - VALIDASI PARAMETER TARGET
==============================================================================*/

-- Memastikan konfigurasi target belum terdaftar sebelum INSERT.


/*==============================================================================
  TAHAP 2 - BACKUP TABEL SEBELUM MELAKUKAN PERUBAHAN
==============================================================================*/

-- Backup dbo.ParamFitur jika parameter koneksi perlu ditambahkan.
-- Backup dbo.ParamDDHIST sebelum melakukan INSERT atau UPDATE.


/*==============================================================================
  TAHAP 3 - INSERT PARAMETER KE TABEL
==============================================================================*/

-- INSERT parameter koneksi jika belum tersedia.
-- INSERT konfigurasi GetDDHIST ke dbo.ParamDDHIST.


/*==============================================================================
  TAHAP 4 - VERIFIKASI HASIL INSERT PARAMETER
==============================================================================*/

-- Memastikan konfigurasi tersimpan sesuai parameter yang dimasukkan.


/*==============================================================================
  TAHAP 5 - COMMIT TRANSAKSI
==============================================================================*/

-- COMMIT jika validasi berhasil.
-- ROLLBACK otomatis jika terjadi kesalahan.


/*==============================================================================
  TAHAP 6 - TAMPILKAN HASIL INSERT PARAMETER KE TABEL
==============================================================================*/

-- Menampilkan record aktual dari dbo.ParamDDHIST.