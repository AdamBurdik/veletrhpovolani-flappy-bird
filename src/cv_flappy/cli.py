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
    INTRO_FPS,
    INTRO_MIN_SECONDS,
    MAX_NAME_LENGTH,
    MENU_SELECT_FRAMES,
    WINDOW_TITLE,
)
from .game import FlappyGame
from .hand_tracker import HandTracker
from .sound import SoundManager
from .tts import Speech
from .ui import PHASE_BOARD, PHASE_ENTRY

MENU = "menu"
INTRO = "intro"
COUNTDOWN = "countdown"
PLAYING = "playing"
GAME_OVER = "game_over"

WINDOWRESIZED = getattr(pygame, "WINDOWRESIZED", -1)


def _flap_pressed(gesture: str | None, prev_gesture: str | None) -> bool:
    if gesture == "fist":
        return prev_gesture != "fist"
    if gesture == "pinch":
        return prev_gesture is None
    return False


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
    sfx = SoundManager()
    voice = Speech()

    state = MENU
    phase = PHASE_ENTRY
    selected = "easy"
    hand_frames = 0
    countdown_left = COUNTDOWN_SECONDS
    intro_t = 0.0
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
            pressed = _flap_pressed(gesture, prev_gesture)
            if flap_cooldown <= 0 and pressed:
                flap_cooldown = FLAP_COOLDOWN
                flap = True
                if state == PLAYING and selected == "hard":
                    sfx.play("flap")
            fist_pressed = gesture == "fist" and prev_gesture != "fist"
            pinch_pressed = gesture == "pinch" and prev_gesture != "pinch"
            confirm = fist_pressed or pinch_pressed
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
                    elif state == PLAYING or state == COUNTDOWN or state == INTRO:
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
                    intro_t = 0.0
                    state = INTRO

                elif (
                    state == INTRO
                    and intro_t >= INTRO_MIN_SECONDS
                    and event.key in (pygame.K_SPACE, pygame.K_RETURN)
                ):
                    countdown_left = COUNTDOWN_SECONDS
                    state = COUNTDOWN

                elif (
                    state == GAME_OVER
                    and phase == PHASE_ENTRY
                    and input_delay <= 0
                ):
                    if event.key == pygame.K_BACKSPACE:
                        name_buffer = name_buffer[:-1]
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        name = name_buffer.strip()
                        if name:
                            entries[selected] = leaderboard.save(
                                name, game.score, selected
                            )
                            saved = True
                            voice.say(name)
                        else:
                            saved = False
                        phase = PHASE_BOARD

                elif (
                    state == GAME_OVER
                    and phase == PHASE_BOARD
                    and input_delay <= 0
                ):
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
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
                if hand_frames >= MENU_SELECT_FRAMES and confirm:
                    game = FlappyGame(selected)
                    intro_t = 0.0
                    state = INTRO

            elif state == INTRO:
                intro_t += dt
                start_gesture = (
                    fist_pressed if game.difficulty == "hard" else pinch_pressed
                )
                if intro_t >= INTRO_MIN_SECONDS and start_gesture:
                    countdown_left = COUNTDOWN_SECONDS
                    state = COUNTDOWN

            elif state == COUNTDOWN:
                countdown_left -= dt
                if countdown_left <= 0:
                    state = PLAYING

            elif state == PLAYING:
                prev_score = game.score
                was_alive = game.alive
                game.update(dt, hand_y, flap)
                if game.score > prev_score:
                    sfx.play("point")
                if was_alive and not game.alive:
                    sfx.play("die")
                    state = GAME_OVER
                    phase = PHASE_ENTRY
                    name_buffer = ""
                    input_delay = GAME_OVER_INPUT_DELAY

            elif (
                state == GAME_OVER
                and phase == PHASE_BOARD
                and input_delay <= 0
                and confirm
            ):
                state = MENU
                phase = PHASE_ENTRY
                name_buffer = ""
                hand_frames = 0

            screen = pygame.display.get_surface()
            layout = ui.compute_layout(*screen.get_size())

            if state == MENU:
                ui.draw_menu(screen, camera.ok, selected, layout, frame)
            else:
                ui.draw_playfield(screen, game, layout, elapsed, frame)
                if state == INTRO:
                    ui.draw_intro(
                        screen,
                        game.difficulty,
                        int(intro_t * INTRO_FPS),
                        layout,
                        hand_y is not None,
                        elapsed,
                        ready=intro_t >= INTRO_MIN_SECONDS,
                    )
                elif state == COUNTDOWN:
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
