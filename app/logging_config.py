"""Central logging setup. Call configure_logging() once, at app startup."""

import logging

def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logging.getLogger("urllib3").setLevel(logging.WARNING)
