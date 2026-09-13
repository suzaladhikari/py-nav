import unittest

from core.map import Map
from core.constants import DIAGONAL_COST


class MapTests(unittest.TestCase):
    def test_walls_are_not_valid_moves(self):
        map_obj = Map([list('-#-'), list('---'), list('---')], diagonal_moves=False)

        locations = {move.location for move in map_obj.get_valid_moves(0, 0)}

        self.assertNotIn((1, 0), locations)
        self.assertIn((0, 1), locations)

    def test_diagonal_is_blocked_by_two_adjacent_walls(self):
        map_obj = Map([list('-#'), list('#-')], diagonal_moves=True)

        locations = {move.location for move in map_obj.get_valid_moves(0, 0)}

        self.assertNotIn((1, 1), locations)

    def test_diagonal_cost_matches_configuration(self):
        true_cost_map = Map([list('--'), list('--')], diagonal_moves=True,
                            diagonal_move_true_cost=True)
        unit_cost_map = Map([list('--'), list('--')], diagonal_moves=True,
                            diagonal_move_true_cost=False)

        true_move = next(move for move in true_cost_map.get_valid_moves(0, 0)
                          if move.location == (1, 1))
        unit_move = next(move for move in unit_cost_map.get_valid_moves(0, 0)
                         if move.location == (1, 1))

        self.assertAlmostEqual(true_move.cost, DIAGONAL_COST)
        self.assertEqual(unit_move.cost, 1.0)

    def test_wrap_moves_across_edges(self):
        map_obj = Map([list('---'), list('---'), list('---')], wrap=True,
                      diagonal_moves=False)

        locations = {move.location for move in map_obj.get_valid_moves(0, 0)}

        self.assertIn((2, 0), locations)
        self.assertIn((0, 2), locations)

    def test_teleport_move_lands_at_paired_exit(self):
        map_obj = Map([list('-A-'), list('---'), list('-A-')],
                      diagonal_moves=False)

        move = next(move for move in map_obj.get_valid_moves(0, 0)
                    if move.location == (0, 1))
        teleport_move = next(move for move in map_obj.get_valid_moves(0, 0)
                             if move.location == (1, 2))

        self.assertEqual(move.cost, 1.0)
        self.assertEqual(teleport_move.cost, 1.0)

    def test_teleport_destination_is_bidirectional(self):
        map_obj = Map([list('-A-'), list('---'), list('-A-')],
                      diagonal_moves=False)

        self.assertEqual(map_obj.get_teleport_destination(1, 0), (1, 2))
        self.assertEqual(map_obj.get_teleport_destination(1, 2), (1, 0))


if __name__ == '__main__':
    unittest.main()
