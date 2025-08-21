import os
import logging
import logging.handlers
from datetime import datetime

def _ensure_dir(path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)

def configure_logging_from_env(logger_name: str) -> logging.Logger:
    log_to_file = os.getenv("LOG_TO_FILE", "false").lower() == "true"
    log_file = os.getenv("LOG_FILE", "logs/app.log")
    log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    rotate_mode = os.getenv("LOG_ROTATE", "size").lower()
    max_bytes = int(os.getenv("LOG_MAX_BYTES", "1048576"))
    backup_count = int(os.getenv("LOG_BACKUP_COUNT", "10"))
    when = os.getenv("LOG_WHEN", "midnight")
    interval = int(os.getenv("LOG_INTERVAL", "1"))

    logger = logging.getLogger(logger_name)
    logger.setLevel(log_level)
    logger.propagate = False  # avoid duplicate logs if root also has handlers

    # Common formatter
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s - %(message)s"
    )

    # Console handler (always useful)
    ch = logging.StreamHandler()
    ch.setLevel(log_level)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    if log_to_file:
        _ensure_dir(log_file)

        if rotate_mode == "time":
            # Time-based rotation, with timestamped filenames
            fh = logging.handlers.TimedRotatingFileHandler(
                log_file, when=when, interval=interval, backupCount=backup_count, encoding="utf-8"
            )
            # Add timestamp suffix to rolled files
            # e.g., guardian.log.2025-08-20_23-59-59
            fh.suffix = "%Y-%m-%d_%H-%M-%S"
        else:
            # Size-based rotation
            fh = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
            )
            # Add timestamp to rotated files instead of .1, .2, ...
            # Use namer/rotator hooks to rename on rollover
            def namer(default_name: str) -> str:
                # default_name looks like "guardian.log.1"
                base, ext = os.path.splitext(log_file)  # "guardian", ".log"
                ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                return f"{base}.{ts}{ext}"

            def rotator(source: str, dest: str):
                # Replace default rotate behavior with our timestamped scheme
                # source is current log path, dest is default target; we ignore dest
                ts_path = namer(dest)
                try:
                    if os.path.exists(ts_path):
                        os.remove(ts_path)
                except FileNotFoundError:
                    pass
                os.replace(source, ts_path)

            fh.namer = namer
            fh.rotator = rotator

        fh.setLevel(log_level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    return logger
