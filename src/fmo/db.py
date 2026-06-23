from pathlib import Path
from typing import Any, cast

import psycopg


class MigrationRunner:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def apply_schema(self, schema_path: Path) -> None:
        sql = schema_path.read_text(encoding="utf-8")
        with psycopg.connect(self.database_url, autocommit=True) as connection:
            connection.execute(cast(Any, sql))

    def table_names(self) -> set[str]:
        with psycopg.connect(self.database_url) as connection:
            rows = connection.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                """
            ).fetchall()
        return {row[0] for row in rows}
