import unittest

from core.map import Map
from ui.map_editor import MapEditor


class MapEditorTeleportTests(unittest.TestCase):
    def test_replacing_existing_gate_removes_provisional_pair_before_allocating(self):
        editor = MapEditor.__new__(MapEditor)
        editor.map_obj = Map([
            list('A--B-C'),
            list('-------'),
            list('A--B--'),
        ])
        editor.next_tp_id = 'D'
        editor.tp_state = 1
        editor.first_tp_pos = (5, 0)

        editor.remove_tp_pair('B')
        editor.map_obj.map[0][5] = '-'
        editor.tp_state = 0
        editor.first_tp_pos = None
        editor._refresh_next_tp_id()

        self.assertEqual(editor.map_obj.map[0], list('A-----'))
        self.assertEqual(editor.map_obj.map[2], list('A-----'))
        self.assertEqual(editor.next_tp_id, 'B')

    def test_deleting_unlinked_next_pair_keeps_next_id_after_existing_pairs(self):
        editor = MapEditor.__new__(MapEditor)
        editor.map_obj = Map([
            list('A---B'),
            list('-----'),
            list('A---B'),
        ])
        editor.next_tp_id = 'C'

        editor.remove_tp_pair('B')

        self.assertEqual(editor.map_obj.map[0], list('A----'))
        self.assertEqual(editor.map_obj.map[2], list('A----'))
        self.assertEqual(editor.next_tp_id, 'B')

    def test_next_id_is_derived_from_grid_after_reindexing(self):
        editor = MapEditor.__new__(MapEditor)
        editor.map_obj = Map([
            list('A---B---C'),
            list('----------'),
            list('A---B---C'),
        ])
        editor.next_tp_id = 'D'

        editor.remove_tp_pair('B')

        self.assertEqual(editor.next_tp_id, 'C')
        self.assertEqual(editor.map_obj.map[0], list('A-------B'))
        self.assertEqual(editor.map_obj.map[2], list('A-------B'))


if __name__ == '__main__':
    unittest.main()
