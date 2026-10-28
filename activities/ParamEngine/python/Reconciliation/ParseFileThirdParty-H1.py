"""ParamEngine ParseFileThirdParty-H1: two-table transactional CLI wizard."""
import sys
import re
from pathlib import Path
from datetime import datetime

def find_project_root(start: Path) -> Path:
    """Cari root project dari lokasi script, seperti wizard Settlement."""
    for parent in start.resolve().parents:
        if (parent / 'db_config.py').is_file() and (parent / 'db_connection.py').is_file():
            return parent
    raise ModuleNotFoundError(
        'Tidak menemukan db_config.py dan db_connection.py di folder induk. '
        'Pastikan keduanya ada di root project Synqra-1.0.'
    )

ROOT = find_project_root(Path(__file__))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
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

    print('\n' + '=' * 60)
    print('  PILIH KONEKSI DATABASE')
    print('=' * 60)
    print('  [1] Server 102  | 172.18.246.102')
    print('  [2] Lokal       | localhost')
    print('-' * 60)
    while True:
        selected = input('Pilih koneksi [1/2]: ').strip()
        if selected in choices:
            SERVER_KEY, cfg, label = choices[selected]
            host = value(cfg, 'host', '?')
            print(f'\n✓ Koneksi dipilih: {label} | {host}\n')
            return cfg
        if selected in {'1', '2'}:
            print('Profil yang dipilih tidak ditemukan di db_config.py. Periksa isi SERVERS.')
        else:
            print('⚠ Pilihan tidak valid. Masukkan 1 atau 2.')

SERVER_KEY='4'  # konfigurasi khusus 172.18.246.102
TARGET_HOST='172.18.246.102'  # server tetap untuk ParamEngine
DB='ParamEngine'
ACTIVITY='ParseFileThirdParty-H1'
OUT=Path(__file__).resolve().parent.parent/'output'/ACTIVITY
TABLES={'1':'ParamParseFile','2':'ParamParseFileMappingColumn'}
PARSE=['ProductId','Task','Activity','LocalPath','Filename','TargetDB','TargetTable','FieldFilename','FieldFiledate','LogActivityFilenameDateAdd','IsFixedCol','Delimiter','HeaderRowSkip','FooterRowSkip','TextQualifier','isActive','Note','CheckSum','FormatInterface']
MAPPING=['ProductId','Task','Activity','Col','FieldTargetName','FixedColSubstring']
FIELDS={'ParamParseFile':PARSE,'ParamParseFileMappingColumn':MAPPING}
KEYS={'ParamParseFile':['ProductId','Task','Activity'],'ParamParseFileMappingColumn':['ProductId','Task','Activity','Col']}
NUMERIC={'LogActivityFilenameDateAdd','IsFixedCol','HeaderRowSkip','FooterRowSkip','isActive','Col'}
REQUIRED={'ProductId','Task','Activity','LocalPath','Filename','TargetDB','TargetTable','FieldTargetName','Col','FormatInterface'}
DEFAULTS={'Activity':ACTIVITY,'LogActivityFilenameDateAdd':0,'IsFixedCol':0,'Delimiter':',','HeaderRowSkip':1,'FooterRowSkip':0,'isActive':1,'TextQualifier':'','Note':'','CheckSum':'{"RowPosition": "footer", "RowIndex": "0", "ColIndex": "0", "SubstringCol":"0,0"}','FormatInterface':'delimiter','FixedColSubstring':''}
SAMPLE_MAP=['TransactionID','PartnerTransactionID','ProductID','ProductCode','IDPEL','AyopopPrice','Amount','SharingFee','ProcessingFee','Status','Token','ResponseCode','RemainingBalance','InitialPaymentRequestAmount','InquiryID','FundholderID','CreatedAt','UpdatedAt']

def ident(x): return '['+x.replace(']',']]')+']'
def lit(v):
    if v is None: return 'NULL'
    if isinstance(v,int): return str(v)
    return "N'"+str(v).replace("'","''")+"'"
def prompt(s, default=None):
    """Input rapi: Enter memakai default, .NULL untuk SQL NULL, .EMPTY untuk string kosong."""
    d = '' if default is None else str(default)
    hint = (' [' + d + ']') if len(d) < 75 and default is not None else (' [default panjang tersedia]' if default is not None else '')
    value = input(f'  {s}{hint}: ')
    if value == '.NULL':
        return None
    if value == '.EMPTY':
        return ''
    if value == '' and default is not None:
        return default
    return value


def banner():
    print('\n' + '=' * 72)
    print('  SYNQRA | PARAMENGINE | PARSE FILE THIRD PARTY')
    print('  Konfigurasi ParamParseFile & ParamParseFileMappingColumn')
    print('=' * 72)
    print('  Database : ParamEngine')
    print(f'  Activity : {ACTIVITY}')
    print('  Alur     : Pilih server -> input -> preview -> backup -> verifikasi -> COMMIT')
    print('-' * 72)

def convert(col,v):
    if col in NUMERIC:
        if str(v).strip()=='' or not re.fullmatch(r'\d+',str(v).strip()): raise ValueError(f'{col} harus bilangan bulat >= 0')
        n=int(v)
        if col in {'isActive','IsFixedCol','LogActivityFilenameDateAdd'} and n not in (0,1): raise ValueError(f'{col} harus 0 atau 1')
        if col=='Col' and n<1: raise ValueError('Col harus >= 1')
        return n
    if col in REQUIRED and not str(v).strip(): raise ValueError(f'{col} wajib diisi')
    return str(v)

def choose_update_columns(table):
    options=[c for c in FIELDS[table] if c not in KEYS[table]]
    print('\nPilih kolom yang ingin diubah (boleh lebih dari satu):')
    for i,c in enumerate(options,1):
        print(f'  [{i:02}] {c}')
    nums=choose_numbers('Nomor kolom UPDATE, pisahkan koma (contoh 1,3,5): ',len(options))
    selected=[options[i-1] for i in nums]
    print('\nKolom yang akan diubah: '+', '.join(selected))
    return selected

def get_values(table,update=False,selected_cols=None):
    cols=FIELDS[table]
    if update:
        cols=selected_cols or choose_update_columns(table)
    elif table=='ParamParseFileMappingColumn':
        cols=[c for c in cols if c!='Activity']
    result={}
    for c in cols:
        v=prompt(c,DEFAULTS.get(c) if not update else None)
        result[c]=convert(c,v)
    if not update: result['Activity']=ACTIVITY
    return result

def choose_numbers(label,maximum):
    raw=input(label).strip()
    try:
        a=[int(x.strip()) for x in raw.split(',')]
        if not a or len(set(a))!=len(a) or any(x<1 or x>maximum for x in a): raise ValueError
        return a
    except ValueError: raise ValueError('Nomor pilihan tidak valid')

def where(keys):
    return ' AND '.join(f'{ident(k)} = ?' for k in keys),list(keys.values())

def rows(cur,table,keys,lock=False):
    w,p=where(keys)
    hint=' WITH (UPDLOCK, HOLDLOCK)' if lock else ''
    cur.execute(f'SELECT '+', '.join(ident(c) for c in FIELDS[table]+['InsertDate','LastModified'])+f' FROM dbo.{ident(table)}{hint} WHERE {w}',*p)
    return [tuple(r) for r in cur.fetchall()]

def show_fields(values, heading=None):
    """Cetak satu field per baris: ProductId = AYOCONECT."""
    if heading:
        print(f'\n--- {heading} ---')
    width = max((len(str(k)) for k in values), default=0)
    for column, value in values.items():
        display = 'NULL' if value is None else str(value)
        print(f'  {column:<{width}} = {display}')


def show(table, data, title):
    print(f'\n=== {title} | dbo.{table} ===')
    cols = FIELDS[table] + ['InsertDate', 'LastModified']
    if not data:
        print('Tidak ada data.')
        return
    for number, record in enumerate(data, 1):
        show_fields(dict(zip(cols, record)), f'RECORD {number}/{len(data)}')
    print(f'\nTotal record: {len(data)}')

def backup(cfg,table):
    name=table+'_Backup_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    con=connect_sqlserver(cfg,DB)
    try:
        con.autocommit=True
        c=con.cursor()
        try:c.execute(f'SELECT * INTO dbo.{ident(name)} FROM dbo.{ident(table)}')
        finally:c.close()
    finally:con.close()
    print('✓ Backup berhasil dibuat:',name)
    return name

def insert_one(cur,table,data):
    key={k:data[k] for k in KEYS[table]}
    if rows(cur,table,key,True):raise ValueError('Record dengan identitas tersebut sudah ada. Gunakan UPDATE.')
    cols=FIELDS[table]
    cur.execute(f'INSERT INTO dbo.{ident(table)} ('+', '.join(ident(c) for c in cols)+', [InsertDate], [LastModified]) VALUES ('+', '.join('?' for _ in cols)+', GETDATE(), GETDATE())',*[data[c] for c in cols])
    if cur.rowcount not in (1,-1):raise RuntimeError('INSERT tidak memengaruhi satu record')
    return key

def update_one(cur,table,key,changes):
    if len(rows(cur,table,key,True))!=1:raise ValueError('UPDATE harus menunjuk tepat satu record')
    w,p=where(key)
    setters=', '.join(f'{ident(k)} = ?' for k in changes)
    cur.execute(f';WITH TargetRows AS (SELECT * FROM dbo.{ident(table)} WITH (UPDLOCK, HOLDLOCK) WHERE {w}) UPDATE TargetRows SET {setters}, [LastModified] = GETDATE()',*(list(changes.values())+p))
    if cur.rowcount not in (1,-1):raise RuntimeError('UPDATE tidak memengaruhi satu record')

def pick_key(cur,table):
    print('\nFilter UPDATE (pilih kolom identitas):')
    key={}
    for c in KEYS[table]:
        v=prompt(c,ACTIVITY if c=='Activity' else None)
        key[c]=convert(c,v)
    if key['Activity']!=ACTIVITY:raise ValueError('Activity harus '+ACTIVITY)
    old=rows(cur,table,key)
    show(table,old,'DATA SEBELUM UPDATE')
    if len(old)!=1:raise ValueError(f'Filter harus menghasilkan tepat satu record, ditemukan {len(old)}')
    return key

def sql_deployment(table,action,items):
    # Each item = (key, changes). No user-entered SQL expressions.
    stamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    decl=[]; statements=[]; verify=[]; final_select=[]
    for idx,(key,data) in enumerate(items,1):
        vars={}
        for c,v in {**key,**data}.items():
            vn=f'@P{idx}_{c}'
            typ='INT' if c in NUMERIC else 'NVARCHAR(MAX)'
            decl.append(f'DECLARE {vn} {typ} = {lit(v)};')
            vars[c]=vn
        wh=' AND '.join(f'{ident(c)} = {vars[c]}' for c in key)
        if action=='INSERT':
            cols=FIELDS[table]
            statements.append(f"IF EXISTS (SELECT 1 FROM dbo.{ident(table)} WITH (UPDLOCK, HOLDLOCK) WHERE {wh})\n    THROW 52001, 'INSERT ditolak: record sudah ada.', 1;\nINSERT INTO dbo.{ident(table)} ("+', '.join(ident(c) for c in cols)+', [InsertDate], [LastModified])\nVALUES ('+', '.join(vars[c] for c in cols)+', GETDATE(), GETDATE());')
        else:
            assignments=', '.join(f'{ident(c)} = {vars[c]}' for c in data)
            statements.append(f"IF (SELECT COUNT(*) FROM dbo.{ident(table)} WITH (UPDLOCK, HOLDLOCK) WHERE {wh}) <> 1\n    THROW 52002, 'UPDATE membutuhkan tepat satu record.', 1;\n;WITH TargetRows AS (SELECT * FROM dbo.{ident(table)} WITH (UPDLOCK, HOLDLOCK) WHERE {wh})\nUPDATE TargetRows SET {assignments}, [LastModified] = GETDATE();")
        verify.append(f"IF (SELECT COUNT(*) FROM dbo.{ident(table)} WHERE {wh}) <> 1\n    THROW 52003, 'Verifikasi jumlah record gagal.', 1;\nSELECT "+', '.join(ident(c) for c in FIELDS[table]+['InsertDate','LastModified'])+f' FROM dbo.{ident(table)} WHERE {wh};')
        final_select.append('SELECT '+', '.join(ident(c) for c in FIELDS[table]+['InsertDate','LastModified'])+f' FROM dbo.{ident(table)} WHERE {wh};')
    backupname=table+'_Backup_'
    return f'''USE [{DB}];
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;
GO
/*==============================================================================
  {ACTIVITY.upper()} - {table.upper()} CONFIGURATION DEPLOYMENT
  Action: {action} | Generated: {stamp}
  SOP: 1 DECLARE/validasi 2 Backup 3 {action} 4 Verifikasi sementara
       5 COMMIT/ROLLBACK 6 SELECT hasil akhir.
  Default @ApproveCommit = 0 (ROLLBACK). Review sebelum production.
==============================================================================*/
/* TAHAP 1 - DECLARE PARAMETER DAN VALIDASI TARGET */
{chr(10).join(decl)}
DECLARE @ApproveCommit BIT = 0;
IF DB_NAME() <> N'{DB}' THROW 52000, 'Database target salah.', 1;

/* TAHAP 2 - BACKUP SEBELUM TRANSAKSI PERUBAHAN */
DECLARE @BackupName SYSNAME = N'{backupname}' +
    CONVERT(CHAR(8), GETDATE(), 112) + N'_' +
    REPLACE(CONVERT(VARCHAR(12), GETDATE(), 114), ':', '') + N'_' +
    RIGHT(REPLACE(CONVERT(VARCHAR(36), NEWID()), '-', ''), 8);
DECLARE @BackupSQL NVARCHAR(MAX) = N'SELECT * INTO dbo.' + QUOTENAME(@BackupName) + N' FROM dbo.{table};';
IF OBJECT_ID(N'dbo.' + @BackupName, N'U') IS NOT NULL THROW 52004, 'Backup sudah ada.', 1;
EXEC sys.sp_executesql @BackupSQL;
PRINT N'Backup: dbo.' + @BackupName;

/* TAHAP 3 - TRANSAKSI {action} */
BEGIN TRY
    BEGIN TRANSACTION;
{chr(10).join(statements)}

/* TAHAP 4 - SELECT VERIFIKASI SEBELUM COMMIT */
{chr(10).join(verify)}

/* TAHAP 5 - PERSETUJUAN COMMIT ATAU ROLLBACK */
    IF @ApproveCommit = 1
    BEGIN
        COMMIT TRANSACTION;
        PRINT N'COMMIT berhasil.';
    END
    ELSE
    BEGIN
        ROLLBACK TRANSACTION;
        PRINT N'ROLLBACK: perubahan tidak disimpan.';
    END;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;

/* TAHAP 6 - SELECT HASIL AKHIR DI DATABASE */
{chr(10).join(final_select)}
GO
'''

def process(cfg,table):
    print('\n' + '-' * 72)
    print(f'  TABEL TARGET : dbo.{table}')
    print('  [1] INSERT  - tambah konfigurasi baru')
    print('  [2] UPDATE  - ubah konfigurasi yang sudah ada')
    print('  [0] Kembali')
    print('-' * 72)
    opt=input('  Pilih proses [0-2]: ').strip()
    if opt=='0':return
    if opt not in ('1','2'):raise ValueError('Pilihan tidak valid')
    action='INSERT' if opt=='1' else 'UPDATE'
    con=connect_sqlserver(cfg,DB)
    con.autocommit=False
    committed=False
    items=[]
    try:
        cur=con.cursor()
        try:
            if action=='INSERT':
                count=1
                if table=='ParamParseFileMappingColumn':
                    count=int(prompt('Jumlah mapping column yang ingin diisi',1))
                    if not 1<=count<=1000:raise ValueError('Jumlah mapping harus 1..1000')
                    print('Isi mapping manual. Activity otomatis:',ACTIVITY)
                for i in range(count):
                    print(f'\nINPUT RECORD {i+1}/{count}')
                    data=get_values(table)
                    key={k:data[k] for k in KEYS[table]}
                    if any(k==key for k,_ in items):raise ValueError('Duplikat identitas dalam batch input')
                    items.append((key,data))
            else:
                selected_cols=choose_update_columns(table)
                key=pick_key(cur,table)
                data=get_values(table,True,selected_cols)
                items.append((key,data))
            print('\n' + '=' * 72)
            print(f'  PREVIEW {action} | dbo.{table}')
            print('  Periksa semua nilai sebelum melanjutkan.')
            print('=' * 72)
            for number, (key, data) in enumerate(items, 1):
                show_fields(key, f'RECORD {number}/{len(items)} - IDENTITAS')
                show_fields(data, 'NILAI YANG AKAN DISIMPAN')
            if input('\n  Buat backup dan jalankan transaksi? [y/N]: ').strip().lower()!='y':
                print('Dibatalkan oleh pengguna; tidak ada perubahan disimpan.')
                return
            con.rollback()  # lepaskan transaksi SELECT sebelum backup terpisah
            backup(cfg,table)
            for key,data in items:
                if action=='INSERT':insert_one(cur,table,data)
                else:update_one(cur,table,key,data)
            for key,_ in items:
                result=rows(cur,table,key)
                if len(result)!=1:raise RuntimeError('Verifikasi gagal: record tidak tepat satu')
                show(table,result,'SELECT HASIL SEMENTARA (BELUM COMMIT)')
            if input('\n  Ketik COMMIT untuk menyimpan permanen (selain itu ROLLBACK): ').strip()!='COMMIT':
                con.rollback();print('↩ ROLLBACK berhasil. Perubahan tidak disimpan.');return
            con.commit();committed=True
            print('✓ COMMIT berhasil. Perubahan tersimpan.')
        finally:cur.close()
    except BaseException:
        if not committed:con.rollback()
        raise
    finally:con.close()
    OUT.mkdir(parents=True,exist_ok=True)
    path=OUT/f'{ACTIVITY}_{table}_{action}_{datetime.now():%Y-%m-%d_%H%M%S_%f}.sql'
    path.write_text(sql_deployment(table,action,items),encoding='utf-8')
    try:path.chmod(0o600)
    except OSError:pass
    print('✓ SQL deployment tersimpan:',path)

def target_config():
    """Gunakan profil server 102 dengan kredensial tersendiri."""
    cfg = choose_activity_server(SERVERS)
    host = getattr(cfg, 'host', getattr(cfg, 'server', 'server terpilih'))
    port = getattr(cfg, 'port', '')
    username = getattr(cfg, 'username', getattr(cfg, 'user', ''))
    print(f'\n  TARGET PARAMENGINE : {host}' + (f':{port}' if port else ''))
    print(f'  LOGIN              : {username} | Profil: {SERVER_KEY}')
    try:
        con = connect_sqlserver(cfg, 'master')
        try:
            cur = con.cursor()
            try:
                cur.execute("SELECT DB_ID(N'ParamEngine'), HAS_DBACCESS(N'ParamEngine')")
                dbid, access = cur.fetchone()
            finally:
                cur.close()
        finally:
            con.close()
        if dbid is None or access != 1:
            raise RuntimeError(f'Database ParamEngine tidak dapat diakses (DB_ID={dbid}, akses={access}).')
        con = connect_sqlserver(cfg, DB)
        try:
            cur = con.cursor()
            try:
                cur.execute("SELECT OBJECT_ID(N'dbo.ParamParseFile',N'U'), OBJECT_ID(N'dbo.ParamParseFileMappingColumn',N'U')")
                if any(x is None for x in cur.fetchone()):
                    raise RuntimeError('Tabel ParamParseFile atau ParamParseFileMappingColumn tidak ditemukan.')
            finally:
                cur.close()
        finally:
            con.close()
    except Exception as exc:
        raise RuntimeError(f'Koneksi {TARGET_HOST} gagal: {exc}. Periksa username/password profil yang dipilih di db_config.py dan izin login.') from exc
    print('Koneksi database dan kedua tabel: OK')
    return cfg

def main():
    banner()
    cfg=target_config()
    while True:
        print('\n' + '=' * 72)
        print('  MENU UTAMA | PARAMENGINE')
        print('  [1] ParamParseFile')
        print('  [2] ParamParseFileMappingColumn')
        print('  [3] Proses kedua tabel secara berurutan')
        print('  [0] Keluar')
        print('=' * 72)
        choice=input('  Pilih menu [0-3]: ').strip()
        if choice=='0':
            print('Sampai jumpa. Tidak ada proses baru yang dijalankan.')
            break
        if choice not in ('1','2','3'):
            print('⚠ Pilihan tidak valid. Masukkan 0, 1, 2, atau 3.')
            continue
        selections=['1','2'] if choice=='3' else [choice]
        for selection in selections:
            try:process(cfg,TABLES[selection])
            except KeyboardInterrupt:print('\nDibatalkan. Transaksi di-rollback.');return
            except Exception as e:print(f'ERROR {type(e).__name__}: {e}')

if __name__=='__main__':main()
