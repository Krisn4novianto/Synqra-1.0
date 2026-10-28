#!/usr/bin/env python3
"""
===============================================================================
GETESBREVAMP - PARAMESBREVAMP CONFIGURATION WIZARD
===============================================================================
PANDUAN SINGKAT:
 1. Pilih koneksi SQL Server (Server 205 atau Localhost) dari db_config.py.
 2. Program terhubung langsung ke database DataSourceDistributor.
 3. Pilih INSERT atau UPDATE dari menu utama.
 4. INSERT: cari ParamFitur berdasarkan DBName atau buat ParamFitur baru.
 5. IDFitur yang terpilih/dibuat digunakan untuk record ParamESBRevamp.
 6. UPDATE: pilih tabel ParamFitur atau ParamESBRevamp yang akan diubah.
 7. Isi FieldSelect, WhereCondition, TableDestination, dan konfigurasi activity.
 8. Periksa preview dan verifikasi, lalu pilih COMMIT atau ROLLBACK.
 9. Setelah COMMIT, program membuat script deployment SQL.

KONFIGURASI TETAP:
 - Activity database : TarikESBRevamp.
 - LogActivityEntity default : GetESBRevamp.
 - Database konfigurasi : DataSourceDistributor.
 - Server yang didukung : 172.18.135.205:1433 dan localhost:1433.

SOP BACKUP:
 - Snapshot data ASLI dibuat pada database yang dipilih, SEBELUM DML.
 - Snapshot dibuat dalam transaksi TERPISAH dan di-COMMIT sebelum DML.
 - Snapshot tetap ada jika transaksi DML di-ROLLBACK.
 - INSERT/UPDATE hanya menyentuh tabel utama sekali; backup bukan duplikasi
   record pada tabel utama.
 - Pembatalan pada tahap preview tidak membuat backup.
 - Backup SELECT INTO tidak menyalin indeks, constraint, trigger, permission.
 - Snapshot bukan pengganti SQL Server BACKUP DATABASE (.bak).
 - SQL deployment mengimplementasikan SOP backup yang sama.

CATATAN KEAMANAN:
 - DBPass dienkripsi di SQL Server menggunakan dbo.fnEncrypt.
 - File deployment memakai variabel SQLCMD hanya bila password diperlukan.
 - Jangan simpan password asli di SQL atau version control.
 - Jalankan dan uji terlebih dahulu pada lingkungan development.
===============================================================================
"""
from __future__ import annotations
import sys
import uuid
from pathlib import Path
from datetime import datetime
from getpass import getpass

HERE = Path(__file__).resolve()
for parent in HERE.parents:
    if (parent / 'db_config.py').exists() and (parent / 'db_connection.py').exists():
        sys.path.insert(0, str(parent))
        break
from db_config import SERVERS
from db_connection import connect_sqlserver

# Database konfigurasi tetap; koneksi tidak memindai seluruh database SQL Server.
DATABASE = 'DataSourceDistributor'
PF = 'dbo.ParamFitur'
ACT = 'dbo.ParamESBRevamp'
# Kolom konfigurasi ParamESBRevamp; IDFitur menghubungkan ke dbo.ParamFitur.
FIELDS = ('IDFitur','FieldSelect','WhereCondition','TableDestination','LogActivityModul',
          'LogActivitySubModul','LogActivityEntity','isActive','Note','SchStart')
# Template FieldSelect bawaan. Operator dapat menggantinya saat input.
DEFAULT_FIELDS = (
    "BillRef, ExternalID, BillName, BillNo, [FeatureId] AS FiturID, Remark2, "
    "BillAuditNo, Remark3, Userid, Remark1, [CreditAccountNumber] AS AccKredit, "
    "TellerId, [DebetAccountNumber] AS AccDebet, "
    "CASE WHEN ISNUMERIC(JournalSeq) = 0 THEN JSON_VALUE(JSONData, '$.core.journalSequence') "
    "ELSE JournalSeq END AS JournalSeq, CAST([CreditAmountFee1] AS DECIMAL(18,2)) AS AmtFee, "
    "RootID, BillAmount, OriginalExternalID, BillCustNo, BillData, "
    "[CreditAccountNumberFee1] AS AccFee, BillInfo, BillDueDate, [JSONData] AS JSON_DATA, "
    "ChannelID, CardNo, [ResponseCode] AS Responcode, [TransactionTime] AS JamTrx, "
    "BillCorpCode, [TransactionDate] AS TanggalTrx, BillInfo1, BillInfo2, BillInfo3, "
    "[DebetAmountTransaction] AS AmtDebet, BillInfo4, [TerminalId] AS Termid, "
    "[CreditAmountTransaction] AS AmtKredit"
)
# Lokasi file SQL deployment yang dibuat setelah transaksi berhasil COMMIT.
OUTPUT = HERE.parent / 'output' / '01_Reconciliation' / 'GetESBRevamp'

# ===========================================================================
# CANCEL — Exception khusus untuk membatalkan input dan kembali ke menu tanpa melanjutkan operasi.
# ===========================================================================
class Cancel(Exception):
    pass

# ===========================================================================
# TITLE — Mencetak judul dan pemisah terminal dengan gaya konsisten seperti wizard GetDDHIST.
# ===========================================================================
def title(value):
    print('\n' + '='*72 + '\n' + value + '\n' + '='*72)

# ===========================================================================
# CHOOSE — Menerima pilihan menu yang valid; huruf B berarti batal dan ditangani oleh caller.
# ===========================================================================
def choose(message, valid):
    while True:
        try: value = input(message + ' (B=batal): ').strip().upper()
        except (EOFError, KeyboardInterrupt): raise Cancel()
        if value == 'B': raise Cancel()
        if value in valid: return value
        print('[WARNING] Pilihan tidak valid. Pilih: ' + ', '.join(sorted(valid)))

# ===========================================================================
# ASK — Membaca input pengguna, mendukung nilai default, input wajib, dan password tersembunyi.
# ===========================================================================
def ask(message, default=None, required=False, secret=False):
    while True:
        hint = f' [{default}]' if default is not None and not secret and len(str(default)) < 100 else ''
        try: value = (getpass if secret else input)(f'{message}{hint} (B=batal): ').strip()
        except (EOFError, KeyboardInterrupt): raise Cancel()
        if value.upper() == 'B': raise Cancel()
        if value == '~': value = ''
        elif not value and default is not None: value = str(default)
        if required and not value:
            print('[WARNING] Kolom wajib diisi.'); continue
        return value

# ===========================================================================
# CONFIG_VALUE — Mengambil atribut konfigurasi koneksi tanpa mencetak password.
# ===========================================================================
def config_value(cfg, name, fallback=None):
    return cfg.get(name, fallback) if isinstance(cfg, dict) else getattr(cfg, name, fallback)

# ===========================================================================
# SERVER_MENU — Menampilkan HANYA koneksi Server 205 dan Localhost dari konfigurasi terpusat.
# ===========================================================================
def server_menu():
    title('[TAHAP 1/6] PILIH KONEKSI DATABASE')
    print('Database target : ' + DATABASE)
    print('Pilih koneksi yang diizinkan untuk GetESBRevamp.\n')
    configs = list(SERVERS.values()) if isinstance(SERVERS, dict) else list(SERVERS)
    def find(hosts):
        return next((cfg for cfg in configs if str(config_value(cfg,'host',config_value(cfg,'server',''))).lower() in hosts), None)
    options = [('Server 205', find({'172.18.135.205'})), ('Localhost', find({'localhost','127.0.0.1','::1'}))]
    options = [(name,cfg) for name,cfg in options if cfg is not None]
    if not options: raise RuntimeError('Server 205 / localhost tidak ditemukan di db_config.SERVERS.')
    for index,(name,cfg) in enumerate(options,1):
        print(f'  {index}. {name:<12} ({config_value(cfg,"host",config_value(cfg,"server"))}:{config_value(cfg,"port",1433)})')
    print('  0. BATAL / KELUAR')
    selected = choose('Pilih koneksi', set(str(i) for i in range(len(options)+1)))
    if selected == '0': raise Cancel()
    name,cfg = options[int(selected)-1]
    print(f'[INFO] Koneksi dipilih : {name}')
    print(f'[INFO] Target host     : {config_value(cfg,"host",config_value(cfg,"server"))}:{config_value(cfg,"port",1433)}')
    print(f'[INFO] Database target : {DATABASE}')
    print('[INFO] Menghubungkan langsung ke database target...')
    return cfg

# ===========================================================================
# ROWS — Menjalankan SELECT berparameter dan mengubah hasil menjadi list dictionary.
# ===========================================================================
def rows(cur, sql, *params):
    cur.execute(sql, *params)
    names = [d[0] for d in cur.description]
    return [dict(zip(names,r)) for r in cur.fetchall()]

# ===========================================================================
# CONNECT_VERIFIED — Koneksi langsung ke DataSourceDistributor lalu memvalidasi database dan kedua tabel.
# ===========================================================================
def connect_verified(cfg):
    conn = connect_sqlserver(cfg, DATABASE)
    try:
        cur = conn.cursor()
        try:
            info = rows(cur, 'SELECT @@SERVERNAME AS ServerName, DB_NAME() AS DatabaseName, SUSER_SNAME() AS LoginName')[0]
            print('SQL Server aktual :', info['ServerName'])
            print('Database aktual   :', info['DatabaseName'])
            print('Login SQL         :', info['LoginName'])
            if str(info['DatabaseName']).lower() != DATABASE.lower(): raise RuntimeError('Database aktual tidak sesuai.')
            for table in ('ParamFitur','ParamESBRevamp'):
                if rows(cur,"SELECT OBJECT_ID(?, 'U') AS oid",'dbo.'+table)[0]['oid'] is None:
                    raise RuntimeError('Tabel dbo.'+table+' tidak ditemukan atau tidak dapat diakses.')
            print('[INFO] Koneksi dan metadata kedua tabel berhasil diverifikasi.')
        finally: cur.close()
        return conn
    except Exception:
        conn.close(); raise

# ===========================================================================
# SHOW — Menampilkan hasil SELECT atau preview dalam tabel terminal yang mudah dibaca.
# ===========================================================================
def show(records, heading, fields=None):
    title(heading)
    if not records:
        print('Tidak ada record.'); return
    fields = fields or list(records[0])
    for i,record in enumerate(records,1):
        print(f'  --- RECORD {i} ---')
        for field in fields:
            value = '[DIRAHASIAKAN]' if field.lower() == 'dbpass' else record.get(field)
            text = 'NULL' if value is None else str(value).replace('\n',' ')
            if len(text) > 180: text = text[:177] + '...'
            print(f'  {field:<24}: {text}')
    print(f'  Total: {len(records)} record')

# ===========================================================================
# FIND_PF — Mencari record ParamFitur untuk dipilih pengguna, termasuk pencarian DBName.
# ===========================================================================
def find_pf(cur):
    title('[TAHAP 3/6] CARI PARAMFITUR BERDASARKAN DBNAME')
    while True:
        dbname = ask('DBName (boleh sebagian)',required=True)
        found = rows(cur, 'SELECT IDFitur,IPServer,DBName,DBUser,DBType FROM dbo.ParamFitur WHERE DBName LIKE ? ORDER BY DBName,IDFitur', '%'+dbname+'%')
        if not found:
            print('[INFO] ParamFitur tidak ditemukan. 1=Cari lagi, 0=Kembali')
            if choose('Pilih',{'0','1'})=='0': raise Cancel()
            continue
        show(found,'HASIL PENCARIAN PARAMFITUR')
        print('Masukkan nomor record dari daftar di atas, atau 0 untuk kembali.')
        selection = choose('Nomor record',set(str(i) for i in range(len(found)+1)))
        if selection=='0': raise Cancel()
        return found[int(selection)-1]

# ===========================================================================
# CREATE_PF_INPUT — Meminta detail ParamFitur baru; password tidak ditampilkan di terminal.
# ===========================================================================
def create_pf_input():
    title('[TAHAP 3/6] INPUT PARAMFITUR BARU')
    print('Semua identitas database diisi manual. Password tidak ditampilkan.')
    return dict(IPServer=ask('IPServer',required=True), DBName=ask('DBName',required=True),
                DBUser=ask('DBUser',required=True), DBPass=ask('DBPass',required=True,secret=True),
                DBType=ask('DBType',default='mssql',required=True))

# ===========================================================================
# PICK_PF — Memilih apakah memakai ParamFitur lama atau membuat baru saat INSERT.
# ===========================================================================
def pick_pf(cur):
    title('[TAHAP 3/6] TENTUKAN IDFITUR / PARAMFITUR')
    print('1. GUNAKAN ParamFitur yang sudah ada (cari DBName)')
    print('   -> Pilih record dan gunakan IDFitur lama.')
    print('2. BUAT ParamFitur baru')
    print('   -> INSERT ParamFitur, lalu gunakan IDFitur baru.')
    print('0. KEMBALI KE MENU UTAMA')
    option = choose('Pilih',{'0','1','2'})
    if option=='0': raise Cancel()
    if option=='1': return find_pf(cur),None
    return None,create_pf_input()

# ===========================================================================
# FIND_ACTIVITY — Mencari konfigurasi ParamESBRevamp yang akan diubah.
# ===========================================================================
def find_activity(cur):
    title('[TAHAP 3/6] CARI RECORD - PARAMESBREVAMP')
    print('1. LogActivityModul\n2. LogActivitySubModul\n3. LogActivityEntity\n4. IDFitur\n0. KEMBALI')
    field = choose('Pilih kolom pencarian',{'0','1','2','3','4'})
    if field=='0': raise Cancel()
    names = {'1':'LogActivityModul','2':'LogActivitySubModul','3':'LogActivityEntity','4':'IDFitur'}
    name = names[field]
    value = ask('Nilai '+name,required=True)
    if field=='4':
        try: value=int(value)
        except ValueError: raise ValueError('IDFitur harus angka.')
        sql=f'SELECT {",".join("["+f+"]" for f in FIELDS)} FROM {ACT} WHERE IDFitur=?'
    else:
        sql=f'SELECT {",".join("["+f+"]" for f in FIELDS)} FROM {ACT} WHERE [{name}] LIKE ?'
        value='%'+value+'%'
    found=rows(cur,sql,value)
    if not found: raise ValueError('Record ParamESBRevamp tidak ditemukan.')
    show(found,'HASIL PENCARIAN PARAMESBREVAMP')
    print('Masukkan nomor record; 0 untuk kembali.')
    selection=choose('Nomor record',set(str(i) for i in range(len(found)+1)))
    if selection=='0': raise Cancel()
    selected=found[int(selection)-1]
    count=rows(cur,f'SELECT COUNT(*) AS n FROM {ACT} WHERE LogActivityModul=? AND LogActivitySubModul=?',selected['LogActivityModul'],selected['LogActivitySubModul'])[0]['n']
    if count!=1: raise ValueError('Kunci Modul + SubModul tidak unik. UPDATE dibatalkan.')
    return selected

# ===========================================================================
# EDIT_ACTIVITY — Mengumpulkan konfigurasi activity, termasuk FieldSelect, SchStart, dan nilai default.
# ===========================================================================
def edit_activity(old=None):
    title('[TAHAP 4/6] ISI KONFIGURASI PARAMESBREVAMP')
    print('Enter = pertahankan nilai lama/default; ~ = kosongkan field opsional; B = batal.')
    old=old or {}
    new=dict(old)
    for name in FIELDS[1:]:
        default=old.get(name)
        if name=='FieldSelect' and default is None: default=DEFAULT_FIELDS
        if name=='LogActivityEntity' and default is None: default='GetESBRevamp'
        if name=='isActive' and default is None: default=1
        if name=='Note' and default is None: default=''
        if name=='LogActivitySubModul' and default is None: default=''
        if name=='FieldSelect':
            print('[INFO] FieldSelect menggunakan template bawaan bila input dikosongkan.')
            response=ask('FieldSelect (T=template, K=ketik manual)',default='T' if not old else 'L',required=True).upper()
            if response=='T': new[name]=DEFAULT_FIELDS
            elif response=='L' and old: new[name]=old[name]
            elif response=='K': new[name]=ask('FieldSelect',required=True)
            else: raise ValueError('Pilihan FieldSelect tidak valid.')
            continue
        required=name in ('WhereCondition','TableDestination','LogActivityModul','LogActivityEntity','SchStart')
        value=ask(name,default=default,required=required)
        if name=='isActive':
            if value not in ('0','1'): raise ValueError('isActive harus 0 atau 1.')
            value=int(value)
        new[name]=value
    return new

# ===========================================================================
# SQL_LIT — Mengubah nilai Python menjadi literal SQL untuk file deployment; bukan untuk query live.
# ===========================================================================
def sql_lit(value):
    if value is None: return 'NULL'
    if isinstance(value,(int,bool)): return str(int(value))
    return "N'"+str(value).replace("'","''")+"'"

# ===========================================================================
# BACKUP_SNAPSHOT — Snapshot data ASLI sebelum DML, committed terpisah dari DML.
# Snapshot tabel yang dipilih; kegagalan backup menghentikan seluruh operasi.
# ===========================================================================
def backup_snapshot(conn, tables):
    suffix=datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'_'+uuid.uuid4().hex[:8]
    names=[]
    cur=conn.cursor()
    try:
        conn.autocommit=False
        cur.execute('SET XACT_ABORT ON')
        for table in tables:
            if table not in ('ParamFitur','ParamESBRevamp'):
                raise ValueError('Tabel backup tidak diizinkan: '+str(table))
            name=f'{table}_Backup_{suffix}'
            cur.execute(f'SELECT * INTO dbo.[{name}] FROM dbo.[{table}]')
            # Verifikasi snapshot ada; SELECT INTO gagal akan menggagalkan operasi.
            check=rows(cur,"SELECT OBJECT_ID(?, 'U') AS oid",'dbo.'+name)
            if not check or check[0]['oid'] is None:
                raise RuntimeError('Verifikasi backup gagal: '+name)
            names.append('dbo.'+name)
        conn.commit()
        print('[SUCCESS] BACKUP data sebelum perubahan berhasil:')
        for name in names: print('  - '+name)
        return names
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()

# ===========================================================================
# DEPLOYMENT_BACKUP_SQL — Snapshot SQL deployment dibuat SEBELUM BEGIN TRANSACTION
# DML, sehingga ROLLBACK DML tidak menghapus backup data lama.
# ===========================================================================
def deployment_backup_sql(tables):
    lines=[
        'DECLARE @BackupSuffix VARCHAR(48) = CONVERT(CHAR(8),GETDATE(),112)',
        "    + '_' + REPLACE(CONVERT(CHAR(12),GETDATE(),114),':','')",
        "    + '_' + LEFT(REPLACE(CONVERT(VARCHAR(36),NEWID()),'-',''),8);",
        'DECLARE @BackupName SYSNAME, @BackupSql NVARCHAR(MAX);',
    ]
    for table in tables:
        lines.extend([
            f"SET @BackupName=N'{table}_Backup_'+@BackupSuffix;",
            "IF OBJECT_ID(N'dbo.'+@BackupName,'U') IS NOT NULL THROW 51001,'Nama backup sudah ada.',1;",
            f"SET @BackupSql=N'SELECT * INTO dbo.'+QUOTENAME(@BackupName)+N' FROM dbo.[{table}]';",
            'EXEC sys.sp_executesql @BackupSql;',
            "IF OBJECT_ID(N'dbo.'+@BackupName,'U') IS NULL THROW 51002,'Backup gagal.',1;",
            "PRINT N'BACKUP BERHASIL: dbo.'+@BackupName;",
        ])
    return '\n    '.join(lines)

# ===========================================================================
# DEPLOYMENT — SQL deployment untuk INSERT/UPDATE activity, backup + COMMIT/ROLLBACK.
# Tidak membuat ParamFitur baru jika operasi asal menggunakan ParamFitur lama.
# ===========================================================================
def deployment(action, row, pf, old=None, pf_new=False):
    ip=sql_lit(pf['IPServer']); db=sql_lit(pf['DBName'])
    puser=sql_lit(pf['DBUser']); ptype=sql_lit(pf['DBType'])
    fields=[f for f in FIELDS if f!='IDFitur']
    vals=', '.join('@IDFitur' if f=='IDFitur' else sql_lit(row[f]) for f in FIELDS)
    new_key=f'LogActivityModul={sql_lit(row["LogActivityModul"])} AND LogActivitySubModul={sql_lit(row["LogActivitySubModul"])}'
    if action=='INSERT':
        action_sql=f'''IF EXISTS (SELECT 1 FROM dbo.ParamESBRevamp WITH (UPDLOCK,HOLDLOCK) WHERE {new_key})
        THROW 51011, 'ParamESBRevamp sudah ada.', 1;
    INSERT INTO dbo.ParamESBRevamp ({', '.join('['+f+']' for f in FIELDS)}) VALUES ({vals});
    IF @@ROWCOUNT<>1 THROW 51012, 'INSERT gagal.', 1;'''
    else:
        old_key=f'LogActivityModul={sql_lit(old["LogActivityModul"])} AND LogActivitySubModul={sql_lit(old["LogActivitySubModul"])}'
        assignments=',\n        '.join('['+f+']='+sql_lit(row[f]) for f in fields)
        action_sql=f'''IF EXISTS (SELECT 1 FROM dbo.ParamESBRevamp WITH (UPDLOCK,HOLDLOCK)
        WHERE {new_key} AND NOT ({old_key}))
        THROW 51015, 'Kunci baru sudah digunakan.', 1;
    UPDATE dbo.ParamESBRevamp SET IDFitur=@IDFitur,\n        {assignments}
        WHERE {old_key};
    IF @@ROWCOUNT<>1 THROW 51013, 'UPDATE tidak tepat satu record.', 1;'''
    create_sql=f'''IF @N=0
    BEGIN
        INSERT INTO dbo.ParamFitur (IPServer,DBName,DBUser,DBPass,DBType)
        VALUES ({ip},{db},{puser},dbo.fnEncrypt(N'$(DBPASS)',{ip}+N'BR!'),{ptype});
        SELECT @N=COUNT(*),@IDFitur=MIN(IDFitur) FROM dbo.ParamFitur WHERE IPServer={ip} AND DBName={db};
        IF @N<>1 OR @IDFitur IS NULL THROW 51004,'Verifikasi ParamFitur gagal.',1;
    END;''' if pf_new else "IF @N<>1 THROW 51004,'ParamFitur lama tidak ditemukan.',1;"
    return f'''/* ============================================================================
 GETESBREVAMP / TarikESBRevamp - SOP DEPLOYMENT ({action})
 1. BACKUP data asli kedua tabel. 2. Resolve ParamFitur.
 3. {action} ParamESBRevamp. 4. Verifikasi. 5. COMMIT / ROLLBACK.
 BACKUP disimpan SEBELUM transaksi DML; ROLLBACK DML tidak menghapus backup.
 {'Jalankan SQLCMD mode dan berikan DBPASS secara aman.' if pf_new else 'Tidak membutuhkan variabel DBPASS; ParamFitur lama harus tersedia.'}
 Backup SELECT INTO tidak menyalin index, constraint, trigger, atau permission.
============================================================================ */
USE [DataSourceDistributor];
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;
DECLARE @IDFitur INT, @N INT;
BEGIN TRY
    {deployment_backup_sql(('ParamFitur','ParamESBRevamp'))}
    BEGIN TRANSACTION;
    SELECT @N=COUNT(*),@IDFitur=MIN(IDFitur) FROM dbo.ParamFitur WITH (UPDLOCK,HOLDLOCK)
        WHERE IPServer={ip} AND DBName={db};
    IF @N>1 THROW 51003,'Duplikat ParamFitur.',1;
    {create_sql}
    {action_sql}
    IF (SELECT COUNT(*) FROM dbo.ParamESBRevamp
        WHERE IDFitur=@IDFitur AND {new_key})<>1
        THROW 51014,'Verifikasi ParamESBRevamp gagal.',1;
    COMMIT TRANSACTION;
    PRINT N'Deployment {action} TarikESBRevamp berhasil.';
END TRY
BEGIN CATCH
    IF XACT_STATE()<>0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO
'''

# ===========================================================================
# DEPLOYMENT_PF_UPDATE — SQL deployment untuk UPDATE ParamFitur secara terpisah.
# Password tidak dimasukkan ke file; gunakan SQLCMD DBPASS jika diubah.
# ===========================================================================
def deployment_pf_update(selected, changes):
    ip=sql_lit(selected['IPServer']); db=sql_lit(selected['DBName'])
    assigns=[]
    for field,value in changes.items():
        if field=='DBPass':
            salt=sql_lit(changes.get('IPServer',selected['IPServer']))
            assigns.append(f"[DBPass]=dbo.fnEncrypt(N'$(DBPASS)',{salt}+N'BR!')")
        else:
            assigns.append(f'[{field}]={sql_lit(value)}')
    verifies=' AND '.join(f'[{f}]={sql_lit(v)}' for f,v in changes.items() if f!='DBPass')
    if not verifies: verifies='1=1'
    return f'''/* ============================================================================
 GETESBREVAMP - SOP DEPLOYMENT UPDATE PARAMFITUR
 Backup data asli ParamFitur sebelum UPDATE, terpisah dari transaksi DML.
 {'SQLCMD variable DBPASS WAJIB diisi secara aman.' if 'DBPass' in changes else 'Tidak membutuhkan variabel DBPASS.'}
 Backup SELECT INTO bukan backup database penuh.
============================================================================ */
USE [DataSourceDistributor];
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;
DECLARE @TargetID INT, @N INT;
BEGIN TRY
    {deployment_backup_sql(('ParamFitur',))}
    BEGIN TRANSACTION;
    SELECT @N=COUNT(*),@TargetID=MIN(IDFitur) FROM dbo.ParamFitur WITH (UPDLOCK,HOLDLOCK)
        WHERE IPServer={ip} AND DBName={db};
    IF @N<>1 THROW 51031,'ParamFitur target tidak unik atau tidak ditemukan.',1;
    UPDATE dbo.ParamFitur SET {', '.join(assigns)} WHERE IDFitur=@TargetID;
    IF @@ROWCOUNT<>1 THROW 51032,'UPDATE ParamFitur gagal.',1;
    IF (SELECT COUNT(*) FROM dbo.ParamFitur WHERE IDFitur=@TargetID AND {verifies})<>1
        THROW 51033,'Verifikasi UPDATE ParamFitur gagal.',1;
    COMMIT TRANSACTION;
    PRINT N'UPDATE ParamFitur berhasil.';
END TRY
BEGIN CATCH
    IF XACT_STATE()<>0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO
'''

# ===========================================================================
# WRITE_DEPLOYMENT — Simpan script SQL setelah COMMIT berhasil.
# ===========================================================================
def write_deployment(action, content, folder=OUTPUT):
    try:
        folder=Path(folder or OUTPUT)
        folder.mkdir(parents=True,exist_ok=True)
        target=folder/f'GetESBRevamp_{action}_{datetime.now():%Y%m%d_%H%M%S_%f}.sql'
        target.write_text(content,encoding='utf-8')
        print('[INFO] SQL deployment:',target)
    except OSError as exc:
        print('[WARNING] COMMIT berhasil, tetapi file deployment gagal dibuat:',exc)

# ===========================================================================
# UPDATE_PF — UPDATE khusus ParamFitur dengan backup sebelum DML, preview,
# validasi, COMMIT/ROLLBACK, dan generator SQL deployment.
# ===========================================================================
def update_pf(conn):
    cur=conn.cursor(); committed=False
    try:
        selected=find_pf(cur)
        title('[TAHAP 4/6] UPDATE PARAMFITUR')
        print('1. IPServer\n2. DBName\n3. DBUser\n4. DBType\n5. DBPass (dienkripsi)\n0. SELESAI PILIH KOLOM')
        changes={}
        names={'1':'IPServer','2':'DBName','3':'DBUser','4':'DBType','5':'DBPass'}
        while True:
            opt=choose('Pilih kolom',{'0','1','2','3','4','5'})
            if opt=='0': break
            name=names[opt]
            changes[name]=ask('Nilai baru '+name,required=True,secret=name=='DBPass')
        if not changes: return 'BACK'
        if 'IPServer' in changes and 'DBPass' not in changes:
            raise ValueError('Perubahan IPServer wajib sekaligus mengisi DBPass baru untuk re-enkripsi.')
        show([selected],'[TAHAP 5/6] PREVIEW DATA LAMA')
        show([{k:('[DIRAHASIAKAN]' if k=='DBPass' else v) for k,v in changes.items()}],'PREVIEW NILAI BARU')
        print('1. BACKUP + Jalankan UPDATE\n2. Ulangi\n0. Kembali')
        opt=choose('Pilih',{'0','1','2'})
        if opt!='1': return 'RETRY' if opt=='2' else 'BACK'
        backup_snapshot(conn,('ParamFitur',))
        conn.autocommit=False
        cur.execute('SET XACT_ABORT ON')
        pfid=selected['IDFitur']
        matched=rows(cur,'SELECT IDFitur,IPServer,DBName,DBUser,DBType FROM dbo.ParamFitur WITH (UPDLOCK,HOLDLOCK) WHERE IDFitur=?',pfid)
        if len(matched)!=1: raise RuntimeError('ParamFitur target tidak unik.')
        if any(str(matched[0][k])!=str(selected[k]) for k in ('IPServer','DBName','DBUser','DBType')):
            raise RuntimeError('ParamFitur berubah sejak preview. UPDATE dibatalkan.')
        assignments=[]; params=[]
        for name,value in changes.items():
            if name=='DBPass':
                assignments.append('[DBPass]=dbo.fnEncrypt(?, ?)')
                params.extend([value,changes.get('IPServer',matched[0]['IPServer'])+'BR!'])
            else:
                assignments.append('['+name+']=?'); params.append(value)
        cur.execute('UPDATE dbo.ParamFitur SET '+', '.join(assignments)+' WHERE IDFitur=?',*(params+[pfid]))
        if cur.rowcount!=1: raise RuntimeError('UPDATE ParamFitur gagal.')
        actual=rows(cur,'SELECT IDFitur,IPServer,DBName,DBUser,DBType FROM dbo.ParamFitur WHERE IDFitur=?',pfid)
        if len(actual)!=1 or any(str(actual[0][k])!=str(v) for k,v in changes.items() if k!='DBPass'):
            raise RuntimeError('Verifikasi ParamFitur gagal.')
        show(actual,'[TAHAP 6/6] HASIL UPDATE (BELUM COMMIT)')
        print('1. COMMIT\n2. ROLLBACK & ULANGI\n0. ROLLBACK & KEMBALI')
        opt=choose('Pilih',{'0','1','2'})
        if opt!='1': conn.rollback(); return 'RETRY' if opt=='2' else 'BACK'
        conn.commit(); committed=True
        print('[SUCCESS] COMMIT ParamFitur berhasil.')
        write_deployment('UPDATE_ParamFitur',deployment_pf_update(selected,changes))
        return 'DONE'
    except Cancel: return 'BACK'
    except Exception as exc:
        print('[ERROR]',exc)
        print('1. Ulangi\n0. Kembali')
        try: return 'RETRY' if choose('Pilih',{'0','1'})=='1' else 'BACK'
        except Cancel: return 'BACK'
    finally:
        if not committed:
            try: conn.rollback()
            except Exception: pass
        try: conn.autocommit=True
        except Exception: pass
        cur.close()

# ===========================================================================
# EXECUTE — INSERT/UPDATE ParamESBRevamp, backup data lama SEBELUM transaksi
# DML, lalu verifikasi dan COMMIT/ROLLBACK secara eksplisit.
# ===========================================================================
def execute(conn, action, folder):
    cur=conn.cursor(); committed=False
    try:
        old=find_activity(cur) if action=='UPDATE' else None
        if action=='INSERT':
            existing,newpf=pick_pf(cur)
        else:
            print('[INFO] UPDATE: gunakan ParamFitur terkait atau pilih ParamFitur lain berdasarkan DBName.')
            print('1. PERTAHANKAN IDFitur yang sudah ada\n2. PILIH ParamFitur lain (cari DBName)\n0. KEMBALI')
            opt=choose('Pilih',{'0','1','2'})
            if opt=='0': raise Cancel()
            if opt=='1':
                found=rows(cur,'SELECT IDFitur,IPServer,DBName,DBUser,DBType FROM dbo.ParamFitur WHERE IDFitur=?',old['IDFitur'])
                if len(found)!=1: raise ValueError('IDFitur lama tidak ditemukan.')
                existing=found[0]
            else: existing=find_pf(cur)
            newpf=None
        row=edit_activity(old)
        row['IDFitur']=existing['IDFitur'] if existing else '[ID BARU OTOMATIS]'
        title('[TAHAP 5/6] PREVIEW KONFIGURASI')
        if old: show([old],'KONFIGURASI SEBELUM UPDATE',FIELDS)
        show([row],'KONFIGURASI YANG AKAN DISIMPAN',FIELDS)
        if existing: show([existing],'PARAMFITUR TERPILIH')
        else: show([{k:('[DIRAHASIAKAN]' if k=='DBPass' else v) for k,v in newpf.items()}],'PARAMFITUR BARU')
        print('1. BACKUP + JALANKAN PERUBAHAN\n2. ULANGI INPUT\n0. KEMBALI')
        opt=choose('Pilih',{'0','1','2'})
        if opt!='1': return 'RETRY' if opt=='2' else 'BACK'
        backup_snapshot(conn,('ParamFitur','ParamESBRevamp'))
        conn.autocommit=False
        cur.execute('SET XACT_ABORT ON')
        if newpf:
            match=rows(cur,'SELECT IDFitur FROM dbo.ParamFitur WITH (UPDLOCK,HOLDLOCK) WHERE IPServer=? AND DBName=?',newpf['IPServer'],newpf['DBName'])
            if match: raise ValueError('ParamFitur sudah ada; gunakan menu cari DBName.')
            cur.execute('INSERT INTO dbo.ParamFitur (IPServer,DBName,DBUser,DBPass,DBType) OUTPUT INSERTED.IDFitur VALUES (?,?,?,dbo.fnEncrypt(?,?),?)',newpf['IPServer'],newpf['DBName'],newpf['DBUser'],newpf['DBPass'],newpf['IPServer']+'BR!',newpf['DBType'])
            new_id=cur.fetchone()
            if not new_id or new_id[0] is None: raise RuntimeError('Gagal mendapatkan IDFitur baru.')
            row['IDFitur']=int(new_id[0]); pf=newpf
        else:
            pfcheck=rows(cur,'SELECT IDFitur,IPServer,DBName,DBUser,DBType FROM dbo.ParamFitur WITH (UPDLOCK,HOLDLOCK) WHERE IDFitur=?',existing['IDFitur'])
            if len(pfcheck)!=1 or any(str(pfcheck[0][k])!=str(existing[k]) for k in ('IPServer','DBName','DBUser','DBType')):
                raise RuntimeError('ParamFitur terpilih berubah sejak preview.')
            row['IDFitur']=existing['IDFitur']; pf=existing
        matching=rows(cur,'SELECT IDFitur FROM dbo.ParamESBRevamp WITH (UPDLOCK,HOLDLOCK) WHERE LogActivityModul=? AND LogActivitySubModul=?',row['LogActivityModul'],row['LogActivitySubModul'])
        if action=='INSERT' and matching: raise ValueError('Modul + SubModul sudah digunakan.')
        if action=='UPDATE':
            oldmatch=rows(cur,'SELECT IDFitur FROM dbo.ParamESBRevamp WITH (UPDLOCK,HOLDLOCK) WHERE LogActivityModul=? AND LogActivitySubModul=?',old['LogActivityModul'],old['LogActivitySubModul'])
            if len(oldmatch)!=1: raise RuntimeError('Target UPDATE tidak unik.')
            if (row['LogActivityModul'],row['LogActivitySubModul']) != (old['LogActivityModul'],old['LogActivitySubModul']) and matching:
                raise ValueError('Kunci Modul + SubModul baru sudah digunakan.')
            current=rows(cur,'SELECT '+','.join('['+f+']' for f in FIELDS)+' FROM dbo.ParamESBRevamp WITH (UPDLOCK,HOLDLOCK) WHERE LogActivityModul=? AND LogActivitySubModul=?',old['LogActivityModul'],old['LogActivitySubModul'])
            if len(current)!=1 or any(str(current[0][f])!=str(old[f]) for f in FIELDS):
                raise RuntimeError('Data berubah sejak preview. UPDATE dibatalkan.')
        if action=='INSERT':
            cur.execute('INSERT INTO dbo.ParamESBRevamp ('+','.join('['+f+']' for f in FIELDS)+') VALUES ('+','.join('?' for _ in FIELDS)+')',*(row[f] for f in FIELDS))
        else:
            mutable=FIELDS[1:]
            cur.execute('UPDATE dbo.ParamESBRevamp SET IDFitur=?, '+', '.join('['+f+']=?' for f in mutable)+' WHERE LogActivityModul=? AND LogActivitySubModul=?',*( [row['IDFitur']]+[row[f] for f in mutable]+[old['LogActivityModul'],old['LogActivitySubModul']] ))
        if cur.rowcount!=1: raise RuntimeError(f'{action} tidak memengaruhi tepat satu record.')
        actual=rows(cur,'SELECT '+','.join('['+f+']' for f in FIELDS)+' FROM dbo.ParamESBRevamp WHERE LogActivityModul=? AND LogActivitySubModul=?',row['LogActivityModul'],row['LogActivitySubModul'])
        if len(actual)!=1 or any(str(actual[0][f])!=str(row[f]) for f in FIELDS):
            raise RuntimeError('Verifikasi aktual ParamESBRevamp gagal.')
        show(actual,'[TAHAP 6/6] HASIL AKTUAL (BELUM COMMIT)',FIELDS)
        print('1. COMMIT - simpan permanen\n2. ROLLBACK - ulangi\n0. ROLLBACK - kembali')
        opt=choose('Pilih',{'0','1','2'})
        if opt!='1': conn.rollback(); return 'RETRY' if opt=='2' else 'BACK'
        conn.commit(); committed=True
        print('[SUCCESS] COMMIT berhasil.')
        write_deployment(action,deployment(action,row,pf,old,newpf is not None),folder)
        return 'DONE'
    except Cancel: return 'BACK'
    except Exception as exc:
        print('[ERROR]',exc)
        print('[INFO] Perubahan yang belum COMMIT akan di-ROLLBACK.')
        print('1. ULANGI\n0. KEMBALI')
        try: return 'RETRY' if choose('Pilih',{'0','1'})=='1' else 'BACK'
        except Cancel: return 'BACK'
    finally:
        if not committed:
            try: conn.rollback()
            except Exception: pass
        try: conn.autocommit=True
        except Exception: pass
        cur.close()

# ===========================================================================
# RUN — Pengendali menu utama: pemilihan koneksi, INSERT/UPDATE, ulangi, kembali, dan keluar.
# ===========================================================================
def run():
    title('GETESBREVAMP - WIZARD INSERT / UPDATE')
    try: cfg=server_menu()
    except Cancel:
        print('[INFO] Wizard dibatalkan.'); return
    try: conn=connect_verified(cfg)
    except Exception as exc:
        print('[ERROR] Koneksi gagal:',exc)
        print('[INFO] Tidak ada perubahan database.'); return
    try:
        while True:
            title('MENU UTAMA - GETESBREVAMP')
            print('Database : DataSourceDistributor')
            print('Tabel    : dbo.ParamFitur + dbo.ParamESBRevamp')
            print('Activity : TarikESBRevamp')
            print('-'*72)
            print('1. INSERT KONFIGURASI BARU')
            print('   Buat ParamFitur baru ATAU cari yang sudah ada berdasarkan DBName,')
            print('   lalu INSERT ParamESBRevamp dengan IDFitur yang sama.')
            print('2. UPDATE KONFIGURASI')
            print('   Pilih UPDATE ParamFitur atau ParamESBRevamp.')
            print('0. KELUAR')
            try:
                op=choose('Pilih menu utama',{'0','1','2'})
                if op=='0': break
                if op=='2':
                    title('PILIH TABEL UNTUK UPDATE')
                    print('1. UPDATE ParamFitur (database/kredensial)')
                    print('2. UPDATE ParamESBRevamp (konfigurasi activity)')
                    print('0. KEMBALI')
                    target=choose('Pilih tabel',{'0','1','2'})
                    if target=='0': continue
                else: target=None
                action='INSERT' if op=='1' else 'UPDATE'
                while True:
                    title('[TAHAP 2/6] '+action+' KONFIGURASI')
                    print('Ketik B saat input untuk membatalkan operasi.')
                    result=update_pf(conn) if target=='1' else execute(conn,action,OUTPUT)
                    if result=='RETRY': continue
                    if result=='BACK': break
                    print('1. OPERASI LAGI\n0. KEMBALI KE MENU UTAMA')
                    if choose('Pilih',{'0','1'})=='0': break
            except Cancel:
                print('[INFO] Kembali ke menu utama.')
    finally: conn.close()
    print('[INFO] Keluar dari wizard.')

# Entry point untuk menjalankan activity secara langsung dari terminal.
if __name__=='__main__':
    try: run()
    except (KeyboardInterrupt,EOFError): print('\n[INFO] Wizard dihentikan.')
