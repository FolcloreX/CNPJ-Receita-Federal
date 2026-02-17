import json
import logging
from pathlib import Path

from typing import Literal, Dict, Optional
from enum import Enum
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, computed_field


def setup_logging():
    log_file = settings.log_dir / "cnpj.log"
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(levelname)s - %(asctime)s - [%(name)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, mode="w"),
            logging.StreamHandler(),
        ],
    )


class PipelineStep(str, Enum):
    CHECK = "check"
    DOWNLOAD = "download"
    EXTRACT = "extract"
    CONSOLIDATE = "consolidate"
    LOAD = "load"
    CONSTRAINTS = "constraints"


class StepStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    RUNNING = "running"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Estrutura do Projeto ---
    project_root: Path = Field(
        default=Path(__file__).resolve().parents[1],
        description="Caminho raiz do projeto (sobe 2 níveis a partir deste arquivo).",
    )

    rfb_base_url: str = Field(
        default="https://arquivos.receitafederal.gov.br/public.php/webdav/",
        description="URL Base da Receita Federal onde ficam as pastas por data.",
    )

    rfb_token: str = Field(
        default="YggdBLfdninEJX9",
        description="teste"
    )

    target_date: str = Field(
        default="",
        description=(
            "Data alvo (YYYY-MM) para download. Se vazio, é preenchido"
            "dinamicamente pelo check_update."
        ),
    )

    # --- Banco de Dados (Obrigatórios) ---
    postgres_user: str = Field(description="Usuário do PostgreSQL.")
    postgres_password: str = Field(description="Senha do PostgreSQL.")
    postgres_host: str = Field(description="Host do banco (ex: localhost, db).")
    postgres_port: int = Field(default=5432, description="Porta do banco.")
    postgres_database: str = Field(description="Nome do banco de dados.")

    # --- Performance de Download/Extração ---
    max_workers: int = Field(
        default=4,
        description="Número máximo de downloads simultâneos.",
    )
    extract_workers: int = Field(
        default=2, description="Número de processos paralelos para extração de ZIPs."
    )
    download_chunk_size: int = Field(
        default=8192, description="Tamanho do buffer (bytes) para download em stream."
    )

    # --- Otimização de Carga (UNLOGGED) ---
    use_unlogged: bool = Field(
        default=True,
        description=(
            "Cria tabelas como UNLOGGED (sem WAL) para escrita ultra-rápida."
            "Dados somem se o servidor reiniciar durante a carga.",
        ),
    )

    set_logged_after_copy: bool = Field(
        default=True,
        description=(
            "Se True, altera as tabelas para LOGGED (persistentes) ao final"
            "da carga. Recomendado para segurança.",
        ),
    )

    cluster_after_copy: bool = Field(
        default=False,
        description=(
            "Se True, reordena fisicamente a tabela no disco baseada"
            "no índice (CLUSTER). Operação muito lenta.",
        ),
    )

    # --- Constraints e Integridade ---
    skip_constraints: bool = Field(
        default=False,
        description=(
            "Se True, PULA a criação de PKs, FKs e Índices. "
            "Útil se você quer apenas os dados brutos para leitura rápida "
            "ou se os dados da Receita estiverem muito inconsistentes."
        ),
    )

    # --- Tratamento de Arquivos ---
    normalize_line_endings: bool = Field(
        default=True, description="Converte quebras de linha Windows/Linux para padrão."
    )
    strip_bom: bool = Field(
        default=True,
        description="Remove Byte Order Mark (BOM) do início dos arquivos CSV.",
    )
    file_encoding: str = Field(
        default="latin1",
        description="Encoding original dos arquivos da Receita (geralmente latin1/iso-8859-1).",
    )

    chunk_size: int = Field(
        default=200_000,
        description=(
            "Quantidade de linhas lidas por vez na memória (Pandas Chunk). "
            "Aumentar consome mais RAM, diminuir deixa o processo mais lento."
        ),
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", description="Nível de detalhe dos logs."
    )

    @computed_field
    def download_url(self) -> str:
        """Monta a URL completa baseada na data alvo."""
        if not self.target_date:
            return ""
            
        return f"{self.rfb_base_url}{self.target_date}/"

    @computed_field
    def data_dir(self) -> Path:
        return self.project_root / "data"

    @computed_field
    def log_dir(self) -> Path:
        return self.project_root / "logs"

    @computed_field
    def compressed_dir(self) -> Path:
        return self.data_dir / "compressed_files"

    @computed_field
    def extracted_dir(self) -> Path:
        return self.data_dir / "extracted_files"

    @computed_field
    def queries_dir(self) -> Path:
        return self.project_root / "queries"

    @computed_field
    def database_uri(self) -> str:
        return (
            f"postgresql://{self.postgres_user}"
            f":{self.postgres_password}"
            f"@{self.postgres_host}"
            f":{self.postgres_port}"
            f"/{self.postgres_database}"
        )

    def create_dirs(self):
        """Garante que a estrutura de pastas exista."""
        dirs = [
            self.data_dir,
            self.compressed_dir,
            self.extracted_dir,
            self.queries_dir,
            self.log_dir,
        ]
        for p in dirs:
            p.mkdir(parents=True, exist_ok=True)


class ProcessState:
    def __init__(self, data_dir: Path):
        self.file_path = data_dir / "state.json"
        self.data = self._load()

    def _load(self) -> Dict:
        """Carrega o JSON. Retorna vazio se não existir."""
        if not self.file_path.exists():
            return {}
        try:
            return json.loads(self.file_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self):
        """Persiste o estado atual no disco."""
        self.file_path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    @property
    def target_date(self) -> Optional[str]:
        return self.data.get("target_date")

    @property
    def current_status(self) -> Optional[str]:
        return self.data.get("status")

    @property
    def current_state(self) -> Optional[str]:
        return self.data.get("stage")

    @target_date.setter
    def target_date(self, value: str):
        """Define a data alvo. Reseta o estágio para None se a data mudar."""
        current = self.data.get("target_date")
        if value != current:
            self.data = {"target_date": value, "stage": None, "status": None}
            self._save()

    def update(self, step: PipelineStep, status: StepStatus):
        """
        Atualiza o estágio atual e seu status.
        Ex: stage='download', status='completed'
        """
        self.data["stage"] = step.value
        self.data["status"] = status.value
        self._save()

    def should_skip(self, current_step: PipelineStep) -> bool:
        """
        Verifica se deve pular a etapa atual baseada no histórico salvo.
        Retorna True se a etapa já foi concluída ou superada.
        """

        if not self.target_date:
            return False

        saved_stage = self.data.get("stage")
        saved_status = self.data.get("status")

        if not saved_stage:
            return False

        # Define a ordem exata de execução
        # (Isso precisa bater com a ordem do PipelineStep Enum na main)
        order = [
            PipelineStep.CHECK.value,
            PipelineStep.DOWNLOAD.value,
            PipelineStep.EXTRACT.value,
            PipelineStep.CONSOLIDATE.value,
            PipelineStep.LOAD.value,
            PipelineStep.CONSTRAINTS.value,
        ]

        try:
            current_index = order.index(current_step.value)
            saved_index = order.index(saved_stage)
        except ValueError:
            # Se tiver algum valor estranho no JSON, não pula por segurança
            return False

        # Se a etapa salva é SUPERIOR a atual (ex: Salvo=Load, Atual=Download) -> PULA
        if saved_index > current_index:
            return True

        # Se é a MESMA etapa e está COMPLETED -> PULA
        if saved_index == current_index and saved_status == StepStatus.COMPLETED.value:
            return True

        return False


# --- Instanciação Global ---
settings = Settings()
settings.create_dirs()

# Instância única do Estado
state = ProcessState(settings.data_dir)
