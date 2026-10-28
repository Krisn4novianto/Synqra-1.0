"""Interactive ParamEngine.dbo.ParamFTP INSERT/UPDATE wizard.

Run from the project root: python activities/ParamEngine/python/GetFTPThirdParty-H1.py
"""
import sys
from pathlib import Path
from datetime import datetime
from getpass import getpass

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
from db_config import SERVERS
from db_connection import connect_sqlserver



def choose_activity_server(servers):
    """Pilih Server 102 atau Lokal dari konfigurasi terpusat db_config.SERVERS."""
    global SERVER_KEY

    def value(cfg, name, default=''):
        if isinstance(cfg, dict):
            return cfg.get(name, default)
        return getattr(cfg, name, default)

    choices = {}
    for key, cfg in servers.items():
        host = str(value(cfg, 'host')).strip().lower()
        name = str(value(cfg, 'name')).strip().lower()
        config_key = str(value(cfg, 'key')).strip().lower()
        if str(key) == '4' or host == '172.18.246.102':
            choices['1'] = (str(key), cfg, 'Server 102')
        if (str(key) == '3' or config_key in {'local', 'localhost', 'server_local'}
                or host in {'localhost', '127.0.0.1', '.', '(local)'}
                or 'local' in name):
            choices['2'] = (str(key), cfg, 'Lokal')

    print('\nPilih koneksi database untuk activity ini:')
    print('  1. Server 102 (172.18.246.102)')
    print('  2. Lokal (localhost)')
    while True:
        selected = input('Pilih koneksi [1/2]: ').strip()
        if selected in choices:
            SERVER_KEY, cfg, label = choices[selected]
            host = value(cfg, 'host', '?')
            print(f'Koneksi dipilih: {label} | {host}')
            return cfg
        if selected in {'1', '2'}:
            print('Profil yang dipilih tidak ditemukan di db_config.py. Periksa isi SERVERS.')
        else:
            print('Pilihan tidak valid. Masukkan 1 atau 2.')

SERVER_KEY = '4'  # konfigurasi khusus 172.18.246.102
TARGET_HOST = '172.18.246.102'  # only ParamEngine server
DATABASE = 'ParamEngine'
TABLE = 'dbo.ParamFTP'
ACTIVITY = 'GetFTPThirdParty-H1'
OUTPUT = Path(__file__).resolve().parent.parent / 'output' / 'GetFTPThirdParty-H1'
FIELDS = ['ProductId','Task','Activity','Action','FTPType','FTPAddress','FTPPort','FTPUser','FTPPass','FTPPassPhrase','FTPisPassive','FTPencryption','UseProxy','FTPPath','LocalPath','Filename','FilenameDownload','LogActivityFilenameDateAdd','isActive','Note','Script']
BINARY = {'FTPisPassive','UseProxy','LogActivityFilenameDateAdd','isActive'}
REQUIRED = {'ProductId','Task','Activity','Action','FTPType','FTPAddress','FTPPort','FTPUser','FTPPass','FTPPath','LocalPath','Filename'}
DEFAULTS = {'Activity':ACTIVITY,'Action':'GET','FTPType':'SFTP','FTPPort':'22','FTPisPassive':0,'UseProxy':0,'LogActivityFilenameDateAdd':0,'isActive':1}
FILTERS = ['ProductId','Task','Activity','FTPAddress','FTPUser','Filename','isActive']
DISPLAY = [x for x in FIELDS if x not in ('FTPPass','FTPPassPhrase')]+['InsertDate','LastModified']

def ask(message, default=None, secret=False):
    suffix = f' [{default}]' if default is not None and not secret else ''
    value = (getpass(message+': ') if secret else input(message+suffix+': ')).strip()
    return value if value else default

def ident(s):
    return '['+s.replace(']',']]')+']'

def literal(v):
    if v is None: return 'NULL'
    if isinstance(v,int): return str(v)
    return "N'"+str(v).replace("'","''")+"'"

def show(rows, cols, heading):
    """Tampilkan satu field per baris agar mudah dibaca di terminal."""
    print('\n' + '=' * 68)
    print(f' {heading}')
    print('=' * 68)
    if not rows:
        print(' Tidak ada data.')
        print(' Total record: 0')
        return

    label_width = max(len(str(col)) for col in cols)
    for index, record in enumerate(rows, 1):
        print(f'\n--- RECORD {index} / {len(rows)} ---')
        for column, value in zip(cols, record):
            if column in ('FTPPass', 'FTPPassPhrase'):
                display_value = '[DISEMBUNYIKAN]'
            elif value is None:
                display_value = 'NULL'
            else:
                display_value = str(value).replace('\r', '\\r').replace('\n', '\\n')
            print(f'  {column:<{label_width}} = {display_value}')
    print('\n' + '-' * 68)
    print(f' Total record: {len(rows)}')

def choose_filter():
    print('\nFilter UPDATE (bisa beberapa field):')
    for i, col in enumerate(FILTERS,1): print(f'{i}. {col}')
    while True:
        raw=input('Nomor filter (contoh 1,2,3): ').strip()
        try:
            indexes=[int(x.strip()) for x in raw.split(',')]
            if not indexes or len(set(indexes))!=len(indexes) or any(x<1 or x>len(FILTERS) for x in indexes): raise ValueError
            return {FILTERS[i-1]:ask(f'Nilai {FILTERS[i-1]}') for i in indexes}
        except ValueError: print('Pilihan tidak valid.')

def where_clause(filters):
    clauses=[]; params=[]
    for k,v in filters.items():
        if v is None: clauses.append(f'{ident(k)} IS NULL')
        else: clauses.append(f'{ident(k)} = ?'); params.append(v)
    return ' AND '.join(clauses), params

def fetch(conn, filters, lock=False):
    where,params=where_clause(filters)
    hint=' WITH (UPDLOCK, HOLDLOCK)' if lock else ''
    cur=conn.cursor()
    try:
        cur.execute(f'SELECT {", ".join(ident(c) for c in DISPLAY)} FROM {TABLE}{hint} WHERE {where}',*params)
        return [tuple(r) for r in cur.fetchall()]
    finally: cur.close()

def collect_insert():
    result={}
    for col in FIELDS:
        default=DEFAULTS.get(col)
        val=ask(col,default,secret=(col=='FTPPass'))
        if col in REQUIRED and (val is None or val==''): raise ValueError(f'{col} wajib diisi')
        if col in BINARY:
            if str(val) not in ('0','1'): raise ValueError(f'{col} harus 0 atau 1')
            val=int(val)
        result[col]=val
    if result['Activity']!=ACTIVITY: raise ValueError('Activity harus '+ACTIVITY)
    return result

def collect_update():
    print('\nPilih field untuk diubah (kolom identitas ProductId/Task/Activity tidak diubah).')
    available=[c for c in FIELDS if c not in ('ProductId','Task','Activity')]
    for i,c in enumerate(available,1): print(f'{i}. {c}')
    nums=[int(x.strip()) for x in input('Nomor field (pisahkan koma): ').split(',')]
    if not nums or len(nums)!=len(set(nums)) or any(i<1 or i>len(available) for i in nums): raise ValueError('Nomor field tidak valid')
    result={}
    for i in nums:
        col=available[i-1]
        val=ask('Nilai baru '+col,secret=col=='FTPPass')
        if col in REQUIRED and not val: raise ValueError(f'{col} wajib diisi')
        if col in BINARY:
            if val not in ('0','1'): raise ValueError(f'{col} harus 0 atau 1')
            val=int(val)
        result[col]=val
    return result

def sql_expr(col, value, params):
    if col=='FTPPass':
        params.extend([value])
        return "dbo.fnEncrypt(?, [FTPAddress] + 'BR!')"
    params.append(value)
    return '?'

def backup(conn):
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    name='ParamFTP_Backup_'+stamp
    cur=conn.cursor()
    try:
        cur.execute(f'SELECT * INTO dbo.{ident(name)} FROM {TABLE}')
        conn.commit()
    finally: cur.close()
    print('Backup: dbo.'+name)
    return name

def run_insert(conn, data):
    filters={k:data[k] for k in ('ProductId','Task','Activity')}
    if fetch(conn,filters,lock=True): raise ValueError('Identitas ProductId + Task + Activity sudah ada. Gunakan UPDATE.')
    params=[]; exprs=[]
    for col in FIELDS:
        if col=='FTPPass':
            params.extend([data[col],data['FTPAddress']]); exprs.append("dbo.fnEncrypt(?, ? + 'BR!')")
        else: exprs.append('?'); params.append(data[col])
    cur=conn.cursor()
    try:
        cur.execute(f'INSERT INTO {TABLE} ({", ".join(ident(c) for c in FIELDS)}, [InsertDate], [LastModified]) VALUES ({", ".join(exprs)}, GETDATE(), GETDATE())',*params)
        if cur.rowcount!=1: raise RuntimeError('INSERT tidak memengaruhi tepat satu baris')
    finally:cur.close()
    return filters

def run_update(conn, filters, changes):
    before=fetch(conn,filters,lock=True)
    if len(before)!=1: raise ValueError(f'UPDATE membutuhkan tepat satu record, ditemukan {len(before)}')
    where,where_params=where_clause(filters)
    params=[]; assignments=[]
    # If FTPAddress changes, use the new address to encrypt the new password.
    # A changed FTPAddress requires FTPPass to be re-entered for safe re-encryption.
    if 'FTPAddress' in changes and 'FTPPass' not in changes:
        raise ValueError('Mengubah FTPAddress wajib sekaligus mengisi ulang FTPPass.')
    for col,val in changes.items():
        if col=='FTPPass':
            address=changes.get('FTPAddress')
            if address is not None:
                assignments.append("[FTPPass] = dbo.fnEncrypt(?, ? + 'BR!')")
                params.extend([val,address])
            else:
                assignments.append("[FTPPass] = dbo.fnEncrypt(?, [FTPAddress] + 'BR!')")
                params.append(val)
        else:
            assignments.append(f'{ident(col)} = ?');params.append(val)
    assignments.append('[LastModified] = GETDATE()')
    # CTE identifies exactly the locked target row; the UPDATE is still transactional.
    query=f'''WITH TargetRows AS (
      SELECT * FROM {TABLE} WITH (UPDLOCK, HOLDLOCK) WHERE {where}
    )
    UPDATE TargetRows SET {', '.join(assignments)};'''
    cur=conn.cursor()
    try:
        cur.execute(query,*(params+where_params))
        if cur.rowcount not in (1,-1): raise RuntimeError('UPDATE tidak memengaruhi tepat satu baris')
    finally:cur.close()
    return before

def deployment(action, filters, changes, backup_name):
    """SOP SQL deployment with DECLARE, backup, CTE, verification and safe default."""
    binary = BINARY
    def declaration(prefix, key, value):
        dtype = 'INT' if key in binary else 'NVARCHAR(MAX)'
        return f"DECLARE @{prefix}_{key} {dtype} = {literal(value)};"

    declarations = [declaration('Filter', k, v) for k, v in filters.items()]
    declarations += [declaration('New', k, v) for k, v in changes.items()]
    # The password is a SQL literal in this file: secure the generated script.
    declarations_sql = '\n'.join(declarations)
    where = ' AND '.join(
        f"([{k}] IS NULL AND @Filter_{k} IS NULL OR [{k}] = @Filter_{k})"
        if v is None else f"[{k}] = @Filter_{k}"
        for k, v in filters.items()
    )
    if action == 'INSERT':
        cols = ',\n            '.join(ident(c) for c in FIELDS) + ',\n            [InsertDate], [LastModified]'
        exprs = []
        for col in FIELDS:
            if col == 'FTPPass':
                exprs.append("dbo.fnEncrypt(@New_FTPPass, @New_FTPAddress + N'BR!')")
            else:
                exprs.append('@New_' + col)
        values = ',\n            '.join(exprs) + ',\n            GETDATE(), GETDATE()'
        mutation = f"""    IF EXISTS (SELECT 1 FROM dbo.ParamFTP WITH (UPDLOCK, HOLDLOCK) WHERE {where})
        THROW 51001, 'INSERT dibatalkan: konfigurasi sudah ada.', 1;

    INSERT INTO dbo.ParamFTP (
            {cols}
    ) VALUES (
            {values}
    );
    IF @@ROWCOUNT <> 1
        THROW 51002, 'INSERT harus memengaruhi satu record.', 1;"""
    else:
        assignments = []
        for col in changes:
            if col == 'FTPPass':
                key_address = '@New_FTPAddress' if 'FTPAddress' in changes else '[FTPAddress]'
                assignments.append(f"[FTPPass] = dbo.fnEncrypt(@New_FTPPass, {key_address} + N'BR!')")
            else:
                assignments.append(f"{ident(col)} = @New_{col}")
        assignments.append('[LastModified] = GETDATE()')
        set_sql = ',\n        '.join(assignments)
        mutation = f"""    IF (SELECT COUNT(1) FROM dbo.ParamFTP WITH (UPDLOCK, HOLDLOCK) WHERE {where}) <> 1
        THROW 51003, 'UPDATE membutuhkan tepat satu record.', 1;

    ;WITH TargetRows AS (
        SELECT * FROM dbo.ParamFTP WITH (UPDLOCK, HOLDLOCK)
        WHERE {where}
    )
    UPDATE TargetRows
    SET {set_sql};
    IF @@ROWCOUNT <> 1
        THROW 51004, 'UPDATE harus memengaruhi satu record.', 1;"""

    visible = ',\n        '.join(ident(c) for c in DISPLAY)
    return f"""USE [ParamEngine];
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;
GO

/*==============================================================================
  GETFTPTHIRDPARTY-H1 - PARAMFTP CONFIGURATION DEPLOYMENT
  ACTION        : {action}
  GENERATED     : {datetime.now():%Y-%m-%d %H:%M:%S}
  SOURCE BACKUP : dbo.{backup_name}

  TUJUAN:
      Deployment konfigurasi GetFTPThirdParty-H1 pada dbo.ParamFTP.

  URUTAN DEPLOYMENT:
      1. DECLARE dan validasi parameter target.
      2. Backup tabel sebelum perubahan.
      3. {action} konfigurasi (UPDATE menggunakan CTE).
      4. Verifikasi SELECT di dalam transaksi.
      5. COMMIT jika disetujui, selain itu ROLLBACK.
      6. SELECT hasil akhir sesudah keputusan transaksi.

  PERINGATAN:
      File dapat berisi password plaintext dalam DECLARE sebelum dienkripsi.
      Batasi akses dan jangan commit ke repository.
      Default deployment: ROLLBACK. Ganti @ApproveCommit = 1 hanya
      setelah review SQL dan persetujuan deployment.
==============================================================================*/

/*==============================================================================
  TAHAP 1 - DECLARE DAN VALIDASI PARAMETER TARGET
==============================================================================*/
{declarations_sql}
DECLARE @ApproveCommit BIT = 0; -- 0 = ROLLBACK (default); 1 = COMMIT
DECLARE @BackupSuffix VARCHAR(32) =
    CONVERT(CHAR(8), GETDATE(), 112) + '_' +
    REPLACE(REPLACE(CONVERT(VARCHAR(12), GETDATE(), 114), ':', ''), '.', '');
DECLARE @BackupTable SYSNAME = N'ParamFTP_Backup_' + @BackupSuffix;
DECLARE @BackupSQL NVARCHAR(MAX);
DECLARE @WasCommitted BIT = 0;

IF DB_NAME() <> N'ParamEngine'
    THROW 51010, 'Database target bukan ParamEngine.', 1;
IF @Filter_Activity <> N'GetFTPThirdParty-H1'
    THROW 51011, 'Activity target tidak sesuai.', 1;
IF @ApproveCommit NOT IN (0,1) OR @ApproveCommit IS NULL
    THROW 51012, 'ApproveCommit hanya boleh 0 atau 1.', 1;

/*==============================================================================
  TAHAP 2 - BACKUP TABEL SEBELUM MELAKUKAN PERUBAHAN
==============================================================================*/
IF OBJECT_ID(N'dbo.' + @BackupTable, N'U') IS NOT NULL
    THROW 51013, 'Nama tabel backup sudah tersedia.', 1;
SET @BackupSQL = N'SELECT * INTO dbo.' + QUOTENAME(@BackupTable) +
                 N' FROM dbo.ParamFTP;';
EXEC sys.sp_executesql @BackupSQL;
PRINT N'Backup berhasil: dbo.' + @BackupTable;

BEGIN TRY
    BEGIN TRANSACTION;

/*==============================================================================
  TAHAP 3 - {action} PARAMETER KE TABEL
==============================================================================*/
{mutation}

/*==============================================================================
  TAHAP 4 - VERIFIKASI HASIL {action} SEBELUM COMMIT
==============================================================================*/
    IF (SELECT COUNT(1) FROM dbo.ParamFTP WHERE {where}) <> 1
        THROW 51014, 'Verifikasi gagal: jumlah record bukan satu.', 1;
    PRINT N'HASIL SEMENTARA DALAM TRANSAKSI (BELUM COMMIT)';
    SELECT N'BELUM COMMIT' AS [StatusTransaksi],
        {visible}
    FROM dbo.ParamFTP WHERE {where};

/*==============================================================================
  TAHAP 5 - COMMIT ATAU ROLLBACK TRANSAKSI
==============================================================================*/
    IF @ApproveCommit = 1
    BEGIN
        COMMIT TRANSACTION;
        SET @WasCommitted = 1;
        PRINT N'COMMIT berhasil: konfigurasi disimpan.';
    END
    ELSE
    BEGIN
        ROLLBACK TRANSACTION;
        PRINT N'ROLLBACK: konfigurasi tidak disimpan.';
    END;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;

/*==============================================================================
  TAHAP 6 - TAMPILKAN HASIL AKHIR KONFIGURASI
==============================================================================*/
SELECT CASE WHEN @WasCommitted = 1 THEN N'COMMITTED' ELSE N'ROLLED BACK' END
       AS [StatusDeployment],
       {visible}
FROM dbo.ParamFTP
WHERE {where};
PRINT N'Catatan: backup tetap tersedia meskipun transaksi di-ROLLBACK.';
GO
"""

def choose_database_server():
    """Gunakan profil server 102; jangan pinjam kredensial server 205."""
    cfg = choose_activity_server(SERVERS)
    print(f'\n=== SERVER PARAMENGINE: {cfg.host}:{cfg.port} ===')
    print(f'Login: {cfg.username} | Profil: {SERVER_KEY}')
    try:
        probe = connect_sqlserver(cfg, 'master')
        try:
            cur = probe.cursor()
            try:
                cur.execute("SELECT DB_ID(N'ParamEngine'), HAS_DBACCESS(N'ParamEngine')")
                db_id, access = cur.fetchone()
            finally:
                cur.close()
        finally:
            probe.close()
        if db_id is None or access != 1:
            raise RuntimeError(f'Database ParamEngine tidak tersedia/dapat diakses (DB_ID={db_id}, akses={access}).')
        probe = connect_sqlserver(cfg, DATABASE)
        try:
            cur = probe.cursor()
            try:
                cur.execute("SELECT OBJECT_ID(N'dbo.ParamFTP', N'U')")
                if cur.fetchone()[0] is None:
                    raise RuntimeError('Tabel dbo.ParamFTP tidak ditemukan.')
            finally:
                cur.close()
        finally:
            probe.close()
    except Exception as exc:
        raise RuntimeError(f'Koneksi {TARGET_HOST} gagal: {exc}. Periksa kredensial profil yang dipilih di db_config.py dan izin login.') from exc
    print('Koneksi database dan tabel ParamFTP: OK')
    return cfg

def main():
    cfg=choose_database_server()
    if cfg is None: return
    print(f'\nGETFTPTHIRDPARTY-H1 | {DATABASE}.{TABLE}')
    print('1. INSERT\n2. UPDATE\n0. Keluar')
    choice=input('Pilih proses: ').strip()
    if choice=='0':return
    if choice not in ('1','2'):raise ValueError('Pilihan tidak valid')
    action='INSERT' if choice=='1' else 'UPDATE'
    conn=connect_sqlserver(cfg,DATABASE)
    conn.autocommit=False
    try:
        if action=='INSERT':
            changes=collect_insert()
            filters={k:changes[k] for k in ('ProductId','Task','Activity')}
            existing=fetch(conn,filters)
            if existing: raise ValueError('Record sudah ada. Pilih UPDATE.')
        else:
            filters=choose_filter()
            if 'Activity' not in filters: filters['Activity']=ACTIVITY
            existing=fetch(conn,filters)
            show(existing,DISPLAY,'SELECT DATA SEBELUM UPDATE')
            if len(existing)!=1:raise ValueError('Filter harus menghasilkan tepat satu record. Persempit filter.')
            if ask('Lanjut pilih field UPDATE? (y/n)','n').lower()!='y':return
            changes=collect_update()
        print('\nPerubahan:',{k:('[REDACTED]' if k=='FTPPass' else v) for k,v in changes.items()})
        if ask('Buat backup dan mulai transaksi? (y/n)','n').lower()!='y':return
        # Release any locks from preview SELECT before backing up.
        conn.rollback()
        # Separate committed backup connection to persist even if the data transaction rolls back.
        backup_conn=connect_sqlserver(cfg,DATABASE)
        try:
            backup_conn.autocommit=False
            backup_name=backup(backup_conn)
        finally:backup_conn.close()
        if action=='INSERT':run_insert(conn,changes)
        else:run_update(conn,filters,changes)
        after_filters = filters if action == 'INSERT' else {
            'ProductId': existing[0][DISPLAY.index('ProductId')],
            'Task': existing[0][DISPLAY.index('Task')],
            'Activity': existing[0][DISPLAY.index('Activity')],
        }
        after=fetch(conn,after_filters)
        if len(after)!=1:raise RuntimeError('Verifikasi gagal: jumlah record bukan satu')
        show(after,DISPLAY,'HASIL AKTUAL DALAM TRANSAKSI (BELUM COMMIT)')
        if ask('Ketik COMMIT untuk simpan, lainnya ROLLBACK','ROLLBACK')!='COMMIT':
            conn.rollback();print('ROLLBACK berhasil; perubahan tidak disimpan.');return
        conn.commit();print('COMMIT berhasil.')
    except BaseException:
        conn.rollback()
        raise
    finally:conn.close()
    sql=deployment(action,after_filters,changes,backup_name)
    OUTPUT.mkdir(parents=True,exist_ok=True)
    destination=OUTPUT/f'GetFTPThirdParty-H1_{datetime.now():%Y-%m-%d}.sql'
    if destination.exists():
        destination=OUTPUT/f'GetFTPThirdParty-H1_{datetime.now():%Y-%m-%d_%H%M%S}.sql'
    destination.write_text(sql,encoding='utf-8')
    try: destination.chmod(0o600)
    except OSError:pass
    print('Deployment SQL:',destination)
    print('PERINGATAN: SQL memuat credential; batasi akses file.')

if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:print('\nDibatalkan.')
    except Exception as exc:print(f'ERROR {type(exc).__name__}: {exc}');raise
