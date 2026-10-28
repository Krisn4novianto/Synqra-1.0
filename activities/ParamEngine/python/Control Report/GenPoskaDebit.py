"""Wizard GenPoskaDebit for ParamEngine Control Report."""
"""Shared transactional ParamEngine wizard for Control Report activities."""
import sys
from pathlib import Path
from datetime import datetime
# Locate project root from the actual script location, including nested folders.
HERE = Path(__file__).resolve()
ROOT = next((p for p in HERE.parents if (p / 'db_config.py').is_file() and
             (p / 'db_connection.py').is_file()), None)
if ROOT is None:
    raise RuntimeError('db_config.py dan db_connection.py tidak ditemukan di parent folder script. '
                       'Pastikan folder Control Report berada di dalam proyek Synqra-1.0.')
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from db_config import SERVERS
from db_connection import connect_sqlserver

DB = 'ParamEngine'
REMOTE_HOST = '172.18.246.102'


def _server_host(cfg):
    # Mendukung konfigurasi berupa dataclass maupun dictionary.
    if isinstance(cfg, dict):
        return str(cfg.get('host', cfg.get('server', cfg.get('hostname', ''))))
    return str(next((getattr(cfg, key) for key in ('host', 'server', 'hostname')
                     if getattr(cfg, key, None)), ''))


def choose_activity_server():
    """Pilih satu koneksi untuk seluruh operasi pada activity ini."""
    remote = None
    local = None
    for cfg in SERVERS.values():
        host = _server_host(cfg).lower().split(',')[0].split(':')[0]
        if host == REMOTE_HOST:
            remote = cfg
        elif host in ('localhost', '127.0.0.1', '::1', '.'):
            local = cfg

    if remote is None:
        raise RuntimeError(
            f'Konfigurasi Server 102 ({REMOTE_HOST}) tidak ditemukan di db_config.SERVERS.'
        )
    if local is None:
        raise RuntimeError(
            'Konfigurasi SQL Server lokal tidak ditemukan. Tambahkan host localhost '
            'atau 127.0.0.1 pada db_config.SERVERS.'
        )

    print('\n' + '=' * 72)
    print('  SYNQRA | PARAMENGINE | CONTROL REPORT')
    print('  Pilih koneksi database untuk activity ini')
    print('-' * 72)
    print(f'  [1] Server 102  | {REMOTE_HOST}')
    print(f'  [2] Lokal       | {_server_host(local)}')
    print('  [0] Keluar')
    print('=' * 72)
    while True:
        choice = input('Pilih koneksi [1/2]: ').strip()
        if choice == '1':
            print(f'\n  Koneksi dipilih : Server 102 | {_server_host(remote)}')
            return remote
        if choice == '2':
            print(f'\n  Koneksi dipilih : Lokal | {_server_host(local)}')
            return local
        if choice == '0':
            raise SystemExit('Activity dibatalkan pengguna.')
        print('Pilihan tidak valid. Masukkan 1 atau 2.')

def qi(s): return '['+s.replace(']',']]')+']'
def lit(v):
    if v is None:return 'NULL'
    if isinstance(v,int):return str(v)
    return "N'"+str(v).replace("'","''")+"'"
def ask(label,default=None):
    d='' if default is None else str(default)
    hint=(' ['+d+']') if len(d)<75 else ' [default panjang tersedia]'
    v=input(label+hint+': ')
    if v=='.NULL':return None
    if v=='.EMPTY':return ''
    return default if v=='' else v
def ask_required(label):
    while True:
        value=input(label+': ').strip()
        if value and value not in ('.NULL', '.EMPTY'):
            return value
        print(label+' wajib diisi manual dan tidak boleh kosong.')

def display(data,title):
    print('\n=== '+title+' ===')
    width=max(map(len,data))
    for k,v in data.items():
        lines=str('NULL' if v is None else v).splitlines() or ['']
        print(f'{k:<{width}} = {lines[0]}')
        for l in lines[1:]:print(' '*(width+3)+l)
def numeric(k,v,nums):
    if v is None:return None
    if k in nums:
        x=int(v)
        if k.lower() in ('isactive','issourcefromsp','isheader','logactivitydateadd','logactivityfilenamedateadd') and x not in (0,1):raise ValueError(k+' harus 0 atau 1')
        if k=='OrderExecute' and x<1:raise ValueError('OrderExecute harus positif')
        return x
    return v
def condition(keys):return ' AND '.join(qi(k)+' = ?' for k in keys),list(keys.values())
def fetch(cur,table,cols,keys,lock=False):
    w,p=condition(keys)
    cur.execute('SELECT '+', '.join(map(qi,cols+['InsertDate','LastModified']))+' FROM dbo.'+qi(table)+(' WITH (UPDLOCK,HOLDLOCK)' if lock else '')+' WHERE '+w,*p)
    return [dict(zip(cols+['InsertDate','LastModified'],r)) for r in cur.fetchall()]
def backup(cfg,table):
    name=table+'_Backup_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    c=connect_sqlserver(cfg,DB)
    try:
        c.autocommit=True
        cur=c.cursor();cur.execute('SELECT * INTO dbo.'+qi(name)+' FROM dbo.'+qi(table));cur.close()
    finally:c.close()
    return name
def deployment(table,activity,cols,keys,nums,action,items,out):
    lines=['USE [ParamEngine];','GO','SET XACT_ABORT ON;','DECLARE @ApproveCommit BIT = 0;','BEGIN TRY','  BEGIN TRAN;']
    for idx,(key,values) in enumerate(items,1):
        if action=='INSERT':
            allv={k:values[k] for k in cols}
            names={k:'@V'+str(idx)+'_'+str(n) for n,k in enumerate(cols,1)}
            for k,v in allv.items():lines.append('  DECLARE '+names[k]+' '+('INT' if k in nums else 'NVARCHAR(MAX)')+' = '+lit(v)+';')
            wh=' AND '.join(qi(k)+' = '+names[k] for k in keys)
            lines+=['  IF EXISTS (SELECT 1 FROM dbo.'+qi(table)+' WITH (UPDLOCK,HOLDLOCK) WHERE '+wh+') THROW 51000, '+chr(39)+'Duplikat identitas INSERT'+chr(39)+', 1;',
                    '  INSERT INTO dbo.'+qi(table)+' ('+', '.join(map(qi,cols))+', [InsertDate], [LastModified]) VALUES ('+', '.join(names[k] for k in cols)+', GETDATE(), GETDATE());']
        else:
            names={k:'@K'+str(idx)+'_'+str(n) for n,k in enumerate(keys,1)}
            for k,v in key.items():lines.append('  DECLARE '+names[k]+' '+('INT' if k in nums else 'NVARCHAR(MAX)')+' = '+lit(v)+';')
            wh=' AND '.join(qi(k)+' = '+names[k] for k in keys)
            lines.append('  IF (SELECT COUNT(*) FROM dbo.'+qi(table)+' WITH (UPDLOCK,HOLDLOCK) WHERE '+wh+') <> 1 THROW 51001, '+chr(39)+'Identitas UPDATE tidak unik'+chr(39)+', 1;')
            lines.append('  UPDATE dbo.'+qi(table)+' SET '+', '.join(qi(k)+' = '+lit(v) for k,v in values.items())+', [LastModified] = GETDATE() WHERE '+wh+';')
            new_key = dict(key); new_key.update({k: values[k] for k in keys if k in values})
            new_wh = ' AND '.join(qi(k)+' = '+lit(v) for k,v in new_key.items())
            lines.append('  IF (SELECT COUNT(*) FROM dbo.'+qi(table)+' WHERE '+new_wh+') <> 1 THROW 51002, '+chr(39)+'Verifikasi UPDATE gagal setelah perubahan identitas'+chr(39)+', 1;')
            lines.append('  SELECT * FROM dbo.'+qi(table)+' WHERE '+new_wh+';')
            continue
        lines.append('  SELECT * FROM dbo.'+qi(table)+' WHERE '+wh+';')
    lines+=['  IF @ApproveCommit = 1 COMMIT TRAN;','  ELSE BEGIN ROLLBACK TRAN; PRINT '+chr(39)+'ROLLBACK: ubah @ApproveCommit menjadi 1 setelah verifikasi'+chr(39)+'; END','END TRY','BEGIN CATCH','  IF @@TRANCOUNT > 0 ROLLBACK TRAN;','  THROW;','END CATCH;','GO']
    out.mkdir(parents=True,exist_ok=True)
    path=out/(activity+'_'+action+'_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.sql')
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return path
def run(config,script_file):
    table=config['table'];activity=config['activity'];cols=config['columns'];keys=config['keys'];nums=set(config.get('numeric',[]));defaults=config['defaults']
    # Pilih satu koneksi dari konfigurasi terpusat db_config.py.
    # Objek cfg yang sama dipakai untuk membaca, backup, INSERT/UPDATE,
    # dan verifikasi agar seluruh operasi activity konsisten pada server pilihan.
    cfg = choose_activity_server()
    host = _server_host(cfg)
    print('\\n' + '=' * 72)
    print('  SYNQRA | PARAMENGINE | CONTROL REPORT')
    print('-' * 72)
    print(f'  Activity : {activity}')
    print(f'  Target   : {DB}.dbo.{table}')
    print(f'  Server   : {host}')
    print('-' * 72)
    print('  [1] INSERT  - tambah konfigurasi')
    print('  [2] UPDATE  - pilih record dan kolom yang diubah')
    print('  [0] Keluar')
    print('=' * 72)
    action=ask('Pilih','1')
    if action=='0':return
    if action not in ('1','2'):raise ValueError('Pilihan salah')
    action='INSERT' if action=='1' else 'UPDATE'
    try:
        conn=connect_sqlserver(cfg,DB)
    except Exception as exc:
        print('\n' + '!' * 72)
        print('  KONEKSI SQL SERVER GAGAL')
        print('-' * 72)
        print(f'  Server   : {host}')
        print(f'  Database : {DB}')
        print(f'  Detail   : {exc}')
        print('\n  Login timeout biasanya berarti host/port tidak dapat dijangkau atau')
        print('  SQL Server tidak aktif. Periksa VPN/jaringan dan db_config.py.')
        retry=input('\nCoba pilih server/koneksi lain sekarang? [y/N]: ').strip().lower()
        if retry == 'y':
            try:
                cfg=choose_activity_server()
                host=_server_host(cfg)
                conn=connect_sqlserver(cfg,DB)
                print(f'Koneksi berhasil: {host} | {DB}')
            except Exception as retry_exc:
                print(f'Koneksi ulang gagal: {retry_exc}')
                print('Tidak ada perubahan database yang dilakukan.')
                return
        else:
            print('Tidak ada perubahan database yang dilakukan.')
            return
    try:
        cur=conn.cursor()
        # Confirm actual schema before touching data.
        cur.execute('SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=? AND TABLE_NAME=?','dbo',table)
        actual={r[0].lower() for r in cur.fetchall()}
        missing=[c for c in cols+['InsertDate','LastModified'] if c.lower() not in actual]
        if missing:raise RuntimeError('Kolom tabel tidak ditemukan: '+', '.join(missing))
        product = task = None
        count = 1
        if action == 'INSERT':
            product = ask_required('ProductId')
            task = ask_required('Task')
        if 'OrderExecute' in keys and action=='INSERT':
            count=int(ask('Jumlah tahap INSERT (bisa lebih dari template)',str(len(config.get('orders',[1])))))
            if count<1 or count>1000:raise ValueError('Jumlah tahap harus 1..1000')
        items=[];seen=set()
        for i in range(count):
            print('\n--- Record',i+1,'/',count,'---')
            if action=='INSERT':
                order=None
                if 'OrderExecute' in keys:
                    suggested=config.get('orders',[])
                    order=numeric('OrderExecute',ask('OrderExecute',suggested[i] if i<len(suggested) else i+1),nums)
                d=dict(defaults)
                if order is not None:d.update(config.get('order_defaults',{}).get(order,{}))
                d.update(ProductId=product,Task=task,Activity=activity)
                if order is not None:d['OrderExecute']=order
                edit=ask('Edit field dari template? (y/n)','n').lower()
                if edit=='y':
                    editable=[k for k in cols if k not in keys]
                    for n,k in enumerate(editable,1):print(f'{n:3}. {k} = {str(d.get(k))[:90]}')
                    selected=ask('Nomor field dipisah koma (atau ALL)','ALL')
                    chosen=editable if selected.upper()=='ALL' else [editable[int(n.strip())-1] for n in selected.split(',')]
                    for k in chosen:d[k]=numeric(k,ask(k,d.get(k,'')),nums)
                elif edit!='n':raise ValueError('Jawaban y/n')
                for k in cols:
                    if k not in d:d[k]=0 if k in nums else ''
                key={k:d[k] for k in keys}
                values=d
            else:
                # UPDATE: cari record dengan kombinasi kolom pilihan pengguna,
                # bukan meminta ProductId/Task/Activity satu per satu.
                searchable = cols + ['InsertDate', 'LastModified']
                print('\nKolom yang bisa dijadikan filter:')
                for n, col in enumerate(searchable, 1):
                    print(f'{n:3}. {col}')
                raw = ask_required('Nomor kolom filter (pisahkan koma, contoh 1,3,10)')
                indexes = [int(x.strip()) for x in raw.split(',')]
                if len(indexes) != len(set(indexes)):
                    raise ValueError('Kolom filter tidak boleh dipilih dua kali')
                if any(i < 1 or i > len(searchable) for i in indexes):
                    raise ValueError('Nomor kolom filter tidak valid')
                filters = {}
                for idx in indexes:
                    col = searchable[idx - 1]
                    val = ask_required(f'Nilai filter {col} (gunakan % untuk pencarian pola)')
                    filters[col] = val
                clauses, params = [], []
                for col, val in filters.items():
                    if '%' in val or '_' in val:
                        clauses.append(qi(col) + ' LIKE ?')
                        params.append(val)
                    else:
                        clauses.append(qi(col) + ' = ?')
                        params.append(val)
                sql = ('SELECT TOP (100) ' + ', '.join(map(qi, searchable)) +
                       ' FROM dbo.' + qi(table) + ' WHERE ' + ' AND '.join(clauses) +
                       ' ORDER BY ' + ', '.join(qi(k) for k in keys))
                cur.execute(sql, *params)
                rows = [dict(zip(searchable, row)) for row in cur.fetchall()]
                if not rows:
                    raise ValueError('Tidak ada record yang cocok dengan filter tersebut. Coba kolom/nilai lain.')
                print(f'\nDitemukan {len(rows)} record (maksimal 100 ditampilkan):')
                for row_no, row in enumerate(rows, 1):
                    print(f'\n[{row_no}]')
                    display(row, 'HASIL FILTER')
                if len(rows) == 1:
                    selected = 1
                else:
                    selected = int(ask_required(f'Pilih nomor record yang akan di-UPDATE [1-{len(rows)}]'))
                    if selected < 1 or selected > len(rows):
                        raise ValueError('Nomor record pilihan tidak valid')
                picked = rows[selected - 1]
                # Gunakan nilai identitas asli dari record terpilih untuk UPDATE aman.
                key = {k: picked[k] for k in keys}
                found = fetch(cur, table, cols, key)
                if len(found) != 1:
                    raise ValueError('Record terpilih tidak dapat diidentifikasi secara unik dari kolom kunci.')
                display(found[0], 'DATA SEBELUM UPDATE')
                editable = list(cols)  # Semua kolom, termasuk ProductId/Task/Activity, boleh diubah.
                for n, k in enumerate(editable, 1):
                    print(f'{n:3}. {k} = {str(found[0][k])[:120]}')
                raw_fields = ask_required('Nomor field UPDATE yang diubah (pisahkan koma, atau ALL)')
                chosen = editable if raw_fields.strip().upper() == 'ALL' else [editable[int(n.strip()) - 1] for n in raw_fields.split(',')]
                if len(chosen) != len(set(chosen)):
                    raise ValueError('Field duplikat')
                if any(k not in editable for k in chosen):
                    raise ValueError('Field UPDATE tidak valid')
                values = {k: numeric(k, ask(k, found[0][k]), nums) for k in chosen}
            ident=tuple(key.values())
            if ident in seen:raise ValueError('Identitas record ganda dalam batch')
            seen.add(ident);items.append((key,values))
            display(values,'PREVIEW '+action+' '+str(i+1)+'/'+str(count))
        if ask('Lanjut backup dan transaksi? (ketik LANJUT)','')!='LANJUT':return
        name=backup(cfg,table);print('Backup penuh dbo.'+name)
        try:
            for key,values in items:
                w,p=condition(key)
                if action=='INSERT':
                    if fetch(cur,table,cols,key,True):raise ValueError('INSERT ditolak: identitas sudah ada '+str(key))
                    cur.execute('INSERT INTO dbo.'+qi(table)+' ('+', '.join(map(qi,cols))+', [InsertDate], [LastModified]) VALUES ('+', '.join('?' for _ in cols)+', GETDATE(), GETDATE())',*[values[k] for k in cols])
                else:
                    if len(fetch(cur,table,cols,key,True))!=1:raise ValueError('UPDATE harus tepat satu record')
                    new_key = dict(key); new_key.update({k: values[k] for k in keys if k in values})
                    if new_key != key and fetch(cur, table, cols, new_key, True):
                        raise ValueError('Identitas baru sudah digunakan record lain: ' + str(new_key))
                    cur.execute('UPDATE dbo.'+qi(table)+' SET '+', '.join(qi(k)+' = ?' for k in values)+', [LastModified] = GETDATE() WHERE '+w,*(list(values.values())+p))
                    verified=fetch(cur,table,cols,new_key)
                    if len(verified)!=1:raise RuntimeError('Verifikasi gagal setelah perubahan identitas '+str(new_key))
                    display(verified[0],'HASIL SEMENTARA '+str(new_key))
            if ask('Ketik COMMIT untuk simpan; selain itu ROLLBACK','')!='COMMIT':
                conn.rollback();print('ROLLBACK. Backup tetap tersedia.');return
            conn.commit();print('COMMIT berhasil.')
        except Exception:
            conn.rollback();raise
        out=Path(script_file).resolve().parent.parent/'output'/activity
        path=deployment(table,activity,cols,keys,nums,action,items,out)
        print('SQL deployment:',path)
    finally:conn.close()
CONFIG = {'activity': 'GenPoskaDebit', 'table': 'ParamGenerateFile', 'columns': ['ProductId', 'Task', 'Activity', 'Description', 'LocalPath', 'Filename', 'LogActivityFilenameDateAdd', 'SourceDatabase', 'FieldSelect', 'TableSource', 'WhereCondition', 'DateCol', 'isSourceFromSP', 'SPName', 'isHeader', 'Delimiter', 'TextQualifier', 'isActive', 'Note'], 'keys': ['ProductId', 'Task', 'Activity'], 'defaults': {'ProductId': 'AYOCONECT', 'Task': 'AYOCONECT-IAFEEMYREPTV-1', 'isActive': 1, 'Description': 'Report GenPoskaDebit', 'LocalPath': 'ControlReport', 'Filename': 'GenPoskaDebit-{%Y%m%d}-AYOCONECT-IAFEEMYREPTV-1.xlsx', 'LogActivityFilenameDateAdd': 0, 'SourceDatabase': 'ReconciliationDBName', 'FieldSelect': '', 'TableSource': '', 'WhereCondition': '', 'DateCol': '', 'isSourceFromSP': 1, 'SPName': "sp_GenerateFileControlReportPoskaDebit '{%Y%m%d}', '{dbo.v_ControlReportAccountListFeatureId.FeatureId_Json}', 'AYOCONECT', '{dbo.v_ControlReportAccountListFeatureId.AccountNumber}'", 'isHeader': 1, 'Delimiter': '|', 'TextQualifier': '', 'Note': None}, 'numeric': ['LogActivityFilenameDateAdd', 'isSourceFromSP', 'isHeader', 'isActive']}
if __name__ == "__main__":
    try:
        run(CONFIG, __file__)
    except (KeyboardInterrupt, EOFError):
        print("\\nActivity dibatalkan oleh pengguna.")
    except SystemExit as exc:
        if str(exc):
            print(exc)
    except Exception as exc:
        print("\\n" + "=" * 72)
        print("  ACTIVITY GAGAL")
        print("-" * 72)
        print(f"  {type(exc).__name__}: {exc}")
        print("  Periksa input, konfigurasi koneksi, dan struktur tabel.")
        print("=" * 72)
