import glob
import math
import multiprocessing
import os
import random
import time
from queue import Empty
from concurrent.futures import ProcessPoolExecutor

import pygame
import pygame_gui

from agents import AGENTS_MAP
from core.constants import *
from core.map import Map
from utils.validation import dijkstra_min_distance
from utils.yaml_handler import load_map
from utils.session_state import load_session_state, save_session_state
from ui.help_dialog import HelpOverlay

SIDEBAR_W = 330
SCREEN_W = 1200
SCREEN_H = 768
MAP_TOP = 52


def compute_tile_size(width, height):
    return max(4, min((SCREEN_W - SIDEBAR_W) // width,
                      (SCREEN_H - MAP_TOP) // height, 64))


def _run_agent_worker(agent_name, data, start, goal, exploration_queue):
    agent_map = Map([row[:] for row in data['grid']], data['wrap'],
                    data['diagonal_moves'], data['diagonal_move_true_cost'],
                    data['min_distance'])
    agent_map.set_start_goal(start, goal)
    agent_type = AGENTS_MAP[agent_name]
    agent = agent_type(agent_map)
    agent._exploration_sink = exploration_queue.put
    try:
        return {'path': agent.run(), 'explored': agent.get_explored()}
    except Exception:
        return {
            'path': None,
            'explored': agent.get_explored(),
            'error': 'Error',
        }


class RunSimulationButton(pygame_gui.elements.UIButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.spinner_visible = False
        self.spinner_phase = 0

    def set_spinner(self, visible, phase=0):
        self.spinner_visible = visible
        self.spinner_phase = phase

    def draw(self, surface):
        super().draw(surface)


class SimulationView:
    selected_map_name = None

    def __init__(self, screen, manager):
        self.screen = screen
        self.manager = manager
        self.session_state = load_session_state()
        simulation_state = self.session_state.get('simulation', {})
        self.simulation_state = simulation_state
        self.selected_map_name = (
            self.session_state.get('selected_map_name')
            or simulation_state.get('selected_map_name')
            or self.selected_map_name
        )
        self.font = pygame.font.SysFont(None, 21)
        self.small_font = pygame.font.SysFont(None, 17)
        self.table_font = pygame.font.SysFont('Arial', 13, bold=False)
        self.warning_msg = ''
        self.warning_time = 0
        self.agent_names = list(AGENTS_MAP)
        self.selected_agents = [
            name for name in simulation_state.get('selected_agents', [])
            if name in AGENTS_MAP
        ]
        self.results = {
            name: simulation_state.get('results', {}).get(name, [])
            for name in self.selected_agents
        }
        self.pairs = simulation_state.get('pairs', [])
        self.instance_count = simulation_state.get('instance_count', 10)
        self.current_agent = simulation_state.get('current_agent')
        self.current_instance = simulation_state.get('current_instance', 0)
        self.last_instance_by_agent = {
            name: int(index)
            for name, index in simulation_state.get('last_instance_by_agent', {}).items()
        }
        self.animation_step = simulation_state.get('animation_step', 0)
        self.animation_playing = False
        self.animation_fps = max(10, min(
            120, simulation_state.get('animation_fps', 60)
        ))
        self.animation_speeds = [10, 20, 30, 40, 50, 60]
        self.animation_speeds.extend([70, 80, 90, 100, 110, 120])
        self.last_animation_tick = time.monotonic()
        self.map_obj = None
        self.tile_size = 1
        self.running = False
        self.running_spinner_count = 30
        self.running_spinner_interval = 1 / 30
        self.running_spinner_index = 0
        self.last_running_spinner_tick = time.monotonic()
        self.executor = None
        self.pending_future = None
        self.pending_agent = None
        self.pending_started = 0
        self.progress_manager = None
        self.exploration_queue = None
        self.pending_explored = []
        self.run_status = ''
        self.help_overlay = None
        self.results_table_y = 475
        self._build_ui()
        self._restore_simulation_state(simulation_state)

    def _build_ui(self):
        sx, sw, y = 10, SIDEBAR_W - 20, 10
        self.btn_edit = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((sx, y), (sw // 2 - 3, 30)),
            text='Edit Map', manager=self.manager)
        self.btn_edit.enable()
        self.btn_run_agents = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((sx + sw // 2 + 3, y), (sw // 2 - 3, 30)),
            text='Run Agents', manager=self.manager)
        self.btn_run_agents.select()
        y += 40
        map_names = [os.path.basename(path).replace('.yaml', '')
                     for path in sorted(glob.glob('maps/*.yaml'))]
        if self.selected_map_name not in map_names:
            self.selected_map_name = map_names[0] if map_names else None
            SimulationView.selected_map_name = self.selected_map_name
            self.session_state['selected_map_name'] = self.selected_map_name
            self.simulation_state['selected_map_name'] = self.selected_map_name
            if self.selected_map_name is None:
                self.results = {}
                self.pairs = []
            save_session_state(self.session_state)
        self.dropdown_map = pygame_gui.elements.UIDropDownMenu(
            options_list=['Select Map...'] + map_names,
            starting_option=(self.selected_map_name
                             if self.selected_map_name in map_names
                             else 'Select Map...'),
            relative_rect=pygame.Rect((sx + 45, y), (sw - 45, 30)), manager=self.manager)
        self._add_left_label((sx, y, 42, 30), 'Map:')
        y += 42
        self._add_left_label((sx, y, sw, 24), 'Agents:')
        y += 28
        self.agent_buttons = {}
        self.agent_scroll = pygame_gui.elements.UIScrollingContainer(
            relative_rect=pygame.Rect((sx, y), (sw, 120)),
            manager=self.manager, allow_scroll_x=False, allow_scroll_y=True,
            should_grow_automatically=True)
        agent_container = self.agent_scroll.get_container()
        agent_y = 0
        for name in self.agent_names:
            self.agent_buttons[name] = pygame_gui.elements.UIButton(
                relative_rect=pygame.Rect((0, agent_y), (sw - 18, 30)),
                text=name, manager=self.manager, container=agent_container)
            if name in self.selected_agents:
                self.agent_buttons[name].select()
            agent_y += 36
        agent_content_height = max(120, agent_y)
        if agent_content_height > 120:
            self.agent_scroll.set_dimensions((sw, 120))
        y += 128
        self._add_left_label((sx, y, 185, 30), 'Instances per agent:')
        self.instances_input = pygame_gui.elements.UITextEntryLine(
            relative_rect=pygame.Rect((sx + 190, y), (sw - 190, 30)), manager=self.manager)
        self.instances_input.set_allowed_characters(list('0123456789'))
        self.instances_input.set_text_length_limit(6)
        self.instances_input.set_text(str(self.instance_count))
        y += 36
        self._add_left_label((sx, y, 185, 30), 'Max seconds per instance:')
        self.timeout_input = pygame_gui.elements.UITextEntryLine(
            relative_rect=pygame.Rect((sx + 190, y), (sw - 190, 30)), manager=self.manager)
        self.timeout_input.set_allowed_characters(list('0123456789.'))
        self.timeout_input.set_text_length_limit(8)
        self.timeout_input.set_text(str(self.simulation_state.get('timeout', 10)))
        y += 36
        self._add_left_label((sx, y, 185, 30), 'Random seed:')
        self.seed_input = pygame_gui.elements.UITextEntryLine(
            relative_rect=pygame.Rect((sx + 190, y), (sw - 190, 30)), manager=self.manager)
        self.seed_input.set_allowed_characters(list('0123456789'))
        self.seed_input.set_text_length_limit(12)
        self.seed_input.set_text(str(self.simulation_state.get('seed', '')))
        y += 42
        self.btn_simulate = RunSimulationButton(
            relative_rect=pygame.Rect((sx, y), (sw, 36)), text='Run Simulation', manager=self.manager)
        stop_width = 92
        spinner_width = 32
        text_width = sw - stop_width - spinner_width
        self.lbl_running = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect((sx + spinner_width, y), (text_width, 36)),
            text='Running (0 of 0)', manager=self.manager)
        self.running_spinner_center = (
            sx + spinner_width // 2, y + 18
        )
        self.btn_stop = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((sx + sw - stop_width, y),
                                      (stop_width, 36)),
            text='Stop', manager=self.manager)
        self.lbl_running.hide()
        self.btn_stop.hide()
        self.btn_copy = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((170, 470), (65, 26)),
            text='Copy', manager=self.manager)
        self.btn_help = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((SCREEN_W - 82, SCREEN_H - 40), (72, 30)),
            text='Help', manager=self.manager)
        y += 42
        if self.selected_map_name in map_names:
            self._load_map(self.selected_map_name)

        control_y = 10
        control_x = SIDEBAR_W + 10
        control_gap = 6
        self.btn_prev = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((control_x, control_y), (42, 30)),
            text='<', manager=self.manager)
        self.lbl_instance = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect((control_x + 48, control_y), (160, 30)),
            text='No simulation selected', manager=self.manager)
        self.btn_next = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((control_x + 214, control_y), (42, 30)),
            text='>', manager=self.manager)
        self.btn_play = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((control_x + 262, control_y), (90, 30)),
            text='Play', manager=self.manager)
        self.btn_results = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((control_x + 358, control_y), (90, 30)),
            text='Results', manager=self.manager)
        self.lbl_speed = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect((control_x + 454, control_y), (70, 30)),
            text=f'{self.animation_fps} FPS', manager=self.manager)
        self.speed_slider = pygame_gui.elements.UIHorizontalSlider(
            relative_rect=pygame.Rect((control_x + 526, control_y + 4), (120, 22)),
            start_value=min(self.animation_fps, 120), value_range=(10, 120),
            manager=self.manager)

    def _results_layout(self):
        row_count = len(self.selected_agents)
        table_height = 41 + 31 * row_count
        gap = 24

        run_rect = self.btn_simulate.get_abs_rect()
        table_y = run_rect.bottom + gap

        if table_y + table_height > SCREEN_H:
            table_y = max(0, run_rect.top - gap - table_height)

        self.results_table_y = table_y
        self.btn_copy.set_position((170, table_y - 5))
        return table_y

    def _add_left_label(self, rect, text):
        label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(rect), text=text, manager=self.manager)
        label.text_horiz_alignment = 'left'
        label.rebuild()
        return label

    def _show_warning(self, message):
        self.warning_msg = message
        self.warning_time = pygame.time.get_ticks()

    def _restore_simulation_state(self, state):
        if not self.selected_map_name or not self.map_obj:
            self.results = {name: [] for name in self.selected_agents}
            self.pairs = []
            self.current_agent = None
            self.current_instance = 0
            self.animation_step = 0
            self._update_animation_controls()
            return
        if state.get('selected_map_name') not in (None, self.selected_map_name):
            self.results = {name: [] for name in self.selected_agents}
            self.pairs = []
            self.current_agent = None
            self.current_instance = 0
            self.animation_step = 0
            self._update_animation_controls()
            return
        normalized_results = self._normalize_results(
            state.get('results', self.results)
        )
        self.results = {
            name: normalized_results.get(name, [])
            for name in self.selected_agents
        }
        self.pairs = [
            (tuple(start), tuple(goal), distance)
            for start, goal, distance in state.get('pairs', self.pairs)
        ]
        self.instance_count = state.get('instance_count', self.instance_count)
        self.current_agent = state.get('current_agent', self.current_agent)
        self.current_instance = state.get('current_instance', self.current_instance)
        self.last_instance_by_agent.update({
            name: int(index)
            for name, index in state.get('last_instance_by_agent', {}).items()
        })
        self.animation_step = state.get('animation_step', self.animation_step)
        if self.selected_agents:
            self.results = {name: self.results.get(name, []) for name in self.selected_agents}
        if self.current_agent not in self.selected_agents:
            self.current_agent = self.selected_agents[0] if self.selected_agents else None
        self._update_animation_controls()

    @staticmethod
    def _normalize_results(results):
        normalized = {}
        for agent_name, entries in results.items():
            normalized[agent_name] = []
            for entry in entries:
                result = dict(entry)
                result['explored'] = [tuple(cell) for cell in result.get('explored', [])]
                if result.get('path'):
                    result['path'] = [tuple(cell) for cell in result['path']]
                normalized[agent_name].append(result)
        return normalized

    def _save_session(self, active_view='simulation'):
        self.session_state['active_view'] = active_view
        self.session_state['selected_map_name'] = self.selected_map_name
        self.session_state['simulation'] = {
            'selected_map_name': self.selected_map_name,
            'selected_agents': self.selected_agents,
            'results': self.results,
            'pairs': self.pairs,
            'instance_count': self.instance_count,
            'timeout': self._positive(self.timeout_input, 10, minimum=0.1),
            'seed': self.seed_input.get_text(),
            'current_agent': self.current_agent,
            'current_instance': self.current_instance,
            'last_instance_by_agent': self.last_instance_by_agent,
            'animation_step': self.animation_step,
            'animation_fps': self.animation_fps,
        }
        save_session_state(self.session_state)

    def _load_map(self, name):
        data = load_map(f'maps/{name}.yaml')
        if not data:
            return
        self.map_obj = Map(data['map'], data['wrap'], data['diagonal_moves'],
                           data['diagonal_move_true_cost'], data['min_distance'])
        self.selected_map_name = name
        SimulationView.selected_map_name = name
        self.session_state['selected_map_name'] = name
        save_session_state(self.session_state)
        self.tile_size = compute_tile_size(self.map_obj.width, self.map_obj.height)
        self._reset_results()
        self._save_session('simulation')

    def _reset_results(self):
        self.results = {name: [] for name in self.selected_agents}
        self.pairs = []
        self.current_agent = None
        self.current_instance = 0
        self.last_instance_by_agent = {}
        self.animation_step = 0
        self.animation_playing = False
        self.pending_agent = None
        if self.running:
            self._stop_simulation()

    def _update_agent_selection(self, name):
        if name in self.selected_agents:
            self.selected_agents.remove(name)
            self.results.pop(name, None)
        else:
            self.selected_agents.append(name)
            self.results.setdefault(name, [])
        self.current_agent = next(iter(self.results), None)
        self.current_instance = self.last_instance_by_agent.get(self.current_agent, 0)
        self.animation_step = 0
        self.animation_playing = False
        if self.running:
            self._stop_simulation()

    @staticmethod
    def _positive(entry, default, minimum=1, integer=False):
        try:
            value = int(entry.get_text()) if integer else float(entry.get_text())
            value = max(minimum, value)
            entry.set_text(str(int(value) if integer else value))
            return int(value) if integer else value
        except ValueError:
            entry.set_text(str(default))
            return default

    def _allowed_cells(self, marker):
        cells = []
        for y, row in enumerate(self.map_obj.map):
            for x, value in enumerate(row):
                if value == marker or value == '$' or (marker == '-' and value == '-'):
                    cells.append((x, y))
        return cells

    def _make_pairs(self, count):
        starts = self._allowed_cells('@') or self._allowed_cells('-')
        goals = self._allowed_cells('!') or self._allowed_cells('-')
        candidates = []
        for start in starts:
            for goal in goals:
                if start == goal:
                    continue
                distance = dijkstra_min_distance(self.map_obj, start, goal)
                if distance is not None and distance >= self.map_obj.min_distance:
                    candidates.append((start, goal, distance))
        if not candidates:
            return []
        if len(candidates) >= count:
            return random.sample(candidates, count)
        return [random.choice(candidates) for _ in range(count)]

    def _start_simulation(self):
        if self.map_obj is None:
            self._show_warning('Choose a map before running.')
            return
        if not self.selected_agents:
            self._show_warning('Select at least one agent.')
            return
        count = self._positive(self.instances_input, 10, minimum=1, integer=True)
        self._positive(self.timeout_input, 10, minimum=0.1)
        seed_text = self.seed_input.get_text().strip()
        if seed_text:
            try:
                random.seed(int(seed_text))
            except ValueError:
                self._show_warning('Random seed must be an integer.')
                return
        self.instance_count = count
        self.pairs = self._make_pairs(count)
        if not self.pairs:
            self._show_warning('No valid start/goal pair satisfies this map.')
            return
        self.results = {name: [] for name in self.selected_agents}
        self.current_agent = self.selected_agents[0]
        self.current_instance = 0
        self.animation_step = 0
        self.running = True
        self.run_status = ''
        self.running_spinner_index = 0
        self.last_running_spinner_tick = time.monotonic()
        self.executor = ProcessPoolExecutor(max_workers=1)
        self.progress_manager = multiprocessing.Manager()
        self.exploration_queue = self.progress_manager.Queue()
        self._submit_next()

    def _submit_next(self):
        for name in self.selected_agents:
            if len(self.results[name]) >= len(self.pairs):
                continue
            index = len(self.results[name])
            data = {'grid': self.map_obj.map, 'wrap': self.map_obj.wrap,
                    'diagonal_moves': self.map_obj.diagonal_moves,
                    'diagonal_move_true_cost': self.map_obj.diagonal_move_true_cost,
                    'min_distance': self.map_obj.min_distance}
            start, goal, _ = self.pairs[index]
            self.pending_agent = name
            self.pending_explored = []
            self.pending_future = self.executor.submit(
                _run_agent_worker, name, data, start, goal, self.exploration_queue
            )
            self.pending_started = time.monotonic()
            return
        self._stop_simulation()

    def _stop_simulation(self):
        self.running = False
        self.pending_future = None
        self.pending_agent = None
        if self.executor:
            self.executor.shutdown(wait=False, cancel_futures=True)
            self.executor = None
        if self.progress_manager:
            self.progress_manager.shutdown()
            self.progress_manager = None
            self.exploration_queue = None

    def _poll_simulation(self):
        if not self.running or self.pending_future is None:
            return
        self._drain_exploration_queue()
        agent_name = self.pending_agent
        limit = self._positive(self.timeout_input, 10, minimum=0.1)
        if time.monotonic() - self.pending_started > limit:
            self.results[agent_name].append({
                'error': 'Timed out',
                'explored': list(self.pending_explored),
                'path': None,
                'runtime': time.monotonic() - self.pending_started,
            })
            self.run_status = 'Timed out during this run'
            self._save_session('simulation')
            self._show_warning(f'{agent_name} instance timed out.')
            self._stop_simulation()
            self.running = True
            self.executor = ProcessPoolExecutor(max_workers=1)
            self.progress_manager = multiprocessing.Manager()
            self.exploration_queue = self.progress_manager.Queue()
            self._submit_next()
            return
        if not self.pending_future.done():
            return
        index = len(self.results[agent_name])
        try:
            result = self.pending_future.result()
            self._drain_exploration_queue()
            if result.get('error'):
                self.run_status = 'Error during this run'
            path = result.get('path')
            result['runtime'] = time.monotonic() - self.pending_started
            result['optimal'] = bool(path) and abs(self._path_cost(path) - self.pairs[index][2]) < 0.001
            if not result.get('explored'):
                result['explored'] = list(self.pending_explored)
            self.results[agent_name].append(result)
            if (agent_name == self.current_agent and
                    len(self.results[agent_name]) == 1 and
                    'error' not in result):
                self.current_instance = 0
                self.animation_step = 0
                self.animation_playing = True
                self.last_animation_tick = time.monotonic()
        except Exception as exc:
            self._drain_exploration_queue()
            self.results[agent_name].append({
                'error': 'Error',
                'explored': list(self.pending_explored),
                'path': None,
            })
            self.run_status = 'Error during this run'
            self._show_warning(f'{agent_name}: {type(exc).__name__}')
        self.pending_future = None
        self._save_session('simulation')
        self._submit_next()

    def _drain_exploration_queue(self):
        if self.exploration_queue is None:
            return
        while True:
            try:
                self.pending_explored.append(tuple(self.exploration_queue.get_nowait()))
            except Empty:
                return

    def _path_cost(self, path):
        total = 0.0
        for current, target in zip(path or [], (path or [])[1:]):
            for move in self.map_obj.get_valid_moves(*current):
                if move.location == target:
                    total += move.cost
                    break
        return total

    def _current_result(self):
        entries = self.results.get(self.current_agent, [])
        if not entries or self.current_instance >= len(entries):
            return None
        return entries[self.current_instance]

    def _current_run_status(self):
        result = self._current_result()
        if not result:
            return ''
        if result.get('error') == 'Timed out':
            return 'Timed out during this run'
        if result.get('error'):
            return 'Error during this run'
        return ''

    def _update_animation_controls(self):
        entries = self.results.get(self.current_agent, [])
        has_results = bool(self.current_agent and entries)
        current_result = self._current_result() if has_results else None
        can_play = bool(current_result and current_result.get('explored'))
        if has_results:
            self.lbl_instance.set_text(
                f'{self.current_agent}: {self.current_instance + 1} of {len(entries)}'
            )
            if self.current_instance > 0:
                self.btn_prev.enable()
            else:
                self.btn_prev.disable()
            if self.current_instance < len(entries) - 1:
                self.btn_next.enable()
            else:
                self.btn_next.disable()
        else:
            self.lbl_instance.set_text('No simulation selected')
            self.animation_playing = False
            self.btn_prev.disable()
            self.btn_next.disable()
        if can_play:
            self.btn_play.enable()
        else:
            self.btn_play.disable()
            self.animation_playing = False
        if has_results:
            self.btn_results.enable()
        else:
            self.btn_results.disable()
        self.btn_play.set_text('Pause' if self.animation_playing else 'Play')

    def _update_run_button(self):
        if self.running:
            now = time.monotonic()
            if now - self.last_running_spinner_tick >= self.running_spinner_interval:
                self.running_spinner_index = (
                    self.running_spinner_index + 1
                ) % self.running_spinner_count
                self.last_running_spinner_tick += self.running_spinner_interval
            completed_instances = sum(
                len(self.results.get(name, [])) for name in self.selected_agents
            )
            total_instances = self.instance_count * len(self.selected_agents)
            self.btn_simulate.hide()
            self.lbl_running.show()
            self.btn_stop.show()
            self.lbl_running.set_text(f'Running ({completed_instances} of {total_instances})...')
            return

        self.btn_simulate.show()
        self.lbl_running.hide()
        self.btn_stop.hide()
        has_results = any(self.results.get(name) for name in self.selected_agents)
        self.btn_simulate.set_text('Rerun Simulation' if has_results else 'Run Simulation')

    def _draw_run_spinner(self, screen):
        if not self.running:
            return
        center_x, center_y = self.running_spinner_center
        radius = 7
        spinner_rect = pygame.Rect(
            center_x - radius, center_y - radius, radius * 2, radius * 2
        )
        start_angle = self.running_spinner_index * (
            2 * math.pi / self.running_spinner_count
        )
        pygame.draw.arc(
            screen, (155, 155, 155), spinner_rect,
            0, (math.pi * 2), 3
        )
        pygame.draw.arc(
            screen, (155, 220, 245), spinner_rect,
            start_angle, start_angle + (math.pi / 2), 3
        )

    def _select_instance(self, offset):
        entries = self.results.get(self.current_agent, [])
        if not entries:
            return
        next_instance = self.current_instance + offset
        if next_instance < 0 or next_instance >= len(entries):
            return
        self.current_instance = next_instance
        self.last_instance_by_agent[self.current_agent] = self.current_instance
        self.animation_step = 0
        self.animation_playing = True
        self.last_animation_tick = time.monotonic()
        self._update_animation_controls()

    def _show_results(self):
        result = self._current_result()
        if result:
            self.animation_step = len(result.get('explored', []))
        self.animation_playing = False
        self._update_animation_controls()

    def _help(self):
        self.help_overlay = HelpOverlay(self.screen, 'Running simulations', [
            'Choose a map and one or more agents, then choose how many instances to run.',
            'Every selected agent uses the same generated start and goal pairs.',
            'Random seed: leave blank for a fresh random experiment. Enter an integer to '
            'repeat the same start and goal pairs later.',
            'Runtime is the total time for completed instances of an agent. While running, '
            'the current instance time is included so the value updates as progress is made.',
            'Search is the number of recorded expanded nodes. Solution is the path cost. '
            'Optimal means the path cost matches the map shortest-path cost.',
            'Click an agent row to inspect its exploration animation. Use Play, Results, '
            'and the arrow buttons to control it.',
            'Copy places a fixed-width version of the results table on the system clipboard '
            'so you can paste it into a lab report.',
            'A* uses its configured heuristic. Maps with wrapping or teleporters can expose '
            'when a heuristic is not admissible for the movement rules.',
        ])

    def _copy_results(self):
        headers = ('Agent', 'Runtime (s)', 'Search', 'Solution', 'Optimal')
        lines = ['{:<16} {:>12} {:>10} {:>10} {:>8}'.format(*headers)]
        for name in self.selected_agents:
            rows = self.results.get(name, [])
            runtime = sum(row.get('runtime', 0) for row in rows)
            searched = (sum(len(row.get('explored', [])) for row in rows) / len(rows)
                        if rows else 0)
            paths = [self._path_cost(row.get('path')) for row in rows if row.get('path')]
            solution = sum(paths) / len(paths) if paths else 0
            optimal = 'Yes' if rows and all(row.get('optimal', False) for row in rows) else 'No'
            lines.append('{:<16} {:>12.3f} {:>10.1f} {:>10.1f} {:>8}'.format(
                name, runtime, searched, solution, optimal))
        try:
            pygame.scrap.init()
            pygame.scrap.put(pygame.SCRAP_TEXT, '\n'.join(lines).encode())
            self._show_warning('Results copied to clipboard.')
        except pygame.error:
            self._show_warning('Clipboard is unavailable.')

    def _step_animation(self, amount):
        result = self._current_result()
        if not result or not result.get('explored'):
            return
        self.animation_step = max(0, min(len(result.get('explored', [])),
                                         self.animation_step + amount))

    def _select_agent(self, name):
        if self.results.get(name):
            self.current_agent = name
            self.current_instance = min(
                self.last_instance_by_agent.get(name, 0),
                len(self.results[name]) - 1
            )
            self.animation_step = 0
            self.animation_playing = bool(self._current_result())
            self.last_animation_tick = time.monotonic()
            self.last_instance_by_agent[name] = self.current_instance
            self._update_animation_controls()

    def handle_event(self, event):
        if self.help_overlay:
            if self.help_overlay.handle_event(event):
                self.help_overlay = None
            return None
        if event.type == pygame_gui.UI_TEXT_ENTRY_CHANGED and event.ui_element == self.instances_input:
            try:
                count = max(1, int(event.text))
                if count != self.instance_count:
                    self._reset_results()
            except ValueError:
                pass
        if event.type == pygame_gui.UI_TEXT_ENTRY_CHANGED and event.ui_element == self.seed_input:
            self._reset_results()
        if event.type == pygame_gui.UI_DROP_DOWN_MENU_CHANGED and event.ui_element == self.dropdown_map:
            if event.text != 'Select Map...':
                self._load_map(event.text)
        if event.type == pygame_gui.UI_BUTTON_PRESSED:
            if event.ui_element == self.btn_edit:
                self._stop_simulation()
                self._save_session('editor')
                from ui.map_editor import MapEditor
                MapEditor.selected_map_name = self.selected_map_name
                return MapEditor
            if event.ui_element == self.btn_run_agents:
                self.btn_run_agents.select()
                return None
            if event.ui_element == self.btn_simulate:
                self._start_simulation()
            elif event.ui_element == self.btn_stop:
                self._stop_simulation()
            elif event.ui_element in self.agent_buttons.values():
                name = next(key for key, value in self.agent_buttons.items() if value == event.ui_element)
                if name in self.selected_agents:
                    event.ui_element.unselect()
                else:
                    event.ui_element.select()
                self._update_agent_selection(name)
            elif event.ui_element == self.btn_play:
                result = self._current_result()
                if not result or not result.get('explored'):
                    self._update_animation_controls()
                    return None
                if (not self.animation_playing and result and
                    self.animation_step >= len(result.get('explored', []))):
                    self.animation_step = 0
                    self.last_animation_tick = time.monotonic()
                self.animation_playing = not self.animation_playing
                self._update_animation_controls()
            elif event.ui_element == self.btn_prev:
                self._select_instance(-1)
            elif event.ui_element == self.btn_next:
                self._select_instance(1)
            elif event.ui_element == self.btn_results:
                self._show_results()
            elif event.ui_element == self.btn_help:
                self._help()
            elif event.ui_element == self.btn_copy:
                self._copy_results()
            elif event.ui_element == self.speed_slider:
                self.animation_fps = min(
                    self.animation_speeds,
                    key=lambda speed: abs(speed - event.value)
                )
                self.speed_slider.set_current_value(self.animation_fps)
                self.lbl_speed.set_text(f'{self.animation_fps} FPS')
                self._save_session()
        if event.type == pygame_gui.UI_HORIZONTAL_SLIDER_MOVED:
            if event.ui_element == self.speed_slider:
                self.animation_fps = min(
                    self.animation_speeds,
                    key=lambda speed: abs(speed - event.value)
                )
                self.speed_slider.set_current_value(self.animation_fps)
                self.lbl_speed.set_text(f'{self.animation_fps} FPS')
                self._save_session()
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            x, y = event.pos
            table_y = self.results_table_y
            row_start = table_y + 40
            if x < SIDEBAR_W and row_start <= y < row_start + 31 * len(self.selected_agents):
                index = (y - row_start) // 31
                self._select_agent(self.selected_agents[index])
        return None

    def update(self):
        if self.help_overlay:
            return
        self._poll_simulation()
        if self.animation_playing:
            interval = 1 / self.animation_fps
            now = time.monotonic()
            while now - self.last_animation_tick >= interval:
                self._step_animation(1)
                self.last_animation_tick += interval
                result = self._current_result()
                if result and self.animation_step >= len(result.get('explored', [])):
                    self.animation_playing = False
                    self._update_animation_controls()
                    break
        self._update_run_button()
        self._update_animation_controls()

    def _draw_flag(self, rect):
        pole_x = rect.left + rect.width // 2 - 4
        pygame.draw.line(self.screen, (245, 245, 245), (pole_x, rect.top + 6), (pole_x, rect.bottom - 5), 2)
        pygame.draw.polygon(self.screen, (220, 40, 45), [(pole_x, rect.top + 7),
                          (rect.right - 6, rect.top + 12), (pole_x, rect.top + 18)])

    def _draw_grid(self):
        if self.map_obj is None:
            return
        result = self._current_result()
        if self.pairs:
            pair_index = min(self.current_instance, len(self.pairs) - 1)
            start, goal, _ = self.pairs[pair_index]
            self.map_obj.set_start_goal(start, goal)
        explored = result.get('explored', []) if result else []
        visible = explored[:self.animation_step]
        path = (result.get('path') or []) if result else []
        for y, row in enumerate(self.map_obj.map):
            for x, value in enumerate(row):
                rect = pygame.Rect(SIDEBAR_W + x * self.tile_size, MAP_TOP + y * self.tile_size,
                                   self.tile_size, self.tile_size)
                color = COLOR_BG_WALL if value == '#' else COLOR_BG_EMPTY
                if (x, y) in visible:
                    color = COLOR_PREV_EXPLORED
                if visible and (x, y) == visible[-1]:
                    color = COLOR_EXPLORED
                if self.animation_step >= len(explored) and (x, y) in path:
                    color = COLOR_PATH
                if self.map_obj.is_start(x, y):
                    color = COLOR_START_BG
                pygame.draw.rect(self.screen, color, rect)
                pygame.draw.rect(self.screen, (55, 55, 55), rect, 1)
                if value.isalpha() and value.isupper():
                    label = self.small_font.render(value, True, COLOR_TP_TEXT)
                    self.screen.blit(label, label.get_rect(center=rect.center))
                if self.map_obj.is_goal(x, y):
                    self._draw_flag(rect)

    def _draw_table(self):
        table_y = self._results_layout()
        self.screen.blit(self.font.render('Simulation Results', True, (235, 235, 240)), (10, table_y))
        header_rect = pygame.Rect(8, table_y + 21, SIDEBAR_W - 16, 20)
        pygame.draw.rect(self.screen, (60, 60, 72), header_rect)
        agent_left = 14
        time_anchor = 147
        time_left = time_anchor - self.table_font.size('888.888')[0]
        agent_right = time_left - 5
        header_specs = [
            ('Agent', 'left', agent_left), ('Time', 'right', time_anchor),
            ('Search', 'right', 215), ('Path', 'right', 274),
            ('Best', 'center', 296),
        ]
        for text, alignment, anchor in header_specs:
            rendered = self.table_font.render(text, True, (235, 235, 240))
            if alignment == 'right':
                position = (anchor - rendered.get_width(), 500)
            elif alignment == 'center':
                position = (anchor - rendered.get_width() // 2, 500)
            else:
                position = (anchor, 500)
            self.screen.blit(rendered, (position[0], table_y + 25))
        row_y = table_y + 40
        mouse = pygame.mouse.get_pos()
        for name in self.selected_agents:
            rect = pygame.Rect(8, row_y, SIDEBAR_W - 16, 29)
            color = (145, 90, 190) if name == self.current_agent else ((115, 115, 150) if rect.collidepoint(mouse) else (165, 165, 165))
            pygame.draw.rect(self.screen, color, rect)
            rows = self.results.get(name, [])
            errors = [row['error'] for row in rows if 'error' in row]
            if errors:
                values = [name, errors[0], errors[0], errors[0], errors[0]]
            else:
                runtime = sum(row.get('runtime', 0) for row in rows)
                if self.running and name == self.pending_agent:
                    runtime += time.monotonic() - self.pending_started
                runtime_text = f'{runtime:.3f}' if rows or runtime else '-'
                explored = f'{sum(len(row.get("explored", [])) for row in rows) / len(rows):.1f}' if rows else '-'
                paths = [self._path_cost(row.get('path')) for row in rows if row.get('path')]
                path = f'{sum(paths) / len(paths):.1f}' if paths else '-'
                optimal = 'Yes' if rows and all(row.get('optimal', False) for row in rows) else 'No'
                values = [name, runtime_text, explored, path, optimal]
            display_values = list(values)
            display_values[0] = self._fit_table_text(
                display_values[0], agent_right - agent_left
            )
            for index, (value, spec) in enumerate(zip(display_values, header_specs)):
                text = self.table_font.render(str(value), True, COLOR_TEXT)
                _, alignment, anchor = spec
                if alignment == 'right':
                    position = (anchor - text.get_width(), row_y + 7)
                elif alignment == 'center':
                    position = (anchor - text.get_width() // 2, row_y + 7)
                else:
                    position = (anchor, row_y + 7)
                if index == 0:
                    self.screen.set_clip(pygame.Rect(
                        agent_left, row_y + 7,
                        agent_right - agent_left, text.get_height()
                    ))
                    self.screen.blit(text, position)
                    self.screen.set_clip(None)
                else:
                    self.screen.blit(text, position)
            row_y += 31

    def _fit_table_text(self, value, max_width):
        value = str(value)
        if self.table_font.size(value)[0] <= max_width:
            return value
        while value and self.table_font.size(value + '...')[0] > max_width:
            value = value[:-1]
        return value + '...'

    def draw(self, screen):
        screen.fill((30, 30, 36))
        pygame.draw.rect(screen, (22, 22, 28), pygame.Rect(0, 0, SIDEBAR_W, SCREEN_H))
        pygame.draw.line(screen, (60, 60, 80), (SIDEBAR_W, 0), (SIDEBAR_W, SCREEN_H), 1)
        self._draw_grid()
        self._draw_table()
        self._draw_run_spinner(screen)
        run_status = self._current_run_status()
        if run_status:
            status = self.font.render(run_status, True, (235, 170, 110))
            screen.blit(status, (SIDEBAR_W + 12, MAP_TOP + 8))
        if self.warning_msg and pygame.time.get_ticks() - self.warning_time < 3000:
            warning = self.font.render(self.warning_msg, True, (145, 20, 20))
            screen.blit(warning, (SIDEBAR_W + 12, SCREEN_H - 30))
