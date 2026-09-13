import math

# Grid defaults
DEFAULT_GRID_WIDTH = 10
DEFAULT_GRID_HEIGHT = 10
TILE_SIZE = 40

DIAGONAL_COST = math.sqrt(2)

# Colors
COLOR_BG_EMPTY = (0, 0, 0)         # Black
COLOR_BG_WALL = (128, 128, 128)    # Gray
COLOR_TP_TEXT = (0, 128, 128)      # Teal
COLOR_START_BG = (0, 0, 139)       # Dark Blue
COLOR_GOAL_ICON = (255, 0, 0)      # Red (for flag icon placeholder)

COLOR_EXPLORED = (128, 0, 128)     # Purple
COLOR_PREV_EXPLORED = (173, 216, 230) # Light blue
COLOR_PATH = (255, 255, 0)         # Yellow

# UI Colors
COLOR_UI_BG = (200, 200, 200)
COLOR_TEXT = (0, 0, 0)
