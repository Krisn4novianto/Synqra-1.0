#!/usr/bin/env python3
"""
===============================================================================
GETDDHIST - PARAMDDHIST CONFIGURATION WIZARD
===============================================================================

PANDUAN SINGKAT / SOP OPERASIONAL:
  1. Pilih koneksi SQL Server dari db_config.py (.205 atau localhost).
  2. Verifikasi database DataSourceDistributor dan tabel yang dibutuhkan.
  3. Pilih INSERT atau UPDATE melalui menu utama.
  4. INSERT: cari ParamFitur berdasarkan DBName atau buat ParamFitur baru.
  5. UPDATE: pilih ParamFitur atau ParamDDHIST, lalu tentukan record target.
  6. Periksa preview input dan relasi IDFitur sebelum perubahan.
  7. Buat backup kondisi SEBELUM perubahan pada tabel backup terpisah.
  8. Jalankan INSERT/UPDATE di dalam transaksi dan verifikasi hasilnya.
  9. Pilih COMMIT untuk menyimpan atau ROLLBACK untuk membatalkan perubahan.
 10. Setelah COMMIT, buat script SQL deployment untuk lingkungan tujuan.

SOP BACKUP DAN PEMULIHAN:
  - Backup menyimpan snapshot data SEBELUM INSERT/UPDATE, bukan hasil perubahan.
  - Backup tidak melakukan INSERT ulang ke tabel utama.
  - Backup terpisah dapat tetap tersedia walaupun transaksi perubahan di-ROLLBACK.
  - Setiap operasi memiliki nama backup unik untuk menghindari penimpaan.
  - Backup snapshot data BUKAN pengganti SQL Server BACKUP DATABASE.
  - Restore dari backup harus diperiksa dan dijalankan secara terkontrol.

CATATAN KEAMANAN:
  - DBPass dienkripsi menggunakan dbo.fnEncrypt di SQL Server.
  - Jangan menulis password plaintext ke deployment SQL atau log terminal.
  - Deployment dapat memakai variabel SQLCMD $(DBPASS) bila diperlukan.
  - Uji terlebih dahulu di development sebelum dipakai di production.
===============================================================================
"""
from __future__ import annotations
import sys
import secrets
from pathlib import Path
from datetime import datetime
from getpass import getpass

ROOT_DIR = Path(__file__).resolve().parents[3] if len(Path(__file__).resolve().parents) > 3 else Path.cwd()
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
try:
    from db_config import SERVERS
    from db_connection import connect_sqlserver
except ImportError:
    sys.path.insert(0, str(Path.cwd()))
    from db_config import SERVERS
    from db_connection import connect_sqlserver

DATABASE = 'DataSourceDistributor'
PF = 'dbo.ParamFitur'
DDH = 'dbo.ParamDDHIST'
FIELDS = ('IDFitur','FieldSelectTrue','FieldSelectFalse','Rekening','WhereCondition',
          'TableTrueDestination','TableFalseDestination','LogActivityModul',
          'LogActivitySubModul','LogActivityEntity','isActive','Note')
KEY = ('IDFitur','LogActivityModul','LogActivityEntity')
REQUIRED = ('FieldSelectTrue','LogActivityModul','LogActivityEntity')
DEFAULT_OUTPUT_FOLDER = Path(__file__).resolve().parent / 'output' / '01_Reconciliation' / 'GetDDHIST'

# ===========================================================================
# BAGIAN 1 - SINYAL PEMBATALAN
# SOP: Membatalkan tahap wizard secara terkendali tanpa memaksa keluar dari menu utama.
# ===========================================================================
class Cancel(Exception):
    pass

# ===========================================================================
# BAGIAN 2 - FORMAT JUDUL TERMINAL
# SOP: Menyeragamkan garis pemisah dan judul setiap tahap wizard.
# ===========================================================================
def heading(text):
    print('\n' + '=' * 72 + '\n' + text + '\n' + '=' * 72)

# ===========================================================================
# BAGIAN 3 - AKSES KONFIGURASI SERVER
# SOP: Membaca nilai konfigurasi koneksi tanpa menampilkan password.
# ===========================================================================
def _server_value(cfg, name, default=None):
    return cfg.get(name, default) if isinstance(cfg, dict) else getattr(cfg, name, default)

# ===========================================================================
# BAGIAN 4 - IDENTITAS HOST SERVER
# SOP: Membaca host server terpilih untuk informasi dan pesan kesalahan.
# ===========================================================================
def host(cfg):
    return str(_server_value(cfg, 'host', _server_value(cfg, 'server', '')))

# ===========================================================================
# BAGIAN 5 - INPUT PENGGUNA
# SOP: Meminta nilai manual; mendukung default, nilai rahasia, dan pembatalan.
# ===========================================================================
def ask(label, default=None, required=False, secret=False):
    while True:
        suffix = f' [{default}]' if default is not None and not secret else ''
        try:
            raw = (getpass if secret else input)(f'{label}{suffix} (B=batal): ')
        except (EOFError, KeyboardInterrupt):
            raise Cancel()
        if raw.upper() == 'B':
            raise Cancel()
        value = None if raw == '~' else default if raw == '' and default is not None else raw
        if required and (value is None or not str(value).strip()):
            print('[ERROR] Nilai wajib diisi.')
            continue
        return value

# ===========================================================================
# BAGIAN 6 - VALIDASI MENU
# SOP: Membatasi pilihan menu agar hanya menerima opsi yang tersedia.
# ===========================================================================
def choice(label, allowed):
    while True:
        v = ask(label)
        if v in allowed:
            return v
        print('Pilihan tidak valid:', ', '.join(sorted(allowed)))

# ===========================================================================
# BAGIAN 7 - QUERY DATABASE
# SOP: Mengeksekusi query berparameter dan mengubah hasil menjadi dictionary.
# ===========================================================================
def rows(cur, sql, *params):
    cur.execute(sql, *params)
    columns = [c[0] for c in cur.description]
    return [dict(zip(columns, record)) for record in cur.fetchall()]

# ===========================================================================
# BAGIAN 8 - FORMAT NILAI SQL DEPLOYMENT
# SOP: Melakukan escaping literal untuk SQL deployment; bukan untuk input query langsung.
# ===========================================================================
def sql_literal(value):
    if value is None:
        return 'NULL'
    if isinstance(value, (bool, int)):
        return str(int(value))
    return "N'" + str(value).replace("'", "''") + "'"

# ===========================================================================
# BAGIAN 9 - TABEL TERMINAL
# SOP: Menampilkan preview dan hasil pencarian tanpa mengungkap DBPass.
# ===========================================================================
def display(records, title='HASIL', fields=FIELDS):
    heading(title)
    if not records:
        print('Tidak ada data.')
    for index, record in enumerate(records, 1):
        print(f'--- [{index}] ---')
        for field in fields:
            value = '[TERSEMBUNYI]' if field == 'DBPass' else record.get(field)
            print(f'  {field:<24}: {"NULL" if value is None else value}')
    print(f'Total: {len(records)} record')

# ===========================================================================
# BAGIAN 10 - PILIH SERVER
# SOP: Memilih koneksi .205 atau localhost yang disediakan db_config.py.
# ===========================================================================
def choose_connection():
    heading('[TAHAP 1/6] PILIH KONEKSI')
    configs = list(SERVERS.values()) if isinstance(SERVERS, dict) else list(SERVERS)
    remote = next((c for c in configs if host(c).lower() == '172.18.135.205'), None)
    local = next((c for c in configs if host(c).lower() in ('localhost','127.0.0.1','::1')), None)
    valid = [(label, cfg) for label, cfg in [('Server 205', remote), ('Localhost', local)] if cfg is not None]
    if not valid:
        raise RuntimeError('Server .205 / localhost tidak ditemukan di db_config.SERVERS')
    for index, (label, cfg) in enumerate(valid, 1):
        print(f'{index}. {label} ({host(cfg)}:{_server_value(cfg,"port",1433)})')
    print('0. Keluar')
    picked = choice('Pilih koneksi', {str(i) for i in range(len(valid)+1)})
    if picked == '0':
        raise Cancel()
    return valid[int(picked)-1][1]

# ===========================================================================
# BAGIAN 11 - KONEKSI DATABASE TARGET
# SOP: Menghubungkan langsung ke database target dan memeriksa keberadaan tabel.
# ===========================================================================
def connect_verified_database(cfg):
    try:
        conn = connect_sqlserver(cfg, DATABASE)
    except Exception as exc:
        raise RuntimeError(f'Koneksi ke {DATABASE} pada {host(cfg)} gagal: {exc}') from exc
    try:
        cur = conn.cursor()
        try:
            record = rows(cur, "SELECT DB_NAME() AS db, OBJECT_ID(N'dbo.ParamFitur',N'U') AS pf, OBJECT_ID(N'dbo.ParamDDHIST',N'U') AS ddh")[0]
            if str(record['db']).lower() != DATABASE.lower() or record['pf'] is None or record['ddh'] is None:
                raise RuntimeError('Database atau tabel target tidak sesuai.')
        finally:
            cur.close()
        return conn
    except Exception:
        conn.close()
        raise

# ===========================================================================
# BAGIAN 12 - VERIFIKASI KONEKSI
# SOP: Memastikan SQL Server, database, dan tabel sesuai target.
# ===========================================================================
def verify_connection(conn):
    cur = conn.cursor()
    try:
        print('[INFO] Identitas koneksi:', rows(cur, 'SELECT @@SERVERNAME AS SQLServer, DB_NAME() AS DatabaseAktual, SUSER_SNAME() AS LoginSQL')[0])
    finally:
        cur.close()

# ===========================================================================
# BAGIAN 13 - BACA PARAMDDHIST
# SOP: Mengambil kolom konfigurasi ParamDDHIST dengan filter opsional.
# ===========================================================================
def fetch(cur, where='', params=()):
    query = f'SELECT {", ".join("["+f+"]" for f in FIELDS)} FROM {DDH}'
    return rows(cur, query + (' WHERE ' + where if where else ''), *params)

# ===========================================================================
# BAGIAN 14 - PENCARIAN PARAMFITUR
# SOP: Mencari DBName dan memilih IDFitur yang benar dari hasil pencarian.
# ===========================================================================
def find_pf_by_dbname(cur):
    while True:
        heading('CARI PARAMFITUR BERDASARKAN DBNAME')
        name = ask('DBName (boleh sebagian)', required=True)
        found = rows(cur, f'SELECT IDFitur,IPServer,DBName,DBUser,DBType FROM {PF} WHERE DBName LIKE ? ORDER BY DBName,IDFitur', '%'+name+'%')
        display(found, 'HASIL PARAMFITUR', ('IDFitur','IPServer','DBName','DBUser','DBType'))
        if not found:
            if choice('1=Cari lagi 0=Kembali', {'0','1'}) == '0':
                raise Cancel()
            continue
        n = choice('Nomor record (0=cari lagi)', {str(i) for i in range(len(found)+1)})
        if n != '0':
            return found[int(n)-1]

# ===========================================================================
# BAGIAN 15 - PILIH RECORD UPDATE
# SOP: Menentukan tepat satu record ParamDDHIST yang akan diubah.
# ===========================================================================
def select_target(cur):
    while True:
        heading('PILIH PARAMDDHIST UNTUK UPDATE')
        print('1. Modul\n2. IDFitur\n3. Entity\n0. Kembali')
        method = choice('Cari berdasarkan', {'0','1','2','3'})
        if method == '0':
            raise Cancel()
        if method == '2':
            try:
                value = int(ask('IDFitur', required=True))
            except ValueError:
                print('IDFitur harus angka.')
                continue
            result = fetch(cur, '[IDFitur]=?', (value,))
        else:
            field = 'LogActivityModul' if method == '1' else 'LogActivityEntity'
            result = fetch(cur, f'[{field}] LIKE ?', ('%'+ask(field,required=True)+'%',))
        display(result, 'HASIL PENCARIAN', ('IDFitur','LogActivityModul','LogActivitySubModul','LogActivityEntity','TableTrueDestination'))
        if not result:
            continue
        selected = choice('Nomor record (0=cari lagi)', {str(i) for i in range(len(result)+1)})
        if selected == '0':
            continue
        record = result[int(selected)-1]
        if len(fetch(cur, ' AND '.join(f'[{k}]=?' for k in KEY), tuple(record[k] for k in KEY))) != 1:
            print('[ERROR] Kunci tidak unik.')
            continue
        return record

# ===========================================================================
# BAGIAN 16 - INPUT FIELD PARAMDDHIST
# SOP: INSERT mengisi nilai baru; UPDATE dapat mempertahankan nilai lama.
# ===========================================================================
def edit(old, action):
    record = dict(old)
    print('ENTER=nilai lama/default, ~=NULL, B=batal')
    for field in FIELDS[1:]:
        default = old.get(field) if action == 'UPDATE' else (1 if field == 'isActive' else '')
        while True:
            value = ask(field, default=default, required=field in REQUIRED)
            if field == 'isActive':
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    print('isActive harus 0 atau 1.')
                    continue
                if value not in (0,1):
                    print('isActive harus 0 atau 1.')
                    continue
            record[field] = value
            break
    return record

# ===========================================================================
# BAGIAN 17 - PILIH ATAU BUAT PARAMFITUR
# SOP: Menggunakan ParamFitur lama atau menyiapkan identitas ParamFitur baru.
# ===========================================================================
def credentials(cur, action, old=None):
    heading('TENTUKAN PARAMFITUR')
    print('1. Gunakan ParamFitur yang ada')
    if action == 'INSERT':
        print('2. Buat ParamFitur baru')
    print('0. Kembali')
    method = choice('Pilih', {'0','1','2'} if action == 'INSERT' else {'0','1'})
    if method == '0':
        raise Cancel()
    if method == '1':
        selected = find_pf_by_dbname(cur)
        if action == 'UPDATE' and int(selected['IDFitur']) != int(old['IDFitur']):
            raise ValueError('IDFitur tidak sesuai target UPDATE.')
        return {k:selected[k] for k in ('IPServer','DBName','DBUser','DBType')} | {'_selected_id':int(selected['IDFitur'])}
    return {field:ask(field, default='mssql' if field=='DBType' else None, required=True)
            for field in ('IPServer','DBName','DBUser','DBType')}

# ===========================================================================
# BAGIAN 18 - RESOLUSI IDFITUR
# SOP: Memverifikasi IDFitur terpilih atau membuat ParamFitur baru bila diperlukan.
# ===========================================================================
def resolve_pf(cur, cred, action, old):
    if '_selected_id' in cred:
        result = rows(cur, f'SELECT IDFitur FROM {PF} WITH (UPDLOCK,HOLDLOCK) WHERE IDFitur=?', cred['_selected_id'])
        if len(result) != 1:
            raise RuntimeError('ParamFitur terpilih tidak tersedia.')
        return int(result[0]['IDFitur']), False
    found = rows(cur, f'SELECT IDFitur,DBUser,DBType FROM {PF} WITH (UPDLOCK,HOLDLOCK) WHERE IPServer=? AND DBName=?', cred['IPServer'],cred['DBName'])
    if len(found)>1:
        raise ValueError('ParamFitur ganda berdasarkan IPServer + DBName.')
    if found:
        if found[0]['DBUser'] != cred['DBUser'] or found[0]['DBType'] != cred['DBType']:
            raise ValueError('DBUser / DBType tidak cocok.')
        return int(found[0]['IDFitur']), False
    if action != 'INSERT':
        raise ValueError('ParamFitur tidak ditemukan.')
    password = ask('DBPass baru', required=True, secret=True)
    cur.execute(f"INSERT INTO {PF} (IPServer,DBName,DBUser,DBPass,DBType) VALUES (?,?,?,dbo.fnEncrypt(?, ? + 'BR!'),?)",
                cred['IPServer'],cred['DBName'],cred['DBUser'],password,cred['IPServer'],cred['DBType'])
    if cur.rowcount != 1:
        raise RuntimeError('INSERT ParamFitur gagal.')
    result = rows(cur, f'SELECT IDFitur FROM {PF} WHERE IPServer=? AND DBName=?', cred['IPServer'],cred['DBName'])
    if len(result) != 1:
        raise RuntimeError('Verifikasi ParamFitur gagal.')
    return int(result[0]['IDFitur']), True

# ===========================================================================
# BAGIAN 19 - VALIDASI DUPLIKASI
# SOP: Mencegah kombinasi kunci ParamDDHIST yang sama.
# ===========================================================================
def check_unique(cur, record, old=None):
    matches = fetch(cur, ' AND '.join(f'[{k}]=?' for k in KEY), tuple(record[k] for k in KEY))
    if len(matches)>1 or (matches and (old is None or any(record[k]!=old[k] for k in KEY))):
        raise ValueError('Kombinasi IDFitur, Modul, Entity sudah digunakan.')

# ===========================================================================
# BAGIAN 20 - EKSEKUSI INSERT / UPDATE
# SOP: Menulis satu record dan memeriksa jumlah baris terdampak.
# ===========================================================================
def apply(cur, action, record, old):
    if action == 'INSERT':
        cur.execute(f'INSERT INTO {DDH} ({", ".join("["+f+"]" for f in FIELDS)}) VALUES ({", ".join("?" for _ in FIELDS)})', *(record[f] for f in FIELDS))
    else:
        mutable = FIELDS[1:]
        cur.execute(f'UPDATE {DDH} SET {", ".join("["+f+"]= ?" for f in mutable)} WHERE '+ ' AND '.join(f'[{k}]=?' for k in KEY),
                    *([record[f] for f in mutable] + [old[k] for k in KEY]))
    if cur.rowcount != 1:
        raise RuntimeError(f'{action} harus memengaruhi tepat satu record, aktual {cur.rowcount}.')

# A separate, committed transaction ensures backup persists even after a change rollback.
# ===========================================================================
# BAGIAN 21 - BACKUP SEBELUM PERUBAHAN
# SOP: Menyimpan snapshot kondisi awal ke tabel backup terpisah sebelum DML; tidak mengubah tabel utama.
# ===========================================================================
def backup_tables(conn, tables):
    if not tables:
        return []
    suffix = datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '_' + secrets.token_hex(3)
    backup_names = []
    cur = conn.cursor()
    try:
        conn.rollback()
        conn.autocommit = False
        cur.execute('SET XACT_ABORT ON')
        for table in tables:
            if table not in ('ParamFitur','ParamDDHIST'):
                raise ValueError('Tabel backup tidak diizinkan.')
            name = f'{table}_Backup_{suffix}'
            cur.execute(f'SELECT * INTO dbo.[{name}] FROM dbo.[{table}]')
            backup_names.append('dbo.'+name)
        conn.commit()
        print('[BACKUP] Snapshot permanen berhasil:')
        for name in backup_names:
            print('  ', name)
        return backup_names
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()

# ===========================================================================
# BAGIAN 22 - GENERATOR SQL DEPLOYMENT PARAMDDHIST
# SOP: Menyusun deployment dengan backup, transaksi, verifikasi, COMMIT, dan ROLLBACK.
# ===========================================================================
def deployment(action, record, cred, old, pf_created):
    """Generate standalone deployment with persistent backup BEFORE DML transaction."""
    ip, db = sql_literal(cred['IPServer']), sql_literal(cred['DBName'])
    lines = [
        '/* GETDDHIST deployment. Run in SQLCMD mode when creating ParamFitur.',
        '   Set DBPASS securely; do not save plaintext credentials in this script.',
        '   Backups are data snapshots (SELECT INTO), not full database backups.',
        '   Backups are COMMITTED BEFORE the DML transaction and survive rollback. */',
        f'USE [{DATABASE}];', 'GO', 'SET NOCOUNT ON;', 'SET XACT_ABORT ON;',
        'DECLARE @IDFitur INT, @CountPF INT;',
        'DECLARE @Suffix VARCHAR(40) = CONVERT(CHAR(8),SYSDATETIME(),112) + N\'_\' + REPLACE(CONVERT(VARCHAR(8),SYSDATETIME(),108),\':\',\'\') + N\'_\' + RIGHT(REPLACE(CONVERT(VARCHAR(36),NEWID()),\'-\',\'\'),8);',
        '/* Persistent backup transaction; failure prevents any data modification. */',
        'BEGIN TRY', '  BEGIN TRANSACTION;'
    ]
    for table in ('ParamFitur','ParamDDHIST'):
        lines += [
            f"  DECLARE @Backup{table} SYSNAME = N'{table}_Backup_' + @Suffix;",
            f"  IF OBJECT_ID(N'dbo.' + @Backup{table},N'U') IS NOT NULL THROW 51020,'Backup already exists',1;",
            f"  EXEC(N'SELECT * INTO dbo.' + QUOTENAME(@Backup{table}) + N' FROM dbo.[{table}]');"
        ]
    lines += [
        '  COMMIT TRANSACTION;', "  PRINT 'PERSISTENT BACKUP SUCCESS';",
        'END TRY', 'BEGIN CATCH', '  IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;', '  THROW;', 'END CATCH;',
        'BEGIN TRY', '  BEGIN TRANSACTION;',
        f'  SELECT @CountPF=COUNT(*),@IDFitur=MIN(IDFitur) FROM {PF} WITH (UPDLOCK,HOLDLOCK) WHERE IPServer={ip} AND DBName={db};',
        "  IF @CountPF>1 THROW 51021,'Duplicate ParamFitur',1;"
    ]
    if action == 'INSERT':
        lines += [
            '  IF @IDFitur IS NULL', '  BEGIN',
            f"    INSERT INTO {PF} (IPServer,DBName,DBUser,DBPass,DBType) VALUES ({ip},{db},{sql_literal(cred['DBUser'])},dbo.fnEncrypt(N'$(DBPASS)',{ip}+N'BR!'),{sql_literal(cred['DBType'])});",
            f'    SELECT @IDFitur=IDFitur FROM {PF} WHERE IPServer={ip} AND DBName={db};',
            '  END;'
        ]
    else:
        lines += ["  IF @IDFitur IS NULL THROW 51022,'ParamFitur not found',1;"]
    new_key = ' AND '.join(['[IDFitur]=@IDFitur']+[f'[{k}]={sql_literal(record[k])}' for k in KEY[1:]])
    if action == 'INSERT':
        lines += [
            f"  IF EXISTS(SELECT 1 FROM {DDH} WITH (UPDLOCK,HOLDLOCK) WHERE {new_key}) THROW 51024,'Duplicate ParamDDHIST',1;",
            f"  INSERT INTO {DDH} ({', '.join('['+f+']' for f in FIELDS)}) VALUES ({', '.join('@IDFitur' if f=='IDFitur' else sql_literal(record[f]) for f in FIELDS)});"
        ]
    else:
        old_key = ' AND '.join(['[IDFitur]=@IDFitur']+[f'[{k}]={sql_literal(old[k])}' for k in KEY[1:]])
        lines += [f"  UPDATE {DDH} SET {', '.join('['+f+']=' + sql_literal(record[f]) for f in FIELDS[1:])} WHERE {old_key};"]
    lines += [
        "  IF @@ROWCOUNT <> 1 THROW 51025,'Affected rows != 1',1;",
        f"  IF (SELECT COUNT(*) FROM {DDH} WHERE {new_key}) <> 1 THROW 51026,'Verification failed',1;",
        '  COMMIT TRANSACTION;', "  PRINT 'COMMIT SUCCESS';", 'END TRY', 'BEGIN CATCH',
        '  IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;', '  THROW;', 'END CATCH;',
        f'SELECT * FROM {DDH} WHERE {new_key};', 'GO'
    ]
    return '\n'.join(lines)+'\n'

# ===========================================================================
# BAGIAN 23 - GENERATOR SQL DEPLOYMENT PARAMFITUR
# SOP: Menyusun deployment UPDATE ParamFitur dengan backup kondisi awal.
# ===========================================================================
def pf_deployment(identity, selected, changed):
    """ParamFitur UPDATE deployment. Password provided at execution as SQLCMD DBPASS."""
    lines = [
        '/* ParamFitur UPDATE deployment. If changing DBPass use SQLCMD variable DBPASS.',
        '   Full-table backup persists even if UPDATE transaction is rolled back. */',
        f'USE [{DATABASE}];', 'GO', 'SET NOCOUNT ON;', 'SET XACT_ABORT ON;',
        "DECLARE @Suffix VARCHAR(40) = CONVERT(CHAR(8),SYSDATETIME(),112) + N'_' + REPLACE(CONVERT(VARCHAR(8),SYSDATETIME(),108),':','') + N'_' + RIGHT(REPLACE(CONVERT(VARCHAR(36),NEWID()),'-',''),8);",
        "DECLARE @Backup SYSNAME = N'ParamFitur_Backup_' + @Suffix;",
        'BEGIN TRY', '  BEGIN TRANSACTION;',
        "  IF OBJECT_ID(N'dbo.' + @Backup,N'U') IS NOT NULL THROW 51030,'Backup already exists',1;",
        "  EXEC(N'SELECT * INTO dbo.' + QUOTENAME(@Backup) + N' FROM dbo.ParamFitur');",
        '  COMMIT TRANSACTION;', "  PRINT 'PERSISTENT BACKUP SUCCESS';",
        'END TRY', 'BEGIN CATCH', '  IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;', '  THROW;', 'END CATCH;',
        'BEGIN TRY', '  BEGIN TRANSACTION;'
    ]
    assigns = []
    for field, value in changed.items():
        if field == 'DBPass':
            salt_ip = sql_literal(changed.get('IPServer', selected['IPServer']))
            assigns.append(f"[DBPass]=dbo.fnEncrypt(N'$(DBPASS)',{salt_ip}+N'BR!')")
        else:
            assigns.append(f'[{field}]={sql_literal(value)}')
    lines += [
        f"  IF (SELECT COUNT(*) FROM {PF} WITH (UPDLOCK,HOLDLOCK) WHERE IDFitur={identity}) <> 1 THROW 51031,'ParamFitur missing',1;",
        f"  UPDATE {PF} SET {', '.join(assigns)} WHERE IDFitur={identity};",
        "  IF @@ROWCOUNT <> 1 THROW 51032,'UPDATE affected rows != 1',1;",
        '  COMMIT TRANSACTION;', "  PRINT 'COMMIT SUCCESS';", 'END TRY', 'BEGIN CATCH',
        '  IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;', '  THROW;', 'END CATCH;',
        f'SELECT IDFitur,IPServer,DBName,DBUser,DBType FROM {PF} WHERE IDFitur={identity};', 'GO'
    ]
    return '\n'.join(lines)+'\n'

# ===========================================================================
# BAGIAN 24 - PENYIMPANAN FILE SQL
# SOP: Menyimpan SQL deployment ke folder output setelah COMMIT.
# ===========================================================================
def save_sql(output_folder, prefix, content):
    folder = Path(output_folder or DEFAULT_OUTPUT_FOLDER)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f'{prefix}_{datetime.now():%Y%m%d_%H%M%S_%f}.sql'
    path.write_text(content, encoding='utf-8')
    print('[SQL DEPLOYMENT]', path)
    return path

# ===========================================================================
# BAGIAN 25 - TRANSAKSI DAN KONFIRMASI PARAMDDHIST
# SOP: Preview, backup, perubahan, verifikasi, lalu COMMIT/ROLLBACK sesuai pilihan.
# ===========================================================================
def execute_wizard(conn, action, output_folder):
    cur = conn.cursor()
    committed = False
    try:
        old = select_target(cur) if action == 'UPDATE' else None
        cred = credentials(cur, action, old)
        heading('[TAHAP 4/6] INPUT PARAMDDHIST')
        record = edit(old or {f:None for f in FIELDS}, action)
        if '_selected_id' in cred:
            record['IDFitur'] = cred['_selected_id']
        display([record], 'PREVIEW INPUT')
        decision = choice('1=Lanjut 2=Ulang 0=Batal', {'0','1','2'})
        if decision != '1':
            return 'RETRY' if decision == '2' else 'BACK'
        heading('[BACKUP] KONFIRMASI SNAPSHOT SEBELUM PERUBAHAN')
        print('Backup permanen kedua tabel akan dibuat sebelum INSERT/UPDATE.')
        if choice('1=Backup dan lanjut 0=Batal', {'0','1'}) != '1':
            return 'BACK'
        # Critical: backup transaction is committed independently of DML transaction.
        backup_tables(conn, ('ParamFitur','ParamDDHIST'))
        conn.autocommit = False
        cur.execute('SET XACT_ABORT ON')
        id_fitur, created = resolve_pf(cur, cred, action, old)
        record['IDFitur'] = id_fitur
        check_unique(cur, record, old)
        heading('[TAHAP 5/6] PREVIEW TRANSAKSI')
        display([record], 'DATA YANG AKAN DIUBAH')
        print('IDFitur:', id_fitur, '| ParamFitur:', 'BARU' if created else 'SUDAH ADA')
        decision = choice('1=Jalankan 2=Rollback/ulang 0=Rollback/kembali', {'0','1','2'})
        if decision != '1':
            conn.rollback()
            return 'RETRY' if decision == '2' else 'BACK'
        apply(cur, action, record, old)
        actual = fetch(cur, ' AND '.join(f'[{k}]=?' for k in KEY), tuple(record[k] for k in KEY))
        if len(actual)!=1 or any(actual[0][f]!=record[f] for f in FIELDS):
            raise RuntimeError('Verifikasi sebelum COMMIT gagal.')
        heading('[TAHAP 6/6] KONFIRMASI COMMIT')
        display(actual, 'HASIL (BELUM COMMIT)')
        decision = choice('1=COMMIT 2=ROLLBACK/ulang 0=ROLLBACK/kembali', {'0','1','2'})
        if decision != '1':
            conn.rollback()
            print('[INFO] Perubahan dibatalkan; tabel backup tetap tersimpan.')
            return 'RETRY' if decision == '2' else 'BACK'
        conn.commit()
        committed = True
        print('[SUCCESS] COMMIT berhasil; backup permanen tetap tersimpan.')
        try:
            save_sql(output_folder, f'GetDDHIST_{action}', deployment(action,record,cred,old,created))
            if action == 'INSERT':
                print('[INFO] Deployment membutuhkan SQLCMD DBPASS hanya bila ParamFitur baru diperlukan.')
        except Exception as exc:
            print('[WARNING] COMMIT berhasil tetapi pembuatan SQL gagal:', exc)
        return 'DONE'
    except Cancel:
        if not committed:
            conn.rollback()
        return 'BACK'
    except Exception as exc:
        if not committed:
            conn.rollback()
        print('[ERROR]', exc)
        print('[INFO] Perubahan di-ROLLBACK; backup yang sudah dibuat tetap tersimpan.')
        return 'RETRY' if choice('1=Ulang 0=Kembali', {'0','1'}) == '1' else 'BACK'
    finally:
        try:
            conn.autocommit = True
        except Exception:
            pass
        cur.close()

# ===========================================================================
# BAGIAN 26 - UPDATE PARAMFITUR SECARA TERPISAH
# SOP: Pilih DBName, backup kondisi awal, update, verifikasi, dan COMMIT eksplisit.
# ===========================================================================
def update_paramfitur(conn, output_folder=None):
    cur = conn.cursor()
    committed = False
    try:
        selected = find_pf_by_dbname(cur)
        identity = int(selected['IDFitur'])
        heading('UPDATE PARAMFITUR')
        print('1. IPServer\n2. DBName\n3. DBUser\n4. DBType\n5. DBPass\n0. Preview')
        field_map = {'1':'IPServer','2':'DBName','3':'DBUser','4':'DBType','5':'DBPass'}
        changed = {}
        while True:
            op = choice('Pilih kolom', {'0','1','2','3','4','5'})
            if op == '0':
                break
            field = field_map[op]
            changed[field] = ask('Nilai baru '+field, required=True, secret=field=='DBPass')
        if not changed:
            return 'BACK'
        display([selected], 'SEBELUM UPDATE', ('IDFitur','IPServer','DBName','DBUser','DBType'))
        print('Perubahan:', {k:('[TERSEMBUNYI]' if k=='DBPass' else v) for k,v in changed.items()})
        if choice('1=Backup dan UPDATE 2=Ulang 0=Batal', {'0','1','2'}) != '1':
            return 'BACK'
        backup_tables(conn, ('ParamFitur',))
        conn.autocommit = False
        cur.execute('SET XACT_ABORT ON')
        before = rows(cur, f'SELECT IDFitur FROM {PF} WITH (UPDLOCK,HOLDLOCK) WHERE IDFitur=?', identity)
        if len(before) != 1:
            raise RuntimeError('IDFitur tidak ditemukan / tidak unik.')
        assigns, params = [], []
        for field, value in changed.items():
            if field == 'DBPass':
                assigns.append("[DBPass]=dbo.fnEncrypt(?, ? + 'BR!')")
                params.extend([value, changed.get('IPServer', selected['IPServer'])])
            else:
                assigns.append(f'[{field}]=?')
                params.append(value)
        cur.execute(f'UPDATE {PF} SET {", ".join(assigns)} WHERE IDFitur=?', *(params+[identity]))
        if cur.rowcount != 1:
            raise RuntimeError('UPDATE tidak memengaruhi tepat satu record.')
        result = rows(cur, f'SELECT IDFitur,IPServer,DBName,DBUser,DBType FROM {PF} WHERE IDFitur=?', identity)
        if len(result)!=1 or any(str(result[0][k])!=str(v) for k,v in changed.items() if k!='DBPass'):
            raise RuntimeError('Verifikasi UPDATE gagal.')
        display(result, 'HASIL UPDATE (BELUM COMMIT)', ('IDFitur','IPServer','DBName','DBUser','DBType'))
        decision = choice('1=COMMIT 2=ROLLBACK/ulang 0=ROLLBACK/kembali', {'0','1','2'})
        if decision != '1':
            conn.rollback()
            return 'RETRY' if decision == '2' else 'BACK'
        conn.commit()
        committed = True
        print('[SUCCESS] COMMIT berhasil; backup tetap tersimpan.')
        try:
            save_sql(output_folder, 'GetDDHIST_UPDATE_ParamFitur', pf_deployment(identity, selected, changed))
        except Exception as exc:
            print('[WARNING] Gagal menulis SQL deployment:', exc)
        return 'DONE'
    except Cancel:
        if not committed:
            conn.rollback()
        return 'BACK'
    except Exception as exc:
        if not committed:
            conn.rollback()
        print('[ERROR]', exc)
        return 'RETRY' if choice('1=Ulang 0=Kembali', {'0','1'}) == '1' else 'BACK'
    finally:
        try:
            conn.autocommit = True
        except Exception:
            pass
        cur.close()

# ===========================================================================
# BAGIAN 27 - MENU UTAMA
# SOP: Memilih server, memverifikasi koneksi, dan mengulang menu INSERT/UPDATE.
# ===========================================================================
def run(output_folder=None, cfg=None):
    heading('GETDDHIST - WIZARD INSERT / UPDATE + BACKUP')
    try:
        cfg = cfg if cfg is not None else choose_connection()
        conn = connect_verified_database(cfg)
    except Cancel:
        return
    except Exception as exc:
        print('[ERROR]', exc)
        return
    try:
        verify_connection(conn)
        while True:
            heading('MENU UTAMA - GETDDHIST')
            print('1. INSERT KONFIGURASI BARU\n2. UPDATE KONFIGURASI\n0. KELUAR')
            try:
                op = choice('Menu utama', {'0','1','2'})
                if op == '0':
                    break
                if op == '1':
                    action, updater = 'INSERT', None
                else:
                    print('1. UPDATE ParamFitur\n2. UPDATE ParamDDHIST\n0. Kembali')
                    target = choice('Tabel', {'0','1','2'})
                    if target == '0':
                        continue
                    action, updater = 'UPDATE', ('PF' if target=='1' else None)
                while True:
                    result = update_paramfitur(conn,output_folder) if updater=='PF' else execute_wizard(conn,action,output_folder)
                    if result == 'RETRY':
                        continue
                    if result == 'BACK':
                        break
                    if choice('1=Operasi lagi 0=Menu utama', {'0','1'}) == '0':
                        break
            except Cancel:
                print('[INFO] Kembali ke menu utama.')
    finally:
        conn.close()

if __name__ == '__main__':
    try:
        run()
    except (KeyboardInterrupt,EOFError,Cancel):
        print('\nKeluar.')
