import unittest

from core.map import Map
from utils.validation import dijkstra_min_distance, validate_min_distance


class ValidationTests(unittest.TestCase):
    def test_dijkstra_min_distance_returns_shortest_cost(self):
        map_obj = Map([list('--'), list('--')], diagonal_moves=True,
                      diagonal_move_true_cost=True)

        distance = dijkstra_min_distance(map_obj, (0, 0), (1, 1))

        self.assertAlmostEqual(distance, 2 ** 0.5)

    def test_dijkstra_min_distance_returns_none_when_unreachable(self):
        map_obj = Map([list('--'), list('##')], diagonal_moves=False)

        self.assertIsNone(dijkstra_min_distance(map_obj, (0, 0), (1, 1)))

    def test_validate_min_distance_checks_allowed_pairs(self):
        map_obj = Map([list('---'), list('---'), list('---')],
                      diagonal_moves=False, min_distance=3)

        self.assertTrue(validate_min_distance(map_obj, [(0, 0)], [(2, 1)]))

    def test_validate_min_distance_rejects_unsatisfied_constraint(self):
        map_obj = Map([list('---'), list('---')],
                      diagonal_moves=False, min_distance=4)

        self.assertFalse(validate_min_distance(map_obj, [(0, 0)], [(1, 1)]))

    def test_validate_min_distance_skips_same_cell_pair(self):
        map_obj = Map([list('-')], diagonal_moves=False, min_distance=0)

        self.assertFalse(validate_min_distance(map_obj, [(0, 0)], [(0, 0)]))


if __name__ == '__main__':
    unittest.main()
