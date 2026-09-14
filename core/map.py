import math
from typing import List, Tuple, Optional
from dataclasses import dataclass
from core.constants import DIAGONAL_COST

@dataclass
class Move:
    """A single possible move from a cell.

    Attributes:
        location: Destination coordinates (x, y).
        action: Direction code — 0=N, 1=E, 2=S, 3=W,
                4=NE, 5=SE, 6=SW, 7=NW.
        cost: Movement cost - 
               1.0 for orthogonal,
               either 1.0 or sqrt(2) for diagonal (depending on map settings).
    """
    location: Tuple[int, int]
    action: int
    cost: float

class Map:
    """A 2-D grid map for pathfinding.

    Grid cells are single-character strings:
        ``'-'``  empty, ``'#'`` wall, ``'@'`` start, ``'!'`` goal,
        ``'$'`` both start AND goal,
        ``'A'``-``'Z'`` teleport gates (pairs auto-link).

    Constructor options control movement rules:
        wrap: allow agents to wrap around map edges.
        diagonal_moves: allow diagonal steps.
        diagonal_move_true_cost: use sqrt(2) for diagonal steps (vs 1.0).
        min_distance: optional constraint checked during validation.

    Attributes:
        map: 2-D list of cell characters (row-major).
        width, height: grid dimensions.
        current_start, current_goal: active start/goal coordinates.
    """

    def __init__(
        self,
        grid: List[List[str]],
        wrap: bool = False,
        diagonal_moves: bool = True,
        diagonal_move_true_cost: bool = True,
        min_distance: int = 0
    ):
        self.map = grid
        self.height = len(self.map)
        self.width = len(self.map[0]) if self.height > 0 else 0
        self.wrap = wrap
        self.diagonal_moves = diagonal_moves
        self.diagonal_move_true_cost = diagonal_move_true_cost
        self.min_distance = min_distance

        self.current_start: Optional[Tuple[int, int]] = None
        self.current_goal: Optional[Tuple[int, int]] = None

    def get_start(self) -> Tuple[int, int]:
        return self.current_start

    def get_goal(self) -> Tuple[int, int]:
        return self.current_goal

    def set_start_goal(self, start: Tuple[int, int], goal: Tuple[int, int]):
        self.current_start = start
        self.current_goal = goal

    def is_start(self, x: int, y: int) -> bool:
        return self.current_start == (x, y)

    def is_goal(self, x: int, y: int) -> bool:
        return self.current_goal == (x, y)

    def is_wall(self, x: int, y: int) -> bool:
        return self.map[y][x] == '#'

    def is_teleport(self, x: int, y: int) -> bool:
        cell = self.map[y][x]
        return cell.isalpha() and cell.isupper()

    def get_teleport_destination(self, x: int, y: int) -> Optional[Tuple[int, int]]:
        if not self.is_teleport(x, y):
            return None
        target_id = self.map[y][x]
        for ry in range(self.height):
            for rx in range(self.width):
                if (rx, ry) != (x, y) and self.map[ry][rx] == target_id:
                    return (rx, ry)
        return None

    def get_valid_moves(self, x: int, y: int) -> List[Move]:
        moves = []
        
        # Directions: 0=N, 1=E, 2=S, 3=W, 4=NE, 5=SE, 6=SW, 7=NW
        # Coordinates: (dx, dy)
        ortho_dirs = [
            (0, 0, -1), (1, 1, 0), (2, 0, 1), (3, -1, 0)
        ]
        diag_dirs = [
            (4, 1, -1), (5, 1, 1), (6, -1, 1), (7, -1, -1)
        ]

        def get_wrapped_coords(nx: int, ny: int) -> Optional[Tuple[int, int]]:
            if self.wrap:
                return nx % self.width, ny % self.height
            elif 0 <= nx < self.width and 0 <= ny < self.height:
                return nx, ny
            return None

        # Check orthogonal moves
        for action, dx, dy in ortho_dirs:
            coords = get_wrapped_coords(x + dx, y + dy)
            if coords:
                nx, ny = coords
                if not self.is_wall(nx, ny):
                    cost = 1.0
                    target_loc = (nx, ny)
                    if self.is_teleport(nx, ny):
                        dest = self.get_teleport_destination(nx, ny)
                        if dest:
                            target_loc = dest
                    moves.append(Move(location=target_loc, action=action, cost=cost))

        # Check diagonal moves
        if self.diagonal_moves:
            for action, dx, dy in diag_dirs:
                coords = get_wrapped_coords(x + dx, y + dy)
                if coords:
                    nx, ny = coords
                    if not self.is_wall(nx, ny):
                        # Diagonal allowed unless both adjacent orthogonal cells are walls
                        # e.g., moving (1,1) -> (2,2) means dx=1, dy=1
                        # adjacent orthogonals are (x+dx, y) and (x, y+dy)
                        adj1 = get_wrapped_coords(x + dx, y)
                        adj2 = get_wrapped_coords(x, y + dy)
                        
                        blocked = False
                        if adj1 and adj2:
                            if self.is_wall(*adj1) and self.is_wall(*adj2):
                                blocked = True
                                
                        if not blocked:
                            cost = DIAGONAL_COST if self.diagonal_move_true_cost else 1.0
                            target_loc = (nx, ny)
                            if self.is_teleport(nx, ny):
                                dest = self.get_teleport_destination(nx, ny)
                                if dest:
                                    target_loc = dest
                            moves.append(Move(location=target_loc, action=action, cost=cost))

        return moves
