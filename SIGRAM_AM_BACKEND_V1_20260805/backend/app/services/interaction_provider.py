from abc import ABC, abstractmethod
from typing import List, Dict, Any

class InteractionProvider(ABC):
    @abstractmethod
    def find_interactions(self, normalized_medications: List[str]) -> List[Dict[str, Any]]:
        """Recibe una lista de principios activos normalizados y devuelve una lista de resultados de interacción.

        No debe consultar bases externas.
        """
        pass
