# Py-Nav

Py-Nav is a small pygame laboratory for exploring how pathfinding algorithms behave on different grid maps. The important questions are not only which agent finds a solution, but also how much it searches and whether its solution is optimal under the map's movement rules.

## Running the app

From this folder, run:

```text
python main.py
```

Use **Edit Map** to create and save YAML maps. Use **Run Agents** to select a map, choose agents, and compare identical randomly generated start and goal pairs. The **Help** button in each screen contains the relevant quick instructions.

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

The package discovers agent subclasses automatically when the app starts, so no central registry edit is required. A minimal shape is:

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

Run the tests with:

```text
python -m unittest discover -s unit_test -v
```

The existing tests check map movement rules, YAML persistence, validation, agent behavior, and teleport editing. Add tests for any new agent or movement idea you introduce.
