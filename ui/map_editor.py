import pygame
import pygame_gui
import os
import glob
from core.constants import *
from core.map import Map
from utils.yaml_handler import save_map, load_map
from utils.session_state import load_session_state, save_session_state
from ui.help_dialog import HelpOverlay

# ── Layout constants ─────────────────────────────────────────────────────────
SIDEBAR_W = 330          # width of left sidebar
SCREEN_W  = 1200
SCREEN_H  = 768
MAP_AREA_X = SIDEBAR_W   # map starts here
MAP_AREA_W = SCREEN_W - SIDEBAR_W
MAP_AREA_H = SCREEN_H

MIN_GRID = 5
MAX_GRID = 20


def compute_tile_size(w, h):
    """Return the largest tile size that fits the map in the drawable area."""
    ts_w = MAP_AREA_W // w
    ts_h = MAP_AREA_H // h
    return max(4, min(ts_w, ts_h, 60))   # cap at 60, floor at 4


class MapEditor:
    selected_map_name = None

    def __init__(self, screen, manager):
        self.screen  = screen
        self.manager = manager
        self.font         = pygame.font.SysFont(None, 22)
        self.warning_font = pygame.font.SysFont(None, 28)
        self.session_state = load_session_state()
        editor_state = self.session_state.get('editor', {})

        # ── File management ───────────────────────────────────────────────
        self.map_files        = []
        self.current_file_idx = -1
        self.temporary_name   = editor_state.get('temporary_name')
        os.makedirs("maps", exist_ok=True)
        self.refresh_file_list()
        if self.map_files:
            preferred = (
                self.session_state.get('selected_map_name')
                or editor_state.get('selected_map_name')
                or self.selected_map_name
            )
            self.current_file_idx = (
                self.map_files.index(preferred)
                if preferred in self.map_files else 0
            )
            MapEditor.selected_map_name = self.map_files[self.current_file_idx]
        else:
            self.current_file_idx = -1
            MapEditor.selected_map_name = None

        # ── Map state ─────────────────────────────────────────────────────
        self.map_obj = Map(
            [['-' for _ in range(DEFAULT_GRID_WIDTH)]
             for _ in range(DEFAULT_GRID_HEIGHT)]
        )
        self.tile_size = compute_tile_size(
            self.map_obj.width, self.map_obj.height
        )

        self.tools        = ['Empty', 'Wall', 'Start', 'Goal', 'Teleport']
        self.current_tool = 'Empty'
        self.tp_state     = 0
        self.next_tp_id   = 'A'
        self.first_tp_pos = None

        self.is_dragging        = False
        self.last_modified_cell = None
        self.drag_mode          = 'draw'

        self.warning_msg  = ""
        self.warning_time = 0

        # Dirty flag – tracks unsaved changes
        self.dirty = False

        # Pending action while waiting for unsaved-changes dialog
        self._pending_action    = None   # ('select', idx) | ('new',) | ('sim',)
        self.unsaved_panel      = None   # custom 3-button dialog panel
        self.unsaved_btn_save   = None
        self.unsaved_btn_discard = None
        self.unsaved_btn_cancel = None
        self.confirm_dialog     = None   # for delete
        self.help_overlay       = None

        # ── Build UI ──────────────────────────────────────────────────────
        self._build_ui()
        self.load_current_map()
        self._restore_editor_state(editor_state)

    # ═══════════════════════════════════════════════════════════════════════
    # UI construction
    # ═══════════════════════════════════════════════════════════════════════

    def _build_ui(self):
        sx = 10            # sidebar left padding
        sw = SIDEBAR_W - 20  # usable width

        y = 10

        self.btn_edit = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((sx, y), (sw // 2 - 3, 30)),
            text="Edit Map", manager=self.manager
        )
        self.btn_edit.select()
        self.btn_run = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((sx + sw // 2 + 3, y), (sw // 2 - 3, 30)),
            text="Run Agents", manager=self.manager
        )
        y += 40

        # ── Map selector dropdown ─────────────────────────────────────────
        pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect((sx, y), (sw, 24)),
            text="Map:", manager=self.manager
        )
        y += 26
        self.dropdown_map = None
        self._dropdown_y = y
        self.refresh_dropdown()
        y += 36

        # ── Map name input ────────────────────────────────────────────────
        pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect((sx, y), (sw, 24)),
            text="Name:", manager=self.manager
        )
        y += 26
        self.name_input = pygame_gui.elements.UITextEntryLine(
            relative_rect=pygame.Rect((sx, y), (sw, 30)),
            manager=self.manager
        )
        y += 36

        # ── Dup / Del buttons under name ──────────────────────────────────
        half = (sw - 6) // 2
        self.btn_dup = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((sx, y), (half, 30)),
            text="Duplicate", manager=self.manager
        )
        self.btn_del = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((sx + half + 6, y), (half, 30)),
            text="Delete", manager=self.manager
        )
        y += 40

        # ── Grid size ─────────────────────────────────────────────────────
        pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect((sx, y), (sw, 24)),
            text="--- Grid Size ---", manager=self.manager
        )
        y += 28

        lbl_w = 24   # "W:" prefix label width
        bw    = 28   # +/- button width
        val_w = sw - lbl_w - 2 * bw - 8

        # Width row
        pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect((sx, y), (lbl_w, 30)),
            text="W:", manager=self.manager
        )
        self.btn_w_minus = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((sx + lbl_w, y), (bw, 30)),
            text="-", manager=self.manager
        )
        self.lbl_width = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect((sx + lbl_w + bw + 2, y), (val_w, 30)),
            text=str(self.map_obj.width), manager=self.manager
        )
        self.btn_w_plus = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((sx + lbl_w + bw + 2 + val_w + 2, y), (bw, 30)),
            text="+", manager=self.manager
        )
        y += 36

        # Height row
        pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect((sx, y), (lbl_w, 30)),
            text="H:", manager=self.manager
        )
        self.btn_h_minus = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((sx + lbl_w, y), (bw, 30)),
            text="-", manager=self.manager
        )
        self.lbl_height = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect((sx + lbl_w + bw + 2, y), (val_w, 30)),
            text=str(self.map_obj.height), manager=self.manager
        )
        self.btn_h_plus = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((sx + lbl_w + bw + 2 + val_w + 2, y), (bw, 30)),
            text="+", manager=self.manager
        )
        y += 40

        # ── Drawing tools ─────────────────────────────────────────────────
        pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect((sx, y), (sw, 24)),
            text="--- Drawing Tool ---", manager=self.manager
        )
        y += 28

        self.tool_btns = {}
        for tool in self.tools:
            b = pygame_gui.elements.UIButton(
                relative_rect=pygame.Rect((sx, y), (sw, 32)),
                text=tool, manager=self.manager
            )
            self.tool_btns[tool] = b
            if tool == self.current_tool:
                b.select()
            y += 36

        y += 4

        # ── Map options ───────────────────────────────────────────────────
        pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect((sx, y), (sw, 24)),
            text="--- Map Options ---", manager=self.manager
        )
        y += 28

        self.btn_wrap = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((sx, y), (sw, 30)), text="", manager=self.manager
        )
        y += 36
        self.btn_diag = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((sx, y), (sw, 30)), text="", manager=self.manager
        )
        y += 36
        self.btn_diag_cost = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((sx, y), (sw, 30)), text="", manager=self.manager
        )
        y += 40

        # Min distance row: [−] [label] [+]
        dist_bw  = 30
        dist_mid = sw - 2 * dist_bw - 4
        self.btn_dist_minus = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((sx, y), (dist_bw, 30)),
            text="-", manager=self.manager
        )
        self.lbl_dist = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect((sx + dist_bw + 2, y), (dist_mid, 30)),
            text="", manager=self.manager
        )
        self.btn_dist_plus = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((sx + dist_bw + 2 + dist_mid + 2, y), (dist_bw, 30)),
            text="+", manager=self.manager
        )
        y += 44

        # ── Save button ───────────────────────────────────────────────────
        self.btn_save = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((sx, y), (sw, 36)),
            text="Save Map", manager=self.manager
        )
        self.btn_help = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((SCREEN_W - 82, SCREEN_H - 40), (72, 30)),
            text="Help", manager=self.manager
        )

    # ═══════════════════════════════════════════════════════════════════════
    # File / dropdown helpers
    # ═══════════════════════════════════════════════════════════════════════

    def refresh_file_list(self):
        files = glob.glob("maps/*.yaml")
        self.map_files = [
            os.path.basename(f).replace('.yaml', '') for f in sorted(files)
        ]

    def get_current_name(self):
        if 0 <= self.current_file_idx < len(self.map_files):
            return self.map_files[self.current_file_idx]
        return self.temporary_name or "new_map"

    def refresh_dropdown(self):
        if self.dropdown_map:
            self.dropdown_map.kill()
        options = ["Select Map...", "+ Create New Map"] + self.map_files
        self.dropdown_map = pygame_gui.elements.UIDropDownMenu(
            options_list=options,
            starting_option=(self.get_current_name()
                             if self.get_current_name() in self.map_files
                             else "Select Map..."),
            relative_rect=pygame.Rect((10, self._dropdown_y), (SIDEBAR_W - 20, 30)),
            manager=self.manager
        )

    # ═══════════════════════════════════════════════════════════════════════
    # Map loading / saving
    # ═══════════════════════════════════════════════════════════════════════

    def load_current_map(self):
        name     = self.get_current_name()
        filepath = f"maps/{name}.yaml"
        data     = load_map(filepath)

        if data:
            self.map_obj.map                     = data['map']
            self.map_obj.wrap                    = data['wrap']
            self.map_obj.diagonal_moves          = data['diagonal_moves']
            self.map_obj.diagonal_move_true_cost = data['diagonal_move_true_cost']
            self.map_obj.min_distance            = data['min_distance']
            self.map_obj.height = len(self.map_obj.map)
            self.map_obj.width  = (
                len(self.map_obj.map[0]) if self.map_obj.height else DEFAULT_GRID_WIDTH
            )

            max_tp = '@'
            for row in self.map_obj.map:
                for cell in row:
                    if cell.isalpha() and cell.isupper() and cell not in ['s', 'g', 'x']:
                        if cell > max_tp:
                            max_tp = cell
            self.next_tp_id = chr(ord(max_tp) + 1) if max_tp >= 'A' else 'A'
        else:
            self.map_obj.map    = [
                ['-' for _ in range(DEFAULT_GRID_WIDTH)]
                for _ in range(DEFAULT_GRID_HEIGHT)
            ]
            self.map_obj.width  = DEFAULT_GRID_WIDTH
            self.map_obj.height = DEFAULT_GRID_HEIGHT
            self.next_tp_id     = 'A'

        self.tile_size = compute_tile_size(self.map_obj.width, self.map_obj.height)
        self.name_input.set_text(name)
        self.lbl_width.set_text(str(self.map_obj.width))
        self.lbl_height.set_text(str(self.map_obj.height))
        self.update_option_buttons()
        MapEditor.selected_map_name = name if self.current_file_idx >= 0 else None
        self.dirty = False

    def _restore_editor_state(self, state):
        if not state:
            return
        state_name = state.get('selected_map_name') or state.get('name')
        # Saved YAML is authoritative. Only restore map content for an
        # unsaved temporary map; existing maps may have changed on disk.
        if state.get('map') and self.current_file_idx < 0 and self.temporary_name:
            self.map_obj.map = state['map']
            self.map_obj.height = len(self.map_obj.map)
            self.map_obj.width = len(self.map_obj.map[0]) if self.map_obj.map else DEFAULT_GRID_WIDTH
            self.map_obj.wrap = state.get('wrap', False)
            self.map_obj.diagonal_moves = state.get('diagonal_moves', True)
            self.map_obj.diagonal_move_true_cost = state.get('diagonal_move_true_cost', True)
            self.map_obj.min_distance = state.get('min_distance', 0)
            self.tile_size = compute_tile_size(self.map_obj.width, self.map_obj.height)
            self.name_input.set_text(self.temporary_name or state.get('name', self.get_current_name()))
            self.lbl_width.set_text(str(self.map_obj.width))
            self.lbl_height.set_text(str(self.map_obj.height))
            self.update_option_buttons()
            self.dirty = state.get('dirty', True)
        tool = state.get('current_tool')
        if tool in self.tool_btns:
            for name, button in self.tool_btns.items():
                button.select() if name == tool else button.unselect()
            self.current_tool = tool

    def _save_session(self, active_view='editor'):
        self.session_state['active_view'] = active_view
        if self.current_file_idx >= 0:
            self.session_state['selected_map_name'] = self.get_current_name()
        self.session_state['editor'] = {
            'selected_map_name': self.get_current_name() if self.current_file_idx >= 0 else None,
            'temporary_name': self.temporary_name,
            'name': self.name_input.get_text(),
            'map': self.map_obj.map,
            'wrap': self.map_obj.wrap,
            'diagonal_moves': self.map_obj.diagonal_moves,
            'diagonal_move_true_cost': self.map_obj.diagonal_move_true_cost,
            'min_distance': self.map_obj.min_distance,
            'current_tool': self.current_tool,
            'dirty': self.dirty,
        }
        save_session_state(self.session_state)

    def save_current_map(self):
        """Save map; returns True on success, False on name-conflict error."""
        new_name = self.name_input.get_text().strip()
        if not new_name:
            new_name = "map"
            self.name_input.set_text(new_name)

        old_name = self.get_current_name()
        is_temporary = self.current_file_idx < 0

        if new_name != old_name:
            # Guard: target name already exists as a DIFFERENT map entry
            if (new_name in self.map_files and
                    self.map_files.index(new_name) != self.current_file_idx):
                self._show_warning(
                    f"Name '{new_name}' already exists. Please choose a different name."
                )
                return False

            old_path = f"maps/{old_name}.yaml"
            new_path = f"maps/{new_name}.yaml"
            if not is_temporary and os.path.exists(old_path):
                os.rename(old_path, new_path)

            if not is_temporary:
                self.map_files[self.current_file_idx] = new_name

        if is_temporary:
            self.map_files.append(new_name)
            self.current_file_idx = len(self.map_files) - 1
            self.temporary_name = None

        filepath = f"maps/{new_name}.yaml"
        save_map(filepath, self.map_obj, False)

        self._show_warning(f"Saved: {new_name}")
        self.refresh_dropdown()
        MapEditor.selected_map_name = new_name
        self.dirty = False
        return True

    def _create_new_map(self):
        number = 1
        while f"Map {number:02d}" in self.map_files:
            number += 1
        self.current_file_idx = -1
        self.temporary_name = f"Map {number:02d}"
        self.map_obj.map = [
            ['-' for _ in range(DEFAULT_GRID_WIDTH)]
            for _ in range(DEFAULT_GRID_HEIGHT)
        ]
        self.map_obj.width = DEFAULT_GRID_WIDTH
        self.map_obj.height = DEFAULT_GRID_HEIGHT
        self.map_obj.wrap = False
        self.map_obj.diagonal_moves = True
        self.map_obj.diagonal_move_true_cost = True
        self.map_obj.min_distance = 0
        self.next_tp_id = 'A'
        self.tp_state = 0
        self.first_tp_pos = None
        self.current_tool = 'Empty'
        for tool, button in self.tool_btns.items():
            button.select() if tool == 'Empty' else button.unselect()
        self.tile_size = compute_tile_size(DEFAULT_GRID_WIDTH, DEFAULT_GRID_HEIGHT)
        self.name_input.set_text(self.temporary_name)
        self.lbl_width.set_text(str(DEFAULT_GRID_WIDTH))
        self.lbl_height.set_text(str(DEFAULT_GRID_HEIGHT))
        self.update_option_buttons()
        self.refresh_dropdown()
        self.dirty = True

    # ═══════════════════════════════════════════════════════════════════════
    # Option button labels
    # ═══════════════════════════════════════════════════════════════════════

    def update_option_buttons(self):
        self.btn_wrap.set_text(
            f"Wrap: {'Yes' if self.map_obj.wrap else 'No'}"
        )
        self.btn_diag.set_text(
            f"Diagonals: {'Yes' if self.map_obj.diagonal_moves else 'No'}"
        )
        if self.map_obj.diagonal_moves:
            cost_val = "1.414" if self.map_obj.diagonal_move_true_cost else "1.0"
            self.btn_diag_cost.set_text(f"Diag cost: {cost_val}")
            self.btn_diag_cost.enable()
        else:
            self.btn_diag_cost.set_text("Diag cost: N/A")
            self.btn_diag_cost.disable()
        self.lbl_dist.set_text(f"Min dist: {self.map_obj.min_distance}")

    # ═══════════════════════════════════════════════════════════════════════
    # Grid-size helpers
    # ═══════════════════════════════════════════════════════════════════════

    def _resize_grid(self, new_w, new_h):
        """Resize map grid; crop or pad with '-'. Clean up orphaned TP pairs."""
        old_map = self.map_obj.map
        old_h   = self.map_obj.height
        old_w   = self.map_obj.width

        new_map = []
        for ry in range(new_h):
            if ry < old_h:
                row = list(old_map[ry])
                if new_w > old_w:
                    row += ['-'] * (new_w - old_w)
                else:
                    row = row[:new_w]
            else:
                row = ['-'] * new_w
            new_map.append(row)

        # Remove any TP whose partner was cropped out
        tp_counts = {}
        for row in new_map:
            for cell in row:
                if cell.isalpha() and cell.isupper() and cell not in ['s', 'g', 'x']:
                    tp_counts[cell] = tp_counts.get(cell, 0) + 1
        for cell, cnt in tp_counts.items():
            if cnt != 2:
                for row in new_map:
                    for xi in range(len(row)):
                        if row[xi] == cell:
                            row[xi] = '-'

        # Re-index TPs to be contiguous A, B, C ...
        existing_ids = sorted(set(
            cell for row in new_map for cell in row
            if cell.isalpha() and cell.isupper() and cell not in ['s', 'g', 'x']
        ))
        remap = {old: chr(ord('A') + i) for i, old in enumerate(existing_ids)}
        for row in new_map:
            for xi in range(len(row)):
                if row[xi] in remap:
                    row[xi] = remap[row[xi]]

        self.map_obj.map    = new_map
        self.map_obj.width  = new_w
        self.map_obj.height = new_h
        self.next_tp_id     = chr(ord('A') + len(existing_ids))
        self.tile_size      = compute_tile_size(new_w, new_h)
        self.lbl_width.set_text(str(new_w))
        self.lbl_height.set_text(str(new_h))
        self.dirty = True

    # ═══════════════════════════════════════════════════════════════════════
    # Unsaved-changes guard
    # ═══════════════════════════════════════════════════════════════════════

    def _check_unsaved(self, pending_action):
        """If dirty, show 3-button panel. Returns True to pause caller."""
        if not self.dirty:
            return False
        self._pending_action = pending_action

        pw, ph = 380, 150
        px     = (SCREEN_W - pw) // 2
        py     = (SCREEN_H - ph) // 2

        self.unsaved_panel = pygame_gui.elements.UIPanel(
            relative_rect=pygame.Rect((px, py), (pw, ph)),
            manager=self.manager
        )
        pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect((10, 8), (pw - 20, 52)),
            text="You have unsaved changes.",
            manager=self.manager,
            container=self.unsaved_panel
        )
        btn_y, btn_h = 70, 38
        bw1, bw2, bw3 = 110, 130, 90
        gap = (pw - bw1 - bw2 - bw3 - 20) // 2
        x1 = 10
        x2 = x1 + bw1 + gap
        x3 = x2 + bw2 + gap
        self.unsaved_btn_save = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((x1, btn_y), (bw1, btn_h)),
            text="Save & Exit",
            manager=self.manager,
            container=self.unsaved_panel
        )
        self.unsaved_btn_discard = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((x2, btn_y), (bw2, btn_h)),
            text="Discard & Exit",
            manager=self.manager,
            container=self.unsaved_panel
        )
        self.unsaved_btn_cancel = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((x3, btn_y), (bw3, btn_h)),
            text="Cancel",
            manager=self.manager,
            container=self.unsaved_panel
        )
        return True

    def _close_unsaved_panel(self):
        if self.unsaved_panel:
            self.unsaved_panel.kill()
            self.unsaved_panel       = None
            self.unsaved_btn_save    = None
            self.unsaved_btn_discard = None
            self.unsaved_btn_cancel  = None

    def _execute_pending(self, did_save):
        """Run the stored pending action after unsaved-changes dialog resolves."""
        action               = self._pending_action
        self._pending_action = None

        if did_save:
            ok = self.save_current_map()
            if not ok:
                return None   # save failed (name clash) – stay put

        if action is None:
            return None
        kind = action[0]

        if kind == 'select':
            self.current_file_idx = action[1]
            self.refresh_dropdown()
            self.load_current_map()
            self._share_selected_map(self.get_current_name())
        elif kind == 'new':
            self._create_new_map()
        elif kind == 'sim':
            from ui.sim_view import SimulationView
            SimulationView.selected_map_name = self.get_current_name()
            return SimulationView

        return None

    # ═══════════════════════════════════════════════════════════════════════
    # Warning helper
    # ═══════════════════════════════════════════════════════════════════════

    def _show_warning(self, msg):
        self.warning_msg  = msg
        self.warning_time = pygame.time.get_ticks()

    # ═══════════════════════════════════════════════════════════════════════
    # Event handling
    # ═══════════════════════════════════════════════════════════════════════

    def handle_event(self, event):
        if self.help_overlay:
            if self.help_overlay.handle_event(event):
                self.help_overlay = None
            return None
        # ── Name input changed → mark dirty ───────────────────────────────
        if event.type == pygame_gui.UI_TEXT_ENTRY_CHANGED:
            if event.ui_element == self.name_input:
                self.dirty = True

        # ── Unsaved-changes 3-button panel ────────────────────────────────
        if event.type == pygame_gui.UI_BUTTON_PRESSED and self.unsaved_panel:
            if event.ui_element == self.unsaved_btn_save:
                self._close_unsaved_panel()
                return self._execute_pending(did_save=True)
            elif event.ui_element == self.unsaved_btn_discard:
                self._close_unsaved_panel()
                self.dirty = False   # mark clean so _execute_pending skips save
                return self._execute_pending(did_save=False)
            elif event.ui_element == self.unsaved_btn_cancel:
                self._close_unsaved_panel()
                self._pending_action = None
                return None

        # ── Delete-confirmation dialog ────────────────────────────────────
        if event.type == pygame_gui.UI_CONFIRMATION_DIALOG_CONFIRMED:
            if self.confirm_dialog and event.ui_element == self.confirm_dialog:
                self.confirm_dialog = None
                name = self.get_current_name()
                path = f"maps/{name}.yaml"
                if os.path.exists(path):
                    os.remove(path)
                self.refresh_file_list()
                if not self.map_files:
                    self.map_files = ["new_map"]
                self.current_file_idx = 0
                self.refresh_dropdown()
                self.load_current_map()

        # ── Dropdown ──────────────────────────────────────────────────────
        if event.type == pygame_gui.UI_DROP_DOWN_MENU_CHANGED:
            if event.ui_element == self.dropdown_map:
                selection = event.text
                if selection == "+ Create New Map":
                    if self._check_unsaved(('new',)):
                        return None
                    self._create_new_map()
                    return None
                elif selection in self.map_files:
                    idx = self.map_files.index(selection)
                    if idx == self.current_file_idx:
                        # Same map re-selected – just reset dropdown visual
                        self.refresh_dropdown()
                        return None
                    if self._check_unsaved(('select', idx)):
                        return None
                    self.current_file_idx = idx
                    self.refresh_dropdown()
                    self.load_current_map()
                    self._share_selected_map(selection)
                else:
                    # e.g. "Select Map..." chosen – reset visual
                    self.refresh_dropdown()

        # ── Button events ─────────────────────────────────────────────────
        if event.type == pygame_gui.UI_BUTTON_PRESSED:

            if event.ui_element == self.btn_edit:
                self.btn_edit.select()
                return None

            if event.ui_element == self.btn_dup:
                base_dup = self.get_current_name() + "_copy"
                new_name = base_dup
                counter  = 1
                while new_name in self.map_files:
                    new_name = f"{base_dup}_{counter}"
                    counter += 1
                self.map_files.insert(self.current_file_idx + 1, new_name)
                self.current_file_idx += 1
                self.name_input.set_text(new_name)
                self.refresh_dropdown()
                self.dirty = True

            elif event.ui_element == self.btn_del:
                self.confirm_dialog = pygame_gui.windows.UIConfirmationDialog(
                    rect=pygame.Rect(
                        (SCREEN_W // 2 - 130, SCREEN_H // 2 - 100), (260, 200)
                    ),
                    manager=self.manager,
                    window_title="Delete Map",
                    action_long_desc="Are you sure you want to delete this map?",
                    action_short_name="Delete",
                    blocking=True
                )

            elif event.ui_element == self.btn_w_minus:
                if self.map_obj.width > MIN_GRID:
                    self._resize_grid(self.map_obj.width - 1, self.map_obj.height)
            elif event.ui_element == self.btn_w_plus:
                if self.map_obj.width < MAX_GRID:
                    self._resize_grid(self.map_obj.width + 1, self.map_obj.height)
            elif event.ui_element == self.btn_h_minus:
                if self.map_obj.height > MIN_GRID:
                    self._resize_grid(self.map_obj.width, self.map_obj.height - 1)
            elif event.ui_element == self.btn_h_plus:
                if self.map_obj.height < MAX_GRID:
                    self._resize_grid(self.map_obj.width, self.map_obj.height + 1)

            elif event.ui_element == self.btn_wrap:
                self.map_obj.wrap = not self.map_obj.wrap
                self.update_option_buttons()
                self.dirty = True
            elif event.ui_element == self.btn_diag:
                self.map_obj.diagonal_moves = not self.map_obj.diagonal_moves
                self.update_option_buttons()
                self.dirty = True
            elif event.ui_element == self.btn_diag_cost:
                self.map_obj.diagonal_move_true_cost = not self.map_obj.diagonal_move_true_cost
                self.update_option_buttons()
                self.dirty = True
            elif event.ui_element == self.btn_dist_minus:
                if self.map_obj.min_distance > 0:
                    self.map_obj.min_distance -= 1
                    self.update_option_buttons()
                    self.dirty = True
            elif event.ui_element == self.btn_dist_plus:
                self.map_obj.min_distance += 1
                self.update_option_buttons()
                self.dirty = True

            elif event.ui_element == self.btn_save:
                self.save_current_map()

            elif event.ui_element == self.btn_help:
                self.help_overlay = HelpOverlay(self.screen, 'Creating maps', [
                    'Use the drawing tools to place empty cells, walls, allowed starts, '
                    'and allowed goals. A cell may be both a start and a goal.',
                    'Use Teleport to place two gates with the same letter. Teleport gates '
                    'are paired and the move costs one step into the gate.',
                    'Choose wrapping, diagonal movement, diagonal cost, and minimum distance '
                    'to define the movement rules for the map.',
                    'The minimum distance is checked against at least one allowed start-goal '
                    'pair before the map can be run.',
                    'Create maps that reveal differences between BFS, DFS, Dijkstra, and A*. '
                    'Try open grids, mazes, dead ends, wraparound, diagonal costs, and '
                    'teleport shortcuts.',
                    'Save often.',
                    'When finished, switch to Run Agents to choose a map and compare the '
                    'algorithms on identical start and goal pairs.',
                ])

            elif event.ui_element == self.btn_run:
                if self._check_unsaved(('sim',)):
                    return None
                self._save_session('simulation')
                from ui.sim_view import SimulationView
                SimulationView.selected_map_name = self.get_current_name()
                return SimulationView

            else:
                for tool, btn in self.tool_btns.items():
                    if event.ui_element == btn:
                        for b in self.tool_btns.values():
                            b.unselect()
                        btn.select()
                        self.current_tool = tool
                        if tool != 'Teleport':
                            self.tp_state = 0
                            if self.first_tp_pos:
                                fx, fy = self.first_tp_pos
                                self.map_obj.map[fy][fx] = '-'
                                self.first_tp_pos = None

        # ── Grid mouse events (only to the right of the sidebar) ──────────
        mouse_x, mouse_y = pygame.mouse.get_pos()
        if mouse_x >= MAP_AREA_X:
            gx = (mouse_x - MAP_AREA_X) // self.tile_size
            gy = mouse_y // self.tile_size

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if 0 <= gx < self.map_obj.width and 0 <= gy < self.map_obj.height:
                    self.is_dragging = True
                    cell = self.map_obj.map[gy][gx]
                    self.drag_mode = 'draw'
                    if self.current_tool == 'Wall' and cell == '#':
                        self.drag_mode = 'erase'
                    elif self.current_tool == 'Empty' and cell == '-':
                        self.drag_mode = 'erase'
                    elif self.current_tool == 'Start' and cell in ['s', 'x']:
                        self.drag_mode = 'erase'
                    elif self.current_tool == 'Goal' and cell in ['g', 'x']:
                        self.drag_mode = 'erase'
                    elif (self.current_tool == 'Teleport'
                          and cell.isalpha() and cell.isupper()
                          and cell not in ['s', 'g', 'x']):
                        self.drag_mode = 'erase'
                    self.apply_tool(gx, gy)
                    self.last_modified_cell = (gx, gy)

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.is_dragging        = False
                self.last_modified_cell = None

            elif event.type == pygame.MOUSEMOTION and self.is_dragging:
                if 0 <= gx < self.map_obj.width and 0 <= gy < self.map_obj.height:
                    if (gx, gy) != self.last_modified_cell:
                        self.apply_tool(gx, gy)
                        self.last_modified_cell = (gx, gy)

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.is_dragging        = False
            self.last_modified_cell = None

        return None

    def _share_selected_map(self, name):
        MapEditor.selected_map_name = name
        self.session_state['selected_map_name'] = name
        simulation_state = self.session_state.setdefault('simulation', {})
        simulation_state['selected_map_name'] = name
        simulation_state['results'] = {}
        simulation_state['pairs'] = []
        simulation_state['current_agent'] = None
        simulation_state['current_instance'] = 0
        simulation_state['animation_step'] = 0
        save_session_state(self.session_state)
        from ui.sim_view import SimulationView
        SimulationView.selected_map_name = name

    # ═══════════════════════════════════════════════════════════════════════
    # TP helpers
    # ═══════════════════════════════════════════════════════════════════════

    def _refresh_next_tp_id(self):
        existing_ids = sorted({
            cell
            for row in self.map_obj.map
            for cell in row
            if cell.isalpha() and cell.isupper()
            and cell not in ['s', 'g', 'x']
        })
        self.next_tp_id = (
            chr(ord(existing_ids[-1]) + 1)
            if existing_ids else 'A'
        )

    def remove_tp_pair(self, tp_id):
        for ry in range(self.map_obj.height):
            for rx in range(self.map_obj.width):
                if self.map_obj.map[ry][rx] == tp_id:
                    self.map_obj.map[ry][rx] = '-'
        for ry in range(self.map_obj.height):
            for rx in range(self.map_obj.width):
                cell = self.map_obj.map[ry][rx]
                if (cell.isalpha() and cell.isupper()
                        and cell > tp_id and cell not in ['s', 'g', 'x']):
                    self.map_obj.map[ry][rx] = chr(ord(cell) - 1)
        self._refresh_next_tp_id()

    # ═══════════════════════════════════════════════════════════════════════
    # Tool application
    # ═══════════════════════════════════════════════════════════════════════

    def apply_tool(self, x, y):
        cell  = self.map_obj.map[y][x]
        is_tp = cell.isalpha() and cell.isupper() and cell not in ['s', 'g', 'x']

        if self.current_tool in ['Start', 'Goal']:
            if cell == '#' or is_tp:
                self._show_warning(
                    f"Cannot place {self.current_tool} on a Wall or TP"
                )
                return

        if is_tp:
            if self.drag_mode == 'erase' or self.current_tool != 'Teleport':
                self.remove_tp_pair(cell)
                if self.tp_state == 1:
                    fx, fy = self.first_tp_pos
                    self.map_obj.map[fy][fx] = '-'
                    self.tp_state     = 0
                    self.first_tp_pos = None
                    self._refresh_next_tp_id()

        if self.current_tool == 'Empty':
            self.map_obj.map[y][x] = '-'
        elif self.current_tool == 'Wall':
            if self.drag_mode == 'erase':
                self.map_obj.map[y][x] = '-'
            else:
                self.map_obj.map[y][x] = '#'
        elif self.current_tool == 'Start':
            if self.drag_mode == 'erase':
                if cell == 'x':   self.map_obj.map[y][x] = 'g'
                elif cell == 's': self.map_obj.map[y][x] = '-'
            else:
                if cell == 'g':                    self.map_obj.map[y][x] = 'x'
                elif cell in ['-', 's', 'x']:      self.map_obj.map[y][x] = 's'
        elif self.current_tool == 'Goal':
            if self.drag_mode == 'erase':
                if cell == 'x':   self.map_obj.map[y][x] = 's'
                elif cell == 'g': self.map_obj.map[y][x] = '-'
            else:
                if cell == 's':                    self.map_obj.map[y][x] = 'x'
                elif cell in ['-', 'g', 'x']:      self.map_obj.map[y][x] = 'g'
        elif self.current_tool == 'Teleport':
            if self.drag_mode != 'erase':
                if self.tp_state == 0:
                    if self.next_tp_id > 'Z':
                        self._show_warning("Maximum 26 teleport pairs allowed")
                        return
                    self.map_obj.map[y][x] = self.next_tp_id
                    self.first_tp_pos = (x, y)
                    self.tp_state = 1
                elif self.tp_state == 1:
                    if (x, y) != self.first_tp_pos:
                        self.map_obj.map[y][x] = self.next_tp_id
                        self.next_tp_id   = chr(ord(self.next_tp_id) + 1)
                        self.tp_state     = 0
                        self.first_tp_pos = None

        self.dirty = True

    # ═══════════════════════════════════════════════════════════════════════
    # Update / Draw
    # ═══════════════════════════════════════════════════════════════════════

    def update(self):
        pass

    def draw(self, screen):
        screen.fill((30, 30, 36))

        # Sidebar background
        pygame.draw.rect(
            screen, (22, 22, 28), pygame.Rect(0, 0, SIDEBAR_W, SCREEN_H)
        )
        pygame.draw.line(
            screen, (60, 60, 80), (SIDEBAR_W, 0), (SIDEBAR_W, SCREEN_H), 1
        )

        ts = self.tile_size

        # Draw grid
        for ry in range(self.map_obj.height):
            for rx in range(self.map_obj.width):
                px   = MAP_AREA_X + rx * ts
                py   = ry * ts
                rect = pygame.Rect(px, py, ts, ts)
                cell = self.map_obj.map[ry][rx]

                pygame.draw.rect(screen, COLOR_BG_EMPTY, rect)
                if cell == '#':
                    pygame.draw.rect(screen, COLOR_BG_WALL, rect)
                elif cell in ['s', 'x']:
                    pygame.draw.rect(screen, COLOR_START_BG, rect)

                if cell in ['g', 'x']:
                    pygame.draw.circle(
                        screen, COLOR_GOAL_ICON, rect.center, max(3, ts // 4)
                    )

                if (cell.isalpha() and cell.isupper()
                        and cell not in ['s', 'g', 'x']):
                    lbl = self.font.render(cell, True, COLOR_TP_TEXT)
                    screen.blit(lbl, (px + max(2, ts // 4), py + max(2, ts // 4)))

                pygame.draw.rect(screen, (50, 50, 60), rect, 1)

        # Dirty indicator
        if self.dirty:
            dirty_surf = self.warning_font.render(
                "* unsaved changes", True, (220, 180, 40)
            )
            screen.blit(dirty_surf, (MAP_AREA_X + 8, SCREEN_H - 30))

        # Warning / status message
        if self.warning_msg and pygame.time.get_ticks() - self.warning_time < 4000:
            is_err = any(
                kw in self.warning_msg
                for kw in ("already exists", "Cannot", "Maximum")
            )
            color = (255, 80, 80) if is_err else (80, 200, 120)
            warn  = self.warning_font.render(self.warning_msg, True, color)
            screen.blit(warn, (MAP_AREA_X + 8, SCREEN_H - 56))
