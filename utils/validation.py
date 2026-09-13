import heapq
from typing import Tuple, Optional, List
from core.map import Map

def dijkstra_min_distance(map_obj: Map, start: Tuple[int, int], goal: Tuple[int, int]) -> Optional[float]:
    """Finds the shortest distance from start to goal on the given map using Dijkstra."""
    frontier = []
    heapq.heappush(frontier, (0.0, start))
    cost_so_far = {start: 0.0}

    while frontier:
        current_cost, current = heapq.heappop(frontier)

        if current == goal:
            return current_cost

        for move in map_obj.get_valid_moves(current[0], current[1]):
            new_cost = cost_so_far[current] + move.cost
            if move.location not in cost_so_far or new_cost < cost_so_far[move.location]:
                cost_so_far[move.location] = new_cost
                heapq.heappush(frontier, (new_cost, move.location))

    return None

def validate_min_distance(map_obj: Map, allowed_starts: List[Tuple[int, int]], allowed_goals: List[Tuple[int, int]]) -> bool:
    """Checks if there is at least one start-goal pair that satisfies the min_distance constraint."""
    min_dist = map_obj.min_distance
    for s in allowed_starts:
        for g in allowed_goals:
            if s == g:
                continue
            dist = dijkstra_min_distance(map_obj, s, g)
            if dist is not None and dist >= min_dist:
                return True
    return False
