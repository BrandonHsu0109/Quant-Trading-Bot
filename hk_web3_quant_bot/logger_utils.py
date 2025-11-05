import logging
import os
import config

def setup_logging():
    os.makedirs(os.path.dirname(config.LOG_FILE), exist_ok=True)
    logging.basicConfig(
        filename=config.LOG_FILE,
        level=getattr(logging, config.LOG_LEVEL),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    console = logging.StreamHandler()
    console.setLevel(getattr(logging, config.LOG_LEVEL))
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    console.setFormatter(formatter)
    logging.getLogger("").addHandler(console)