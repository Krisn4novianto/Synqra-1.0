#!/usr/bin/env python3
"""Generate reviewed, idempotent ParamEngine deployment SQL.

Run: python3 generateScriptDeploy/ParamEngine-generateScriptDeploy.py
Source connections: server 102 or localhost from db_config.SERVERS.
Only SELECT queries are sent to source. Output SQL is never executed.
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

DATABASE = 'ParamEngine'
TABLES = (
    'ParamCriteria', 'ParamDataFlow', 'ParamGetESB', 'ParamGetMasterBRI',
    'ParamGetDDHIST', 'ParamGetDDMAST', 'ParamGenerateFile', 'ParamFTP',
    'ParamSPExecutor', 'ParamParseFile', 'ParamParseFileMappingColumn', 'ParamRecon',
)


def ident(value):
    return '[' + str(value).replace(']', ']]') + ']'


def literal(value):
    if value is None:
        return 'NULL'
    if isinstance(value, bool):
        return '1' if value else '0'
    if isinstance(value, (int, Decimal)):
        return str(value)
    if isinstance(value, float):
        if value != value or value in (float('inf'), float('-inf')):
            raise ValueError('Nilai float non-finite tidak didukung.')
        return repr(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return '0x' + bytes(value).hex()
    if isinstance(value, datetime):
        return "N'" + value.isoformat(sep=' ') + "'"
    if isinstance(value, (date, time)):
        return "N'" + value.isoformat() + "'"
    return "N'" + str(value).replace("'", "''") + "'"


def safe_name(value):
    return re.sub(r'[^A-Za-z0-9_-]+', '_', str(value)).strip('_')[:80] or 'TanpaModul'


def ask(prompt, valid=None):
    while True:
        try:
            value = input(prompt).strip()
        except EOFError as exc:
            raise RuntimeError('Input terminal ditutup.') from exc
        if value.lower() in ('q', 'quit', 'keluar'):
            print('Dibatalkan.')
            raise SystemExit(0)
        if value and (valid is None or value.lower() in valid):
            return value
        print('Pilihan tidak valid. Coba lagi (atau ketik q untuk keluar).')


def server_host(config):
    if isinstance(config, dict):
        for key, value in config.items():
            if str(key).lower() in ('server', 'host', 'hostname', 'ipserver', 'ip', 'address'):
                return str(value)
        return ''
    if isinstance(config, str):
        match = re.search(r'(?i)(?:server|data source)\s*=\s*([^;]+)', config)
        return match.group(1).strip() if match else config
    # SQLServerConfig di db_config.py adalah dataclass, bukan dict.
    # Jangan gunakan str(config): dapat menampilkan password.
    return str(getattr(config, 'host', '') or '')


def select_server():
    options = {'1': None, '2': None}
    for key, config in SERVERS.items():
        host = server_host(config).lower()
        config_key = str(getattr(config, 'key', '')).lower()
        if host == '172.18.246.102' or config_key == 'server_102':
            options['1'] = config
        if host in ('localhost', '127.0.0.1', '.', '(local)') or config_key == 'server_local':
            options['2'] = config
    section('PILIH SERVER SUMBER')
    print('  1. Server 102' + ('' if options['1'] else ' (belum terdaftar)'))
    print('  2. Localhost' + ('' if options['2'] else ' (belum terdaftar)'))
    while True:
        choice = ask('Pilih [1-2]: ', {'1', '2'})
        if options[choice] is not None:
            return options[choice], ('Server 102' if choice == '1' else 'Localhost')
        print('Server belum terdaftar di db_config.SERVERS.')


def metadata(cur, table):
    cur.execute('''SELECT c.name, c.is_identity, c.is_computed, c.system_type_id,
                          ty.name AS type_name
                   FROM sys.columns c
                   JOIN sys.tables t ON c.object_id=t.object_id
                   JOIN sys.schemas s ON s.schema_id=t.schema_id
                   JOIN sys.types ty ON c.user_type_id=ty.user_type_id
                   WHERE s.name='dbo' AND t.name=? ORDER BY c.column_id''', table)
    records = cur.fetchall()
    if not records:
        raise RuntimeError(f'dbo.{table} tidak ditemukan pada sumber.')
    cols = [(r[0], str(r[4]).lower()) for r in records if not r[1] and not r[2] and r[3] != 189]
    names = {c.lower() for c, _ in cols}
    if not {'productid', 'task'}.issubset(names):
        raise RuntimeError(f'dbo.{table} tidak memiliki ProductId dan Task.')
    return cols


def read_rows(cur, table, cols, product, task):
    col_sql = ', '.join(ident(c) for c, _ in cols)
    cur.execute(f'SELECT {col_sql} FROM dbo.{ident(table)} WHERE [ProductId]=? AND [Task]=?', product, task)
    return [dict(zip((c for c, _ in cols), row)) for row in cur.fetchall()]


def equals_condition(column, dtype, value):
    name = ident(column)
    if value is None:
        return f't.{name} IS NULL'
    # Cast non-comparable legacy text/ntext/image/xml columns to comparable forms.
    if dtype in ('text', 'ntext', 'xml'):
        return f'CONVERT(NVARCHAR(MAX), t.{name}) = {literal(value)}'
    if dtype == 'image':
        return f'CONVERT(VARBINARY(MAX), t.{name}) = {literal(value)}'
    if dtype in ('geography', 'geometry', 'hierarchyid', 'sql_variant'):
        raise RuntimeError(f'Kolom {column} tipe {dtype} perlu strategi perbandingan khusus.')
    return f't.{name} = {literal(value)}'


def render_table(table, cols, rows):
    out = [f'-- ===== {table}: {len(rows)} baris sumber =====']
    if not rows:
        return out + [f'-- Tidak ada data untuk ProductId/Task pada {table}.', '']
    col_names = ', '.join(ident(c) for c, _ in cols)
    for n, row in enumerate(rows, 1):
        conditions = ' AND\n        '.join(equals_condition(c, dtype, row[c]) for c, dtype in cols)
        values = ', '.join(literal(row[c]) for c, _ in cols)
        out.extend([
            f'-- Baris {n}',
            f'IF NOT EXISTS (SELECT 1 FROM dbo.{ident(table)} AS t WITH (UPDLOCK, HOLDLOCK) WHERE',
            f'        {conditions})',
            'BEGIN',
            f'    INSERT INTO dbo.{ident(table)} ({col_names})',
            f'    VALUES ({values});',
            'END', '',
        ])
    return out


def read_source(cur, product, task, selected):
    data = {}
    for table in selected:
        cols = metadata(cur, table)
        rows = read_rows(cur, table, cols, product, task)
        data[table] = (cols, rows)
    return data


def build_sql(product, task, data):
    lines = [
        '-- SOP DEPLOYMENT PARAMENGINE',
        f'-- Generated: {datetime.now():%Y-%m-%d %H:%M:%S}',
        f'-- ProductId: {product} | Task: {task}',
        '-- Generated from source SELECT only; SQL not executed automatically.',
        '-- Review target schema, server IDs, credentials, and file paths before deployment.',
        'USE [ParamEngine];', 'GO', 'SET NOCOUNT ON;', 'SET XACT_ABORT ON;',
        'BEGIN TRY', '    BEGIN TRANSACTION;', '',
    ]
    for table, (cols, rows) in data.items():
        lines.extend(render_table(table, cols, rows))
    lines.extend([
        '    COMMIT TRANSACTION;', 'END TRY', 'BEGIN CATCH',
        '    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;',
        '    THROW;', 'END CATCH;', 'GO', '',
    ])
    return '\n'.join(lines)


TABLE_DESCRIPTIONS = {
    'ParamCriteria': 'Kriteria dan aturan aktivitas proses',
    'ParamDataFlow': 'Alur data dari sumber ke tujuan',
    'ParamGetESB': 'Pengambilan data dari ESB',
    'ParamGetMasterBRI': 'Pengambilan data master BRI',
    'ParamGetDDHIST': 'Pengambilan data histori DD',
    'ParamGetDDMAST': 'Pengambilan data master DD',
    'ParamGenerateFile': 'Konfigurasi pembuatan file',
    'ParamFTP': 'Konfigurasi transfer file FTP/SFTP',
    'ParamSPExecutor': 'Urutan eksekusi stored procedure',
    'ParamParseFile': 'Konfigurasi pembacaan file',
    'ParamParseFileMappingColumn': 'Pemetaan kolom file ke database',
    'ParamRecon': 'Aturan rekonsiliasi data',
}


def select_tables():
    section('PILIH TABEL PARAMENGINE')
    print('Pilih konfigurasi yang ingin dibuatkan script deployment.')
    print('  1. Semua tabel'.ljust(36) + '- Generate seluruh 12 tabel')
    for index, table in enumerate(TABLES, 2):
        print(f'  {index:>2}. {table:<29} - {TABLE_DESCRIPTIONS[table]}')
    print('  q. Keluar')
    choice = ask(f'\nMasukkan nomor tabel [1-{len(TABLES) + 1}]: ',
                 {str(i) for i in range(1, len(TABLES) + 2)})
    result = None if choice == '1' else TABLES[int(choice) - 2]
    print(f'Pilihan aktif: {result or "Semua tabel (12 tabel)"}')
    return result


def like_pattern(value):
    """Escape LIKE metacharacters; search input as a literal substring."""
    return '%' + value.replace('[', '[[]').replace('%', '[%]').replace('_', '[_]') + '%'


def search_candidates(cur, product, task, selected, limit=30, relaxed=False):
    """Find matching ProductId/Task pairs; optionally match either keyword."""
    matches = set()
    operator = 'OR' if relaxed else 'AND'
    for table in selected:
        cur.execute(
            f"""SELECT DISTINCT TOP (150) [ProductId], [Task]
                FROM dbo.{ident(table)}
                WHERE [ProductId] LIKE ? {operator} [Task] LIKE ?""",
            like_pattern(product), like_pattern(task),
        )
        for pid, tsk in cur.fetchall():
            if pid is not None and tsk is not None:
                matches.add((str(pid), str(tsk)))
    def rank(pair):
        pid, tsk = pair
        return (0 if product.casefold() in pid.casefold() and task.casefold() in tsk.casefold()
                else 1, pid.casefold(), tsk.casefold())
    return sorted(matches, key=rank)[:limit]


def section(title):
    print('\n' + '=' * 58)
    print('  ' + title)
    print('=' * 58)


def field(label, value, indent='  '):
    print(f'{indent}{label:<15}: {value}')


def show_candidate(index, product, task):
    print(f'\n  [{index}] KONFIGURASI')
    field('ProductId', product, '      ')
    field('Task', task, '      ')


def choose_product_task(cur, chosen):
    """Repeat search until a matching pair is selected or user exits."""
    while True:
        section('CARI PRODUCT ID DAN TASK')
        print('Masukkan nama lengkap atau sebagian kata yang ingin dicari.')
        print('Contoh: ProductId = PLNICON, Task = PREPAID')
        print('ProductId = kode produk. Task = nama pekerjaan/proses.')
        print('Tekan q untuk keluar tanpa membuat file.')
        product = ask('\nCari ProductId : ')
        task = ask('Cari Task      : ')
        if len(product) > 50 or len(task) > 100:
            print('Input terlalu panjang: ProductId maks. 50, Task maks. 100 karakter.')
            continue
        print('\nMemeriksa pasangan ProductId dan Task yang sama persis...')
        data = read_source(cur, product, task, chosen)
        if sum(len(rows) for _, rows in data.values()):
            print('DATA DITEMUKAN: pasangan ProductId dan Task cocok.')
            return product, task, data
        print('Belum ada pasangan yang cocok persis.')
        print('Mencari nama yang mengandung kedua kata kunci (LIKE)...')
        candidates = search_candidates(cur, product, task, chosen)
        if not candidates:
            print('Belum ada hasil untuk kedua kata kunci sekaligus.')
            print('Mencoba pencarian lebih luas: cocok ProductId ATAU Task...')
            candidates = search_candidates(cur, product, task, chosen, relaxed=True)
        if candidates:
            section('HASIL PENCARIAN - PILIH KONFIGURASI')
            print('Pilih nomor untuk memakai ProductId dan Task lengkap di bawah.')
            print('Data yang dipilih akan dibaca ulang sebelum membuat file SQL.\n')
            for i, (pid, tsk) in enumerate(candidates, 1):
                show_candidate(i, pid, tsk)
            print('\n   0. Cari lagi dengan kata kunci berbeda')
            print('   q. Keluar tanpa membuat file')
            while True:
                raw = ask(f'\nPilih nomor hasil [1-{len(candidates)}], 0, atau q: ')
                if raw == '0':
                    break
                if raw.isdigit() and 1 <= int(raw) <= len(candidates):
                    product, task = candidates[int(raw) - 1]
                    data = read_source(cur, product, task, chosen)
                    if sum(len(rows) for _, rows in data.values()):
                        section('KONFIGURASI YANG DIPILIH')
                        field('ProductId', product)
                        field('Task', task)
                        return product, task, data
                    print('Data tidak tersedia lagi. Pilih nomor lain atau 0 untuk mencari ulang.')
                else:
                    print('Nomor tidak tersedia. Pilih nomor dalam daftar, 0, atau q.')
        else:
            print('\n=== KONFIGURASI BELUM DITEMUKAN ===')
            print('Tidak ada pasangan yang cocok pada tabel yang dipilih.')
            print('Saran: coba nama produk lain, kata kunci lebih pendek,')
            print('atau jalankan ulang program dan pilih "Semua tabel".')
            print('  1. Cari ulang')
            print('  0. Keluar')
            action = ask('Pilih [1/0]: ', {'1', '0'})
            if action == '0':
                print('Dibatalkan. Tidak ada file yang dibuat.')
                raise SystemExit(0)


def main():
    section('PARAMENGINE | GENERATE SCRIPT DEPLOY SOP')
    print('Buat file SQL INSERT dari konfigurasi ParamEngine yang sudah ada.')
    print('Database sumber hanya dibaca (SELECT); tidak ada perubahan data.')
    config, server_name = select_server()
    selected = select_tables()
    chosen = TABLES if selected is None else (selected,)
    print('\nMenghubungkan ke database ParamEngine...')
    conn = connect_sqlserver(config, DATABASE)
    try:
        product, task, data = choose_product_task(conn.cursor(), chosen)
    finally:
        conn.close()

    count = sum(len(rows) for _, rows in data.values())
    stamp = datetime.now().strftime('%Y%m%d')
    module = safe_name(product + '_' + task)
    filename = (f'SOP ParamEngine_{stamp}.sql' if selected is None
                else f'SOP ParamEngine_{selected}_{module}_{stamp}.sql')
    outdir = Path(__file__).resolve().parent / 'output'
    dest = outdir / filename

    section('PREVIEW KONFIGURASI DEPLOYMENT')
    print('Periksa informasi di bawah sebelum membuat file SQL.\n')
    field('Server sumber', server_name)
    field('Database', DATABASE)
    field('Pilihan tabel', selected or 'Semua tabel (12 tabel)')
    print()
    field('ProductId', product)
    field('Task', task)

    section('RINCIAN DATA YANG AKAN DI-GENERATE')
    for index, (table, (_, rows)) in enumerate(data.items(), 1):
        print(f'  {index:>2}. {table}')
        field('Jumlah data', f'{len(rows)} baris', '      ')
    print('  ' + '-' * 54)
    field('TOTAL DATA', f'{count} baris')

    section('INFORMASI FILE OUTPUT')
    print('  Nama file:')
    print(f'    {filename}')
    print('\n  Folder penyimpanan:')
    print(f'    {outdir}')
    print('\n  Keterangan:')
    print('    - SQL dihasilkan dari data sumber (SELECT saja).')
    print('    - SQL tidak dijalankan secara otomatis.')
    print('    - Periksa isi SQL sebelum deployment ke production.')
    print('\n  Ketik YA untuk membuat file atau TIDAK untuk membatalkan.')
    if ask('Lanjut buat file SQL? [YA/TIDAK]: ', {'ya', 'tidak'}).lower() != 'ya':
        print('Dibatalkan.')
        return
    if dest.exists() and ask(f'File {filename} sudah ada. Timpa? [YA/TIDAK]: ',
                             {'ya', 'tidak'}).lower() != 'ya':
        print('Dibatalkan agar file lama tidak tertimpa.')
        return

    sql = build_sql(product, task, data)
    outdir.mkdir(parents=True, exist_ok=True)
    dest.write_text(sql, encoding='utf-8-sig')
    try:
        dest.chmod(0o600)
    except OSError:
        pass
    section('FILE SQL BERHASIL DIBUAT')
    print(f'File: {dest}')
    print('Periksa isi file SQL dan konfigurasi tujuan sebelum deployment.')


if __name__ == '__main__':
    try:
        main()
    except (Exception, KeyboardInterrupt) as exc:
        print(f'GAGAL: {exc}', file=sys.stderr)
        sys.exit(1)
