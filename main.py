import logging
import argparse
import sys
import time

# Imports do projeto
from src import (
    extract_files,
    downloader,
    consolidate_csv,
    database_loader,
    check_update,
)
from src.settings import setup_logging, state, PipelineStep, StepStatus

setup_logging()
logger = logging.getLogger("orchestrator")


PIPELINE_MAP = {
    PipelineStep.DOWNLOAD: downloader.run_download,
    PipelineStep.EXTRACT: extract_files.run_extraction,
    PipelineStep.CONSOLIDATE: consolidate_csv.run_consolidation,
    PipelineStep.LOAD: database_loader.run_loader,
    PipelineStep.CONSTRAINTS: database_loader.run_constraints,
}


def run_pipeline(force: bool = False):
    start_time = time.time()
    logger.info("🚀 Iniciando Pipeline CNPJ...")

    check_update.run_check_step()

    for step_name, step_func in PIPELINE_MAP.items():
        if not force and state.should_skip(step_name):
            logger.info(f"⏭️  [SKIP] {step_name.value.upper()}")
            continue

        logger.info(f"▶️  [RUN] {step_name.value.upper()}...")
        state.update(step_name, StepStatus.RUNNING)

        try:
            step_func()
            state.update(step_name, StepStatus.COMPLETED)
            logger.info(f"✅ [OK] {step_name.value.upper()}")

        except KeyboardInterrupt:
            logger.warning("\n⚠️ Interrompido pelo usuário.")
            state.update(step_name, StepStatus.FAILED)
            sys.exit(130)

        except SystemExit:
            raise

        except Exception as e:
            logger.error(f"❌ [ERRO] {step_name.value.upper()}: {e}", exc_info=True)
            state.update(step_name, StepStatus.FAILED)
            sys.exit(1)

    elapsed = time.time() - start_time
    logger.info(f"🏁 Pipeline Finalizado com Sucesso em {elapsed:.2f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force", action="store_true", help="Ignora o histórico e roda tudo."
    )
    args = parser.parse_args()

    run_pipeline(force=args.force)
