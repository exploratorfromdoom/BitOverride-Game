import os
import ast
import re
import pygame
from os import listdir
from os.path import isfile, join
pygame.init()

pygame.display.set_caption("Platformer")

WIDTH, HEIGHT = 1200, 710
FPS = 60
PLAYER_VEL = 5

window = pygame.display.set_mode((WIDTH, HEIGHT))

# Font for HUD
FONT = pygame.font.SysFont(None, 36)

# Caches to avoid repeated image loads / transforms
_BLOCK_CACHE = {}
_END_CACHE = {}
_COLLECTIBLE_CACHE = {}
_ENEMY_CACHE = {}


def flip(sprites):
    """Inverte horizontalmente cada surface na lista `sprites`.

    Retorna uma nova lista com as sprites viradas para a direita.
    """
    return [pygame.transform.flip(sprite, True, False) for sprite in sprites]


def load_sprite_sheets(dir1, dir2, width, height, direction=False):
    """Carrega spritesheets da pasta especificada e retorna um dicionário.

    Cada ficheiro PNG na pasta é cortado em frames de `width`x`height` e escalado.
    Se `direction` for True, adiciona versões _left e _right.
    """

    path = join("assets", dir1, dir2)
    images = [f for f in listdir(path) if isfile(join(path, f))]

    all_sprites = {}

    for image in images:
        sprite_sheet = pygame.image.load(join(path, image)).convert_alpha()

        sprites = []
        for i in range(sprite_sheet.get_width() // width):
            surface = pygame.Surface((width, height), pygame.SRCALPHA, 32)
            rect = pygame.Rect(i * width, 0, width, height)
            surface.blit(sprite_sheet, (0, 0), rect)
            sprites.append(pygame.transform.scale2x(surface))

        if direction:
            all_sprites[image.replace(".png", "") + "_right"] = sprites
            all_sprites[image.replace(".png", "") + "_left"] = flip(sprites)
        else:
            all_sprites[image.replace(".png", "")] = sprites

    return all_sprites


def get_block(size):
    """Carrega e retorna o tile de terreno com lado `size` (cacheado).

    Evita recarregar/transformar a imagem para cada bloco.
    """

    if size in _BLOCK_CACHE:
        return _BLOCK_CACHE[size]

    path = join("assets", "Terrain", "Terrain.png")
    image = pygame.image.load(path).convert_alpha()
    surface = pygame.Surface((size, size), pygame.SRCALPHA, 32)
    rect = pygame.Rect(96, 0, size, size)
    surface.blit(image, (0, 0), rect)
    scaled = pygame.transform.scale2x(surface)
    _BLOCK_CACHE[size] = scaled
    return scaled


class Player(pygame.sprite.Sprite):
    """Representa o jogador — controla movimento, física e sprite/estado.

    A classe gerencia velocidade, salto duplo, animações e colisões.
    """
    COLOR = (255, 0, 0)
    GRAVITY = 1
    SPRITES = load_sprite_sheets("MainCharacters", "MaskDude", 32, 32, True)
    ANIMATION_DELAY = 3

    def __init__(self, x, y, width, height):
        super().__init__()
        self.rect = pygame.Rect(x, y, width, height)
        self.x_vel = 0
        self.y_vel = 0
        self.mask = None
        self.direction = "left"
        self.animation_count = 0
        self.fall_count = 0
        self.jump_count = 0
        self.hit = False
        self.hit_count = 0
        self.won = False
        self.score = 0
        self.dead = False
        self.score = 0

    def jump(self):
        self.y_vel = -self.GRAVITY * 8
        self.animation_count = 0
        self.jump_count += 1
        if self.jump_count == 1:
            self.fall_count = 0

    def move(self, dx, dy):
        self.rect.x += dx
        self.rect.y += dy

    def make_hit(self):
        self.hit = True

    def move_left(self, vel):
        self.x_vel = -vel
        if self.direction != "left":
            self.direction = "left"
            self.animation_count = 0

    def move_right(self, vel):
        self.x_vel = vel
        if self.direction != "right":
            self.direction = "right"
            self.animation_count = 0

    def loop(self, fps):
        self.y_vel += min(1, (self.fall_count / fps) * self.GRAVITY)
        self.move(self.x_vel, self.y_vel)

        if self.hit:
            self.hit_count += 1
        if self.hit_count > fps * 2:
            self.hit = False
            self.hit_count = 0

        self.fall_count += 1
        self.update_sprite()

    def landed(self):
        self.fall_count = 0
        self.y_vel = 0
        self.jump_count = 0

    def hit_head(self):
        self.count = 0
        self.y_vel *= -1

    def update_sprite(self):
        sprite_sheet = "idle"
        if self.hit:
            sprite_sheet = "hit"
        elif self.y_vel < 0:
            if self.jump_count == 1:
                sprite_sheet = "jump"
            elif self.jump_count == 2:
                sprite_sheet = "double_jump"
        elif self.y_vel > self.GRAVITY * 2:
            sprite_sheet = "fall"
        elif self.x_vel != 0:
            sprite_sheet = "run"

        sprite_sheet_name = sprite_sheet + "_" + self.direction
        sprites = self.SPRITES[sprite_sheet_name]
        sprite_index = (self.animation_count //
                        self.ANIMATION_DELAY) % len(sprites)
        self.sprite = sprites[sprite_index]
        self.animation_count += 1
        self.update()

    def update(self):
        self.rect = self.sprite.get_rect(topleft=(self.rect.x, self.rect.y))
        self.mask = pygame.mask.from_surface(self.sprite)

    def draw(self, win, offset_x):
        win.blit(self.sprite, (self.rect.x - offset_x, self.rect.y))


class Object(pygame.sprite.Sprite):
    def __init__(self, x, y, width, height, name=None):
        """Base para objetos do nível com `rect`, `image` e `name` opcional.

        Usada para blocos, inimigos, colecionáveis e outros objetos estáticos.
        """
        super().__init__()
        self.rect = pygame.Rect(x, y, width, height)
        self.image = pygame.Surface((width, height), pygame.SRCALPHA)
        self.width = width
        self.height = height
        self.name = name

    def draw(self, win, offset_x):
        win.blit(self.image, (self.rect.x - offset_x, self.rect.y))


class Block(Object):
    def __init__(self, x, y, size):
        """Bloco de terreno: desenha o tile de terreno dentro de seu `image`."""
        super().__init__(x, y, size, size)
        block = get_block(size)
        self.image.blit(block, (0, 0))
        self.mask = pygame.mask.from_surface(self.image)


class Fire(Object):
    ANIMATION_DELAY = 3

    def __init__(self, x, y, width, height):
        """Armadilha de fogo animada; tem estados 'on' e 'off'."""
        super().__init__(x, y, width, height, "fire")
        self.fire = load_sprite_sheets("Traps", "Fire", width, height)
        self.image = self.fire["off"][0]
        self.mask = pygame.mask.from_surface(self.image)
        self.animation_count = 0
        self.animation_name = "off"

    def on(self):
        self.animation_name = "on"

    def off(self):
        self.animation_name = "off"

    def loop(self):
        sprites = self.fire[self.animation_name]
        sprite_index = (self.animation_count //
                        self.ANIMATION_DELAY) % len(sprites)
        self.image = sprites[sprite_index]
        self.animation_count += 1

        self.rect = self.image.get_rect(topleft=(self.rect.x, self.rect.y))
        self.mask = pygame.mask.from_surface(self.image)

        if self.animation_count // self.ANIMATION_DELAY > len(sprites):
            self.animation_count = 0


class End(Object):
    def __init__(self, x, y, size, image_path=None):
        """Objeto de fim de nível (troféu). Colidir com ele vence o nível."""
        super().__init__(x, y, size, size, "end")
        # Resolve image path if provided, else try project-relative default
        if image_path and os.path.exists(image_path):
            img = pygame.image.load(image_path).convert_alpha()
        else:
            # default location relative to project
            project_root = os.path.dirname(os.path.abspath(__file__))
            default_path = os.path.join(project_root, "assets", "Items", "Checkpoints", "End", "End (Idle).png")
            img = pygame.image.load(default_path).convert_alpha()

        # scale to fit block, cache by (path, size)
        cache_key = (image_path or "default", size)
        if cache_key in _END_CACHE:
            self.image = _END_CACHE[cache_key]
        else:
            img = pygame.transform.scale(img, (size, size))
            _END_CACHE[cache_key] = img
            self.image = img

        self.mask = pygame.mask.from_surface(self.image)


class Collectible(Object):
    def __init__(self, x, y, size, image_path=None):
        """Item colecionável; some ao ser recolhido e aumenta a pontuação."""
        super().__init__(x, y, size, size, "collectible")
        # try provided path, otherwise project-relative default
        if image_path and os.path.exists(image_path):
            img = pygame.image.load(image_path).convert_alpha()
        else:
            project_root = os.path.dirname(os.path.abspath(__file__))
            default_path = os.path.join(project_root, "assets", "Traps", "Spiked Ball", "Spiked Ball.png")
            img = pygame.image.load(default_path).convert_alpha()

        cache_key = (image_path or "default", size)
        if cache_key in _COLLECTIBLE_CACHE:
            self.image = _COLLECTIBLE_CACHE[cache_key]
        else:
            img = pygame.transform.scale(img, (size, size))
            _COLLECTIBLE_CACHE[cache_key] = img
            self.image = img

        self.mask = pygame.mask.from_surface(self.image)


class Enemy(Object):
    def __init__(self, x, y, size, image_path=None):
        """Inimigo estático/patrulhante que mata o jogador ao contato."""
        super().__init__(x, y, size, size, "enemy")
        # try provided path, otherwise project-relative default
        if image_path and os.path.exists(image_path):
            img = pygame.image.load(image_path).convert_alpha()
        else:
            project_root = os.path.dirname(os.path.abspath(__file__))
            default_path = os.path.join(project_root, "assets", "Traps", "Spike Head", "Idle.png")
            img = pygame.image.load(default_path).convert_alpha()

        cache_key = (image_path or "default", size)
        if cache_key in _ENEMY_CACHE:
            self.image = _ENEMY_CACHE[cache_key]
        else:
            img = pygame.transform.scale(img, (size, size))
            _ENEMY_CACHE[cache_key] = img
            self.image = img

        self.mask = pygame.mask.from_surface(self.image)
        # patrol defaults; will be overridden by caller if needed
        self.start_x = self.rect.x
        self.patrol_distance = size * 2
        self.speed = 2
        self.direction = 1

    def loop(self):
        # initialize start_x if not set
        if not hasattr(self, "start_x"):
            self.start_x = self.rect.x

        self.rect.x += self.speed * self.direction

        # reverse at patrol boundaries
        if self.rect.x > self.start_x + self.patrol_distance:
            self.rect.x = self.start_x + self.patrol_distance
            self.direction = -1
        elif self.rect.x < self.start_x:
            self.rect.x = self.start_x
            self.direction = 1

        # update mask after moving
        self.rect = self.image.get_rect(topleft=(self.rect.x, self.rect.y))
        self.mask = pygame.mask.from_surface(self.image)


def get_background(name):
    """Carrega e retorna posições de tile e a imagem de fundo `name`.

    Retorna uma tupla `(tiles, image)` onde `tiles` é a lista de coordenadas
    para desenhar repetidamente a imagem de background para preencher a tela.
    """

    image = pygame.image.load(join("assets", "Background", name))
    _, _, width, height = image.get_rect()
    tiles = []

    for i in range(WIDTH // width + 1):
        for j in range(HEIGHT // height + 1):
            pos = (i * width, j * height)
            tiles.append(pos)

    return tiles, image


def draw(window, background, bg_image, player, objects, offset_x):
    """Desenha o background, objetos, jogador e HUD (pontuação)."""

    for tile in background:
        window.blit(bg_image, tile)

    for obj in objects:
        obj.draw(window, offset_x)

    player.draw(window, offset_x)

    # Draw score HUD
    try:
        score_text = FONT.render(f"Score: {player.score}", True, (255, 255, 255))
        window.blit(score_text, (10, 10))
    except Exception:
        pass

    pygame.display.update()


def show_win_screen(window, bg_image, objects):
    """Mostra uma tela de vitória com o troféu e espera por tecla para sair."""
    font = pygame.font.SysFont(None, 72)
    small = pygame.font.SysFont(None, 36)

    # Find trophy image from objects if present
    trophy = None
    for obj in objects:
        if getattr(obj, "name", None) == "end":
            trophy = obj.image
            break

    overlay = pygame.Surface((WIDTH, HEIGHT))
    overlay.fill((0, 0, 0))
    overlay.set_alpha(200)

    waiting = True
    clock = pygame.time.Clock()
    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                quit()
            if event.type == pygame.KEYDOWN:
                waiting = False

        window.blit(bg_image, (0, 0))
        window.blit(overlay, (0, 0))

        if trophy:
            tw, th = trophy.get_size()
            tx = (WIDTH - tw) // 2
            ty = HEIGHT // 4
            window.blit(trophy, (tx, ty))

        text = font.render("You Win!", True, (255, 215, 0))
        sub = small.render("Press any key to exit", True, (255, 255, 255))
        window.blit(text, ((WIDTH - text.get_width()) // 2, HEIGHT // 2))
        window.blit(sub, ((WIDTH - sub.get_width()) // 2, HEIGHT // 2 + 80))

        pygame.display.update()
        clock.tick(30)


def show_lose_screen(window, bg_image, objects):
    """Mostra uma tela de derrota e espera por tecla para sair."""
    font = pygame.font.SysFont(None, 72)
    small = pygame.font.SysFont(None, 36)

    overlay = pygame.Surface((WIDTH, HEIGHT))
    overlay.fill((0, 0, 0))
    overlay.set_alpha(200)

    waiting = True
    clock = pygame.time.Clock()
    # Return True to restart level, False to quit
    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                # any key restarts the level
                return True

        window.blit(bg_image, (0, 0))
        window.blit(overlay, (0, 0))

        text = font.render("You Lost!", True, (220, 20, 60))
        sub = small.render("Press any key to restart or close window to quit", True, (255, 255, 255))
        window.blit(text, ((WIDTH - text.get_width()) // 2, HEIGHT // 2))
        window.blit(sub, ((WIDTH - sub.get_width()) // 2, HEIGHT // 2 + 80))

        pygame.display.update()
        clock.tick(30)


def load_level(path, block_size):
    """Carrega um nível a partir de `path` e retorna (player_pos, objects).

    Suporta formatos: uma grelha simples de caracteres, linhas entre aspas
    ou um literal Python `[...]` (ex.: `MAPA_LONGO = ["....", ...]`).
    Símbolos: `P` jogador, `B`/`#` bloco, `F` fim, `Q` colecionável, `E` inimigo.
    """

    if not os.path.exists(path):
        return None, []

    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    rows = []

    # Try to parse a Python list literal (e.g. MAPA_LONGO = ["....", "...."])
    try:
        if "[" in text and "]" in text:
            list_text = text[text.index("["): text.rindex("]") + 1]
            data = ast.literal_eval(list_text)
            if isinstance(data, list) and all(isinstance(s, str) for s in data):
                rows = data
    except Exception:
        rows = []

    # Fallback: extract quoted lines or use plain file lines
    if not rows:
        # Try to find all quoted strings
        quoted = re.findall(r'"([^"]+)"', text)
        if quoted:
            rows = quoted
        else:
            rows = [line.rstrip("\n") for line in text.splitlines() if line.strip() != ""]

    level_height = len(rows)
    base_y = HEIGHT - level_height * block_size

    objects = []
    player_pos = None

    for row_i, row in enumerate(rows):
        for col_i, ch in enumerate(row):
            x = col_i * block_size
            y = base_y + row_i * block_size
            if ch == "P":
                player_pos = (x, y)
            elif ch in ("B", "#"):
                objects.append(Block(x, y, block_size))
            elif ch == "F":
                # Create an end/trophy at this cell. Use project-relative asset if available.
                project_root = os.path.dirname(os.path.abspath(path))
                trophy_path = os.path.join(project_root, "assets", "Items", "Checkpoints", "End", "End (Idle).png")
                end_obj = End(x, y, block_size, image_path=trophy_path)
                objects.append(end_obj)
            elif ch == "Q":
                # Create a collectible centered in the cell
                csize = block_size // 2
                cx = x + (block_size - csize) // 2
                cy = y + (block_size - csize) // 2
                project_root = os.path.dirname(os.path.abspath(path))
                collect_path = os.path.join(project_root, "assets", "Traps", "Spiked Ball", "Spiked Ball.png")
                col = Collectible(cx, cy, csize, image_path=collect_path)
                objects.append(col)
            elif ch == "E":
                # Create an enemy in this cell with a 2-block patrol
                esize = block_size
                project_root = os.path.dirname(os.path.abspath(path))
                enemy_path = os.path.join(project_root, "assets", "Traps", "Spike Head", "Idle.png")
                enemy = Enemy(x, y, esize, image_path=enemy_path)
                # set patrol distance to 2 blocks and a moderate speed
                enemy.patrol_distance = block_size * 2
                enemy.speed = 2
                enemy.start_x = x
                objects.append(enemy)

    return player_pos, objects


def handle_vertical_collision(player, objects, dy):
    """Verifica colisões verticais do `player` com `objects`.

    Se o jogador descer (dy>0) é colocado em cima do objeto; se subir, bate a cabeça.
    Retorna a lista de objetos com os quais houve colisão vertical.
    """

    collided_objects = []
    for obj in objects:
        if player.rect.colliderect(obj.rect) and pygame.sprite.collide_mask(player, obj):
            if dy > 0:
                player.rect.bottom = obj.rect.top
                player.landed()
            elif dy < 0:
                player.rect.top = obj.rect.bottom
                player.hit_head()

            collided_objects.append(obj)

    return collided_objects


def collide(player, objects, dx):
    """Move temporariamente o jogador em x (`dx`) e testa colisão.

    Retorna o objeto colidido (ou None), e restaura a posição do jogador.
    """

    player.move(dx, 0)
    player.update()
    collided_object = None
    for obj in objects:
        if player.rect.colliderect(obj.rect) and pygame.sprite.collide_mask(player, obj):
            collided_object = obj
            break

    player.move(-dx, 0)
    player.update()
    return collided_object


def handle_move(player, objects):
    """Lê input do teclado e aplica movimento horizontal e verificações.

    Controla movimento à esquerda/direita, checa colisões horizontais e verticais
    e trata efeitos (fogo, fim, colecionáveis, inimigos).
    """

    keys = pygame.key.get_pressed()

    player.x_vel = 0
    collide_left = collide(player, objects, -PLAYER_VEL * 2)
    collide_right = collide(player, objects, PLAYER_VEL * 2)

    if keys[pygame.K_LEFT] and not collide_left:
        player.move_left(PLAYER_VEL)
    if keys[pygame.K_RIGHT] and not collide_right:
        player.move_right(PLAYER_VEL)

    vertical_collide = handle_vertical_collision(player, objects, player.y_vel)
    to_check = [collide_left, collide_right, *vertical_collide]

    for obj in to_check:
        if obj and obj.name == "fire":
            player.make_hit()
        if obj and obj.name == "end":
            player.won = True
        if obj and obj.name == "collectible":
            # collect the item: increment score and remove it
            player.score += 1
            if obj in objects:
                try:
                    objects.remove(obj)
                except ValueError:
                    pass
        if obj and obj.name == "enemy":
            # touching an enemy causes immediate loss
            player.dead = True


def main(window):
    """Função principal: inicializa o nível, loop do jogo e trata encerramento."""

    clock = pygame.time.Clock()
    background, bg_image = get_background("Blue.png")

    block_size = 96

    # Resolve map path relative to this script so it loads correctly
    script_dir = os.path.dirname(os.path.abspath(__file__))
    map_path = os.path.join(script_dir, "map.txt")
    player_start, map_objects = load_level(map_path, block_size)

    print(f"Loaded map: {map_path}, player_start={player_start}, objects={len(map_objects)}")

    if player_start:
        player = Player(player_start[0], player_start[1], 50, 50)
    else:
        player = Player(100, 100, 50, 50)

    # Use parsed map objects if present, otherwise fall back to default demo objects
    if map_objects:
        objects = map_objects
    else:
        fire = Fire(100, HEIGHT - block_size - 64, 16, 32)
        fire.on()
        floor = [Block(i * block_size, HEIGHT - block_size, block_size)
                 for i in range(-WIDTH // block_size, (WIDTH * 2) // block_size)]
        objects = [*floor, Block(0, HEIGHT - block_size * 2, block_size),
                   Block(block_size * 3, HEIGHT - block_size * 4, block_size), fire]

    # compute level horizontal bounds from objects
    if objects:
        min_x = min(obj.rect.left for obj in objects)
        max_x = max(obj.rect.right for obj in objects)
    else:
        min_x = 0
        max_x = WIDTH
    level_width = max_x - min_x

    offset_x = 0
    scroll_area_width = 200

    run = True
    while run:
        clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False
                break

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE and player.jump_count < 2:
                    player.jump()

        player.loop(FPS)
        for obj in objects:
            if hasattr(obj, "loop"):
                obj.loop()

        # handle input / movement once per frame
        handle_move(player, objects)

        # Enemy collision -> immediate loss
        if getattr(player, "dead", False):
            show_lose_screen(window, bg_image, objects)
            run = False
            break

        # Losing condition: fell off the bottom of the screen
        if player.rect.top > HEIGHT:
            restart = show_lose_screen(window, bg_image, objects)
            if restart:
                # reload level fresh
                player_start, map_objects = load_level(map_path, block_size)
                if player_start:
                    player = Player(player_start[0], player_start[1], 50, 50)
                else:
                    player = Player(100, 100, 50, 50)
                objects = map_objects if map_objects else objects
                offset_x = 0
                # recompute level bounds
                if objects:
                    min_x = min(obj.rect.left for obj in objects)
                    max_x = max(obj.rect.right for obj in objects)
                else:
                    min_x = 0
                    max_x = WIDTH
                level_width = max_x - min_x
                continue
            else:
                run = False
                break

        if player.won:
            # show win screen and wait for key or quit
            show_win_screen(window, bg_image, objects)
            run = False
            break
        draw(window, background, bg_image, player, objects, offset_x)

        # Camera: center player on screen but clamp to level bounds
        desired = player.rect.centerx - (WIDTH // 2)
        if level_width <= WIDTH:
            offset_x = min_x
        else:
            if desired < min_x:
                offset_x = min_x
            elif desired > max_x - WIDTH:
                offset_x = max_x - WIDTH
            else:
                offset_x = int(desired)

    pygame.quit()
    quit()


if __name__ == "__main__":
    main(window)
