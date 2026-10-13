"""Game state, simulation, collision handling, and drawing."""
import math
import random
import pygame

import audio
from audio import play_sound
from effects import Star, Particle, FloatingText
from entities.ball import Ball
from entities.paddle import Paddle
from entities.powerup import PowerUp
from levels import make_level
from settings import (
    WIDTH, HEIGHT, BG, WHITE, MUTED, CYAN, BLUE, PINK, GOLD,
    TOP_WALL, FPS, GREEN,
)
from utils import (
    clamp, draw_text, load_save, save_progress, circle_rect_collision,
    load_checkpoint, save_checkpoint, clear_checkpoint,
)
from economy import Economy
from shop import Shop


def level_ball_speed(level):
    """Return a controlled launch speed for the given level."""
    level = max(1, int(level))
    return min(600, 390 + (level - 1) * 18)


class StarDriftGame:
    def __init__(self):
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("STARDRIFT: Space Paddle")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("arial", 22)
        self.small = pygame.font.SysFont("arial", 16)
        self.medium = pygame.font.SysFont("arial", 32, bold=True)
        self.large = pygame.font.SysFont("arial", 58, bold=True)

        saved = load_save()
        self.high_score = saved["high_score"]
        self.best_level = saved["best_level"]
        self.checkpoint = load_checkpoint()
        self.economy = Economy()
        self.shop = Shop(self.economy.db)
        self.ball_color = self.shop.get_active_ball_color()
        self.ball_skin = (
            "iran_flag"
            if self.shop.get_active_ball_color_key() == "ball_skin_iran"
            else None
        )
        self.shop_items = self.shop.get_items()
        self.shop_purchase_pending = False
        self.shop_purchase_request_id = None
        self.shop_purchase_price = 0
        self.shop_purchase_key = None
        self.shop_selection = 0
        self.shop_scroll = 0
        self.shop_scroll_max = 0
        self.shop_card_rects = []
        self.shop_message = ""
        self.shop_message_timer = 0.0
        self.stars = [Star() for _ in range(110)]
        self.particles = []
        self.floating_texts = []
        self.screen_shake = 0.0
        self.elapsed = 0.0
        self.sound_enabled = True
        self.running = True
        self.state = "menu"
        self.game = self._reset_run()
        self.game["balls"] = [
            Ball(WIDTH / 2, self.game["paddle"].y - 18, 390, attached=True, color=self.ball_color, skin=self.ball_skin)
        ]

    def _create_paddle(self):
        upgrades = self.economy.db.get_upgrades()
        return Paddle(
            width_level=upgrades.get("paddle_width", 0),
            speed_level=upgrades.get("paddle_speed", 0),
        )

    def _reset_run(self):
        upgrades = self.economy.db.get_upgrades()
        return {
            "score": 0,
            "lives": 3 + min(2, max(0, int(upgrades.get("extra_life", 0)))),
            "level": 1,
            "bricks": make_level(1),
            "paddle": self._create_paddle(),
            "balls": [],
            "powerups": [],
            "lasers": [],
            "laser_level": upgrades.get("laser", 0),
            "laser_cooldown": 0.0,
            "shield_level": upgrades.get("permanent_shield", 0),
            "shield_cooldown": 0.0,
            "bomb_level": upgrades.get("emergency_bomb", 0),
            "row_clear_level": upgrades.get("row_clear", 0),
            "state": "ready",
            "level_banner": 1.6,
            "combo": 0,
            "combo_timer": 0.0,
        }

    def start_run(self):
        # === START A FRESH RUN ===
        clear_checkpoint()
        self.checkpoint = None
        self.economy.start_run()
        self.game = self._reset_run()
        self.game["balls"] = [
            Ball(WIDTH / 2, self.game["paddle"].y - 18, 390, attached=True, color=self.ball_color, skin=self.ball_skin)
        ]
        self.particles.clear()
        self.floating_texts.clear()
        self.screen_shake = 0.0
        self.state = "playing"
        self._save_checkpoint()

    def _save_checkpoint(self):
        # === SAVE CHECKPOINT AT THE CURRENT LEVEL START ===
        checkpoint = {
            "level": self.game["level"],
            "score": self.game["score"],
            "lives": self.game["lives"],
        }
        save_checkpoint(**checkpoint)
        self.checkpoint = checkpoint

    def continue_run(self):
        # === RESUME FROM THE LAST SAVED LEVEL START ===
        checkpoint = load_checkpoint()
        if checkpoint is None:
            self.checkpoint = None
            return False

        self.economy.start_run(record_game=False)
        self.game = self._reset_run()
        self.game["level"] = checkpoint["level"]
        self.game["score"] = checkpoint["score"]
        self.game["lives"] = checkpoint["lives"]
        self.game["bricks"] = make_level(checkpoint["level"])

        paddle = self.game["paddle"]
        speed = level_ball_speed(checkpoint["level"])
        self.game["balls"] = [
            Ball(
                paddle.x + paddle.width / 2,
                paddle.y - 18,
                speed,
                attached=True,
                color=self.ball_color,
                skin=self.ball_skin,
            )
        ]

        self.particles.clear()
        self.floating_texts.clear()
        self.screen_shake = 0.0
        self.state = "playing"
        self.checkpoint = checkpoint
        return True

    def persist_score(self):
        if self.game["score"] > self.high_score:
            self.high_score = self.game["score"]
        if self.game["level"] > self.best_level:
            self.best_level = self.game["level"]
        save_progress(self.high_score, self.best_level)

    def next_level(self):
        reward = self.economy.stage_cleared(self.game["level"])
        self.floating_texts.append(
            FloatingText(
                WIDTH / 2, HEIGHT / 2,
                f"STAGE BONUS +{reward} CR", GOLD
            )
        )
        self.game["level"] += 1
        self.game["bricks"] = make_level(self.game["level"])
        self._save_checkpoint()
        self.game["powerups"].clear()
        self.game["level_banner"] = 1.8
        paddle = self.game["paddle"]
        paddle.x = WIDTH / 2 - paddle.width / 2

        # Start every new level with one fresh ball attached to the paddle.
        # Discarding old balls prevents carrying momentum into the next level.
        ball_speed = level_ball_speed(self.game["level"])
        self.game["balls"] = [
            Ball(
                paddle.x + paddle.width / 2,
                paddle.y - 18,
                ball_speed,
                attached=True,
                color=self.ball_color,
                skin=self.ball_skin,
            )
        ]
        play_sound("win")

    def emit_particles(self, x, y, color, amount=12):
        self.particles.extend(Particle(x, y, color) for _ in range(amount))

    def apply_powerup(self, kind):
        paddle = self.game["paddle"]
        if kind == "wide":
            paddle.wide_timer = 9.0
        elif kind == "shield":
            paddle.shield_timer = 8.0
        elif kind == "slow":
            for ball in self.game["balls"]:
                ball.vx *= 0.72
                ball.vy *= 0.72
                ball.speed *= 0.72
        elif kind == "multiball":
            new_balls = []
            for ball in self.game["balls"]:
                if not ball.attached:
                    for angle in (-0.45, 0.45):
                        new = Ball(ball.x, ball.y, ball.speed, color=self.ball_color, skin=self.ball_skin)
                        base_angle = math.atan2(ball.vy, ball.vx) + angle
                        new.vx = math.cos(base_angle) * ball.speed
                        new.vy = math.sin(base_angle) * ball.speed
                        new_balls.append(new)
            # Limit the total ball count to avoid uncontrolled exponential growth.
            self.game["balls"].extend(new_balls[:max(0, 6 - len(self.game["balls"]))])

        self.emit_particles(paddle.rect.centerx, paddle.y, PowerUp.COLORS[kind], 28)
        labels = {
            "wide": "WIDE PADDLE!",
            "shield": "SHIELD!",
            "slow": "TIME DILATION!",
            "multiball": "MULTI-BALL!",
        }
        self.floating_texts.append(
            FloatingText(paddle.x, paddle.y - 28, labels[kind], PowerUp.COLORS[kind])
        )
        play_sound("power")

    def update(self, dt):
        self.elapsed += dt
        self.shop_message_timer = max(0.0, self.shop_message_timer - dt)
        self._process_shop_purchase_results()
        for star in self.stars:
            star.update(dt)
        for particle in self.particles[:]:
            particle.update(dt)
            if particle.life <= 0:
                self.particles.remove(particle)
        for floating in self.floating_texts[:]:
            floating.update(dt)
            if floating.life <= 0:
                self.floating_texts.remove(floating)
        self.screen_shake = max(0.0, self.screen_shake - dt)

        if self.state == "playing":
            self.update_game(dt)

    def update_game(self, dt):
        game = self.game
        paddle = game["paddle"]
        paddle.update(dt)
        game["shield_cooldown"] = max(
            0.0, game["shield_cooldown"] - dt
        )

        # Preserve the original mouse behavior: drag with the left button.
        if pygame.mouse.get_focused() and pygame.mouse.get_pressed()[0]:
            mouse_x, _ = pygame.mouse.get_pos()
            paddle.move_to_mouse(mouse_x)

        # Twin-laser upgrade: hold Ctrl to fire when the cooldown permits.
        game["laser_cooldown"] = max(0.0, game["laser_cooldown"] - dt)
        keys = pygame.key.get_pressed()
        laser_level = game["laser_level"]

        if (
            laser_level > 0
            and (keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL])
            and game["laser_cooldown"] <= 0
        ):
            cooldowns = {1: 8.0, 2: 6.5, 3: 5.0, 4: 4.5, 5: 4.0}
            damage = 3 if laser_level >= 5 else 2 if laser_level >= 4 else 1
            game["lasers"].extend([
                {
                    "x": paddle.x + 18,
                    "y": paddle.y - 3,
                    "damage": damage,
                },
                {
                    "x": paddle.x + paddle.width - 18,
                    "y": paddle.y - 3,
                    "damage": damage,
                },
            ])
            game["laser_cooldown"] = cooldowns[min(5, laser_level)]
            play_sound("power")

        for ball in game["balls"]:
            if ball.attached:
                ball.x = paddle.x + paddle.width / 2
                ball.y = paddle.y - ball.radius - 3
                continue

            ball.update(dt)

            # Paddle collision, only while the ball is descending.
            if (
                ball.vy > 0
                and ball.y + ball.radius >= paddle.y
                and ball.y - ball.radius <= paddle.y + paddle.height
                and paddle.x <= ball.x <= paddle.x + paddle.width
            ):
                ball.y = paddle.y - ball.radius
                offset = (ball.x - (paddle.x + paddle.width / 2)) / (paddle.width / 2)
                offset = clamp(offset, -0.88, 0.88)
                angle = offset * math.radians(62)
                ball.speed = min(640, max(360, ball.speed * 1.01))
                ball.vx = math.sin(angle) * ball.speed
                ball.vy = -math.cos(angle) * ball.speed
                game["score"] += 5
                credit_reward = self.economy.paddle_hit()
                if credit_reward:
                    self.floating_texts.append(
                        FloatingText(
                            paddle.x, paddle.y - 48,
                            f"+{credit_reward} CR", GOLD
                        )
                    )
                game["combo"] += 1
                game["combo_timer"] = 1.8
                self.emit_particles(ball.x, paddle.y, CYAN, 8)
                play_sound("hit")

            # One brick per ball per update.
            for brick in game["bricks"][:]:
                collided, dx, dy = circle_rect_collision(ball, brick.rect)
                if not collided:
                    continue

                if abs(dx) > abs(dy):
                    ball.vx *= -1
                    ball.x += math.copysign(2, dx if dx else ball.vx)
                else:
                    ball.vy *= -1
                    ball.y += math.copysign(2, dy if dy else ball.vy)

                destroyed = brick.hit()
                if destroyed:
                    game["bricks"].remove(brick)
                    credit_reward = self.economy.brick_destroyed(brick.max_hp)
                    self.floating_texts.append(
                        FloatingText(
                            brick.rect.centerx, brick.rect.centery + 14,
                            f"+{credit_reward} CR", GOLD
                        )
                    )
                    points = 20 * brick.max_hp * min(5, 1 + game["combo"] // 8)
                    game["score"] += points
                    self.floating_texts.append(
                        FloatingText(brick.rect.centerx, brick.rect.centery, f"+{points}", brick.color)
                    )
                    self.emit_particles(brick.rect.centerx, brick.rect.centery, brick.color, 14)
                    game["combo"] += 1
                    if random.random() < 0.14:
                        game["powerups"].append(PowerUp(brick.rect.centerx, brick.rect.centery))
                else:
                    game["score"] += 5
                    self.emit_particles(ball.x, ball.y, brick.color, 4)

                play_sound("brick")
                self.screen_shake = max(self.screen_shake, 0.035)
                break

        # Move laser bolts and resolve their brick collisions.
        for laser in game["lasers"][:]:
            laser["y"] -= 820 * dt
            laser_rect = pygame.Rect(
                round(laser["x"] - 2),
                round(laser["y"] - 9),
                4,
                12,
            )

            if laser_rect.bottom < TOP_WALL:
                game["lasers"].remove(laser)
                continue

            for brick in game["bricks"][:]:
                if not laser_rect.colliderect(brick.rect):
                    continue

                destroyed = False
                for _ in range(laser["damage"]):
                    if brick.hit():
                        destroyed = True
                        break

                if destroyed:
                    game["bricks"].remove(brick)
                    reward = self.economy.brick_destroyed(brick.max_hp)
                    self.floating_texts.append(
                        FloatingText(
                            brick.rect.centerx,
                            brick.rect.centery + 14,
                            f"+{reward} CR",
                            GOLD,
                        )
                    )
                    points = 20 * brick.max_hp * min(
                        5, 1 + game["combo"] // 8
                    )
                    game["score"] += points
                    self.floating_texts.append(
                        FloatingText(
                            brick.rect.centerx,
                            brick.rect.centery,
                            f"+{points}",
                            brick.color,
                        )
                    )
                    self.emit_particles(
                        brick.rect.centerx, brick.rect.centery, brick.color, 14
                    )
                    game["combo"] += 1
                    if random.random() < 0.14:
                        game["powerups"].append(
                            PowerUp(brick.rect.centerx, brick.rect.centery)
                        )
                else:
                    game["score"] += 5
                    self.emit_particles(
                        laser["x"], laser["y"], CYAN, 4
                    )

                play_sound("brick")
                self.screen_shake = max(self.screen_shake, 0.035)
                game["lasers"].remove(laser)
                break

        # Process lost balls after all balls have moved.
        kept = []
        lost = 0
        for ball in game["balls"]:
            if ball.y - ball.radius > HEIGHT:
                if paddle.shield_timer > 0:
                    ball.y = paddle.y - ball.radius
                    ball.attached = True
                    kept.append(ball)
                    paddle.shield_timer = max(0.0, paddle.shield_timer - 2.5)
                    self.floating_texts.append(
                        FloatingText(paddle.x, paddle.y - 35, "SHIELD SAVE!", BLUE)
                    )
                else:
                    lost += 1
                    self.emit_particles(ball.x, HEIGHT - 8, (255, 83, 170), 14)
            else:
                kept.append(ball)

        game["balls"] = kept
        if lost and not game["balls"]:
            game["lives"] -= 1
            play_sound("lose")
            if game["lives"] <= 0:
                self.persist_score()
                clear_checkpoint()
                self.checkpoint = None
                self.state = "gameover"
            else:
                game["balls"] = [
                    Ball(paddle.x + paddle.width / 2, paddle.y - 18,
                         level_ball_speed(game["level"]), attached=True,
                         color=self.ball_color, skin=self.ball_skin)
                ]

        for power in game["powerups"][:]:
            power.update(dt)
            if power.rect.colliderect(paddle.rect):
                self.apply_powerup(power.kind)
                game["powerups"].remove(power)
            elif power.y > HEIGHT + 20:
                game["powerups"].remove(power)

        for brick in game["bricks"]:
            brick.update(dt)

        game["combo_timer"] = max(0.0, game["combo_timer"] - dt)
        if game["combo_timer"] <= 0:
            game["combo"] = 0
        game["level_banner"] = max(0.0, game["level_banner"] - dt)

        if not game["bricks"] and self.state == "playing":
            self.next_level()

    def draw_background(self):
        self.screen.fill(BG)
        for i in range(5):
            x = (i * 237 + 90) % WIDTH
            y = (i * 139 + 110) % HEIGHT
            pygame.draw.circle(self.screen, (8, 12, 38), (x, y), 115)
        for star in self.stars:
            star.draw(self.screen, self.elapsed)
        pygame.draw.line(self.screen, (25, 46, 86), (0, 61), (WIDTH, 61), 1)

    def draw_hud(self):
        game = self.game
        pygame.draw.rect(self.screen, (8, 13, 35), (0, 0, WIDTH, 62))
        pygame.draw.line(self.screen, (31, 70, 112), (0, 61), (WIDTH, 61), 1)
        self.screen.blit(self.font.render(f"SCORE  {game['score']:,}", True, WHITE), (22, 17))
        self.screen.blit(
            self.small.render(f"BEST  {max(self.high_score, game['score']):,}", True, GOLD),
            (25, 42),
        )
        draw_text(self.screen, f"SECTOR {game['level']:02d}", self.font, CYAN, (WIDTH // 2, 25))
        lives_text = "◆ " * game["lives"]
        self.screen.blit(
            self.font.render(f"LIVES  {lives_text}", True, PINK),
            (WIDTH - 235, 17),
        )
        credits = self.economy.credits
        self.screen.blit(
            self.small.render(f"CREDITS  {credits:,} CR", True, GOLD),
            (WIDTH - 235, 42),
        )
        if game["combo"] >= 3 and game["combo_timer"] > 0:
            draw_text(
                self.screen,
                f"COMBO x{min(5, 1 + game['combo'] // 8)}  ·  {game['combo']} HITS",
                self.small, GOLD, (WIDTH // 2, 47),
            )

    def draw_overlay(self, title, subtitle, options):
        # === Minimal overlay ===
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((3, 6, 19, 218))
        self.screen.blit(overlay, (0, 0))

        center_x = WIDTH // 2
        panel_width = min(680, WIDTH - 48)
        panel_height = 210 + len(options) * 32
        panel = pygame.Rect(
            center_x - panel_width // 2,
            (HEIGHT - panel_height) // 2,
            panel_width,
            panel_height,
        )

        pygame.draw.rect(
            self.screen, (12, 19, 39), panel, border_radius=8
        )
        pygame.draw.rect(
            self.screen, (31, 49, 77), panel, width=1, border_radius=8
        )
        pygame.draw.line(
            self.screen, CYAN,
            (panel.left + 34, panel.top + 2),
            (panel.right - 34, panel.top + 2), 2,
        )

        draw_text(
            self.screen, title, self.large, CYAN,
            (center_x, panel.top + 58),
        )
        draw_text(
            self.screen, subtitle, self.small, WHITE,
            (center_x, panel.top + 108),
        )

        divider_y = panel.top + 132
        pygame.draw.line(
            self.screen, (37, 51, 76),
            (panel.left + 42, divider_y),
            (panel.right - 42, divider_y), 1,
        )

        for i, option in enumerate(options):
            draw_text(
                self.screen, option, self.small,
                GOLD if i == 0 else MUTED,
                (center_x, panel.top + 158 + i * 32),
            )

    def draw_world(self):
        self.draw_background()
        pygame.draw.line(self.screen, (19, 45, 89), (24, 82), (24, HEIGHT - 22), 1)
        pygame.draw.line(
            self.screen, (19, 45, 89),
            (WIDTH - 24, 82), (WIDTH - 24, HEIGHT - 22), 1,
        )
        for brick in self.game["bricks"]:
            brick.draw(self.screen)
        for laser in self.game.get("lasers", []):
            x, y = round(laser["x"]), round(laser["y"])
            pygame.draw.line(self.screen, (35, 150, 255), (x, y + 7), (x, y - 8), 7)
            pygame.draw.line(self.screen, (180, 245, 255), (x, y + 6), (x, y - 8), 3)
        for power in self.game["powerups"]:
            power.draw(self.screen, self.small)
        for ball in self.game["balls"]:
            ball.draw(self.screen)
        self.game["paddle"].draw(self.screen)
        for particle in self.particles:
            particle.draw(self.screen)
        for floating in self.floating_texts:
            floating.draw(self.screen, self.small)
        self.draw_hud()

        if self.game["level_banner"] > 0 and self.state == "playing":
            alpha = min(1.0, self.game["level_banner"] * 2)
            banner = self.large.render(f"SECTOR {self.game['level']:02d}", True, WHITE)
            banner.set_alpha(int(220 * alpha))
            self.screen.blit(banner, banner.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 10)))

    def _refresh_shop_statuses(self):
        credits = self.economy.credits

        for item in self.shop_items:
            item["credits"] = credits

            if item.get("category") == "cosmetic":
                owned = bool(item["maxed"])
                item["affordable"] = owned or credits >= item["price"]

                if owned:
                    if item["status"] not in ("equipped", "owned"):
                        item["status"] = "owned"
                else:
                    item["status"] = (
                        "available"
                        if credits >= item["price"]
                        else "insufficient_credits"
                    )
                continue

            item["affordable"] = (
                item["price"] is not None and credits >= item["price"]
            )
            if item["maxed"]:
                item["status"] = (
                    "unlocked"
                    if item["key"] in ("emergency_bomb", "row_clear")
                    else "maxed"
                )
            elif item["locked"]:
                item["status"] = "locked"
            elif item["price"] is None:
                item["status"] = "maxed"
            elif credits < item["price"]:
                item["status"] = "insufficient_credits"
            else:
                item["status"] = "available"

    def _process_shop_purchase_results(self):
        while not self.economy.results.empty():
            request_id, success, message, items = self.economy.results.get_nowait()
            if request_id != self.shop_purchase_request_id:
                continue

            if success:
                self.economy._credits = max(
                    0, self.economy.credits - self.shop_purchase_price
                )
                if self.shop_purchase_key and (
                    self.shop_purchase_key.startswith("ball_color_")
                    or self.shop_purchase_key == "ball_skin_iran"
                ):
                    self.ball_color = self.shop.get_active_ball_color()
                    self.ball_skin = (
                        "iran_flag"
                        if self.shop.get_active_ball_color_key() == "ball_skin_iran"
                        else None
                    )
                    for ball in self.game["balls"]:
                        ball.color = self.ball_color
                        ball.skin = self.ball_skin

            if items is not None:
                self.shop_items = items

            self.shop_purchase_pending = False
            self.shop_purchase_request_id = None
            self.shop_purchase_price = 0
            self.shop_purchase_key = None
            self._refresh_shop_statuses()
            self.shop_message = message
            self.shop_message_timer = 2.5

    def _purchase_selected_upgrade(self):
        if self.shop_purchase_pending:
            self.shop_message = "Purchase is still processing..."
            self.shop_message_timer = 1.5
            return

        items = self.shop_items
        if not items:
            return

        self._refresh_shop_statuses()
        self.shop_selection = max(0, min(self.shop_selection, len(items) - 1))
        item = items[self.shop_selection]

        if item.get("category") == "cosmetic" and item["status"] in ("equipped", "owned"):
            if item["status"] == "equipped":
                self.shop_message = f'{item["name"]} is already equipped.'
            else:
                success, message = self.shop.purchase(item["key"])
                self.shop_message = message
                if success:
                    self.ball_color = self.shop.get_active_ball_color()
                    self.ball_skin = (
                        "iran_flag"
                        if self.shop.get_active_ball_color_key() == "ball_skin_iran"
                        else None
                    )
                    for ball in self.game["balls"]:
                        ball.color = self.ball_color
                        ball.skin = self.ball_skin
                    self.shop_items = self.shop.get_items()
                    self._refresh_shop_statuses()

            self.shop_message_timer = 2.5
            return

        if item["status"] != "available":
            messages = {
                "locked": "Required upgrade not purchased yet.",
                "insufficient_credits": "Not enough credits.",
                "maxed": "This upgrade is already at maximum level.",
                "unlocked": "Emergency Bomb is already unlocked.",
            }
            self.shop_message = messages.get(item["status"], "Cannot purchase.")
            self.shop_message_timer = 2.5
            return

        self.shop_purchase_price = item["price"]
        self.shop_purchase_key = item["key"]
        self.shop_purchase_request_id = self.economy.request_shop_purchase(
            self.shop, item["key"]
        )
        self.shop_purchase_pending = True
        self.shop_message = "Processing purchase..."
        self.shop_message_timer = 2.5

    def draw_shop(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((2, 4, 18, 246))
        self.screen.blit(overlay, (0, 0))

        draw_text(self.screen, "UPGRADE BAY", self.large, CYAN, (WIDTH // 2, 36))
        draw_text(
            self.screen, "PERMANENT UPGRADES  /  BALL COLORS",
            self.small, MUTED, (WIDTH // 2, 70),
        )

        credits = self.economy.credits
        credit_box = pygame.Rect(WIDTH - 245, 17, 195, 38)
        pygame.draw.rect(self.screen, (18, 30, 54), credit_box, border_radius=11)
        pygame.draw.rect(self.screen, (115, 91, 46), credit_box, 1, border_radius=11)
        draw_text(self.screen, f"{credits:,} CR", self.font, GOLD, credit_box.center)

        self._refresh_shop_statuses()
        items = self.shop_items
        if not items:
            draw_text(self.screen, "NO UPGRADES AVAILABLE", self.font, MUTED,
                      (WIDTH // 2, HEIGHT // 2))
            return

        self.shop_selection = max(0, min(self.shop_selection, len(items) - 1))
        viewport = pygame.Rect(42, 100, WIDTH - 84, HEIGHT - 178)
        gap_x, gap_y = 14, 12
        card_w = (viewport.width - gap_x) // 2
        card_h = 138
        row_step = card_h + gap_y
        rows = (len(items) + 1) // 2
        content_h = rows * row_step - gap_y
        self.shop_scroll_max = max(0, content_h - viewport.height)
        self.shop_scroll = max(0, min(getattr(self, "shop_scroll", 0),
                                      self.shop_scroll_max))
        self.shop_card_rects = []

        self.screen.set_clip(viewport)
        for i, item in enumerate(items):
            x = viewport.x + (i % 2) * (card_w + gap_x)
            y = viewport.y + (i // 2) * row_step - self.shop_scroll
            rect = pygame.Rect(x, y, card_w, card_h)
            self.shop_card_rects.append((i, rect))

            status = item["status"]
            accent = {
                "available": GOLD,
                "locked": PINK,
                "insufficient_credits": PINK,
                "maxed": (90, 220, 160),
                "unlocked": (90, 220, 160),
                "equipped": (90, 220, 160),
                "owned": (90, 220, 160),
            }.get(status, MUTED)

            selected = i == self.shop_selection
            fill = (17, 32, 59) if selected else (8, 16, 35)
            border = CYAN if selected else (37, 55, 83)
            pygame.draw.rect(self.screen, fill, rect, border_radius=13)
            pygame.draw.rect(self.screen, border, rect, 2 if selected else 1,
                             border_radius=13)
            pygame.draw.rect(self.screen, accent,
                             (rect.x + 1, rect.y + 12, 3, rect.height - 24),
                             border_radius=2)

            badge = pygame.Rect(rect.x + 14, rect.y + 15, 44, 44)
            if item.get("category") == "cosmetic":
                if item["key"] == "ball_skin_iran":
                    size = 44
                    flag = pygame.Surface((size, size), pygame.SRCALPHA)
                    green = (35, 159, 64)
                    red = (218, 0, 0)

                    pygame.draw.rect(flag, green, (0, 0, size, size // 3))
                    pygame.draw.rect(
                        flag, (255, 255, 255),
                        (0, size // 3, size, size // 3),
                    )
                    pygame.draw.rect(
                        flag, red, (0, 2 * size // 3, size, size // 3),
                    )

                    # Clip the tricolor to a circular flag preview.
                    radius = size // 2 - 1
                    for px in range(size):
                        for py in range(size):
                            if (
                                (px - size // 2) ** 2
                                + (py - size // 2) ** 2 > radius ** 2
                            ):
                                flag.set_at((px, py), (0, 0, 0, 0))

                    emblem_font = pygame.font.Font("/usr/share/fonts/truetype/freefont/FreeSerif.ttf", 17)
                    emblem = emblem_font.render("☫", True, red)
                    flag.blit(emblem, emblem.get_rect(center=badge.center))
                    self.screen.blit(flag, badge.topleft)
                    pygame.draw.circle(
                        self.screen, (205, 215, 230), badge.center, radius, 1
                    )
                else:
                    preview_color = item.get("color", CYAN)
                    pygame.draw.circle(
                        self.screen, preview_color, badge.center, 14
                    )
                    pygame.draw.circle(
                        self.screen, WHITE, badge.center, 14, 1
                    )
                    pygame.draw.circle(
                        self.screen, preview_color, badge.center, 19, 1
                    )
            else:
                pygame.draw.rect(
                    self.screen, (23, 40, 68), badge, border_radius=12
                )
                pygame.draw.rect(
                    self.screen, accent, badge, 1, border_radius=12
                )
                symbol = {"mobility": "M", "offense": "O", "defense": "D"}.get(
                    item["category"], "*"
                )
                icon_surface = self.font.render(symbol, True, accent)
                self.screen.blit(
                    icon_surface, icon_surface.get_rect(center=badge.center)
                )

            name = item["name"]
            name_width = card_w - 76
            while name and self.font.size(name)[0] > name_width:
                name = name[:-1]
            if name != item["name"]:
                name = name.rstrip() + "..."
            self.screen.blit(
                self.font.render(name, True, CYAN if selected else WHITE),
                (rect.x + 70, rect.y + 16),
            )

            if item.get("category") == "cosmetic":
                level = {
                    "equipped": "EQUIPPED",
                    "owned": "OWNED",
                    "available": "COLOR",
                    "insufficient_credits": "COLOR",
                }.get(status, "COLOR")
            else:
                level = (
                    "LOCKED" if status == "locked"
                    else "UNLOCKED" if status == "unlocked"
                    else f"LV {item['level']}/{item['max_level']}"
                )
            level_surface = self.small.render(level, True, accent)
            self.screen.blit(level_surface, (rect.right - level_surface.get_width() - 12,
                                             rect.y + 48))

            description = item["description"]
            desc_width = card_w - 28
            while description and self.small.size(description)[0] > desc_width:
                description = description[:-1]
            if description != item["description"]:
                description = description.rstrip() + "..."
            self.screen.blit(self.small.render(description, True, MUTED),
                             (rect.x + 14, rect.y + 76))

            pygame.draw.line(self.screen, (34, 49, 73),
                             (rect.x + 14, rect.y + 101),
                             (rect.right - 14, rect.y + 101), 1)

            if status == "equipped":
                label = "CURRENT BALL COLOR"
            elif status == "owned":
                label = "ENTER / CLICK TO EQUIP"
            elif status == "available":
                label = f"{item['price']:,} CR  /  ENTER TO BUY"
            elif status == "locked":
                req = item["missing_requirements"][0]
                label = f"REQUIRES {req['name'].upper()} LV {req['required_level']}"
            elif status == "insufficient_credits":
                label = f"NEED {item['price']:,} CR"
            elif status == "unlocked":
                key_name = item["key"]
                control = "R" if key_name == "row_clear" else "B"
                label = f"UNLOCKED  /  PRESS {control} IN RUN"
            else:
                label = "MAX LEVEL REACHED"

            while label and self.small.size(label)[0] > card_w - 28:
                label = label[:-1]
            if label and label != label.rstrip():
                label = label.rstrip()
            self.screen.blit(self.small.render(label, True, accent),
                             (rect.x + 14, rect.y + 111))

        self.screen.set_clip(None)

        if self.shop_scroll_max > 0:
            track = pygame.Rect(WIDTH - 24, viewport.y, 4, viewport.height)
            pygame.draw.rect(self.screen, (24, 39, 63), track, border_radius=2)
            thumb_h = max(28, int(viewport.height ** 2 / content_h))
            thumb_y = viewport.y + int(
                (viewport.height - thumb_h) * self.shop_scroll / self.shop_scroll_max
            )
            pygame.draw.rect(self.screen, CYAN,
                             (track.x, thumb_y, track.width, thumb_h),
                             border_radius=2)

        if self.shop_message_timer > 0 and self.shop_message:
            msg = self.small.render(self.shop_message, True, GOLD)
            self.screen.blit(msg, msg.get_rect(center=(WIDTH // 2, HEIGHT - 55)))

        draw_text(
            self.screen,
            "ARROWS: SELECT   ENTER/CLICK: BUY OR EQUIP   WHEEL: SCROLL   ESC: BACK",
            self.small, WHITE, (WIDTH // 2, HEIGHT - 20),
        )

    def _activate_emergency_bomb(self):
        game = self.game

        if game.get("bomb_level", 0) <= 0:
            self.shop_message = "Emergency Bomb is locked. Unlock it in the shop."
            self.shop_message_timer = 2.5
            return

        if not game["bricks"]:
            self.shop_message = "No bricks left to destroy."
            self.shop_message_timer = 2.0
            return

        # Finish pending rewards before checking the credit balance.
        self.economy.jobs.join()
        if not self.economy.db.spend_credits(120, "emergency_bomb_use"):
            self.economy._credits = self.economy.db.get_profile()["credits"]
            self.shop_message = "Emergency Bomb costs 120 CR. Not enough credits."
            self.shop_message_timer = 2.5
            return

        self.economy._credits = self.economy.db.get_profile()["credits"]
        targets = random.sample(game["bricks"], min(5, len(game["bricks"])))
        destroyed_count = 0

        for brick in targets:
            if brick not in game["bricks"]:
                continue

            game["bricks"].remove(brick)
            reward = self.economy.brick_destroyed(brick.max_hp)
            points = 20 * brick.max_hp * min(5, 1 + game["combo"] // 8)
            game["score"] += points
            game["combo"] += 1
            game["combo_timer"] = 1.8
            destroyed_count += 1

            self.floating_texts.append(
                FloatingText(
                    brick.rect.centerx, brick.rect.centery + 14,
                    f"+{reward} CR", GOLD
                )
            )
            self.floating_texts.append(
                FloatingText(
                    brick.rect.centerx, brick.rect.centery,
                    f"+{points}", brick.color
                )
            )
            self.emit_particles(
                brick.rect.centerx, brick.rect.centery, brick.color, 14
            )
            if random.random() < 0.14:
                game["powerups"].append(
                    PowerUp(brick.rect.centerx, brick.rect.centery)
                )

        self.floating_texts.append(
            FloatingText(
                WIDTH / 2, HEIGHT / 2,
                f"EMERGENCY BOMB: {destroyed_count} BRICKS!", CYAN
            )
        )
        self.screen_shake = max(self.screen_shake, 0.12)
        play_sound("power")

    def _activate_row_clear(self):
        game = self.game

        if game.get("row_clear_level", 0) <= 0:
            self.shop_message = "Row Clear is locked. Unlock it in the shop."
            self.shop_message_timer = 2.5
            return

        if not game["bricks"]:
            self.shop_message = "No bricks left to clear."
            self.shop_message_timer = 2.0
            return

        # Finish pending rewards before checking the credit balance.
        self.economy.jobs.join()
        if not self.economy.db.spend_credits(180, "row_clear_use"):
            self.economy._credits = self.economy.db.get_profile()["credits"]
            self.shop_message = "Row Clear costs 180 CR. Not enough credits."
            self.shop_message_timer = 2.5
            return

        self.economy._credits = self.economy.db.get_profile()["credits"]

        # Clear the lowest row currently present in the level.
        target_y = max(brick.rect.y for brick in game["bricks"])
        targets = [brick for brick in game["bricks"] if brick.rect.y == target_y]
        destroyed_count = 0

        for brick in targets:
            if brick not in game["bricks"]:
                continue

            game["bricks"].remove(brick)
            reward = self.economy.brick_destroyed(brick.max_hp)
            points = 20 * brick.max_hp * min(5, 1 + game["combo"] // 8)
            game["score"] += points
            game["combo"] += 1
            game["combo_timer"] = 1.8
            destroyed_count += 1

            self.floating_texts.append(
                FloatingText(
                    brick.rect.centerx, brick.rect.centery + 14,
                    f"+{reward} CR", GOLD
                )
            )
            self.floating_texts.append(
                FloatingText(
                    brick.rect.centerx, brick.rect.centery,
                    f"+{points}", brick.color
                )
            )
            self.emit_particles(
                brick.rect.centerx, brick.rect.centery, brick.color, 14
            )
            if random.random() < 0.14:
                game["powerups"].append(
                    PowerUp(brick.rect.centerx, brick.rect.centery)
                )

        self.floating_texts.append(
            FloatingText(
                WIDTH / 2, HEIGHT / 2,
                f"ROW CLEAR: {destroyed_count} BRICKS!", CYAN
            )
        )
        self.screen_shake = max(self.screen_shake, 0.12)
        play_sound("power")

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False
            return

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_m:
                enabled = audio.toggle_sound()
                self.sound_enabled = enabled

            if self.state == "menu":
                if event.key == pygame.K_c:
                    self.continue_run()
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.start_run()
                elif event.key == pygame.K_s:
                    self.shop_selection = 0
                    self.shop_message = ""
                    self.state = "shop"
                elif event.key == pygame.K_ESCAPE:
                    self.running = False

            elif self.state == "shop":
                if event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT):
                    count = len(self.shop_items)
                    if count:
                        if event.key in (pygame.K_UP, pygame.K_LEFT):
                            self.shop_selection = (self.shop_selection - 1) % count
                        else:
                            self.shop_selection = (self.shop_selection + 1) % count

                        row = self.shop_selection // 2
                        top = row * 150
                        bottom = top + 138
                        viewport_height = HEIGHT - 178
                        if top < self.shop_scroll:
                            self.shop_scroll = top
                        elif bottom > self.shop_scroll + viewport_height:
                            self.shop_scroll = bottom - viewport_height
                        self.shop_scroll = max(0, min(self.shop_scroll, self.shop_scroll_max))
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self._purchase_selected_upgrade()
                elif event.key == pygame.K_ESCAPE:
                    self.state = "menu"

            elif self.state == "playing":
                if event.key == pygame.K_r:
                    self._activate_row_clear()
                elif event.key == pygame.K_b:
                    self._activate_emergency_bomb()
                elif event.key == pygame.K_SPACE:
                    for ball in self.game["balls"]:
                        ball.launch()
                elif event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                    game = self.game
                    paddle = game["paddle"]

                    if game["shield_level"] <= 0:
                        self.shop_message = "Emergency Barrier is locked."
                        self.shop_message_timer = 2.0
                    elif (
                        game["shield_cooldown"] <= 0
                        and paddle.shield_timer <= 0
                    ):
                        paddle.shield_timer = 8.0
                        game["shield_cooldown"] = 18.0
                        self.floating_texts.append(
                            FloatingText(
                                paddle.x, paddle.y - 28,
                                "EMERGENCY BARRIER!", BLUE
                            )
                        )
                        play_sound("power")
                elif event.key in (pygame.K_p, pygame.K_ESCAPE):
                    self.state = "paused"
                elif event.key == pygame.K_r:
                    self.start_run()

            elif self.state == "paused":
                if event.key in (pygame.K_p, pygame.K_SPACE, pygame.K_RETURN):
                    self.state = "playing"
                elif event.key == pygame.K_ESCAPE:
                    self.state = "menu"

            elif self.state in ("gameover", "victory"):
                if event.key in (pygame.K_r, pygame.K_RETURN, pygame.K_SPACE):
                    self.start_run()
                elif event.key == pygame.K_ESCAPE:
                    self.state = "menu"

        elif event.type == pygame.MOUSEWHEEL and self.state == "shop":
            self.shop_scroll = max(
                0, min(self.shop_scroll - event.y * 48, self.shop_scroll_max)
            )

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.state == "menu":
                self.start_run()
            elif self.state == "shop":
                for index, rect in getattr(self, "shop_card_rects", []):
                    if rect.collidepoint(event.pos):
                        self.shop_selection = index
                        self._purchase_selected_upgrade()
                        break
            elif self.state == "paused":
                self.state = "playing"
            elif self.state in ("gameover", "victory"):
                self.start_run()

    def draw(self):
        self.draw_world()
        if self.state == "menu":
            self.draw_overlay("STARDRIFT", "A SPACE ARCADE SURVIVAL", [
                "PRESS ENTER OR CLICK TO START",
                f"PERSONAL BEST  {self.high_score:,}    ·    BEST SECTOR  {self.best_level:02d}",
                "C: CONTINUE SAVED RUN",
                "MOVE: A/D OR ARROWS / MOUSE   ·   LAUNCH: SPACE",
                "S: UPGRADE SHOP    P: PAUSE    M: SOUND    ESC: QUIT",
            ])
        elif self.state == "shop":
            self.draw_shop()
        elif self.state == "paused":
            self.draw_overlay("PAUSED", "Take a breath, pilot.", [
                "PRESS SPACE OR P TO RESUME",
                "ESC  ·  RETURN TO MAIN MENU",
                "M  ·  TOGGLE SOUND",
            ])
        elif self.state == "gameover":
            self.draw_overlay("SHIP LOST", f"FINAL SCORE  {self.game['score']:,}", [
                "PRESS R OR ENTER TO RUN AGAIN",
                f"PERSONAL BEST  {self.high_score:,}    ·    SECTOR {self.game['level']:02d}",
                "ESC  ·  MAIN MENU",
            ])
        elif self.state == "victory":
            self.draw_overlay("SECTOR CLEARED", "You survived the sector.", [
                "PRESS ENTER TO PLAY AGAIN",
                "ESC  ·  MAIN MENU",
            ])

        if self.screen_shake > 0 and self.state == "playing":
            dx, dy = random.randint(-2, 2), random.randint(-2, 2)
            frame = self.screen.copy()
            self.screen.fill(BG)
            self.screen.blit(frame, (dx, dy))
        pygame.display.flip()

    def run(self):
        while self.running:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.025)
            for event in pygame.event.get():
                self.handle_event(event)
            self.update(dt)
            self.draw()

        self.persist_score()
        self.economy.close()
        pygame.quit()
