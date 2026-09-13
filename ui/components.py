import pygame

class Button:
    def __init__(self, x, y, width, height, text, font, color, hover_color, text_color):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.font = font
        self.color = color
        self.hover_color = hover_color
        self.text_color = text_color
        self.is_hovered = False
        self.is_active = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.is_hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self.is_hovered:
                return True
        return False

    def draw(self, screen):
        bg_color = self.hover_color if (self.is_hovered or self.is_active) else self.color
        pygame.draw.rect(screen, bg_color, self.rect)
        pygame.draw.rect(screen, (0, 0, 0), self.rect, 2)
        text_surf = self.font.render(self.text, True, self.text_color)
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)

class TextInput:
    def __init__(self, x, y, width, height, text, font):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.font = font
        self.color = (255, 255, 255)
        self.active_color = (200, 255, 200)
        self.is_active = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                self.is_active = self.rect.collidepoint(event.pos)
        elif event.type == pygame.KEYDOWN and self.is_active:
            if event.key == pygame.K_RETURN:
                self.is_active = False
            elif event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            else:
                # Basic filename character filtering
                if event.unicode.isalnum() or event.unicode in "-_":
                    self.text += event.unicode
        return False

    def draw(self, screen):
        bg = self.active_color if self.is_active else self.color
        pygame.draw.rect(screen, bg, self.rect)
        pygame.draw.rect(screen, (0, 0, 0), self.rect, 2)
        text_surf = self.font.render(self.text, True, (0, 0, 0))
        screen.blit(text_surf, (self.rect.x + 5, self.rect.y + 5))

class Dropdown:
    def __init__(self, x, y, width, height, options, font, selected_index=0):
        self.rect = pygame.Rect(x, y, width, height)
        self.options = options
        self.font = font
        self.selected_index = selected_index
        self.is_open = False
        self.color = (220, 220, 220)
        self.hover_color = (180, 180, 180)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.is_open:
                for i in range(len(self.options)):
                    opt_rect = pygame.Rect(self.rect.x, self.rect.y + (i+1)*self.rect.height, self.rect.width, self.rect.height)
                    if opt_rect.collidepoint(event.pos):
                        self.selected_index = i
                        self.is_open = False
                        return True
                self.is_open = False
            else:
                if self.rect.collidepoint(event.pos):
                    self.is_open = True
        return False

    def get_selected(self):
        if 0 <= self.selected_index < len(self.options):
            return self.options[self.selected_index]
        return None

    def draw(self, screen):
        pygame.draw.rect(screen, self.color, self.rect)
        pygame.draw.rect(screen, (0,0,0), self.rect, 2)
        text = self.get_selected() if self.options else ""
        text_surf = self.font.render(text, True, (0,0,0))
        screen.blit(text_surf, (self.rect.x + 5, self.rect.y + 5))

        if self.is_open:
            for i, opt in enumerate(self.options):
                opt_rect = pygame.Rect(self.rect.x, self.rect.y + (i+1)*self.rect.height, self.rect.width, self.rect.height)
                mouse_pos = pygame.mouse.get_pos()
                color = self.hover_color if opt_rect.collidepoint(mouse_pos) else (240,240,240)
                pygame.draw.rect(screen, color, opt_rect)
                pygame.draw.rect(screen, (0,0,0), opt_rect, 1)
                opt_surf = self.font.render(opt, True, (0,0,0))
                screen.blit(opt_surf, (opt_rect.x + 5, opt_rect.y + 5))

