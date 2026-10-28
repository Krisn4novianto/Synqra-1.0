#!/usr/bin/env python3
"""Read-only OtomasiMCS deployment SQL generator. Run from Synqra project root."""
from __future__ import annotations
import re
import sys
from datetime import datetime, date, time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from db_config import SERVERS
from db_connection import connect_sqlserver

DATABASE = 'OtomasiMCS'
FEATURE_COLS = ('Modul Name FiturID SettlementTarget MaxCount DBName SourceTable WhereCondition '
                'DateCol StatusCol MakerCol CheckerCol SignerCol OldestDataDate SchStart SchEnd '
                'StatusValueApproved isOtomasiMCS StatusValuePrepareSendSettlement '
                'StatusValueDoneSendSettlement isSendSettlement').split()
CEKLOG_COLS = 'IDFitur LogActivityModul LogActivitySubModul LogActivityEntity LogActivityDateAdd IsActive'.split()
PEMBUKUAN_COLS = ('IDFitur IdTrans AppName TranCode BranchCode TellerId SupervisorId '
                  + ' '.join(f'Bucket{i}' for i in range(1, 21))
                  + ' ThirdPartyName TellerRemark1 TellerRemark2 DefaultCurrency '
                    'AlternateCurrency1 AlternateCurrency2 AlternateCurrency3 Seq DateTrans').split()
CHILDREN = {'ParamFiturCekLogActivity': CEKLOG_COLS, 'ParamQryPembukuanRekonESB': PEMBUKUAN_COLS}
OPTIONS = {'1': 'Semua', '2': 'ParamFitur', '3': 'ParamFiturCekLogActivity', '4': 'ParamQryPembukuanRekonESB'}
PROD_COLS = ['Modul', 'Name', 'FiturID', 'SettlementTarget', 'MaxCount', 'IPServer',
             'DBName', 'DBUser', 'DBPass', 'SourceTable', 'WhereCondition', 'DateCol',
             'StatusCol', 'MakerCol', 'CheckerCol', 'SignerCol', 'OldestDataDate',
             'SchStart', 'SchEnd', 'StatusValueApproved', 'isOtomasiMCS',
             'StatusValuePrepareSendSettlement', 'StatusValueDoneSendSettlement', 'isSendSettlement']

def ident(value):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', value):
        raise ValueError(f'Identifier tidak valid: {value}')
    return f'[{value}]'

def lit(value):
    if value is None: return 'NULL'
    if isinstance(value, bool): return '1' if value else '0'
    if isinstance(value, (int, float, Decimal)): return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)): return '0x' + bytes(value).hex()
    if isinstance(value, datetime): value = value.isoformat(sep=' ')
    elif isinstance(value, (date, time)): value = value.isoformat()
    return "N'" + str(value).replace("'", "''") + "'"

def metadata(cur, table):
    cur.execute('''SELECT c.name,c.is_identity,c.is_computed,c.system_type_id
      FROM sys.columns c JOIN sys.tables t ON t.object_id=c.object_id
      JOIN sys.schemas s ON s.schema_id=t.schema_id
      WHERE s.name='dbo' AND t.name=? ORDER BY c.column_id''', table)
    rows = cur.fetchall()
    if not rows: raise RuntimeError(f'Tabel dbo.{table} tidak ditemukan.')
    return {r[0].lower(): (r[0], bool(r[1]), bool(r[2]), int(r[3])) for r in rows}

def validate(meta, table, cols):
    for c in cols:
        if c.lower() not in meta: raise RuntimeError(f'dbo.{table}: kolom {c} tidak ditemukan')
        _, identity, computed, typ = meta[c.lower()]
        if computed or typ == 189: raise RuntimeError(f'dbo.{table}.{c}: computed/rowversion')
        if identity and c.lower() != 'idfitur': raise RuntimeError(f'dbo.{table}.{c}: identity tidak didukung dalam daftar insert')

def fetch(cur, table, cols, fid):
    cur.execute(f'SELECT {", ".join(map(ident, cols))} FROM dbo.{ident(table)} WHERE [IDFitur]=?', fid)
    return [dict(zip(cols, r)) for r in cur.fetchall()]

def choose_server():
    options = {'1': SERVERS['2'], '2': SERVERS['3']}
    while True:
        print('\n=== PILIH SERVER SUMBER ===')
        for k, v in options.items(): print(f'{k}. {v.name}:{v.port}')
        print('0. Keluar')
        answer = input('Pilihan [1/2/0]: ').strip()
        if answer == '0': sys.exit(0)
        if answer in options: return options[answer]
        print('[ERROR] Pilihan tidak valid.')

def choose_table():
    while True:
        print('\n=== PILIH TABEL ===')
        for k, v in OPTIONS.items(): print(f'{k}. {v}')
        print('0. Keluar')
        answer = input('Pilihan [1/2/3/4/0]: ').strip()
        if answer == '0': sys.exit(0)
        if answer in OPTIONS: return answer
        print('[ERROR] Pilihan tidak valid.')

def filename_for(selection, feature):
    today = datetime.now().strftime('%Y%m%d')
    if selection == '1': return f'SOP OtomasiMCS_{today}.sql'
    name = '_'.join(str(feature[k]) for k in ('Modul', 'Name') if feature.get(k))
    name = re.sub(r'[^A-Za-z0-9_-]+', '_', name).strip('_-')[:80] or 'TanpaNamaModul'
    return f'SOP OtomasiMCS_{OPTIONS[selection]}_{name}_{today}.sql'

def condition(row, keys):
    return ' AND '.join(f'{ident(k)} IS NULL' if row[k] is None else f'{ident(k)}={lit(row[k])}' for k in keys)

def render_children(table, cols, rows):
    out = [f'-- {table} | {len(rows)} baris']
    for row in rows:
        # Without a documented business key, all non-FK columns form an exact-row key.
        keys = cols[1:]
        predicates = ['[IDFitur]=@IDFitur'] + [f'{ident(k)} IS NULL' if row[k] is None else f'{ident(k)}={lit(row[k])}' for k in keys]
        values = ['@IDFitur'] + [lit(row[k]) for k in keys]
        out.extend([
            f'IF NOT EXISTS (SELECT 1 FROM dbo.{ident(table)} WITH (UPDLOCK,HOLDLOCK) WHERE {" AND ".join(predicates)})',
            'BEGIN',
            f'    INSERT INTO dbo.{ident(table)} ({", ".join(map(ident, cols))})',
            f'    VALUES ({", ".join(values)});',
            'END;', ''
        ])
    return out

def generate(feature, children, selection, ip, user):
    fid = feature['IDFitur']
    natural = condition(feature, ('Modul', 'Name', 'FiturID'))
    values = []
    for col in PROD_COLS:
        if col == 'IPServer': values.append(lit(ip))
        elif col == 'DBUser': values.append(lit(user))
        elif col == 'DBPass': values.append(f"dbo.[fnEncrypt](N'$(PasswordProduction)', {lit(ip + 'BR!')})")
        else: values.append(lit(feature[col]))
    out = [
        '-- SOP OtomasiMCS | Generate Script Deploy',
        f'-- Generated: {datetime.now():%Y-%m-%d %H:%M:%S}',
        f'-- Source IDFitur: {fid}',
        f'-- Scope: {OPTIONS[selection]}',
        '-- SQLCMD PasswordProduction wajib disediakan saat eksekusi.',
        '-- PERINGATAN: SQLCMD adalah substitusi teks; password dengan apostrof harus di-escape.',
        '-- Source read-only. SQL ini belum dieksekusi.',
        'USE [OtomasiMCS];', 'GO', 'SET NOCOUNT ON;', 'SET XACT_ABORT ON;',
        'BEGIN TRY', '    BEGIN TRANSACTION;',
        '-- ParamFitur (induk)',
        f'IF (SELECT COUNT_BIG(*) FROM dbo.[ParamFitur] WITH (UPDLOCK,HOLDLOCK) WHERE {natural}) > 1',
        "    THROW 51001, N'Duplikat natural key ParamFitur target', 1;",
        f'IF NOT EXISTS (SELECT 1 FROM dbo.[ParamFitur] WITH (UPDLOCK,HOLDLOCK) WHERE {natural})',
        'BEGIN',
        f'    INSERT INTO dbo.[ParamFitur] ({", ".join(map(ident, PROD_COLS))})',
        f'    VALUES ({", ".join(values)});',
        'END;',
        'DECLARE @IDFitur INT;',
        f'SELECT @IDFitur=[IDFitur] FROM dbo.[ParamFitur] WHERE {natural};',
        "IF @IDFitur IS NULL THROW 51002, N'IDFitur target tidak ditemukan', 1;", ''
    ]
    for table, cols in CHILDREN.items():
        if selection == '1' or OPTIONS[selection] == table:
            out.extend(render_children(table, cols, children[table]))
    out.extend(['    COMMIT TRANSACTION;', "    PRINT N'DEPLOY SUCCESS';", 'END TRY',
                'BEGIN CATCH', '    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;',
                '    THROW;', 'END CATCH;', ''])
    return '\n'.join(out)

def heading(title):
    print(f"\n=== {title} ===")


def detail(label, value):
    print(f"  {label:<22}: {value}")


def ask(prompt):
    value = input(prompt).strip()
    if value.lower() in ('q', 'keluar', 'exit'):
        print('Program ditutup. Tidak ada file dibuat.')
        sys.exit(0)
    return value


def find_features(cur, keyword):
    # Cari IDFitur, Modul, Name, FiturID.
    term = keyword.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_').replace('[', '[[]')
    pattern = '%' + term + '%'
    cur.execute('''SELECT TOP (50) [IDFitur], [Modul], [Name], [FiturID]
        FROM dbo.[ParamFitur]
        WHERE CONVERT(NVARCHAR(30), [IDFitur]) LIKE ? ESCAPE '\\'
           OR CONVERT(NVARCHAR(MAX), [Modul]) LIKE ? ESCAPE '\\'
           OR CONVERT(NVARCHAR(MAX), [Name]) LIKE ? ESCAPE '\\'
           OR CONVERT(NVARCHAR(MAX), [FiturID]) LIKE ? ESCAPE '\\'
        ORDER BY [Modul], [Name], [IDFitur]''', pattern, pattern, pattern, pattern)
    return cur.fetchall()


def choose_feature(cur):
    while True:
        heading('CARI FITUR SUMBER')
        print('  Masukkan IDFitur, nama Modul, Name, atau FiturID.')
        print('  Pencarian mendukung sebagian kata (LIKE).')
        print('  0. Kembali ke menu tabel')
        print('  q. Keluar')
        term = ask('  Kata kunci pencarian: ')
        if term == '0':
            return None
        if not term:
            print('  [INFO] Kata kunci tidak boleh kosong. Silakan coba lagi.')
            continue
        results = find_features(cur, term)
        if not results:
            print('\n  [INFO] Data tidak ditemukan. Coba kata kunci lebih pendek.')
            print('  Anda bisa mencari ulang, kembali (0), atau keluar (q).')
            continue
        heading('HASIL PENCARIAN FITUR')
        for i, r in enumerate(results, 1):
            print(f'  [{i}]')
            detail('IDFitur', r[0])
            detail('Modul', r[1])
            detail('Name', r[2])
            detail('FiturID', r[3])
            print()
        print('  0. Cari ulang')
        print('  q. Keluar')
        while True:
            choice = ask(f'  Pilih nomor [1-{len(results)}], 0, atau q: ')
            if choice == '0':
                break
            if choice.isdigit() and 1 <= int(choice) <= len(results):
                return int(results[int(choice) - 1][0])
            print('  [ERROR] Pilihan tidak valid.')


def ask_required(label, maxlen=50):
    while True:
        value = ask(f'  {label}: ')
        if value and len(value) <= maxlen and '\n' not in value and '\r' not in value:
            return value
        print(f'  [ERROR] Wajib diisi, maksimal {maxlen} karakter. Ketik q untuk keluar.')


def confirm(prompt):
    while True:
        answer = ask(prompt).lower()
        if answer in ('ya', 'y', 'yes'):
            return True
        if answer in ('tidak', 't', 'no', 'n', '0'):
            return False
        print('  [ERROR] Ketik YA atau TIDAK (atau q untuk keluar).')


def main():
    print('=== OTOMASIMCS | GENERATE SCRIPT DEPLOY SOP ===')
    print('  Membaca database sumber (SELECT saja).')
    print('  SQL disimpan sebagai file, tidak langsung dieksekusi.')
    config = choose_server()
    while True:
        selection = choose_table()
        print('\n[INFO] Menghubungkan ke database sumber...')
        conn = connect_sqlserver(config, DATABASE)
        try:
            cur = conn.cursor()
            meta = metadata(cur, 'ParamFitur')
            validate(meta, 'ParamFitur', FEATURE_COLS + [c for c in PROD_COLS if c not in ('IPServer', 'DBUser', 'DBPass')])
            fid = choose_feature(cur)
            if fid is None:
                continue
            features = fetch(cur, 'ParamFitur', ['IDFitur'] + FEATURE_COLS, fid)
            if len(features) != 1:
                print(f'  [INFO] IDFitur {fid} tidak ditemukan atau tidak unik. Cari ulang.')
                continue
            feature = features[0]
            for key in ('Modul', 'Name', 'FiturID'):
                if feature[key] is None:
                    raise RuntimeError(f'ParamFitur.{key} tidak boleh NULL.')
            children = {}
            for table, cols in CHILDREN.items():
                if selection == '1' or OPTIONS[selection] == table:
                    validate(metadata(cur, table), table, cols)
                    children[table] = fetch(cur, table, cols, fid)
        finally:
            conn.close()

        heading('KONFIGURASI DATABASE TUJUAN')
        print('  Isi konfigurasi production untuk script deployment.')
        print('  Password tidak diminta; gunakan SQLCMD PasswordProduction.')
        ip = ask_required('IPServer produksi')
        user = ask_required('DBUser produksi')
        name = filename_for(selection, feature)
        outdir = Path(__file__).resolve().parent / 'output'
        path = outdir / name
        heading('PREVIEW KONFIGURASI DEPLOYMENT')
        detail('Server sumber', config.name)
        detail('Database', DATABASE)
        detail('Pilihan tabel', OPTIONS[selection])
        print()
        detail('IDFitur sumber', fid)
        detail('Modul', feature['Modul'])
        detail('Name', feature['Name'])
        detail('FiturID', feature['FiturID'])
        print()
        detail('IPServer produksi', ip)
        detail('DBUser produksi', user)
        heading('RINCIAN DATA YANG AKAN DI-GENERATE')
        detail('ParamFitur (induk)', '1 baris')
        total = 1
        for table, rows in children.items():
            print(f'  - {table}')
            detail('Jumlah data', f'{len(rows)} baris')
            total += len(rows)
        print('  ' + '-' * 48)
        detail('TOTAL DATA', f'{total} baris')
        heading('INFORMASI FILE OUTPUT')
        print('  Nama file:')
        print(f'    {name}')
        print('  Folder penyimpanan:')
        print(f'    {outdir}')
        print('\n  Keterangan:')
        print('  - Database sumber hanya dibaca (SELECT).')
        print('  - Script SQL belum dijalankan.')
        print('  - PasswordProduction harus diisi melalui SQLCMD saat deployment.')
        print('  - Periksa script sebelum menjalankan di production.')
        if not confirm('\n  Lanjut buat file SQL? [YA/TIDAK]: '):
            print('  [INFO] Dibatalkan. File belum dibuat.')
            if confirm('  Cari fitur lain? [YA/TIDAK]: '):
                continue
            return
        if path.exists():
            print('  [PERINGATAN] File output dengan nama yang sama sudah ada.')
            if not confirm('  Timpa file lama? [YA/TIDAK]: '):
                print('  [INFO] File lama tetap disimpan.')
                continue
        sql = generate(feature, children, selection, ip, user)
        outdir.mkdir(parents=True, exist_ok=True)
        path.write_text(sql, encoding='utf-8')
        try:
            path.chmod(0o600)
        except OSError:
            pass
        heading('GENERATE BERHASIL')
        detail('Nama file', name)
        detail('Lokasi', outdir)
        print('  [OK] SQL siap direview; belum dieksekusi.')
        return


if __name__ == '__main__':
    try: main()
    except KeyboardInterrupt:
        print('\nDibatalkan oleh pengguna.', file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f'[ERROR] {exc}', file=sys.stderr)
        sys.exit(1)
