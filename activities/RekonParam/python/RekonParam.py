#!/usr/bin/env python3
"""
===============================================================================
SOP / STANDARD OPERATING PROCEDURE - SYNQRA REKONPARAM
===============================================================================
TUJUAN
    Wizard untuk INSERT / UPDATE dbo.ParamFitur dan dbo.ParamJoin pada
    database RekonParam dengan backup snapshot sebelum perubahan.

PERSIAPAN
    1. Jalankan dari root repository.
    2. Pastikan db_config.py memuat profil server 172.18.135.205 atau localhost.
    3. Pastikan db_connection.py dan activities/RekonParam/common.py tersedia.
    4. Pastikan akun database memiliki izin SELECT, INSERT, UPDATE dan transaksi.
    5. Uji di localhost terlebih dahulu sebelum menjalankan di produksi.

CARA MENJALANKAN
    ./.venv/bin/python activities/RekonParam/python/RekonParam.py

LANGKAH OPERASIONAL
    1. Pilih server dari profil tersimpan (tanpa mengetik ulang password).
    2. Pilih INSERT atau UPDATE.
    3. INSERT -> pilih ParamFitur (preset) atau ParamJoin (IDFitur existing).
    4. UPDATE -> pilih ParamFitur atau ParamJoin, filter dan pilih record.
    5. Isi perubahan, baca PREVIEW, dan konfirmasi dengan mengetik YA.
    6. Program menyimpan snapshot JSON sebelum mengubah record database.
    7. Periksa hasil aktual yang masih berada di dalam transaksi.
    8. Ketik COMMIT untuk menyimpan, atau input lain untuk ROLLBACK.
    9. Setelah COMMIT berhasil, periksa script deployment yang dibuat.

LOKASI OUTPUT
    Backup JSON   : output/RekonParam/backup/
    Deployment SQL: output/RekonParam/

ATURAN KEAMANAN
    - DBPass tidak boleh ditampilkan dalam preview atau verifikasi terminal.
    - Snapshot dapat berisi data sensitif, termasuk DBPass terenkripsi.
      Lindungi file backup, batasi akses, dan jangan unggah ke Git.
    - Backup JSON adalah snapshot data, BUKAN backup database SQL Server .bak.
    - Restore snapshot belum otomatis; pemulihan harus diverifikasi DBA.
    - Script deployment dibuat hanya setelah COMMIT berhasil.
    - Jangan mengubah default ROLLBACK pada script deployment tanpa review.

JIKA TERJADI ERROR
    - Sebelum COMMIT: transaksi dibatalkan (ROLLBACK).
    - Sesudah COMMIT: perubahan sudah tersimpan; gunakan snapshot untuk
      investigasi dan rencanakan restore secara terkontrol.
    - Periksa koneksi, permission, trigger, constraint, dan log SQL Server.

CATATAN
    Script ini bergantung pada modul repository yang disebutkan di atas.
    Pengujian sintaks tidak menggantikan pengujian transaksi pada SQL Server.
===============================================================================
"""
import sys
import json
import os
import base64
import hashlib
import tempfile
from pathlib import Path
from datetime import datetime, date, time
from decimal import Decimal
from uuid import UUID

HERE = Path(__file__).resolve()
ROOT_DIR = next((p for p in HERE.parents if (p / 'db_connection.py').is_file() and (p / 'db_config.py').is_file()), None)
if ROOT_DIR is None:
    raise RuntimeError('Root repository dengan db_connection.py dan db_config.py tidak ditemukan.')
sys.path.insert(0, str(ROOT_DIR))
from db_connection import connect_sqlserver
from db_config import SERVERS
from activities.RekonParam.common import sql_literal, print_query_results

DATABASE = 'RekonParam'
OUTPUT = ROOT_DIR / 'output' / 'RekonParam'
BACKUPS = OUTPUT / 'backup'
WIDTH = 78
PRESETS = [
    ('Leasing - Update MasterBRI', 'Leasing', 'Leasing', '', 'BuildMasterBRI'),
    ('Leasing - Rekon BAF - MasterBRI vs SYB', 'Leasing', 'Leasing', 'BAF', 'RekonBRIvsSYB'),
    ('Leasing - Rekon FIF - MasterBRI vs SYB', 'Leasing', 'Leasing', 'FIF', 'RekonBRIvsSYB'),
    ('Leasing - Rekon FINANSIA - MasterBRI vs SYB', 'Leasing', 'Leasing', 'FINANSIA', 'RekonBRIvsSYB'),
    ('Leasing - Rekon OTO - MasterBRI vs SYB', 'Leasing', 'Leasing', 'OTO', 'RekonBRIvsSYB'),
    ('Leasing - Rekon VERENA - MasterBRI vs SYB', 'Leasing', 'Leasing', 'VERENA', 'RekonBRIvsSYB'),
    ('Leasing - Rekon WOM - MasterBRI vs SYB', 'Leasing', 'Leasing', 'WOM', 'RekonBRIvsSYB'),
    ('Kisel - Update Master BRI', 'BrilinkKisel', 'Brilink', 'Kisel', 'UpdateMasterBRI'),
    ('Leasing - Cleansing EC DDTRN', 'Leasing', 'Leasing', '', 'CleansingDDTRN'),
    ('Leasing - Rekon BAF - DDTRN vs SYB', 'Leasing', 'Leasing', 'BAF', 'RekonDDTRNvsSYB'),
]
# Value below is a legacy ParamFitur preset value, NOT a SQL Server login password.
# Override via environment variable for deployment without embedding it in generated SQL.
PRESET_DB_PASS = os.environ.get('REKONPARAM_PRESET_DBPASS', 'Â²ååé¢äÖ£¤¥')
PRESET_DB_HOST = '172.18.135.205'
PRESET_DB_USER = 'sa'

JOIN_COLUMNS = ['IDFitur', 'OrderExecute', 'Note', 'Source1Table', 'Source2Table',
                'Source1Where', 'Source2Where', 'Source1DataDateCol', 'Source2DataDateCol']
for i in range(1, 11):
    JOIN_COLUMNS += [f'Source1KeyJoinCol{i}', f'Source2KeyJoinCol{i}']
JOIN_COLUMNS += ['Source1PartitionCol', 'Source2PartitionCol', 'Source1OrderCol', 'Source2OrderCol']
for i in range(1, 11):
    JOIN_COLUMNS += [f'Source1UpdateCol{i}', f'Source2UpdateData{i}']
for i in range(1, 11):
    JOIN_COLUMNS += [f'Source2UpdateCol{i}', f'Source1UpdateData{i}']
JOIN_COLUMNS += ['Source1isMoveDataMatch', 'Source2isMoveDataMatch', 'Source1UniqueCol',
                 'Source2UniqueCol', 'Source1FlagMatchCol', 'Source2FlagMatchCol',
                 'Source1FieldSelectMove', 'Source2FieldSelectMove',
                 'Source1MoveTargetTable', 'Source2MoveTargetTable', 'isActive',
                 'Source1SelectCol', 'Source2SelectCol']
NUMERIC = {'OrderExecute', 'Source1isMoveDataMatch', 'Source2isMoveDataMatch', 'isActive'}
PF_EDIT = ['Name', 'IPServer', 'DBName', 'DBUser', 'LogActivityModul',
           'LogActivitySubModul', 'LogActivityEntity', 'IsActive']
PF_DISPLAY = ['IDFitur'] + PF_EDIT


def heading(title):
    print('\n' + '=' * WIDTH + '\n  ' + title + '\n' + '=' * WIDTH)


def section(title):
    print('\n' + '-' * WIDTH + '\n  ' + title + '\n' + '-' * WIDTH)


def info(message):
    print('[INFO] ' + str(message))


def require_yes(message='Ketik YA untuk melanjutkan: '):
    return input(message).strip().upper() == 'YA'


def choose(title, choices):
    while True:
        section(title)
        for key, label in choices:
            print(f'  [{key}] {label}')
        value = input('Pilihan: ').strip()
        if value in {str(k) for k, _ in choices}:
            return value
        print('[WARN] Pilihan tidak valid.')


def qident(name):
    return '[' + str(name).replace(']', ']]') + ']'


def sqlval(value):
    if value is None:
        return 'NULL'
    if isinstance(value, bool):
        return '1' if value else '0'
    if isinstance(value, (int, Decimal)):
        return str(value)
    return sql_literal(str(value))


def typed_json(value):
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {'__type__': 'bytes', 'base64': base64.b64encode(bytes(value)).decode('ascii')}
    if isinstance(value, (datetime, date, time)):
        return {'__type__': type(value).__name__, 'value': value.isoformat()}
    if isinstance(value, Decimal):
        return {'__type__': 'decimal', 'value': str(value)}
    if isinstance(value, UUID):
        return {'__type__': 'uuid', 'value': str(value)}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f'Tipe kolom tidak didukung backup: {type(value).__name__}')


def fetch_dicts(cur, sql, *params):
    cur.execute(sql, *params)
    names = [c[0] for c in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def show_rows(rows, columns=None):
    if not rows:
        print('  (tidak ada record)')
        return
    columns = columns or list(rows[0])
    print_query_results(columns, [[r.get(k) for k in columns] for r in rows])


def save_backup(cur, cfg, operation, ids=None, *, include_all=False):
    """Snapshot durable BEFORE first write, using same transaction/connection.

    Includes all columns and DBPass ciphertext. Files must be access-controlled.
    """
    if not include_all and not ids:
        raise ValueError('Backup membutuhkan IDFitur atau include_all=True.')
    ids = sorted(set(int(x) for x in (ids or [])))
    tables = {}
    for table in ('ParamFitur', 'ParamJoin', 'ParamFiturCekLogActivity'):
        if include_all:
            query = f'SELECT * FROM dbo.{qident(table)};'
            rows = fetch_dicts(cur, query)
        else:
            marks = ', '.join('?' for _ in ids)
            rows = fetch_dicts(cur, f'SELECT * FROM dbo.{qident(table)} WHERE IDFitur IN ({marks});', *ids)
        tables[table] = {
            'columns': list(rows[0]) if rows else [],
            'rows': [{k: typed_json(v) for k, v in row.items()} for row in rows],
        }
        if not rows:
            cur.execute(f'SELECT TOP (0) * FROM dbo.{qident(table)};')
            tables[table]['columns'] = [c[0] for c in cur.description]
    payload = {
        'format': 'RekonParamSnapshotV1', 'timestamp': datetime.now().isoformat(),
        'server': str(cfg.host), 'port': int(cfg.port), 'database': DATABASE,
        'operation': operation, 'scope': 'full_tables' if include_all else 'IDFitur',
        'ids': ids, 'warning': 'Contains DBPass ciphertext and potentially sensitive data. Not an automatic restore script.',
        'tables': tables,
    }
    BACKUPS.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    safe_op = ''.join(ch if ch.isalnum() or ch in '-_' else '_' for ch in operation)
    safe_host = ''.join(ch if ch.isalnum() or ch in '-_' else '_' for ch in str(cfg.host))
    target = BACKUPS / f'{stamp}_{safe_host}_{safe_op}.json'
    fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(payload, out, ensure_ascii=False, indent=2)
            out.flush()
            os.fsync(out.fileno())
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    info(f'Backup sebelum perubahan: {target}')
    info('Snapshot JSON mencakup seluruh kolom, termasuk DBPass terenkripsi. Jaga akses file.')
    return target


def save_deployment(text, operation):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    target = OUTPUT / f'{stamp}_{operation}.sql'
    target.write_text(text, encoding='utf-8')
    info(f'Deployment SQL (default ROLLBACK): {target}')


def deployment(statements):
    return '\n'.join([
        f'USE [{DATABASE}];', 'GO', 'SET XACT_ABORT ON;', 'BEGIN TRY',
        '    BEGIN TRANSACTION;', *['    ' + s for s in statements],
        '    -- Periksa hasil sebelum menyimpan.',
        '    ROLLBACK TRANSACTION; -- Default aman',
        '    -- COMMIT TRANSACTION;', 'END TRY', 'BEGIN CATCH',
        '    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;',
        '    THROW;', 'END CATCH;', 'GO', '',
    ])


def server_menu():
    profiles = []
    for key, cfg in SERVERS.items():
        host = str(cfg.host).strip().lower()
        if host in {'172.18.135.205', 'localhost', '127.0.0.1', '::1'}:
            profiles.append((key, cfg))
    profiles.sort(key=lambda pair: 0 if str(pair[1].host) == '172.18.135.205' else 1)
    if not profiles:
        raise RuntimeError('Tidak ada profil server 172.18.135.205 / localhost di db_config.SERVERS.')
    options = [(str(i), f'{cfg.name} ({cfg.host}:{cfg.port})') for i, (_, cfg) in enumerate(profiles, 1)]
    value = choose('PILIH PROFIL SERVER', options + [('0', 'Keluar')])
    return None if value == '0' else profiles[int(value) - 1][1]


def select_record(cfg, table):
    """Filter multiple arbitrary table columns; never expose DBPass as filter/display."""
    while True:
        conn = connect_sqlserver(cfg, DATABASE)
        try:
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute(f'SELECT TOP (0) * FROM dbo.{qident(table)};')
            columns = [c[0] for c in cur.description if c[0].lower() != 'dbpass']
            section(f'FILTER {table.upper()}')
            for i, col in enumerate(columns, 1):
                print(f'  [{i:>2}] {col}')
            raw = input('Nomor kolom filter (contoh 1,3; 0=batal): ').strip()
            if raw == '0':
                return None
            try:
                nums = [int(s.strip()) for s in raw.split(',')]
                if not nums or len(set(nums)) != len(nums) or any(n < 1 or n > len(columns) for n in nums):
                    raise ValueError
            except ValueError:
                print('[WARN] Nomor filter tidak valid.')
                continue
            clauses, params = [], []
            for n in nums:
                column = columns[n - 1]
                value = input(f'Nilai {column} (NULL=SQL NULL): ').strip()
                if value.upper() == 'NULL':
                    clauses.append(f'{qident(column)} IS NULL')
                else:
                    clauses.append(f'CONVERT(NVARCHAR(MAX), {qident(column)}) = ?')
                    params.append(value)
            select_cols = [c for c in columns if c.lower() != 'dbpass']
            sql = ('SELECT ' + ', '.join(qident(c) for c in select_cols) +
                   f' FROM dbo.{qident(table)} WHERE ' + ' AND '.join(clauses) +
                   ' ORDER BY IDFitur' + (', OrderExecute' if table == 'ParamJoin' else '') + ';')
            rows = fetch_dicts(cur, sql, *params)
        finally:
            conn.close()
        if not rows:
            info('Tidak ada hasil. Coba filter lain.')
            continue
        section(f'HASIL FILTER: {len(rows)} RECORD')
        for i, row in enumerate(rows, 1):
            if table == 'ParamFitur':
                print(f" [{i}] IDFitur={row['IDFitur']} | {row.get('Name')} | {row.get('DBName')} | {row.get('LogActivityEntity')}")
            else:
                print(f" [{i}] IDFitur={row['IDFitur']} | Order={row['OrderExecute']} | {row.get('Source1Table')} vs {row.get('Source2Table')} | {row.get('Note')}")
        while True:
            value = input('Pilih nomor record (0=ulang filter): ').strip()
            if value == '0':
                break
            if value.isdigit() and 1 <= int(value) <= len(rows):
                return rows[int(value) - 1]
            print('[WARN] Pilihan tidak valid.')


def choose_pf_by_activity(cfg):
    while True:
        section('CARI PARAMFITUR BERDASARKAN MODUL & ENTITY')
        modul = input('Modul (0=batal): ').strip()
        if modul == '0':
            return None
        entity = input('Entity: ').strip()
        if not modul or not entity:
            info('Modul dan Entity wajib diisi.')
            continue
        conn = connect_sqlserver(cfg, DATABASE)
        try:
            conn.autocommit = True
            rows = fetch_dicts(conn.cursor(),
                'SELECT ' + ', '.join(qident(c) for c in PF_DISPLAY) +
                ' FROM dbo.ParamFitur WHERE LTRIM(RTRIM(LogActivityModul))=? '
                'AND LTRIM(RTRIM(LogActivityEntity))=? ORDER BY IDFitur;', modul, entity)
        finally:
            conn.close()
        if not rows:
            info('Tidak ditemukan. Ulangi pencarian.')
            continue
        for i, row in enumerate(rows, 1):
            print(f" [{i}] IDFitur={row['IDFitur']} | {row.get('Name')} | SubModul={row.get('LogActivitySubModul')} | DB={row.get('DBName')}")
        while True:
            raw = input('Pilih nomor (0=ulang): ').strip()
            if raw == '0':
                break
            if raw.isdigit() and 1 <= int(raw) <= len(rows):
                return rows[int(raw) - 1]
            info('Pilihan tidak valid.')


def parse_number(column, value):
    if value is None or (isinstance(value, str) and value.upper() == 'NULL'):
        if column == 'OrderExecute':
            raise ValueError('OrderExecute wajib diisi.')
        return None
    result = int(value)
    if column == 'OrderExecute' and result < 1:
        raise ValueError('OrderExecute minimal 1.')
    if column in {'isActive', 'Source1isMoveDataMatch', 'Source2isMoveDataMatch'} and result not in (0, 1):
        raise ValueError(f'{column} harus 0 atau 1.')
    return result


def prompt_join(idfitur, order, existing=None):
    existing = existing or {}
    section(f'INPUT PARAMJOIN | IDFitur={idfitur}, OrderExecute={order}')
    info('Enter mempertahankan default. Ketik NULL untuk SQL NULL. Ketik EMPTY untuk string kosong.')
    row = {'IDFitur': int(idfitur), 'OrderExecute': int(order)}
    for column in JOIN_COLUMNS[2:]:
        default = existing.get(column, 0 if column in NUMERIC else '')
        label = 'NULL' if default is None else str(default)
        raw = input(f'{column} [{label}]: ').strip()
        if not raw:
            value = default
        elif raw.upper() == 'NULL':
            value = None
        elif raw.upper() == 'EMPTY':
            value = ''
        else:
            value = raw
        if column in NUMERIC:
            value = parse_number(column, value)
        row[column] = value
    return row


def print_join_preview(row, old=None):
    section('PREVIEW PARAMJOIN')
    for col in JOIN_COLUMNS:
        value = row[col]
        if old is None or old.get(col) != value:
            print(f'  {col:<30}: {old.get(col) if old else "(baru)"} -> {value}')


def verify(cur, idfitur):
    section('HASIL AKTUAL DATABASE | BELUM COMMIT')
    for table in ('ParamFitur', 'ParamFiturCekLogActivity', 'ParamJoin'):
        cols = '*' if table != 'ParamFitur' else ', '.join(qident(c) for c in PF_DISPLAY)
        rows = fetch_dicts(cur, f'SELECT {cols} FROM dbo.{qident(table)} WHERE IDFitur=?;', idfitur)
        print(f'\n{table} ({len(rows)} record)')
        show_rows(rows)


def decision(conn):
    if input('\nKetik COMMIT untuk menyimpan; selain itu ROLLBACK: ').strip().upper() == 'COMMIT':
        conn.commit()
        print('[OK] COMMIT berhasil.')
        return True
    conn.rollback()
    print('[OK] ROLLBACK berhasil; perubahan tidak disimpan.')
    return False


def sync_log(cur, pf):
    modul = pf['LogActivityModul']
    entity = pf['LogActivityEntity']
    sub = pf.get('LogActivitySubModul') or ''
    cur.execute('''IF NOT EXISTS (SELECT 1 FROM dbo.ParamFiturCekLogActivity WITH (UPDLOCK,HOLDLOCK)
                    WHERE IDFitur=? AND LogActivityModul=? AND ISNULL(LogActivitySubModul,'')=? AND LogActivityEntity=?)
                    INSERT INTO dbo.ParamFiturCekLogActivity
                    (IDFitur, LogActivityModul, LogActivitySubModul, LogActivityEntity, LogActivityDateAdd, IsActive)
                    VALUES (?, ?, ?, ?, '0', '1');''',
                pf['IDFitur'], modul, sub, entity, pf['IDFitur'], modul, sub, entity)


def pf_identity_sql(pf):
    return ('SELECT @IDFitur = IDFitur FROM dbo.ParamFitur WHERE '
            f"IPServer={sqlval(pf['IPServer'])} AND DBName={sqlval(pf['DBName'])} "
            f"AND LogActivityModul={sqlval(pf['LogActivityModul'])} "
            f"AND ISNULL(LogActivitySubModul,'')={sqlval(pf.get('LogActivitySubModul') or '')} "
            f"AND LogActivityEntity={sqlval(pf['LogActivityEntity'])};")


def join_deployment(pf, row, action, original_order=None):
    lines = ['DECLARE @IDFitur INT;', pf_identity_sql(pf),
             "IF @IDFitur IS NULL THROW 50001, 'ParamFitur tidak ditemukan.', 1;"]
    if action == 'INSERT':
        cols = ', '.join(qident(c) for c in JOIN_COLUMNS)
        vals = ', '.join('@IDFitur' if c == 'IDFitur' else sqlval(row[c]) for c in JOIN_COLUMNS)
        lines.append(f'INSERT INTO dbo.ParamJoin ({cols}) VALUES ({vals});')
    else:
        assignments = ', '.join(f'{qident(c)}={sqlval(row[c])}' for c in JOIN_COLUMNS[2:])
        lines.append(f'UPDATE dbo.ParamJoin SET {assignments} WHERE IDFitur=@IDFitur AND OrderExecute={int(original_order)};')
        lines.append("IF @@ROWCOUNT <> 1 THROW 50002, 'Jumlah record UPDATE tidak sesuai.', 1;")
    lines.append('SELECT * FROM dbo.ParamJoin WHERE IDFitur=@IDFitur ORDER BY OrderExecute;')
    return deployment(lines)


def insert_pf(cfg):
    options = [(str(i), p[0]) for i, p in enumerate(PRESETS, 1)]
    selected = choose('INSERT | PILIH PRESET PARAMFITUR', options + [('0', 'Batal')])
    if selected == '0':
        return
    name, dbname, modul, sub, entity = PRESETS[int(selected) - 1]
    pf = {'Name': name, 'IPServer': PRESET_DB_HOST, 'DBName': dbname,
          'DBUser': PRESET_DB_USER, 'LogActivityModul': modul,
          'LogActivitySubModul': sub, 'LogActivityEntity': entity, 'IsActive': 1}
    section('PREVIEW INSERT PARAMFITUR')
    for k, v in pf.items():
        print(f'  {k}: {v}')
    print('  DBPass: [DIRAHASIAKAN]')
    if not require_yes():
        return
    conn = connect_sqlserver(cfg, DATABASE)
    committed = False
    try:
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute('SET XACT_ABORT ON;')
        # Full-table snapshot captures the pre-insert state and related rows.
        save_backup(cur, cfg, 'INSERT_ParamFitur', include_all=True)
        cur.execute('''DECLARE @IDs TABLE (IDFitur BIGINT);
            INSERT INTO dbo.ParamFitur
            (Name, IPServer, DBName, DBUser, DBPass, LogActivityModul,
             LogActivitySubModul, LogActivityEntity, IsActive, SchStart)
            OUTPUT INSERTED.IDFitur INTO @IDs(IDFitur)
            VALUES (?, ?, ?, ?, dbo.fnEncrypt(?, ?), ?, ?, ?, 1, '00:00:00');
            SELECT IDFitur FROM @IDs;''', name, PRESET_DB_HOST, dbname, PRESET_DB_USER,
            PRESET_DB_PASS, f'{PRESET_DB_HOST}BR!', modul, sub, entity)
        result = cur.fetchone()
        if not result:
            raise RuntimeError('INSERT ParamFitur tidak menghasilkan IDFitur.')
        pf['IDFitur'] = int(result[0])
        sync_log(cur, pf)
        verify(cur, pf['IDFitur'])
        committed = decision(conn)
        if committed:
            # Password intentionally not embedded in deployment SQL.
            # Requires a SQLCMD variable to be set securely at execution time.
            lines = [
                '-- SQLCMD mode required: set variable ParamFiturPassword securely before execution.',
                'DECLARE @IDs TABLE (IDFitur BIGINT);',
                'INSERT INTO dbo.ParamFitur (Name, IPServer, DBName, DBUser, DBPass, LogActivityModul, LogActivitySubModul, LogActivityEntity, IsActive, SchStart)',
                'OUTPUT INSERTED.IDFitur INTO @IDs(IDFitur)',
                f"VALUES ({sqlval(name)}, {sqlval(PRESET_DB_HOST)}, {sqlval(dbname)}, {sqlval(PRESET_DB_USER)}, dbo.fnEncrypt(N'$(ParamFiturPassword)', {sqlval(PRESET_DB_HOST + 'BR!')}), {sqlval(modul)}, {sqlval(sub)}, {sqlval(entity)}, 1, '00:00:00');",
                'DECLARE @IDFitur BIGINT = (SELECT TOP (1) IDFitur FROM @IDs);',
                "IF @IDFitur IS NULL THROW 50001, 'INSERT gagal.', 1;",
                'INSERT INTO dbo.ParamFiturCekLogActivity (IDFitur, LogActivityModul, LogActivitySubModul, LogActivityEntity, LogActivityDateAdd, IsActive)',
                f"VALUES (@IDFitur, {sqlval(modul)}, {sqlval(sub)}, {sqlval(entity)}, '0', '1');",
                'SELECT IDFitur, Name, DBName, LogActivityModul, LogActivityEntity FROM dbo.ParamFitur WHERE IDFitur=@IDFitur;',
            ]
            save_deployment(deployment(lines), 'ParamFitur_INSERT')
    except BaseException:
        if not committed:
            conn.rollback()
        raise
    finally:
        conn.close()


def insert_join(cfg):
    pf = choose_pf_by_activity(cfg)
    if pf is None:
        return
    idfitur = int(pf['IDFitur'])
    conn = connect_sqlserver(cfg, DATABASE)
    committed = False
    try:
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute('SET XACT_ABORT ON;')
        cur.execute('SELECT ISNULL(MAX(OrderExecute),0)+1 FROM dbo.ParamJoin WITH (UPDLOCK,HOLDLOCK) WHERE IDFitur=?;', idfitur)
        order = int(cur.fetchone()[0])
        row = prompt_join(idfitur, order)
        print_join_preview(row)
        if not require_yes():
            conn.rollback()
            return
        save_backup(cur, cfg, 'INSERT_ParamJoin', [idfitur])
        sync_log(cur, pf)
        cur.execute('INSERT INTO dbo.ParamJoin (' + ', '.join(qident(c) for c in JOIN_COLUMNS) +
                    ') VALUES (' + ', '.join('?' for _ in JOIN_COLUMNS) + ');',
                    *(row[c] for c in JOIN_COLUMNS))
        verify(cur, idfitur)
        committed = decision(conn)
        if committed:
            save_deployment(join_deployment(pf, row, 'INSERT'), 'ParamJoin_INSERT')
    except BaseException:
        if not committed:
            conn.rollback()
        raise
    finally:
        conn.close()


def update_pf(cfg):
    selected = select_record(cfg, 'ParamFitur')
    if selected is None:
        return
    idfitur = int(selected['IDFitur'])
    options = [(str(i), f'{col}: {selected.get(col)}') for i, col in enumerate(PF_EDIT, 1)]
    section('PILIH FIELD UPDATE PARAMFITUR')
    for key, label in options:
        print(f' [{key}] {label}')
    raw = input('Nomor field (contoh 1,3; 0=batal): ').strip()
    if raw == '0':
        return
    try:
        nums = [int(x.strip()) for x in raw.split(',')]
        if not nums or len(nums) != len(set(nums)) or any(x < 1 or x > len(PF_EDIT) for x in nums):
            raise ValueError
    except ValueError:
        info('Pilihan field tidak valid.')
        return
    changes = {}
    for n in nums:
        col = PF_EDIT[n - 1]
        old = selected.get(col)
        raw = input(f'{col} [{old}] (Enter=tetap, NULL=SQL NULL, EMPTY=kosong): ').strip()
        if not raw:
            continue
        value = None if raw.upper() == 'NULL' else '' if raw.upper() == 'EMPTY' else raw
        if col == 'IsActive':
            if value is None or str(value) not in ('0', '1'):
                raise ValueError('IsActive harus 0 atau 1.')
            value = int(value)
        if value != old:
            changes[col] = value
    if not changes:
        info('Tidak ada perubahan.')
        return
    section('PREVIEW UPDATE PARAMFITUR')
    for k, v in changes.items():
        print(f'  {k}: {selected.get(k)!r} -> {v!r}')
    if not require_yes():
        return
    conn = connect_sqlserver(cfg, DATABASE)
    committed = False
    try:
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute('SET XACT_ABORT ON;')
        cur.execute('SELECT IDFitur FROM dbo.ParamFitur WITH (UPDLOCK,HOLDLOCK) WHERE IDFitur=?;', idfitur)
        if cur.fetchone() is None:
            raise RuntimeError('ParamFitur sudah tidak tersedia.')
        save_backup(cur, cfg, 'UPDATE_ParamFitur', [idfitur])
        cur.execute('UPDATE dbo.ParamFitur SET ' + ', '.join(f'{qident(k)}=?' for k in changes) +
                    ' WHERE IDFitur=?;', *changes.values(), idfitur)
        if cur.rowcount != 1:
            raise RuntimeError('UPDATE ParamFitur tidak tepat 1 record.')
        verify(cur, idfitur)
        committed = decision(conn)
        if committed:
            # Use identity fields rather than IDFitur which may differ between deployments.
            identity = (' AND '.join(f'{qident(c)}={sqlval(selected.get(c))}' for c in
                        ('IPServer', 'DBName', 'LogActivityModul', 'LogActivityEntity')) +
                        f" AND ISNULL(LogActivitySubModul,'')={sqlval(selected.get('LogActivitySubModul') or '')}")
            assignments = ', '.join(f'{qident(k)}={sqlval(v)}' for k, v in changes.items())
            statements = [f'UPDATE dbo.ParamFitur SET {assignments} WHERE {identity};',
                          "IF @@ROWCOUNT <> 1 THROW 50002, 'Jumlah record UPDATE tidak sesuai.', 1;"]
            save_deployment(deployment(statements), 'ParamFitur_UPDATE')
    except BaseException:
        if not committed:
            conn.rollback()
        raise
    finally:
        conn.close()


def update_join(cfg):
    selected = select_record(cfg, 'ParamJoin')
    if selected is None:
        return
    idfitur, order = int(selected['IDFitur']), int(selected['OrderExecute'])
    conn = connect_sqlserver(cfg, DATABASE)
    committed = False
    try:
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute('SET XACT_ABORT ON;')
        old_rows = fetch_dicts(cur, 'SELECT * FROM dbo.ParamJoin WITH (UPDLOCK,HOLDLOCK) WHERE IDFitur=? AND OrderExecute=?;', idfitur, order)
        if len(old_rows) != 1:
            raise RuntimeError('ParamJoin tidak ditemukan atau kunci tidak unik.')
        old = old_rows[0]
        pf_rows = fetch_dicts(cur, 'SELECT ' + ', '.join(qident(c) for c in PF_DISPLAY) +
                              ' FROM dbo.ParamFitur WHERE IDFitur=?;', idfitur)
        if len(pf_rows) != 1:
            raise RuntimeError('ParamFitur induk tidak ditemukan.')
        pf = pf_rows[0]
        row = prompt_join(idfitur, order, old)
        print_join_preview(row, old)
        if all(row[c] == old[c] for c in JOIN_COLUMNS):
            info('Tidak ada perubahan.')
            conn.rollback()
            return
        if not require_yes():
            conn.rollback()
            return
        save_backup(cur, cfg, 'UPDATE_ParamJoin', [idfitur])
        cols = JOIN_COLUMNS[2:]
        cur.execute('UPDATE dbo.ParamJoin SET ' + ', '.join(f'{qident(c)}=?' for c in cols) +
                    ' WHERE IDFitur=? AND OrderExecute=?;', *(row[c] for c in cols), idfitur, order)
        if cur.rowcount != 1:
            raise RuntimeError('UPDATE ParamJoin tidak tepat 1 record.')
        verify(cur, idfitur)
        committed = decision(conn)
        if committed:
            save_deployment(join_deployment(pf, row, 'UPDATE', order), 'ParamJoin_UPDATE')
    except BaseException:
        if not committed:
            conn.rollback()
        raise
    finally:
        conn.close()


def main():
    heading('SYNQRA | REKONPARAM - TRANSACTIONAL WIZARD + BACKUP')
    cfg = server_menu()
    if cfg is None:
        return
    conn = connect_sqlserver(cfg, DATABASE)
    conn.close()
    info(f'Koneksi berhasil: {cfg.host}:{cfg.port} / {DATABASE}')
    info('Kredensial diambil dari db_config.py; tidak diminta ulang.')
    while True:
        action = choose('PILIH OPERASI', [('1', 'INSERT'), ('2', 'UPDATE'), ('0', 'Keluar')])
        if action == '0':
            return
        table = choose('PILIH TABEL', [('1', 'ParamFitur'), ('2', 'ParamJoin'), ('0', 'Kembali')])
        if table == '0':
            continue
        if action == '1' and table == '1':
            insert_pf(cfg)
        elif action == '1':
            insert_join(cfg)
        elif table == '1':
            update_pf(cfg)
        else:
            update_join(cfg)
        info('Operasi selesai. Kembali ke menu utama.')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n[DIBATALKAN] Proses dihentikan. Transaksi aktif akan di-rollback saat koneksi ditutup.')
    except Exception as exc:
        print(f'\n[ERROR] {exc}')
        raise
