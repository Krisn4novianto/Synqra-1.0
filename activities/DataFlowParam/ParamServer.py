#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DATAFLOWPARAM — WIZARD INSERT/UPDATE + SOP BACKUP

SOP OPERASIONAL:
 1. Pilih Server 205 atau Localhost dari db_config.py.
 2. Koneksi langsung ke DataFlowParam; verifikasi tabel target.
 3. Pilih operasi satu tabel atau operasi berantai.
 4. Cari record UPDATE menggunakan kolom yang dipilih; SQL NULL didukung.
 5. Periksa preview; DBPass selalu disembunyikan.
 6. Buat snapshot ASLI menggunakan SELECT INTO sebelum DML.
 7. COMMIT backup pada transaksi terpisah sehingga tahan ROLLBACK DML.
 8. Jalankan DML, verifikasi, lalu pilih COMMIT atau ROLLBACK.
 9. Setelah COMMIT, simpan SQL deployment dengan SOP backup yang sama.
10. Jalankan deployment dalam SQLCMD mode bila membutuhkan DBPASS.

CATATAN: Snapshot bukan SQL Server BACKUP DATABASE (.bak). SELECT INTO tidak
menyalin index, constraint, trigger, atau permission. Uji di development.
"""
from __future__ import annotations
import getpass
import secrets
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve()
ROOT = next((p for p in HERE.parents if (p/'db_config.py').is_file() and (p/'db_connection.py').is_file()), None)
if ROOT is None:
    raise SystemExit('[ERROR] db_config.py dan db_connection.py tidak ditemukan di parent script.')
sys.path.insert(0, str(ROOT))
from db_config import SERVERS
from db_connection import connect_sqlserver

DATABASE = 'DataFlowParam'
TABLES = ('ParamServer', 'ParamFitur', 'ParamFiturCekLogActivity')
RELATIONS = {
    'ParamFitur': {'IPServerSourceId':'source','IPServerDestinationId':'destination','IPServerLogActivityId':'log'},
    'ParamFiturCekLogActivity': {'IDFitur':'feature','IPServerLogActivityId':'log'},
}
OUTPUT = HERE.parent/'output'/'01_Reconciliation'/'DataFlowParam'
SKIP_TYPES = {'timestamp','rowversion','image','varbinary','binary'}

class Cancel(Exception): pass

def heading(s): print('\n'+'='*72+'\n'+s+'\n'+'='*72)
def warn(s): print('[WARNING]',s)
def info(s): print('[INFO]',s)
def qi(s):
    if not s or any(c in s for c in '[]') or not all(c.isalnum() or c=='_' for c in s):
        raise ValueError('Identifier SQL tidak valid: '+str(s))
    return '['+s+']'
def tn(s):
    if s not in TABLES: raise ValueError('Tabel tidak diizinkan: '+str(s))
    return 'dbo.'+qi(s)
def lit(v):
    if v is None: return 'NULL'
    if isinstance(v,(bool,int,Decimal,float)): return str(int(v)) if isinstance(v,bool) else str(v)
    return "N'"+str(v).replace("'","''")+"'"
def hidden(k,v): return '[TERSEMBUNYI]' if k.lower()=='dbpass' else ('NULL' if v is None else str(v))
def choose(label, opts):
    while True:
        try: v=input(label+' (B=batal): ').strip().upper()
        except (EOFError,KeyboardInterrupt): raise Cancel()
        if v=='B': raise Cancel()
        if v in opts: return v
        warn('Pilihan tidak valid: '+', '.join(sorted(opts)))
def yes(label): return choose(label+' 1=Ya 0=Tidak',{'0','1'})=='1'
def config_value(c,k,d=None): return c.get(k,d) if isinstance(c,dict) else getattr(c,k,d)
def host(c): return str(config_value(c,'host',config_value(c,'server',''))).lower()

def connect():
    heading('[TAHAP 1/6] PILIH SERVER')
    configs=list(SERVERS.values()) if isinstance(SERVERS,dict) else list(SERVERS)
    opts=[('Server 205',next((c for c in configs if host(c)=='172.18.135.205'),None)),
          ('Localhost',next((c for c in configs if host(c) in ('localhost','127.0.0.1','::1')),None))]
    opts=[x for x in opts if x[1] is not None]
    if not opts: raise RuntimeError('Server 205/Localhost tidak ada di db_config.SERVERS.')
    for i,(name,cfg) in enumerate(opts,1): print(f'{i}. {name} ({host(cfg)}:{config_value(cfg,"port",1433)})')
    print('0. KELUAR')
    sel=choose('Pilih server',{str(i) for i in range(len(opts)+1)})
    if sel=='0': raise Cancel()
    cfg=opts[int(sel)-1][1]
    conn=connect_sqlserver(cfg,DATABASE)
    try:
        conn.autocommit=True
        cur=conn.cursor()
        cur.execute('SELECT @@SERVERNAME, DB_NAME(), ORIGINAL_LOGIN()')
        server,db,login=cur.fetchone()
        print('SQL Server:',server,'| Database:',db,'| Login:',login)
        if str(db).lower()!=DATABASE.lower(): raise RuntimeError('Database target tidak sesuai.')
        for t in TABLES:
            cur.execute("SELECT OBJECT_ID(?, 'U')",'dbo.'+t)
            if cur.fetchone()[0] is None: raise RuntimeError('Tabel dbo.'+t+' tidak ditemukan.')
        cur.close()
        return conn
    except Exception:
        conn.close(); raise

def rows(conn,sql,*args):
    cur=conn.cursor()
    try:
        cur.execute(sql,*args)
        names=[d[0] for d in cur.description]
        return [dict(zip(names,r)) for r in cur.fetchall()]
    finally: cur.close()

def schema(conn,t):
    result=rows(conn,'''SELECT c.name AS name, ty.name AS type, c.is_identity AS identity,
        c.is_nullable AS nullable,c.is_computed AS computed,dc.definition AS default_value
        FROM sys.columns c JOIN sys.tables tb ON c.object_id=tb.object_id
        JOIN sys.schemas s ON tb.schema_id=s.schema_id
        JOIN sys.types ty ON c.user_type_id=ty.user_type_id
        LEFT JOIN sys.default_constraints dc ON c.default_object_id=dc.object_id
        WHERE s.name='dbo' AND tb.name=? ORDER BY c.column_id''',t)
    if not result: raise RuntimeError('Skema tidak ditemukan: '+t)
    return result

def convert(meta,raw):
    if raw.upper()=='NULL':
        if not meta['nullable']: raise ValueError('Kolom tidak menerima NULL')
        return None
    typ=meta['type'].lower()
    if typ in ('int','smallint','tinyint','bigint','bit'):
        v=int(raw)
        if typ=='bit' and v not in (0,1): raise ValueError('Bit harus 0/1')
        return v
    if typ in ('decimal','numeric','float','real','money','smallmoney'): return Decimal(raw)
    return raw

def input_fields(conn,t,update=False,exclude=()):
    heading(('UPDATE' if update else 'INSERT')+' dbo.'+t)
    print('ENTER = lewati/pertahankan; NULL = SQL NULL; B = batal (kecuali password).')
    result={}
    for m in schema(conn,t):
        k=m['name']
        if m['identity'] or m['computed'] or k in exclude or m['type'].lower() in ('timestamp','rowversion'): continue
        while True:
            try: raw=(getpass.getpass if k=='DBPass' else input)(f'{k} ({m["type"]}): ')
            except (EOFError,KeyboardInterrupt): raise Cancel()
            if k!='DBPass' and raw.upper()=='B': raise Cancel()
            if raw=='':
                if not update and not m['nullable'] and m['default_value'] is None:
                    warn(k+' wajib diisi'); continue
                break
            try: result[k]=convert(m,raw); break
            except (ValueError,TypeError) as exc: warn(str(exc))
    return result

def predicate(values):
    parts=[]; params=[]
    for k,v in values.items():
        parts.append(qi(k)+(' IS NULL' if v is None else '=?'))
        if v is not None: params.append(v)
    if not parts: raise ValueError('Filter kosong')
    return ' AND '.join(parts),params

def show(records):
    for i,r in enumerate(records,1):
        print(f'--- RECORD {i} ---')
        for k,v in r.items(): print(f'  {k:<28}: {hidden(k,v)}')
    print('Total:',len(records))

def select_record(conn,t,extra=None):
    metas=schema(conn,t)
    visible=[m for m in metas if m['name']!='DBPass' and m['type'].lower() not in SKIP_TYPES]
    heading('CARI RECORD dbo.'+t)
    for i,m in enumerate(visible,1): print(f'{i}. {m["name"]}')
    print('0. KEMBALI')
    while True:
        raw=input('Kolom pencarian (misal 1,2; 0=batal): ').strip()
        if raw=='0': raise Cancel()
        try:
            nums=[int(s.strip()) for s in raw.split(',')]
            if not nums or len(nums)!=len(set(nums)) or any(n<1 or n>len(visible) for n in nums): raise ValueError()
            break
        except ValueError: warn('Nomor tidak valid')
    vals=dict(extra or {})
    for n in nums:
        m=visible[n-1]
        while True:
            try: vals[m['name']]=convert(m,input('Cari '+m['name']+' (NULL=IS NULL): ')); break
            except ValueError as exc: warn(str(exc))
    where,params=predicate(vals)
    names=[m['name'] for m in visible]
    records=rows(conn,f'SELECT TOP (100) {", ".join(qi(x) for x in names)} FROM {tn(t)} WHERE {where}',*params)
    show(records)
    if not records: raise Cancel()
    n=choose('Pilih record (0=batal)',{str(i) for i in range(len(records)+1)})
    if n=='0': raise Cancel()
    return records[int(n)-1]

def stable_key(conn,t,record):
    indexes=rows(conn,'''SELECT i.name AS index_name, c.name AS col, i.is_primary_key AS pk
        FROM sys.indexes i JOIN sys.index_columns ic ON i.object_id=ic.object_id AND i.index_id=ic.index_id
        JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id
        JOIN sys.tables tb ON tb.object_id=i.object_id
        WHERE tb.name=? AND SCHEMA_NAME(tb.schema_id)='dbo' AND i.is_unique=1
        AND i.is_disabled=0 AND i.has_filter=0 AND ic.is_included_column=0
        ORDER BY i.is_primary_key DESC,i.index_id,ic.key_ordinal''',t)
    groups={}
    for r in indexes: groups.setdefault(r['index_name'],[]).append(r['col'])
    for cols in groups.values():
        if all(c in record and record[c] is not None for c in cols): return {c:record[c] for c in cols}
    raise RuntimeError('Tidak ada primary/unique key yang bisa dipakai untuk UPDATE aman di '+t)

def backup(conn,tables):
    """SOP: commit snapshot SEBELUM transaksi perubahan; rollback DML tidak menghapusnya."""
    suffix=datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'_'+secrets.token_hex(3)
    names=[]
    conn.rollback(); conn.autocommit=False
    cur=conn.cursor()
    try:
        cur.execute('SET XACT_ABORT ON')
        for t in dict.fromkeys(tables):
            tn(t)
            name=t+'_Backup_'+suffix
            cur.execute(f'SELECT * INTO dbo.{qi(name)} FROM {tn(t)}')
            cur.execute("SELECT OBJECT_ID(?, 'U')",'dbo.'+name)
            if cur.fetchone()[0] is None: raise RuntimeError('Backup tidak terverifikasi: '+name)
            names.append('dbo.'+name)
        conn.commit()
        for n in names: info('BACKUP SEBELUM DML: '+n)
        return names
    except Exception:
        conn.rollback(); raise
    finally: cur.close()

def deploy_backup(tables):
    lines=["DECLARE @BackupSuffix VARCHAR(48)=CONVERT(CHAR(8),SYSDATETIME(),112)+'_'+REPLACE(CONVERT(CHAR(8),SYSDATETIME(),108),':','')+'_'+LEFT(REPLACE(CONVERT(VARCHAR(36),NEWID()),'-',''),8);",
           'DECLARE @BackupName SYSNAME,@BackupSql NVARCHAR(MAX);','BEGIN TRANSACTION;']
    for t in dict.fromkeys(tables):
        tn(t)
        lines.extend([f"SET @BackupName=N'{t}_Backup_'+@BackupSuffix;",
                      "IF OBJECT_ID(N'dbo.'+@BackupName,'U') IS NOT NULL THROW 51001,'Backup name collision',1;",
                      f"SET @BackupSql=N'SELECT * INTO dbo.'+QUOTENAME(@BackupName)+N' FROM {tn(t)}';",
                      'EXEC sys.sp_executesql @BackupSql;',
                      "IF OBJECT_ID(N'dbo.'+@BackupName,'U') IS NULL THROW 51002,'Backup failed',1;"])
    lines.append('COMMIT TRANSACTION;')
    return '\n'.join(lines)

def sql_insert(t,values,refs=None,password_var="DBPASS"):
    refs=refs or {}
    cols=list(values)+[k for k in refs if k not in values]
    expressions=[]
    for k in cols:
        if k in refs: expressions.append(refs[k]); continue
        if t=='ParamServer' and k=='DBPass':
            expressions.append("dbo.fnEncrypt(N'$("+password_var+")',"+lit(values['IPServer'])+"+N'BR!')")
        else: expressions.append(lit(values[k]))
    return f'INSERT INTO {tn(t)} ({", ".join(map(qi,cols))}) VALUES ({", ".join(expressions)});\nIF @@ROWCOUNT<>1 THROW 51010,\'INSERT failed\',1;'

def sql_update(t,values,key):
    if not values: return '-- No changes'
    parts=[]
    for k,v in values.items():
        if t=='ParamServer' and k=='DBPass':
            ip=values.get('IPServer',key.get('IPServer'))
            parts.append("[DBPass]=dbo.fnEncrypt(N'$(DBPASS)',"+lit(ip)+"+N'BR!')")
        else: parts.append(qi(k)+'='+lit(v))
    where=' AND '.join(qi(k)+(' IS NULL' if v is None else '='+lit(v)) for k,v in key.items())
    return f'UPDATE {tn(t)} SET {", ".join(parts)} WHERE {where};\nIF @@ROWCOUNT<>1 THROW 51011,\'UPDATE must affect exactly one row\',1;'

def save_deploy(prefix,tables,statements,needs_password=False):
    OUTPUT.mkdir(parents=True,exist_ok=True)
    p=OUTPUT/(prefix+'_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.sql')
    header=('/* DATAFLOWPARAM — SOP DEPLOYMENT\n   Backup asli committed terpisah sebelum DML.\n   SELECT INTO bukan full database backup.\n   '+('Aktifkan SQLCMD mode dan berikan DBPASS dengan aman.' if needs_password else 'Tidak menggunakan variabel DBPASS.')+'\n*/\n')
    script=(header+f'USE [{DATABASE}];\nGO\nSET NOCOUNT ON;\nSET XACT_ABORT ON;\nBEGIN TRY\n'
            +deploy_backup(tables)+'\nBEGIN TRANSACTION;\n'+'\n'.join(statements)
            +'\nCOMMIT TRANSACTION;\nEND TRY\nBEGIN CATCH\nIF XACT_STATE()<>0 ROLLBACK TRANSACTION;\nTHROW;\nEND CATCH;\nGO\n')
    p.write_text(script,encoding='utf-8'); info('SQL deployment: '+str(p))

def apply(conn,t,action,values,key=None):
    cur=conn.cursor()
    try:
        if action=='INSERT':
            if not values: raise ValueError('INSERT tanpa kolom')
            cols=list(values); expressions=[]; params=[]
            for k in cols:
                if t=='ParamServer' and k=='DBPass':
                    expressions.append("dbo.fnEncrypt(?, ? + 'BR!')")
                    params.extend([values[k],values['IPServer']])
                else: expressions.append('?'); params.append(values[k])
            cur.execute(f'INSERT INTO {tn(t)} ({", ".join(map(qi,cols))}) VALUES ({", ".join(expressions)})',*params)
            if cur.rowcount!=1: raise RuntimeError('INSERT tidak tepat satu record')
            return
        if not key or not values: raise ValueError('UPDATE membutuhkan key dan perubahan')
        where,wp=predicate(key)
        cur.execute(f'SELECT COUNT_BIG(*) FROM {tn(t)} WITH (UPDLOCK,HOLDLOCK) WHERE {where}',*wp)
        if cur.fetchone()[0]!=1: raise RuntimeError('Target UPDATE tidak unik/berubah')
        sets=[];params=[]
        for k,v in values.items():
            if t=='ParamServer' and k=='DBPass':
                ip=values.get('IPServer',key.get('IPServer'))
                if ip is None: raise ValueError('IPServer diperlukan untuk DBPass')
                sets.append("[DBPass]=dbo.fnEncrypt(?, ? + 'BR!')");params.extend([v,ip])
            else: sets.append(qi(k)+'=?');params.append(v)
        cur.execute(f'UPDATE {tn(t)} SET {", ".join(sets)} WHERE {where}',*(params+wp))
        if cur.rowcount!=1: raise RuntimeError('UPDATE tidak tepat satu record')
    finally: cur.close()

def verify(conn,t,values,key=None):
    # Verifikasi kolom non-password. Password disimpan encrypted; tidak ditampilkan atau didecrypt ke hasil.
    target=dict(key or {});target.update({k:v for k,v in values.items() if k!='DBPass'})
    if not target: raise RuntimeError('Tidak ada filter verifikasi')
    where,params=predicate(target)
    count=rows(conn,f'SELECT COUNT_BIG(*) AS n FROM {tn(t)} WHERE {where}',*params)[0]['n']
    if count!=1: raise RuntimeError('Verifikasi data aktual gagal: '+t)

def single(conn,t,action):
    heading(f'[TAHAP 2/6] {action} dbo.{t}')
    old=select_record(conn,t) if action=='UPDATE' else None
    key=stable_key(conn,t,old) if old else None
    values=input_fields(conn,t,action=='UPDATE')
    if not values: info('Tidak ada kolom yang diubah');return
    if t=='ParamServer' and action=='UPDATE' and 'IPServer' in values and 'DBPass' not in values:
        raise ValueError('IPServer berubah: wajib isi DBPass baru untuk re-enkripsi.')
    if t=='ParamServer' and action=='INSERT' and not values.get('DBPass'):
        raise ValueError('DBPass wajib diisi untuk ParamServer baru.')
    heading('[TAHAP 4/6] PREVIEW (BELUM BACKUP)')
    if old: show([old])
    show([values])
    if not yes('BACKUP DATA ASLI + jalankan perubahan?'): return
    backup(conn,(t,))
    try:
        conn.autocommit=False
        apply(conn,t,action,values,key)
        if action=='UPDATE': verify(conn,t,values,key)
        elif t=='ParamServer': verify(conn,t,{k:v for k,v in values.items() if k!='DBPass'})
        heading('[TAHAP 6/6] KONFIRMASI TRANSAKSI')
        if not yes('COMMIT perubahan? (0=ROLLBACK)'):
            conn.rollback();info('ROLLBACK DML. Backup tetap tersedia.');return
        conn.commit();info('COMMIT berhasil.')
    except Exception:
        conn.rollback();raise
    finally: conn.autocommit=True
    statement=sql_insert(t,values) if action=='INSERT' else sql_update(t,values,key)
    if t=='ParamServer' and action=='INSERT':
        statement=(f"IF EXISTS(SELECT 1 FROM dbo.ParamServer WHERE IPServer={lit(values['IPServer'])} AND DBUser={lit(values['DBUser'])}) THROW 51030,'Duplicate ParamServer',1;\n"+statement)
    try: save_deploy(t+'_'+action,(t,),[statement],t=='ParamServer' and 'DBPass' in values)
    except OSError as exc: warn('COMMIT berhasil, gagal menulis deployment: '+str(exc))

def insert_chain(conn):
    heading('INSERT BERANTAI — ParamServer > ParamFitur > CekLogActivity')
    roles={};pending={}
    for role in ('source','destination','log'):
        heading('SERVER '+role.upper())
        print('1. Pilih ParamServer lama\n2. Buat ParamServer baru')
        opt=choose('Pilihan',{'1','2'})
        if opt=='1':
            rec=select_record(conn,'ParamServer')
            if 'IdServer' not in rec: raise RuntimeError('IdServer tidak ada dalam hasil pencarian.')
            roles[role]=('old',rec)
        else:
            val=input_fields(conn,'ParamServer')
            if not all(val.get(k) for k in ('IPServer','DBUser','DBPass')): raise ValueError('IPServer, DBUser, DBPass wajib.')
            nk=(val['IPServer'],val['DBUser'])
            if nk not in pending:
                if rows(conn,'SELECT COUNT_BIG(*) AS n FROM dbo.ParamServer WHERE IPServer=? AND DBUser=?',*nk)[0]['n']:
                    raise ValueError('Server sudah ada, pilih record lama.')
                pending[nk]=val
            roles[role]=('new',pending[nk])
    feature=input_fields(conn,'ParamFitur',exclude=RELATIONS['ParamFitur'])
    if not feature.get('FiturName'): raise ValueError('FiturName wajib diisi')
    with_log=yes('Buat ParamFiturCekLogActivity?')
    log=input_fields(conn,'ParamFiturCekLogActivity',exclude=RELATIONS['ParamFiturCekLogActivity']) if with_log else {}
    heading('[TAHAP 4/6] PREVIEW INSERT BERANTAI')
    for role,(mode,val) in roles.items(): print(role,mode,{k:hidden(k,v) for k,v in val.items()})
    show([feature]);
    if with_log: show([log])
    if not yes('BACKUP ketiga tabel + jalankan INSERT?'): return
    backup(conn,TABLES)
    statements=[];needs_password=bool(pending)
    try:
        conn.autocommit=False
        ids={};created={}
        for role,(mode,val) in roles.items():
            if mode=='old':
                sid=int(val['IdServer'])
                if rows(conn,'SELECT COUNT_BIG(*) AS n FROM dbo.ParamServer WHERE IdServer=?',sid)[0]['n']!=1: raise RuntimeError('Server lama tidak ditemukan')
            else:
                nk=(val['IPServer'],val['DBUser'])
                if nk in created: sid=created[nk]
                else:
                    apply(conn,'ParamServer','INSERT',val)
                    found=rows(conn,'SELECT IdServer FROM dbo.ParamServer WHERE IPServer=? AND DBUser=?',*nk)
                    if len(found)!=1: raise RuntimeError('IdServer baru tidak unik')
                    sid=int(found[0]['IdServer']);created[nk]=sid
            ids[role]=sid
        feature.update({k:ids[r] for k,r in RELATIONS['ParamFitur'].items()})
        cur=conn.cursor()
        cols=list(feature)
        cur.execute(f'INSERT INTO dbo.ParamFitur ({", ".join(map(qi,cols))}) OUTPUT INSERTED.IDFitur VALUES ({", ".join("?" for _ in cols)})',*[feature[k] for k in cols])
        fid=cur.fetchone()[0];cur.close()
        if with_log:
            log.update({'IDFitur':fid,'IPServerLogActivityId':ids['log']})
            apply(conn,'ParamFiturCekLogActivity','INSERT',log)
        heading('[TAHAP 6/6] VERIFIKASI INSERT BERANTAI')
        verify(conn,'ParamFitur',{'IDFitur':fid})
        if with_log: verify(conn,'ParamFiturCekLogActivity',log)
        info('IDFitur baru: '+str(fid))
        if not yes('COMMIT seluruh INSERT berantai?'):
            conn.rollback();info('ROLLBACK DML, backup tetap ada');return
        conn.commit();info('COMMIT berhasil.')
    except Exception:
        conn.rollback();raise
    finally: conn.autocommit=True
    # SQL deployment resolve ID secara dinamis; tidak memakai identity dari DB sumber.
    statements=['DECLARE @SourceId INT,@DestinationId INT,@LogId INT,@FiturId INT;']
    seen=set();password_index=0
    for role,var in (('source','@SourceId'),('destination','@DestinationId'),('log','@LogId')):
        mode,val=roles[role];nk=(val['IPServer'],val['DBUser'])
        keysql=f'IPServer={lit(nk[0])} AND DBUser={lit(nk[1])}'
        if mode=='new' and nk not in seen:
            statements.append(f"IF EXISTS(SELECT 1 FROM dbo.ParamServer WHERE {keysql}) THROW 51020,'ParamServer already exists',1;")
            password_index+=1
            statements.append(sql_insert('ParamServer',val,password_var='DBPASS_'+str(password_index)));seen.add(nk)
        statements.append(f'SELECT {var}=MIN(IdServer) FROM dbo.ParamServer WHERE {keysql};')
        statements.append(f"IF (SELECT COUNT_BIG(*) FROM dbo.ParamServer WHERE {keysql})<>1 THROW 51021,'Server key not unique',1;")
    vals={k:v for k,v in feature.items() if k not in RELATIONS['ParamFitur']}
    cols=list(vals)+list(RELATIONS['ParamFitur'])
    expressions=[lit(v) for v in vals.values()]+['@SourceId','@DestinationId','@LogId']
    statements.append('DECLARE @InsertedFitur TABLE (IDFitur INT);')
    statements.append(f'INSERT INTO dbo.ParamFitur ({", ".join(map(qi,cols))}) OUTPUT INSERTED.IDFitur INTO @InsertedFitur VALUES ({", ".join(expressions)});')
    statements.append('SELECT @FiturId=IDFitur FROM @InsertedFitur;')
    statements.append("IF @FiturId IS NULL THROW 51022,'Fitur insert failed',1;")
    if with_log:
        lvals={k:v for k,v in log.items() if k not in RELATIONS['ParamFiturCekLogActivity']}
        statements.append(sql_insert('ParamFiturCekLogActivity',lvals,{'IDFitur':'@FiturId','IPServerLogActivityId':'@LogId'}))
    if needs_password: info('Deployment chain memerlukan SQLCMD DBPASS_1 s.d. DBPASS_'+str(password_index)+' (satu per server baru).')
    try: save_deploy('CHAIN_INSERT',TABLES,statements,needs_password)
    except OSError as exc: warn('COMMIT berhasil, SQL gagal disimpan: '+str(exc))

def update_chain(conn):
    heading('UPDATE BERANTAI — ParamFitur + CekLogActivity')
    feature=select_record(conn,'ParamFitur')
    fkey=stable_key(conn,'ParamFitur',feature)
    changes=input_fields(conn,'ParamFitur',update=True)
    ops=[]
    if changes: ops.append(('ParamFitur',changes,fkey))
    if yes('Update record log terkait?'):
        logs=rows(conn,'SELECT COUNT_BIG(*) AS n FROM dbo.ParamFiturCekLogActivity WHERE IDFitur=?',feature['IDFitur'])
        if logs[0]['n']:
            old=select_record(conn,'ParamFiturCekLogActivity',{'IDFitur':feature['IDFitur']})
            key=stable_key(conn,'ParamFiturCekLogActivity',old)
            upd=input_fields(conn,'ParamFiturCekLogActivity',update=True,exclude={'IDFitur'})
            if upd: ops.append(('ParamFiturCekLogActivity',upd,key))
        else: info('Tidak ada record log terkait.')
    if not ops: info('Tidak ada perubahan.');return
    heading('[TAHAP 4/6] PREVIEW UPDATE BERANTAI')
    for t,vals,key in ops: print(t,'KEY:',key);show([vals])
    if not yes('BACKUP tabel terkait + jalankan UPDATE?'): return
    tables=tuple(dict.fromkeys(t for t,_,_ in ops))
    backup(conn,tables)
    try:
        conn.autocommit=False
        for t,vals,key in ops:
            apply(conn,t,'UPDATE',vals,key)
            verify(conn,t,vals,key)
        if not yes('COMMIT seluruh UPDATE? (0=ROLLBACK)'):
            conn.rollback();info('ROLLBACK, backup tetap ada');return
        conn.commit();info('COMMIT berhasil.')
    except Exception:
        conn.rollback();raise
    finally: conn.autocommit=True
    try: save_deploy('CHAIN_UPDATE',tables,[sql_update(t,vals,key) for t,vals,key in ops])
    except OSError as exc: warn('COMMIT berhasil, SQL gagal disimpan: '+str(exc))

def run():
    heading('DATAFLOWPARAM — WIZARD INSERT/UPDATE + BACKUP SOP')
    conn=connect()
    try:
        while True:
            heading('MENU UTAMA')
            print('1. INSERT/UPDATE ParamServer\n2. INSERT/UPDATE ParamFitur')
            print('3. INSERT/UPDATE ParamFiturCekLogActivity')
            print('4. INSERT BERANTAI (3 tabel)\n5. UPDATE BERANTAI (Fitur + Log)\n0. KELUAR')
            try:
                opt=choose('Pilih',{'0','1','2','3','4','5'})
                if opt=='0': break
                if opt=='4': insert_chain(conn)
                elif opt=='5': update_chain(conn)
                else:
                    t=TABLES[int(opt)-1]
                    print('1. INSERT\n2. UPDATE\n0. KEMBALI')
                    action=choose('Pilih',{'0','1','2'})
                    if action!='0': single(conn,t,'INSERT' if action=='1' else 'UPDATE')
            except Cancel: info('Kembali ke menu utama.')
            except Exception as exc:
                try: conn.rollback()
                except Exception: pass
                print('[ERROR]',exc,'\n[INFO] DML yang belum COMMIT di-ROLLBACK; backup committed tetap tersedia.')
    finally:
        try: conn.rollback()
        except Exception: pass
        conn.close()
    info('Keluar dari wizard.')

if __name__=='__main__':
    try: run()
    except (Cancel,KeyboardInterrupt,EOFError): print('\n[INFO] Wizard dihentikan.')
    except Exception as exc: print('[ERROR]',exc);sys.exit(1)
