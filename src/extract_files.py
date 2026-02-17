import zipfile
import shutil
import os
from pathlib import Path
from itertools import groupby, takewhile
from typing import List, Iterator, Tuple
import logging
from .settings import settings
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


def get_file_base_name(path: Path) -> str:
    """
    Extrai o nome base de um arquivo, removendo números e a extensão.
    Exemplo: "Empresas4.zip" -> "Empresas"
    """
    base = "".join(takewhile(str.isalpha, path.stem))
    return base or "desconhecido"


def group_files(paths: List[Path]) -> Iterator[Tuple[str, Iterator[Path]]]:
    """
    Agrupa uma lista de caminhos de arquivo pelo seu nome base.
    A função requer que a lista de entrada esteja pré-ordenada
    pela chave de agrupamento.
    """
    # Pré-ordena a lista para que o groupby funcione corretamente
    sorted_paths = sorted(paths, key=get_file_base_name)
    return groupby(sorted_paths, key=get_file_base_name)


def create_directory_if_not_exists(directory: Path):
    """
    Cria um diretório de forma segura, sem falhar se ele já existir.
    Esta função é projetada para executar um efeito colateral:
    modificar o sistema de arquivos.
    """
    try:
        directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"✔️ Diretório '{directory}' garantido.")
    except OSError as e:
        logger.error(f"❌ Erro ao criar o diretório '{directory}': {e}")
        raise


def extract_single_zip(zip_path: Path, destination_dir: Path):
    """
    Extrai um único arquivo .zip para um diretório de destino.
    Isola a operação de extração e lida com erros específicos.
    """
    logger.info(f"   -> Extraindo '{zip_path.name}'...")

    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            for member in zip_ref.infolist():
                member_path = Path(member.filename)
                if member_path.is_absolute():
                    logger.warning(f"~ Ignorando entrada absoluta: {member.filename}")
                    continue

                target_path = (destination_dir / member_path).resolve()
                base_dir = destination_dir.resolve()
                try:
                    base_str = str(base_dir)
                    target_str = str(target_path)
                    if os.path.commonpath([base_str, target_str]) != base_str:
                        logger.warning(
                            f"~ Ignorando entrada potencialmente maliciosa: {member.filename}"
                        )
                        continue
                except Exception:
                    logger.warning(
                        f"   ~ Ignorando entrada inválida: {member.filename}"
                    )
                    continue

                if member.is_dir():
                    target_path.mkdir(parents=True, exist_ok=True)
                else:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    with (
                        zip_ref.open(member, "r") as src,
                        open(target_path, "wb") as dst,
                    ):
                        shutil.copyfileobj(src, dst)

    except zipfile.BadZipFile:
        logger.error(
            f"⚠️ AVISO: O arquivo '{zip_path.name}' está corrompido "
            "ou não é um ZIP válido. Pulando."
        )
        raise

    except Exception as e:
        logger.error(f"   ❌ Erro inesperado ao extrair '{zip_path.name}': {e}")
        raise


# --- Função Principal (Orquestrador) ---


def run_extraction():
    """
    Orquestra todo o processo de descompactação.
    """

    compressed_dir = settings.compressed_dir
    extracted_dir = settings.extracted_dir

    if not compressed_dir.is_dir():
        raise FileNotFoundError(
            f"O diretório de origem '{compressed_dir}' não foi encontrado."
        )

    logger.info(
        f"Iniciando processo de descompactação...\n"
        f"Origem: '{compressed_dir}'\n"
        f"Destino: '{extracted_dir}'\n"
    )

    # 2. Leitura do sistema de arquivos para obter a lista de arquivos.
    zip_files = list(compressed_dir.glob("*.zip"))

    if not zip_files:
        raise FileNotFoundError("Nenhum arquivo .zip encontrado no diretório de origem.")

    # 3. Lógica pura para agrupar os arquivos.
    file_groups = group_files(zip_files)

    # 4. Itera sobre os grupos e aplica os efeitos colaterais (criar dir e extrair).
    for base_name, files_iterator in file_groups:
        target_subdir_name = base_name.lower()
        target_path = extracted_dir / target_subdir_name

        logger.info(f"\n📂 Processando grupo: '{base_name}'")

        create_directory_if_not_exists(target_path)

        files_list = list(files_iterator)
        with ThreadPoolExecutor(max_workers=settings.extract_workers) as executor:
            futures = [
                executor.submit(extract_single_zip, fp, target_path)
                for fp in files_list
            ]
            for future in as_completed(futures):
                future.result()

    logger.info("\n✅ Processo de descompactação concluído com sucesso!")


if __name__ == "__main__":
    run_extraction()
