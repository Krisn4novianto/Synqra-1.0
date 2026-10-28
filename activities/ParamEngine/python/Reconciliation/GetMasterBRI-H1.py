"""Transactional INSERT/UPDATE wizard for ParamEngine.dbo.ParamGetMasterBRI.

Run from project root:
    ./.venv/bin/python activities/ParamEngine/python/GetMasterBRI-H1.py
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

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
TARGET_HOST = '172.18.246.102'
DATABASE = 'ParamEngine'
TABLE = 'dbo.ParamGetMasterBRI'
ACTIVITY = 'GetMasterBRI-H1'
OUTPUT = Path(__file__).resolve().parent.parent / 'output' / ACTIVITY
FIELDS = ['ProductId', 'Task', 'Activity', 'SelectQry', 'WhereQry', 'TargetDB', 'TargetTable', 'isActive', 'SourceDBLocation']
KEYS = ['ProductId', 'Task', 'Activity']
DISPLAY = FIELDS + ['InsertDate', 'LastModified']
REQUIRED = {'ProductId', 'Task', 'SelectQry', 'WhereQry', 'TargetDB', 'TargetTable', 'SourceDBLocation'}
DEFAULTS = {'TargetDB': 'ReconciliationDBName', 'TargetTable': 'MasterBRI', 'isActive': 1, 'SourceDBLocation': 'source'}


def ident(value):
    return '[' + value.replace(']', ']]') + ']'


def sql_literal(value):
    if value is None:
        return 'NULL'
    if isinstance(value, int):
        return str(value)
    return "N'" + str(value).replace("'", "''") + "'"


def prompt(name, default=None, multiline=False):
    if multiline:
        print(f'\n{name} (akhiri input dengan satu baris berisi .SELESAI):')
        lines = []
        while True:
            line = input('> ')
            if line.strip() == '.SELESAI':
                break
            lines.append(line)
        result = '\n'.join(lines).strip()
        return result if result else default
    hint = f' [{default}]' if default is not None else ''
    result = input(f'{name}{hint}: ').strip()
    return result if result else default


def validate(field, value):
    if field == 'isActive':
        if str(value) not in ('0', '1'):
            raise ValueError('isActive hanya boleh 0 atau 1')
        return int(value)
    if field in REQUIRED and (value is None or not str(value).strip()):
        raise ValueError(f'{field} wajib diisi')
    return value


def display_record(values, title, record_number=None):
    print('\n' + '=' * 76)
    print(title)
    print('=' * 76)
    if record_number is not None:
        print(f'RECORD {record_number}')
    width = max(map(len, values)) if values else 15
    for field, value in values.items():
        rendered = 'NULL' if value is None else str(value)
        if '\n' not in rendered:
            print(f'{field:<{width}} = {rendered}')
        else:
            lines = rendered.splitlines()
            print(f'{field:<{width}} = {lines[0]}')
            for line in lines[1:]:
                print(' ' * (width + 3) + line)
    print('-' * 76)


def show_rows(records, title):
    print(f'\n=== {title} ===')
    for number, record in enumerate(records, 1):
        display_record(record, title, f'{number}/{len(records)}')
    print(f'Total record: {len(records)}')


def fetch(cursor, key, lock=False):
    where = ' AND '.join(f'{ident(k)} = ?' for k in key)
    hint = ' WITH (UPDLOCK, HOLDLOCK)' if lock else ''
    cursor.execute(
        f'SELECT {", ".join(map(ident, DISPLAY))} FROM {TABLE}{hint} WHERE {where}',
        *list(key.values()),
    )
    return [dict(zip(DISPLAY, row)) for row in cursor.fetchall()]


def collect_insert():
    print('\n=== INPUT INSERT ===')
    result = {}
    for field in FIELDS:
        if field == 'Activity':
            result[field] = ACTIVITY
            print(f'Activity = {ACTIVITY} (otomatis)')
            continue
        value = prompt(field, DEFAULTS.get(field), multiline=field in ('SelectQry', 'WhereQry'))
        result[field] = validate(field, value)
    return result


def collect_key():
    print('\n=== FILTER RECORD UPDATE ===')
    key = {}
    for field in KEYS:
        if field == 'Activity':
            key[field] = ACTIVITY
            print(f'Activity = {ACTIVITY} (otomatis)')
        else:
            key[field] = validate(field, prompt(field))
    return key


def collect_changes():
    choices = [field for field in FIELDS if field not in KEYS]
    print('\n=== PILIH FIELD UPDATE ===')
    for number, field in enumerate(choices, 1):
        print(f'{number}. {field}')
    raw = input('Nomor field (contoh 1,2,4): ').strip()
    try:
        numbers = [int(x.strip()) for x in raw.split(',')]
        if not numbers or len(set(numbers)) != len(numbers) or any(x < 1 or x > len(choices) for x in numbers):
            raise ValueError
    except ValueError as exc:
        raise ValueError('Pilihan field UPDATE tidak valid') from exc
    changes = {}
    for number in numbers:
        field = choices[number - 1]
        changes[field] = validate(field, prompt('Nilai baru ' + field, multiline=field in ('SelectQry', 'WhereQry')))
    return changes


def create_backup(cfg):
    name = 'ParamGetMasterBRI_Backup_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    connection = connect_sqlserver(cfg, DATABASE)
    try:
        connection.autocommit = True
        cursor = connection.cursor()
        try:
            cursor.execute(f'SELECT * INTO dbo.{ident(name)} FROM {TABLE}')
        finally:
            cursor.close()
    finally:
        connection.close()
    print('Backup berhasil: dbo.' + name)
    return name


def insert_record(cursor, data):
    key = {field: data[field] for field in KEYS}
    if fetch(cursor, key, lock=True):
        raise ValueError('Record ProductId + Task + Activity sudah ada. Gunakan UPDATE.')
    cols = ', '.join(map(ident, FIELDS))
    marks = ', '.join('?' for _ in FIELDS)
    cursor.execute(
        f'INSERT INTO {TABLE} ({cols}, [InsertDate], [LastModified]) '
        f'VALUES ({marks}, GETDATE(), GETDATE())',
        *[data[field] for field in FIELDS],
    )
    if cursor.rowcount not in (1, -1):
        raise RuntimeError('INSERT tidak memengaruhi tepat satu record')


def update_record(cursor, key, changes):
    if len(fetch(cursor, key, lock=True)) != 1:
        raise ValueError('UPDATE harus menemukan tepat satu record')
    where = ' AND '.join(f'{ident(field)} = ?' for field in key)
    assignments = ', '.join(f'{ident(field)} = ?' for field in changes)
    cursor.execute(
        f';WITH TargetRows AS (SELECT * FROM {TABLE} WITH (UPDLOCK, HOLDLOCK) WHERE {where}) '
        f'UPDATE TargetRows SET {assignments}, [LastModified] = GETDATE()',
        *(list(changes.values()) + list(key.values())),
    )
    if cursor.rowcount not in (1, -1):
        raise RuntimeError('UPDATE tidak memengaruhi tepat satu record')


def deployment_sql(action, key, values, backup_source):
    stamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    decl = []
    for field, value in key.items():
        dtype = 'INT' if field == 'isActive' else 'NVARCHAR(MAX)'
        decl.append(f'DECLARE @Filter_{field} {dtype} = {sql_literal(value)};')
    for field, value in values.items():
        dtype = 'INT' if field == 'isActive' else 'NVARCHAR(MAX)'
        decl.append(f'DECLARE @New_{field} {dtype} = {sql_literal(value)};')
    where = ' AND '.join(f'{ident(field)} = @Filter_{field}' for field in key)
    if action == 'INSERT':
        cols = ', '.join(map(ident, FIELDS))
        newvals = ', '.join('@New_' + field for field in FIELDS)
        mutation = (
            f"IF EXISTS (SELECT 1 FROM {TABLE} WITH (UPDLOCK, HOLDLOCK) WHERE {where})\n"
            "    THROW 53101, 'INSERT ditolak: record sudah ada.', 1;\n"
            f'INSERT INTO {TABLE} ({cols}, [InsertDate], [LastModified])\n'
            f'VALUES ({newvals}, GETDATE(), GETDATE());\n'
            "IF @@ROWCOUNT <> 1 THROW 53102, 'INSERT gagal: jumlah record tidak sesuai.', 1;"
        )
    else:
        setters = ', '.join(f'{ident(field)} = @New_{field}' for field in values)
        mutation = (
            f"IF (SELECT COUNT(*) FROM {TABLE} WITH (UPDLOCK, HOLDLOCK) WHERE {where}) <> 1\n"
            "    THROW 53103, 'UPDATE harus menemukan satu record.', 1;\n"
            f';WITH TargetRows AS (SELECT * FROM {TABLE} WITH (UPDLOCK, HOLDLOCK) WHERE {where})\n'
            f'UPDATE TargetRows SET {setters}, [LastModified] = GETDATE();\n'
            "IF @@ROWCOUNT <> 1 THROW 53104, 'UPDATE gagal: jumlah record tidak sesuai.', 1;"
        )
    return f'''USE [{DATABASE}];
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;
GO
/*==============================================================================
  {ACTIVITY} - {TABLE}
  Action: {action} | Generated: {stamp}
  Backup saat eksekusi Python: dbo.{backup_source}
  SOP: DECLARE -> Validasi -> Backup -> {action} -> SELECT -> COMMIT/ROLLBACK -> SELECT
  Default ROLLBACK. Ubah @ApproveCommit menjadi 1 setelah review.
==============================================================================*/

/* TAHAP 1: PARAMETER DAN VALIDASI */
{chr(10).join(decl)}
DECLARE @ApproveCommit BIT = 0;
DECLARE @BackupName SYSNAME = N'ParamGetMasterBRI_Backup_' +
    CONVERT(CHAR(8), GETDATE(), 112) + N'_' +
    REPLACE(REPLACE(CONVERT(VARCHAR(12), GETDATE(), 114), ':', ''), '.', '') + N'_' +
    RIGHT(REPLACE(CONVERT(VARCHAR(36), NEWID()), '-', ''), 8);
DECLARE @BackupSQL NVARCHAR(MAX);
DECLARE @Committed BIT = 0;
IF DB_NAME() <> N'{DATABASE}' THROW 53110, 'Database salah.', 1;
IF @Filter_Activity <> N'{ACTIVITY}' THROW 53111, 'Activity salah.', 1;
IF @ApproveCommit IS NULL OR @ApproveCommit NOT IN (0,1)
    THROW 53112, 'ApproveCommit harus 0 atau 1.', 1;
IF OBJECT_ID(N'{TABLE}', N'U') IS NULL THROW 53113, 'Tabel tidak ditemukan.', 1;

/* TAHAP 2: BACKUP TABEL (PERSISTEN MESKIPUN ROLLBACK) */
SET @BackupSQL = N'SELECT * INTO dbo.' + QUOTENAME(@BackupName) + N' FROM {TABLE};';
EXEC sys.sp_executesql @BackupSQL;
PRINT N'Backup berhasil: dbo.' + @BackupName;

BEGIN TRY
    BEGIN TRANSACTION;
    /* TAHAP 3: {action} */
{mutation}

    /* TAHAP 4: VERIFIKASI SEBELUM COMMIT */
    IF (SELECT COUNT(*) FROM {TABLE} WHERE {where}) <> 1
        THROW 53114, 'Verifikasi gagal: jumlah record tidak sesuai.', 1;
    SELECT N'BELUM COMMIT' AS StatusTransaksi,
        {', '.join(map(ident, DISPLAY))}
    FROM {TABLE} WHERE {where};

    /* TAHAP 5: COMMIT ATAU ROLLBACK */
    IF @ApproveCommit = 1
    BEGIN
        COMMIT TRANSACTION;
        SET @Committed = 1;
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

/* TAHAP 6: SELECT HASIL AKHIR */
SELECT CASE WHEN @Committed = 1 THEN N'COMMITTED' ELSE N'ROLLED BACK' END AS StatusDeployment,
    {', '.join(map(ident, DISPLAY))}
FROM {TABLE} WHERE {where};
GO
'''


def target_config():
    cfg = choose_activity_server(SERVERS)
    print(f'\n=== SERVER PARAMENGINE: {cfg.host}:{cfg.port} ===')
    print(f'Login: {cfg.username} | Profil: {SERVER_KEY}')
    connection = connect_sqlserver(cfg, DATABASE)
    try:
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT OBJECT_ID(N'dbo.ParamGetMasterBRI', N'U')")
            if cursor.fetchone()[0] is None:
                raise RuntimeError('Tabel dbo.ParamGetMasterBRI tidak ditemukan atau tidak terlihat oleh login.')
        finally:
            cursor.close()
    finally:
        connection.close()
    print('Koneksi database dan tabel: OK')
    return cfg


def main():
    cfg = target_config()
    print(f'\n=== {ACTIVITY} | {TABLE} ===')
    print('1. INSERT\n2. UPDATE\n0. Keluar')
    choice = input('Pilih proses: ').strip()
    if choice == '0':
        return
    if choice not in ('1', '2'):
        raise ValueError('Pilihan proses tidak valid')
    action = 'INSERT' if choice == '1' else 'UPDATE'
    connection = connect_sqlserver(cfg, DATABASE)
    connection.autocommit = False
    committed = False
    try:
        cursor = connection.cursor()
        try:
            if action == 'INSERT':
                values = collect_insert()
                key = {field: values[field] for field in KEYS}
                if fetch(cursor, key):
                    raise ValueError('Record sudah ada, gunakan UPDATE.')
                display_record(values, 'PREVIEW INSERT')
            else:
                key = collect_key()
                existing = fetch(cursor, key)
                show_rows(existing, 'DATA SEBELUM UPDATE')
                if len(existing) != 1:
                    raise ValueError(f'UPDATE membutuhkan tepat satu record, ditemukan {len(existing)}')
                if input('Lanjut UPDATE? (y/n): ').strip().lower() != 'y':
                    return
                values = collect_changes()
                display_record(values, 'PREVIEW PERUBAHAN UPDATE')
            if input('Backup dan mulai transaksi? (y/n): ').strip().lower() != 'y':
                return
            connection.rollback()  # release SELECT transaction before backup on separate connection
            backup_name = create_backup(cfg)
            if action == 'INSERT':
                insert_record(cursor, values)
            else:
                update_record(cursor, key, values)
            after = fetch(cursor, key)
            if len(after) != 1:
                raise RuntimeError('Verifikasi gagal: jumlah record bukan satu')
            show_rows(after, 'HASIL SEMENTARA (BELUM COMMIT)')
            if input('Ketik COMMIT untuk menyimpan; lainnya ROLLBACK: ').strip() != 'COMMIT':
                connection.rollback()
                print('ROLLBACK berhasil; perubahan tidak disimpan.')
                return
            connection.commit()
            committed = True
            print('COMMIT berhasil.')
        finally:
            cursor.close()
    except BaseException:
        if not committed:
            connection.rollback()
        raise
    finally:
        connection.close()

    OUTPUT.mkdir(parents=True, exist_ok=True)
    destination = OUTPUT / f'{ACTIVITY}_{action}_{datetime.now():%Y-%m-%d_%H%M%S_%f}.sql'
    destination.write_text(deployment_sql(action, key, values, backup_name), encoding='utf-8')
    try:
        destination.chmod(0o600)
    except OSError:
        pass
    print('SQL deployment:', destination)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nDibatalkan; transaksi yang belum COMMIT di-rollback.')
    except Exception as exc:
        print(f'ERROR {type(exc).__name__}: {exc}')
        raise
