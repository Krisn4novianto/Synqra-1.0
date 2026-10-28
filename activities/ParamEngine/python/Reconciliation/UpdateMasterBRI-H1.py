"""ParamEngine activity configuration wizard. Run from project root."""
import sys
from pathlib import Path
from datetime import datetime

def find_project_root(start: Path) -> Path:
    """Cari root Synqra dari lokasi script, bukan berdasarkan kedalaman folder."""
    start = start.resolve()
    candidates = (start, *start.parents)
    for parent in candidates:
        if (parent / "db_config.py").is_file() and (parent / "db_connection.py").is_file():
            return parent
    raise ModuleNotFoundError(
        "Tidak menemukan db_config.py dan db_connection.py di folder induk. "
        "Pastikan kedua file tersebut ada di root project Synqra-1.0."
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

SERVER_KEY = '4'
HOST = '172.18.246.102'
DB = 'ParamEngine'
TABLE = 'ParamRecon'
ACTIVITY = 'UpdateMasterBRI-H1'
COLUMNS = ['ProductId', 'Task', 'Activity', 'OrderExecute', 'Description', 'Source1Table', 'Source2Table', 'Source1Where', 'Source2Where', 'Source1DataDateCol', 'Source2DataDateCol', 'Source1KeyJoinCol1', 'Source2KeyJoinCol1', 'Source1KeyJoinCol2', 'Source2KeyJoinCol2', 'Source1KeyJoinCol3', 'Source2KeyJoinCol3', 'Source1KeyJoinCol4', 'Source2KeyJoinCol4', 'Source1KeyJoinCol5', 'Source2KeyJoinCol5', 'Source1KeyJoinCol6', 'Source2KeyJoinCol6', 'Source1KeyJoinCol7', 'Source2KeyJoinCol7', 'Source1KeyJoinCol8', 'Source2KeyJoinCol8', 'Source1KeyJoinCol9', 'Source2KeyJoinCol9', 'Source1KeyJoinCol10', 'Source2KeyJoinCol10', 'Source1SelectCol', 'Source2SelectCol', 'Source1PartitionCol', 'Source2PartitionCol', 'Source1OrderCol', 'Source2OrderCol', 'Source1UpdateCol1', 'Source2UpdateData1', 'Source1UpdateCol2', 'Source2UpdateData2', 'Source1UpdateCol3', 'Source2UpdateData3', 'Source1UpdateCol4', 'Source2UpdateData4', 'Source1UpdateCol5', 'Source2UpdateData5', 'Source1UpdateCol6', 'Source2UpdateData6', 'Source1UpdateCol7', 'Source2UpdateData7', 'Source1UpdateCol8', 'Source2UpdateData8', 'Source1UpdateCol9', 'Source2UpdateData9', 'Source1UpdateCol10', 'Source2UpdateData10', 'Source2UpdateCol1', 'Source1UpdateData1', 'Source2UpdateCol2', 'Source1UpdateData2', 'Source2UpdateCol3', 'Source1UpdateData3', 'Source2UpdateCol4', 'Source1UpdateData4', 'Source2UpdateCol5', 'Source1UpdateData5', 'Source2UpdateCol6', 'Source1UpdateData6', 'Source2UpdateCol7', 'Source1UpdateData7', 'Source2UpdateCol8', 'Source1UpdateData8', 'Source2UpdateCol9', 'Source1UpdateData9', 'Source2UpdateCol10', 'Source1UpdateData10', 'Source1isMoveDataMatch', 'Source2isMoveDataMatch', 'Source1UniqueCol', 'Source2UniqueCol', 'Source1FlagMatchCol', 'Source2FlagMatchCol', 'Source1FieldSelectMove', 'Source2FieldSelectMove', 'Source1MoveTargetTable', 'Source2MoveTargetTable', 'isActive', 'ReconDB']
KEYS = ['ProductId','Task','Activity'] + (['OrderExecute'] if TABLE == 'ParamRecon' else [])
NUMERIC = {'SourceDataDateAdd','SourceServerId','DestinationServerId','IsActive','isActive','OrderExecute','Source1isMoveDataMatch','Source2isMoveDataMatch'}
REQUIRED = {'ProductId','Task','Activity'} | ({'OrderExecute'} if TABLE == 'ParamRecon' else set())
DEFAULTS = {'OrderExecute': 1, 'Description': 'Update ReconcileKey 1-6', 'Source1Table': 'MasterBRI', 'Source1Where': "FeatureId = 'AYOCONECT-TVKABEL' and (ReconcileKey1 is NULL or ReconcileKey2 is NULL or ReconcileKey3 is NULL or ReconcileKey4 is NULL or ReconcileKey5 is NULL or ReconcileKey6 is NULL)", 'Source1DataDateCol': 'TransactionDate', 'isActive': 1, 'ReconDB': 'ReconciliationDBName', 'Source1isMoveDataMatch': 0, 'Source2isMoveDataMatch': 0, 'Source1UpdateCol1': 'ReconcileKey1', 'Source1UpdateCol2': 'ReconcileKey2', 'Source1UpdateCol3': 'ReconcileKey3', 'Source1UpdateCol4': 'ReconcileKey4', 'Source1UpdateCol5': 'ReconcileKey5', 'Source1UpdateCol6': 'ReconcileKey6', 'Source2UpdateData1': 'RIGHT(Remark1,12)', 'Source2UpdateData2': "SUBSTRING(TLBTPN, CHARINDEX('MYREPTV', TLBTPN) + LEN('MYREPTV'), CHARINDEX('NBMB', TLBTPN) - (CHARINDEX('MYREPTV', TLBTPN) + LEN('MYREPTV')))", 'Source2UpdateData3': 'DebetAccountNumber', 'Source2UpdateData4': 'CONVERT(VARCHAR(19), TransactionDatetime, 120)', 'Source2UpdateData5': "CASE WHEN TLCUR1 IS NOT NULL THEN TLCUR1 WHEN TLCUR1 IS NULL AND SUBSTRING(RIGHT(CONCAT(REPLICATE('0',15), DebetAccountNumber),15),5,2) = '01' THEN 'IDR' END", 'Source2UpdateData6': 'CONVERT(DECIMAL(18,2), DebetAmountTransaction)', 'ProductId': 'AYOCONECT', 'Task': 'AYOCONECT-TVKABEL', 'Activity': '', 'Source2Table': '', 'Source2Where': '', 'Source2DataDateCol': '', 'Source1KeyJoinCol1': '', 'Source2KeyJoinCol1': '', 'Source1KeyJoinCol2': '', 'Source2KeyJoinCol2': '', 'Source1KeyJoinCol3': '', 'Source2KeyJoinCol3': '', 'Source1KeyJoinCol4': '', 'Source2KeyJoinCol4': '', 'Source1KeyJoinCol5': '', 'Source2KeyJoinCol5': '', 'Source1KeyJoinCol6': '', 'Source2KeyJoinCol6': '', 'Source1KeyJoinCol7': '', 'Source2KeyJoinCol7': '', 'Source1KeyJoinCol8': '', 'Source2KeyJoinCol8': '', 'Source1KeyJoinCol9': '', 'Source2KeyJoinCol9': '', 'Source1KeyJoinCol10': '', 'Source2KeyJoinCol10': '', 'Source1SelectCol': '', 'Source2SelectCol': '', 'Source1PartitionCol': '', 'Source2PartitionCol': '', 'Source1OrderCol': '', 'Source2OrderCol': '', 'Source1UpdateCol7': '', 'Source2UpdateData7': '', 'Source1UpdateCol8': '', 'Source2UpdateData8': '', 'Source1UpdateCol9': '', 'Source2UpdateData9': '', 'Source1UpdateCol10': '', 'Source2UpdateData10': '', 'Source2UpdateCol1': '', 'Source1UpdateData1': '', 'Source2UpdateCol2': '', 'Source1UpdateData2': '', 'Source2UpdateCol3': '', 'Source1UpdateData3': '', 'Source2UpdateCol4': '', 'Source1UpdateData4': '', 'Source2UpdateCol5': '', 'Source1UpdateData5': '', 'Source2UpdateCol6': '', 'Source1UpdateData6': '', 'Source2UpdateCol7': '', 'Source1UpdateData7': '', 'Source2UpdateCol8': '', 'Source1UpdateData8': '', 'Source2UpdateCol9': '', 'Source1UpdateData9': '', 'Source2UpdateCol10': '', 'Source1UpdateData10': '', 'Source1UniqueCol': '', 'Source2UniqueCol': '', 'Source1FlagMatchCol': '', 'Source2FlagMatchCol': '', 'Source1FieldSelectMove': '', 'Source2FieldSelectMove': '', 'Source1MoveTargetTable': '', 'Source2MoveTargetTable': ''}
OUT = Path(__file__).resolve().parent.parent / 'output' / ACTIVITY


def qid(s):
    return '[' + s.replace(']', ']]') + ']'


def sql_literal(value):
    if value is None:
        return 'NULL'
    if isinstance(value, int):
        return str(value)
    return "N'" + str(value).replace("'", "''") + "'"


def ask(label, default=None, multiline=False):
    suffix = f' [{default}]' if default is not None and len(str(default)) < 70 else ''
    if multiline:
        print(f'{label} (multi-baris; ketik .SELESAI untuk selesai; Enter kosong = default)')
        lines = []
        while True:
            line = input('  > ')
            if line.strip() == '.SELESAI':
                break
            lines.append(line)
        value = '\n'.join(lines).strip()
    else:
        value = input(f'{label}{suffix}: ').strip()
    return default if not value and default is not None else value


def convert(col, value):
    if col in NUMERIC:
        try:
            result = int(value)
        except (ValueError, TypeError):
            raise ValueError(f'{col} harus angka bulat')
        if col in ('IsActive','isActive','Source1isMoveDataMatch','Source2isMoveDataMatch','SourceDataDateAdd') and result not in (0,1):
            raise ValueError(f'{col} harus 0 atau 1')
        if col == 'OrderExecute' and result < 1:
            raise ValueError('OrderExecute minimal 1')
        return result
    if col in REQUIRED and not str(value).strip():
        raise ValueError(f'{col} wajib diisi')
    return str(value)


def show_record(title, record, n=None, total=None):
    print('\n=== ' + title + ' ===')
    if n is not None:
        print(f'--- RECORD {n}/{total} ---')
    width = max(len(k) for k in record) if record else 12
    for key, value in record.items():
        rendered = 'NULL' if value is None else str(value)
        lines = rendered.splitlines() or ['']
        print(f'{key:<{width}} = {lines[0]}')
        for line in lines[1:]:
            print(' ' * (width + 3) + line)


def choose_columns():
    cols = list(COLUMNS)  # Semua kolom termasuk kolom identitas boleh diubah.
    print('\nPilih field yang akan di-UPDATE:')
    for i, c in enumerate(cols, 1):
        print(f' {i:2}. {c}')
    raw = input('Nomor field (contoh 1,3,5): ').strip()
    try:
        indexes = [int(v.strip()) for v in raw.split(',')]
        if not indexes or len(indexes) != len(set(indexes)) or any(i < 1 or i > len(cols) for i in indexes):
            raise ValueError()
    except ValueError:
        raise ValueError('Nomor field UPDATE tidak valid')
    return [cols[i-1] for i in indexes]


def input_data(update=False):
    columns = choose_columns() if update else [c for c in COLUMNS if c != 'Activity']
    result = {}
    for col in columns:
        default = None if update else DEFAULTS.get(col, '' if col not in REQUIRED else None)
        result[col] = convert(col, ask(col, default, multiline=col in {'SelectQry','WhereQry','SPExecute','Source1Where','Source2Where','FieldSelect','WhereCondition'}))
    if not update:
        result['Activity'] = ACTIVITY
    return result


def condition(keys):
    return ' AND '.join(f'{qid(k)} = ?' for k in keys), list(keys.values())


def read_record(cur, keys, lock=False):
    wh, params = condition(keys)
    hint = ' WITH (UPDLOCK, HOLDLOCK)' if lock else ''
    cols = COLUMNS + ['InsertDate','LastModified']
    cur.execute(f'SELECT {", ".join(qid(c) for c in cols)} FROM dbo.{qid(TABLE)}{hint} WHERE {wh}', *params)
    return [dict(zip(cols, row)) for row in cur.fetchall()]



def choose_update_target(cur):
    """Cari record UPDATE memakai kolom pilihan pengguna, lalu ambil key record terpilih."""
    print('\nKolom yang bisa dipakai sebagai filter:')
    for i, col in enumerate(COLUMNS, 1):
        print(f' {i:2}. {col}')
    raw = input('Nomor kolom filter (pisah koma, contoh 1,3,4): ').strip()
    try:
        indexes = [int(x.strip()) for x in raw.split(',')]
        if not indexes or len(indexes) != len(set(indexes)) or any(i < 1 or i > len(COLUMNS) for i in indexes):
            raise ValueError()
    except ValueError:
        raise ValueError('Pilihan kolom filter tidak valid')
    filters = {}
    for i in indexes:
        col = COLUMNS[i-1]
        filters[col] = convert(col, ask('Filter ' + col))
    where_sql = ' AND '.join(f'{qid(col)} = ?' for col in filters)
    cur.execute(f'SELECT {", ".join(qid(c) for c in COLUMNS)} FROM dbo.{qid(TABLE)} WHERE {where_sql}', *filters.values())
    rows = [dict(zip(COLUMNS, row)) for row in cur.fetchall()]
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
    return {k: row[k] for k in KEYS}, row

def backup(cfg):
    name = TABLE + '_Backup_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    con = connect_sqlserver(cfg, DB)
    try:
        con.autocommit = True
        cur = con.cursor()
        try:
            cur.execute(f'SELECT * INTO dbo.{qid(name)} FROM dbo.{qid(TABLE)}')
        finally:
            cur.close()
    finally:
        con.close()
    print('Backup berhasil: dbo.' + name)
    return name


def insert_record(cur, values):
    keys = {k: values[k] for k in KEYS}
    if read_record(cur, keys, True):
        raise ValueError('Record dengan identitas tersebut sudah ada. Gunakan UPDATE.')
    cols = COLUMNS
    query = (f'INSERT INTO dbo.{qid(TABLE)} (' + ', '.join(qid(c) for c in cols)
             + ', [InsertDate], [LastModified]) VALUES ('
             + ', '.join('?' for _ in cols) + ', GETDATE(), GETDATE())')
    cur.execute(query, *[values[c] for c in cols])
    if cur.rowcount not in (1,-1):
        raise RuntimeError('INSERT tidak memengaruhi tepat satu record')
    return keys


def update_record(cur, keys, changes):
    if len(read_record(cur, keys, True)) != 1:
        raise ValueError('UPDATE membutuhkan tepat satu record')
    wh, params = condition(keys)
    assignments = ', '.join(f'{qid(k)} = ?' for k in changes)
    sql = (f';WITH TargetRows AS (SELECT * FROM dbo.{qid(TABLE)} WITH (UPDLOCK, HOLDLOCK) WHERE {wh}) '
           f'UPDATE TargetRows SET {assignments}, [LastModified] = GETDATE()')
    cur.execute(sql, *(list(changes.values()) + params))
    if cur.rowcount not in (1,-1):
        raise RuntimeError('UPDATE tidak memengaruhi tepat satu record')


def deployment(action, keys, values, backup_name):
    merged = dict(keys)
    merged.update(values)
    names = {c: '@V_' + c for c in merged}
    old_names = {c: '@OLD_' + c for c in keys}
    declares = '\n'.join([f'DECLARE {old_names[c]} {"INT" if c in NUMERIC else "NVARCHAR(MAX)"} = {sql_literal(v)};' for c,v in keys.items()] + [f'DECLARE {names[c]} {"INT" if c in NUMERIC else "NVARCHAR(MAX)"} = {sql_literal(v)};' for c,v in merged.items()])
    wh = ' AND '.join(f'{qid(c)} = {old_names[c]}' for c in keys)
    if action == 'INSERT':
        cols = ', '.join(qid(c) for c in COLUMNS)
        vals = ', '.join(names[c] for c in COLUMNS)
        mutation = (f"IF EXISTS (SELECT 1 FROM dbo.{qid(TABLE)} WITH (UPDLOCK, HOLDLOCK) WHERE {wh})\n"
                    "    THROW 52001, 'Record sudah ada.', 1;\n"
                    f'INSERT INTO dbo.{qid(TABLE)} ({cols}, [InsertDate], [LastModified])\n'
                    f'VALUES ({vals}, GETDATE(), GETDATE());\n'
                    "IF @@ROWCOUNT <> 1 THROW 52002, 'INSERT tidak tepat satu record.', 1;")
    else:
        setters = ', '.join(f'{qid(c)} = {names[c]}' for c in values)
        mutation = (f"IF (SELECT COUNT(*) FROM dbo.{qid(TABLE)} WITH (UPDLOCK, HOLDLOCK) WHERE {wh}) <> 1\n"
                    "    THROW 52003, 'UPDATE membutuhkan satu record.', 1;\n"
                    f';WITH TargetRows AS (SELECT * FROM dbo.{qid(TABLE)} WITH (UPDLOCK, HOLDLOCK) WHERE {wh})\n'
                    f'UPDATE TargetRows SET {setters}, [LastModified] = GETDATE();\n'
                    "IF @@ROWCOUNT <> 1 THROW 52004, 'UPDATE tidak tepat satu record.', 1;")
    new_keys = dict(keys)
    if action == 'UPDATE':
        new_keys.update({c: values[c] for c in KEYS if c in values})
    new_wh = ' AND '.join(f'{qid(c)} = {names[c] if action == "UPDATE" and c in values else old_names[c]}' for c in new_keys)
    select = f'SELECT * FROM dbo.{qid(TABLE)} WHERE {new_wh};'
    return f"""USE [{DB}];
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;
GO
-- {ACTIVITY} | {TABLE} | {action}
-- Generated {datetime.now():%Y-%m-%d %H:%M:%S}
-- Source backup: dbo.{backup_name}
-- Default ROLLBACK. Ubah @ApproveCommit = 1 setelah review.
{declares}
DECLARE @ApproveCommit BIT = 0;
DECLARE @BackupName SYSNAME = N'{TABLE}_Backup_' +
    CONVERT(CHAR(8), GETDATE(), 112) + N'_' +
    REPLACE(REPLACE(CONVERT(VARCHAR(12), GETDATE(), 114), ':', ''), '.', '') + N'_' +
    RIGHT(REPLACE(CONVERT(VARCHAR(36), NEWID()), '-', ''), 8);
DECLARE @BackupSQL NVARCHAR(MAX);
IF DB_NAME() <> N'{DB}' THROW 52010, 'Database tidak sesuai.', 1;
IF @V_Activity <> N'{ACTIVITY}' THROW 52011, 'Activity tidak sesuai.', 1;
IF @ApproveCommit NOT IN (0,1) OR @ApproveCommit IS NULL THROW 52012, 'ApproveCommit invalid.', 1;

-- Backup di luar transaksi data agar tetap ada setelah ROLLBACK.
IF OBJECT_ID(N'dbo.' + @BackupName, N'U') IS NOT NULL THROW 52013, 'Backup sudah ada.', 1;
SET @BackupSQL = N'SELECT * INTO dbo.' + QUOTENAME(@BackupName) + N' FROM dbo.{TABLE};';
EXEC sys.sp_executesql @BackupSQL;
PRINT N'Backup: dbo.' + @BackupName;

BEGIN TRY
    BEGIN TRANSACTION;
    {mutation}
    IF (SELECT COUNT(*) FROM dbo.{qid(TABLE)} WHERE {new_wh}) <> 1
        THROW 52014, 'Verifikasi gagal.', 1;
    PRINT N'VERIFIKASI BELUM COMMIT';
    {select}
    IF @ApproveCommit = 1
    BEGIN
        COMMIT TRANSACTION;
        PRINT N'COMMIT berhasil';
    END
    ELSE
    BEGIN
        ROLLBACK TRANSACTION;
        PRINT N'ROLLBACK berhasil';
    END
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
PRINT N'HASIL AKHIR';
{select}
GO
"""


def main():
    cfg = choose_activity_server(SERVERS)
    print(f'\n{ACTIVITY} | {HOST}:{cfg.port} | {DB}.dbo.{TABLE}')
    con = connect_sqlserver(cfg, DB)
    con.autocommit = False
    try:
        cur = con.cursor()
        try:
            cur.execute('SELECT OBJECT_ID(?, ?)', f'dbo.{TABLE}', 'U')
            if cur.fetchone()[0] is None:
                raise RuntimeError(f'Tabel dbo.{TABLE} tidak ditemukan')
            con.rollback()
            print('1. INSERT\n2. UPDATE\n0. Keluar')
            opt = input('Pilih proses: ').strip()
            if opt == '0':
                return
            if opt not in ('1','2'):
                raise ValueError('Pilihan tidak valid')
            action = 'INSERT' if opt == '1' else 'UPDATE'
            if action == 'INSERT':
                values = input_data()
                keys = {k:values[k] for k in KEYS}
                if read_record(cur, keys):
                    raise ValueError('Record sudah ada. Gunakan UPDATE.')
                show_record('PREVIEW INSERT', values)
            else:
                keys, selected_row = choose_update_target(cur)
                show_record('DATA SEBELUM UPDATE', selected_row)
                values = input_data(update=True)
                show_record('PREVIEW PERUBAHAN', values)
            if input('Buat backup dan jalankan transaksi? (y/n) [n]: ').strip().lower() != 'y':
                return
            con.rollback()
            backup_name = backup(cfg)
            verify_keys = dict(keys)
            if action == 'UPDATE':
                verify_keys.update({k: v for k, v in values.items() if k in KEYS})
                if verify_keys != keys and read_record(cur, verify_keys):
                    raise ValueError('Identitas baru sudah digunakan record lain')
                update_record(cur, keys, values)
            else:
                insert_record(cur, values)
            after = read_record(cur, verify_keys)
            if len(after) != 1:
                raise RuntimeError('Verifikasi gagal setelah UPDATE')
            show_record('HASIL SEMENTARA (BELUM COMMIT)', after[0])
            if input('Ketik COMMIT untuk menyimpan, lainnya ROLLBACK: ').strip() != 'COMMIT':
                con.rollback()
                print('ROLLBACK berhasil. Backup tetap tersedia.')
                return
            con.commit()
            print('COMMIT berhasil.')
        except BaseException:
            con.rollback()
            raise
        finally:
            cur.close()
    finally:
        con.close()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f'{ACTIVITY}_{action}_{datetime.now():%Y%m%d_%H%M%S_%f}.sql'
    path.write_text(deployment(action, keys, values, backup_name), encoding='utf-8')
    try:
        path.chmod(0o600)
    except OSError:
        pass
    print('SQL deployment:', path)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nDibatalkan.')
    except Exception as exc:
        print(f'ERROR {type(exc).__name__}: {exc}')
        raise
