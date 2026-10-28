#!/usr/bin/env python3
"""
===============================================================================
GETFTPREPORT - PARAMFTP CONFIGURATION WIZARD
===============================================================================

PANDUAN SINGKAT:
 1. Pilih koneksi Server 205 atau Localhost dari db_config.py.
 2. Pilih INSERT atau UPDATE dari menu utama.
 3. INSERT: cari ParamFitur berdasarkan DBName atau buat ParamFitur baru.
 4. IDFitur yang terpilih/dibuat dipakai untuk dbo.ParamFTP.
 5. UPDATE: pilih tabel ParamFitur atau ParamFTP, lalu cari record.
 6. Periksa preview dan hasil SELECT aktual sebelum COMMIT/ROLLBACK.
 7. Setelah COMMIT ParamFTP, program membuat SQL deployment dengan backup.

CATATAN KEAMANAN:
 - DBPass dan FTPPass dienkripsi SQL Server menggunakan dbo.fnEncrypt.
 - Password tidak ditampilkan di preview atau hasil SELECT.
 - SQL deployment memakai variabel SQLCMD DBPASS/FTPPASS, bukan password asli.
 - SQLCMD mode perlu diaktifkan saat menjalankan file deployment.
 - Backup SELECT INTO tidak menyalin index, constraint, trigger, permission.
 - Uji terlebih dahulu di lingkungan development.
===============================================================================
"""
from __future__ import annotations
import sys
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

# BAGIAN 1 — KONFIGURASI
DATABASE = 'DataSourceDistributor'
PF = 'dbo.ParamFitur'
FTP = 'dbo.ParamFTP'
TARGET_SERVER = 'rekonenterprise-dbs-grp-08.dbs.prd.bri.co.id'
ACTIVITY = 'GetFTPReport'
SUFFIX = 'BR!'
OUTPUT = HERE.parent / 'output' / '01_Reconciliation' / 'GetFTPReport'
COLUMNS = ('IDFitur','Action','FTPType','FTPAddress','FTPPort','FTPUser','FTPPass',
           'FTPPassPhrase','FTPisPassive','FTPencryption','UseProxy','FTPPath',
           'LocalPath','Filename','FilenameDownload','LogActivityModul',
           'LogActivitySubModul','LogActivityEntity','LogActivityFilenameDateAdd',
           'isActive','Note','Script','SchStart','SchEnd')
SECRET = {'DBPass','FTPPass','FTPPassPhrase'}
BOOL_FIELDS = {'FTPisPassive','UseProxy','LogActivityFilenameDateAdd','isActive'}
REQUIRED = {'Action','FTPType','FTPAddress','FTPPort','FTPUser','FTPPath',
            'LocalPath','Filename','LogActivityModul'}
DEFAULTS = {'FTPisPassive':1,'UseProxy':0,'LogActivityFilenameDateAdd':1,
            'isActive':1,'LogActivityEntity':ACTIVITY}
VISIBLE = tuple(c for c in COLUMNS if c not in SECRET)

# BAGIAN 2 — INPUT, OUTPUT TERMINAL, DAN PEMILIHAN SERVER
class Cancel(Exception):
    pass

def title(message):
    print('\n'+'='*72+'\n'+message+'\n'+'='*72)

def choose(label, valid):
    while True:
        result = input(label+' (B=batal): ').strip().upper()
        if result == 'B': raise Cancel()
        if result in valid: return result
        print('[WARNING] Pilihan tidak valid: '+', '.join(sorted(valid)))

def ask(label, default=None, required=False, secret=False):
    while True:
        hint = f' [{default}]' if default is not None and not secret and len(str(default)) < 70 else ''
        value = (getpass if secret else input)(f'{label}{hint} (B=batal): ').strip()
        if not secret and value.upper() == 'B': raise Cancel()
        if value == '~' and not secret: value = ''
        elif not value and default is not None: value = str(default)
        if required and not value:
            print('[WARNING] Wajib diisi.'); continue
        return value

def cfg_value(cfg, name, fallback=None):
    return cfg.get(name, fallback) if isinstance(cfg, dict) else getattr(cfg, name, fallback)

def choose_server():
    title('[TAHAP 1/6] PILIH KONEKSI DATABASE')
    print('Database target : '+DATABASE)
    configs = list(SERVERS.values())
    def locate(hosts):
        return next((c for c in configs if str(cfg_value(c,'host','')).lower() in hosts),None)
    options = [('Server 205',locate({'172.18.135.205'})),
               ('Localhost',locate({'localhost','127.0.0.1','::1'}))]
    options = [(n,c) for n,c in options if c is not None]
    if not options: raise RuntimeError('Server 205/Localhost tidak ada di db_config.py.')
    for i,(n,c) in enumerate(options,1):
        print(f'  {i}. {n:<12} ({cfg_value(c,"host")}:{cfg_value(c,"port",1433)})')
    print('  0. BATAL / KELUAR')
    option=choose('Pilih koneksi',set(str(i) for i in range(len(options)+1)))
    if option=='0': raise Cancel()
    name,cfg=options[int(option)-1]
    print(f'[INFO] Koneksi dipilih : {name}')
    print(f'[INFO] Target host     : {cfg_value(cfg,"host")}:{cfg_value(cfg,"port",1433)}')
    print(f'[INFO] Database target : {DATABASE}')
    return cfg

def fetch(cur, sql, *params):
    cur.execute(sql,*params)
    cols=[c[0] for c in cur.description]
    return [dict(zip(cols,r)) for r in cur.fetchall()]

def connect_verified(cfg):
    print('[INFO] Menghubungkan langsung ke database '+DATABASE+'...')
    conn=connect_sqlserver(cfg,DATABASE)
    try:
        cur=conn.cursor()
        try:
            db=fetch(cur,'SELECT DB_NAME() AS db')[0]['db']
            if str(db).lower()!=DATABASE.lower(): raise RuntimeError('Database koneksi tidak sesuai.')
            for table in ('ParamFitur','ParamFTP'):
                if fetch(cur,"SELECT OBJECT_ID(?, 'U') AS oid",'dbo.'+table)[0]['oid'] is None:
                    raise RuntimeError('Tabel dbo.'+table+' tidak ditemukan atau tidak bisa diakses.')
            print('[SUCCESS] Koneksi dan kedua tabel berhasil diverifikasi.')
        finally: cur.close()
        return conn
    except Exception:
        conn.close(); raise

def show(records, heading):
    title(heading)
    if not records:
        print('Tidak ada record.'); return
    for index,record in enumerate(records,1):
        print(f'--- RECORD {index} ---')
        for k,v in record.items():
            value='[DIRAHASIAKAN]' if k in SECRET else ('NULL' if v is None else str(v))
            if len(value)>160: value=value[:157]+'...'
            print(f'  {k:<28}: {value}')
    print(f'Total: {len(records)} record')

# BAGIAN 3 — PENCARIAN PARAMFITUR DAN PARAMFTP
def find_pf(cur):
    title('[TAHAP 3/6] CARI PARAMFITUR BERDASARKAN DBNAME')
    search=ask('DBName (boleh sebagian)',required=True)
    result=fetch(cur,'SELECT IDFitur,IPServer,DBName,DBUser,DBType FROM dbo.ParamFitur WHERE DBName LIKE ? ORDER BY DBName,IDFitur','%'+search+'%')
    if not result: raise ValueError('ParamFitur tidak ditemukan.')
    show(result,'HASIL PENCARIAN PARAMFITUR')
    opt=choose('Nomor record (0=kembali)',set(str(i) for i in range(len(result)+1)))
    if opt=='0': raise Cancel()
    return result[int(opt)-1]

def new_pf():
    title('[TAHAP 3/6] INPUT PARAMFITUR BARU')
    print('IPServer target FTP default: '+TARGET_SERVER)
    return {'IPServer':ask('IPServer',TARGET_SERVER,required=True),
            'DBName':ask('DBName',required=True),
            'DBUser':ask('DBUser',required=True),
            'DBPass':ask('DBPass',required=True,secret=True),
            'DBType':ask('DBType','mssql',required=True)}

def pick_pf(cur):
    title('[TAHAP 3/6] TENTUKAN IDFITUR')
    print('1. GUNAKAN ParamFitur yang sudah ada (cari DBName)')
    print('2. BUAT ParamFitur baru')
    print('0. KEMBALI')
    opt=choose('Pilih',{'0','1','2'})
    if opt=='0': raise Cancel()
    return (find_pf(cur),None) if opt=='1' else (None,new_pf())

def find_ftp(cur):
    title('[TAHAP 3/6] CARI PARAMFTP UNTUK UPDATE')
    print('1. LogActivityModul\n2. FTPAddress\n3. Filename\n4. DBName (via ParamFitur)\n0. KEMBALI')
    opt=choose('Pilih pencarian',{'0','1','2','3','4'})
    if opt=='0': raise Cancel()
    term=ask('Kata kunci',required=True)
    column={'1':'p.LogActivityModul','2':'p.FTPAddress','3':'p.Filename','4':'f.DBName'}[opt]
    cols=', '.join('p.['+c+']' for c in VISIBLE)
    result=fetch(cur,f'''SELECT {cols}, f.DBName AS LinkedDBName, f.IPServer AS LinkedIPServer
        FROM dbo.ParamFTP p LEFT JOIN dbo.ParamFitur f ON f.IDFitur=p.IDFitur
        WHERE {column} LIKE ? ORDER BY p.LogActivityModul,p.Filename''','%'+term+'%')
    if not result: raise ValueError('ParamFTP tidak ditemukan.')
    show(result,'HASIL PENCARIAN PARAMFTP')
    opt=choose('Nomor record (0=kembali)',set(str(i) for i in range(len(result)+1)))
    if opt=='0': raise Cancel()
    selected=result[int(opt)-1]
    # ParamFTP tidak diasumsikan memiliki primary key tertentu; gunakan pasangan
    # LogActivityModul + LogActivitySubModul hanya jika benar-benar unik.
    where,params=ftp_key(selected)
    count=fetch(cur,f'SELECT COUNT(*) AS n FROM dbo.ParamFTP WHERE {where}',*params)[0]['n']
    if count!=1: raise RuntimeError('Kunci Modul/SubModul tidak unik; UPDATE dibatalkan.')
    return selected

def ftp_key(p):
    if p.get('LogActivitySubModul') in (None,''):
        return "LogActivityModul=? AND (LogActivitySubModul IS NULL OR LogActivitySubModul='')",(p['LogActivityModul'],)
    return 'LogActivityModul=? AND LogActivitySubModul=?',(p['LogActivityModul'],p['LogActivitySubModul'])

# BAGIAN 4 — INPUT DAN EDIT FIELD PARAMFTP
def input_ftp(old=None):
    title('[TAHAP 4/6] ISI KONFIGURASI PARAMFTP')
    print('Enter=nilai lama/default; ~=kosongkan field opsional; B=batal.')
    old=old or {}
    data={}
    for name in COLUMNS[1:]:
        if name=='LogActivityEntity':
            data[name]=ACTIVITY
            continue
        if name=='FTPPass':
            # Untuk UPDATE, Enter berarti password lama dipertahankan.
            if old:
                print('[INFO] FTPPass: Enter untuk mempertahankan password lama.')
                value=ask('FTPPass baru (Enter=tidak diubah)',secret=True)
                data[name]=value if value else None
            else: data[name]=ask('FTPPass',required=True,secret=True)
            continue
        if name=='FTPPassPhrase':
            data[name]=ask(name,old.get(name) or '',secret=True)
            continue
        default=old.get(name)
        if default is None: default=DEFAULTS.get(name)
        value=ask(name,default,required=name in REQUIRED)
        if name in BOOL_FIELDS:
            if value not in ('0','1'): raise ValueError(name+' harus 0 atau 1.')
            value=int(value)
        data[name]=value or None
    return data

def sql_lit(value):
    if value is None: return 'NULL'
    if isinstance(value,int): return str(value)
    return "N'"+str(value).replace("'","''")+"'"

# BAGIAN 5 — SQL DEPLOYMENT: BACKUP, SQLCMD PASSWORD, TRANSAKSI
def deployment(action,p,pf,old=None,pf_created=False,ftp_password_changed=True):
    ip,dbname=sql_lit(pf['IPServer']),sql_lit(pf['DBName'])
    fields=[c for c in COLUMNS if c!='IDFitur']
    expressions=[]
    for col in fields:
        if col=='FTPPass':
            expressions.append("dbo.fnEncrypt(N'$(FTPPASS)',"+sql_lit(p['FTPAddress'])+"+N'BR!')")
        elif col=='FTPPassPhrase' and old and not p.get(col):
            expressions.append(None)
        else: expressions.append(sql_lit(p.get(col)))
    if action=='INSERT':
        assignments=', '.join('['+c+']' for c in COLUMNS)
        vals=', '.join(['@IDFitur']+expressions)
        where='LogActivityModul='+sql_lit(p['LogActivityModul'])+' AND '+('LogActivitySubModul='+sql_lit(p['LogActivitySubModul']) if p['LogActivitySubModul'] else "(LogActivitySubModul IS NULL OR LogActivitySubModul=N'')")
        activity_sql=f'''IF EXISTS(SELECT 1 FROM dbo.ParamFTP WITH(UPDLOCK,HOLDLOCK) WHERE {where}) THROW 52010,'ParamFTP sudah ada.',1;
INSERT INTO dbo.ParamFTP ({assignments}) VALUES ({vals});
IF @@ROWCOUNT<>1 THROW 52011,'INSERT ParamFTP gagal.',1;'''
    else:
        parts=['[IDFitur]=@IDFitur']
        for col,expr in zip(fields,expressions):
            if col in ('LogActivityModul','LogActivitySubModul'): continue
            if col=='FTPPass' and not ftp_password_changed: continue
            if col=='FTPPassPhrase' and expr is None: continue
            parts.append('['+col+']='+expr)
        oldwhere='LogActivityModul='+sql_lit(old['LogActivityModul'])+' AND '+('LogActivitySubModul='+sql_lit(old['LogActivitySubModul']) if old['LogActivitySubModul'] else "(LogActivitySubModul IS NULL OR LogActivitySubModul=N'')")
        activity_sql=f"UPDATE dbo.ParamFTP SET {', '.join(parts)} WHERE {oldwhere};\nIF @@ROWCOUNT<>1 THROW 52012,'UPDATE ParamFTP gagal.',1;"
    newwhere='LogActivityModul='+sql_lit(p['LogActivityModul'])+' AND '+('LogActivitySubModul='+sql_lit(p['LogActivitySubModul']) if p['LogActivitySubModul'] else "(LogActivitySubModul IS NULL OR LogActivitySubModul=N'')")
    return f'''/* ============================================================================
 GETFTPREPORT - SOP DEPLOYMENT ({action})
 1. Backup tabel. 2. Resolve IDFitur. 3. {action} ParamFTP.
 4. Verifikasi SELECT. 5. COMMIT / ROLLBACK.
 SQLCMD mode: set DBPASS untuk ParamFitur baru, FTPPASS untuk password FTP baru.
 Backup SELECT INTO tidak menyalin indeks, constraint, trigger, permission.
============================================================================ */
USE [DataSourceDistributor];
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;
DECLARE @IDFitur INT, @N INT, @Backup SYSNAME, @SQL NVARCHAR(MAX);
DECLARE @Suffix VARCHAR(40)=CONVERT(CHAR(8),GETDATE(),112)+'_'+REPLACE(REPLACE(CONVERT(VARCHAR(12),GETDATE(),114),':',''),'.','');
BEGIN TRY
    -- Backup di luar transaksi; snapshot tetap ada bila perubahan ROLLBACK.
    SET @Backup=N'ParamFitur_Backup_'+@Suffix;
    IF OBJECT_ID(N'dbo.'+@Backup,'U') IS NOT NULL THROW 52001,'Backup ParamFitur sudah ada.',1;
    SET @SQL=N'SELECT * INTO dbo.'+QUOTENAME(@Backup)+N' FROM dbo.ParamFitur'; EXEC sys.sp_executesql @SQL;
    SET @Backup=N'ParamFTP_Backup_'+@Suffix;
    IF OBJECT_ID(N'dbo.'+@Backup,'U') IS NOT NULL THROW 52002,'Backup ParamFTP sudah ada.',1;
    SET @SQL=N'SELECT * INTO dbo.'+QUOTENAME(@Backup)+N' FROM dbo.ParamFTP'; EXEC sys.sp_executesql @SQL;
    BEGIN TRANSACTION;
    SELECT @N=COUNT(*),@IDFitur=MIN(IDFitur) FROM dbo.ParamFitur WITH(UPDLOCK,HOLDLOCK)
     WHERE IPServer={ip} AND DBName={dbname};
    IF @N>1 THROW 52003,'Duplikat ParamFitur.',1;
    IF @N=0
    BEGIN
        INSERT INTO dbo.ParamFitur(IPServer,DBName,DBUser,DBPass,DBType)
        VALUES({ip},{dbname},{sql_lit(pf['DBUser'])},dbo.fnEncrypt(N'$(DBPASS)',{ip}+N'BR!'),{sql_lit(pf['DBType'])});
        SELECT @N=COUNT(*),@IDFitur=MIN(IDFitur) FROM dbo.ParamFitur
         WHERE IPServer={ip} AND DBName={dbname};
        IF @N<>1 OR @IDFitur IS NULL THROW 52004,'Resolve ParamFitur gagal.',1;
    END;
    {activity_sql}
    IF (SELECT COUNT(*) FROM dbo.ParamFTP WHERE {newwhere} AND IDFitur=@IDFitur)<>1
        THROW 52013,'Verifikasi ParamFTP gagal.',1;
    SELECT IDFitur,Action,FTPType,FTPAddress,FTPPort,FTPUser,FTPPath,Filename,
           LogActivityModul,LogActivitySubModul,isActive FROM dbo.ParamFTP WHERE {newwhere};
    COMMIT TRANSACTION;
    PRINT N'GetFTPReport {action} berhasil.';
END TRY
BEGIN CATCH
    IF XACT_STATE()<>0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO
'''

def save_sql(action,p,pf,old=None,pf_created=False,ftp_password_changed=True):
    sql=deployment(action,p,pf,old,pf_created,ftp_password_changed)
    OUTPUT.mkdir(parents=True,exist_ok=True)
    base=OUTPUT/f'GetFTPReport_{datetime.now():%Y-%m-%d}.sql'
    path=base
    index=2
    while path.exists():
        path=OUTPUT/f'{base.stem}_{index}.sql'; index+=1
    path.write_text(sql,encoding='utf-8')
    try: path.chmod(0o600)
    except OSError: pass
    print('[SUCCESS] SQL deployment dibuat : '+str(path))
    print('[WARNING] SQLCMD DBPASS/FTPPASS diperlukan jika deployment membuat password baru.')

# BAGIAN 6 — TRANSAKSI LIVE DAN VERIFIKASI
def resolve_pf(cur,existing,new):
    if existing:
        result=fetch(cur,'SELECT IDFitur,IPServer,DBName,DBUser,DBType FROM dbo.ParamFitur WITH(UPDLOCK,HOLDLOCK) WHERE IDFitur=?',existing['IDFitur'])
        if len(result)!=1: raise RuntimeError('ParamFitur pilihan sudah tidak tersedia.')
        return result[0],False
    result=fetch(cur,'SELECT IDFitur,IPServer,DBName,DBUser,DBType FROM dbo.ParamFitur WITH(UPDLOCK,HOLDLOCK) WHERE IPServer=? AND DBName=?',new['IPServer'],new['DBName'])
    if result: raise RuntimeError('ParamFitur sudah ada. Gunakan pilihan ParamFitur lama.')
    cur.execute('''INSERT INTO dbo.ParamFitur(IPServer,DBName,DBUser,DBPass,DBType)
        OUTPUT INSERTED.IDFitur VALUES(?,?,?,dbo.fnEncrypt(?,?),?)''',
        new['IPServer'],new['DBName'],new['DBUser'],new['DBPass'],new['IPServer']+SUFFIX,new['DBType'])
    row=cur.fetchone()
    if not row: raise RuntimeError('Gagal mendapatkan IDFitur baru.')
    return dict(IDFitur=int(row[0]),IPServer=new['IPServer'],DBName=new['DBName'],DBUser=new['DBUser'],DBType=new['DBType']),True

def execute_ftp(conn,action,p,existing,new,old=None):
    cur=conn.cursor(); committed=False
    try:
        pf,pf_created=resolve_pf(cur,existing,new)
        idf=pf['IDFitur']
        where,key=ftp_key(old if old else p)
        count=fetch(cur,f'SELECT COUNT(*) AS n FROM dbo.ParamFTP WITH(UPDLOCK,HOLDLOCK) WHERE {where}',*key)[0]['n']
        if action=='INSERT' and count!=0: raise RuntimeError('ParamFTP sudah ada; gunakan UPDATE.')
        if action=='UPDATE' and count!=1: raise RuntimeError('UPDATE memerlukan tepat satu record.')
        if action=='UPDATE' and old and str(old['FTPAddress']) != str(p['FTPAddress']) and p['FTPPass'] is None:
            raise ValueError('FTPAddress berubah: wajib mengisi FTPPass baru untuk re-enkripsi.')
        if action=='INSERT':
            exprs=['?']*len(COLUMNS)
            exprs[COLUMNS.index('FTPPass')]='dbo.fnEncrypt(?,?)'
            params=[]
            for c in COLUMNS:
                if c=='IDFitur': params.append(idf)
                elif c=='FTPPass': params.extend([p['FTPPass'],p['FTPAddress']+SUFFIX])
                else: params.append(p.get(c))
            cur.execute('INSERT INTO dbo.ParamFTP ('+', '.join('['+c+']' for c in COLUMNS)+') VALUES ('+', '.join(exprs)+')',*params)
        else:
            updates=['[IDFitur]=?']; params=[idf]
            for c in COLUMNS[1:]:
                if c in ('LogActivityModul','LogActivitySubModul'): continue
                if c=='FTPPass':
                    if p[c] is not None:
                        updates.append('[FTPPass]=dbo.fnEncrypt(?,?)')
                        params.extend([p[c],p['FTPAddress']+SUFFIX])
                elif c=='FTPPassPhrase' and p[c] is None:
                    continue
                else:
                    updates.append('['+c+']=?'); params.append(p.get(c))
            cur.execute('UPDATE dbo.ParamFTP SET '+', '.join(updates)+' WHERE '+where,*(params+list(key)))
        if cur.rowcount!=1: raise RuntimeError('Perubahan ParamFTP tidak tepat satu record.')
        newwhere,newkey=ftp_key(p)
        visible=', '.join('['+c+']' for c in VISIBLE)
        actual=fetch(cur,'SELECT '+visible+' FROM dbo.ParamFTP WHERE '+newwhere,*newkey)
        if len(actual)!=1 or int(actual[0]['IDFitur'])!=idf:
            raise RuntimeError('Verifikasi SELECT aktual gagal.')
        show(actual,'[TAHAP 6/6] HASIL SELECT AKTUAL (BELUM COMMIT)')
        print('1. COMMIT\n2. ROLLBACK & ULANGI\n0. ROLLBACK & KEMBALI')
        opt=choose('Pilih',{'0','1','2'})
        if opt!='1': conn.rollback(); return 'RETRY' if opt=='2' else 'BACK'
        conn.commit(); committed=True
        print('[SUCCESS] COMMIT ParamFTP berhasil.')
        try: save_sql(action,p,pf,old,pf_created,p.get('FTPPass') is not None)
        except Exception as exc: print('[WARNING] COMMIT berhasil, tetapi SQL deployment gagal dibuat:',exc)
        return 'DONE'
    finally:
        if not committed:
            try: conn.rollback()
            except Exception: pass
        cur.close()

def update_pf(conn):
    cur=conn.cursor(); committed=False
    try:
        selected=find_pf(cur)
        title('[TAHAP 4/6] UPDATE PARAMFITUR')
        print('1. IPServer\n2. DBName\n3. DBUser\n4. DBType\n5. DBPass\n0. SELESAI')
        changes={}; names={'1':'IPServer','2':'DBName','3':'DBUser','4':'DBType','5':'DBPass'}
        while True:
            opt=choose('Pilih field',{'0','1','2','3','4','5'})
            if opt=='0': break
            name=names[opt]
            changes[name]=ask('Nilai baru '+name,required=True,secret=name=='DBPass')
        if not changes: return 'BACK'
        if 'IPServer' in changes and 'DBPass' not in changes:
            raise ValueError('Mengubah IPServer wajib mengisi ulang DBPass untuk re-enkripsi.')
        show([selected],'[TAHAP 5/6] DATA SEBELUM UPDATE')
        show([changes],'PREVIEW PERUBAHAN')
        print('1. JALANKAN UPDATE\n2. ULANGI\n0. KEMBALI')
        opt=choose('Pilih',{'0','1','2'})
        if opt!='1': return 'RETRY' if opt=='2' else 'BACK'
        sql=[]; params=[]
        for name,value in changes.items():
            if name=='DBPass':
                sql.append('[DBPass]=dbo.fnEncrypt(?,?)')
                params.extend([value,changes.get('IPServer',selected['IPServer'])+SUFFIX])
            else: sql.append('['+name+']=?'); params.append(value)
        cur.execute('UPDATE dbo.ParamFitur SET '+', '.join(sql)+' WHERE IDFitur=?',*(params+[selected['IDFitur']]))
        if cur.rowcount!=1: raise RuntimeError('UPDATE ParamFitur gagal.')
        actual=fetch(cur,'SELECT IDFitur,IPServer,DBName,DBUser,DBType FROM dbo.ParamFitur WHERE IDFitur=?',selected['IDFitur'])
        if len(actual)!=1 or any(str(actual[0][k])!=str(v) for k,v in changes.items() if k!='DBPass'):
            raise RuntimeError('Verifikasi ParamFitur gagal.')
        show(actual,'[TAHAP 6/6] VERIFIKASI SEBELUM COMMIT')
        print('1. COMMIT\n2. ROLLBACK & ULANGI\n0. ROLLBACK & KEMBALI')
        opt=choose('Pilih',{'0','1','2'})
        if opt!='1': conn.rollback(); return 'RETRY' if opt=='2' else 'BACK'
        conn.commit(); committed=True
        print('[SUCCESS] COMMIT ParamFitur berhasil.')
        print('[INFO] UPDATE ParamFitur belum menghasilkan SQL deployment otomatis.')
        return 'DONE'
    finally:
        if not committed:
            try: conn.rollback()
            except Exception: pass
        cur.close()

# BAGIAN 7 — MENU UTAMA DAN NAVIGASI
def run():
    title('GETFTPREPORT - WIZARD INSERT / UPDATE')
    try:
        cfg=choose_server()
        conn=connect_verified(cfg)
    except (Cancel,KeyboardInterrupt):
        print('[INFO] Wizard dibatalkan.'); return
    except Exception as exc:
        print('[ERROR] Koneksi gagal:',exc); return
    try:
        while True:
            title('[TAHAP 2/6] MENU UTAMA - GETFTPREPORT')
            print('1. INSERT KONFIGURASI BARU\n2. UPDATE KONFIGURASI\n0. KELUAR')
            try: option=choose('Pilih menu',{'0','1','2'})
            except Cancel: break
            if option=='0': break
            if option=='2':
                title('PILIH TABEL UNTUK UPDATE')
                print('1. ParamFitur\n2. ParamFTP\n0. KEMBALI')
                try: table=choose('Pilih tabel',{'0','1','2'})
                except Cancel: continue
                if table=='0': continue
            else: table='2'
            while True:
                try:
                    cur=conn.cursor()
                    try:
                        if option=='1': existing,new=pick_pf(cur); old=None
                        elif table=='2':
                            old=find_ftp(cur)
                            title('PILIH PARAMFITUR UNTUK UPDATE PARAMFTP')
                            print('1. PERTAHANKAN IDFitur lama\n2. PILIH ParamFitur lain\n0. KEMBALI')
                            choice=choose('Pilih',{'0','1','2'})
                            if choice=='0': raise Cancel()
                            if choice=='1':
                                result=fetch(cur,'SELECT IDFitur,IPServer,DBName,DBUser,DBType FROM dbo.ParamFitur WHERE IDFitur=?',old['IDFitur'])
                                if len(result)!=1: raise RuntimeError('ParamFitur lama tidak ditemukan.')
                                existing,new=result[0],None
                            else: existing,new=find_pf(cur),None
                    finally: cur.close()
                    if option=='2' and table=='1':
                        status=update_pf(conn)
                    else:
                        p=input_ftp(old)
                        if old:
                            # Key UPDATE tetap dipertahankan karena key berbasis Modul/SubModul.
                            p['LogActivityModul']=old['LogActivityModul']
                            p['LogActivitySubModul']=old['LogActivitySubModul']
                        title('[TAHAP 5/6] PREVIEW KONFIGURASI')
                        if old: show([old],'DATA LAMA PARAMFTP')
                        show([p],'DATA BARU PARAMFTP')
                        show([existing or new],'PARAMFITUR TERPILIH / BARU')
                        print('1. JALANKAN PERUBAHAN\n2. ULANGI INPUT\n0. KEMBALI')
                        choice=choose('Pilih',{'0','1','2'})
                        if choice=='0': status='BACK'
                        elif choice=='2': status='RETRY'
                        else: status=execute_ftp(conn,'INSERT' if option=='1' else 'UPDATE',p,existing,new,old)
                    if status=='RETRY': continue
                    break
                except (Cancel,KeyboardInterrupt):
                    try: conn.rollback()
                    except Exception: pass
                    print('[INFO] Operasi dibatalkan, kembali ke menu.'); break
                except Exception as exc:
                    try: conn.rollback()
                    except Exception: pass
                    print('[ERROR]',type(exc).__name__+':',exc)
                    print('1. ULANGI\n0. KEMBALI')
                    try: retry=choose('Pilih',{'0','1'})
                    except Cancel: break
                    if retry!='1': break
    finally:
        conn.close()
        print('[INFO] Koneksi ditutup. Wizard selesai.')

if __name__=='__main__':
    run()
