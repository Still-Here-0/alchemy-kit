from logging import Logger
from typing import Optional


class BetterLogger:

    def __init__(self, logger: Optional[Logger]) -> None:
        self.logger = logger

