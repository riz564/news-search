from abc import ABC, abstractmethod

class NewsProvider(ABC):
    @abstractmethod
    def fetch(self, query, page, page_size, offline):
        pass
