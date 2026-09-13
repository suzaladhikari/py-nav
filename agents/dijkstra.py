import heapq
from typing import List, Tuple, Optional
from core.agent import Agent

class DijkstraAgent(Agent):
    name = 'Dijkstra'

    def find_path(self) -> Optional[List[Tuple[int, int]]]:
        start = self.start
        goal = self.goal
        if not start or not goal:
            return None

        cost_so_far = {start: 0.0}
        came_from = {start: None}

        counter = 0
        frontier = [(0.0, counter, start)]

        while frontier:
            current_cost, _, current = heapq.heappop(frontier)

            if current == goal:
                path = []
                curr = goal
                while curr is not None:
                    path.append(curr)
                    curr = came_from[curr]
                path.reverse()
                return path

            for move in self.get_valid_moves(current[0], current[1]):
                new_cost = cost_so_far[current] + move.cost
                if move.location not in cost_so_far or new_cost < cost_so_far[move.location]:
                    cost_so_far[move.location] = new_cost
                    came_from[move.location] = current
                    counter += 1
                    heapq.heappush(frontier, (new_cost, counter, move.location))

        return None
