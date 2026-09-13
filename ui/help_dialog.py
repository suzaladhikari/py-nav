import pygame


class HelpOverlay:
    def __init__(self, screen, title, paragraphs):
        self.screen = screen
        self.title = title
        self.paragraphs = paragraphs
        self.scroll = 0
        self.font = pygame.font.SysFont(None, 22, bold=False)
        self.title_font = pygame.font.SysFont(None, 30, bold=False)
        self.line_height = 28
        self.rect = pygame.Rect(150, 70, 900, 620)
        self.close_rect = pygame.Rect(self.rect.right - 150, self.rect.top + 12, 130, 35)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 4:
                self.scroll = max(0, self.scroll - 3)
            elif event.button == 5:
                self.scroll += 3
            elif event.button == 1 and (self.close_rect.collidepoint(event.pos)
                                         or not self.rect.collidepoint(event.pos)):
                self.scroll = 0
                return True
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.scroll = 0
            return True
        return False

    def draw(self):
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self.screen.blit(overlay, (0, 0))
        pygame.draw.rect(self.screen, (35, 35, 44), self.rect)
        pygame.draw.rect(self.screen, (155, 220, 245), self.rect, 2)
        title = self.title_font.render(self.title, True, (245, 245, 245))
        self.screen.blit(title, (self.rect.x + 20, self.rect.y + 16))
        close_font = pygame.font.SysFont(None, 18, bold=False)
        close = close_font.render('Close (Esc)', True, (210, 210, 210))
        self.screen.blit(close, close.get_rect(center=self.close_rect.center))

        content = pygame.Surface((self.rect.width - 40, self.rect.height - 75), pygame.SRCALPHA)
        y = -self.scroll * self.line_height
        max_width = content.get_width()
        for paragraph in self.paragraphs:
            for source_line in paragraph.split('\n'):
                words = source_line.split()
                line = ''
                for word in words:
                    candidate = f'{line} {word}'.strip()
                    if line and self.font.size(candidate)[0] > max_width:
                        text = self.font.render(line, True, (235, 235, 240))
                        content.blit(text, (0, y))
                        y += self.line_height
                        line = word
                    else:
                        line = candidate
                if line:
                    text = self.font.render(line, True, (235, 235, 240))
                    content.blit(text, (0, y))
                    y += self.line_height
            y += self.line_height // 2
        clip = pygame.Rect(self.rect.x + 20, self.rect.y + 62,
                           self.rect.width - 40, self.rect.height - 82)
        self.screen.set_clip(clip)
        self.screen.blit(content, clip.topleft)
        self.screen.set_clip(None)
