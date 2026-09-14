import os
import tempfile
import unittest

from core.map import Map
from utils.yaml_handler import load_map, save_map


class YamlHandlerTests(unittest.TestCase):
    def test_save_and_load_preserves_map_configuration(self):
        map_obj = Map([list('@-#'), list('-!-')], wrap=True,
                      diagonal_moves=False, diagonal_move_true_cost=False,
                      min_distance=7)

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'round_trip.yaml')
            save_map(path, map_obj, validated=True)
            loaded = load_map(path)

        self.assertEqual(loaded['map'], [['@', '-', '#'], ['-', '!', '-']])
        self.assertTrue(loaded['wrap'])
        self.assertFalse(loaded['diagonal_moves'])
        self.assertFalse(loaded['diagonal_move_true_cost'])
        self.assertEqual(loaded['min_distance'], 7)
        self.assertTrue(loaded['validated'])

    def test_missing_file_returns_empty_data(self):
        self.assertEqual(load_map('does-not-exist.yaml'), {})


if __name__ == '__main__':
    unittest.main()
