
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, MutableMapping

import aiorun
import tomli

from . import loader, log

def load_config(path: str = "config.toml") -> MutableMapping[str, Any]:
    cfg_path = Path(path)
    if not cfg_path.is_file():
        raise FileNotFoundError(f"Config file not found: {cfg_path}")
    with cfg_path.open("rb") as f:
        return tomli.load(f)



def main() -> None:
    """Main entry point for the Zyra bot launcher."""
    config = load_config()
    if config:
        log.setup_log(config["bot"]["colorlog"] if config else False)
        logs = logging.getLogger("Loader")
        logs.info("Loading code")
    else:
        logs.error(
            "'config.toml' is missing, Configuration must be done before running the bot."
        )
    
    loader.main(config)
    
    
if __name__ == "__main__":
    main()
    