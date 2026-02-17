import pandas as pd
import logging
import io
import re
import psycopg2
from psycopg2 import sql
from pathlib import Path
from .settings import settings

logger = logging.getLogger(__name__)

# --- Funções de Carga e Limpeza ---


def fast_load_chunk(conn, df, table_name):
    """
    Função de Carga Ultra-Rápida (PostgreSQL COPY).
    Recebe a conexão direta do psycopg2 (conn).
    """
    output = io.StringIO()

    # Prepara o CSV em memória
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

    # Usa um cursor para executar o COPY
    try:
        with conn.cursor() as cursor:
            ident_cols = [sql.Identifier(c) for c in columns]
            copy_stmt = sql.SQL(
                "COPY {table} ({cols}) FROM STDIN WITH (FORMAT CSV, DELIMITER ';', NULL '', QUOTE '\"', HEADER FALSE)"
            ).format(
                table=sql.Identifier(table_name),
                cols=sql.SQL(", ").join(ident_cols),
            )
            cursor.copy_expert(copy_stmt.as_string(conn), output)

        # O commit é feito no nível superior (loop de processamento)
        # para evitar commit a cada chunk pequeno se desejar,
        # mas aqui faremos commit por chunk para liberar memória do PG.
        conn.commit()

    except Exception as e:
        conn.rollback()
        logger.error(f"Erro no COPY para tabela {table_name}: {e}")
        raise


def sanitize_dates(df, date_columns):
    cols = [c for c in date_columns if c in df.columns]
    if cols:
        df[cols] = df[cols].apply(
            lambda s: pd.to_datetime(s, format="%Y%m%d", errors="coerce")
        )
    return df


def clean_empresas_chunk(chunk_df):
    if "capital_social" in chunk_df.columns:
        chunk_df["capital_social"] = pd.to_numeric(
            chunk_df["capital_social"].astype(str).str.replace(",", ".", regex=False),
            errors="coerce",
        )
    return chunk_df


def clean_estabelecimentos_chunk(chunk_df):
    date_cols = [
        "data_situacao_cadastral",
        "data_inicio_atividade",
        "data_situacao_especial",
    ]
    chunk_df = sanitize_dates(chunk_df, date_cols)
    col_name = "cnae_fiscal_secundaria"
    if col_name in chunk_df.columns:
        s = chunk_df[col_name].fillna("").astype(str)

        def to_pg_array(x):
            if not x.strip():
                return None
            parts = [p.strip() for p in re.split(r"[;,]", x) if p.strip()]
            return "{" + ",".join(parts) + "}" if parts else None

        chunk_df[col_name] = s.map(to_pg_array)
    return chunk_df


def clean_socios_chunk(chunk_df):
    return sanitize_dates(chunk_df, ["data_entrada_sociedade"])


def clean_simples_chunk(chunk_df):
    return sanitize_dates(
        chunk_df,
        [
            "data_opcao_pelo_simples",
            "data_exclusao_do_simples",
            "data_opcao_pelo_mei",
            "data_exclusao_do_mei",
        ],
    )


ETL_CONFIG = {
    # --- Tabelas de Domínio ---
    # Tipar essas tabelas evita que códigos "01" virem "1" se forem lidos como int,
    # ou garante performance se forem int. Aqui assumimos int para códigos.
    "paises": {
        "table_name": "paises",
        "column_names": ["codigo", "nome"],
        "dtype_map": {"codigo": pd.Int64Dtype(), "nome": str},
    },
    "municipios": {
        "table_name": "municipios",
        "column_names": ["codigo", "nome"],
        "dtype_map": {"codigo": pd.Int64Dtype(), "nome": str},
    },
    "qualificacoes": {
        "table_name": "qualificacoes_socios",
        "column_names": ["codigo", "nome"],
        "dtype_map": {"codigo": pd.Int64Dtype(), "nome": str},
    },
    "naturezas": {
        "table_name": "naturezas_juridicas",
        "column_names": ["codigo", "nome"],
        "dtype_map": {"codigo": pd.Int64Dtype(), "nome": str},
    },
    "cnaes": {
        "table_name": "cnaes",
        "column_names": ["codigo", "nome"],
        "dtype_map": {"codigo": pd.Int64Dtype(), "nome": str},
    },
    # --- Tabelas de Dados Principais ---
    "empresas": {
        "table_name": "empresas",
        "column_names": [
            "cnpj_basico",
            "razao_social",
            "natureza_juridica_codigo",
            "qualificacao_responsavel",
            "capital_social",
            "porte_empresa",
            "ente_federativo_responsavel",
        ],
        "dtype_map": {
            "cnpj_basico": str,
            "razao_social": str,
            "natureza_juridica_codigo": pd.Int64Dtype(),
            "qualificacao_responsavel": pd.Int64Dtype(),
            "capital_social": str,  # Lido como str para tratamento de vírgula
            "porte_empresa": pd.Int64Dtype(),
            "ente_federativo_responsavel": str,
        },
        "custom_clean_func": clean_empresas_chunk,
    },
    "estabelecimentos": {
        "table_name": "estabelecimentos",
        "column_names": [
            "cnpj_basico",
            "cnpj_ordem",
            "cnpj_dv",
            "identificador_matriz_filial",
            "nome_fantasia",
            "situacao_cadastral",
            "data_situacao_cadastral",
            "motivo_situacao_cadastral",
            "nome_cidade_exterior",
            "pais_codigo",
            "data_inicio_atividade",
            "cnae_fiscal_principal_codigo",
            "cnae_fiscal_secundaria",
            "tipo_logradouro",
            "logradouro",
            "numero",
            "complemento",
            "bairro",
            "cep",
            "uf",
            "municipio_codigo",
            "ddd_1",
            "telefone_1",
            "ddd_2",
            "telefone_2",
            "ddd_fax",
            "fax",
            "correio_eletronico",
            "situacao_especial",
            "data_situacao_especial",
        ],
        "dtype_map": {
            "cnpj_basico": str,
            "cnpj_ordem": str,
            "cnpj_dv": str,
            "identificador_matriz_filial": pd.Int64Dtype(),
            "nome_fantasia": str,
            "situacao_cadastral": pd.Int64Dtype(),
            "data_situacao_cadastral": str,  # Data como str para limpeza posterior
            "motivo_situacao_cadastral": pd.Int64Dtype(),
            "nome_cidade_exterior": str,
            "pais_codigo": pd.Int64Dtype(),
            "data_inicio_atividade": str,  # Data como str
            "cnae_fiscal_principal_codigo": pd.Int64Dtype(),
            "cnae_fiscal_secundaria": str,  # Lista vem como texto
            "tipo_logradouro": str,
            "logradouro": str,
            "numero": str,  # Número pode ter letras "S/N", "KM 30"
            "complemento": str,
            "bairro": str,
            "cep": str,
            "uf": str,
            "municipio_codigo": pd.Int64Dtype(),
            "ddd_1": str,
            "telefone_1": str,
            "ddd_2": str,
            "telefone_2": str,
            "ddd_fax": str,
            "fax": str,
            "correio_eletronico": str,
            "situacao_especial": str,
            "data_situacao_especial": str,  # Data como str
        },
        "custom_clean_func": clean_estabelecimentos_chunk,
    },
    "socios": {
        "table_name": "socios",
        "column_names": [
            "cnpj_basico",
            "identificador_socio",
            "nome_socio_ou_razao_social",
            "cnpj_cpf_socio",
            "qualificacao_socio_codigo",
            "data_entrada_sociedade",
            "pais_codigo",
            "representante_legal_cpf",
            "nome_representante_legal",
            "qualificacao_representante_legal_codigo",
            "faixa_etaria",
        ],
        "dtype_map": {
            "cnpj_basico": str,
            "identificador_socio": pd.Int64Dtype(),
            "nome_socio_ou_razao_social": str,
            "cnpj_cpf_socio": str,
            "qualificacao_socio_codigo": pd.Int64Dtype(),
            "data_entrada_sociedade": str,  # Data como str
            "pais_codigo": pd.Int64Dtype(),
            "representante_legal_cpf": str,
            "nome_representante_legal": str,
            "qualificacao_representante_legal_codigo": pd.Int64Dtype(),
            "faixa_etaria": pd.Int64Dtype(),
        },
        "custom_clean_func": clean_socios_chunk,
    },
    "simples": {
        "table_name": "simples",
        "column_names": [
            "cnpj_basico",
            "opcao_pelo_simples",
            "data_opcao_pelo_simples",
            "data_exclusao_do_simples",
            "opcao_pelo_mei",
            "data_opcao_pelo_mei",
            "data_exclusao_do_mei",
        ],
        "dtype_map": {
            "cnpj_basico": str,
            "opcao_pelo_simples": str,
            "data_opcao_pelo_simples": str,
            "data_exclusao_do_simples": str,
            "opcao_pelo_mei": str,
            "data_opcao_pelo_mei": str,
            "data_exclusao_do_mei": str,
        },
        "custom_clean_func": clean_simples_chunk,
    },
}

# --- Processador ---


def process_and_load_file(conn, config_name) -> None:
    try:
        etl_config = ETL_CONFIG[config_name]
    except KeyError:
        logger.error(f"Configuração para '{config_name}' não encontrada.")
        raise

    table_name = etl_config["table_name"]
    file_path = settings.extracted_dir / config_name / f"{config_name}.csv"

    if not file_path.exists():
        logger.warning(f"Arquivo '{file_path}' não encontrado. Pulando.")
        raise FileNotFoundError(f"Arquivo '{file_path}' não encontrado. Pulando.")

    logger.info(f"--- Processando tabela '{table_name}' (via '{config_name}') ---")

    reader = pd.read_csv(
        file_path,
        delimiter=";",
        encoding=settings.file_encoding,
        header=None,
        names=etl_config["column_names"],
        dtype=etl_config.get("dtype_map", None),
        chunksize=settings.chunk_size,
    )

    total_rows = 0
    for i, chunk in enumerate(reader):
        if "custom_clean_func" in etl_config:
            chunk = etl_config["custom_clean_func"](chunk)

        # Passa a conexão direta
        fast_load_chunk(conn, chunk, table_name)

        total_rows += len(chunk)
        logger.info(f"  ... Chunk {i + 1} processado. Total: {total_rows} linhas.")

    logger.info(f"--- Tabela '{table_name}' finalizada! ---")


def execute_sql_file(conn, filename) -> None:
    """
    Lê e executa um arquivo SQL usando cursor do psycopg2.
    """
    base_path = Path(__file__).parent
    file_path = base_path / filename

    if not file_path.exists():
        logger.error(f"Arquivo SQL não encontrado: {file_path}")
        return

    logger.info(f"Executando SQL: {filename}")
    with open(file_path, "r", encoding="utf-8") as f:
        sql_content = f.read()

    try:
        with conn.cursor() as cursor:
            cursor.execute(sql_content)
        conn.commit()  # Confirma as alterações do DDL
        logger.info(f"Sucesso ao executar {filename}")
    except Exception as e:
        conn.rollback()
        logger.error(f"ERRO ao executar SQL de {filename}: {e}")
        raise


def run_loader() -> None:
    logger.info("🚀 Iniciando carga para PostgreSQL (Driver Nativo)...")

    # Conexão direta via psycopg2
    try:
        conn = psycopg2.connect(settings.database_uri)
    except Exception as e:
        logger.error(f"Erro ao conectar no banco: {e}")
        raise

    try:
        # Cria as tabelas
        execute_sql_file(conn, "schema.sql")

        all_tables = [
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

        if not settings.use_unlogged:
            logger.info("use_unlogged=False: Tornando tabelas LOGGED antes da carga...")
            with conn.cursor() as cursor:
                for tbl in all_tables:
                    cursor.execute(
                        sql.SQL("ALTER TABLE {} SET LOGGED;").format(sql.Identifier(tbl))
                    )
            conn.commit()

        processing_order = [
            "paises",
            "municipios",
            "qualificacoes",
            "naturezas",
            "cnaes",
            "empresas",
            "estabelecimentos",
            "simples",
            "socios",
        ]

        # Fluxo principal de processamento dos arquivos CSV para SQL
        for config_name in processing_order:
            process_and_load_file(conn, config_name)

        if settings.use_unlogged and settings.set_logged_after_copy:
            logger.info("Tornando tabelas persistentes (LOGGED) novamente...")
            with conn.cursor() as cursor:
                for tbl in all_tables:
                    cursor.execute(
                        sql.SQL("ALTER TABLE {} SET LOGGED;").format(sql.Identifier(tbl))
                    )
            conn.commit()

        logger.info("Carga finalizada com sucesso.")

    except Exception as e:
        logger.error(f"Erro crítico durante o processo: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def run_constraints() -> None:
    if settings.skip_constraints:
        logger.info("⏭️  [SKIP OPCIONAL] CONSTRAINTS definido pelo usuário")
        return

    logger.info("🔒 Iniciando aplicação de Constraints e Índices...")
    logger.info("É um processo demorado!!!")

    conn = None
    try:
        conn = psycopg2.connect(settings.database_uri)

        # Como isso demora, aumentar o timeout da sessão se necessário,
        # mas índices geralmente rodam bem na conexão padrão.
        execute_sql_file(conn, "constraints.sql")

        logger.info("✅ Constraints e Índices aplicados com sucesso.")

    except Exception as e:
        logger.error(f"❌ Erro ao aplicar constraints: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    from .settings import setup_logging

    setup_logging()
    run_loader()
