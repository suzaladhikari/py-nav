import unittest

from agents.dijkstra import DijkstraAgent
from core.map import Map


def path_cost(map_obj, path):
    total = 0.0
    for current, target in zip(path, path[1:]):
        move = next(move for move in map_obj.get_valid_moves(*current)
                    if move.location == target)
        total += move.cost
    return total


class DijkstraTests(unittest.TestCase):
    def test_finds_lower_cost_path_in_weighted_map(self):
        grid = [list('-----'), list('-###-'), list('-----')]
        map_obj = Map(grid, diagonal_moves=False)
        map_obj.set_start_goal((0, 1), (4, 1))

        path = DijkstraAgent(map_obj).run()

        self.assertEqual(path[0], (0, 1))
        self.assertEqual(path[-1], (4, 1))
        self.assertEqual(path_cost(map_obj, path), 6.0)

    def test_returns_none_when_goal_is_unreachable(self):
        grid = [list('---'), list('###'), list('---')]
        map_obj = Map(grid, diagonal_moves=False)
        map_obj.set_start_goal((0, 0), (2, 2))

        self.assertIsNone(DijkstraAgent(map_obj).run())

    def test_supports_teleport_exit_with_step_cost(self):
        grid = [list('-A--'), list('----'), list('--A-')]
        map_obj = Map(grid, diagonal_moves=False)
        map_obj.set_start_goal((0, 0), (3, 2))

        path = DijkstraAgent(map_obj).run()

        self.assertEqual(path[0], (0, 0))
        self.assertEqual(path[-1], (3, 2))
        self.assertEqual(path_cost(map_obj, path), 2.0)


if __name__ == '__main__':
    unittest.main()
