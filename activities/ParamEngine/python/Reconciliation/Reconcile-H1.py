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
TABLE='ParamRecon'
ACTIVITY='Reconcile-H1'
COLUMNS=['ProductId', 'Task', 'Activity', 'OrderExecute', 'Description', 'Source1Table', 'Source2Table', 'Source1Where', 'Source2Where', 'Source1DataDateCol', 'Source2DataDateCol', 'Source1KeyJoinCol1', 'Source2KeyJoinCol1', 'Source1KeyJoinCol2', 'Source2KeyJoinCol2', 'Source1KeyJoinCol3', 'Source2KeyJoinCol3', 'Source1KeyJoinCol4', 'Source2KeyJoinCol4', 'Source1KeyJoinCol5', 'Source2KeyJoinCol5', 'Source1KeyJoinCol6', 'Source2KeyJoinCol6', 'Source1KeyJoinCol7', 'Source2KeyJoinCol7', 'Source1KeyJoinCol8', 'Source2KeyJoinCol8', 'Source1KeyJoinCol9', 'Source2KeyJoinCol9', 'Source1KeyJoinCol10', 'Source2KeyJoinCol10', 'Source1SelectCol', 'Source2SelectCol', 'Source1PartitionCol', 'Source2PartitionCol', 'Source1OrderCol', 'Source2OrderCol', 'Source1UpdateCol1', 'Source2UpdateData1', 'Source1UpdateCol2', 'Source2UpdateData2', 'Source1UpdateCol3', 'Source2UpdateData3', 'Source1UpdateCol4', 'Source2UpdateData4', 'Source1UpdateCol5', 'Source2UpdateData5', 'Source1UpdateCol6', 'Source2UpdateData6', 'Source1UpdateCol7', 'Source2UpdateData7', 'Source1UpdateCol8', 'Source2UpdateData8', 'Source1UpdateCol9', 'Source2UpdateData9', 'Source1UpdateCol10', 'Source2UpdateData10', 'Source2UpdateCol1', 'Source1UpdateData1', 'Source2UpdateCol2', 'Source1UpdateData2', 'Source2UpdateCol3', 'Source1UpdateData3', 'Source2UpdateCol4', 'Source1UpdateData4', 'Source2UpdateCol5', 'Source1UpdateData5', 'Source2UpdateCol6', 'Source1UpdateData6', 'Source2UpdateCol7', 'Source1UpdateData7', 'Source2UpdateCol8', 'Source1UpdateData8', 'Source2UpdateCol9', 'Source1UpdateData9', 'Source2UpdateCol10', 'Source1UpdateData10', 'Source1isMoveDataMatch', 'Source2isMoveDataMatch', 'Source1UniqueCol', 'Source2UniqueCol', 'Source1FlagMatchCol', 'Source2FlagMatchCol', 'Source1FieldSelectMove', 'Source2FieldSelectMove', 'Source1MoveTargetTable', 'Source2MoveTargetTable', 'isActive', 'ReconDB']
NUMERIC=set(['OrderExecute', 'isActive', 'Source1isMoveDataMatch', 'Source2isMoveDataMatch'])
KEYS=['ProductId','Task','Activity','OrderExecute']
DEFAULTS={1: {'isActive': 1, 'Source1isMoveDataMatch': 0, 'Source2isMoveDataMatch': 0, 'ReconDB': 'ReconciliationDBName', 'Source1DataDateCol': 'TransactionDate', 'Description': 'Update ReconciliationStart', 'Source1Table': 'MasterBRI', 'Source2Table': '', 'Source1Where': "FeatureId = 'AYOCONECT-TVKABEL'", 'Source2Where': '', 'Source1UpdateCol1': 'ReconciliationStart', 'Source2UpdateData1': 'GetDate()', 'Source1UpdateCol2': 'ReconType1', 'Source2UpdateData2': 'Third Party* vs BRI'}, 2: {'isActive': 1, 'Source1isMoveDataMatch': 0, 'Source2isMoveDataMatch': 0, 'ReconDB': 'ReconciliationDBName', 'Source1DataDateCol': 'TransactionDate', 'Description': 'Update ReconciliationStart', 'Source1Table': 'MasterThirdParty', 'Source2Table': '', 'Source1Where': "FeatureId = 'AYOCONECT-TVKABEL'", 'Source2Where': '', 'Source1UpdateCol1': 'ReconciliationStart', 'Source2UpdateData1': 'GetDate()', 'Source1UpdateCol2': 'ReconType1', 'Source2UpdateData2': 'Third Party* vs BRI'}, 3: {'isActive': 1, 'Source1isMoveDataMatch': 0, 'Source2isMoveDataMatch': 0, 'ReconDB': 'ReconciliationDBName', 'Source1DataDateCol': 'TransactionDate', 'Description': 'Recon MasterBRI vs MasterThirdParty', 'Source1Table': 'MasterBRI', 'Source2Table': 'MasterThirdParty', 'Source1Where': "FeatureId = 'AYOCONECT-TVKABEL'", 'Source2Where': '', 'Source2DataDateCol': 'TransactionDate', 'Source1KeyJoinCol1': 'ReconcileKey1', 'Source2KeyJoinCol1': 'ReconcileKey1', 'Source1KeyJoinCol2': 'ReconcileKey2', 'Source2KeyJoinCol2': 'ReconcileKey2', 'Source1KeyJoinCol3': 'ReconcileKey3', 'Source2KeyJoinCol3': 'ReconcileKey3', 'Source1KeyJoinCol4': 'TransactionDate', 'Source2KeyJoinCol4': 'TransactionDate', 'Source1KeyJoinCol5': 'ReconcileKey6', 'Source2KeyJoinCol5': 'ReconcileKey6', 'Source1PartitionCol': 'ReconcileKey1, ReconcileKey2, ReconcileKey3, TransactionDate, ReconcileKey6', 'Source2PartitionCol': 'ReconcileKey1, ReconcileKey2, ReconcileKey3, TransactionDate, ReconcileKey6', 'Source1OrderCol': 'TransactionTime', 'Source2OrderCol': 'TransactionTime', 'Source1UpdateCol1': 'ReconMatchObject1', 'Source2UpdateData1': 'MasterThirdParty', 'Source1UpdateCol2': 'ReconStatus1', 'Source2UpdateData2': 'Match', 'Source2UpdateCol1': 'ReconMatchObject1', 'Source1UpdateData1': 'MasterBRI', 'Source2UpdateCol2': 'ReconStatus1', 'Source1UpdateData2': 'Match', 'Source1UniqueCol': 'IDMasterBRI', 'Source2UniqueCol': 'IdMasterThirdParty', 'Source1FlagMatchCol': 'ReconMatchKey1', 'Source2FlagMatchCol': 'ReconMatchKey1'}, 4: {'isActive': 1, 'Source1isMoveDataMatch': 0, 'Source2isMoveDataMatch': 0, 'ReconDB': 'ReconciliationDBName', 'Source1DataDateCol': 'TransactionDate', 'Description': 'Recon MasterBRI vs MasterThirdParty', 'Source1Table': 'MasterBRI', 'Source2Table': 'MasterThirdParty', 'Source1Where': "FeatureId = 'AYOCONECT-TVKABEL'", 'Source2Where': "FeatureId = 'AYOCONECT-TVKABEL' AND (ReconcileKey3 is NULL or ReconcileKey3 = '')", 'Source2DataDateCol': 'TransactionDate', 'Source1KeyJoinCol1': 'ReconcileKey1', 'Source2KeyJoinCol1': 'ReconcileKey1', 'Source1KeyJoinCol2': 'ReconcileKey2', 'Source2KeyJoinCol2': 'ReconcileKey2', 'Source1KeyJoinCol3': 'TransactionDate', 'Source2KeyJoinCol3': 'TransactionDate', 'Source1KeyJoinCol4': 'ReconcileKey6', 'Source2KeyJoinCol4': 'ReconcileKey6', 'Source1PartitionCol': 'ReconcileKey1, ReconcileKey2, TransactionDate, ReconcileKey6', 'Source2PartitionCol': 'ReconcileKey1, ReconcileKey2, TransactionDate, ReconcileKey6', 'Source1OrderCol': 'TransactionTime', 'Source2OrderCol': 'TransactionTime', 'Source1UpdateCol1': 'ReconMatchObject1', 'Source2UpdateData1': 'MasterThirdParty', 'Source1UpdateCol2': 'ReconStatus1', 'Source2UpdateData2': 'Match', 'Source2UpdateCol1': 'ReconMatchObject1', 'Source1UpdateData1': 'MasterBRI', 'Source2UpdateCol2': 'ReconStatus1', 'Source1UpdateData2': 'Match', 'Source1UniqueCol': 'IDMasterBRI', 'Source2UniqueCol': 'IdMasterThirdParty', 'Source1FlagMatchCol': 'ReconMatchKey1', 'Source2FlagMatchCol': 'ReconMatchKey1'}, 5: {'isActive': 1, 'Source1isMoveDataMatch': 0, 'Source2isMoveDataMatch': 0, 'ReconDB': 'ReconciliationDBName', 'Source1DataDateCol': 'TransactionDate', 'Description': 'Update ReconStatus', 'Source1Table': 'MasterBRI', 'Source2Table': '', 'Source1Where': "FeatureId = 'AYOCONECT-TVKABEL' and ReconStatus1 is NULL", 'Source2Where': '', 'Source1UpdateCol1': 'ReconStatus1', 'Source2UpdateData1': 'Unmatch BRI'}, 6: {'isActive': 1, 'Source1isMoveDataMatch': 0, 'Source2isMoveDataMatch': 0, 'ReconDB': 'ReconciliationDBName', 'Source1DataDateCol': 'TransactionDate', 'Description': 'Update ReconStatus', 'Source1Table': 'MasterThirdParty', 'Source2Table': '', 'Source1Where': "FeatureId = 'AYOCONECT-TVKABEL' and ReconStatus1 is NULL", 'Source2Where': '', 'Source1UpdateCol1': 'ReconStatus1', 'Source2UpdateData1': 'Unmatch Third Party'}, 98: {'isActive': 1, 'Source1isMoveDataMatch': 0, 'Source2isMoveDataMatch': 0, 'ReconDB': 'ReconciliationDBName', 'Source1DataDateCol': 'TransactionDate', 'Description': 'Update ReconciliationEnd', 'Source1Table': 'MasterBRI', 'Source2Table': '', 'Source1Where': "FeatureId = 'AYOCONECT-TVKABEL'", 'Source2Where': '', 'Source1UpdateCol1': 'ReconciliationEnd', 'Source2UpdateData1': 'GetDate()'}, 99: {'isActive': 1, 'Source1isMoveDataMatch': 0, 'Source2isMoveDataMatch': 0, 'ReconDB': 'ReconciliationDBName', 'Source1DataDateCol': 'TransactionDate', 'Description': 'Update ReconciliationEnd', 'Source1Table': 'MasterThirdParty', 'Source2Table': '', 'Source1Where': "FeatureId = 'AYOCONECT-TVKABEL'", 'Source2Where': '', 'Source1UpdateCol1': 'ReconciliationEnd', 'Source2UpdateData1': 'GetDate()'}}
ORDERS=[1, 2, 3, 4, 5, 6, 98, 99]
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
    opts=[k for k in COLUMNS if k not in KEYS]
    for i,k in enumerate(opts,1):print(f'{i}. {k}')
    raw=input('Nomor field UPDATE, pisah koma: ')
    nums=[int(x.strip()) for x in raw.split(',')]
    if not nums or len(set(nums))!=len(nums) or any(n<1 or n>len(opts) for n in nums):raise ValueError('Nomor salah')
    return {opts[n-1]:number(opts[n-1],ask('Nilai baru '+opts[n-1])) for n in nums}
def deployment(action,items):
    decl=[];mut=[];checks=[];final=[]
    for i,(key,data) in enumerate(items,1):
        merged=dict(key);merged.update(data)
        names={k:f'@R{i}_{k}' for k in merged}
        decl += [f'DECLARE {names[k]} {"INT" if k in NUMERIC else "NVARCHAR(MAX)"} = {literal(v)};' for k,v in merged.items()]
        wh=' AND '.join(f'{ident(k)} = {names[k]}' for k in key)
        if action=='INSERT':
            cols=', '.join(map(ident,COLUMNS));values=', '.join(names[k] for k in COLUMNS)
            mut.append(f"IF EXISTS (SELECT 1 FROM dbo.{ident(TABLE)} WITH (UPDLOCK,HOLDLOCK) WHERE {wh}) THROW 53001, 'Record sudah ada', 1;\nINSERT INTO dbo.{ident(TABLE)} ({cols}, [InsertDate], [LastModified]) VALUES ({values}, GETDATE(), GETDATE());\nIF @@ROWCOUNT <> 1 THROW 53002, 'INSERT gagal', 1;")
        else:
            sets=', '.join(f'{ident(k)} = {names[k]}' for k in data)
            mut.append(f"IF (SELECT COUNT(*) FROM dbo.{ident(TABLE)} WITH (UPDLOCK,HOLDLOCK) WHERE {wh}) <> 1 THROW 53003, 'UPDATE tidak tepat satu', 1;\n;WITH T AS (SELECT * FROM dbo.{ident(TABLE)} WITH (UPDLOCK,HOLDLOCK) WHERE {wh}) UPDATE T SET {sets}, [LastModified] = GETDATE();\nIF @@ROWCOUNT <> 1 THROW 53004, 'UPDATE gagal', 1;")
        checks.append(f"IF (SELECT COUNT(*) FROM dbo.{ident(TABLE)} WHERE {wh}) <> 1 THROW 53005, 'Verifikasi gagal', 1;\nSELECT * FROM dbo.{ident(TABLE)} WHERE {wh};")
        final.append(f'SELECT * FROM dbo.{ident(TABLE)} WHERE {wh};')
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
            product=ask('ProductId','AYOCONECT');task=ask('Task','AYOCONECT-TVKABEL')
            items=[]
            if action=='INSERT':
                orders=ORDERS if ask('INSERT semua OrderExecute template? (y/n)','y').lower()=='y' else [int(x.strip()) for x in input('OrderExecute (pisah koma): ').split(',')]
                if len(set(orders))!=len(orders) or any(x<1 for x in orders):raise ValueError('OrderExecute duplikat/tidak valid')
                for order in orders:
                    data=input_insert(order,product,task)
                    items.append((key_for(data),data))
            else:
                order=int(ask('OrderExecute'))
                key={'ProductId':product,'Task':task,'Activity':ACTIVITY,'OrderExecute':order}
                found=fetch(cur,key)
                if len(found)!=1:raise ValueError(f'Ditemukan {len(found)} record; harus tepat satu')
                show('DATA SEBELUM UPDATE',found[0])
                if ask('Lanjut? (y/n)','n').lower()!='y':return
                items.append((key,choose_changes()))
            for i,(key,data) in enumerate(items,1):show(f'PREVIEW {action} {i}/{len(items)}',data)
            if ask('Backup dan jalankan transaksi? (y/n)','n').lower()!='y':return
            con.rollback()
            backup(cfg)
            for key,data in items:
                if action=='INSERT':insert(cur,data)
                else:update(cur,key,data)
            for i,(key,_) in enumerate(items,1):
                result=fetch(cur,key)
                if len(result)!=1:raise RuntimeError('Verifikasi record gagal')
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
