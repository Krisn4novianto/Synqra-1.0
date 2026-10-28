#!/usr/bin/env python3
"""Generate DataFlowParam deployment SQL from a read-only source connection.

Requires db_config.SERVERS and db_connection.connect_sqlserver.
Only the selected IDFitur and its dependent records are exported, not the
entire database. Generated SQL requires manual review before execution.
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

DATABASE = "DataFlowParam"
SERVER_COLUMNS = ("IPServer", "DBUser", "DBPass", "DBType", "DBPort", "IsListenerHA", "ApplicationIntent", "InitialCatalog")
FEATURE_COLUMNS = (
    "FiturName", "IPServerSourceId", "DBSource", "StoredProcedureExecute",
    "TableSourceA", "TableSourceB", "TableSourceC", "TableSourceD",
    "AJoinBType", "ABJoinCType", "ABCJoinDType", "AJoinBKey", "ABJoinCKey", "ABCJoinDKey",
    "FieldSelect", "WhereCondition", "GroupByCondition", "HavingCondition", "OrderByCondition",
    "IPServerDestinationId", "DBDestination", "TableDestination", "IPServerLogActivityId",
    "LogActivityModul", "LogActivitySubModul", "LogActivityEntity",
    "LogActivityDateAddSource", "LogActivityDateAddDestination", "isActive", "Note",
)
CHILD_COLUMNS = ("IDFitur", "IPServerLogActivityId", "LogActivityModul", "LogActivitySubModul", "LogActivityEntity", "LogActivityDateAdd", "IsActive")
FEATURE_KEYS = ("FiturName", "DBSource", "DBDestination", "TableDestination", "LogActivityModul", "LogActivitySubModul", "LogActivityEntity")
ROLES = (("Source", "IPServerSourceId"), ("Destination", "IPServerDestinationId"), ("LogActivity", "IPServerLogActivityId"))
TABLE_OPTIONS = {"1": "Semua", "2": "ParamServer", "3": "ParamFitur", "4": "ParamFiturCekLogActivity"}


def literal(value):
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    if isinstance(value, (date, datetime, time)):
        return "N'" + value.isoformat().replace("'", "''") + "'"
    if isinstance(value, bytes):
        return "0x" + value.hex()
    return "N'" + str(value).replace("'", "''") + "'"


def ident(name):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError(f"Identifier tidak valid: {name}")
    return f"[{name}]"


def condition(row, keys):
    return " AND ".join(f"{ident(k)} IS NULL" if row[k] is None else f"{ident(k)} = {literal(row[k])}" for k in keys)


def fetch(cur, table, columns, where, args=()):
    query = f"SELECT {', '.join(map(ident, columns))} FROM dbo.{ident(table)} WHERE {where}"
    cur.execute(query, *args)
    keys = [c[0] for c in cur.description]
    return [dict(zip(keys, row)) for row in cur.fetchall()]


def exactly_one(rows, label):
    if len(rows) != 1:
        raise RuntimeError(f"{label}: harus tepat satu baris; ditemukan {len(rows)}")
    return rows[0]


def section(title):
    print("\n" + "=" * 62)
    print("  " + title)
    print("=" * 62)


def ask(prompt):
    value = input(prompt).strip()
    if value.lower() == "q":
        print("\nProgram dihentikan oleh pengguna.")
        sys.exit(0)
    return value


def choose_connection():
    options = {"1": SERVERS["2"], "2": SERVERS["3"]}
    while True:
        section("PILIH SERVER SUMBER")
        print("  Pilih database yang akan dibaca. Tidak ada perubahan pada sumber.\n")
        for key, cfg in options.items():
            print(f"  {key}. {cfg.name}:{cfg.port}")
        print("  0. Keluar")
        choice = ask("\n  Pilihan [1/2/0]: ")
        if choice == "0":
            sys.exit(0)
        if choice in options:
            return options[choice]
        print("  [ERROR] Pilihan tidak valid. Silakan ulangi.")


def choose_tables():
    while True:
        section("PILIH TABEL DEPLOYMENT")
        print("  Tabel induk yang diperlukan otomatis ikut disertakan.\n")
        print("  1. Semua tabel (ParamServer + ParamFitur + child)")
        print("  2. ParamServer saja")
        print("  3. ParamFitur (termasuk ParamServer)")
        print("  4. ParamFiturCekLogActivity (termasuk semua induk)")
        print("  0. Keluar")
        choice = ask("\n  Pilihan [1/2/3/4/0]: ")
        if choice == "0":
            sys.exit(0)
        if choice in TABLE_OPTIONS:
            return choice
        print("  [ERROR] Pilihan tidak valid.")


def search_feature(cur):
    while True:
        section("CARI FITUR SUMBER")
        print("  Cari menggunakan IDFitur, FiturName, DBSource, DBDestination,")
        print("  Modul, SubModul, atau Entity. Boleh ketik sebagian kata (LIKE).")
        print("  Contoh: REKON, SETTLEMENT, atau 1234.")
        print("  0. Kembali ke menu tabel | q. Keluar\n")
        keyword = ask("  Kata kunci pencarian: ")
        if keyword == "0":
            return None
        if not keyword:
            print("  [INFO] Masukkan kata kunci terlebih dahulu.")
            continue
        fields = ("FiturName", "DBSource", "DBDestination", "TableDestination",
                  "LogActivityModul", "LogActivitySubModul", "LogActivityEntity")
        escaped = keyword.replace("[", "[[]").replace("%", "[%]").replace("_", "[_]")
        pattern = "%" + escaped + "%"
        where = " OR ".join("[" + col + "] LIKE ?" for col in fields)
        args = [pattern] * len(fields)
        if keyword.isdigit():
            where = "[IDFitur] = ? OR " + where
            args.insert(0, int(keyword))
        sql = ("SELECT TOP (100) [IDFitur], [FiturName], [DBSource], [DBDestination], "
               "[LogActivityModul], [LogActivitySubModul], [LogActivityEntity] "
               "FROM dbo.[ParamFitur] WHERE " + where + " ORDER BY [IDFitur]")
        cur.execute(sql, *args)
        rows = cur.fetchall()
        if not rows:
            print("\n  [INFO] Tidak ditemukan fitur yang cocok.")
            print("  Coba kata kunci lebih pendek atau pilih tabel lain.")
            continue
        section("HASIL PENCARIAN FITUR")
        for i, row in enumerate(rows, 1):
            print(f"  [{i}]")
            for label, value in zip(("IDFitur", "FiturName", "DBSource", "DBDestination",
                                     "Modul", "SubModul", "Entity"), row):
                print(f"    {label:<22}: {value if value is not None else '-'}")
            print("  " + "-" * 54)
        if len(rows) == 100:
            print("  [INFO] Maksimal 100 hasil; gunakan kata kunci lebih spesifik.")
        print("  0. Cari ulang | q. Keluar")
        while True:
            selected = ask(f"\n  Pilih nomor [1-{len(rows)}] / 0 / q: ")
            if selected == "0":
                break
            if selected.isdigit() and 1 <= int(selected) <= len(rows):
                row = rows[int(selected) - 1]
                print(f"\n  [OK] Fitur dipilih: {row[0]} - {row[1]}")
                return int(row[0])
            print("  [ERROR] Pilih nomor yang tersedia, 0, atau q.")


def prompt_role(role, source):
    section(f"KONFIGURASI TARGET - {role.upper()}")
    print("  Masukkan server dan user tujuan untuk role ini.")
    print(f"  IPServer sumber : {source.get('IPServer') or '-'}")
    print(f"  DBUser sumber   : {source.get('DBUser') or '-'}")
    print("  Ketik q untuk keluar.\n")
    while True:
        host = ask(f"  IPServer {role} target : ")
        user = ask(f"  DBUser {role} target   : ")
        if host and user and len(host) <= 250 and len(user) <= 250 and not any(x in host + user for x in "\r\n"):
            return {**source, "IPServer": host, "DBUser": user}
        print("  [ERROR] Host dan user wajib diisi (maks. 250 karakter).")


def load_source_data(cur, feature_id, selection):
    feature = exactly_one(fetch(cur, "ParamFitur", FEATURE_COLUMNS, "IDFitur=?", (feature_id,)), "ParamFitur")
    sources = {}
    for role, field in ROLES:
        if feature[field] is None:
            raise RuntimeError(f"{field} NULL pada IDFitur {feature_id}")
        sources[role] = exactly_one(fetch(cur, "ParamServer", SERVER_COLUMNS, "IdServer=?", (feature[field],)), f"ParamServer {role}")
    children = fetch(cur, "ParamFiturCekLogActivity", CHILD_COLUMNS, "IDFitur=?", (feature_id,)) if selection in ("1", "4") else []
    return feature, sources, children


def render_server(role, row):
    where = condition(row, ("IPServer", "DBUser"))
    # SQLCMD substitutions are textual. Do not execute without validating passwords.
    secret = f"N'$(Password{role})'"
    encrypted = f"dbo.fnEncrypt({secret}, {literal(row['IPServer'] + 'BR!')})"
    values = [encrypted if col == "DBPass" else literal(row[col]) for col in SERVER_COLUMNS]
    var = f"@IDServer{role}"
    return [
        f"-- ParamServer: {role}",
        f"IF (SELECT COUNT_BIG(*) FROM dbo.ParamServer WITH (UPDLOCK,HOLDLOCK) WHERE {where}) > 1",
        "    THROW 51001, N'Duplikat ParamServer pada target', 1;",
        f"IF NOT EXISTS (SELECT 1 FROM dbo.ParamServer WITH (UPDLOCK,HOLDLOCK) WHERE {where})",
        "BEGIN",
        f"    INSERT INTO dbo.ParamServer ({', '.join(map(ident, SERVER_COLUMNS))})",
        f"    VALUES ({', '.join(values)});",
        "END;",
        f"DECLARE {var} INT;",
        f"SELECT {var}=IdServer FROM dbo.ParamServer WHERE {where};",
        f"IF {var} IS NULL THROW 51002, N'ID ParamServer target tidak ditemukan', 1;",
        "",
    ]


def render_feature(feature):
    where = condition(feature, FEATURE_KEYS)
    foreign = {"IPServerSourceId": "@IDServerSource", "IPServerDestinationId": "@IDServerDestination", "IPServerLogActivityId": "@IDServerLogActivity"}
    values = [foreign.get(col, literal(feature[col])) for col in FEATURE_COLUMNS]
    return [
        "-- ParamFitur",
        f"IF (SELECT COUNT_BIG(*) FROM dbo.ParamFitur WITH (UPDLOCK,HOLDLOCK) WHERE {where}) > 1",
        "    THROW 51003, N'Duplikat ParamFitur pada target', 1;",
        f"IF NOT EXISTS (SELECT 1 FROM dbo.ParamFitur WITH (UPDLOCK,HOLDLOCK) WHERE {where})",
        "BEGIN",
        f"    INSERT INTO dbo.ParamFitur ({', '.join(map(ident, FEATURE_COLUMNS))})",
        f"    VALUES ({', '.join(values)});",
        "END;",
        "DECLARE @IDFitur INT;",
        f"SELECT @IDFitur=IDFitur FROM dbo.ParamFitur WHERE {where};",
        "IF @IDFitur IS NULL THROW 51004, N'IDFitur target tidak ditemukan', 1;",
        "",
    ]


def render_children(children):
    lines = ["-- ParamFiturCekLogActivity: INSERT hanya bila belum ada"]
    for row in children:
        values = ["@IDFitur", "@IDServerLogActivity"] + [literal(row[c]) for c in CHILD_COLUMNS[2:]]
        predicates = ["[IDFitur]=@IDFitur", "[IPServerLogActivityId]=@IDServerLogActivity"]
        predicates.extend(f"{ident(c)} IS NULL" if row[c] is None else f"{ident(c)}={literal(row[c])}" for c in CHILD_COLUMNS[2:])
        lines.extend([
            "IF NOT EXISTS (",
            "    SELECT 1 FROM dbo.ParamFiturCekLogActivity WITH (UPDLOCK,HOLDLOCK)",
            "    WHERE " + " AND ".join(predicates),
            ")",
            "BEGIN",
            f"    INSERT INTO dbo.ParamFiturCekLogActivity ({', '.join(map(ident, CHILD_COLUMNS))})",
            f"    VALUES ({', '.join(values)});",
            "END;",
        ])
    if not children:
        lines.append("-- Tidak ada data child untuk IDFitur sumber ini.")
    lines.append("")
    return lines


def generate(feature_id, targets, selection, feature, children):
    lines = [
        "-- ===============================================================",
        "-- DataFlowParam | Generate Script Deploy",
        f"-- Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"-- Source IDFitur: {feature_id}",
        f"-- FiturName: {str(feature['FiturName']).replace(chr(10), ' ')}",
        f"-- Selection: {TABLE_OPTIONS[selection]}",
        "-- Generated script is for manual review and execution on target.",
        "-- SQLCMD variables: PasswordSource / PasswordDestination / PasswordLogActivity",
        "-- CAUTION: SQLCMD substitutions are textual, not bound parameters.",
        "-- Validate and safely escape password values before execution.",
        "-- Source database is never modified by the Python generator.",
        "-- ===============================================================",
        "USE [DataFlowParam];", "GO", "SET XACT_ABORT ON;", "BEGIN TRY", "    BEGIN TRANSACTION;", "",
    ]
    for role, _ in ROLES:
        lines.extend(render_server(role, targets[role]))
    if selection in ("1", "3", "4"):
        lines.extend(render_feature(feature))
    if selection in ("1", "4"):
        lines.extend(render_children(children))
    lines.extend([
        "    COMMIT TRANSACTION;", "    PRINT N'DEPLOY SUCCESS';",
        "END TRY", "BEGIN CATCH", "    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;",
        "    THROW;", "END CATCH;", "",
    ])
    return "\n".join(lines)


def safe_filename(value):
    value = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip())
    return re.sub(r"_+", "_", value).strip("_-")[:80] or "TanpaNamaModul"


def build_output_path(selection, feature):
    output = Path(__file__).resolve().parent / "output"
    output.mkdir(parents=True, exist_ok=True)
    tanggal = datetime.now().strftime("%Y%m%d")
    if selection == "1":
        filename = f"SOP DataFlowParam_{tanggal}.sql"
    else:
        filename = f"SOP DataFlowParam_{TABLE_OPTIONS[selection]}_{safe_filename(feature['FiturName'])}_{tanggal}.sql"
    return output / filename


def confirm_generate():
    while True:
        answer = ask("\n  Lanjut buat file SQL? [YA/TIDAK]: ").lower()
        if answer in ("ya", "yes", "y"):
            return True
        if answer in ("tidak", "no", "n"):
            return False
        print("[ERROR] Masukkan YA atau TIDAK.")


def main():
    section("DATAFLOWPARAM | GENERATE SCRIPT DEPLOY SOP")
    print("  Sumber hanya dibaca (SELECT). SQL tidak dieksekusi otomatis.")
    config = choose_connection()
    while True:
        selection = choose_tables()
        print("\n  Membuka koneksi ke DataFlowParam (SELECT saja)...")
        with connect_sqlserver(config, DATABASE) as conn:
            cur = conn.cursor()
            feature_id = search_feature(cur)
            if feature_id is None:
                continue
            feature, sources, children = load_source_data(cur, feature_id, selection)
        break

    targets = {role: prompt_role(role, sources[role]) for role, _ in ROLES}
    path = build_output_path(selection, feature)
    section("PREVIEW KONFIGURASI DEPLOYMENT")
    print(f"  Server sumber          : {config.name}")
    print(f"  Database sumber        : {DATABASE}")
    print(f"  Pilihan tabel          : {TABLE_OPTIONS[selection]}")
    print(f"  IDFitur sumber         : {feature_id}")
    print(f"  FiturName              : {feature['FiturName']}")
    print(f"  DBSource               : {feature['DBSource']}")
    print(f"  DBDestination          : {feature['DBDestination']}")
    print(f"  Modul                  : {feature['LogActivityModul']}")
    print(f"  SubModul               : {feature['LogActivitySubModul']}")
    print(f"  Entity                 : {feature['LogActivityEntity']}")
    section("KONFIGURASI SERVER PRODUKSI")
    for role, _ in ROLES:
        print(f"  {role.upper()}")
        print(f"    IPServer target      : {targets[role]['IPServer']}")
        print(f"    DBUser target        : {targets[role]['DBUser']}")
        print()
    section("RINCIAN DATA YANG AKAN DI-GENERATE")
    print("  1. ParamServer")
    print("     Role                : Source, Destination, LogActivity")
    print("     Jumlah referensi    : 3 (dapat menunjuk server yang sama)")
    count = 3
    if selection in ("1", "3", "4"):
        print("  2. ParamFitur")
        print("     Jumlah data         : 1 baris")
        count += 1
    if selection in ("1", "4"):
        print("  3. ParamFiturCekLogActivity")
        print(f"     Jumlah data         : {len(children)} baris")
        count += len(children)
    print("  " + "-" * 54)
    print(f"  TOTAL REFERENSI/BARIS : {count}")
    section("INFORMASI FILE OUTPUT")
    print("  Nama file:")
    print(f"    {path.name}")
    print("\n  Folder penyimpanan:")
    print(f"    {path.parent}")
    print("\n  Keterangan:")
    print("    - Database sumber hanya SELECT.")
    print("    - File SQL tidak dijalankan otomatis.")
    print("    - PasswordSource, PasswordDestination, PasswordLogActivity")
    print("      diisi lewat SQLCMD saat deployment.")
    if path.exists():
        print("\n  [WARNING] File dengan nama yang sama sudah ada.")
    if not confirm_generate():
        print("\n  Dibatalkan. Tidak ada file yang ditulis.")
        return
    if path.exists():
        if not confirm_overwrite():
            print("  Dibatalkan agar file lama tidak tertimpa.")
            return
    sql = generate(feature_id, targets, selection, feature, children)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(sql, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    section("BERHASIL - FILE SQL DIBUAT")
    print(f"  Nama file   : {path.name}")
    print(f"  Lokasi      : {path.parent}")
    print("  Status      : SQL belum dieksekusi; review sebelum produksi.")


def confirm_overwrite():
    while True:
        answer = ask("  Timpa file lama? [YA/TIDAK]: ").lower()
        if answer in ("ya", "yes", "y"):
            return True
        if answer in ("tidak", "no", "n"):
            return False
        print("  [ERROR] Masukkan YA atau TIDAK.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nDibatalkan oleh pengguna.", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
