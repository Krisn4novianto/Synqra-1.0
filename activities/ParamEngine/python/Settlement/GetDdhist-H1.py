"""Shared transactional ParamEngine wizard (reconciliation-style) for Control Report activities."""
import sys
from pathlib import Path
from datetime import datetime
def find_project_root(start: Path) -> Path:
    """Find Synqra project root by locating db_config.py, independent of nesting depth."""
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
DB='ParamEngine'; SERVER_KEY=None; HOST=None


def choose_activity_server(servers):
    """Prompt for Server 102 or Local using the central db_config.SERVERS profiles."""
    global SERVER_KEY, HOST
    def value(cfg, name, default=''):
        if isinstance(cfg, dict):
            aliases = {'host': ('host','server','hostname'), 'name': ('name','label','description'), 'key': ('key','profile','type')}
            for alias in aliases.get(name, (name,)):
                if cfg.get(alias) not in (None, ''):
                    return cfg[alias]
            return default
        return getattr(cfg, name, default)

    choices = {}
    for key, cfg in servers.items():
        host = str(value(cfg, 'host')).strip().lower()
        name = str(value(cfg, 'name')).strip().lower()
        config_key = str(value(cfg, 'key')).strip().lower()
        if str(key) == '4' or host.split(',')[0].split(':')[0] == '172.18.246.102':
            choices['1'] = (str(key), cfg, 'Server 102')
        if (str(key) == '3' or config_key in {'local','localhost','server_local'}
                or host in {'localhost','127.0.0.1','.','(local)'} or 'local' in name):
            choices['2'] = (str(key), cfg, 'Lokal')

    print('\n' + '=' * 72)
    print('  SYNQRA | PARAMENGINE | SETTLEMENT')
    print('  Pilih koneksi database untuk activity ini')
    print('-' * 72)
    print('  [1] Server 102  | 172.18.246.102')
    print('  [2] Lokal       | localhost')
    print('  [0] Keluar')
    print('=' * 72)
    while True:
        selected = input('Pilih server [1/2]: ').strip()
        if selected == '0':
            raise SystemExit('Activity dibatalkan pengguna.')
        if selected in choices:
            SERVER_KEY, cfg, label = choices[selected]
            HOST = str(value(cfg, 'host', '?'))
            print(f'\\n  Koneksi dipilih : {label}')
            print(f'  Host            : {HOST}')
            return cfg
        if selected in {'1','2'}:
            print('Profil server tersebut tidak ditemukan di db_config.py. Periksa SERVERS.')
        else:
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
    lines=['USE [ParamEngine];','GO','SET XACT_ABORT ON;','DECLARE @ApproveCommit BIT = 0;',
    'DECLARE @BackupTable SYSNAME = '+lit(table+'_Backup_'+datetime.now().strftime('%Y%m%d_%H%M%S'))+';',
    'IF OBJECT_ID(N\'dbo.\' + @BackupTable, N\'U\') IS NOT NULL THROW 51010, \'Backup exists\', 1;',
    'DECLARE @BackupSQL NVARCHAR(MAX) = N\'SELECT * INTO dbo.\' + QUOTENAME(@BackupTable) + N\' FROM dbo.'+qi(table)+';\';',
    'EXEC sys.sp_executesql @BackupSQL;',
    'BEGIN TRY','  BEGIN TRAN;']
    for idx,(key,values) in enumerate(items,1):
        if action=='INSERT':
            allv={k:values[k] for k in cols}
            names={k:'@V'+str(idx)+'_'+str(n) for n,k in enumerate(cols,1)}
            for k,v in allv.items():lines.append('  DECLARE '+names[k]+' '+('INT' if k in nums else 'NVARCHAR(MAX)')+' = '+lit(v)+';')
            wh=' AND '.join(qi(k)+' = '+names[k] for k in keys)
            lines+=['  IF EXISTS (SELECT 1 FROM dbo.'+qi(table)+' WITH (UPDLOCK,HOLDLOCK) WHERE '+wh+') THROW 51000, '+chr(39)+'Duplikat identitas INSERT'+chr(39)+', 1;',
                    '  INSERT INTO dbo.'+qi(table)+' ('+', '.join(map(qi,cols))+', [InsertDate], [LastModified]) VALUES ('+', '.join(names[k] for k in cols)+', GETDATE(), GETDATE());']
        else:
            names={k:'@K'+str(idx)+'_'+str(n) for n,k in enumerate(key,1)}
            for k,v in key.items():lines.append('  DECLARE '+names[k]+' '+('INT' if k in nums else 'NVARCHAR(MAX)')+' = '+lit(v)+';')
            wh=' AND '.join(qi(k)+' = '+names[k] for k in key)
            lines.append('  IF (SELECT COUNT(*) FROM dbo.'+qi(table)+' WITH (UPDLOCK,HOLDLOCK) WHERE '+wh+') <> 1 THROW 51001, '+chr(39)+'Identitas UPDATE tidak unik'+chr(39)+', 1;')
            lines.append('  UPDATE dbo.'+qi(table)+' SET '+', '.join(qi(k)+' = '+lit(v) for k,v in values.items())+', [LastModified] = GETDATE() WHERE '+wh+';')
        lines.append('  SELECT * FROM dbo.'+qi(table)+' WHERE '+wh+';')
    lines+=['  IF @ApproveCommit = 1 COMMIT TRAN;','  ELSE BEGIN ROLLBACK TRAN; PRINT '+chr(39)+'ROLLBACK: ubah @ApproveCommit menjadi 1 setelah verifikasi'+chr(39)+'; END','END TRY','BEGIN CATCH','  IF @@TRANCOUNT > 0 ROLLBACK TRAN;','  THROW;','END CATCH;','GO']
    out.mkdir(parents=True,exist_ok=True)
    path=out/(activity+'_'+action+'_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.sql')
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return path
def run(config,script_file):
    table=config['table'];activity=config['activity'];cols=config['columns'];keys=config['keys'];nums=set(config.get('numeric',[]));defaults=config['defaults']
    cfg=choose_activity_server(SERVERS)
    print('\\n' + '=' * 72)
    print('  SYNQRA | PARAMENGINE | SETTLEMENT')
    print('-' * 72)
    print(f'  Activity : {activity}')
    print(f'  Target   : {DB}.dbo.{table}')
    print(f'  Server   : {HOST}')
    print('-' * 72)
    print('  [1] INSERT  - tambah konfigurasi')
    print('  [2] UPDATE  - pilih record dan kolom yang diubah')
    print('  [0] Keluar')
    print('=' * 72)
    action=ask('Pilih menu (0/1/2)')
    if action=='0':return
    if action not in ('1','2'):raise ValueError('Pilihan salah')
    action='INSERT' if action=='1' else 'UPDATE'
    try:
        conn=connect_sqlserver(cfg,DB)
    except Exception as exc:
        print('\\n' + '!' * 72)
        print('  KONEKSI SQL SERVER GAGAL')
        print('-' * 72)
        print(f'  Server   : {HOST}')
        print(f'  Database : {DB}')
        print(f'  Detail   : {exc}')
        print('\\n  Periksa SQL Server, host/port, VPN/jaringan, dan kredensial db_config.py.')
        print('  Jika localhost bukan instance SQL Server yang aktif, pilih Server 102.')
        print('  Tidak ada perubahan database yang dilakukan.')
        print('=' * 72)
        return
    conn.autocommit=False
    try:
        cur=conn.cursor()
        # Confirm actual schema before touching data.
        cur.execute('SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=? AND TABLE_NAME=?','dbo',table)
        actual={r[0].lower() for r in cur.fetchall()}
        missing=[c for c in cols+['InsertDate','LastModified'] if c.lower() not in actual]
        if missing:raise RuntimeError('Kolom tabel tidak ditemukan: '+', '.join(missing))
        product = task = None
        if action == 'INSERT':
            product=ask('ProductId',defaults.get('ProductId'))
            task=ask('Task',defaults.get('Task'))
        count=1
        if config.get('batch',False) and action=='INSERT':
            count=int(ask('Jumlah record INSERT',str(len(config.get('rows',[])))))
            if count<1 or count>1000:raise ValueError('Jumlah record 1..1000')
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
                if config.get('rows') and i<len(config['rows']):d.update(config['rows'][i])
                if order is not None:d.update(config.get('order_defaults',{}).get(order,{}))
                d.update(ProductId=product,Task=task)
                if not config.get('variable_activity'):d['Activity']=activity
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
                # Let the operator choose the WHERE/filter columns instead of forcing ProductId + Task.
                print('\nKolom yang bisa dipakai sebagai filter UPDATE:')
                for n, col in enumerate(cols, 1):
                    marker = ' [key]' if col in keys else ''
                    print(f'{n:3}. {col}{marker}')
                default_filter = ','.join(str(cols.index(k)+1) for k in keys if k in cols)
                selection = ask('Nomor kolom filter dipisah koma (contoh 1,2,3)', default_filter).strip()
                try:
                    filter_cols = [cols[int(token.strip())-1] for token in selection.split(',') if token.strip()]
                except (ValueError, IndexError):
                    raise ValueError('Pilihan kolom filter tidak valid')
                if not filter_cols:
                    raise ValueError('Pilih minimal satu kolom filter')
                if len(filter_cols) != len(set(filter_cols)):
                    raise ValueError('Kolom filter tidak boleh dipilih berulang')
                key = {}
                for col in filter_cols:
                    default_filter_value = defaults.get(col)
                    if col == 'Activity':
                        default_filter_value = activity
                    val = ask('Filter ' + col, default_filter_value)
                    key[col] = numeric(col, val, nums)
                found=fetch(cur,table,cols,key)
                if not found:
                    raise ValueError('UPDATE dihentikan: tidak ada record yang cocok dengan filter tersebut')
                if len(found)>1:
                    print(f'Filter menghasilkan {len(found)} record. Pilih record yang memang ingin diubah:')
                    for idx, row in enumerate(found[:50], 1):
                        print(f"\n[{idx}] " + ' | '.join(f"{k}={row.get(k)}" for k in keys))
                    if len(found)>50:
                        raise ValueError('Hasil lebih dari 50 record. Batasi filter agar daftar target lebih spesifik.')
                    pick=ask('Nomor record target (0 untuk batal)','0').strip()
                    if not pick.isdigit() or int(pick)<1 or int(pick)>len(found):
                        raise ValueError('UPDATE dibatalkan: nomor record target tidak valid atau dibatalkan')
                    selected=found[int(pick)-1]
                    # Setelah target dipilih, gunakan seluruh kolom key supaya UPDATE hanya menyentuh satu record.
                    key={col:selected[col] for col in keys}
                    found=fetch(cur,table,cols,key)
                    if len(found)!=1:
                        raise ValueError(f'UPDATE dibatalkan: key record terpilih masih cocok dengan {len(found)} record')
                display(found[0],'DATA SEBELUM UPDATE')
                editable=[k for k in cols if k not in key]
                for n,k in enumerate(editable,1):print(f'{n:3}. {k}')
                selection=ask('Nomor field UPDATE dipisah koma, atau ALL untuk semua kolom','ALL').strip()
                if selection.upper()=='ALL':
                    chosen=editable
                else:
                    try: chosen=[editable[int(n.strip())-1] for n in selection.split(',')]
                    except (ValueError, IndexError): raise ValueError('Pilihan kolom UPDATE tidak valid')
                if not chosen: raise ValueError('Pilih minimal satu kolom UPDATE')
                if len(chosen)!=len(set(chosen)):raise ValueError('Field duplikat')
                values={k:numeric(k,ask(k,found[0][k]),nums) for k in chosen}
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
                    cur.execute('UPDATE dbo.'+qi(table)+' SET '+', '.join(qi(k)+' = ?' for k in values)+', [LastModified] = GETDATE() WHERE '+w,*(list(values.values())+p))
                verified=fetch(cur,table,cols,key)
                if len(verified)!=1:raise RuntimeError('Verifikasi gagal '+str(key))
                display(verified[0],'HASIL SEMENTARA '+str(key))
            if ask('Ketik COMMIT untuk simpan; selain itu ROLLBACK','')!='COMMIT':
                conn.rollback();print('ROLLBACK. Backup tetap tersedia.');return
            conn.commit();print('COMMIT berhasil.')
        except Exception:
            conn.rollback();raise
        out=Path(script_file).resolve().parent.parent/'output'/activity
        path=deployment(table,activity,cols,keys,nums,action,items,out)
        print('SQL deployment:',path)
    finally:conn.close()


CONFIG = {'table': 'ParamGetDDHIST', 'columns': ['ProductId', 'Task', 'Activity', 'SelectQryDaily', 'WhereQryDaily', 'SelectQryMonthly', 'WhereQryMonthly', 'TargetDB', 'TargetTable', 'isActive', 'Note'], 'keys': ['ProductId', 'Task', 'Activity'], 'numeric': ['isActive'], 'defaults': {'ProductId': 'AYOCONECT', 'Task': 'AYOCONECT-TVKABEL-FEE', 'SelectQryDaily': "Right('000' + Convert(varchar(15), [TRACCT]), 15) as AccountNumber, [TRBR] as AccountBranch, Convert(Varchar(10), [8000_RC_MASTER].dbo.formatjulian(TRDATE), 121) as PostingDate, STUFF(STUFF(RIGHT(REPLICATE('0', 6) + CAST(TIMENT AS VARCHAR(6)), 6), 3, 0, ':'), 6, 0, ':') as PostingTime, [DORC] as DebetOrCredit, [TRANCD] as Trancode, [AMT] as Amount, [AUXTRC] as Auxtrc, [TRREMK] as Remark, Convert(Varchar(10), [8000_RC_MASTER].dbo.formatjulian(TREFFD), 121) as EffectiveDate, [TRUSER] as TellerId, [TRSTAT] as TrStat, [TRATYP] as AccountType, [TRCTYP] Currency, [SEQ] Sequence, [SERIAL] as Serial, [TLBDS1] as Tlbds1, [TLBDS2] as Tlbds2", 'WhereQryDaily': 'TRACCT in ({dbo.v_BalanceAccountNumber.AccountNumber})', 'SelectQryMonthly': None, 'WhereQryMonthly': None, 'TargetDB': 'SettlementDBName', 'TargetTable': 'AccountStatement', 'isActive': 1, 'Note': 'Get Data DDHIST for Source Settlement'}, 'activity': 'GetDdhist-H1'}
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
        print("  Periksa input, konfigurasi koneksi, dan struktur tabel. Tidak ada COMMIT otomatis.")
        print("=" * 72)
