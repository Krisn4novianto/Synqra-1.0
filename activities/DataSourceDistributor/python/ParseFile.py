#!/usr/bin/env python3
"""
===============================================================================
PARSEFILE - PARAMPARSEFILE CONFIGURATION WIZARD
===============================================================================

PANDUAN SINGKAT:
 1. Pilih Server 205 atau Localhost dari db_config.py.
 2. Pilih INSERT atau UPDATE pada menu utama.
 3. Pilih ParamFitur berdasarkan DBName/IDFitur atau buat baru.
 4. Pilih/buat ParamParseFile; IDFitur diisi otomatis.
 5. Tambah/ubah mapping; IDParamParseFile diisi otomatis.
 6. Periksa SELECT aktual, lalu ketik COMMIT atau ROLLBACK.
 7. Sebelum INSERT/UPDATE, backup tiga tabel disimpan permanen di SQL Server.
 8. Setelah COMMIT, simpan SQL deployment SOP dengan backup tabel.

CATATAN KEAMANAN:
 - DBPass dienkripsi di SQL Server menggunakan dbo.fnEncrypt.
 - Password tidak ditampilkan atau disimpan sebagai teks biasa dalam SQL SOP.
 - Deployment ParamFitur baru meminta variabel SQLCMD DBPASS.
 - Backup live memakai koneksi terpisah dan tetap ada setelah ROLLBACK.
 - SELECT INTO tidak menyalin indeks, constraint, trigger, atau permission.
 - Uji pada lingkungan development sebelum production.
===============================================================================
"""
from __future__ import annotations

import getpass
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from db_config import SERVERS
from db_connection import connect_sqlserver

DATABASE = 'DataSourceDistributor'
PF = 'dbo.ParamFitur'
PP = 'dbo.ParamParseFile'
MC = 'dbo.ParamParseFileMappingColumn'
OUTPUT = ROOT / 'output' / '01_Reconciliation' / 'ParseFile'
PP_FIELDS = ['LocalPath','Filename','TableDestination','FieldFilename','FieldFiledate',
             'LogActivityModul','LogActivitySubModul','LogActivityEntity',
             'LogActivityFilenameDateAdd','IsFixedCol','Delimiter','HeaderRowSkip',
             'FooterRowSkip','TextQualifier','isActive','Note']
MAP_FIELDS = ['Col','FieldTargetName','FixedColSubstring']
SECRET_COLUMNS = {'DBPass'}

class Cancel(Exception):
    pass

def stage(n, title):
    print('\n' + '=' * 72)
    print(f'[TAHAP {n}/6] {title}')
    print('=' * 72)

def info(message): print('[INFO] ' + str(message))
def quote(name): return '[' + str(name).replace(']', ']]') + ']'
def literal(value):
    if value is None: return 'NULL'
    if isinstance(value, bool): return '1' if value else '0'
    if isinstance(value, (int, float, Decimal)): return str(value)
    if isinstance(value, datetime): return "N'" + value.isoformat(sep=' ') + "'"
    return "N'" + str(value).replace("'", "''") + "'"

def ask(label, default=None, required=False, secret=False):
    while True:
        suffix = f' [{default}]' if default is not None and not secret else ''
        value = (getpass.getpass if secret else input)(f'{label}{suffix} (B=batal): ').strip()
        if value.upper() == 'B' and not secret: raise Cancel()
        if not value and default is not None: value = str(default)
        if value or not required: return value
        print('[ERROR] Nilai wajib diisi.')

def pick(title, options, back=True):
    print('\n' + title)
    for i, option in enumerate(options, 1): print(f'  {i}. {option}')
    if back: print('  0. KEMBALI / BATAL')
    while True:
        raw = input('Pilih nomor (B=batal): ').strip().upper()
        if raw == 'B' or (back and raw == '0'): raise Cancel()
        if raw.isdigit() and 1 <= int(raw) <= len(options): return int(raw)-1
        print('[ERROR] Pilihan tidak valid.')

def table(data, title, limit=30):
    print('\n--- ' + title + ' ---')
    if not data:
        print('(tidak ada data)'); return
    keys = list(data[0])
    print(' | '.join(str(k)[:24].ljust(24) for k in keys))
    print('-' * min(160, 27 * len(keys)))
    for row in data[:limit]:
        print(' | '.join(('[DIRAHASIAKAN]' if k in SECRET_COLUMNS else str(row.get(k, 'NULL')))[:24].ljust(24) for k in keys))
    print(f'Jumlah record: {len(data)}' + (' (sebagian ditampilkan)' if len(data)>limit else ''))

def config_value(cfg, key): return cfg.get(key) if isinstance(cfg, dict) else getattr(cfg, key, None)

def choose_connection():
    stage(1, 'PILIH KONEKSI DATABASE')
    print(f'Database target : {DATABASE}')
    choices = [('Server 205', '172.18.135.205'), ('Localhost', 'localhost')]
    found = []
    for label, host in choices:
        matched = [(key, cfg) for key,cfg in SERVERS.items() if str(config_value(cfg,'host')).lower() == host.lower()]
        if len(matched) != 1: raise RuntimeError(f'Konfigurasi {label} ({host}) harus tepat satu di db_config.py.')
        found.append((label, matched[0][1]))
    index = pick('Pilih salah satu koneksi:', [f'{label}  ({config_value(cfg,"host")}:{config_value(cfg,"port")})' for label,cfg in found])
    label,cfg = found[index]
    info(f'Koneksi dipilih : {label}')
    info(f'Menghubungkan langsung ke {DATABASE}...')
    conn = connect_sqlserver(cfg, DATABASE)
    conn.autocommit = False
    cur = conn.cursor()
    try:
        cur.execute('SELECT DB_NAME()')
        if str(cur.fetchone()[0]).lower() != DATABASE.lower(): raise RuntimeError('Database aktif tidak sesuai target.')
        for name in (PF, PP, MC):
            cur.execute('SELECT OBJECT_ID(?, ?)', name, 'U')
            if cur.fetchone()[0] is None: raise RuntimeError(f'Tabel {name} tidak ditemukan.')
    except Exception:
        conn.close(); raise
    finally:
        cur.close()
    info('Koneksi dan ketiga tabel berhasil diverifikasi.')
    return conn, cfg

def metadata(cur, table_name):
    schema,name = table_name.split('.')
    cur.execute('''SELECT c.name, TYPE_NAME(c.user_type_id), c.is_nullable, c.is_identity,
                   c.is_computed, c.default_object_id FROM sys.columns c
                   JOIN sys.tables t ON t.object_id=c.object_id
                   JOIN sys.schemas s ON s.schema_id=t.schema_id
                   WHERE s.name=? AND t.name=? ORDER BY c.column_id''',schema,name)
    data = {r[0]: dict(type=str(r[1]).lower(),nullable=bool(r[2]),identity=bool(r[3]),computed=bool(r[4]),default=bool(r[5])) for r in cur.fetchall()}
    if not data: raise RuntimeError(f'Metadata {table_name} tidak ditemukan.')
    return data

def parse_value(value, typ):
    if value.upper() == 'NULL': return None
    if typ in ('int','bigint','smallint','tinyint','bit'): return int(value)
    if typ in ('decimal','numeric','money','smallmoney','float','real'): return Decimal(value)
    return value

def records(cur, tab, where='', args=(), top=200):
    cur.execute(f'SELECT TOP ({int(top)}) * FROM {tab}' + (f' WHERE {where}' if where else '') + ';', *args)
    names=[d[0] for d in cur.description]
    return [dict(zip(names,row)) for row in cur.fetchall()]

def insert_row(cur, tab, data, pk=None):
    names=list(data)
    sql=f'INSERT INTO {tab} ('+', '.join(quote(k) for k in names)+')'
    if pk: sql+=f' OUTPUT INSERTED.{quote(pk)}'
    sql+=' VALUES ('+', '.join('?' for _ in names)+')'
    cur.execute(sql, *(data[k] for k in names))
    if pk:
        row=cur.fetchone()
        if not row: raise RuntimeError('INSERT tidak mengembalikan identity.')
        return int(row[0])
    if cur.rowcount not in (1,-1): raise RuntimeError('INSERT gagal.')

def update_row(cur, tab, changes, where, args):
    if not changes: return
    cur.execute(f'SELECT COUNT(*) FROM {tab} WHERE {where}',*args)
    if int(cur.fetchone()[0]) != 1: raise RuntimeError('UPDATE ditolak: target tidak tepat satu baris.')
    sql=f'UPDATE {tab} SET '+', '.join(f'{quote(k)}=?' for k in changes)+f' WHERE {where}'
    cur.execute(sql, *changes.values(), *args)
    if cur.rowcount not in (1,-1): raise RuntimeError('UPDATE tidak tepat satu baris.')

def input_fields(cur, tab, fields, current=None, replace=False):
    meta=metadata(cur,tab); result={}
    for field in fields:
        if field not in meta: raise RuntimeError(f'Kolom {tab}.{field} tidak ditemukan.')
        m=meta[field]
        if m['identity'] or m['computed']: continue
        old=current.get(field) if current else None
        hint='Enter=tidak diubah, NULL=kosongkan' if current and not replace else 'NULL=kosongkan'
        raw=ask(f'{field} ({m["type"]}; {hint})',required=(current is None and not m['nullable'] and not m['default']))
        if not raw:
            if current is not None: continue
            if m['default']: continue
            if m['nullable']: result[field]=None
            continue
        value=parse_value(raw,m['type'])
        if value is None and not m['nullable']: raise ValueError(f'{field} tidak boleh NULL.')
        if current is None or value != old: result[field]=value
    return result

def choose_row(data, title, label_keys):
    if not data: raise RuntimeError(f'Tidak ada record untuk {title}.')
    table(data,title)
    i=pick('PILIH RECORD', [' | '.join(f'{k}={str(r.get(k))[:30]}' for k in label_keys) for r in data])
    return data[i]

def edit_fields(cur, tab, row, allowed):
    options=[x for x in allowed if x in row]
    selected=[]
    while True:
        remaining=[x for x in options if x not in selected]
        idx=pick('KOLOM YANG INGIN DIUBAH',remaining+['SELESAI PILIH KOLOM'])
        if idx==len(remaining): break
        selected.append(remaining[idx])
    if not selected: return {}
    changes=input_fields(cur,tab,selected,current=row)
    table([dict(Kolom=k,Lama=row.get(k),Baru=v) for k,v in changes.items()],'PREVIEW PERUBAHAN')
    return changes

def feature_stage(cur, ops, mode):
    stage(3, 'PILIH / KELOLA PARAMFITUR')
    action=pick('PARAMFITUR', ['GUNAKAN PARAMFITUR EXISTING','INSERT PARAMFITUR BARU','UPDATE PARAMFITUR EXISTING'])
    if action in (0,2):
        key=ask('Cari DBName (Enter=semua)')
        cur.execute(f'SELECT DISTINCT DBName FROM {PF} WHERE DBName IS NOT NULL AND DBName LIKE ? ORDER BY DBName',f'%{key}%')
        names=[str(r[0]) for r in cur.fetchall()]
        if not names: raise RuntimeError('DBName tidak ditemukan.')
        dbname=names[pick('PILIH DBNAME',names)]
        cur.execute(f'SELECT IDFitur, IPServer, DBName, DBUser, DBType FROM {PF} WHERE DBName=? ORDER BY IDFitur',dbname)
        names=['IDFitur','IPServer','DBName','DBUser','DBType']
        items=[dict(zip(names,r)) for r in cur.fetchall()]
        row=choose_row(items,'PARAMFITUR EXISTING',['IDFitur','IPServer','DBName'])
        if action==2:
            changes=edit_fields(cur,PF,row,['IPServer','DBName','DBUser','DBType'])
            if changes:
                update_row(cur,PF,changes,'IDFitur=?',(row['IDFitur'],))
                ops.append(dict(table=PF,action='UPDATE',before=row.copy(),changes=changes,where={'IDFitur':row['IDFitur']}))
                row.update(changes)
        return int(row['IDFitur']),row
    ip=ask('IPServer target',required=True); db=ask('DBName target',required=True)
    cur.execute(f'SELECT COUNT(*) FROM {PF} WHERE IPServer=? AND DBName=?',ip,db)
    if int(cur.fetchone()[0]): raise RuntimeError('ParamFitur sudah ada; pilih existing.')
    user=ask('DBUser',required=True); password=getpass.getpass('DBPass (tersembunyi): ')
    if not password: raise RuntimeError('DBPass wajib diisi.')
    typ=ask('DBType','mssql',required=True)
    data=dict(IPServer=ip,DBName=db,DBUser=user,DBType=typ)
    table([data],'PREVIEW PARAMFITUR BARU')
    cur.execute(f'''INSERT INTO {PF}(IPServer,DBName,DBUser,DBPass,DBType)
                    OUTPUT INSERTED.IDFitur VALUES (?,?,?,dbo.fnEncrypt(?,?+'BR!'),?)''',ip,db,user,password,ip,typ)
    row=cur.fetchone()
    if not row: raise RuntimeError('Gagal membuat IDFitur.')
    idf=int(row[0]); data['IDFitur']=idf
    ops.append(dict(table=PF,action='INSERT',values=data.copy(),needs_password=True))
    return idf,data

def parent_pk(cur):
    cur.execute('''SELECT c.name FROM sys.indexes i JOIN sys.index_columns ic
        ON i.object_id=ic.object_id AND i.index_id=ic.index_id
        JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id
        WHERE i.object_id=OBJECT_ID(?) AND i.is_primary_key=1 ORDER BY ic.key_ordinal''',PP)
    names=[r[0] for r in cur.fetchall()]
    if len(names)==1:return names[0]
    cols=metadata(cur,PP)
    for name in ('IDParamParseFile','ID'):
        if name in cols:return name
    raise RuntimeError('Primary key ParamParseFile tidak ditemukan.')

def parent_stage(cur,idf,ops,pk,mode):
    stage(4, 'KELOLA PARAMPARSEFILE')
    existing=records(cur,PP,'IDFitur=?',(idf,),top=1000)
    options=['INSERT KONFIGURASI BARU','UPDATE KONFIGURASI EXISTING','REPLACE NILAI EXISTING','GUNAKAN EXISTING / SKIP']
    if mode=='INSERT': options=['INSERT KONFIGURASI BARU','GUNAKAN EXISTING / SKIP']
    action=options[pick('PILIH OPERASI PARAMPARSEFILE',options)]
    if action.startswith('INSERT'):
        data={'IDFitur':idf}; data.update(input_fields(cur,PP,PP_FIELDS))
        table([data],'PREVIEW INSERT PARAMPARSEFILE')
        pid=insert_row(cur,PP,data,pk)
        ops.append(dict(table=PP,action='INSERT',values=data,local_id=pid))
        return pid
    row=choose_row(existing,'PILIH PARAMPARSEFILE',[pk,'Filename','LogActivityModul'])
    pid=int(row[pk])
    if action.startswith('UPDATE') or action.startswith('REPLACE'):
        changes=(edit_fields(cur,PP,row,PP_FIELDS) if action.startswith('UPDATE') else input_fields(cur,PP,PP_FIELDS,current=row,replace=True))
        if changes:
            update_row(cur,PP,changes,f'{quote(pk)}=? AND IDFitur=?',(pid,idf))
            ops.append(dict(table=PP,action='UPDATE',before=row,changes=changes,local_id=pid))
    return pid

def mapping_stage(cur,pid,ops,mode):
    stage(5, 'KELOLA MAPPING COLUMN')
    metadata(cur,MC)
    while True:
        current=records(cur,MC,'IDParamParseFile=?',(pid,),top=1000)
        table(current,f'MAPPING IDParamParseFile={pid}')
        options=['INSERT MAPPING BARU','UPDATE MAPPING EXISTING','SELESAI / SKIP']
        action=pick('PILIH OPERASI MAPPING',options)
        if action==2: break
        if action==0:
            data={'IDParamParseFile':pid}; data.update(input_fields(cur,MC,MAP_FIELDS))
            if data.get('Col') is None or not data.get('FieldTargetName'): raise ValueError('Col dan FieldTargetName wajib diisi.')
            cur.execute(f'SELECT COUNT(*) FROM {MC} WHERE IDParamParseFile=? AND Col=?',pid,data['Col'])
            if int(cur.fetchone()[0]): print('[ERROR] Col sudah ada.');continue
            table([data],'PREVIEW INSERT MAPPING')
            insert_row(cur,MC,data)
            ops.append(dict(table=MC,action='INSERT',values=data))
        else:
            row=choose_row(current,'PILIH MAPPING',['Col','FieldTargetName'])
            col=row['Col'];changes=edit_fields(cur,MC,row,MAP_FIELDS)
            if not changes:continue
            if 'Col' in changes:
                cur.execute(f'SELECT COUNT(*) FROM {MC} WHERE IDParamParseFile=? AND Col=?',pid,changes['Col'])
                if int(cur.fetchone()[0]): raise RuntimeError('Col baru sudah digunakan.')
            update_row(cur,MC,changes,'IDParamParseFile=? AND Col=?',(pid,col))
            ops.append(dict(table=MC,action='UPDATE',before=row,changes=changes,old_col=col))

def backup_live(cfg):
    """Backup permanen ketiga tabel SEBELUM transaksi perubahan dimulai.

    Gunakan koneksi terpisah dengan autocommit agar tabel backup tetap ada
    walaupun wizard melakukan ROLLBACK pada transaksi konfigurasi.
    Bila salah satu backup gagal, hentikan operasi (fail closed).
    """
    suffix = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    names = ('ParamFitur', 'ParamParseFile', 'ParamParseFileMappingColumn')
    backup_conn = connect_sqlserver(cfg, DATABASE)
    backup_conn.autocommit = True
    created = []
    try:
        cursor = backup_conn.cursor()
        try:
            for name in names:
                backup_name = f'{name}_Backup_{suffix}'
                # Identifier bersumber dari konstanta internal dan timestamp.
                if len(backup_name) > 128:
                    raise RuntimeError('Nama tabel backup terlalu panjang.')
                cursor.execute("SELECT OBJECT_ID(?, 'U')", f'dbo.{backup_name}')
                if cursor.fetchone()[0] is not None:
                    raise RuntimeError(f'Backup dbo.{backup_name} sudah ada.')
                cursor.execute(
                    f'SELECT * INTO dbo.[{backup_name}] FROM dbo.[{name}];'
                )
                created.append(backup_name)
                info(f'Backup live tersimpan: dbo.{backup_name}')
        finally:
            cursor.close()
    except Exception as exc:
        print('[ERROR] Backup tidak lengkap; perubahan konfigurasi dibatalkan.')
        if created:
            print('[INFO] Tabel backup yang berhasil dibuat tetap tersimpan: '
                  + ', '.join('dbo.' + n for n in created))
        raise RuntimeError(f'Gagal membuat backup live: {exc}') from exc
    finally:
        backup_conn.close()
    return created


def sql_backup():
    return '''-- BACKUP SEBELUM TRANSAKSI. Backup tetap tersedia saat ROLLBACK.
DECLARE @Suffix VARCHAR(32)=CONVERT(CHAR(8),GETDATE(),112)+'_'+REPLACE(CONVERT(CHAR(8),GETDATE(),108),':','');
DECLARE @T SYSNAME,@B SYSNAME,@S NVARCHAR(MAX);
DECLARE @Tables TABLE(T SYSNAME);
INSERT INTO @Tables VALUES(N'ParamFitur'),(N'ParamParseFile'),(N'ParamParseFileMappingColumn');
DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT T FROM @Tables;
OPEN c; FETCH NEXT FROM c INTO @T;
WHILE @@FETCH_STATUS=0
BEGIN
 SET @B=@T+N'_Backup_'+@Suffix;
 IF OBJECT_ID(N'dbo.'+QUOTENAME(@B),N'U') IS NOT NULL THROW 51001,'Backup sudah ada',1;
 SET @S=N'SELECT * INTO dbo.'+QUOTENAME(@B)+N' FROM dbo.'+QUOTENAME(@T);
 EXEC sys.sp_executesql @S;
 FETCH NEXT FROM c INTO @T;
END
CLOSE c; DEALLOCATE c;'''

def deploy_sql(feature, ops, pk, parent_before):
    """Bangun deployment portabel dengan resolusi ID berdasarkan natural key.

    Password hanya diminta melalui SQLCMD, bukan disimpan dalam file.
    """
    ip=literal(feature['IPServer']); db=literal(feature['DBName'])
    lines=[f'''/* ============================================================================
PARSEFILE - SQL DEPLOYMENT SOP
DATABASE: {DATABASE}
PERINGATAN: Jalankan dengan SQLCMD mode jika ada ParamFitur INSERT.
BACKUP SELECT INTO tidak menyalin index/constraint/trigger/permission.
============================================================================ */
USE {quote(DATABASE)};
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;
{sql_backup()}
GO
BEGIN TRY
BEGIN TRANSACTION;
DECLARE @IDFitur INT, @IDParamParseFile INT;
''']
    pf_insert=next((o for o in ops if o['table']==PF and o['action']=='INSERT'),None)
    pf_update=next((o for o in ops if o['table']==PF and o['action']=='UPDATE'),None)
    if pf_insert:
        d=pf_insert['values']
        lines.append(f'''IF EXISTS(SELECT 1 FROM {PF} WHERE IPServer={ip} AND DBName={db}) THROW 51002,'ParamFitur sudah ada',1;
-- Aktifkan SQLCMD Mode; berikan nilai DBPASS melalui variabel SQLCMD.
INSERT INTO {PF}(IPServer,DBName,DBUser,DBPass,DBType)
VALUES({ip},{db},{literal(d['DBUser'])},dbo.fnEncrypt(N'$(DBPASS)',{ip}+N'BR!'),{literal(d['DBType'])});''')
    if pf_update:
        before=pf_update['before']; change=pf_update['changes']
        lines.append(f'''IF (SELECT COUNT(*) FROM {PF} WHERE IPServer={literal(before['IPServer'])} AND DBName={literal(before['DBName'])})<>1 THROW 51003,'ParamFitur target ambigu',1;
UPDATE {PF} SET '''+', '.join(f'{quote(k)}={literal(v)}' for k,v in change.items())+f" WHERE IPServer={literal(before['IPServer'])} AND DBName={literal(before['DBName'])};")
    lines.append(f'''IF (SELECT COUNT(*) FROM {PF} WHERE IPServer={ip} AND DBName={db})<>1 THROW 51004,'ParamFitur tidak unik',1;
SELECT @IDFitur=IDFitur FROM {PF} WHERE IPServer={ip} AND DBName={db};''')
    pp_insert=next((o for o in ops if o['table']==PP and o['action']=='INSERT'),None)
    pp_update=next((o for o in ops if o['table']==PP and o['action']=='UPDATE'),None)
    if pp_insert:
        d=pp_insert['values']; keys=list(d)
        lines.append(f"INSERT INTO {PP} ("+', '.join(quote(k) for k in keys)+') VALUES ('+', '.join('@IDFitur' if k=='IDFitur' else literal(d[k]) for k in keys)+');')
        lines.append('SET @IDParamParseFile=CONVERT(INT,SCOPE_IDENTITY());')
    else:
        before=pp_update['before'] if pp_update else parent_before
        stable=['LocalPath','Filename','TableDestination','LogActivityModul','LogActivitySubModul','LogActivityEntity']
        criteria=[f'p.{quote(k)} '+('IS NULL' if before.get(k) is None else '= '+literal(before[k])) for k in stable if k in before]
        where=' AND '.join(['p.IDFitur=@IDFitur']+criteria)
        lines.append(f"IF (SELECT COUNT(*) FROM {PP} p WHERE {where})<>1 THROW 51005,'ParamParseFile tidak unik',1;")
        lines.append(f'SELECT @IDParamParseFile=p.{quote(pk)} FROM {PP} p WHERE {where};')
        if pp_update:
            lines.append(f'UPDATE {PP} SET '+', '.join(f'{quote(k)}={literal(v)}' for k,v in pp_update['changes'].items())+f' WHERE {quote(pk)}=@IDParamParseFile;')
    for op in ops:
        if op['table']!=MC:continue
        if op['action']=='INSERT':
            d=op['values']; keys=list(d)
            lines.append(f"IF EXISTS(SELECT 1 FROM {MC} WHERE IDParamParseFile=@IDParamParseFile AND Col={literal(d['Col'])}) THROW 51006,'Mapping Col sudah ada',1;")
            lines.append(f'INSERT INTO {MC} ('+', '.join(quote(k) for k in keys)+') VALUES ('+', '.join('@IDParamParseFile' if k=='IDParamParseFile' else literal(d[k]) for k in keys)+');')
        else:
            lines.append(f"IF (SELECT COUNT(*) FROM {MC} WHERE IDParamParseFile=@IDParamParseFile AND Col={literal(op['old_col'])})<>1 THROW 51007,'Mapping ambigu',1;")
            lines.append(f'UPDATE {MC} SET '+', '.join(f'{quote(k)}={literal(v)}' for k,v in op['changes'].items())+f" WHERE IDParamParseFile=@IDParamParseFile AND Col={literal(op['old_col'])};")
    lines.append(f'''IF (SELECT COUNT(*) FROM {PP} WHERE {quote(pk)}=@IDParamParseFile AND IDFitur=@IDFitur)<>1 THROW 51008,'Verifikasi gagal',1;
COMMIT TRANSACTION;
END TRY
BEGIN CATCH
 IF @@TRANCOUNT>0 ROLLBACK TRANSACTION;
 THROW;
END CATCH;
SELECT IDFitur,IPServer,DBName,DBUser,DBType FROM {PF} WHERE IDFitur=@IDFitur;
SELECT * FROM {PP} WHERE {quote(pk)}=@IDParamParseFile;
SELECT * FROM {MC} WHERE IDParamParseFile=@IDParamParseFile;
GO''')
    return '\n\n'.join(lines)+'\n'

def run():
    print('\n'+'='*72+'\nPARSEFILE - WIZARD INSERT / UPDATE\n'+'='*72)
    conn=None
    cfg=None
    while True:
        try:
            conn,cfg=choose_connection();break
        except Cancel:
            info('Wizard dibatalkan.');return
        except Exception as exc:
            print(f'[ERROR] {type(exc).__name__}: {exc}')
            try:
                if pick('KONEKSI GAGAL',['COBA LAGI','KELUAR'])==1:return
            except Cancel:return
    try:
        cur=conn.cursor(); pk=parent_pk(cur)
        while True:
            try:
                stage(2,'MENU UTAMA')
                try:
                    mode=['INSERT','UPDATE'][pick('MENU UTAMA - PARSEFILE',['INSERT KONFIGURASI BARU','UPDATE KONFIGURASI'])]
                except Cancel:
                    break
                ops=[]
                try:
                    # Backup HARUS selesai sebelum DML apa pun pada koneksi live.
                    # Backup menggunakan autocommit di koneksi terpisah.
                    # Karena itu snapshot tetap ada saat transaksi wizard ROLLBACK.
                    backup_names = backup_live(cfg)
                    info(f'{len(backup_names)} tabel backup berhasil dibuat sebelum perubahan.')
                    idf,feature=feature_stage(cur,ops,mode)
                    pid=parent_stage(cur,idf,ops,pk,mode)
                    mapping_stage(cur,pid,ops,mode)
                    stage(6,'PREVIEW, VERIFIKASI DAN COMMIT / ROLLBACK')
                    parent=records(cur,PP,f'{quote(pk)}=?',(pid,))
                    if len(parent)!=1:raise RuntimeError('Parent tidak tepat satu record.')
                    table(records(cur,PF,'IDFitur=?',(idf,)),'PARAMFITUR (BELUM COMMIT)')
                    table(parent,'PARAMPARSEFILE (BELUM COMMIT)')
                    table(records(cur,MC,'IDParamParseFile=?',(pid,),top=1000),'MAPPING (BELUM COMMIT)')
                    if not ops:
                        info('Tidak ada perubahan.');conn.rollback();continue
                    choice=input('Ketik COMMIT untuk menyimpan (lainnya ROLLBACK): ').strip().upper()
                    if choice!='COMMIT':conn.rollback();info('ROLLBACK berhasil.');continue
                    # Buat SQL di memori dahulu; jangan tulis file sebelum COMMIT.
                    sql=deploy_sql(feature,ops,pk,parent[0])
                    conn.commit()
                    info('COMMIT berhasil.')
                    try:
                        OUTPUT.mkdir(parents=True,exist_ok=True)
                        stamp=datetime.now().strftime('%Y-%m-%d_%H%M%S_%f')
                        path=OUTPUT/f'ParseFile_{stamp}.sql'
                        path.write_text(sql,encoding='utf-8')
                        info(f'SQL deployment: {path}')
                        if any(o.get('needs_password') for o in ops):
                            info('Deployment membutuhkan SQLCMD variable DBPASS; jangan simpan password di SQL.')
                    except OSError as exc:
                        print(f'[ERROR] COMMIT SUDAH BERHASIL, tetapi file SQL gagal ditulis: {exc}')
                except Cancel:
                    conn.rollback();info('Kembali ke menu utama; ROLLBACK.')
                except (KeyboardInterrupt,EOFError):
                    conn.rollback();info('Dibatalkan; ROLLBACK.');break
                except Exception as exc:
                    conn.rollback();print(f'[ERROR] {type(exc).__name__}: {exc}\n[INFO] ROLLBACK dijalankan.')
            except (KeyboardInterrupt,EOFError):
                conn.rollback();break
    finally:
        conn.close()
    info('Wizard selesai.')

if __name__=='__main__':
    run()
