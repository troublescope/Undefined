import logging
import os
from typing import Optional

try:
    import colorlog
except Exception:
    colorlog = None

level = logging.INFO


def setup_log(
    colorlog_enable: bool = False, logfile_path: Optional[str] = "Bot/Bot.log"
) -> None:
    """Configure root logging; silence noisy libs (PTB, httpx, urllib3, etc)."""
    # ensure log dir exists
    if logfile_path:
        logdir = os.path.dirname(logfile_path)
        if logdir and not os.path.exists(logdir):
            os.makedirs(logdir, exist_ok=True)

    logging.root.setLevel(level)

    # file handler
    file_fmt = "[ %(asctime)s: %(levelname)-8s ] %(name)-15s - %(message)s"
    fh = None
    if logfile_path:
        fh = logging.FileHandler(logfile_path)
        fh.setLevel(level)
        fh.setFormatter(logging.Formatter(file_fmt, datefmt="%H:%M:%S"))

    # console handler
    if not (colorlog_enable and colorlog):
        stream_fmt = logging.Formatter(
            "  %(levelname)-8s  |  %(name)-11s  |  %(message)s"
        )
    else:
        stream_fmt = colorlog.ColoredFormatter(  # type: ignore[attr-defined]
            "  %(log_color)s%(levelname)-8s%(reset)s  |  "
            "%(name)-11s  |  %(log_color)s%(message)s%(reset)s"
        )

    sh = logging.StreamHandler()
    sh.setLevel(level)
    sh.setFormatter(stream_fmt)

    root = logging.getLogger()
    root.setLevel(level)
    # idempotent: clear handlers supaya gak dobel kalau dipanggil ulang
    if root.handlers:
        root.handlers.clear()
    root.addHandler(sh)
    if fh:
        root.addHandler(fh)

    # silence libs (sesuai request)
    logging.getLogger("telegram").setLevel(logging.WARNING)  # PTB core
    logging.getLogger("telegram.ext").setLevel(logging.WARNING)  # PTB ext
    logging.getLogger("apscheduler").setLevel(logging.WARNING)  # dipakai PTB
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
