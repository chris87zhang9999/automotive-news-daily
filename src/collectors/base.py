import logging
from abc import ABC, abstractmethod
from src.schemas import NewsItem

logger = logging.getLogger(__name__)

class BaseCollector(ABC):
    name: str = "base"

    @abstractmethod
    def collect(self) -> list[NewsItem]:
        ...
