-- ============================================================================
-- 0. AUTO-REPAIR (CORREÇÃO DE DADOS FALTANTES NAS TABELAS DE DOMÍNIO)
-- ============================================================================

-- 0.1a Corrigir Qualificações (Origem: Empresas)
INSERT INTO qualificacoes_socios (codigo, nome)
SELECT DISTINCT e.qualificacao_responsavel, 'NÃO INFORMADO NA ORIGEM (' || e.qualificacao_responsavel || ')'
FROM empresas e
LEFT JOIN qualificacoes_socios q ON e.qualificacao_responsavel = q.codigo
WHERE q.codigo IS NULL AND e.qualificacao_responsavel IS NOT NULL;

-- 0.1b Corrigir Qualificações (Origem: Sócios)
INSERT INTO qualificacoes_socios (codigo, nome)
SELECT DISTINCT s.qualificacao_socio_codigo, 'NÃO INFORMADO NA ORIGEM (' || s.qualificacao_socio_codigo || ')'
FROM socios s
LEFT JOIN qualificacoes_socios q ON s.qualificacao_socio_codigo = q.codigo
WHERE q.codigo IS NULL AND s.qualificacao_socio_codigo IS NOT NULL;

-- 0.2 Corrigir Naturezas Jurídicas
INSERT INTO naturezas_juridicas (codigo, nome)
SELECT DISTINCT e.natureza_juridica_codigo, 'NÃO INFORMADO NA ORIGEM (' || e.natureza_juridica_codigo || ')'
FROM empresas e
LEFT JOIN naturezas_juridicas n ON e.natureza_juridica_codigo = n.codigo
WHERE n.codigo IS NULL AND e.natureza_juridica_codigo IS NOT NULL;

-- 0.3a Corrigir Países (Origem: Estabelecimentos)
INSERT INTO paises (codigo, nome)
SELECT DISTINCT est.pais_codigo, 'NÃO INFORMADO NA ORIGEM (' || est.pais_codigo || ')'
FROM estabelecimentos est
LEFT JOIN paises p ON est.pais_codigo = p.codigo
WHERE p.codigo IS NULL AND est.pais_codigo IS NOT NULL;

-- 0.3b Corrigir Países (Origem: Sócios)
INSERT INTO paises (codigo, nome)
SELECT DISTINCT s.pais_codigo, 'NÃO INFORMADO NA ORIGEM (' || s.pais_codigo || ')'
FROM socios s
LEFT JOIN paises p ON s.pais_codigo = p.codigo
WHERE p.codigo IS NULL AND s.pais_codigo IS NOT NULL;

-- 0.4 Corrigir Municípios
INSERT INTO municipios (codigo, nome)
SELECT DISTINCT est.municipio_codigo, 'NÃO INFORMADO NA ORIGEM (' || est.municipio_codigo || ')'
FROM estabelecimentos est
LEFT JOIN municipios m ON est.municipio_codigo = m.codigo
WHERE m.codigo IS NULL AND est.municipio_codigo IS NOT NULL;

-- 0.5 Corrigir CNAEs
INSERT INTO cnaes (codigo, nome)
SELECT DISTINCT est.cnae_fiscal_principal_codigo, 'NÃO INFORMADO NA ORIGEM (' || est.cnae_fiscal_principal_codigo || ')'
FROM estabelecimentos est
LEFT JOIN cnaes c ON est.cnae_fiscal_principal_codigo = c.codigo
WHERE c.codigo IS NULL AND est.cnae_fiscal_principal_codigo IS NOT NULL;


-- ============================================================================
-- 1. LIMPEZA DE ÓRFÃOS (REGISTROS SEM EMPRESA PAI)
-- ============================================================================

DELETE FROM simples s
WHERE NOT EXISTS (
    SELECT 1 FROM empresas e WHERE e.cnpj_basico = s.cnpj_basico
);

DELETE FROM socios s
WHERE NOT EXISTS (
    SELECT 1 FROM empresas e WHERE e.cnpj_basico = s.cnpj_basico
);

DELETE FROM estabelecimentos est
WHERE NOT EXISTS (
    SELECT 1 FROM empresas e WHERE e.cnpj_basico = est.cnpj_basico
);


-- ============================================================================
-- 2. ÍNDICES SECUNDÁRIOS
-- ============================================================================

-- Sócios
CREATE INDEX IF NOT EXISTS idx_socios_cnpj_basico ON socios (cnpj_basico);
CREATE INDEX IF NOT EXISTS idx_socios_nome ON socios (nome_socio_ou_razao_social);
CREATE INDEX IF NOT EXISTS idx_socios_cpf_cnpj ON socios (cnpj_cpf_socio);

-- Estabelecimentos
CREATE INDEX IF NOT EXISTS idx_estabelecimentos_uf ON estabelecimentos (uf);
CREATE INDEX IF NOT EXISTS idx_estabelecimentos_cnae ON estabelecimentos (cnae_fiscal_principal_codigo);

-- Empresas
CREATE INDEX IF NOT EXISTS idx_empresas_cnpj ON empresas (cnpj_basico);
CREATE INDEX IF NOT EXISTS idx_empresas_razao_social ON empresas (razao_social);
