import heapq
from typing import List, Tuple, Optional
from core.agent import Agent

class AStarAgent(Agent):
    name = 'A* (dumb)'

    def heuristic(self, a: Tuple[int, int], b: Tuple[int, int]) -> float:
        return 1

    def find_path(self) -> Optional[List[Tuple[int, int]]]:
        start = self.start
        goal = self.goal
        if not start or not goal:
            return None

        counter = 0
        start_g_cost = 0.0
        start_f_cost = start_g_cost + self.heuristic(start, goal)
        # Queue entries are ordered by f = g + h, while retaining g for stale-entry checks.
        frontier = [(start_f_cost, counter, start_g_cost, start)]
        cost_so_far = {start: start_g_cost}
        came_from = {start: None}

        while frontier:
            _, _, current_g_cost, current = heapq.heappop(frontier)
            if current_g_cost != cost_so_far[current]:
                continue

            if current == goal:
                path = []
                curr = goal
                while curr is not None:
                    path.append(curr)
                    curr = came_from[curr]
                path.reverse()
                return path

            for move in self.get_valid_moves(current[0], current[1]):
                tentative_g_cost = current_g_cost + move.cost
                if (move.location not in cost_so_far or
                        tentative_g_cost < cost_so_far[move.location]):
                    cost_so_far[move.location] = tentative_g_cost
                    came_from[move.location] = current
                    f_cost = tentative_g_cost + self.heuristic(move.location, goal)
                    counter += 1
                    heapq.heappush(
                        frontier, (f_cost, counter, tentative_g_cost, move.location)
                    )

        return None
