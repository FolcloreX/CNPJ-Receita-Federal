import requests
import logging
import shutil
import sys
import re
import xml.etree.ElementTree as ET

from typing import Optional
from requests.auth import HTTPBasicAuth

from .settings import settings, state, StepStatus, PipelineStep

# Configura logger local para este script
logger = logging.getLogger("updater")


def get_latest_remote_date() -> Optional[str]:
    """
    Consulta o WebDAV público da Receita Federal (Nextcloud)
    e retorna a pasta mais recente no formato YYYY-MM.
    """

    try:
        headers = {"Depth": "1"}  # evita listar subníveis desnecessários

        response = requests.request(
            "PROPFIND",
            settings.rfb_base_url,
            headers=headers,
            auth=HTTPBasicAuth(settings.rfb_token, ""),
            timeout=60,
        )

        response.raise_for_status()

        root = ET.fromstring(response.text)

        namespaces = {"d": "DAV:"}
        date_pattern = re.compile(r"(\d{4}-\d{2})/$")

        dates = []

        for item in root.findall("d:response", namespaces):
            href_element = item.find("d:href", namespaces)
            if href_element is None:
                continue

            href = href_element.text
            match = date_pattern.search(href)

            if match:
                dates.append(match.group(1))

        if not dates:
            logger.warning("Nenhuma pasta YYYY-MM encontrada no WebDAV.")
            return None

        dates.sort(reverse=True)
        latest = dates[0]

        logger.info(f"Versão mais recente encontrada via WebDAV: {latest}")
        return latest

    except Exception as e:
        logger.error(f"Erro ao checar atualizações via WebDAV: {e}")
        return None


def clean_data_dirs() -> None:
    """
    Limpa as pastas de dados antigos antes de baixar os novos.
    Isso é crucial para não misturar dados de meses diferentes.
    """
    logger.info("Limpando diretórios de dados antigos...")

    compressed_dir = settings.compressed_dir
    extracted_dir = settings.extracted_dir

    # Limpa arquivos comprimidos
    for item in compressed_dir.glob("*"):
        if item.is_file():
            item.unlink()

    # Limpa arquivos extraídos
    for item in extracted_dir.glob("*"):
        if item.is_dir():
            shutil.rmtree(item)
        elif item.is_file():
            item.unlink()

    logger.info("Diretórios limpos.")


def check_updates() -> Optional[str]:
    logger.info("Verificando atualizações na Receita Federal via WebDAV...")

    latest_remote = get_latest_remote_date()
    last_processed = state.target_date

    if not latest_remote:
        logger.error("Não foi possível determinar a versão remota.")
        raise RuntimeError(
            "Falha crítica: Não foi possível obter a última versão no WebDAV da Receita."
        )

    logger.info(f"Última versão disponível: {latest_remote}")
    logger.info(f"Última versão processada: {last_processed}")

    if latest_remote == last_processed:
        return None

    logger.info(f"Nova versão encontrada: {latest_remote}. Iniciando atualização.")

    # Atualiza estado (isso já reseta os steps anteriores)
    state.target_date = latest_remote

    logger.info("Removendo arquivos antigos (se existirem)...")
    clean_data_dirs()

    return latest_remote


def run_check_step() -> None:
    """
    Executa a verificação. Se achar nova versão, reseta o estado.
    Se não achar e não tiver histórico, encerra o script.
    """

    new_date = check_updates()

    if new_date:
        logger.info(f"📅 Nova versão detectada: {new_date}")

        # Atualiza config runtime (state.target_date already set in check_updates)
        settings.target_date = new_date

    elif state.target_date:
        # NÃO sobrescreve com None
        settings.target_date = state.target_date
        logger.info(f"🔄 Nenhuma novidade. Retomando versão: {state.target_date}")

    else:
        logger.error("Nenhuma versão encontrada e nenhum histórico salvo.")
        sys.exit(1)

    # Caso já esteja completamente processado
    if (
        state.current_state == PipelineStep.CONSTRAINTS
        and state.current_status == StepStatus.COMPLETED.value
    ):
        logger.info(
            f"✅ Versão {state.target_date} já processada completamente. Nada a fazer."
        )
        sys.exit(0)


if __name__ == "__main__":
    run_check_step()
