-- ============================================================================
-- 1. LIMPEZA INICIAL (DROP) | CUIDADO APAGA TUDO
-- ============================================================================
DROP TABLE IF EXISTS socios CASCADE;
DROP TABLE IF EXISTS simples CASCADE;
DROP TABLE IF EXISTS estabelecimentos CASCADE;
DROP TABLE IF EXISTS empresas CASCADE;
DROP TABLE IF EXISTS cnaes CASCADE;
DROP TABLE IF EXISTS naturezas_juridicas CASCADE;
DROP TABLE IF EXISTS qualificacoes_socios CASCADE;
DROP TABLE IF EXISTS municipios CASCADE;
DROP TABLE IF EXISTS paises CASCADE;

-- ============================================================================
-- 2. TABELAS DE DOMÍNIO (UNLOGGED para carga rápida) SEM PK SEM FK
-- Se use_unlogged=False, o loader altera para LOGGED logo após criação.
-- ============================================================================

CREATE UNLOGGED TABLE paises (
    codigo SMALLINT, -- Max 999
    nome VARCHAR(100)
);

CREATE UNLOGGED TABLE municipios (
    codigo SMALLINT, -- Código SIAFI (4 dígitos)
    nome VARCHAR(150)
);

CREATE UNLOGGED TABLE qualificacoes_socios (
    codigo SMALLINT,
    nome VARCHAR(100)
);

CREATE UNLOGGED TABLE naturezas_juridicas (
    codigo SMALLINT,
    nome VARCHAR(150)
);

CREATE UNLOGGED TABLE cnaes (
    codigo INTEGER, -- 7 dígitos (ex: 4711302), precisa ser INTEGER
    nome VARCHAR(500) -- Algumas descrições são longas
);

-- ============================================================================
-- 3. TABELAS PRINCIPAIS (UNLOGGED)
-- ============================================================================

CREATE UNLOGGED TABLE empresas (
    cnpj_basico CHAR(8),
    razao_social VARCHAR(255),
    natureza_juridica_codigo SMALLINT,
    qualificacao_responsavel SMALLINT,
    capital_social NUMERIC(18, 2),
    porte_empresa SMALLINT,
    ente_federativo_responsavel VARCHAR(100)
);

CREATE UNLOGGED TABLE estabelecimentos (
    cnpj_basico CHAR(8),
    cnpj_ordem CHAR(4),
    cnpj_dv CHAR(2),
    identificador_matriz_filial SMALLINT,
    nome_fantasia VARCHAR(255),
    situacao_cadastral SMALLINT,
    data_situacao_cadastral DATE,
    motivo_situacao_cadastral SMALLINT,
    nome_cidade_exterior VARCHAR(100),
    pais_codigo SMALLINT,
    data_inicio_atividade DATE,
    cnae_fiscal_principal_codigo INTEGER, -- 7 dígitos
    cnae_fiscal_secundaria TEXT[],        -- Array nativo do Postgres
    tipo_logradouro VARCHAR(50),
    logradouro VARCHAR(255),
    numero VARCHAR(20),
    complemento VARCHAR(255),
    bairro VARCHAR(100),
    cep CHAR(8),
    uf CHAR(2),
    municipio_codigo SMALLINT,
    ddd_1 VARCHAR(4),
    telefone_1 VARCHAR(9),
    ddd_2 VARCHAR(4),
    telefone_2 VARCHAR(9),
    ddd_fax VARCHAR(4),
    fax VARCHAR(9),
    correio_eletronico VARCHAR(255),
    situacao_especial VARCHAR(100),
    data_situacao_especial DATE
);

CREATE UNLOGGED TABLE simples (
    cnpj_basico CHAR(8),
    opcao_pelo_simples CHAR(1),
    data_opcao_pelo_simples DATE,
    data_exclusao_do_simples DATE,
    opcao_pelo_mei CHAR(1),
    data_opcao_pelo_mei DATE,
    data_exclusao_do_mei DATE
);

CREATE UNLOGGED TABLE socios (
    cnpj_basico CHAR(8),
    identificador_socio SMALLINT, -- 1, 2 ou 3
    nome_socio_ou_razao_social VARCHAR(255),
    cnpj_cpf_socio VARCHAR(14), -- Pode ser CPF (11) ou CNPJ (14)
    qualificacao_socio_codigo SMALLINT,
    data_entrada_sociedade DATE,
    pais_codigo SMALLINT,
    representante_legal_cpf VARCHAR(11),
    nome_representante_legal VARCHAR(255),
    qualificacao_representante_legal_codigo SMALLINT,
    faixa_etaria SMALLINT -- 0 a 9
);
