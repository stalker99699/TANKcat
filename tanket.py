import pygame
import random
import math
import json
import os
import time

pygame.init()

NEON_BLUE = (0, 150, 255)
NEON_BLUE_DARK = (0, 60, 140)
NEON_RED = (255, 50, 50)
NEON_RED_DARK = (160, 20, 20)
BLACK = (0, 0, 0)
WHITE = (220, 220, 230)
GRAY = (100, 100, 110)
WALL_COLOR = (55, 55, 80)
WALL_TOP = (85, 85, 115)
WALL_BOT = (30, 30, 50)
BG_COLOR = (10, 10, 22)

CELL = 18
CORRIDOR_W = 3
MAZE_COARSE = 8
MAZE_W = MAZE_COARSE * CORRIDOR_W * 2 + 1
MAZE_H = MAZE_COARSE * CORRIDOR_W * 2 + 1
WORLD_W = MAZE_W * CELL
WORLD_H = MAZE_H * CELL
SCREEN_W = 1200
SCREEN_H = 900
FPS = 60

PLAYER_SPEED = 5.2
BOT_SPEED = 2.9
SPRINT_MULT = 1.5
PLAYER_MAX_HP = 3
FIRE_RATE = 0.35
MAGAZINE = 6
RELOAD_TIME = 1.5
BULLET_SPEED = 30.0
BULLET_SPREAD = 2.5
MAX_BOUNCES = 3
TANK_RADIUS = 0.35
BULLET_HIT_RADIUS = 0.4
TURN_SPEED = 200.0
ZOOM_MIN = 0.4
ZOOM_MAX = 2.0
ZOOM_STEP = 0.1
SLOW_MO_FACTOR = 0.12
BOT_DETECT_RANGE = 14
BOT_BULLET_SENSE = 6.0
BOT_PATROL_CHANGE = 1.5

PATROL, CHASE, SEARCH = 0, 1, 2

def reflect(vx, vy, nx, ny):
    dot = vx * nx + vy * ny
    return vx - 2 * dot * nx, vy - 2 * dot * ny

class Tank:
    def __init__(self, x, y, color, color_dark, is_player, hp=1):
        self.x = x
        self.y = y
        self.angle = 0.0
        self.last_shot = 0.0
        self.reloading = False
        self.reload_start = 0.0
        self.magazine = MAGAZINE
        self.color = color
        self.color_dark = color_dark
        self.is_player = is_player
        self.alive = True
        self.hp = hp
        self.hit_flash = 0.0

    def can_shoot(self, now):
        if self.reloading:
            return False
        if now - self.last_shot < FIRE_RATE:
            return False
        return self.magazine > 0

    def shoot(self, now):
        self.last_shot = now
        self.magazine -= 1
        if self.magazine == 0:
            self.reloading = True
            self.reload_start = now

    def update_reload(self, now):
        if self.reloading and now - self.reload_start > RELOAD_TIME:
            self.reloading = False
            self.magazine = MAGAZINE

class Bullet:
    __slots__ = ('x', 'y', 'dx', 'dy', 'bounces', 'trail', 'owner_is_player')

    def __init__(self, x, y, dx, dy, owner_is_player):
        self.x = x
        self.y = y
        self.dx = dx
        self.dy = dy
        self.bounces = 0
        self.trail = [(x, y)]
        self.owner_is_player = owner_is_player

class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("TANKcat")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont('Arial', 11, bold=True)
        self.big_font = pygame.font.SysFont('Arial', 22, bold=True)
        self.maze = []
        self.player = None
        self.bot = None
        self.bullets = []
        self.show_trails = False
        self.score = 0
        self.deaths = 0
        self.respawn_timer = 0.0
        self.zoom = 1.0
        self.cam_x = 0.0
        self.cam_y = 0.0
        self.time_scale = 1.0

        self.bot_mode = PATROL
        self.bot_last_seen_x = 0.0
        self.bot_last_seen_y = 0.0
        self.bot_investigate_x = 0.0
        self.bot_investigate_y = 0.0
        self.bot_patrol_angle = 0.0
        self.bot_patrol_timer = 0.0
        self.bot_alert_timer = 0.0
        self.bot_prev_px = 0.0
        self.bot_prev_py = 0.0
        self.generate_maze()

    def generate_maze(self):
        w, h = MAZE_W, MAZE_H
        self.maze = [[1 for _ in range(w)] for _ in range(h)]
        cw = CORRIDOR_W

        visited = [[False] * MAZE_COARSE for _ in range(MAZE_COARSE)]

        def carve(cx, cy):
            visited[cy][cx] = True
            rx, ry = cx * cw * 2 + 1, cy * cw * 2 + 1
            for dy in range(cw):
                for dx in range(cw):
                    self.maze[ry + dy][rx + dx] = 0
            dirs = [(0, -1), (1, 0), (0, 1), (-1, 0)]
            random.shuffle(dirs)
            for dx, dy in dirs:
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < MAZE_COARSE and 0 <= ny < MAZE_COARSE and not visited[ny][nx]:
                    for iy in range(cw):
                        for ix in range(cw):
                            if dx != 0:
                                wx = rx + dx * cw + ix
                                wy = ry + iy
                            else:
                                wx = rx + ix
                                wy = ry + dy * cw + iy
                            if 0 <= wx < w and 0 <= wy < h:
                                self.maze[wy][wx] = 0
                    carve(nx, ny)

        from random import randrange
        carve(randrange(MAZE_COARSE), randrange(MAZE_COARSE))

        for y in range(h):
            self.maze[y][0] = 1
            self.maze[y][w - 1] = 1
        for x in range(w):
            self.maze[0][x] = 1
            self.maze[h - 1][x] = 1

        self.player = Tank(3.5, 3.5, NEON_BLUE, NEON_BLUE_DARK, True, hp=PLAYER_MAX_HP)
        bx, by = w - 4.5, h - 4.5
        self.bot = Tank(bx, by, NEON_RED, NEON_RED_DARK, False, hp=1)
        self.bot_mode = PATROL
        self.bot_patrol_angle = random.uniform(0, 360)
        self.bot_patrol_timer = 0.0
        self._clear_spawn(3, 3)
        self._clear_spawn(w - 4, h - 4)

    def _clear_spawn(self, cx, cy):
        for y in range(cy - CORRIDOR_W, cy + CORRIDOR_W + 1):
            for x in range(cx - CORRIDOR_W, cx + CORRIDOR_W + 1):
                if 0 <= y < MAZE_H and 0 <= x < MAZE_W:
                    if y == 0 or y == MAZE_H - 1 or x == 0 or x == MAZE_W - 1:
                        continue
                    self.maze[y][x] = 0

    def is_wall(self, x, y):
        ix, iy = int(x), int(y)
        if 0 <= ix < MAZE_W and 0 <= iy < MAZE_H:
            return self.maze[iy][ix] == 1
        return True

    def is_wall_tank(self, x, y):
        return (self.is_wall(x - TANK_RADIUS, y - TANK_RADIUS) or
                self.is_wall(x + TANK_RADIUS, y - TANK_RADIUS) or
                self.is_wall(x - TANK_RADIUS, y + TANK_RADIUS) or
                self.is_wall(x + TANK_RADIUS, y + TANK_RADIUS))

    def move_tank(self, tank, dx, dy):
        new_x = tank.x + dx
        new_y = tank.y + dy
        can_x = not self.is_wall_tank(new_x, tank.y)
        can_y = not self.is_wall_tank(tank.x, new_y)
        if can_x:
            tank.x = new_x
        if can_y:
            tank.y = new_y

    def update_camera(self):
        p = self.player
        self.cam_x = p.x * CELL - SCREEN_W / (2 * self.zoom)
        self.cam_y = p.y * CELL - SCREEN_H / (2 * self.zoom)

    def world_to_screen(self, wx, wy):
        sx = (wx - self.cam_x) * self.zoom
        sy = (wy - self.cam_y) * self.zoom
        return int(sx), int(sy)

    def handle_input(self, dt):
        p = self.player
        if not p.alive:
            return

        keys = pygame.key.get_pressed()
        step = PLAYER_SPEED * dt
        if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]:
            step *= SPRINT_MULT
        turn = TURN_SPEED * dt

        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            p.angle -= turn
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            p.angle += turn

        dx, dy = 0.0, 0.0
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            dx += math.cos(math.radians(p.angle))
            dy += math.sin(math.radians(p.angle))
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            dx -= math.cos(math.radians(p.angle))
            dy -= math.sin(math.radians(p.angle))

        if dx != 0 and dy != 0:
            norm = math.hypot(dx, dy)
            dx /= norm
            dy /= norm

        self.move_tank(p, dx * step, dy * step)

        now = time.time()
        if (keys[pygame.K_SPACE] or keys[pygame.K_RCTRL]) and p.can_shoot(now):
            self._spawn_bullet(p, True)
            p.shoot(now)

        p.update_reload(now)

    def _spawn_bullet(self, tank, owner_is_player):
        angle = math.radians(tank.angle) + math.radians(random.uniform(-BULLET_SPREAD, BULLET_SPREAD))
        self.bullets.append(Bullet(
            tank.x, tank.y,
            math.cos(angle) * BULLET_SPEED,
            math.sin(angle) * BULLET_SPEED,
            owner_is_player
        ))

    def _has_los(self, x1, y1, x2, y2):
        dist = math.hypot(x2 - x1, y2 - y1)
        steps = max(1, int(dist * 10))
        for i in range(steps + 1):
            t = i / steps
            if self.is_wall(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t):
                return False
        return True

    def bot_ai(self, dt):
        b = self.bot
        p = self.player
        if not b.alive or not p.alive:
            return

        now = time.time()
        has_los = self._has_los(b.x, b.y, p.x, p.y)

        dx_player = p.x - b.x
        dy_player = p.y - b.y
        dist_to_player = math.hypot(dx_player, dy_player)

        if has_los:
            self.bot_last_seen_x = p.x
            self.bot_last_seen_y = p.y

        dodge_dx, dodge_dy = 0.0, 0.0
        nearest_bullet_dist = BOT_BULLET_SENSE
        bullet_from_x, bullet_from_y = 0.0, 0.0
        for bullet in self.bullets:
            if bullet.owner_is_player:
                bdx = bullet.x - b.x
                bdy = bullet.y - b.y
                bdist = math.hypot(bdx, bdy)
                if bdist < 3.0 and bdist > 0.01:
                    perp_x = -bullet.dy
                    perp_y = bullet.dx
                    dot = bdx * perp_x + bdy * perp_y
                    sign = 1 if dot > 0 else -1
                    strength = (3.0 - bdist) / 3.0
                    dodge_dx += perp_x * sign * strength * 0.8
                    dodge_dy += perp_y * sign * strength * 0.8
                if bdist < nearest_bullet_dist and not has_los:
                    nearest_bullet_dist = bdist
                    bullet_from_x = bullet.x - bullet.dx * 8
                    bullet_from_y = bullet.y - bullet.dy * 8

        if nearest_bullet_dist < BOT_BULLET_SENSE and self.bot_mode != CHASE:
            self.bot_mode = SEARCH
            self.bot_investigate_x = bullet_from_x
            self.bot_investigate_y = bullet_from_y
            self.bot_alert_timer = 12.0

        if has_los and dist_to_player < BOT_DETECT_RANGE:
            self.bot_mode = CHASE
            self.bot_alert_timer = 0
        elif self.bot_mode == CHASE and not has_los:
            self.bot_mode = SEARCH
            self.bot_investigate_x = self.bot_last_seen_x
            self.bot_investigate_y = self.bot_last_seen_y
            self.bot_alert_timer = 15.0

        move_angle = b.angle

        if self.bot_mode == PATROL:
            self.bot_patrol_timer -= dt
            if self.bot_patrol_timer <= 0:
                if self.bot_last_seen_x != 0 and random.random() < 0.4:
                    dx = self.bot_last_seen_x - b.x
                    dy = self.bot_last_seen_y - b.y
                    self.bot_patrol_angle = math.degrees(math.atan2(dy, dx))
                else:
                    self.bot_patrol_angle += random.uniform(-90, 90)
                self.bot_patrol_timer = BOT_PATROL_CHANGE * random.uniform(0.5, 1.5)

            move_angle = self.bot_patrol_angle
            step = BOT_SPEED * dt

            mdx = math.cos(math.radians(move_angle))
            mdy = math.sin(math.radians(move_angle))
            self.move_tank(b, mdx * step, mdy * step)

            if self.is_wall_tank(b.x + mdx * TANK_RADIUS * 2, b.y + mdy * TANK_RADIUS * 2):
                for _ in range(8):
                    self.bot_patrol_angle += 45
                    test_angle = self.bot_patrol_angle
                    tdx = math.cos(math.radians(test_angle))
                    tdy = math.sin(math.radians(test_angle))
                    if not self.is_wall_tank(b.x + tdx * TANK_RADIUS * 2, b.y + tdy * TANK_RADIUS * 2):
                        move_angle = test_angle
                        break
                self.bot_patrol_timer = 0

            diff = (move_angle - b.angle + 180) % 360 - 180
            ts = 180 * dt
            if abs(diff) < ts:
                b.angle = move_angle
            else:
                b.angle += ts if diff > 0 else -ts

            if has_los:
                self.bot_patrol_angle = math.degrees(math.atan2(dy_player, dx_player))

        elif self.bot_mode == CHASE:
            dx = self.bot_last_seen_x - b.x
            dy = self.bot_last_seen_y - b.y
            dist = math.hypot(dx, dy)

            if dist > 0.01:
                ndx, ndy = dx / dist, dy / dist

                if dist < 5:
                    strafe_x = -ndy
                    strafe_y = ndx
                    move_dx = ndx + strafe_x * 0.4 + dodge_dx
                    move_dy = ndy + strafe_y * 0.4 + dodge_dy
                else:
                    move_dx = ndx + dodge_dx
                    move_dy = ndy + dodge_dy

                mlen = math.hypot(move_dx, move_dy)
                if mlen > 0.01:
                    move_dx /= mlen
                    move_dy /= mlen

                step = BOT_SPEED * dt
                self.move_tank(b, move_dx * step, move_dy * step)

            target_angle = math.degrees(math.atan2(dy, dx))
            diff = (target_angle - b.angle + 180) % 360 - 180
            ts = 360 * dt
            if abs(diff) < ts:
                b.angle = target_angle
            else:
                b.angle += ts if diff > 0 else -ts

            if b.can_shoot(now) and has_los and dist_to_player < 16:
                travel_time = dist_to_player / BULLET_SPEED
                pvx = p.x - self.bot_prev_px
                pvy = p.y - self.bot_prev_py
                predict_x = p.x + pvx * travel_time * 0.4
                predict_y = p.y + pvy * travel_time * 0.4
                aim_angle = math.degrees(math.atan2(predict_y - b.y, predict_x - b.x))
                aim_diff = (aim_angle - b.angle + 180) % 360 - 180
                if abs(aim_diff) < 15:
                    self._spawn_bullet(b, False)
                    b.shoot(now)

        elif self.bot_mode == SEARCH:
            self.bot_alert_timer -= dt
            if self.bot_alert_timer <= 0:
                self.bot_mode = PATROL
                self.bot_patrol_angle = random.uniform(0, 360)
                self.bot_patrol_timer = 0

            dx = self.bot_investigate_x - b.x
            dy = self.bot_investigate_y - b.y
            dist = math.hypot(dx, dy)

            if dist < 1.5:
                self.bot_investigate_x = b.x + random.uniform(-5, 5)
                self.bot_investigate_y = b.y + random.uniform(-5, 5)
                if self.bot_alert_timer < 3:
                    self.bot_mode = PATROL
                    self.bot_patrol_angle = random.uniform(0, 360)
                    self.bot_patrol_timer = 0
            elif dist > 0.01:
                ndx, ndy = dx / dist, dy / dist
                step = BOT_SPEED * dt
                self.move_tank(b, (ndx + dodge_dx * 0.5) * step, (ndy + dodge_dy * 0.5) * step)

                target_angle = math.degrees(math.atan2(dy, dx))
                diff = (target_angle - b.angle + 180) % 360 - 180
                ts = 220 * dt
                if abs(diff) < ts:
                    b.angle = target_angle
                else:
                    b.angle += ts if diff > 0 else -ts

        self.bot_prev_px = p.x
        self.bot_prev_py = p.y
        b.update_reload(now)

    def update_bullets(self, dt):
        alive = []
        for b in self.bullets:
            b.x += b.dx * dt
            b.y += b.dy * dt
            if self.show_trails:
                b.trail.append((b.x, b.y))
            else:
                b.trail.append((b.x, b.y))
                while len(b.trail) > 5:
                    b.trail.pop(0)

            if b.x < 0 or b.x >= MAZE_W or b.y < 0 or b.y >= MAZE_H:
                continue

            if self.is_wall(b.x, b.y):
                ix, iy = int(b.x), int(b.y)
                nx, ny = 0, 0

                above = not self.is_wall(b.x, iy - 1)
                below = not self.is_wall(b.x, iy + 1)
                left = not self.is_wall(ix - 1, b.y)
                right = not self.is_wall(ix + 1, b.y)

                if above: ny -= 1
                if below: ny += 1
                if left: nx -= 1
                if right: nx += 1

                if nx != 0 or ny != 0:
                    nl = math.hypot(nx, ny)
                    nx, ny = nx / nl, ny / nl
                    b.dx, b.dy = reflect(b.dx, b.dy, nx, ny)
                else:
                    b.dx = -b.dx
                    b.dy = -b.dy

                if b.bounces < MAX_BOUNCES:
                    b.bounces += 1
                    b.x += b.dx * dt * 2
                    b.y += b.dy * dt * 2
                else:
                    continue

            if b.owner_is_player:
                target = self.bot
            else:
                target = self.player

            if target.alive:
                if abs(b.x - target.x) < BULLET_HIT_RADIUS and abs(b.y - target.y) < BULLET_HIT_RADIUS:
                    target.hp -= 1
                    target.hit_flash = 0.15
                    if target.hp <= 0:
                        target.alive = False
                        if target == self.bot:
                            self.score += 1
                            self.respawn_timer = time.time() + 2.0
                    continue

            alive.append(b)
        self.bullets = alive

    def respawn_bot_if_needed(self):
        if self.bot.alive:
            return
        if not self.player.alive:
            return
        if self.respawn_timer == 0:
            return
        if time.time() < self.respawn_timer:
            return
        self.respawn_timer = 0
        for _ in range(200):
            bx = random.randint(5, MAZE_W - 6)
            by = random.randint(5, MAZE_H - 6)
            if self.maze[by][bx] == 0:
                dist = math.hypot(bx - self.player.x, by - self.player.y)
                if dist > 8:
                    self.bot = Tank(bx + 0.5, by + 0.5, NEON_RED, NEON_RED_DARK, False, hp=1)
                    self.bot_mode = PATROL
                    self.bot_patrol_angle = random.uniform(0, 360)
                    self.bot_patrol_timer = 0
                    return

    def draw_walls(self):
        cam_left = int(self.cam_x / CELL) - 1
        cam_right = int((self.cam_x + SCREEN_W / self.zoom) / CELL) + 1
        cam_top = int(self.cam_y / CELL) - 1
        cam_bottom = int((self.cam_y + SCREEN_H / self.zoom) / CELL) + 1

        for y in range(max(0, cam_top), min(MAZE_H, cam_bottom + 1)):
            for x in range(max(0, cam_left), min(MAZE_W, cam_right + 1)):
                if self.maze[y][x] == 0:
                    continue
                sx, sy = self.world_to_screen(x * CELL, y * CELL)
                sz = int(CELL * self.zoom)
                if sx + sz < -10 or sx > SCREEN_W + 10 or sy + sz < -10 or sy > SCREEN_H + 10:
                    continue
                pygame.draw.rect(self.screen, WALL_COLOR, (sx, sy, sz, sz))
                pygame.draw.line(self.screen, WALL_TOP, (sx, sy), (sx + sz - 1, sy))
                pygame.draw.line(self.screen, WALL_TOP, (sx, sy), (sx, sy + sz - 1))
                pygame.draw.line(self.screen, WALL_BOT, (sx, sy + sz - 1), (sx + sz - 1, sy + sz - 1))
                pygame.draw.line(self.screen, WALL_BOT, (sx + sz - 1, sy), (sx + sz - 1, sy + sz - 1))

    def draw_tank(self, tank):
        if tank.hit_flash > 0:
            tank.hit_flash = max(0, tank.hit_flash - self.clock.get_time() / 1000.0)

        cx, cy = self.world_to_screen(tank.x * CELL, tank.y * CELL)
        half = int(CELL * 0.36 * self.zoom)
        if half < 1:
            return

        flash_color = (255, 255, 255) if tank.hit_flash > 0 else tank.color
        flash_dark = (200, 200, 200) if tank.hit_flash > 0 else tank.color_dark

        for r in (5, 3, 1):
            alpha = 50 // (r + 1)
            s = pygame.Surface((r * 6, r * 6), pygame.SRCALPHA)
            pygame.draw.rect(s, (*tank.color, alpha), (0, 0, r * 6, r * 6))
            self.screen.blit(s, (cx - r * 3, cy - r * 3))

        pygame.draw.rect(self.screen, flash_dark,
                         (cx - half, cy - half, half * 2, half * 2), border_radius=3)
        inner = max(2, half - 2)
        pygame.draw.rect(self.screen, flash_color,
                         (cx - inner, cy - inner, inner * 2, inner * 2), border_radius=2)

        angle_rad = math.radians(tank.angle)
        bdx = math.cos(angle_rad)
        bdy = math.sin(angle_rad)

        bx = cx + bdx * half
        by = cy + bdy * half
        elen = int(10 * self.zoom)
        ex = cx + bdx * (half + elen)
        ey = cy + bdy * (half + elen)

        bw = max(3, int(5 * self.zoom))
        pygame.draw.line(self.screen, tank.color_dark, (bx, by), (ex, ey), bw)
        mx = cx + bdx * (half + int(4 * self.zoom))
        my = cy + bdy * (half + int(4 * self.zoom))
        pygame.draw.line(self.screen, tank.color, (mx, my),
                         (ex - bdx * int(2 * self.zoom), ey - bdy * int(2 * self.zoom)),
                         max(1, bw - 2))

        if tank.is_player:
            ammo_str = f"{tank.magazine}/{MAGAZINE}"
            txt = self.font.render(ammo_str, True, WHITE)
            self.screen.blit(txt, (cx - txt.get_width() // 2, cy - half - 16))
            if tank.reloading:
                prog = (time.time() - tank.reload_start) / RELOAD_TIME
                bw = half * 2
                bar_y = cy - half - 10
                pygame.draw.rect(self.screen, (30, 30, 30), (cx - bw // 2, bar_y, bw, 3))
                pygame.draw.rect(self.screen, NEON_BLUE, (cx - bw // 2, bar_y, int(bw * prog), 3))

    def draw_bullets(self):
        for b in self.bullets:
            color = NEON_BLUE if b.owner_is_player else NEON_RED
            bx, by = self.world_to_screen(b.x * CELL, b.y * CELL)

            glow = pygame.Surface((10, 10), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*color, 70), (5, 5), 5)
            self.screen.blit(glow, (bx - 5, by - 5))
            pygame.draw.circle(self.screen, WHITE, (bx, by), 3)
            pygame.draw.circle(self.screen, color, (bx, by), 2)

    def draw_trails(self):
        if not self.show_trails:
            return
        for b in self.bullets:
            if len(b.trail) < 2:
                continue
            color = NEON_BLUE if b.owner_is_player else NEON_RED
            pts = [self.world_to_screen(p[0] * CELL, p[1] * CELL) for p in b.trail]
            if len(pts) >= 2:
                pygame.draw.lines(self.screen, (*color, 120), False, pts, 1)

    def draw_hud(self):
        p = self.player
        score_txt = self.font.render(f"Score: {self.score}", True, WHITE)
        self.screen.blit(score_txt, (8, 8))

        if p.alive:
            hp_txt = self.font.render(f"HP: {p.hp}/{PLAYER_MAX_HP}", True, NEON_BLUE if p.hp > 1 else NEON_RED)
            self.screen.blit(hp_txt, (8, 22))
        else:
            deaths_txt = self.font.render(f"Deaths: {self.deaths}", True, NEON_RED)
            self.screen.blit(deaths_txt, (8, 22))

        zoom_txt = self.font.render(f"Zoom: {self.zoom:.1f}x", True, GRAY)
        self.screen.blit(zoom_txt, (8, 38))

        mode_names = ["PATROL", "CHASE", "SEARCH"]
        mode_txt = self.font.render(f"Bot: {mode_names[self.bot_mode]}", True, GRAY)
        self.screen.blit(mode_txt, (8, 54))

        if self.time_scale < 0.5:
            slow_txt = self.big_font.render("SLOW-MO", True, NEON_BLUE)
            self.screen.blit(slow_txt, (SCREEN_W - slow_txt.get_width() - 12, 8))

        hint = self.font.render("WASD:Move SHIFT:Sprint A/D:Turn SPACE:Shoot TAB:SlowMo +/-:Zoom R:Restart", True, GRAY)
        self.screen.blit(hint, (8, SCREEN_H - 18))

        if not self.player.alive:
            overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 170))
            self.screen.blit(overlay, (0, 0))
            go = self.big_font.render("YOU DIED", True, NEON_RED)
            self.screen.blit(go, (SCREEN_W // 2 - go.get_width() // 2, SCREEN_H // 2 - 30))
            rst = self.font.render("Press R to restart", True, WHITE)
            self.screen.blit(rst, (SCREEN_W // 2 - rst.get_width() // 2, SCREEN_H // 2 + 15))

    def draw(self):
        self.screen.fill(BG_COLOR)
        self.update_camera()
        self.draw_walls()
        self.draw_trails()
        self.draw_bullets()
        if self.player.alive:
            self.draw_tank(self.player)
        if self.bot.alive:
            self.draw_tank(self.bot)
        self.draw_hud()
        pygame.display.flip()

    def restart(self):
        self.bullets.clear()
        self.respawn_timer = 0.0
        self.zoom = 1.0
        self.time_scale = 1.0
        self.show_trails = False
        if not self.player.alive:
            self.deaths += 1
        self.generate_maze()

    def run(self):
        running = True
        while running:
            raw_dt = self.clock.tick(FPS) / 1000.0
            dt = raw_dt * self.time_scale

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_TAB:
                        self.show_trails = not self.show_trails
                        self.time_scale = SLOW_MO_FACTOR if self.show_trails else 1.0
                    elif event.key == pygame.K_r:
                        self.restart()
                    elif event.key == pygame.K_EQUALS or event.key == pygame.K_PLUS:
                        self.zoom = min(ZOOM_MAX, self.zoom + ZOOM_STEP)
                    elif event.key == pygame.K_MINUS:
                        self.zoom = max(ZOOM_MIN, self.zoom - ZOOM_STEP)

            if self.player.alive and self.bot.alive:
                self.handle_input(dt)
                self.bot_ai(dt)
                self.update_bullets(dt)

            self.respawn_bot_if_needed()
            self.draw()
            self.clock.tick(FPS)

        pygame.quit()

if __name__ == "__main__":
    Game().run()