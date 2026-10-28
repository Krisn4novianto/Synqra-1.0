#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""REKONENTERPRISEAPI — WIZARD INSERT BERURUTAN / UPDATE FILTER KOLOM.

Jalankan dari root repository:
    ./.venv/bin/python activities/RekonEnterpriseAPI/python/RekonEnterpriseAPI.py

SOP:
1. Pilih server 205/localhost dari db_config.SERVERS (menu khusus dua server).
2. Pilih INSERT (15 tabel berurutan) atau UPDATE (pilih tabel).
3. INSERT: ParamFitur langsung form tanpa IDFitur (database/default atau alokasi terkunci); opsi existing baru SELECT.\n   Tabel anak otomatis memakai IDFitur aktif; ID endpoint lain manual.
4. UPDATE: pilih kolom filter + operator + nilai, pilih tepat satu record,
   kemudian pilih kolom yang diubah. Tidak menerima WHERE mentah.
5. Preview -> konfirmasi Y -> backup SELECT INTO pada koneksi terpisah,
   COMMIT backup -> DML -> verifikasi -> ketik COMMIT tepat atau ROLLBACK.
6. Setelah COMMIT sukses, simpan deployment SQL per operasi.

PERINGATAN: backup SELECT INTO adalah snapshot data, bukan BACKUP DATABASE.
Indeks, constraint, trigger, permission tidak disalin. Data sensitif tetap
tersimpan di backup database; lindungi aksesnya. Jangan deploy ke produksi
sebelum menguji pada lingkungan nonproduksi dan memeriksa SQL hasil generator.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from getpass import getpass
from pathlib import Path
import os
import re
import secrets
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = next((p for p in (SCRIPT_DIR, *SCRIPT_DIR.parents)
             if (p / 'db_config.py').exists() and (p / 'db_connection.py').exists()), SCRIPT_DIR)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from db_config import SERVERS
from db_connection import connect_sqlserver

DATABASE = 'RekonEnterpriseAPI'
OUTPUT = ROOT / 'activities' / 'RekonEnterpriseAPI' / 'generated'
TABLES = [
    'ParamFitur', 'EndpoinInq', 'EndpoinList', 'EndpoinMCS',
    'ConditionDictionaryInq', 'MappingConditionInq', 'MappingResultList',
    'ResultDictionaryInq', 'MappingResultInq', 'ConditionDictionaryMCS',
    'MappingConditionMCS', 'ResultDictionaryMCS', 'MappingResultMCS',
    'EndpoinFTP', 'ConditionDictionaryFTP',
]
PARAMFITUR_ORDER = ['IDFitur', 'Name', 'IPServer', 'DBName', 'DBUser', 'DBPass', 'IsActive']
SENSITIVE = re.compile(r'(pass|password|secret|token|credential|apikey|api_key)', re.I)
INT_TYPES = {'tinyint', 'smallint', 'int', 'bigint', 'bit'}
NUM_TYPES = INT_TYPES | {'decimal', 'numeric', 'float', 'real', 'money', 'smallmoney'}
EXPR = {'GETDATE()', 'SYSDATETIME()', 'NEWID()', 'SUSER_SNAME()', 'ORIGINAL_LOGIN()'}



def choose_rekon_server():
    """Tampilkan hanya profil 205 dan Localhost, gunakan kredensial asli db_config."""
    profiles = list(SERVERS.values()) if isinstance(SERVERS, dict) else list(SERVERS)

    def field(cfg, key, default=None):
        return cfg.get(key, default) if isinstance(cfg, dict) else getattr(cfg, key, default)

    def host_of(cfg):
        raw = str(field(cfg, 'host', field(cfg, 'server', ''))).strip().lower()
        return raw.split('\\')[0].split(',')[0] if raw == '::1' else raw.split('\\')[0].split(',')[0].split(':')[0]

    candidates = (
        ('Server 205', {'172.18.135.205'}),
        ('Localhost (Testing)', {'localhost', '127.0.0.1', '::1', '(local)', '.'}),
    )
    options = []
    for label, hosts in candidates:
        found = next((cfg for cfg in profiles if host_of(cfg) in hosts), None)
        if found is not None:
            options.append((label, found))
    if len(options) != 2:
        raise RuntimeError(
            'Profil Server 205 dan Localhost wajib tersedia di db_config.SERVERS. '
            'Periksa host/server pada db_config.py.'
        )
    print('\nPilih koneksi SQL Server (khusus RekonEnterpriseAPI):')
    for i, (label, cfg) in enumerate(options, 1):
        print(f'  {i}. {label} ({field(cfg, "host", field(cfg, "server"))}:{field(cfg, "port", 1433)})')
    print('  0. Keluar')
    while True:
        selection = input('Pilih server [1/2/0]: ').strip()
        if selection == '0':
            raise SystemExit(0)
        if selection in ('1', '2'):
            return options[int(selection) - 1][1]
        print('Pilihan tidak valid. Pilih 1, 2, atau 0.')

def ident(name):
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_$#]*', name):
        raise ValueError(f'Identifier SQL tidak valid: {name!r}')
    return '[' + name + ']'


def sql_literal(value):
    if value is None:
        return 'NULL'
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    if isinstance(value, bytes):
        return '0x' + value.hex()
    return "N'" + str(value).replace("'", "''") + "'"


def ask(prompt, default=None, secret=False):
    suffix = f' [{default}]' if default is not None and not secret else ''
    raw = (getpass if secret else input)(f'{prompt}{suffix}: ').strip()
    return str(default) if not raw and default is not None else raw


def menu(items, prompt='Pilih nomor'):
    for i, item in enumerate(items, 1):
        print(f'  [{i}] {item}')
    while True:
        raw = ask(prompt)
        if raw.isdigit() and 1 <= int(raw) <= len(items):
            return int(raw) - 1
        print('Nomor pilihan tidak valid.')


def mask(name, value):
    if SENSITIVE.search(name):
        return '[TERSEMBUNYI]'
    if value is None:
        return 'NULL'
    value = str(value).replace('\r', ' ').replace('\n', ' ')
    return value[:90] + '...' if len(value) > 90 else value


def show_rows(columns, rows, title, limit=30):
    """Cetak hasil SELECT per record secara vertikal agar tidak melebar."""
    shown = list(rows[:limit])
    print(f'\n=== {title} | {len(shown)} record ditampilkan ===')
    if not shown:
        print('(Tidak ada data)')
        return
    width = min(32, max((len(str(c)) for c in columns), default=10))
    for i, row in enumerate(shown, 1):
        print('\n' + '-' * 56)
        print(f'RECORD [{i}]')
        print('-' * 56)
        for col, value in zip(columns, row):
            print(f'{str(col):<{width}} : {mask(str(col), value)}')
    print('-' * 56)



def columns_of(cur, table):
    cur.execute('''SELECT c.name, TYPE_NAME(c.user_type_id), c.is_nullable,
                          c.is_identity, c.is_computed, dc.definition,
                          CASE WHEN pk.column_id IS NULL THEN 0 ELSE 1 END
                   FROM sys.columns c
                   JOIN sys.tables t ON t.object_id = c.object_id
                   JOIN sys.schemas s ON s.schema_id = t.schema_id
                   LEFT JOIN sys.default_constraints dc ON dc.object_id = c.default_object_id
                   LEFT JOIN (
                       SELECT ic.object_id, ic.column_id FROM sys.index_columns ic
                       JOIN sys.indexes ix ON ix.object_id=ic.object_id AND ix.index_id=ic.index_id
                       WHERE ix.is_primary_key=1
                   ) pk ON pk.object_id=c.object_id AND pk.column_id=c.column_id
                   WHERE s.name='dbo' AND t.name=? ORDER BY c.column_id''', table)
    return [dict(name=r[0], type=r[1].lower(), nullable=bool(r[2]),
                 identity=bool(r[3]), computed=bool(r[4]), default=r[5], pk=bool(r[6]))
            for r in cur.fetchall()]


def editable_columns(cols):
    return [c for c in cols if not c['identity'] and not c['computed']
            and c['type'] not in {'timestamp', 'rowversion'}]


def parse_value(raw, col):
    if raw.upper() == 'NULL':
        if not col['nullable']:
            raise ValueError('Kolom ini NOT NULL.')
        return None, 'NULL', False
    if raw.upper().startswith('SQL:'):
        expr = raw[4:].strip().upper()
        if expr not in EXPR:
            raise ValueError('Ekspresi SQL tidak diizinkan.')
        return None, expr, True
    typ = col['type']
    if typ in NUM_TYPES:
        try:
            num = Decimal(raw)
        except InvalidOperation as exc:
            raise ValueError('Harus berupa angka.') from exc
        if not num.is_finite():
            raise ValueError('Angka harus finite.')
        if typ in INT_TYPES and num != num.to_integral_value():
            raise ValueError('Kolom integer tidak menerima pecahan.')
        if typ == 'bit' and num not in (0, 1):
            raise ValueError('bit harus 0 atau 1.')
        return (int(num) if typ in INT_TYPES else num), str(num), False
    return raw, sql_literal(raw), False


def select_fields(cols, action, preset=None):
    values = dict(preset or {})
    selected = list(values)
    print('\nENTER = lewati kolom opsional; NULL = SQL NULL; SQL:GETDATE() = ekspresi terbatas.')
    for c in cols:
        name = c['name']
        if name in values:
            print(f'{name}: [OTOMATIS DARI PRODUK AKTIF]')
            continue
        can_skip = action == 'UPDATE' or c['nullable'] or c['default'] is not None
        while True:
            raw = ask(f'{name} ({c["type"]}; {"ENTER=skip" if can_skip else "WAJIB"})',
                      secret=bool(SENSITIVE.search(name)))
            if not raw:
                if can_skip:
                    break
                print('Kolom wajib diisi.')
                continue
            try:
                values[name] = parse_value(raw, c)
                selected.append(name)
                break
            except ValueError as exc:
                print(f'Input salah: {exc}')
    return values, selected


def input_with_review(cols, preset=None):
    while True:
        values, chosen = select_fields(cols, 'INSERT', preset)
        if not chosen:
            print('Belum ada kolom yang diisi.')
            continue
        while True:
            print('\n=== PREVIEW INPUT ===')
            for name in chosen:
                print(f'  {name}: {mask(name, values[name][0] if not values[name][2] else values[name][1])}')
            choice = menu(['Lanjut INSERT', 'Edit kolom tertentu', 'Ulangi seluruh input', 'Batalkan'], 'Tindakan')
            if choice == 0:
                return values, chosen
            if choice == 2:
                break
            if choice == 3:
                return None, None
            candidates = [c for c in cols if c['name'] not in (preset or {})]
            idx = menu([c['name'] for c in candidates] + ['Kembali'], 'Kolom edit')
            if idx == len(candidates):
                continue
            col = candidates[idx]
            while True:
                raw = ask('Nilai baru ' + col['name'], secret=bool(SENSITIVE.search(col['name'])))
                if not raw:
                    print('Masukkan nilai, NULL, atau kembali dengan mengulang input.')
                    continue
                try:
                    values[col['name']] = parse_value(raw, col)
                    if col['name'] not in chosen:
                        chosen.append(col['name'])
                    break
                except ValueError as exc:
                    print(exc)


def fetch_rows(cur, table, where='1=1', params=(), limit=30):
    cur.execute(f'SELECT TOP ({int(limit)}) * FROM dbo.{ident(table)} WHERE {where}', list(params))
    return [d[0] for d in cur.description], cur.fetchall()


def filter_builder(cols):
    """Filter dipilih via metadata; tidak menerima WHERE mentah.

    SQL yang dihasilkan setara filter pada CTE, tetapi menggunakan WHERE
    berparameter supaya aman dan sederhana.
    """
    terms, params, description = [], [], []
    print('\n=== PILIH KOLOM FILTER (boleh lebih dari satu) ===')
    while True:
        choices = [c['name'] for c in cols] + ['SELESAI memilih filter']
        idx = menu(choices, 'Kolom filter')
        if idx == len(cols):
            if terms:
                break
            print('Minimal satu filter diperlukan.')
            continue
        c = cols[idx]
        operator = menu(['= (sama dengan)', 'LIKE (mengandung; teks)', 'IS NULL'], 'Operator')
        if operator == 2:
            terms.append(f'{ident(c["name"])} IS NULL')
            description.append(f'{c["name"]} IS NULL')
            continue
        if operator == 1 and c['type'] in NUM_TYPES:
            print('LIKE tidak digunakan untuk kolom numerik.')
            continue
        raw = ask(f'Nilai {c["name"]}', secret=bool(SENSITIVE.search(c['name'])))
        if not raw:
            print('Nilai filter tidak boleh kosong.')
            continue
        if operator == 1:
            terms.append(f'{ident(c["name"])} LIKE ?')
            params.append('%' + raw + '%')
            description.append(f'{c["name"]} LIKE {mask(c["name"], raw)}')
        else:
            try:
                value, _, expression = parse_value(raw, c)
                if expression or value is None:
                    print('Gunakan IS NULL untuk NULL; ekspresi SQL tidak diizinkan pada filter.')
                    continue
            except ValueError as exc:
                print(exc)
                continue
            terms.append(f'{ident(c["name"])} = ?')
            params.append(value)
            description.append(f'{c["name"]} = {mask(c["name"], raw)}')
    return ' AND '.join(terms), params, ' AND '.join(description)


def unique_identity(cols, row, headers):
    """Gunakan seluruh PK. Jika tanpa PK, gunakan semua kolom yang dapat dibandingkan.
    Tanpa PK, target harus menghasilkan COUNT=1; NULL ditangani dengan IS NULL.
    """
    pk = [c for c in cols if c['pk']]
    usable = pk or [c for c in cols if c['type'] not in
                    {'text', 'ntext', 'image', 'xml', 'geography', 'geometry', 'sql_variant'}]
    if not usable:
        raise RuntimeError('Tabel tidak memiliki kolom yang aman untuk identifikasi record.')
    rowmap = dict(zip(headers, row))
    parts, params = [], []
    for c in usable:
        val = rowmap[c['name']]
        if val is None:
            parts.append(f'{ident(c["name"])} IS NULL')
        else:
            parts.append(f'{ident(c["name"])} = ?')
            params.append(val)
    return ' AND '.join(parts), params


def backup_table(cfg, table):
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '_' + secrets.token_hex(4)
    backup = f'{table}_Backup_{stamp}'
    conn = connect_sqlserver(cfg, DATABASE)
    try:
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute('SELECT DB_NAME(), OBJECT_ID(?, N\'U\')', 'dbo.' + table)
        db, oid = cur.fetchone()
        if str(db).lower() != DATABASE.lower() or oid is None:
            raise RuntimeError('Database/tabel tidak sesuai, backup dibatalkan.')
        cur.execute(f'SELECT * INTO dbo.{ident(backup)} FROM dbo.{ident(table)}')
        conn.commit()
        print(f'[BACKUP COMMITTED] dbo.{backup}')
        return backup
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def deployment_sql(table, action, chosen, values, where_sql, where_params, backup):
    """SQL deployment mandiri; password tidak ditulis sebagai literal.
    WHERE parameter diubah menjadi literal hanya dari nilai terpilih yang sudah
    dikunci sebagai identitas record; parameter tidak boleh berasal dari SQL mentah.
    """
    def inline_where(sql, params):
        for param in params:
            sql = sql.replace('?', sql_literal(param), 1)
        return sql
    where = inline_where(where_sql, where_params)
    sqlvals = []
    for name in chosen:
        val, literal, expr = values[name]
        sqlvals.append("N'$(SECRET_" + re.sub(r'[^A-Za-z0-9_]', '_', name).upper() + ")'"
                       if SENSITIVE.search(name) else literal)
    t = ident(table)
    lines = [f'USE {ident(DATABASE)};', 'GO', 'SET NOCOUNT ON;', 'SET XACT_ABORT ON;',
             '-- Review seluruh SQL sebelum eksekusi; SQLCMD variables wajib disediakan.',
             f'-- Backup wizard asal: dbo.{backup}',
             'DECLARE @b sysname = N\'' + table + '_Backup_\' + CONVERT(varchar(8),GETDATE(),112) + N\'_\' + REPLACE(CONVERT(varchar(36),NEWID()),N\'-\',N\'\');',
             'BEGIN TRY', ' BEGIN TRANSACTION;',
             f" EXEC(N'SELECT * INTO dbo.' + QUOTENAME(@b) + N' FROM dbo.{t}');",
             ' COMMIT TRANSACTION;', 'END TRY', 'BEGIN CATCH',
             ' IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;', ' THROW;', 'END CATCH;',
             'BEGIN TRY', ' BEGIN TRANSACTION;']
    if action == 'INSERT':
        lines += [f' IF EXISTS (SELECT 1 FROM dbo.{t} WITH (UPDLOCK,HOLDLOCK) WHERE {where}) THROW 51001, \'Record sudah ada\', 1;',
                  f' INSERT INTO dbo.{t} ({", ".join(ident(n) for n in chosen)}) VALUES ({", ".join(sqlvals)});']
    else:
        lines += [f' IF (SELECT COUNT_BIG(*) FROM dbo.{t} WITH (UPDLOCK,HOLDLOCK) WHERE {where}) <> 1 THROW 51001, \'Record tidak unik\', 1;',
                  f' UPDATE dbo.{t} SET ' + ', '.join(f'{ident(n)}={v}' for n, v in zip(chosen, sqlvals)) + f' WHERE {where};']
    lines += [' IF @@ROWCOUNT <> 1 THROW 51003, \'Jumlah baris berubah tidak tepat 1\', 1;',
              ' COMMIT TRANSACTION;', 'END TRY', 'BEGIN CATCH',
              ' IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;', ' THROW;', 'END CATCH;', 'GO']
    return '\n'.join(lines) + '\n'


def save_deployment(table, action, chosen, values, where, params, backup):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '_' + secrets.token_hex(3)
    path = OUTPUT / f'{stamp}_{table}_{action}.sql'
    content = deployment_sql(table, action, chosen, values, where, params, backup)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as out:
        out.write(content)
    return path


def perform_change(conn, cfg, table, action, cols, chosen, values, where, params, description, return_identity=False, allocate_id=False):
    if not chosen:
        return False
    print('\n=== PREVIEW PERUBAHAN ===')
    print('Tabel:', table, '| Aksi:', action)
    print('Target:', description)
    for name in chosen:
        print(f'  {name}: {mask(name, values[name][1])}')
    if ask('Backup dan jalankan DML sementara? Ketik Y').upper() != 'Y':
        print('Dibatalkan tanpa backup atau perubahan.')
        return False
    conn.rollback()  # bebaskan lock baca sebelum koneksi backup
    backup = backup_table(cfg, table)
    try:
        cur = conn.cursor()
        cur.execute('SET XACT_ABORT ON')
        if allocate_id:
            # Ambil ID berikutnya hanya setelah memperoleh lock eksklusif transaksi.
            # sp_getapplock menserialkan seluruh instance wizard; TABLOCKX,HOLDLOCK
            # mencegah writer lain menyisipkan ID ketika MAX sedang dihitung.
            cur.execute('''SET NOCOUNT ON; DECLARE @result int;
                           EXEC @result = sys.sp_getapplock
                               @Resource=N'RekonEnterpriseAPI.ParamFitur.IDFitur',
                               @LockMode=N'Exclusive', @LockOwner=N'Transaction',
                               @LockTimeout=15000;
                           SELECT @result;''')
            lock_result = cur.fetchone()[0]
            if lock_result < 0:
                raise RuntimeError(f'Gagal mengunci alokasi IDFitur (kode {lock_result}).')
            cur.execute('SELECT ISNULL(MAX([IDFitur]), 0) + 1 FROM dbo.[ParamFitur] WITH (TABLOCKX, HOLDLOCK)')
            next_id = cur.fetchone()[0]
            if next_id is None or int(next_id) <= 0:
                raise RuntimeError('Tidak dapat menentukan IDFitur berikutnya.')
            chosen = ['IDFitur', *chosen]
            values = dict(values)
            values['IDFitur'] = (int(next_id), str(int(next_id)), False)
            print(f'[IDFitur DIALOKASIKAN] {next_id} (belum COMMIT)')
        cur.execute(f'SELECT COUNT_BIG(*) FROM dbo.{ident(table)} WITH (UPDLOCK,HOLDLOCK) WHERE {where}', params)
        count = cur.fetchone()[0]
        if (action == 'INSERT' and count != 0) or (action == 'UPDATE' and count != 1):
            raise RuntimeError(f'Target berubah atau tidak unik (count={count}).')
        bind = []
        literals = []
        for name in chosen:
            val, literal, expr = values[name]
            if expr:
                literals.append(literal)
            else:
                literals.append('?')
                bind.append(val)
        if action == 'INSERT':
            output_clause = ' OUTPUT INSERTED.[IDFitur] INTO @created' if return_identity else ''
            sql = (f'INSERT INTO dbo.{ident(table)} (' + ', '.join(ident(n) for n in chosen) +
                   ')' + output_clause + ' VALUES (' + ', '.join(literals) + ')')
            if return_identity:
                # OUTPUT ... INTO aman ketika tabel mempunyai INSERT trigger.
                sql = ('SET NOCOUNT ON; DECLARE @created TABLE (IDFitur bigint); '
                       + sql + '; SELECT IDFitur FROM @created;')
        else:
            sets = ', '.join(f'{ident(n)} = {v}' for n, v in zip(chosen, literals))
            sql = f'UPDATE dbo.{ident(table)} SET {sets} WHERE {where}'
            bind += params
        cur.execute(sql, bind)
        generated_id = None
        if return_identity:
            result_row = cur.fetchone()
            if result_row is None:
                raise RuntimeError('INSERT tidak mengembalikan IDFitur.')
            generated_id = result_row[0]
        if not return_identity and cur.rowcount not in (1, -1):
            raise RuntimeError(f'DML memengaruhi {cur.rowcount} baris, bukan 1.')
        print('\n[SEMENTARA] DML berhasil; transaksi BELUM COMMIT.')
        if action == 'UPDATE':
            # Jika kolom kunci ikut diubah, WHERE lama tidak lagi menemukan data.
            # Verifikasi tetap dilakukan melalui rowcount, lalu tampilkan SELECT jika tersedia.
            headers, rows = fetch_rows(cur, table, where, params)
            show_rows(headers, rows, 'HASIL SELECT (WHERE IDENTITAS AWAL)')
        elif return_identity:
            print(f'[IDFitur OTOMATIS] {generated_id}')
        else:
            headers, rows = fetch_rows(cur, table, where, params)
            show_rows(headers, rows, 'HASIL SELECT (WHERE CEK DUPLIKASI)')
            if not rows:
                print('[INFO] WHERE cek duplikasi tidak menemukan hasil INSERT; periksa default/identity.')
        if ask('Ketik COMMIT untuk menyimpan; input lain = ROLLBACK') != 'COMMIT':
            conn.rollback()
            print(f'[ROLLBACK] DML dibatalkan. Backup dbo.{backup} tetap ada.')
            return None if return_identity else False
        conn.commit()
        print(f'[COMMIT] Perubahan tersimpan. Backup dbo.{backup} tetap ada.')
        try:
            path = save_deployment(table, action, chosen, values, where, params, backup)
            print('[DEPLOYMENT]', path)
        except Exception as exc:
            print('[PERINGATAN] COMMIT berhasil tetapi gagal menyimpan deployment:', exc)
        return generated_id if return_identity else True
    except BaseException:
        conn.rollback()
        raise


# Identitas record mengikuti contoh deployment produk; hanya dipakai jika kolom ada.
KEY_RULES = {
    'ParamFitur': ('IDFitur',),
    'EndpoinInq': ('ID',), 'EndpoinList': ('ID',), 'EndpoinMCS': ('ID',),
    'MappingResultInq': ('IDFitur', 'EndPoin', 'Source'),
    'MappingResultMCS': ('IDFitur', 'EndPoin', 'Source'),
    'MappingConditionInq': ('IDFitur', 'EndPoin', 'Source'),
    'MappingConditionMCS': ('IDFitur', 'EndPoin', 'Source'),
    'MappingResultList': ('IDFitur', 'EndPoin'),
    'ResultDictionaryInq': ('IDFitur', 'EndPoin', 'Field'),
    'ResultDictionaryMCS': ('IDFitur', 'EndPoin', 'Field'),
    'ConditionDictionaryInq': ('IDFitur', 'EndPoin', 'Field'),
    'ConditionDictionaryMCS': ('IDFitur', 'EndPoin', 'Field'),
    'EndpoinFTP': ('IDFitur', 'EndPoin', 'Source'),
    'ConditionDictionaryFTP': ('IDFitur', 'EndPoin', 'Field', 'Posisi'),
}
INQ_REFS = ('MappingResultInq', 'MappingConditionInq', 'ResultDictionaryInq',
            'ConditionDictionaryInq')
MCS_REFS = ('MappingResultMCS', 'MappingConditionMCS', 'ResultDictionaryMCS',
            'ConditionDictionaryMCS')
LIST_REFS = ('MappingResultList',)


def discover_endpoints(conn, actual, product_id, references):
    """SELECT endpoint terkait produk dari tabel yang sudah memiliki konfigurasi.

    Hanya hasil nyata di database yang digunakan; tidak mengarang ID endpoint.
    """
    found = set()
    cur = conn.cursor()
    for table in references:
        if table not in actual:
            continue
        cols = {c['name'].lower(): c['name'] for c in columns_of(cur, table)}
        if 'idfitur' not in cols or 'endpoin' not in cols:
            continue
        cur.execute(f'SELECT DISTINCT {ident(cols["endpoin"])} FROM dbo.{ident(table)} '
                    f'WHERE {ident(cols["idfitur"])} = ?', product_id)
        found.update(r[0] for r in cur.fetchall() if r[0] is not None)
    conn.rollback()
    return sorted(found, key=lambda v: str(v))


def candidate_rows(conn, actual, table, cols, product_id):
    """SELECT konfigurasi existing yang relevan, tidak otomatis menganggap
    hasil SELECT sebagai daftar konfigurasi yang wajib dibuat.
    """
    names = {c['name'].lower(): c['name'] for c in cols}
    where, params = '1=1', []
    if 'idfitur' in names:
        where, params = f'{ident(names["idfitur"])} = ?', [product_id]
    elif 'id' in names:
        if table == 'EndpoinInq':
            ids = discover_endpoints(conn, actual, product_id, INQ_REFS)
        elif table == 'EndpoinMCS':
            ids = discover_endpoints(conn, actual, product_id, MCS_REFS)
        elif table == 'EndpoinList':
            ids = discover_endpoints(conn, actual, product_id, LIST_REFS)
        else:
            ids = []
        if not ids:
            return [], [], 'Tidak ada referensi endpoint dari SELECT konfigurasi produk.'
        where = f'{ident(names["id"])} IN (' + ','.join('?' for _ in ids) + ')'
        params = ids
    cur = conn.cursor()
    cur.execute(f'SELECT COUNT_BIG(*) FROM dbo.{ident(table)} WHERE {where}', params)
    total = cur.fetchone()[0]
    headers, rows = fetch_rows(cur, table, where, params, limit=50)
    conn.rollback()
    return headers, rows, f'SELECT menemukan {total} record (ditampilkan maksimal 50).'


def suggested_key_filter(cols, values, selected):
    """Kunci cek otomatis dari kolom yang sudah diisi; tidak memakai WHERE manual.
    Jika kunci tidak lengkap, minta filter eksplisit.
    """
    table_keys = [c['name'] for c in cols if c['pk']]
    names = {c['name'] for c in cols}
    keys = table_keys if table_keys and all(k in selected for k in table_keys) else []
    if not keys:
        for candidate in KEY_RULES.values():
            if all(k in names for k in candidate) and all(k in selected for k in candidate):
                keys = list(candidate)
                break
    if not keys:
        return None
    terms, params = [], []
    for key in keys:
        val, literal, expr = values[key]
        if expr:
            return None
        if val is None:
            terms.append(f'{ident(key)} IS NULL')
        else:
            terms.append(f'{ident(key)} = ?')
            params.append(val)
    return ' AND '.join(terms), params, ', '.join(keys)


def search_existing(conn, table, cols, limit=30):
    print(f'\n=== CARI EXISTING dbo.{table} ===')
    while True:
        idx = menu([c['name'] for c in cols] + ['Kembali'], 'Cari berdasarkan kolom')
        if idx == len(cols):
            return None
        c = cols[idx]
        raw = ask('Kata kunci / nilai ' + c['name'], secret=bool(SENSITIVE.search(c['name'])))
        if not raw:
            print('Kata kunci wajib diisi.')
            continue
        if c['type'] in NUM_TYPES:
            try:
                val, _, expr = parse_value(raw, c)
                if expr or val is None:
                    raise ValueError('Nilai tidak valid.')
            except ValueError as exc:
                print(exc)
                continue
            where, params = f'{ident(c["name"])} = ?', [val]
        else:
            where, params = f'{ident(c["name"])} LIKE ?', ['%' + raw + '%']
        headers, rows = fetch_rows(conn.cursor(), table, where, params, limit=limit)
        conn.rollback()
        show_rows(headers, rows, 'HASIL PENCARIAN', limit=limit)
        if not rows:
            continue
        choice = menu([f'Gunakan record {i+1}' for i in range(len(rows))] + ['Cari ulang', 'Kembali'], 'Pilih')
        if choice == len(rows):
            continue
        if choice == len(rows) + 1:
            return None
        row = dict(zip(headers, rows[choice]))
        if menu(['Konfirmasi gunakan record ini', 'Cari ulang'], 'Konfirmasi') == 0:
            return row


def paramfitur_stage(conn, cfg, cols):
    """Tidak pernah SELECT seluruh ParamFitur; hanya pencarian bila dipilih."""
    idcol = next((c for c in cols if c['name'].lower() == 'idfitur'), None)
    if not idcol:
        raise RuntimeError('Kolom ParamFitur.IDFitur tidak ditemukan.')
    # Jika IDFitur bukan IDENTITY dan tidak memiliki DEFAULT, alokasikan nomor
    # berikutnya di dalam transaksi terkunci, bukan meminta user mengetik ID.
    auto_allocate = not idcol['identity'] and not idcol['default']
    if auto_allocate and idcol['type'] not in {'tinyint', 'smallint', 'int', 'bigint'}:
        raise RuntimeError('IDFitur bukan IDENTITY/DEFAULT dan bukan bilangan bulat; perlu aturan generator DB.')
    editable = [c for c in editable_columns(cols) if c['name'].lower() != 'idfitur']
    order = {n: i for i, n in enumerate(PARAMFITUR_ORDER)}
    editable.sort(key=lambda c: order.get(c['name'], 999))
    while True:
        print('\n[1/15] PARAMFITUR (tidak menampilkan seluruh tabel)')
        idx = menu(['INSERT ParamFitur baru', 'Cari / gunakan ParamFitur existing',
                    'SKIP tabel', 'Kembali ke menu utama'], 'Tindakan')
        if idx in (2, 3):
            return None
        if idx == 1:
            row = search_existing(conn, 'ParamFitur', cols)
            if row is not None:
                print(f'[PRODUK AKTIF] IDFitur={row[idcol["name"]]}')
                return row[idcol['name']]
            continue
        values, chosen = input_with_review(editable)
        if not chosen:
            continue
        # Tidak meminta IDFitur. IDENTITY/DEFAULT dihasilkan DB, atau
        # dialokasikan dengan lock transaksi bila keduanya tidak tersedia.
        result = perform_change(conn, cfg, 'ParamFitur', 'INSERT', cols, chosen, values,
                                '1=0', [], 'IDFitur otomatis', return_identity=True, allocate_id=auto_allocate)
        conn.rollback()
        if result is not None:
            print(f'[PRODUK AKTIF] IDFitur={result}')
            return result


def insert_table(conn, cfg, actual, table, cols, product_id):
    editable = editable_columns(cols)
    names = {c['name'].lower(): c['name'] for c in cols}
    while True:
        print(f'\n=== [{TABLES.index(table)+1}/15] dbo.{table} | IDFitur aktif {product_id} ===')
        idx = menu(['INSERT record baru', 'SELECT / gunakan existing',
                    'SKIP / lanjut tabel berikutnya', 'Kembali ke tabel sebelumnya'], 'Tindakan')
        if idx == 2:
            return 'next'
        if idx == 3:
            return 'back'
        if idx == 1:
            row = search_existing(conn, table, cols)
            if row is not None:
                print('[EXISTING DIPILIH] Tidak ada INSERT duplikat.')
                if 'id' in names:
                    print(f'[REFERENSI ID] {row[names["id"]]}')
            continue
        if not editable:
            print('Tidak ada kolom editable.')
            continue
        preset = {}
        if 'idfitur' in names:
            c = next(c for c in cols if c['name'] == names['idfitur'])
            preset[c['name']] = (product_id, str(product_id), False)
        values, chosen = input_with_review(editable, preset)
        if not chosen:
            continue
        keys = KEY_RULES.get(table, ())
        if keys and all(k in chosen for k in keys):
            terms, params = [], []
            for key in keys:
                value, _, expr = values[key]
                if expr:
                    raise ValueError('Kolom kunci tidak boleh menggunakan ekspresi SQL.')
                if value is None:
                    terms.append(f'{ident(key)} IS NULL')
                else:
                    terms.append(f'{ident(key)} = ?')
                    params.append(value)
            where, desc = ' AND '.join(terms), ', '.join(keys)
        else:
            print('[PERINGATAN] Kunci belum lengkap; pilih filter untuk pengecekan duplikasi.')
            where, params, desc = filter_builder(cols)
        cur = conn.cursor()
        cur.execute(f'SELECT COUNT_BIG(*) FROM dbo.{ident(table)} WHERE {where}', params)
        count = cur.fetchone()[0]
        conn.rollback()
        if count:
            print(f'[EXISTS → SKIP] {count} record cocok. Silakan INSERT record lain atau SKIP tabel.')
            continue
        perform_change(conn, cfg, table, 'INSERT', cols, chosen, values, where, params, desc)
        conn.rollback()


def insert_wizard(conn, cfg, actual):
    if 'ParamFitur' not in actual:
        print('[GAGAL] dbo.ParamFitur tidak ditemukan.')
        return
    cols = columns_of(conn.cursor(), 'ParamFitur')
    conn.rollback()
    product_id = paramfitur_stage(conn, cfg, cols)
    if product_id is None:
        print('[BATAL] Tidak ada produk aktif; kembali ke menu utama.')
        return
    index = 1
    while index < len(TABLES):
        table = TABLES[index]
        print(f'\n{"="*64}\nINSERT BERURUTAN [{index+1}/{len(TABLES)}] dbo.{table}\n{"="*64}')
        if table not in actual:
            print('[TABEL TIDAK ADA] Dilewati otomatis.')
            index += 1
            continue
        cols = columns_of(conn.cursor(), table)
        conn.rollback()
        try:
            direction = insert_table(conn, cfg, actual, table, cols, product_id)
        except (Exception, KeyboardInterrupt, EOFError) as exc:
            conn.rollback()
            print('[GAGAL / ROLLBACK]', exc)
            direction = 'back' if ask('Ketik B untuk kembali, lainnya lanjut').upper() == 'B' else 'next'
        index = max(1, index - 1) if direction == 'back' else index + 1
    print(f'\n[SELESAI] Semua tabel diproses. IDFitur aktif: {product_id}')


def update_wizard(conn, cfg, actual):
    while True:
        options = [t for t in TABLES if t in actual] + [t for t in sorted(actual) if t not in TABLES]
        idx = menu(options + ['Kembali ke menu utama'], 'Pilih tabel UPDATE')
        if idx == len(options):
            return
        table = options[idx]
        cols = columns_of(conn.cursor(), table)
        conn.rollback()
        print(f'\n=== UPDATE dbo.{table} ===')
        try:
            where, params, desc = filter_builder(cols)
            headers, rows = fetch_rows(conn.cursor(), table, where, params, limit=50)
            show_rows(headers, rows, f'HASIL FILTER: {desc}', limit=50)
            if not rows:
                print('Tidak ada record sesuai filter.')
                conn.rollback()
                continue
            if len(rows) == 50:
                print('[PERINGATAN] Hanya 50 record pertama ditampilkan; persempit filter jika perlu.')
            idx = menu([f'Record {i+1}' for i in range(len(rows))] + ['Batal'], 'Pilih record')
            if idx == len(rows):
                conn.rollback()
                continue
            identity_where, identity_params = unique_identity(cols, rows[idx], headers)
            conn.rollback()
            print('\n=== PILIH KOLOM YANG AKAN DIUBAH ===')
            editable = [c for c in editable_columns(cols) if not c['pk'] and c['name'] != 'IDFitur']
            if not editable:
                print('Tidak ada kolom yang dapat di-update.')
                continue
            chosen = []
            values = {}
            while True:
                pick = menu([c['name'] for c in editable] + ['SELESAI pilih kolom'], 'Kolom UPDATE')
                if pick == len(editable):
                    break
                col = editable[pick]
                raw = ask('Nilai baru ' + col['name'], secret=bool(SENSITIVE.search(col['name'])))
                if not raw:
                    print('Kosong berarti batal untuk kolom ini.')
                    continue
                try:
                    values[col['name']] = parse_value(raw, col)
                except ValueError as exc:
                    print(exc)
                    continue
                if col['name'] not in chosen:
                    chosen.append(col['name'])
            if chosen:
                perform_change(conn, cfg, table, 'UPDATE', cols, chosen, values,
                               identity_where, identity_params, f'{desc} -> record {idx+1}')
        except (Exception, KeyboardInterrupt, EOFError) as exc:
            conn.rollback()
            print('[GAGAL / ROLLBACK]', exc)
        conn.rollback()


def run():
    print('\n=== REKONENTERPRISEAPI | INSERT BERURUTAN / UPDATE FILTER ===')
    cfg = choose_rekon_server()  # hanya 205 / localhost, tanpa mengubah db_config.py
    conn = connect_sqlserver(cfg, DATABASE)
    try:
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute('SELECT DB_NAME()')
        if str(cur.fetchone()[0]).lower() != DATABASE.lower():
            raise RuntimeError('Koneksi bukan ke database RekonEnterpriseAPI.')
        cur.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='dbo' AND TABLE_TYPE='BASE TABLE'")
        actual = {r[0] for r in cur.fetchall() if '_Backup_' not in r[0]}
        conn.rollback()
        while True:
            idx = menu(['INSERT 15 tabel berurutan', 'UPDATE pilih tabel dan filter kolom', 'SELESAI'], 'Operasi')
            if idx == 2:
                break
            if idx == 0:
                insert_wizard(conn, cfg, actual)
            else:
                update_wizard(conn, cfg, actual)
        print('Wizard selesai.')
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


if __name__ == '__main__':
    try:
        run()
    except (Exception, KeyboardInterrupt, EOFError) as exc:
        print('[GAGAL / DIBATALKAN]', exc)
        sys.exit(1)
