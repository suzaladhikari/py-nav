import unittest

from agents.astar import AStarAgent
from agents.dijkstra import DijkstraAgent
from core.map import Map


FAILING_GRID = [
    list('-----#'),
    list('-#--##'),
    list('------'),
    list('#---#-'),
    list('#---#-'),
    list('------'),
]


def path_cost(map_obj, path):
    total = 0.0
    for current, target in zip(path, path[1:]):
        move = next(
            move for move in map_obj.get_valid_moves(*current)
            if move.location == target
        )
        total += move.cost
    return total


class AStarTests(unittest.TestCase):
    def run_agents(self, grid, **options):
        astar_map = Map([row[:] for row in grid], **options)
        dijkstra_map = Map([row[:] for row in grid], **options)
        astar_map.set_start_goal((0, 0), (5, 5))
        dijkstra_map.set_start_goal((0, 0), (5, 5))
        astar_path = AStarAgent(astar_map).run()
        dijkstra_path = DijkstraAgent(dijkstra_map).run()
        return astar_map, astar_path, dijkstra_path, dijkstra_map

    def test_uses_euclidean_heuristic(self):
        map_obj = Map([list('---'), list('---'), list('---')])
        agent = AStarAgent(map_obj)

        self.assertAlmostEqual(agent.heuristic((0, 0), (2, 1)), 5 ** 0.5)

    def test_astar_avoids_walls(self):
        grid = [
            list('-----'),
            list('--#--'),
            list('--#--'),
            list('--#--'),
            list('-----'),
        ]
        map_obj = Map(grid, diagonal_moves=False)
        map_obj.set_start_goal((0, 2), (4, 2))
        path = AStarAgent(map_obj).run()

        self.assertIsNotNone(path)
        self.assertTrue(all(not map_obj.is_wall(x, y) for x, y in path))
        self.assertEqual(path[0], (0, 2))
        self.assertEqual(path[-1], (4, 2))

    def test_exploration_history_contains_expanded_nodes(self):
        map_obj = Map([list('---'), list('---'), list('---')], diagonal_moves=False)
        map_obj.set_start_goal((0, 0), (1, 0))
        agent = AStarAgent(map_obj)

        self.assertEqual(agent.run(), [(0, 0), (1, 0)])
        self.assertEqual(agent.get_explored(), [(0, 0)])

    def test_astar_finds_diagonal_shortest_path(self):
        grid = [list('---'), list('---'), list('---')]
        map_obj = Map(grid, diagonal_moves=True, diagonal_move_true_cost=True)
        map_obj.set_start_goal((0, 0), (2, 2))
        path = AStarAgent(map_obj).run()

        self.assertEqual(path, [(0, 0), (1, 1), (2, 2)])
        self.assertAlmostEqual(path_cost(map_obj, path), 2 * (2 ** 0.5))

    def test_heuristic_ignores_wraparound(self):
        map_obj = Map([list('---'), list('---'), list('---')], wrap=True)
        agent = AStarAgent(map_obj)

        self.assertAlmostEqual(agent.heuristic((0, 0), (2, 0)), 2.0)

    def test_heuristic_ignores_teleports(self):
        map_obj = Map([list('-A-'), list('---'), list('-A-')])
        agent = AStarAgent(map_obj)

        self.assertAlmostEqual(agent.heuristic((0, 0), (2, 2)), 8 ** 0.5)


if __name__ == '__main__':
    unittest.main()
