"""
OtomasiMCS - wizard INSERT/UPDATE untuk tiga tabel.

Jalankan dari root Synqra-1.0:
    ./.venv/bin/python activities/OtomasiMCS/python/OtomasiMCS.py

Koneksi dipilih operator: server 172.18.135.205 atau localhost.
Database OtomasiMCS harus tersedia pada server yang dipilih.
Setiap operasi memiliki transaksi sendiri:
preview -> konfirmasi -> COMMIT/ROLLBACK -> SQL deployment setelah COMMIT.
SQL deployment tidak pernah dieksekusi otomatis.
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from getpass import getpass

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db_config import SERVERS
from db_connection import connect_sqlserver

DATABASE = "OtomasiMCS"
TARGET_HOST = "172.18.135.205"
TABLES = (
    "ParamFitur",
    "ParamQryPembukuanRekonESB",
    "ParamFiturCekLogActivity",
)
OUTPUT = Path(__file__).resolve().parent / "output" / "OtomasiMCS"

REKON_COLUMNS = (
    ["IdTrans", "AppName", "TranCode", "BranchCode", "TellerId",
     "SupervisorId"]
    + [f"Bucket{i}" for i in range(1, 21)]
    + ["ThirdPartyName", "TellerRemark1", "TellerRemark2",
       "DefaultCurrency", "AlternateCurrency1", "AlternateCurrency2",
       "AlternateCurrency3", "Seq", "DateTrans"]
)
LOG_COLUMNS = [
    "LogActivityModul", "LogActivitySubModul", "LogActivityEntity",
    "LogActivityDateAdd", "IsActive",
]
IMMUTABLE = {"IDFitur"}
UNSUPPORTED_WHERE_TYPES = {"text", "ntext", "image", "xml", "geography", "geometry"}
NON_EDITABLE_TYPES = {"timestamp", "rowversion"}


def ident(value: str) -> str:
    """Quote SQL Server identifier."""
    return "[" + str(value).replace("]", "]]") + "]"


def literal(value) -> str:
    """Serialize a Python value into a SQL literal for reviewed deployment SQL."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, (float, Decimal)):
        return str(value)
    if isinstance(value, (datetime, date)):
        return "CONVERT(datetime2, N'" + value.isoformat().replace("'", "''") + "', 126)"
    if isinstance(value, bytes):
        return "0x" + value.hex()
    return "N'" + str(value).replace("'", "''") + "'"


def section(title: str, step: int | None = None, total: int | None = None):
    print("\n" + "=" * 72)
    if step is not None and total is not None:
        print(f"[TAHAP {step}/{total}] {title.upper()}")
    else:
        print(title.upper())
    print("=" * 72)


def status(message: str, level: str = "INFO"):
    print(f"[{level}] {message}")


def ask(label: str, default=None, required: bool = False) -> str:
    while True:
        suffix = f" [{default}]" if default is not None else ""
        value = input(f"{label}{suffix}: ").strip()
        if not value and default is not None:
            return str(default)
        if value or not required:
            return value
        status("Input wajib diisi.", "PERINGATAN")


def confirm(action: str, keyword: str) -> bool:
    print(f"\nTindakan: {action}")
    return input(
        f"Ketik {keyword} untuk melanjutkan; selain itu batal: "
    ).strip() == keyword


def choose_server():
    """Tampilkan hanya server utama dan localhost dari konfigurasi terpusat."""
    configured = list(SERVERS.values())
    wanted = []
    for host, label in (
        ("172.18.135.205", "Server 172.18.135.205 (172.18.135.205:1433)"),
        ("localhost", "Server Lokal (localhost:1433)"),
    ):
        cfg = next((item for item in configured if str(getattr(item, "host", "")).lower() == host.lower()), None)
        if cfg is not None:
            wanted.append((cfg, label))

    if not wanted:
        raise RuntimeError(
            "Konfigurasi server 172.18.135.205 dan localhost tidak ditemukan "
            "di db_config.SERVERS."
        )

    section("PILIH KONEKSI DATABASE", 1, 6)
    print(f"Database target: {DATABASE}")
    for i, (_, label) in enumerate(wanted, 1):
        print(f"  {i}. {label}")
    print("  0. BATAL")
    while True:
        answer = input("Pilih koneksi: ").strip()
        if answer == "0":
            raise RuntimeError("Pemilihan koneksi dibatalkan operator.")
        if answer.isdigit() and 1 <= int(answer) <= len(wanted):
            cfg, label = wanted[int(answer) - 1]
            if str(getattr(cfg, "host", "")).lower() == "localhost":
                status(
                    "Server lokal dipilih. Pastikan database OtomasiMCS memang tersedia di localhost.",
                    "PERINGATAN",
                )
            return cfg, label
        status("Pilihan tidak valid. Pilih nomor yang tersedia.", "PERINGATAN")


def metadata(cur, table: str) -> dict:
    cur.execute(
        """
        SELECT c.name, t.name, c.is_nullable, c.is_identity, c.is_computed,
               c.max_length, c.precision, c.scale, dc.definition
        FROM sys.columns c
        JOIN sys.types t ON t.user_type_id = c.user_type_id
        LEFT JOIN sys.default_constraints dc
          ON dc.object_id = c.default_object_id
        WHERE c.object_id = OBJECT_ID(?)
        ORDER BY c.column_id
        """,
        f"dbo.{table}",
    )
    rows = cur.fetchall()
    if not rows:
        raise ValueError(
            f"Tabel dbo.{table} tidak ditemukan pada database {DATABASE} "
            f"di server {TARGET_HOST}."
        )
    return {
        r[0]: {
            "type": str(r[1]).lower(),
            "nullable": bool(r[2]),
            "identity": bool(r[3]),
            "computed": bool(r[4]),
            "max_length": r[5],
            "precision": r[6],
            "scale": r[7],
            "default": r[8],
        }
        for r in rows
    }


def convert(raw: str, meta: dict):
    if raw.upper() == "NULL":
        if not meta["nullable"]:
            raise ValueError("Kolom ini tidak boleh NULL.")
        return None

    kind = meta["type"]
    if kind in ("int", "smallint", "tinyint", "bigint", "bit"):
        result = int(raw)
        if kind == "bit" and result not in (0, 1):
            raise ValueError("Kolom BIT hanya menerima 0 atau 1.")
        bounds = {
            "tinyint": (0, 255),
            "smallint": (-32768, 32767),
            "int": (-2147483648, 2147483647),
            "bigint": (-9223372036854775808, 9223372036854775807),
        }
        if kind in bounds and not bounds[kind][0] <= result <= bounds[kind][1]:
            raise ValueError(f"Nilai di luar rentang {kind}.")
        return result
    if kind in ("decimal", "numeric", "money", "smallmoney", "float", "real"):
        try:
            return Decimal(raw)
        except InvalidOperation as exc:
            raise ValueError("Format angka tidak valid.") from exc
    if kind in ("date", "datetime", "datetime2", "smalldatetime", "datetimeoffset", "time"):
        # Keep typed temporal values as strings; SQL Server performs type conversion
        # through the parameterized statement.
        return raw
    return raw


def records(cur, table: str, where: str = "", params=()):
    sql = f"SELECT * FROM dbo.{ident(table)}"
    if where:
        sql += f" WHERE {where}"
    cur.execute(sql, *params)
    names = [col[0] for col in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def display(rows, max_rows: int = 30):
    print(f"\nJumlah record: {len(rows)}")
    for idx, row in enumerate(rows[:max_rows], 1):
        print(f"\n--- Record {idx} ---")
        for key, value in row.items():
            if any(token in key.lower() for token in ("pass", "secret", "token")):
                value = "[TERSEMBUNYI]"
            print(f"  {key}: {value!r}")
    if len(rows) > max_rows:
        print(f"... {len(rows) - max_rows} record lain tidak ditampilkan.")


def input_fields(cols: dict, fields: list[str], existing=None) -> dict:
    """Enter skips optional columns on INSERT and leaves existing values unchanged on UPDATE."""
    values = {}
    for name in fields:
        if name not in cols or cols[name]["identity"] or cols[name]["computed"]:
            continue
        if name == "DBPass":
            continue  # handled by the dedicated encrypted-password path

        old = (existing or {}).get(name)
        if existing is not None:
            print(f"  {name} | nilai lama: {old!r}")
        elif not cols[name]["nullable"] and cols[name]["default"] is None:
            print(f"  {name} (WAJIB)")

        raw = input(f"    Nilai {name} (Enter=lewati, NULL=SQL NULL): ").strip()
        if not raw:
            if existing is None and not cols[name]["nullable"] and cols[name]["default"] is None:
                while not raw:
                    raw = input(f"    {name} wajib diisi: ").strip()
                values[name] = convert(raw, cols[name])
            continue
        values[name] = convert(raw, cols[name])
    return values


def choose_table() -> str:
    index = menu(
        "PILIH TABEL TARGET",
        [f"dbo.{table}" for table in TABLES] + ["BATAL / KEMBALI"],
    )
    if index == len(TABLES):
        return ""
    return TABLES[index]


def menu(title: str, options: list[str]) -> int:
    section(title)
    for i, item in enumerate(options, 1):
        print(f"  {i}. {item}")
    while True:
        answer = input("Pilih nomor: ").strip()
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            return int(answer) - 1
        status("Pilihan tidak valid. Pilih nomor yang tersedia.", "PERINGATAN")


def choose_feature_id(cur, cols: dict):
    """Search existing ParamFitur; a failed search can be repeated."""
    while True:
        keyword = ask("Cari DBName (Enter=tampilkan semua)")
        cur.execute(
            """
            SELECT DISTINCT DBName
            FROM dbo.ParamFitur
            WHERE DBName IS NOT NULL
              AND LTRIM(RTRIM(DBName)) <> ''
              AND (? = '' OR DBName LIKE ?)
            ORDER BY DBName
            """,
            keyword,
            f"%{keyword}%",
        )
        names = [r[0] for r in cur.fetchall()]
        if not names:
            status("DBName tidak ditemukan. Coba pencarian lain.", "PERINGATAN")
            if not confirm("Ulangi pencarian DBName", "ULANGI"):
                return None
            continue

        idx = menu("PILIH DBNAME", names + ["ULANGI PENCARIAN", "BATAL"])
        if idx == len(names):
            continue
        if idx == len(names) + 1:
            return None

        cur.execute(
            "SELECT * FROM dbo.ParamFitur WHERE DBName = ? ORDER BY IDFitur",
            names[idx],
        )
        field_names = [d[0] for d in cur.description]
        found = [dict(zip(field_names, row)) for row in cur.fetchall()]
        if not found:
            status("Record tidak ditemukan lagi. Ulangi pencarian.", "PERINGATAN")
            continue

        ix = menu(
            "PILIH IDFITUR",
            [
                f"IDFitur={r.get('IDFitur')} | IP={r.get('IPServer')} | "
                f"DB={r.get('DBName')}"
                for r in found
            ] + ["ULANGI PENCARIAN", "BATAL"],
        )
        if ix == len(found):
            continue
        if ix == len(found) + 1:
            return None
        display([found[ix]])
        return found[ix]


def choose_record(cur, table: str, cols: dict, initial_where="", initial_params=()):
    """Pilih kolom pencarian dahulu, input nilainya setelah itu, lalu cari record."""
    available = [
        name for name, meta in cols.items()
        if meta["type"] not in UNSUPPORTED_WHERE_TYPES
    ]

    while True:
        section(f"PILIH KOLOM UNTUK MENCARI RECORD - {table}")
        print("Pilih satu atau beberapa kolom yang akan dipakai untuk mencari record.")
        for i, name in enumerate(available, 1):
            print(f"  {i}. {name}")
        print(f"  {len(available) + 1}. ULANGI / BATAL")

        raw = ask("Nomor kolom pencarian (pisahkan dengan koma)", required=True)
        try:
            nums = [int(x.strip()) for x in raw.split(",") if x.strip()]
        except ValueError:
            status("Masukkan nomor kolom yang valid, contoh: 1,3,5.", "PERINGATAN")
            continue

        if nums == [len(available) + 1]:
            return None
        if not nums or any(n < 1 or n > len(available) for n in nums):
            status("Pilihan kolom tidak valid.", "PERINGATAN")
            continue

        selected_columns = list(dict.fromkeys(available[n - 1] for n in nums))
        filters = []
        params = []
        if initial_where:
            filters.append(initial_where)
            params.extend(initial_params)

        # Tahap kedua: baru input nilai untuk semua kolom yang dipilih.
        section("INPUT NILAI PENCARIAN")
        for name in selected_columns:
            raw_value = ask(f"Nilai kolom {name} (ketik NULL untuk mencari SQL NULL)", required=True)
            if raw_value.upper() == "NULL":
                filters.append(f"{ident(name)} IS NULL")
            else:
                filters.append(f"{ident(name)} = ?")
                params.append(convert(raw_value, cols[name]))

        where = " AND ".join(f"({part})" for part in filters)
        found = records(cur, table, where, tuple(params))
        section("HASIL PENCARIAN")
        display(found)

        if not found:
            status("Record tidak ditemukan dengan kombinasi kolom dan nilai tersebut.", "PERINGATAN")
            retry = menu("PENCARIAN TIDAK MENEMUKAN RECORD", ["ULANGI PILIH KOLOM DAN NILAI", "BATAL"])
            if retry == 0:
                continue
            return None

        index = menu(
            "PILIH RECORD TARGET UPDATE",
            [f"Record {i + 1}" for i in range(len(found))]
            + ["ULANGI PENCARIAN", "BATAL"],
        )
        if index == len(found):
            continue
        if index == len(found) + 1:
            return None

        selected = found[index]
        # Prefer primary key to guarantee a deterministic, unique UPDATE target.
        cur.execute(
            """
            SELECT c.name
            FROM sys.indexes i
            JOIN sys.index_columns ic
              ON ic.object_id = i.object_id AND ic.index_id = i.index_id
            JOIN sys.columns c
              ON c.object_id = ic.object_id AND c.column_id = ic.column_id
            WHERE i.object_id = OBJECT_ID(?) AND i.is_primary_key = 1
            ORDER BY ic.key_ordinal
            """,
            f"dbo.{table}",
        )
        pk_names = [r[0] for r in cur.fetchall()]
        if pk_names and all(name in selected for name in pk_names):
            exact_parts, exact_params = [], []
            for name in pk_names:
                value = selected[name]
                if value is None:
                    exact_parts.append(f"{ident(name)} IS NULL")
                else:
                    exact_parts.append(f"{ident(name)} = ?")
                    exact_params.append(value)
            exact_where = " AND ".join(exact_parts)
            cur.execute(
                f"SELECT COUNT(*) FROM dbo.{ident(table)} WHERE {exact_where}",
                *exact_params,
            )
            if cur.fetchone()[0] != 1:
                status("Primary key tidak mengidentifikasi tepat satu record.", "ERROR")
                continue
            deploy_where = " AND ".join(
                f"{ident(name)} = {literal(selected[name])}" for name in pk_names
            )
            return selected, exact_where, exact_params, deploy_where

        # Fallback only if the complete searchable row predicate is unique.
        exact_parts, exact_params, deploy_parts = [], [], []
        for name, value in selected.items():
            if name not in available or isinstance(value, bytes):
                continue
            if value is None:
                exact_parts.append(f"{ident(name)} IS NULL")
                deploy_parts.append(f"{ident(name)} IS NULL")
            else:
                exact_parts.append(f"{ident(name)} = ?")
                exact_params.append(value)
                deploy_parts.append(f"{ident(name)} = {literal(value)}")
        if not exact_parts:
            status("Tidak dapat membentuk predicate UPDATE yang aman.", "ERROR")
            return None

        exact_where = " AND ".join(exact_parts)
        cur.execute(
            f"SELECT COUNT(*) FROM dbo.{ident(table)} WHERE {exact_where}",
            *exact_params,
        )
        if cur.fetchone()[0] != 1:
            status(
                "Target tidak unik. Pilih record dengan primary key atau kolom pencarian yang lebih spesifik.",
                "PERINGATAN",
            )
            continue
        return selected, exact_where, exact_params, " AND ".join(deploy_parts)


def apply_insert(cur, table: str, values: dict):
    if not values:
        raise ValueError("Tidak ada kolom untuk INSERT.")
    columns = list(values)
    sql = (
        f"INSERT INTO dbo.{ident(table)} ("
        + ", ".join(ident(c) for c in columns)
        + ") VALUES ("
        + ", ".join("?" for _ in columns)
        + ")"
    )
    cur.execute(sql, *[values[c] for c in columns])
    status(f"INSERT dbo.{table} berhasil dijalankan; rowcount={cur.rowcount}.")


def apply_update(cur, table: str, where: str, params: list, changes: dict):
    if not changes:
        raise ValueError("Tidak ada kolom perubahan untuk UPDATE.")
    if not where or not where.strip():
        raise ValueError("UPDATE dibatalkan karena WHERE kosong.")

    set_sql = ", ".join(f"{ident(c)} = ?" for c in changes)
    sql = (
        f";WITH TargetUpdate AS "
        f"(SELECT * FROM dbo.{ident(table)} WHERE {where}) "
        f"UPDATE TargetUpdate SET {set_sql}; "
        f"SELECT @@ROWCOUNT AS AffectedRows;"
    )
    cur.execute(sql, *list(params), *list(changes.values()))
    result = cur.fetchone()
    affected = int(result[0]) if result and result[0] is not None else -1
    if affected != 1:
        raise ValueError(
            f"UPDATE dbo.{table} harus mengenai tepat 1 record, tetapi hasilnya {affected}. "
            "Transaksi akan di-ROLLBACK."
        )
    status(f"UPDATE CTE dbo.{table} berhasil; record berubah: {affected}.")


def deployment_step(table: str, operation: str, values: dict, where_sql=None) -> str:
    if operation == "INSERT":
        if not values:
            raise ValueError("Deployment INSERT tidak memiliki kolom.")
        cols = ", ".join(ident(c) for c in values)
        vals = ", ".join(literal(v) for v in values.values())
        return f"INSERT INTO dbo.{ident(table)} ({cols}) VALUES ({vals});"

    if not where_sql or not where_sql.strip():
        raise ValueError(f"Deployment UPDATE dbo.{table} dibatalkan: WHERE kosong.")
    if not values:
        raise ValueError("Deployment UPDATE tidak memiliki perubahan.")
    changes = ", ".join(f"{ident(c)} = {literal(v)}" for c, v in values.items())
    return (
        f"DECLARE @Rows_{table} int;\n"
        f";WITH TargetUpdate AS (\n"
        f"    SELECT * FROM dbo.{ident(table)} WHERE {where_sql}\n"
        f")\n"
        f"UPDATE TargetUpdate SET {changes};\n"
        f"SET @Rows_{table} = @@ROWCOUNT;\n"
        f"IF @Rows_{table} <> 1 "
        f"THROW 51001, 'UPDATE harus tepat satu record.', 1;"
    )


def insert_feature(cur, cols: dict):
    fields = [
        c for c in cols
        if c != "DBPass" and not cols[c]["identity"] and not cols[c]["computed"]
    ]
    values = input_fields(cols, fields)

    password = None
    if "DBPass" in cols:
        password = getpass(
            "DBPass (Enter=lewati; input tidak ditampilkan): "
        )
        if not password and not cols["DBPass"]["nullable"] and cols["DBPass"]["default"] is None:
            raise ValueError(
                "DBPass wajib diisi pada skema ini. INSERT dibatalkan tanpa menyimpan password."
            )
        if password:
            ip = values.get("IPServer")
            if not ip:
                raise ValueError("IPServer wajib diisi untuk dbo.fnEncrypt.")
            # Keep password out of preview and generated SQL. It is only passed
            # as a parameter to SQL Server for the live transaction.
            values["DBPass"] = None

    preview = {k: ("[TERSEMBUNYI]" if "pass" in k.lower() else v)
               for k, v in values.items()}
    section("PREVIEW INSERT ParamFitur")
    display([preview])
    if not confirm("INSERT ParamFitur", "INSERT"):
        status("INSERT dibatalkan.", "BATAL")
        return None, None

    if password:
        safe = {k: v for k, v in values.items() if k != "DBPass"}
        columns = list(safe) + ["DBPass"]
        placeholders = ["?" for _ in safe] + ["dbo.fnEncrypt(?, ? + 'BR!')"]
        output_clause = " OUTPUT INSERTED.IDFitur" if cols.get("IDFitur", {}).get("identity") else ""
        cur.execute(
            f"INSERT INTO dbo.ParamFitur ({', '.join(ident(c) for c in columns)})"
            f"{output_clause} VALUES ({', '.join(placeholders)})",
            *list(safe.values()), password, values["IPServer"],
        )
        if output_clause:
            inserted_id = cur.fetchone()[0]
        # Deployment uses SQLCMD variable; never serialize the secret.
        deploy_values = dict(safe)
        deploy_values["DBPass"] = "__SQLCMD_SECRET__"
        cols_sql = ", ".join(ident(c) for c in deploy_values)
        vals_sql = ", ".join(
            "dbo.fnEncrypt(N'$(MCS_DBPASS)', "
            + literal(values["IPServer"]) + " + 'BR!')"
            if c == "DBPass" else literal(v)
            for c, v in deploy_values.items()
        )
        deploy_sql = (
            f"INSERT INTO dbo.ParamFitur ({cols_sql}) VALUES ({vals_sql});"
        )
    else:
        if "IDFitur" in cols and cols["IDFitur"]["identity"]:
            columns = list(values)
            sql = (
                f"INSERT INTO dbo.ParamFitur ("
                + ", ".join(ident(c) for c in columns)
                + ") OUTPUT INSERTED.IDFitur VALUES ("
                + ", ".join("?" for _ in columns) + ")"
            )
            cur.execute(sql, *[values[c] for c in columns])
            inserted_id = cur.fetchone()[0]
        else:
            apply_insert(cur, "ParamFitur", values)
            inserted_id = values.get("IDFitur")
        deploy_sql = deployment_step("ParamFitur", "INSERT", values)

    # Re-read the inserted feature using the returned identity where available.
    if "IDFitur" in cols and cols["IDFitur"]["identity"]:
        new_id = inserted_id
        cur.execute("SELECT * FROM dbo.ParamFitur WHERE IDFitur = ?", new_id)
    elif values.get("IDFitur") is not None:
        cur.execute("SELECT * FROM dbo.ParamFitur WHERE IDFitur = ?", values["IDFitur"])
    else:
        natural = ("Modul", "Name", "FiturID")
        if not all(values.get(k) is not None for k in natural):
            raise ValueError(
                "Fitur berhasil di-INSERT, tetapi tidak bisa dipastikan kembali. "
                "Pastikan IDFitur identity atau kolom Modul, Name, FiturID diisi."
            )
        cur.execute(
            "SELECT TOP (2) * FROM dbo.ParamFitur "
            "WHERE Modul = ? AND Name = ? AND FiturID = ? ORDER BY IDFitur DESC",
            *(values[k] for k in natural),
        )
    row = cur.fetchone()
    if not row:
        raise ValueError("Tidak dapat menemukan ParamFitur yang baru di-INSERT.")
    result = dict(zip([d[0] for d in cur.description], row))
    return result, ("ParamFitur", deploy_sql)


def update_record(cur, table: str, cols: dict, old: dict,
                  where: str, params: list, deploy_where: str, feature=False):
    editable = [
        c for c in cols
        if c not in IMMUTABLE
        and not cols[c]["identity"]
        and not cols[c]["computed"]
        and cols[c]["type"] not in NON_EDITABLE_TYPES
    ]
    if "DBPass" in editable:
        editable.remove("DBPass")

    while True:
        section(f"PILIH KOLOM UPDATE - {table}")
        for i, name in enumerate(editable, 1):
            value = "[TERSEMBUNYI]" if any(
                token in name.lower() for token in ("pass", "secret", "token")
            ) else repr(old.get(name))
            print(f"  {i}. {name} = {value}")
        print(f"  {len(editable) + 1}. BATAL")
        raw = ask("Nomor kolom (pisahkan dengan koma)", required=True)
        try:
            nums = [int(x.strip()) for x in raw.split(",")]
        except ValueError:
            status("Masukkan nomor kolom yang valid.", "PERINGATAN")
            continue
        if nums == [len(editable) + 1]:
            return old if feature else None, None
        if not nums or any(n < 1 or n > len(editable) for n in nums):
            status("Pilihan kolom tidak valid.", "PERINGATAN")
            continue
        chosen = list(dict.fromkeys(editable[n - 1] for n in nums))
        break

    changes = input_fields(cols, chosen, existing=old)
    if not changes:
        status("Tidak ada kolom diubah; UPDATE dilewati.")
        return old if feature else None, None

    section("PREVIEW UPDATE")
    for col, new in changes.items():
        old_value = "[TERSEMBUNYI]" if "pass" in col.lower() else repr(old.get(col))
        new_value = "[TERSEMBUNYI]" if "pass" in col.lower() else repr(new)
        print(f"  {col}: {old_value} -> {new_value}")

    if not confirm(f"UPDATE CTE dbo.{table}", "UPDATE"):
        status("UPDATE dibatalkan.", "BATAL")
        return old if feature else None, None

    apply_update(cur, table, where, params, changes)
    deploy_sql = deployment_step(table, "UPDATE", changes, deploy_where)

    if feature:
        cur.execute("SELECT * FROM dbo.ParamFitur WHERE IDFitur = ?", old["IDFitur"])
        row = cur.fetchone()
        if not row:
            raise ValueError("ParamFitur tidak ditemukan setelah UPDATE.")
        return dict(zip([d[0] for d in cur.description], row)), (table, deploy_sql)
    return None, (table, deploy_sql)


def process_operation(cur, schemas: dict):
    table = choose_table()
    if not table:
        return "BACK", None

    action = menu(
        f"OPERASI dbo.{table}",
        ["INSERT", "UPDATE (CTE)", "KEMBALI PILIH TABEL"],
    )
    if action == 2:
        return "BACK", None

    if action == 0:
        cols = schemas[table]
        if table == "ParamFitur":
            selected, op = insert_feature(cur, cols)
            if selected is None:
                return "CANCELLED", None
            return "DONE", op

        values = {}
        # IDFitur is entered explicitly for child tables so the operator can
        # attach the record to the intended feature.
        if "IDFitur" in cols and not cols["IDFitur"]["identity"]:
            raw_id = ask("IDFitur referensi ParamFitur", required=True)
            values["IDFitur"] = convert(raw_id, cols["IDFitur"])
            cur.execute(
                "SELECT COUNT(*) FROM dbo.ParamFitur WHERE IDFitur = ?",
                values["IDFitur"],
            )
            if cur.fetchone()[0] != 1:
                raise ValueError(
                    f"IDFitur {values['IDFitur']} tidak ditemukan di ParamFitur. "
                    "Ulangi operasi dan masukkan IDFitur yang valid."
                )

        if table == "ParamQryPembukuanRekonESB":
            preferred = [c for c in REKON_COLUMNS if c in cols and c != "IDFitur"]
        else:
            preferred = [c for c in LOG_COLUMNS if c in cols and c != "IDFitur"]
        values.update(input_fields(cols, preferred))

        remaining = [
            c for c in cols
            if c not in values and c not in preferred
            and not cols[c]["identity"] and not cols[c]["computed"]
            and not cols[c]["nullable"] and cols[c]["default"] is None
            and c != "DBPass"
        ]
        values.update(input_fields(cols, remaining))

        # Required-column guard before attempting INSERT.
        missing = [
            c for c, meta in cols.items()
            if not meta["identity"] and not meta["computed"]
            and not meta["nullable"] and meta["default"] is None
            and c not in values and c != "DBPass"
        ]
        if missing:
            raise ValueError(
                "Kolom wajib belum diisi: " + ", ".join(missing)
            )

        section(f"PREVIEW INSERT dbo.{table}")
        display([{
            k: ("[TERSEMBUNYI]" if "pass" in k.lower() else v)
            for k, v in values.items()
        }])
        if not confirm(f"INSERT dbo.{table}", "INSERT"):
            status("INSERT dibatalkan.", "BATAL")
            return "CANCELLED", None

        apply_insert(cur, table, values)
        return "DONE", (table, deployment_step(table, "INSERT", values))

    # UPDATE: semua tabel memakai alur pilih kolom -> input nilai -> cari record.
    # Tidak ada pemilihan DBName atau filter IDFitur khusus sebelum pencarian.
    selected_result = choose_record(cur, table, schemas[table])
    if selected_result is None:
        return "CANCELLED", None
    old, where, params, deploy_where = selected_result

    _, op = update_record(
        cur, table, schemas[table], old,
        where, params, deploy_where,
        feature=(table == "ParamFitur"),
    )
    if op is None:
        return "CANCELLED", None
    return "DONE", op


def build_deployment(operation: tuple[str, str]) -> str:
    table, statement = operation
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_name = f"{table}_BKP_{stamp}"
    secret_header = (
        "-- Jalankan dalam SQLCMD Mode. Isi MCS_DBPASS secara aman; jangan commit password.\n"
        ":setvar MCS_DBPASS <ISI_SECARA_AMAN>\n\n"
        if "$(MCS_DBPASS)" in statement else ""
    )
    return f"""{secret_header}USE [{DATABASE}];
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;
GO

/* ================================================================
   OTOMASIMCS - CONFIGURATION DEPLOYMENT
   Target server : {TARGET_HOST}
   Target table  : dbo.{table}
   Generated     : {datetime.now().isoformat(timespec='seconds')}

   REVIEW WAJIB sebelum dijalankan.
   Backup SELECT INTO tidak menyalin indeks, constraint, atau trigger.
   Script ini tidak dijalankan otomatis oleh wizard.
   ================================================================ */

IF OBJECT_ID(N'dbo.{table}', 'U') IS NULL
    THROW 51011, 'Tabel dbo.{table} tidak ditemukan.', 1;

BEGIN TRY
    BEGIN TRANSACTION;

    IF OBJECT_ID(N'dbo.{backup_name}', 'U') IS NOT NULL
        THROW 51010, 'Nama backup sudah ada.', 1;

    SELECT * INTO dbo.{ident(backup_name)} FROM dbo.{ident(table)};

    /* Operasi hasil preview Python; verifikasi target sebelum eksekusi. */
    {statement}

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

SELECT COUNT(*) AS Total_{table} FROM dbo.{ident(table)};
GO
"""


def save_deployment(operation: tuple[str, str]):
    sql = build_deployment(operation)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    destination = OUTPUT / (
        f"OtomasiMCS_{datetime.now():%Y-%m-%d_%H%M%S_%f}.sql"
    )
    destination.write_text(sql, encoding="utf-8")
    print(f"File SQL deployment: {destination.resolve()}")
    status("SQL deployment dibuat setelah COMMIT.")
    status("SQL tidak dieksekusi otomatis; review sebelum deployment.")


def run():
    global TARGET_HOST
    section("OTOMASIMCS - WIZARD INSERT / UPDATE")
    connection = None

    try:
        cfg, server_label = choose_server()
        TARGET_HOST = str(cfg.host)
        status(f"Koneksi dipilih: {server_label}")
        status(f"Target host: {cfg.host}:{cfg.port}")
        status(f"Database: {DATABASE}")
        status("Menghubungkan ke SQL Server...")

        connection = connect_sqlserver(cfg, DATABASE)
        connection.autocommit = False
        cur = connection.cursor()

        cur.execute(
            "SELECT CAST(SERVERPROPERTY('ServerName') AS nvarchar(256)), DB_NAME(), SUSER_SNAME()"
        )
        actual_server, actual_database, actual_login = cur.fetchone()
        print(f"SQL Server aktual : {actual_server}")
        print(f"Database aktual   : {actual_database}")
        print(f"Login SQL         : {actual_login}")
        if not actual_database or actual_database.lower() != DATABASE.lower():
            raise RuntimeError(
                f"Database aktual {actual_database!r}, seharusnya {DATABASE!r}."
            )

        schemas = {table: metadata(cur, table) for table in TABLES}
        status("Koneksi, database, dan metadata ketiga tabel berhasil diverifikasi.")

        while True:
            section("OPERASI BARU")
            print("Pilih tabel dan INSERT/UPDATE yang ingin dilakukan.")
            print("Setiap operasi memakai transaksi terpisah.")

            try:
                outcome, operation = process_operation(cur, schemas)

                if outcome == "BACK":
                    if confirm("Kembali ke pemilihan tabel", "KEMBALI"):
                        continue
                    break

                if outcome != "DONE" or operation is None:
                    connection.rollback()
                    status("Operasi dibatalkan; tidak ada perubahan yang di-commit.", "BATAL")
                    if confirm("Ulangi atau mulai operasi lain", "YA"):
                        continue
                    break

                section("KONFIRMASI COMMIT")
                print(f"Server target : {TARGET_HOST}:{cfg.port}")
                print(f"Database      : {DATABASE}")
                print(f"Tabel target  : dbo.{operation[0]}")
                print("Perubahan akan disimpan permanen jika COMMIT dikonfirmasi.")
                if not confirm("Simpan perubahan ke database", "COMMIT"):
                    connection.rollback()
                    status("ROLLBACK berhasil; perubahan tidak disimpan.", "BATAL")
                    if confirm("Ulangi atau mulai operasi lain", "YA"):
                        continue
                    break

                try:
                    connection.commit()
                except Exception:
                    try:
                        connection.rollback()
                    except Exception:
                        pass
                    raise
                status("COMMIT berhasil. Perubahan tersimpan di database.", "SUKSES")

                try:
                    save_deployment(operation)
                except Exception as file_exc:
                    status(
                        f"COMMIT berhasil, tetapi file deployment gagal dibuat: {file_exc}",
                        "PERINGATAN",
                    )
                    status(
                        "Database sudah berubah. Jangan mengulang INSERT hanya karena file SQL gagal dibuat.",
                        "PERINGATAN",
                    )

                if not confirm("Lanjut ke operasi INSERT/UPDATE berikutnya", "YA"):
                    break

            except KeyboardInterrupt:
                try:
                    connection.rollback()
                except Exception:
                    pass
                status("Input dibatalkan. Transaksi aktif di-ROLLBACK.", "PERINGATAN")
                if confirm("Kembali ke menu operasi", "YA"):
                    continue
                break
            except Exception as op_exc:
                try:
                    connection.rollback()
                    status("Operasi saat ini di-ROLLBACK; perubahan belum di-commit dibatalkan.", "PERINGATAN")
                except Exception as rollback_exc:
                    status(f"ROLLBACK gagal: {rollback_exc}", "ERROR")
                status(f"Operasi gagal: {op_exc}", "ERROR")
                if confirm("Ulangi operasi atau pilih tabel lain", "ULANGI"):
                    continue
                break

        section("PROSES SELESAI")
        status("Wizard selesai.")

    except KeyboardInterrupt:
        status("Program dihentikan oleh operator.", "PERINGATAN")
        if connection is not None:
            try:
                connection.rollback()
                status("Transaksi yang belum di-commit di-ROLLBACK.")
            except Exception:
                pass
    except Exception as exc:
        status(f"ERROR KONEKSI / INISIALISASI: {exc}", "ERROR")
        status(
            "Pastikan server dapat dijangkau, kredensial benar, database OtomasiMCS tersedia, "
            "dan ketiga tabel berada di schema dbo.",
            "INFO",
        )
    finally:
        if connection is not None:
            try:
                connection.close()
            finally:
                status("Koneksi SQL Server ditutup.")


if __name__ == "__main__":
    run()
