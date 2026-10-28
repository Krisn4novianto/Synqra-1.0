"""Koneksi dan operasi SQL Server untuk Enterprise-4."""
import re
from db_config import PREFERRED_DRIVERS


def _pyodbc():
    try:
        import pyodbc
        return pyodbc
    except ImportError as exc:
        raise RuntimeError(
            "Library pyodbc belum terpasang. Jalankan: python3 -m pip install pyodbc"
        ) from exc


def connect_sqlserver(config, database=None):
    pyodbc = _pyodbc()
    installed = set(pyodbc.drivers())
    driver = next((item for item in PREFERRED_DRIVERS if item in installed), None)
    if not driver:
        raise RuntimeError(
            "Microsoft ODBC Driver tidak ditemukan. Instal ODBC Driver 18 atau 17 for SQL Server."
        )
    db = database or config.database
    conn_str = (
        f"DRIVER={{{driver}}};SERVER={config.host},{config.port};"
        f"DATABASE={db};UID={config.username};PWD={{{config.password}}};"
        f"Encrypt={config.encrypt};TrustServerCertificate={config.trust_server_certificate};"
        f"Connection Timeout={config.timeout};"
    )
    return pyodbc.connect(conn_str, timeout=config.timeout)


def _remove_go_batch_separators(sql):
    """pyodbc tidak mengenal GO; GO adalah command milik SSMS/sqlcmd."""
    return re.sub(r"(?im)^\s*GO\s*;?\s*$", "", sql)


def execute_sql(config, database, sql):
    """Eksekusi SQL hasil generator ke database target.

    File generator boleh memakai GO agar tetap nyaman dibuka di SSMS.
    Sebelum dikirim melalui pyodbc, baris GO dihapus karena bukan T-SQL.
    """
    cleaned = _remove_go_batch_separators(sql)
    with connect_sqlserver(config, database) as conn:
        cursor = conn.cursor()
        cursor.execute(cleaned)
        conn.commit()


def fetch_activity_log(
    config,
    database,
    *,
    log_table,
    log_modul,
    log_entity=None,
    log_submodul=None,
    log_entities=None,
):
    """Ambil konfigurasi activity untuk verifikasi setelah submit."""
    from activities.common import sql_identifier

    conditions = ["LogActivityModul = ?"]
    params = [log_modul]
    entities = list(log_entities or [])
    if entities:
        placeholders = ", ".join("?" for _ in entities)
        conditions.append(f"LogActivityEntity IN ({placeholders})")
        params.extend(entities)
    elif log_entity:
        conditions.append("LogActivityEntity = ?")
        params.append(log_entity)
    else:
        raise ValueError("LogActivityEntity atau log_entities wajib diisi.")

    if log_submodul:
        conditions.append("LogActivitySubModul = ?")
        params.append(log_submodul)

    query = (
        f"SELECT TOP (50) * "
        f"FROM dbo.{sql_identifier(log_table)} WITH (NOLOCK) "
        f"WHERE {' AND '.join(conditions)} "
        f"ORDER BY 1 DESC"
    )

    with connect_sqlserver(config, database) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()
        return rows, columns


def test_connection(config):
    with connect_sqlserver(config) as conn:
        row = conn.cursor().execute(
            "SELECT @@SERVERNAME, DB_NAME(), SUSER_SNAME()"
        ).fetchone()
        return {"server_name": row[0], "database": row[1], "login": row[2]}


def list_databases(config):
    with connect_sqlserver(config, "master") as conn:
        rows = conn.cursor().execute(
            "SELECT name FROM sys.databases WHERE state_desc = 'ONLINE' ORDER BY name"
        ).fetchall()
        return [row[0] for row in rows]


def database_exists(config, database_name):
    with connect_sqlserver(config, "master") as conn:
        row = conn.cursor().execute("SELECT DB_ID(?)", database_name).fetchone()
        return bool(row and row[0] is not None)


def paramserver_exists(config, ip_server):
    with connect_sqlserver(config, "DataFlowParam") as conn:
        row = conn.cursor().execute(
            "SELECT CASE WHEN EXISTS (SELECT 1 FROM dbo.ParamServer WHERE IPServer = ?) THEN 1 ELSE 0 END",
            ip_server,
        ).fetchone()
        return bool(row[0])


def esbrevamp_exists(config, modul, submodul):
    with connect_sqlserver(config, "DataSourceDistributor") as conn:
        row = conn.cursor().execute(
            "SELECT CASE WHEN EXISTS (SELECT 1 FROM dbo.ParamESBRevamp WHERE LogActivityModul = ? AND LogActivitySubModul = ?) THEN 1 ELSE 0 END",
            modul, submodul,
        ).fetchone()
        return bool(row[0])


def paramfitur_exists(config, dbname):
    with connect_sqlserver(config, "DataSourceDistributor") as conn:
        row = conn.cursor().execute(
            "SELECT CASE WHEN EXISTS (SELECT 1 FROM dbo.ParamFitur WHERE DBName = ?) THEN 1 ELSE 0 END",
            dbname,
        ).fetchone()
        return bool(row[0])
