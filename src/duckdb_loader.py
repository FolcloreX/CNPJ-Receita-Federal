import logging

import duckdb
from pathlib import Path

from .settings import settings

logger = logging.getLogger(__name__)


class DuckDBBackend:
    def __init__(self):
        self.conn = None

    def connect(self):
        self.conn = duckdb.connect(str(settings.duckdb_file))
        logger.info(f"Conectado ao DuckDB: {settings.duckdb_file}")

    def create_schema(self):
        self._execute_sql_file("schema_duckdb.sql")

    def load_chunk(self, df, table_name):
        """Carga via integração nativa DuckDB ↔ Pandas DataFrame."""
        columns = ", ".join(df.columns.tolist())
        try:
            self.conn.execute(
                f"INSERT INTO {table_name} ({columns}) SELECT {columns} FROM df"
            )
        except Exception as e:
            logger.error(f"Erro ao inserir dados na tabela {table_name}: {e}")
            raise

    def post_load(self):
        pass  # DuckDB não precisa de conversão UNLOGGED → LOGGED

    def apply_constraints(self):
        self._execute_sql_file("constraints_duckdb.sql")

    def close(self):
        if self.conn:
            self.conn.close()

    def _execute_sql_file(self, filename):
        base_path = Path(__file__).parent
        file_path = base_path / filename

        if not file_path.exists():
            logger.error(f"Arquivo SQL não encontrado: {file_path}")
            return

        logger.info(f"Executando SQL: {filename}")
        sql_content = file_path.read_text(encoding="utf-8")

        try:
            self.conn.execute(sql_content)
            logger.info(f"Sucesso ao executar {filename}")
        except Exception as e:
            logger.error(f"ERRO ao executar SQL de {filename}: {e}")
            raise
