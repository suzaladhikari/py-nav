import sys
import os

# Ensure root directory is on sys.path when main.py runs from main/ subfolder.
_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

import pygame
import pygame_gui
from ui.map_editor import MapEditor
from ui.sim_view import SimulationView
from utils.session_state import load_session_state

def main():
    pygame.init()
    screen = pygame.display.set_mode((1200, 768))
    pygame.display.set_caption("Py-Nav")
    clock = pygame.time.Clock()

    manager = pygame_gui.UIManager((1200, 768), "ui/theme.json")

    session_state = load_session_state()
    if session_state.get('active_view') == 'simulation':
        current_view = SimulationView(screen, manager)
    else:
        current_view = MapEditor(screen, manager)

    running = True
    while running:
        time_delta = clock.tick(120)/1000.0
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                current_view._save_session(
                    'simulation' if isinstance(current_view, SimulationView) else 'editor'
                )
                running = False
            
            if current_view.help_overlay:
                current_view.handle_event(event)
                continue

            manager.process_events(event)
            
            next_view_class = current_view.handle_event(event)
            if next_view_class:
                manager.clear_and_reset()
                current_view = next_view_class(screen, manager)

        manager.update(time_delta)
        current_view.update()
        
        current_view.draw(screen)
        manager.draw_ui(screen)
        if current_view.help_overlay:
            current_view.help_overlay.draw()

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()
