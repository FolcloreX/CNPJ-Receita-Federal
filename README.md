# CNPJ Dados Abertos - Pipeline de `ETL` para PostgreSQL

Este projeto é uma ferramenta de `ETL` (Extract, Transform, Load) de alto desempenho projetada para automatizar o processo de baixar, tratar e carregar os dados públicos de CNPJ.

[(disponibilizados pela Receita Federal do Brasil)](https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/)

O foco principal é **performance**, utilizando técnicas como `COPY FROM STDIN`, tabelas `UNLOGGED` e tratamento de dados em _chunks_ via Pandas.

# Integridade dos Dados e Inconsistências na Origem

É comum que a base de dados da Receita Federal apresente inconsistências de integridade referencial (ex: um sócio referenciado que não consta na tabela de sócios).

O Pipeline trata esses casos automaticamente: todas as constraints e chaves estrangeiras são validadas após a inserção para que seja aplicada as constraints e não de erro no processo. Quando um registro pai não é encontrado, o sistema insere um dado fictício (dummy) identificado como "NÃO CONSTA NA ORIGEM". Portanto, não se preocupe: os dados já estão higienizados e inseridos, você não terá erro algum.

Para aplicar as restrições formalmente no banco de dados **CASO SEJA NECESSÀRIO**, execute o arquivo constraints.sql. Basta corrigir o dado pontual e executá-lo novamente, sem a necessidade de reiniciar todo o processo de inserção.

O script é **totalmente modular**, caso falhe em alguma etapa basta corrigir o problema e executar o módulo de onde parou.

```bash
python -m src.modulo
```

# 🚀 Fluxo de dados

## 1. Verificação Automática

Checa o site da Receita Federal para identificar se há uma nova versão dos dados disponível comparada à versão local. A data de processamento da última versão disponível fica em `data/last_version_processed.txt`

Você pode adicionar o `main.py` ao seu `crontab ` ele checa se há atualizações, se tiver ele inicia o pipeline de processamento.

**Modulo responsável: `check_update.py`**

## 2. Download dos dados

**Download dos arquivos** em multi-thread, máximo de 4 para evitar abusos de conexões simultâneas.

**Módulo responsável: `downloader.py`**

## 3. Descompactação

Descompacta arquivos baixados que por padrão são dívidos em vários arquivos `.zip`. Extrai agrupando o resultado em uma única pasta, normalmente os dados vem com um nome prefixado e as versões, `empresas01.zip`, `empresas02.zip` etc...

**Módulo responsável: `extract_files.py`**

## 4. Consolidação dos arquivos `CSVs`

Agrupo os `CSVs` descompactados em único arquivo, único por categoria, removendo a necessidade de lidar com múltiplos arquivos durante a carga.

**Módulo responsável: `consolidate_csv.py`**

## 5. Carga para o Banco de dados

Utiliza o comando `COPY` do PostgreSQL (via driver `psycopg`) para inserção em massa.

Cria tabelas como `UNLOGGED` para acelerar a escrita inicial.
Realiza a limpeza de dados (conversão de datas, formatação de arrays para `CNAEs`, sanitização de decimais etc...)

Validação das constraints para que não tenha haja erros de integridade.

Aplicação de Chaves Primárias, Estrangeiras e Índices **após** a carga para maximizar a velocidade.

Schema Otimizado Separação clara entre SQL de definição (`DDL`) e código Python.

**Módulo responsável: `database_loader.py`**

## ⚙️ Configuração e Instalação

### 1. Pré-requisitos

- PostgreSQL instalado e rodando.
- **Espaço em disco:** Recomenda-se pelo menos **80GB livres** (Arquivos compactados + Extraídos + Banco de Dados).

### 2. Instalação

```bash
# Clone o repositório
git clone https://github.com/FolcloreX/CNPJ-Receita-Federal
cd CNPJ-Receita-Federal

# Instale as dependências com Poetry
poetry install
poetry shell
```

### 3. Configuração

Crie um arquivo `.env` na raiz do projeto, existe um exemplo `.env.example` que você também pode renomear. Em `settings.py` há mais configurações opcionais.

```text
# URL RFB
RFB_BASE_URL="https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/"

# Database configuration
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=Dados_RFB

# File configuration
FILE_ENCODING=latin1
CHUNK_SIZE=200_000

# Logging configuration
LOG_LEVEL=INFO
```

## 📊 Diagrama do Banco de Dados (ER)

Também pode ser visualizado em um PDF direto no [Site da receita](https://www.gov.br/receitafederal/dados/cnpj-metadados.pdf)
Há uma versão em markdown em `docs`.

```mermaid
erDiagram
    %% ==========================================
    %% TABELAS PRINCIPAIS
    %% ==========================================

    EMPRESAS {
        string cnpj_basico PK
        string razao_social
        numeric capital_social
        int natureza_juridica_codigo FK
        int qualificacao_responsavel FK
        int porte_empresa
        string ente_federativo_responsavel
    }

    ESTABELECIMENTOS {
        string cnpj_basico PK, FK
        string cnpj_ordem PK
        string cnpj_dv PK
        int identificador_matriz_filial
        string nome_fantasia
        int situacao_cadastral
        date data_situacao_cadastral
        int motivo_situacao_cadastral
        int pais_codigo FK
        int municipio_codigo FK
        int cnae_fiscal_principal_codigo FK
        string[] cnae_fiscal_secundaria
        string uf
    }

    SOCIOS {
        string cnpj_basico FK
        int identificador_socio
        string nome_socio_ou_razao_social
        string cnpj_cpf_socio
        int qualificacao_socio_codigo FK
        int pais_codigo FK
        int qualificacao_representante_legal_codigo FK
    }

    SIMPLES {
        string cnpj_basico PK, FK
        string opcao_pelo_simples
        date data_opcao_pelo_simples
        date data_exclusao_do_simples
        string opcao_pelo_mei
    }

    %% ==========================================
    %% TABELAS DE DOMÍNIO
    %% ==========================================

    NATUREZAS_JURIDICAS {
        int codigo PK
        string nome
    }

    QUALIFICACOES_SOCIOS {
        int codigo PK
        string nome
    }

    CNAES {
        int codigo PK
        string nome
    }

    PAISES {
        int codigo PK
        string nome
    }

    MUNICIPIOS {
        int codigo PK
        string nome
    }

    %% ==========================================
    %% RELACIONAMENTOS
    %% ==========================================

    EMPRESAS ||--|{ ESTABELECIMENTOS : "possui (1:N)"
    EMPRESAS ||--o{ SOCIOS : "tem (1:N)"
    EMPRESAS ||--o| SIMPLES : "pode ter (1:1)"

    EMPRESAS }|--|| NATUREZAS_JURIDICAS : "tipo de"
    EMPRESAS }|--|| QUALIFICACOES_SOCIOS : "qualif. responsavel"

    ESTABELECIMENTOS }|--|| MUNICIPIOS : "localizado em"
    ESTABELECIMENTOS }|--|| PAISES : "localizado em"
    ESTABELECIMENTOS }|--|| CNAES : "atividade principal"

    SOCIOS }|--|| PAISES : "nacionalidade"
    SOCIOS }|--|| QUALIFICACOES_SOCIOS : "qualif. sócio"
```

### Explicação Visual das Ligações

1. **EMPRESAS (Central)**: É a tabela pai. Ela conecta com:

   - **ESTABELECIMENTOS**: Ligação forte (PK composta). Uma empresa tem várias filiais.

   - **SOCIOS**: Uma empresa tem vários sócios.

   - **SIMPLES**: Uma empresa pode ou não ter registro no Simples (0 ou 1).

2. **ESTABELECIMENTOS**:

   - Conecta com **CNAES** (Atividade econômica).

   - Conecta com **MUNICIPIOS** e **PAISES** (Geografia).

   - Nota: cnae_fiscal_secundaria não tem linha no diagrama ligando a CNAES porque implementamos como um **Array** de texto para performance, e não como uma tabela associativa (N:N), embora logicamente sejam códigos CNAE.

3. **SOCIOS**:

   - Conecta com **QUALIFICACOES** (Para saber se é diretor, presidente, etc).

## 🤝 Contribuição

Sinta-se à vontade para abrir Issues relatando inconsistências nos dados da Receita ou enviar `PRs` com melhorias de performance.
