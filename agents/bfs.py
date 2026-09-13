from collections import deque
from typing import List, Tuple, Optional
from core.agent import Agent

import time, random


class BFSAgent(Agent):
    name = 'BFS'

    def find_path(self) -> Optional[List[Tuple[int, int]]]:
        start = self.start
        goal = self.goal
        if not start or not goal:
            return None

        queue = deque([(start, [start])])
        visited = set([start])

        while queue:
            current, path = queue.popleft()

            if current == goal:
                return path

            for move in self.get_valid_moves(current[0], current[1]):
                # time.sleep(0.01)
                # if random.random()<0.05: raise Exception()
                if move.location not in visited:
                    visited.add(move.location)
                    queue.append((move.location, path + [move.location]))
        return None
