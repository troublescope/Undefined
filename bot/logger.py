import logging
import os
from typing import Optional

try:
    import colorlog
except ImportError:
    colorlog = None

LEVEL = logging.INFO


def setup_log(
    colorlog_enable: bool = False, logfile_path: Optional[str] = "Bot/Bot.log"
) -> None:
    """Configure root logging; silence noisy libs (PTB, httpx, urllib3, etc)."""
    if logfile_path:
        logdir = os.path.dirname(logfile_path)
        if logdir and not os.path.exists(logdir):
            os.makedirs(logdir, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(LEVEL)

    if root.handlers:
        root.handlers.clear()

    # Console handler
    if colorlog_enable and colorlog:
        fmt = colorlog.ColoredFormatter(
            "  %(log_color)s%(levelname)-8s%(reset)s  |  "
            "%(name)-11s  |  %(log_color)s%(message)s%(reset)s"
        )
    else:
        fmt = logging.Formatter("  %(levelname)-8s  |  %(name)-11s  |  %(message)s")

    sh = logging.StreamHandler()
    sh.setLevel(LEVEL)
    sh.setFormatter(fmt)
    root.addHandler(sh)

    # File handler
    if logfile_path:
        fh = logging.FileHandler(logfile_path)
        fh.setLevel(LEVEL)
        fh.setFormatter(
            logging.Formatter(
                "[ %(asctime)s: %(levelname)-8s ] %(name)-15s - %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        root.addHandler(fh)

    # Silence noisy libs
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
