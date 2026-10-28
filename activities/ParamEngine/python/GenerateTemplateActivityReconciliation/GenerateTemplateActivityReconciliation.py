#!/usr/bin/env python3
"""
Synqra - Generate Template Activity Reconciliation
Menjalankan LogActivity.dbo.sp_GenerateTemplateActivityReconciliation
dengan preview hasil sebelum COMMIT/ROLLBACK.
"""
from pathlib import Path
from datetime import datetime
import sys

def find_project_root(start: Path) -> Path:
    for parent in [start.resolve().parent, *start.resolve().parents]:
        if (parent / "db_config.py").is_file() and (parent / "db_connection.py").is_file():
            return parent
    raise ModuleNotFoundError(
        "Tidak menemukan db_config.py dan db_connection.py di root project Synqra-1.0."
    )

ROOT = find_project_root(Path(__file__))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db_config import SERVERS
from db_connection import connect_sqlserver

DATABASE = "LogActivity"
PROCEDURE = "dbo.sp_GenerateTemplateActivityReconciliation"
TABLE = "dbo.TemplateActivityReconciliation"
KEY_COLUMNS = ["ProductId", "Task", "Activity", "SchEngine", "ReconH0Batch", "ReconWindow"]

def cfg_value(cfg, *names, default=""):
    if isinstance(cfg, dict):
        for name in names:
            if cfg.get(name) not in (None, ""):
                return cfg[name]
    else:
        for name in names:
            value = getattr(cfg, name, None)
            if value not in (None, ""):
                return value
    return default

def server_menu():
    print("\n" + "=" * 76)
    print("  SYNQRA | PARAMENGINE | GENERATE TEMPLATE ACTIVITY RECONCILIATION")
    print("=" * 76)
    print("  Pilih koneksi SQL Server dari db_config.py")
    items = list(SERVERS.items())
    for i, (key, cfg) in enumerate(items, 1):
        label = cfg_value(cfg, "name", "label", "description", default=f"Server {key}")
        host = cfg_value(cfg, "host", "server", "hostname", default="?")
        print(f"  [{i}] {label} | {host}")
    while True:
        choice = input(f"\nPilih server [1-{len(items)}] (0 untuk keluar): ").strip()
        if choice == "0":
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(items):
            key, cfg = items[int(choice)-1]
            print(f"\n  Server dipilih: {cfg_value(cfg, 'name', 'label', default=str(key))}"
                  f" | {cfg_value(cfg, 'host', 'server', 'hostname', default='?')}")
            return cfg
        print("  [!] Pilihan tidak valid. Coba lagi.")

def required_input(label, max_len, default=None):
    while True:
        suffix = f" [{default}]" if default else ""
        value = input(f"  {label}{suffix}: ").strip()
        if not value and default:
            value = default
        if not value:
            print(f"  [!] {label} wajib diisi.")
            continue
        if len(value) > max_len:
            print(f"  [!] Maksimal {max_len} karakter.")
            continue
        return value

def show_rows(rows, title):
    print("\n" + "-" * 76)
    print(f"  {title}")
    print("-" * 76)
    if not rows:
        print("  Tidak ada record yang ditemukan.")
        return
    for idx, row in enumerate(rows, 1):
        print(f"\n  Record #{idx}")
        for col, val in row.items():
            val = "NULL" if val is None else str(val)
            if len(val) > 180:
                val = val[:177] + "..."
            print(f"    {col:<22} : {val}")
    print(f"\n  Total record: {len(rows)}")

def main():
    cfg = server_menu()
    if cfg is None:
        print("\n  Dibatalkan.")
        return

    print("\n" + "=" * 76)
    print("  PARAMETER STORED PROCEDURE")
    print("-" * 76)
    product_id = required_input("@ProductId (varchar(9))", 9)
    activity_group = required_input("@ActivityGroup (varchar(255))", 255)

    print("\n" + "-" * 76)
    print("  RINGKASAN EKSEKUSI")
    print("-" * 76)
    print(f"  Database       : {DATABASE}")
    print(f"  Stored procedure: {PROCEDURE}")
    print(f"  @ProductId     : {product_id}")
    print(f"  @ActivityGroup : {activity_group}")
    print("\n  Prosedur akan dijalankan dalam transaksi yang belum di-COMMIT.")
    print("  Setelah itu hasil akan diperiksa dan ditampilkan untuk ditinjau.")

    confirm = input("\n  Ketik RUN untuk menjalankan stored procedure: ").strip()
    if confirm != "RUN":
        print("  Dibatalkan; tidak ada perubahan dilakukan.")
        return

    conn = None
    cur = None
    try:
        conn = connect_sqlserver(cfg, DATABASE)
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute("SET XACT_ABORT ON;")

        # Snapshot key sebelum prosedur agar dapat menampilkan record baru.
        cur.execute(f"""
            SELECT ProductId, Task, Activity, SchEngine, ReconH0Batch, ReconWindow
            INTO #BeforeTemplateActivity
            FROM {TABLE}
            WHERE ProductId = ? AND ActivityGroup = ?
        """, product_id, activity_group)

        cur.execute(f"EXEC {PROCEDURE} @ProductId = ?, @ActivityGroup = ?",
                    product_id, activity_group)

        # Hasil akhir untuk parameter yang dimasukkan, sekaligus record baru.
        cur.execute(f"""
            SELECT t.ProductId, t.Task, t.Activity, t.Description,
                   t.ActivityOrder, t.SchEngine, t.SchStart, t.IsActive,
                   t.LogActivityDataDateAdd, t.ReconH0Batch, t.ReconWindow,
                   t.ActivityGroup, t.InsertDate, t.LastModified,
                   CASE WHEN b.ProductId IS NULL THEN 'BARU DIBUAT'
                        ELSE 'SUDAH ADA SEBELUM EKSEKUSI' END AS StatusHasil
            FROM {TABLE} AS t
            LEFT JOIN #BeforeTemplateActivity AS b
              ON b.ProductId = t.ProductId
             AND b.Task = t.Task
             AND b.Activity = t.Activity
             AND b.SchEngine = t.SchEngine
             AND ISNULL(b.ReconH0Batch, '') = ISNULL(t.ReconH0Batch, '')
             AND b.ReconWindow = t.ReconWindow
            WHERE t.ProductId = ? AND t.ActivityGroup = ?
            ORDER BY t.ReconWindow, t.Task, t.Activity, t.SchEngine
        """, product_id, activity_group)
        columns = [d[0] for d in cur.description]
        rows = [dict(zip(columns, r)) for r in cur.fetchall()]

        new_rows = [r for r in rows if r["StatusHasil"] == "BARU DIBUAT"]
        show_rows(new_rows, "RECORD BARU DARI STORED PROCEDURE")
        show_rows([r for r in rows if r["StatusHasil"] != "BARU DIBUAT"],
                  "RECORD YANG SUDAH ADA")
        print("\n" + "=" * 76)
        print("  HASIL PEMERIKSAAN")
        print("=" * 76)
        print(f"  Record baru terdeteksi : {len(new_rows)}")
        print(f"  Record sudah ada       : {len(rows) - len(new_rows)}")
        print(f"  Total record hasil     : {len(rows)}")
        print("\n  Periksa hasil di atas sebelum menentukan transaksi.")

        if not rows:
            print("  [!] Tidak ditemukan hasil untuk parameter tersebut.")
            decision = input("  Ketik ROLLBACK untuk membatalkan transaksi: ").strip()
            conn.rollback()
            print("  Transaksi di-ROLLBACK. Tidak ada perubahan disimpan.")
            return

        decision = input("\n  Ketik COMMIT untuk menyimpan atau ROLLBACK untuk membatalkan: ").strip().upper()
        if decision == "COMMIT":
            conn.commit()
            print("\n  [OK] COMMIT berhasil. Perubahan sudah disimpan.")
        else:
            conn.rollback()
            print("\n  [OK] ROLLBACK berhasil. Perubahan dibatalkan.")
    except Exception as exc:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        print("\n" + "!" * 76)
        print("  EKSEKUSI GAGAL — TRANSAKSI DI-ROLLBACK")
        print("!" * 76)
        print(f"  Error: {exc}")
        print("\n  Periksa koneksi, keberadaan stored procedure, dan hak akses database.")
    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

if __name__ == "__main__":
    main()
