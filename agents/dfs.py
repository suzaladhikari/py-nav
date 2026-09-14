from typing import List, Tuple, Optional
from core.agent import Agent

class DFSAgent(Agent):
    name = 'DFS'

    def find_path(self) -> Optional[List[Tuple[int, int]]]:
        start = self.start
        goal = self.goal
        if not start or not goal:
            return None

        stack = [(start, [start])]
        visited = set([start])

        while stack:
            # pop() returns the last element, so neighbors are explored
            # in reverse order of get_valid_moves() (N last, NW first).
            # This is expected DFS behaviour — the stack is LIFO.
            current, path = stack.pop()

            if current == goal:
                return path

            for move in self.get_valid_moves(current[0], current[1]):
                if move.location not in visited:
                    visited.add(move.location)
                    stack.append((move.location, path + [move.location]))
        return None
