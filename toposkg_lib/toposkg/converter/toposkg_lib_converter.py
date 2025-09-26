from abc import ABC, abstractmethod

class GenericConverter(ABC):
    @abstractmethod
    def parse(self):
        pass

    @abstractmethod
    def export(self):
        pass