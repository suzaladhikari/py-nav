from typing import List, Tuple, Optional
from core.map import Map

class Agent:
    name = None

    def __init__(self, map: Map):
        self.map = map
        self._explored = []
        self.start = self.map.get_start()
        self.goal = self.map.get_goal()
        self._exploration_sink = None

    def get_valid_moves(self, x: int, y: int) -> List[Tuple[int, int]]:
        self.mark_explored(x, y)
        return self.map.get_valid_moves(x, y)

    def get_name(self) -> str:
        return getattr(type(self), 'name', None) or type(self).__name__

    def mark_explored(self, x: int, y: int):
        location = (x, y)
        self._explored.append(location)
        if self._exploration_sink is not None:
            self._exploration_sink(location)

    def get_explored(self) -> List[Tuple[int, int]]:
        return self._explored

    def run(self) -> Optional[List[Tuple[int, int]]]:
        try:
            return self.find_path()
        except Exception as e:
            # Re-raise the exception to be handled by the simulation engine
            raise e

    def find_path(self) -> Optional[List[Tuple[int, int]]]:
        raise NotImplementedError("find_path must be implemented by subclasses.")
