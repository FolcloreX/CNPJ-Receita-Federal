import requests
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from requests.auth import HTTPBasicAuth
from tqdm import tqdm

from .settings import settings

logger = logging.getLogger(__name__)


def get_session():
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=2,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def get_zip_links(base_url: str) -> list[str]:
    logger.info(f"Listando arquivos via WebDAV: {base_url}")

    session = get_session()

    headers = {"Depth": "1"}

    response = session.request(
        "PROPFIND",
        base_url,
        headers=headers,
        auth=HTTPBasicAuth(settings.rfb_token, ""),
        timeout=60,
    )

    response.raise_for_status()

    root = ET.fromstring(response.text)
    namespaces = {"d": "DAV:"}

    zip_urls = []

    for item in root.findall("d:response", namespaces):
        href_element = item.find("d:href", namespaces)
        if href_element is None:
            continue

        href = href_element.text

        if href.lower().endswith(".zip"):
            full_url = f"https://arquivos.receitafederal.gov.br{href}"
            zip_urls.append(full_url)

    logger.info(f"Encontrados {len(zip_urls)} arquivos .zip.")
    return zip_urls



def download_file(url: str, dest_dir: Path):
    filename = url.split("/")[-1]
    dest_path = dest_dir / filename
    chunk_size = settings.download_chunk_size

    session = get_session()

    try:
        with session.get(
            url,
            stream=True,
            timeout=120,
            auth=HTTPBasicAuth(settings.rfb_token, ""),
        ) as r:
            r.raise_for_status()

            total_size = int(r.headers.get("content-length", 0))

            with open(dest_path, "wb") as f, tqdm(
                desc=filename,
                total=total_size if total_size > 0 else None,
                unit="iB",
                unit_scale=True,
                unit_divisor=1024,
                leave=False,
            ) as bar:

                for chunk in r.iter_content(chunk_size=chunk_size):
                    if chunk:
                        size = f.write(chunk)
                        bar.update(size)

        logger.info(f"Download concluído: {filename}")
        return True

    except Exception as e:
        logger.error(f"Erro ao baixar {filename}: {e}")
        if dest_path.exists():
            dest_path.unlink()
        return False


def run_download():
    logger.info("Iniciando pipeline de download MULTITHREAD (WebDAV)...")

    max_workers = settings.max_workers
    target_url = settings.download_url
    dest_dir = settings.compressed_dir

    zip_links = get_zip_links(target_url)

    if not zip_links:
        raise RuntimeError("Nenhum arquivo .zip encontrado para download.")

    logger.info(
        f"Iniciando download de {len(zip_links)} arquivos com {max_workers} threads."
    )

    files_downloaded = 0
    errors = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(download_file, url, dest_dir): url
            for url in zip_links
        }

        for future in as_completed(futures):
            try:
                if future.result():
                    files_downloaded += 1
                else:
                    errors += 1
            except Exception as exc:
                logger.error(f"Erro inesperado: {exc}")
                errors += 1

    logger.info("=" * 40)
    logger.info("Resumo do Download:")
    logger.info(f"Sucessos: {files_downloaded}")
    logger.info(f"Erros:    {errors}")
    logger.info("=" * 40)

    if errors > 0:
        raise RuntimeError(f"{errors} erros ocorreram durante o download.")
