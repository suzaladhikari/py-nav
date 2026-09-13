# Py-Nav

Py-Nav is a small pygame laboratory for exploring how pathfinding algorithms behave on different grid maps. The important questions are not only which agent finds a solution, but also how much it searches and whether its solution is optimal under the map's movement rules.

## Prerequisites

- **Python 3.10+** — nothing else is required to run the app.

## Quick start

```text
python run.py
```

or on Linux / macOS:

```text
python3 run.py
```

`run.py` handles everything automatically:

1. If required packages (pygame, pygame_gui, pyyaml) are already installed in your global Python, the app launches directly.
2. Otherwise, a **virtual environment** is created, dependencies are installed (with a spinner animation), and the app runs inside it.
3. If a virtual environment exists but its dependencies are broken, it is removed and rebuilt automatically (up to 3 attempts).

If setup fails, run the installer manually:

```text
python setup.py --force
```

Then try `python run.py` again.

## Your assignment

Create maps that make the algorithms behave differently. Start with small maps that let you predict the result before running the experiment. Useful map families include:

- open grids, with and without diagonal movement
- long corridors and mazes
- dead ends that make DFS commit to a poor branch
- maps where DFS happens to find the goal quickly, even though its path is not optimal
- maps with diagonal moves whose true cost is either 1 or the Euclidean diagonal cost
- wrapping maps where the shortest route crosses an edge
- maps with teleport pairs that create cheap shortcuts
- disconnected maps and maps with difficult but valid start/goal pairs
- maps that make the Euclidean A* heuristic misleading, especially with wrapping or teleports

For each map, write down predictions before running it. Compare runtime, search effort, solution cost, and optimality. Explain surprising results in terms of the movement rules and the algorithm's data structure or heuristic.

Search is the number of locations for which an agent called `get_valid_moves`; it is the app's consistent measure of expanded nodes. Runtime is an approximate total for completed agent runs and includes process startup and communication overhead, so treat small runtime differences cautiously. Repeat an experiment with the same seed when comparing algorithm behavior rather than random start/goal selection.

Leave the **Random seed** field blank for a new experiment. Enter an integer when you want to reproduce the same generated start/goal pairs. Use the **Copy** button beside the results heading to copy a fixed-width table into a report or spreadsheet.

## Adding agents

Students can add their own agents in the `agents/` folder. Define a class that inherits from `core.agent.Agent` and implements `find_path`. Call `self.get_valid_moves(x, y)` whenever the agent expands a location; this records its exploration history for the animation. A class-level `name` is optional. If omitted, Py-Nav displays the class name.

The package discovers agent subclasses automatically at startup, so no central registry edit is required. A minimal shape is:

```python
from core.agent import Agent


class MyAgent(Agent):
    name = 'My agent'

    def find_path(self):
        # Starting location is self.start
        # Goal location is self.goal

        # Must explore using self.get_valid_moves(x, y).
        #  - when self.get_valid_moves(x, y) is called,
        #    the explored node is automatically added to
        #    agent exploration history.

        # self.get_valid_moves(x, y) returns a list of
        #   valid Move objects from location (x,y).
        #   Each Move object will have the following:
        #   - location: Tuple[int, int]
        #       this is a tuple with coordinates x,y
        #   - action: int
        #       action id signifying direction of move:
        #       0=N, 1=E, 2=S, 3=W, 4=NE, 5=SE, 6=SW, 7=NW
        #   - cost: float
        #       signifies travel distance for the move

        return None
```

## Running tests

```text
python -m unittest discover -s unit_test -v
```

The existing tests check map movement rules, YAML persistence, validation, agent behavior, and teleport editing. Add tests for any new agent or movement idea you introduce.

## Project structure

| File / folder                | Description                                                                                       |
|------------------------------|---------------------------------------------------------------------------------------------------|
| `run.py`                     | **Primary launcher.** Handles bootstrapping: dependency checking, venv creation, installation, and launch. Run this file to start the app. |
| `setup.py`                   | Standalone installer. Creates a virtual environment and installs pygame, pygame_gui, pyyaml. Accepts `--force` to recreate, `--verify` to check. |
| `main.py`                    | Entry point for the application itself. Contains the pygame init, event loop, and view management. Run automatically by `run.py` or `setup.py`. |
| `theme.json`                 | pygame_gui theme configuration (button colors, dropdown, text entry styles).                      |
| **`agents/`**                | Pathfinding agent implementations. Each file defines a class inheriting from `core.agent.Agent`. Discovered automatically at startup. |
| `agents/bfs.py`              | Breadth-first search agent (complete, optimal for unweighted grids).                              |
| `agents/dfs.py`              | Depth-first search agent (not complete, not optimal).                                             |
| `agents/dijkstra.py`         | Dijkstra's algorithm agent (complete, optimal for weighted grids).                                |
| `agents/astar.py`            | A* search with Euclidean distance heuristic (admissible on non-wrapping maps).                    |
| `agents/astar2.py`           | A* search with constant heuristic of 1 — effectively behaves like Dijkstra but labeled "A* (dumb)" for educational comparison. |
| **`core/`**                  | Core domain logic — agent base class, map model, and constants.                                   |
| `core/agent.py`              | Abstract `Agent` base class with `get_valid_moves()`, `mark_explored()`, `find_path()`, `run()`.  |
| `core/map.py`                | `Map` class: grid storage, movement rules (walls, wraparound, teleports, diagonals, weighted tiles). |
| `core/constants.py`          | Global constants (grid defaults, tile size, color definitions).                                   |
| **`ui/`**                    | User interface — pygame_gui screens and components.                                                 |
| `ui/map_editor.py`           | Edit Map screen: create, draw, resize, save maps.                                                 |
| `ui/sim_view.py`             | Run Agents screen: select agents, run simulations, animate exploration, view results table.       |
| `ui/components.py`           | Shared UI components.                                                                             |
| `ui/help_dialog.py`          | Help overlay dialog drawn on top of any screen.                                                   |
| **`utils/`**                 | Utility modules.                                                                                  |
| `utils/yaml_handler.py`      | Load and save map YAML files.                                                                     |
| `utils/session_state.py`     | Save and load `session_state.json` with atomic writes.                                            |
| `utils/validation.py`        | Validation helpers (Dijkstra-based minimum distance checking).                                    |
| **`maps/`**                  | Folder where saved YAML maps are stored. Created automatically on first map creation.             |
| **`unit_test/`**             | Unit test suite. Run with `python -m unittest discover -s unit_test -v`.                          |
