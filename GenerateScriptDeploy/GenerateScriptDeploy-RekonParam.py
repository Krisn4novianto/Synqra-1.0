#!/usr/bin/env python3
"""Generate SOP RekonParam per tabel / semua tabel, multi-IDFitur, read-only source.
Run: python3 generateScriptDeploy/RekonParam-generateScriptDeploy.py
Requires db_config.choose_server and db_connection.connect_sqlserver.
SQLCMD mode required for deployment; passwords supplied at execution, not stored in SQL.
"""
from __future__ import annotations

import re
import sys
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from db_config import SERVERS
from db_connection import connect_sqlserver

DATABASE = 'RekonParam'
CHILD_TABLES = ('ParamFiturCekLogActivity', 'ParamSPExecutor', 'ParamJoin')
OPTIONS = {'1': 'Semua tabel', '2': 'ParamFitur', '3': 'ParamFiturCekLogActivity',
           '4': 'ParamSPExecutor', '5': 'ParamJoin'}


def ident(name):
    return '[' + str(name).replace(']', ']]') + ']'


def literal(value):
    if value is None:
        return 'NULL'
    if isinstance(value, bool):
        return '1' if value else '0'
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return '0x' + bytes(value).hex()
    if isinstance(value, (datetime, date, time)):
        value = value.isoformat(sep=' ') if isinstance(value, datetime) else value.isoformat()
    return "N'" + str(value).replace("'", "''") + "'"


def safe_name(value):
    name = re.sub(r'[^A-Za-z0-9_-]+', '_', str(value or 'TanpaModul')).strip('_-')
    return name[:75] or 'TanpaModul'


def get_columns(cur, table):
    cur.execute('''SELECT c.name, c.is_identity, c.is_computed, c.system_type_id
        FROM sys.columns c JOIN sys.tables t ON t.object_id=c.object_id
        JOIN sys.schemas s ON s.schema_id=t.schema_id
        WHERE s.name='dbo' AND t.name=? ORDER BY c.column_id''', table)
    rows = cur.fetchall()
    if not rows:
        raise RuntimeError(f'Tabel dbo.{table} tidak ditemukan.')
    return [r[0] for r in rows if not r[1] and not r[2] and r[3] != 189]


def read_rows(cur, table, fid):
    cur.execute(f'SELECT * FROM dbo.{ident(table)} WHERE [IDFitur]=?', fid)
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def predicate(row, cols, alias=None, replace_id=False):
    parts = []
    for col in cols:
        col_sql = (alias + '.' if alias else '') + ident(col)
        if replace_id and col.lower() == 'idfitur':
            parts.append(f'{col_sql} = @IDFitur')
        elif row.get(col) is None:
            parts.append(f'{col_sql} IS NULL')
        else:
            parts.append(f'{col_sql} = {literal(row[col])}')
    return ' AND '.join(parts)


def emit_feature(feature, cols, index):
    keys = ('IPServer', 'DBName', 'LogActivityModul', 'LogActivitySubModul', 'LogActivityEntity')
    missing = [c for c in keys if c not in cols]
    if missing:
        raise RuntimeError(f'ParamFitur kehilangan kolom natural key: {missing}')
    where = predicate(feature, keys)
    insert_cols = [c for c in cols if c.lower() != 'idfitur']
    values = []
    for col in insert_cols:
        if col == 'DBPass':
            values.append(f"dbo.fnEncrypt(N'$(Password{index})', {literal(str(feature.get('IPServer') or '') + 'BR!')})")
        else:
            values.append(literal(feature.get(col)))
    return [
        '-- PARAMFITUR',
        f"IF (SELECT COUNT_BIG(*) FROM dbo.[ParamFitur] WITH (UPDLOCK, HOLDLOCK) WHERE {where}) > 1",
        "    THROW 51001, N'Duplikat natural key ParamFitur pada target', 1;",
        f'IF NOT EXISTS (SELECT 1 FROM dbo.[ParamFitur] WITH (UPDLOCK, HOLDLOCK) WHERE {where})',
        'BEGIN',
        f"    INSERT INTO dbo.[ParamFitur] ({', '.join(map(ident, insert_cols))})",
        f"    VALUES ({', '.join(values)});",
        'END;',
        'SET @IDFitur = NULL;',
        f'SELECT @IDFitur = [IDFitur] FROM dbo.[ParamFitur] WHERE {where};',
        "IF @IDFitur IS NULL THROW 51002, N'IDFitur target tidak ditemukan', 1;",
        ''
    ]


def emit_children(table, rows, cols):
    lines = [f'-- {table}: {len(rows)} baris sumber']
    if not rows:
        return lines + ['']
    if 'IDFitur' not in cols:
        raise RuntimeError(f'dbo.{table} tidak memiliki kolom IDFitur.')
    # Compare all exported fields: rerunning the deployment does not insert identical rows.
    # Distinct rows with identical values cannot be preserved without a stable business key.
    for row in rows:
        vals = ['@IDFitur' if c == 'IDFitur' else literal(row.get(c)) for c in cols]
        where = predicate(row, cols, replace_id=True)
        lines.extend([
            f'IF NOT EXISTS (SELECT 1 FROM dbo.{ident(table)} WITH (UPDLOCK, HOLDLOCK) WHERE {where})',
            'BEGIN',
            f"    INSERT INTO dbo.{ident(table)} ({', '.join(map(ident, cols))})",
            f"    VALUES ({', '.join(vals)});",
            'END;',
        ])
    return lines + ['']


def parse_ids(raw):
    try:
        ids = list(dict.fromkeys(int(part.strip()) for part in raw.split(',')))
    except ValueError as exc:
        raise ValueError('IDFitur harus angka positif dipisahkan koma.') from exc
    if not ids or any(i <= 0 for i in ids):
        raise ValueError('Masukkan minimal satu IDFitur positif.')
    return ids


def prompt(message):
    value = input(message).strip()
    if value.lower() in ('q', 'quit', 'exit'):
        print('\n[INFO] Program ditutup tanpa mengubah database.')
        sys.exit(0)
    return value


def section(title):
    print('\n' + '=' * 62)
    print('  ' + title)
    print('=' * 62)


def field(label, value):
    print(f'  {label:<23}: {value if value is not None else "-"}')


def choose_server():
    options = {'1': SERVERS['2'], '2': SERVERS['3']}
    while True:
        section('PILIH SERVER SUMBER')
        print('  Pilih database yang akan dibaca (SELECT saja).\n')
        for key, config in options.items():
            print(f'  {key}. {getattr(config, "name", "Server")}')
        print('  0. Keluar')
        answer = prompt('\n  Pilihan [1/2/0]: ')
        if answer == '0': sys.exit(0)
        if answer in options: return options[answer]
        print('  [ERROR] Pilihan tidak valid. Silakan pilih ulang.')


def choose_scope():
    while True:
        section('PILIH TABEL DEPLOYMENT')
        print('  Pilih semua tabel atau salah satu tabel yang akan di-generate.\n')
        for key, name in OPTIONS.items():
            print(f'  {key}. {name}')
        print('  0. Keluar')
        answer = prompt('\n  Pilihan [1-5/0]: ')
        if answer == '0': sys.exit(0)
        if answer in OPTIONS: return answer
        print('  [ERROR] Pilihan tidak valid.')


def find_features(cur, keyword):
    cols = ('IDFitur', 'IPServer', 'DBName', 'LogActivityModul',
            'LogActivitySubModul', 'LogActivityEntity')
    if keyword.isdigit():
        cur.execute('SELECT TOP (50) ' + ', '.join(map(ident, cols)) +
                    ' FROM dbo.[ParamFitur] WHERE [IDFitur]=? ORDER BY [IDFitur]', int(keyword))
    else:
        escaped = keyword.replace('[', '[[]').replace('%', '[%]').replace('_', '[_]')
        pattern = '%' + escaped + '%'
        predicates = ' OR '.join(f'CONVERT(NVARCHAR(4000), {ident(c)}) LIKE ?' for c in cols[1:])
        cur.execute('SELECT TOP (50) ' + ', '.join(map(ident, cols)) +
                    ' FROM dbo.[ParamFitur] WHERE ' + predicates + ' ORDER BY [IDFitur]',
                    *([pattern] * (len(cols) - 1)))
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def choose_features(cur):
    selected = {}
    while True:
        section('CARI FITUR SUMBER')
        print('  Cari berdasarkan IDFitur atau sebagian DBName, Modul, SubModul, Entity.')
        print('  Contoh: SETTLEMENT, REKON, atau 1234.')
        print('  Ketik 0 untuk selesai memilih, q untuk keluar.')
        field('Fitur sudah dipilih', len(selected))
        keyword = prompt('\n  Kata kunci: ')
        if keyword == '0':
            if selected: return list(selected)
            print('  [INFO] Pilih minimal satu fitur terlebih dahulu.')
            continue
        if not keyword:
            print('  [ERROR] Kata kunci tidak boleh kosong.')
            continue
        results = find_features(cur, keyword)
        if not results:
            print('\n  [INFO] Data tidak ditemukan. Coba kata kunci lain atau lebih pendek.')
            continue
        section('HASIL PENCARIAN FITUR')
        print('  Pilih satu atau beberapa nomor dipisahkan koma.')
        print('  Hasil maksimal 50 fitur per pencarian.\n')
        for idx, item in enumerate(results, 1):
            print(f'  [{idx}]')
            for label, key in (('IDFitur', 'IDFitur'), ('DBName', 'DBName'),
                               ('Modul', 'LogActivityModul'),
                               ('SubModul', 'LogActivitySubModul'),
                               ('Entity', 'LogActivityEntity')):
                field(label, item.get(key))
            print('  ' + '-' * 52)
        print('  0. Cari ulang')
        print('  q. Keluar')
        raw = prompt('\n  Pilih nomor (contoh 1,3): ')
        if raw == '0': continue
        try:
            indexes = [int(x.strip()) for x in raw.split(',')]
            if not indexes or any(i < 1 or i > len(results) for i in indexes):
                raise ValueError()
        except ValueError:
            print('  [ERROR] Nomor tidak valid. Silakan cari ulang.')
            continue
        for i in indexes:
            item = results[i-1]
            selected[int(item['IDFitur'])] = item
        print(f'\n  [OK] {len(selected)} fitur dipilih.')
        answer = prompt('  Tambah fitur lain? [YA/TIDAK]: ').lower()
        if answer in ('tidak', 't', 'no', 'n'): return list(selected)


def confirm(message):
    while True:
        answer = prompt(message).lower()
        if answer in ('ya', 'y', 'yes'): return True
        if answer in ('tidak', 't', 'no', 'n'): return False
        print('  [ERROR] Masukkan YA atau TIDAK (atau q untuk keluar).')


def generate(cur, ids, scope):
    feature_cols = get_columns(cur, 'ParamFitur')
    selected = CHILD_TABLES if scope == '1' else (() if scope == '2' else (OPTIONS[scope],))
    child_cols = {t: get_columns(cur, t) for t in selected}
    features = []
    all_children = {}
    for fid in ids:
        rows = read_rows(cur, 'ParamFitur', fid)
        if len(rows) != 1:
            raise RuntimeError(f'ParamFitur IDFitur={fid}: ditemukan {len(rows)} baris (harus 1).')
        features.append(rows[0])
        for table in selected:
            all_children[(fid, table)] = read_rows(cur, table, fid)
    lines = [
        '-- SOP RekonParam | SQL generated, not executed',
        f'-- Generated: {datetime.now():%Y-%m-%d %H:%M:%S}',
        f'-- Scope: {OPTIONS[scope]} | Source IDFitur: {", ".join(map(str, ids))}',
        '-- SQLCMD mode required. Provide Password1, Password2, ... at execution.',
        '-- WARNING: SQLCMD substitution is textual; review password escaping.',
        '-- Review schema, natural keys, and target data before production deployment.',
        'USE [RekonParam];', 'GO', 'SET NOCOUNT ON;', 'SET XACT_ABORT ON;',
        'BEGIN TRY', '    BEGIN TRANSACTION;', '    DECLARE @IDFitur INT;', ''
    ]
    for index, feature in enumerate(features, 1):
        fid = feature['IDFitur']
        activity = str(feature.get('LogActivityEntity') or 'TanpaActivity').replace('\n', ' ')
        lines += [f'-- ========== ACTIVITY: {activity} | IDFitur sumber: {fid} ==========']
        lines += emit_feature(feature, feature_cols, index)
        for table in selected:
            lines += emit_children(table, all_children[(fid, table)], child_cols[table])
    lines += ['    COMMIT TRANSACTION;', 'END TRY', 'BEGIN CATCH',
              '    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;',
              '    THROW;', 'END CATCH;', '']
    return '\n'.join(lines), features, all_children


def main():
    section('REKONPARAM | GENERATE SCRIPT DEPLOY SOP')
    print('  Generator SQL deployment RekonParam.')
    print('  Database sumber hanya dibaca; SQL tidak langsung dieksekusi.')
    print('  Ketik q pada input untuk keluar.\n')
    config = choose_server()
    scope = choose_scope()
    print('\n  [INFO] Menghubungkan ke database sumber...')
    conn = connect_sqlserver(config, DATABASE)
    try:
        cur = conn.cursor()
        features_selected = choose_features(cur)
        ids = list(features_selected)
        print('\n  [INFO] Membaca data tabel untuk fitur terpilih...')
        sql, features, children = generate(cur, ids, scope)
    finally:
        conn.close()

    stamp = datetime.now().strftime('%Y%m%d')
    if scope == '1':
        filename = f'SOP RekonParam_{stamp}.sql'
    else:
        modules = [safe_name(f.get('LogActivityModul') or f.get('DBName')) for f in features]
        module = modules[0] if len(set(modules)) == 1 else 'MultiModul'
        filename = f'SOP RekonParam_{OPTIONS[scope]}_{module}_{stamp}.sql'
    outdir = Path(__file__).resolve().parent / 'output'
    path = outdir / filename

    section('PREVIEW KONFIGURASI DEPLOYMENT')
    field('Server sumber', getattr(config, 'name', 'Server'))
    field('Database', DATABASE)
    field('Pilihan tabel', OPTIONS[scope])
    field('Jumlah fitur', len(features))
    section('RINCIAN FITUR DAN DATA')
    total = 0
    for index, feature in enumerate(features, 1):
        fid = feature['IDFitur']
        print(f'\n  FITUR {index}')
        field('IDFitur', fid)
        field('DBName', feature.get('DBName'))
        field('Modul', feature.get('LogActivityModul'))
        field('SubModul', feature.get('LogActivitySubModul'))
        field('Entity', feature.get('LogActivityEntity'))
        field('ParamFitur (induk)', '1 baris')
        total += 1
        for table in CHILD_TABLES:
            if (fid, table) in children:
                count = len(children[(fid, table)])
                print(f'\n    {table}')
                print(f'      Jumlah data: {count} baris')
                total += count
        print('  ' + '-' * 52)
    field('TOTAL DATA', f'{total} baris')

    section('INFORMASI FILE OUTPUT')
    print('  Nama file:')
    print('    ' + filename)
    print('\n  Folder penyimpanan:')
    print('    ' + str(outdir))
    print('\n  Keterangan:')
    print('    - Source database hanya SELECT.')
    print('    - File SQL tidak dijalankan otomatis.')
    print(f'    - SQLCMD Password1 sampai Password{len(features)} diperlukan saat deployment.')
    print('    - Review SQL dan data target sebelum deployment produksi.')
    if not confirm('\n  Lanjut buat file SQL? [YA/TIDAK]: '):
        print('  [INFO] Pembuatan file dibatalkan.')
        return
    if path.exists() and not confirm('  File sudah ada. Timpa? [YA/TIDAK]: '):
        print('  [INFO] File lama tidak diubah.')
        return
    outdir.mkdir(parents=True, exist_ok=True)
    path.write_text(sql, encoding='utf-8')
    try: path.chmod(0o600)
    except OSError: pass
    section('BERHASIL | FILE SQL DIBUAT')
    field('Nama file', filename)
    field('Lokasi', path)
    field('Total data', f'{total} baris')
    print('\n  [INFO] Database sumber tidak diubah. SQL belum dieksekusi.')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n[INFO] Dibatalkan oleh pengguna.', file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f'\n[ERROR] {exc}', file=sys.stderr)
        sys.exit(1)
