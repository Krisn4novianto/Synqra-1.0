"""Konfigurasi terpusat koneksi SQL Server.

PERINGATAN: Password di file sumber berisiko bocor. Jangan commit file ini
ke Git jika berisi kredensial asli. Lebih aman gunakan .env atau secret manager.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SQLServerConfig:
    key: str
    name: str
    host: str
    port: int
    username: str
    password: str
    database: str = "master"
    encrypt: str = "no"
    trust_server_certificate: str = "yes"
    timeout: int = 10


SERVERS = {
    "1": SQLServerConfig(
        key="server_204",
        name="Server 172.18.135.204",
        host="172.18.135.204",
        port=1433,
        username="sa",
        password="P@ssw0rd123",
    ),
    "2": SQLServerConfig(
        key="server_205",
        name="Server 172.18.135.205",
        host="172.18.135.205",
        port=1433,
        username="sa",
        password="P@ssw0rd123",
    ),
    "3": SQLServerConfig(
        key="server_local",
        name="Localhost (Testing)",
        host="localhost",
        port=1433,
        username="sa",
        password="LocalDev@2026Sql!",
    ),
    "4": SQLServerConfig(
        key="server_102",
        name="ParamEngine 172.18.246.102",
        host="172.18.246.102",
        port=1433,
        username="sa",
        password="P@ssw0rd",
        database="ParamEngine",
    ),
}


PREFERRED_DRIVERS = (
    "ODBC Driver 18 for SQL Server",
    "ODBC Driver 17 for SQL Server",
    "SQL Server Native Client 11.0",
)


def choose_server(default=None):
    print("\nPilih koneksi SQL Server:")
    for key, cfg in SERVERS.items():
        marker = " (default)" if key == default else ""
        print(f"  {key}. {cfg.name}:{cfg.port}{marker}")
    while True:
        choice = input(
            f'Pilih server [{"/".join(SERVERS)}]'
            + (f" [{default}]" if default else "") + ": "
        ).strip()
        if not choice and default:
            choice = default
        if choice in SERVERS:
            return SERVERS[choice]
        print("Pilihan tidak valid.")
