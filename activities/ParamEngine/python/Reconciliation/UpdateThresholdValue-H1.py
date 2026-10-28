# Wizard ParamEngine: konfigurasi INSERT/UPDATE dengan backup dan deployment SQL.
import sys
from pathlib import Path
from datetime import datetime
ROOT=Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
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

SERVER_KEY='4'
HOST='172.18.246.102'
DB='ParamEngine'
TABLE='ParamSPExecutor'
ACTIVITY='UpdateThresholdValue-H1'
COLUMNS=['ProductId', 'Task', 'Activity', 'Description', 'OrderExecute', 'SourceDatabase', 'StoredProcedureName', 'LogActivityDateAdd', 'isActive', 'SourceServerId']
NUMERIC=set(['OrderExecute', 'LogActivityDateAdd', 'isActive', 'SourceServerId'])
KEYS=['ProductId','Task','Activity','OrderExecute']
DEFAULTS={1: {'Description': 'Update Threshold Value on Automation Resolution', 'SourceDatabase': 'ReconciliationDBName', 'StoredProcedureName': "sp_UpdateThresholdAutomationResolution 'AYOCONECT-TVKABEL', '{%Y-%m-%d}'", 'LogActivityDateAdd': 0, 'isActive': 1, 'SourceServerId': 0}}
ORDERS=[1]
OUT=Path(__file__).resolve().parent.parent/'output'/ACTIVITY

def ident(s): return '['+s.replace(']',']]')+']'
def literal(v):
    if v is None:return 'NULL'
    if isinstance(v,int):return str(v)
    return "N'"+str(v).replace("'","''")+"'"
def ask(label,default=None):
    suffix=f' [{default}]' if default is not None and len(str(default))<65 else ''
    v=input(f'{label}{suffix}: ')
    return default if not v and default is not None else v
def number(c,v):
    if c in NUMERIC:
        v=int(v)
        if c in {'isActive','Source1isMoveDataMatch','Source2isMoveDataMatch','LogActivityDateAdd'} and v not in (0,1):raise ValueError(c+' harus 0 atau 1')
        if c=='OrderExecute' and v<1:raise ValueError('OrderExecute harus positif')
    return v
def show(title,data):
    print('\n=== '+title+' ===')
    width=max(map(len,data)) if data else 10
    for k,v in data.items():
        lines=str(v if v is not None else 'NULL').splitlines() or ['']
        print(f'{k:<{width}} = {lines[0]}')
        for line in lines[1:]:print(' '*(width+3)+line)
def key_for(v):return {k:v[k] for k in KEYS}
def where(keys):return ' AND '.join(ident(k)+' = ?' for k in keys),list(keys.values())
def fetch(cur,keys,lock=False):
    w,p=where(keys)
    cols=COLUMNS+['InsertDate','LastModified']
    cur.execute(f'SELECT {", ".join(map(ident,cols))} FROM dbo.{ident(TABLE)}'+(' WITH (UPDLOCK, HOLDLOCK)' if lock else '')+f' WHERE {w}',*p)
    return [dict(zip(cols,r)) for r in cur.fetchall()]
def choose_update_target(cur):
    """Cari record UPDATE berdasarkan satu atau beberapa kolom pilihan pengguna."""
    print('\nKolom yang bisa dipakai sebagai filter:')
    for i, col in enumerate(COLUMNS, 1):
        print(f' {i:2}. {col}')
    raw = input('Nomor kolom filter (pisah koma, contoh 1,3,5): ').strip()
    try:
        indexes = [int(x.strip()) for x in raw.split(',')]
        if not indexes or len(indexes) != len(set(indexes)) or any(i < 1 or i > len(COLUMNS) for i in indexes):
            raise ValueError()
    except ValueError:
        raise ValueError('Pilihan kolom filter tidak valid')
    filters = {}
    for i in indexes:
        col = COLUMNS[i-1]
        filters[col] = number(col, ask('Filter ' + col))
    w, params = where(filters)
    cur.execute(f'SELECT {", ".join(map(ident, COLUMNS))} FROM dbo.{ident(TABLE)} WHERE {w}', *params)
    rows = [dict(zip(COLUMNS, r)) for r in cur.fetchall()]
    if not rows:
        raise ValueError('Tidak ada record yang cocok dengan filter')
    if len(rows) > 1:
        print(f'\nDitemukan {len(rows)} record. Pilih record yang akan di-update:')
        for i, row in enumerate(rows, 1):
            print(f" {i}. " + ' | '.join(f'{k}={row.get(k)}' for k in KEYS))
        try:
            selected = int(input('Nomor record: ').strip())
            if selected < 1 or selected > len(rows): raise ValueError()
        except ValueError:
            raise ValueError('Nomor record tidak valid')
        row = rows[selected-1]
    else:
        row = rows[0]
    return key_for(row), row

def backup(cfg):
    name=TABLE+'_Backup_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    c=connect_sqlserver(cfg,DB)
    try:
        c.autocommit=True
        cur=c.cursor()
        try:cur.execute(f'SELECT * INTO dbo.{ident(name)} FROM dbo.{ident(TABLE)}')
        finally:cur.close()
    finally:c.close()
    print('Backup:',name)
    return name
def insert(cur,v):
    key=key_for(v)
    if fetch(cur,key,True):raise ValueError(f'Record OrderExecute {key["OrderExecute"]} sudah ada')
    sql=f'INSERT INTO dbo.{ident(TABLE)} ('+', '.join(map(ident,COLUMNS))+', [InsertDate], [LastModified]) VALUES ('+', '.join('?' for _ in COLUMNS)+', GETDATE(), GETDATE())'
    cur.execute(sql,*[v[k] for k in COLUMNS])
    if cur.rowcount not in (1,-1):raise RuntimeError('INSERT gagal')
def update(cur,key,changes):
    if len(fetch(cur,key,True))!=1:raise ValueError('UPDATE harus tepat satu record')
    w,p=where(key)
    setters=', '.join(ident(k)+' = ?' for k in changes)
    cur.execute(f';WITH T AS (SELECT * FROM dbo.{ident(TABLE)} WITH (UPDLOCK,HOLDLOCK) WHERE {w}) UPDATE T SET {setters}, [LastModified] = GETDATE()',*(list(changes.values())+p))
    if cur.rowcount not in (1,-1):raise RuntimeError('UPDATE gagal')
def input_insert(order,product,task):
    defaults=DEFAULTS.get(order,{})
    data={k:(0 if k in NUMERIC else '') for k in COLUMNS}
    data.update({k:(v.replace('AYOCONECT-TVKABEL',task) if isinstance(v,str) else v) for k,v in defaults.items()})
    data.update(ProductId=product,Task=task,Activity=ACTIVITY,OrderExecute=order)
    print(f'\nOrderExecute {order}: {data.get("Description", "")}')
    print('1. Pakai template dan edit field tertentu\n2. Input seluruh field')
    mode=ask('Pilihan','1')
    editable=[k for k in COLUMNS if k not in KEYS]
    if mode=='1':
        print('Field yang terisi template:')
        for k in editable:
            if data[k] not in ('',0):print(f'  {k} = {data[k]}')
        if ask('Edit field? (y/n)','n').lower()=='y':
            for i,k in enumerate(editable,1):print(f'{i}. {k}')
            nums=[int(x.strip()) for x in input('Nomor field, pisah koma: ').split(',')]
            if not nums or len(nums)!=len(set(nums)) or any(n<1 or n>len(editable) for n in nums):raise ValueError('Pilihan field salah')
            editable=[editable[n-1] for n in nums]
        else:editable=[]
    elif mode!='2':raise ValueError('Pilihan salah')
    for k in editable:data[k]=number(k,ask(k,data[k]))
    return data
def choose_changes():
    opts=list(COLUMNS)  # Semua kolom termasuk ProductId/Task/Activity/OrderExecute dapat diubah.
    for i,k in enumerate(opts,1):print(f'{i}. {k}')
    raw=input('Nomor field UPDATE, pisah koma: ')
    nums=[int(x.strip()) for x in raw.split(',')]
    if not nums or len(set(nums))!=len(nums) or any(n<1 or n>len(opts) for n in nums):raise ValueError('Nomor salah')
    return {opts[n-1]:number(opts[n-1],ask('Nilai baru '+opts[n-1])) for n in nums}
def deployment(action,items):
    decl=[];mut=[];checks=[];final=[]
    for i,(key,data) in enumerate(items,1):
        old_names={k:f'@OLD{i}_{k}' for k in key}
        merged=dict(key);merged.update(data)
        names={k:f'@V{i}_{k}' for k in merged}
        decl += [f'DECLARE {old_names[k]} {"INT" if k in NUMERIC else "NVARCHAR(MAX)"} = {literal(v)};' for k,v in key.items()]
        decl += [f'DECLARE {names[k]} {"INT" if k in NUMERIC else "NVARCHAR(MAX)"} = {literal(v)};' for k,v in merged.items()]
        old_where=' AND '.join(f'{ident(k)} = {old_names[k]}' for k in key)
        new_key=dict(key)
        if action=='UPDATE':new_key.update({k:v for k,v in data.items() if k in KEYS})
        new_where=' AND '.join(f'{ident(k)} = {names[k] if action=="UPDATE" and k in data else old_names[k]}' for k in new_key)
        if action=='INSERT':
            cols=', '.join(map(ident,COLUMNS));vals=', '.join(names[k] for k in COLUMNS)
            mut.append(f"IF EXISTS (SELECT 1 FROM dbo.{ident(TABLE)} WITH (UPDLOCK,HOLDLOCK) WHERE {old_where}) THROW 53001, 'Record sudah ada', 1;\nINSERT INTO dbo.{ident(TABLE)} ({cols}, [InsertDate], [LastModified]) VALUES ({vals}, GETDATE(), GETDATE());\nIF @@ROWCOUNT <> 1 THROW 53002, 'INSERT gagal', 1;")
            new_where=old_where
        else:
            sets=', '.join(f'{ident(k)} = {names[k]}' for k in data)
            mut.append(f"IF (SELECT COUNT(*) FROM dbo.{ident(TABLE)} WITH (UPDLOCK,HOLDLOCK) WHERE {old_where}) <> 1 THROW 53003, 'UPDATE tidak tepat satu', 1;\nIF EXISTS (SELECT 1 FROM dbo.{ident(TABLE)} WITH (UPDLOCK,HOLDLOCK) WHERE {new_where} AND NOT ({old_where})) THROW 53006, 'Identitas baru sudah digunakan', 1;\n;WITH T AS (SELECT * FROM dbo.{ident(TABLE)} WITH (UPDLOCK,HOLDLOCK) WHERE {old_where}) UPDATE T SET {sets}, [LastModified] = GETDATE();\nIF @@ROWCOUNT <> 1 THROW 53004, 'UPDATE gagal', 1;")
        checks.append(f"IF (SELECT COUNT(*) FROM dbo.{ident(TABLE)} WHERE {new_where}) <> 1 THROW 53005, 'Verifikasi gagal', 1;\nSELECT * FROM dbo.{ident(TABLE)} WHERE {new_where};")
        final.append(f'SELECT * FROM dbo.{ident(TABLE)} WHERE {new_where};')
    return f'''USE [ParamEngine];
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;
GO
-- {ACTIVITY} | {action} | Generated {datetime.now():%Y-%m-%d %H:%M:%S}
-- Review sebelum deployment. Default ROLLBACK.
{chr(10).join(decl)}
DECLARE @ApproveCommit BIT = 0;
IF DB_NAME() <> N'ParamEngine' THROW 53010, 'Database salah', 1;
DECLARE @BackupName SYSNAME = N'{TABLE}_Backup_' + CONVERT(CHAR(8),GETDATE(),112) + N'_' + REPLACE(CONVERT(VARCHAR(12),GETDATE(),114),':','') + N'_' + RIGHT(REPLACE(CONVERT(VARCHAR(36),NEWID()),'-',''),8);
DECLARE @BackupSQL NVARCHAR(MAX) = N'SELECT * INTO dbo.' + QUOTENAME(@BackupName) + N' FROM dbo.{TABLE}';
EXEC sys.sp_executesql @BackupSQL;
PRINT N'Backup: ' + @BackupName;
BEGIN TRY
 BEGIN TRANSACTION;
{chr(10).join(mut)}
-- Verifikasi sebelum keputusan transaksi
{chr(10).join(checks)}
 IF @ApproveCommit = 1 BEGIN COMMIT TRANSACTION; PRINT N'COMMITTED'; END
 ELSE BEGIN ROLLBACK TRANSACTION; PRINT N'ROLLED BACK'; END
END TRY
BEGIN CATCH
 IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
 THROW;
END CATCH;
-- Hasil akhir
{chr(10).join(final)}
GO
'''

def main():
    cfg = choose_activity_server(SERVERS)
    print(f'\n{ACTIVITY} | {HOST} | {DB}.dbo.{TABLE}')
    con=connect_sqlserver(cfg,DB);con.autocommit=False
    try:
        cur=con.cursor()
        try:
            cur.execute('SELECT OBJECT_ID(?,?)',f'dbo.{TABLE}','U')
            if cur.fetchone()[0] is None:raise RuntimeError('Tabel tidak ditemukan')
            con.rollback()
            choice=ask('1. INSERT batch / 2. UPDATE / 0. Keluar','0')
            if choice=='0':return
            if choice not in ('1','2'):raise ValueError('Pilihan salah')
            action='INSERT' if choice=='1' else 'UPDATE'
            items=[]
            if action=='INSERT':
                product=ask('ProductId','AYOCONECT');task=ask('Task','AYOCONECT-TVKABEL')
                orders=ORDERS if ask('INSERT semua OrderExecute template? (y/n)','y').lower()=='y' else [int(x.strip()) for x in input('OrderExecute (pisah koma): ').split(',')]
                if len(set(orders))!=len(orders) or any(x<1 for x in orders):raise ValueError('OrderExecute duplikat/tidak valid')
                for order in orders:
                    data=input_insert(order,product,task)
                    items.append((key_for(data),data))
            else:
                key, old_record = choose_update_target(cur)
                show('DATA SEBELUM UPDATE', old_record)
                if ask('Lanjut? (y/n)','n').lower()!='y':return
                items.append((key,choose_changes()))
            for i,(key,data) in enumerate(items,1):show(f'PREVIEW {action} {i}/{len(items)}',data)
            if ask('Backup dan jalankan transaksi? (y/n)','n').lower()!='y':return
            con.rollback()
            backup(cfg)
            verify_keys=[]
            for key,data in items:
                verify_key=dict(key)
                if action=='UPDATE':
                    verify_key.update({k:v for k,v in data.items() if k in KEYS})
                    if verify_key != key and fetch(cur,verify_key):
                        raise ValueError('Identitas baru sudah digunakan record lain')
                    update(cur,key,data)
                else:
                    insert(cur,data)
                verify_keys.append(verify_key)
            for i,((key,data),verify_key) in enumerate(zip(items,verify_keys),1):
                result=fetch(cur,verify_key)
                if len(result)!=1:raise RuntimeError('Verifikasi record gagal setelah UPDATE')
                show(f'HASIL SEMENTARA {i}/{len(items)} (BELUM COMMIT)',result[0])
            if input('Ketik COMMIT untuk menyimpan, lainnya ROLLBACK: ').strip()!='COMMIT':
                con.rollback();print('ROLLBACK berhasil');return
            con.commit();print('COMMIT berhasil')
        except BaseException:
            con.rollback();raise
        finally:cur.close()
    finally:con.close()
    OUT.mkdir(parents=True,exist_ok=True)
    path=OUT/f'{ACTIVITY}_{action}_{datetime.now():%Y%m%d_%H%M%S_%f}.sql'
    path.write_text(deployment(action,items),encoding='utf-8')
    path.chmod(0o600)
    print('SQL deployment:',path)
if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:print('\nDibatalkan')
    except Exception as exc:print(f'ERROR {type(exc).__name__}: {exc}');raise
