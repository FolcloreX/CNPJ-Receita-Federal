import logging
import shutil
from pathlib import Path
from typing import List
from .settings import settings


logger = logging.getLogger(__name__)


def get_subdirectories(base_path: Path):
    """Retorna um iterador de subdiretórios."""
    if not base_path.is_dir():
        logger.error(f"O diretório base '{base_path}' não existe.")
        return iter([])
    return (item for item in base_path.iterdir() if item.is_dir())


def get_source_csv_files(directory: Path, output_filename: str) -> List[Path]:
    """
    Encontra todos os arquivos .csv (ou .CSV), ignorando o arquivo de saída.
    """
    all_files = directory.glob("*")
    return sorted(
        [f for f in all_files if f.is_file() and f.name != output_filename],
        key=lambda f: f.name,
    )


def concatenate_files_in_directory(dir_path: Path):
    """
    Concatena TODOS os bytes de todos os arquivos de origem,
    pois eles não têm cabeçalho. Evitando também erros de charset
    """
    logger.info(f"Iniciando processamento do diretório: '{dir_path.name}'")
    output_filename = f"{dir_path.name}.csv"
    output_filepath = dir_path / output_filename

    source_files = get_source_csv_files(dir_path, output_filename)

    if not source_files:
        logger.warning(
            f"Nenhum arquivo .csv de origem encontrado em '{dir_path.name}'. Pulando."
        )
        return

    logger.info(
        f"Encontrados {len(source_files)} arquivos para concatenar em '{dir_path.name}'."
    )

    try:
        # Abre o arquivo de saída uma vez em modo 'wb' (Write Binary)
        with open(output_filepath, "wb") as f_out:
            # Itera por TODOS os arquivos de origem
            for filepath in source_files:
                logger.info(f"   + Adicionando conteúdo completo de: {filepath.name}")
                # Abre cada arquivo de origem em modo 'rb' (Read Binary)
                with open(filepath, "rb") as f_in:
                    # Copia o conteúdo INTEIRO, byte a byte.
                    shutil.copyfileobj(f_in, f_out)

        logger.info(f"✅ SUCESSO: Arquivo consolidado '{output_filepath}' criado.")

    except Exception as e:
        logger.error(
            f"❌ ERRO inesperado no diretório '{dir_path.name}': {e}", exc_info=True
        )
        raise


def run_consolidation():
    """
    Função principal que orquestra todo o processo de concatenação.
    """
    logger.info("Iniciando processo de consolidação de dados...")

    extracted_dir = settings.extracted_dir

    if not extracted_dir.exists():
        msg = f"Diretório de extração não encontrado: {extracted_dir}"
        logger.error(msg)
        raise FileNotFoundError(msg)

    subdirectories = get_subdirectories(extracted_dir)

    for subdir in subdirectories:
        concatenate_files_in_directory(subdir)

    logger.info("Processo de consolidação finalizado.")
