import math

import pygame

from . import leaderboard, ui
from .camera import Camera
from .config import (
    COUNTDOWN_SECONDS,
    DEFAULT_WINDOW_SIZE,
    FLAP_COOLDOWN,
    FPS,
    GAME_OVER_INPUT_DELAY,
    MAX_NAME_LENGTH,
    MENU_SELECT_FRAMES,
    WINDOW_TITLE,
)
from .game import FlappyGame
from .hand_tracker import HandTracker
from .ui import PHASE_BOARD, PHASE_ENTRY

MENU = "menu"
COUNTDOWN = "countdown"
PLAYING = "playing"
GAME_OVER = "game_over"

WINDOWRESIZED = getattr(pygame, "WINDOWRESIZED", -1)


def main() -> None:
    pygame.init()
    pygame.display.set_caption(WINDOW_TITLE)
    flags = pygame.RESIZABLE
    fullscreen = False
    windowed_size = DEFAULT_WINDOW_SIZE
    screen = pygame.display.set_mode(windowed_size, flags)
    clock = pygame.time.Clock()

    camera = Camera()
    tracker = HandTracker()
    game = FlappyGame()

    state = MENU
    phase = PHASE_ENTRY
    selected = "easy"
    hand_frames = 0
    countdown_left = COUNTDOWN_SECONDS
    name_buffer = ""
    cursor_timer = 0.0
    input_delay = 0.0
    elapsed = 0.0
    saved = False
    prev_gesture: str | None = None
    flap_cooldown = 0.0
    entries: dict[str, list[dict]] = {
        difficulty: leaderboard.load(difficulty)
        for difficulty in leaderboard.DIFFICULTIES
    }

    try:
        running = True
        while running:
            dt = clock.tick(FPS) / 1000.0
            cursor_timer += dt
            elapsed += dt
            if input_delay > 0:
                input_delay -= dt
            if flap_cooldown > 0:
                flap_cooldown -= dt

            frame = camera.read()
            hand_state = tracker.process(frame) if frame is not None else None
            if hand_state is None:
                hand_y, gesture = None, None
            else:
                hand_y, gesture = hand_state
            flap = False
            menu_confirm = False
            if gesture is not None and prev_gesture is None and flap_cooldown <= 0:
                flap_cooldown = FLAP_COOLDOWN
                flap = True
                menu_confirm = gesture == "fist"
            prev_gesture = gesture

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    continue

                if event.type == WINDOWRESIZED and not fullscreen:
                    if (
                        event.x > 0
                        and event.y > 0
                        and (event.x, event.y) != screen.get_size()
                    ):
                        windowed_size = (event.x, event.y)
                        screen = pygame.display.set_mode(windowed_size, flags)
                    continue

                if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                    fullscreen = not fullscreen
                    if fullscreen:
                        screen = pygame.display.set_mode((0, 0), flags | pygame.FULLSCREEN)
                    else:
                        screen = pygame.display.set_mode(windowed_size, flags)
                    continue

                if event.type == pygame.TEXTINPUT:
                    if (
                        state == GAME_OVER
                        and phase == PHASE_ENTRY
                        and input_delay <= 0
                    ):
                        for ch in event.text:
                            if ch.isprintable() and len(name_buffer) < MAX_NAME_LENGTH:
                                name_buffer += ch
                    continue

                if event.type != pygame.KEYDOWN:
                    continue

                if event.key == pygame.K_ESCAPE:
                    if state == GAME_OVER and phase == PHASE_ENTRY:
                        phase = PHASE_BOARD
                        saved = False
                    elif state == PLAYING or state == COUNTDOWN:
                        state = MENU
                        hand_frames = 0
                    else:
                        running = False

                elif state == MENU and event.key in (pygame.K_1, pygame.K_KP1):
                    selected = "easy"

                elif state == MENU and event.key in (pygame.K_2, pygame.K_KP2):
                    selected = "hard"

                elif state == MENU and event.key == pygame.K_SPACE:
                    game = FlappyGame(selected)
                    countdown_left = COUNTDOWN_SECONDS
                    state = COUNTDOWN

                elif (
                    state == GAME_OVER
                    and phase == PHASE_ENTRY
                    and input_delay <= 0
                ):
                    if event.key == pygame.K_BACKSPACE:
                        name_buffer = name_buffer[:-1]
                    elif event.key == pygame.K_RETURN:
                        name = name_buffer.strip()
                        if name:
                            entries[selected] = leaderboard.save(
                                name, game.score, selected
                            )
                            saved = True
                        else:
                            saved = False
                        phase = PHASE_BOARD

                elif (
                    state == GAME_OVER
                    and phase == PHASE_BOARD
                    and input_delay <= 0
                ):
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        state = MENU
                        phase = PHASE_ENTRY
                        name_buffer = ""
                        hand_frames = 0

            if state == MENU:
                if hand_y is not None:
                    hand_frames += 1
                    selected = "easy" if hand_y < 0.5 else "hard"
                else:
                    hand_frames = 0
                if hand_frames >= MENU_SELECT_FRAMES and menu_confirm:
                    game = FlappyGame(selected)
                    countdown_left = COUNTDOWN_SECONDS
                    state = COUNTDOWN

            elif state == COUNTDOWN:
                countdown_left -= dt
                if countdown_left <= 0:
                    state = PLAYING

            elif state == PLAYING:
                game.update(dt, hand_y, flap)
                if not game.alive:
                    state = GAME_OVER
                    phase = PHASE_ENTRY
                    name_buffer = ""
                    input_delay = GAME_OVER_INPUT_DELAY

            screen = pygame.display.get_surface()
            layout = ui.compute_layout(*screen.get_size())

            if state == MENU:
                ui.draw_menu(screen, camera.ok, selected, layout, frame)
            else:
                ui.draw_playfield(screen, game, layout, elapsed, frame)
                if state == COUNTDOWN:
                    ui.draw_countdown(screen, max(1, math.ceil(countdown_left)), layout)
                elif state == GAME_OVER:
                    ui.draw_game_over(
                        screen, game, phase, name_buffer, cursor_timer, saved, layout
                    )

            ui.draw_camera_panel(screen, frame, hand_y, layout)
            ui.draw_hand_status(screen, hand_y, layout)
            if state == MENU:
                ui.draw_menu_prompt(screen, camera.ok, hand_frames, layout)
            if state == GAME_OVER:
                highlight = (name_buffer.strip(), game.score, selected) if saved else None
            else:
                highlight = None
            ui.draw_leaderboard(screen, entries, layout, highlight)

            pygame.display.flip()
    finally:
        tracker.close()
        camera.close()
        pygame.quit()
