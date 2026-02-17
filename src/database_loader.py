import pandas as pd
import logging
import re
from .settings import settings

logger = logging.getLogger(__name__)

# --- Funções de Limpeza (compartilhadas entre backends) ---


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


# --- Configuração ETL (compartilhada entre backends) ---

ETL_CONFIG = {
    # --- Tabelas de Domínio ---
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
            "data_situacao_cadastral": str,
            "motivo_situacao_cadastral": pd.Int64Dtype(),
            "nome_cidade_exterior": str,
            "pais_codigo": pd.Int64Dtype(),
            "data_inicio_atividade": str,
            "cnae_fiscal_principal_codigo": pd.Int64Dtype(),
            "cnae_fiscal_secundaria": str,
            "tipo_logradouro": str,
            "logradouro": str,
            "numero": str,
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
            "data_situacao_especial": str,
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
            "data_entrada_sociedade": str,
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

PROCESSING_ORDER = [
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

# --- Backend Factory ---


def _get_backend():
    """Retorna o backend correto baseado na configuração db_engine."""
    if settings.db_engine == "duckdb":
        from .duckdb_loader import DuckDBBackend

        return DuckDBBackend()
    else:
        from .postgres_loader import PostgresBackend

        return PostgresBackend()


# --- Processador (compartilhado) ---


def process_and_load_file(backend, config_name) -> None:
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

        backend.load_chunk(chunk, table_name)

        total_rows += len(chunk)
        logger.info(f"  ... Chunk {i + 1} processado. Total: {total_rows} linhas.")

    logger.info(f"--- Tabela '{table_name}' finalizada! ---")


# --- Orquestração ---


def run_loader() -> None:
    backend = _get_backend()
    logger.info(f"Iniciando carga para {settings.db_engine.upper()}...")

    try:
        backend.connect()
    except Exception as e:
        logger.error(f"Erro ao conectar no banco: {e}")
        raise

    try:
        backend.create_schema()

        for config_name in PROCESSING_ORDER:
            process_and_load_file(backend, config_name)

        backend.post_load()
        logger.info("Carga finalizada com sucesso.")

    except Exception as e:
        logger.error(f"Erro crítico durante o processo: {e}")
        raise
    finally:
        backend.close()


def run_constraints() -> None:
    if settings.skip_constraints:
        logger.info("  [SKIP OPCIONAL] CONSTRAINTS definido pelo usuário")
        return

    backend = _get_backend()
    logger.info("Iniciando aplicação de Constraints e Índices...")
    logger.info("É um processo demorado!!!")

    try:
        backend.connect()
        backend.apply_constraints()
        logger.info("Constraints e Índices aplicados com sucesso.")
    except Exception as e:
        logger.error(f"Erro ao aplicar constraints: {e}")
        raise
    finally:
        backend.close()


if __name__ == "__main__":
    from .settings import setup_logging

    setup_logging()
    run_loader()
