import io
import logging

import psycopg2
from psycopg2 import sql
from pathlib import Path

from .settings import settings

logger = logging.getLogger(__name__)


class PostgresBackend:
    def __init__(self):
        self.conn = None

    def connect(self):
        self.conn = psycopg2.connect(settings.database_uri)
        logger.info("Conectado ao PostgreSQL.")

    def create_schema(self):
        self._execute_sql_file("schema.sql")

    def load_chunk(self, df, table_name):
        """Carga via PostgreSQL COPY FROM STDIN."""
        output = io.StringIO()

        df.to_csv(
            output,
            sep=";",
            header=False,
            index=False,
            na_rep="",
            quotechar='"',
            doublequote=True,
        )
        output.seek(0)

        columns = df.columns.tolist()

        try:
            with self.conn.cursor() as cursor:
                ident_cols = [sql.Identifier(c) for c in columns]
                copy_stmt = sql.SQL(
                    "COPY {table} ({cols}) FROM STDIN WITH "
                    "(FORMAT CSV, DELIMITER ';', NULL '', QUOTE '\"', HEADER FALSE)"
                ).format(
                    table=sql.Identifier(table_name),
                    cols=sql.SQL(", ").join(ident_cols),
                )
                cursor.copy_expert(copy_stmt.as_string(self.conn), output)

            self.conn.commit()

        except Exception as e:
            self.conn.rollback()
            logger.error(f"Erro no COPY para tabela {table_name}: {e}")
            raise

    def post_load(self):
        if settings.set_logged_after_copy:
            logger.info("Tornando tabelas persistentes (LOGGED) novamente...")
            tables = [
                "empresas",
                "estabelecimentos",
                "socios",
                "simples",
                "paises",
                "municipios",
                "qualificacoes_socios",
                "naturezas_juridicas",
                "cnaes",
            ]
            with self.conn.cursor() as cursor:
                for tbl in tables:
                    cursor.execute(f"ALTER TABLE {tbl} SET LOGGED;")
            self.conn.commit()

    def apply_constraints(self):
        self._execute_sql_file("constraints.sql")

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
            with self.conn.cursor() as cursor:
                cursor.execute(sql_content)
            self.conn.commit()
            logger.info(f"Sucesso ao executar {filename}")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"ERRO ao executar SQL de {filename}: {e}")
            raise
