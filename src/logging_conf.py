# src/logging_conf.py
from src.settings import WORK_DIR  # Reutilizamos ruta de trabajo

import logging
from pathlib import Path

# Ruta del archivo de log (opcional)
LOG_FILE = WORK_DIR / "app.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
def setup_logging(level: str = "INFO") -> None:
    """
    Configura logging global para la aplicación.

    Args:
        level: Nivel mínimo de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Formato de salida
    log_format = (
        "%(asctime)s | %(levelname)-8s | %(name)s | "
        "%(funcName)s:%(lineno)d | %(message)s"
    )

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=log_format,
        handlers=[
            logging.StreamHandler(),            # salida a consola
            logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")  # archivo
        ],
    )

def get_logger(name: str) -> logging.Logger:
    """
    Retorna un logger listo para usar.
    """
    return logging.getLogger(name)
