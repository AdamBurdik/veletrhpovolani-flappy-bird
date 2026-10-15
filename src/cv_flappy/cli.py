import math

import pygame

from . import leaderboard, ui
from .camera import Camera, CameraWorker
from .config import (
    CAMERA_DIM_SCREENSAVER,
    COUNTDOWN_SECONDS,
    DEFAULT_WINDOW_SIZE,
    FLAP_COOLDOWN,
    FPS,
    GAME_OVER_INPUT_DELAY,
    GROUND_Y,
    INTRO_FPS,
    INTRO_MIN_SECONDS,
    INTRO_MOVE_SWING,
    MAX_NAME_LENGTH,
    MENU_SELECT_FRAMES,
    PIPE_WIDTH,
    PLAYFIELD_MAP_MARGIN,
    SCREENSAVER_DEMO_MODE,
    SCREENSAVER_ENABLED,
    SCREENSAVER_GHOST_HAND,
    SCREENSAVER_RESTART_DELAY,
    SCREENSAVER_SHOW_CAMERA,
    SCREENSAVER_SHOW_LEADERBOARD,
    SCREENSAVER_TARGET_SMOOTHING,
    SCREENSAVER_TIMEOUT,
    SCREENSAVER_WAKE_DELAY,
    SCREENSAVER_WAKE_SWING,
    SCREENSAVER_WOBBLE,
    VIRTUAL_PLAYFIELD_H,
    WINDOW_TITLE,
)
from .game import FlappyGame, blend
from .hand_tracker import HandTracker, HandWorker, playfield_to_hand
from .sound import SoundManager
from .stt import Listener
from .tts import Speech

MENU = "menu"
INTRO = "intro"
COUNTDOWN = "countdown"
PLAYING = "playing"
GAME_OVER = "game_over"
SCREENSAVER = "screensaver"

WINDOWRESIZED = getattr(pygame, "WINDOWRESIZED", -1)


def _flap_pressed(gesture: str | None, prev_gesture: str | None) -> bool:
    if gesture == "fist":
        return prev_gesture != "fist"
    if gesture == "pinch":
        return prev_gesture is None
    return False


def _demo_target(game, elapsed: float) -> float:
    bird = game.bird
    target = VIRTUAL_PLAYFIELD_H * 0.5
    for pipe in game.pipes:
        if pipe.x + PIPE_WIDTH >= bird.x - bird.radius:
            target = pipe.gap_y + math.sin(elapsed * 3.0) * SCREENSAVER_WOBBLE
            break
    return target


def main() -> None:
    pygame.init()
    pygame.display.set_caption(WINDOW_TITLE)
    flags = pygame.RESIZABLE
    fullscreen = False
    windowed_size = DEFAULT_WINDOW_SIZE
    screen = pygame.display.set_mode(windowed_size, flags)
    clock = pygame.time.Clock()

    camera = Camera()
    camera_worker = CameraWorker(camera)
    tracker = HandTracker()
    worker = HandWorker(tracker)
    game = FlappyGame()
    sfx = SoundManager()
    voice = Speech()
    listener = Listener()

    state = MENU
    selected = "easy"
    hand_frames = 0
    countdown_left = COUNTDOWN_SECONDS
    intro_t = 0.0
    intro_hand_min = 1.0
    intro_hand_max = 0.0
    name_buffer = ""
    cursor_timer = 0.0
    input_delay = 0.0
    stt_started = False
    elapsed = 0.0
    prev_gesture: str | None = None
    flap_cooldown = 0.0
    last_activity = 0.0
    wake_grace = 0.0
    demo_game: FlappyGame | None = None
    demo_restart = 0.0
    demo_target = VIRTUAL_PLAYFIELD_H * 0.5
    ghost_hand_y = 0.5
    ss_hand_min = 1.0
    ss_hand_max = 0.0
    last_frame = None
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
            if wake_grace > 0:
                wake_grace -= dt

            frame = camera_worker.latest()
            if frame is not None and frame is not last_frame:
                worker.submit(frame)
                last_frame = frame
            hand = worker.latest()
            if hand is None:
                hand_y, gesture = None, None
            else:
                hand_y, gesture = hand.hand_y, hand.gesture
            activity = hand is not None
            key_pressed = False
            wants_screensaver = False
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

                if event.type == pygame.KEYDOWN:
                    activity = True
                    key_pressed = True
                    if event.key in (pygame.K_0, pygame.K_KP0):
                        wants_screensaver = True
                        continue

                if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                    fullscreen = not fullscreen
                    if fullscreen:
                        screen = pygame.display.set_mode((0, 0), flags | pygame.FULLSCREEN)
                    else:
                        screen = pygame.display.set_mode(windowed_size, flags)
                    continue

                if event.type == pygame.TEXTINPUT:
                    if state == GAME_OVER and input_delay <= 0:
                        for ch in event.text:
                            if ch.isprintable() and len(name_buffer) < MAX_NAME_LENGTH:
                                name_buffer += ch
                    continue

                if event.type != pygame.KEYDOWN:
                    continue

                if event.key == pygame.K_ESCAPE:
                    if state == GAME_OVER:
                        listener.cancel()
                        state = MENU
                        name_buffer = ""
                        hand_frames = 0
                        stt_started = False
                    elif state == PLAYING or state == COUNTDOWN or state == INTRO:
                        state = MENU
                        hand_frames = 0
                    else:
                        running = False

                elif state == MENU and event.key in (pygame.K_1, pygame.K_KP1):
                    selected = "easy"

                elif state == MENU and event.key in (pygame.K_2, pygame.K_KP2):
                    selected = "hard"

                elif state == MENU and wake_grace <= 0 and event.key == pygame.K_SPACE:
                    game = FlappyGame(selected)
                    intro_t = 0.0
                    intro_hand_min = 1.0
                    intro_hand_max = 0.0
                    state = INTRO

                elif (
                    state == INTRO
                    and intro_t >= INTRO_MIN_SECONDS
                    and event.key in (pygame.K_SPACE, pygame.K_RETURN)
                ):
                    countdown_left = COUNTDOWN_SECONDS
                    state = COUNTDOWN

                elif state == GAME_OVER and input_delay <= 0:
                    if event.key == pygame.K_BACKSPACE:
                        name_buffer = ""
                        listener.start()
                        stt_started = True
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        listener.cancel()
                        name = name_buffer.strip()
                        if name:
                            entries[selected] = leaderboard.save(
                                name, game.score, selected
                            )
                            voice.say(name)
                        state = MENU
                        name_buffer = ""
                        hand_frames = 0
                        stt_started = False

            if activity:
                last_activity = elapsed

            if (
                wants_screensaver
                or (
                    SCREENSAVER_ENABLED
                    and state in (MENU, GAME_OVER)
                    and elapsed - last_activity >= SCREENSAVER_TIMEOUT
                )
            ):
                listener.cancel()
                name_buffer = ""
                stt_started = False
                hand_frames = 0
                demo_game = FlappyGame(SCREENSAVER_DEMO_MODE)
                demo_restart = 0.0
                demo_target = VIRTUAL_PLAYFIELD_H * 0.5
                ghost_hand_y = 0.5
                ss_hand_min = 1.0
                ss_hand_max = 0.0
                key_pressed = False
                state = SCREENSAVER
                last_activity = elapsed

            if state == MENU:
                if hand_y is not None:
                    hand_frames += 1
                    selected = "easy" if hand_y < 0.5 else "hard"
                else:
                    hand_frames = 0
                if hand_frames >= MENU_SELECT_FRAMES and confirm and wake_grace <= 0:
                    game = FlappyGame(selected)
                    intro_t = 0.0
                    intro_hand_min = 1.0
                    intro_hand_max = 0.0
                    state = INTRO

            elif state == INTRO:
                intro_t += dt
                if game.difficulty == "hard":
                    start_gesture = fist_pressed
                elif intro_t >= INTRO_MIN_SECONDS and hand_y is not None:
                    intro_hand_min = min(intro_hand_min, hand_y)
                    intro_hand_max = max(intro_hand_max, hand_y)
                    start_gesture = (
                        intro_hand_max - intro_hand_min >= INTRO_MOVE_SWING
                    )
                else:
                    start_gesture = False
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
                    name_buffer = ""
                    input_delay = GAME_OVER_INPUT_DELAY
                    stt_started = False

            elif state == GAME_OVER:
                if input_delay <= 0 and not stt_started:
                    listener.start()
                    stt_started = True
                if listener.done:
                    listener.done = False
                    heard = listener.text.strip()
                    if heard:
                        name_buffer = heard[:MAX_NAME_LENGTH]

            elif state == SCREENSAVER:
                if hand_y is not None:
                    ss_hand_min = min(ss_hand_min, hand_y)
                    ss_hand_max = max(ss_hand_max, hand_y)
                if (
                    key_pressed
                    or ss_hand_max - ss_hand_min >= SCREENSAVER_WAKE_SWING
                ):
                    state = MENU
                    wake_grace = SCREENSAVER_WAKE_DELAY
                    hand_frames = 0
                    last_activity = elapsed
                elif demo_restart > 0:
                    demo_restart -= dt
                    if demo_restart <= 0:
                        demo_game = FlappyGame(SCREENSAVER_DEMO_MODE)
                        demo_target = VIRTUAL_PLAYFIELD_H * 0.5
                        ghost_hand_y = 0.5
                elif demo_game is not None:
                    raw_target = _demo_target(demo_game, elapsed)
                    demo_target = blend(
                        demo_target, raw_target, SCREENSAVER_TARGET_SMOOTHING, dt
                    )
                    ghost_hand_y = playfield_to_hand(
                        demo_target,
                        float(PLAYFIELD_MAP_MARGIN),
                        float(GROUND_Y - PLAYFIELD_MAP_MARGIN),
                    )
                    demo_game.update(dt, ghost_hand_y, False)
                    if not demo_game.alive:
                        demo_restart = SCREENSAVER_RESTART_DELAY

            screen = pygame.display.get_surface()
            if state == SCREENSAVER:
                layout = ui.compute_screensaver_layout(*screen.get_size())
                ui.draw_playfield(
                    screen, demo_game, layout, elapsed, frame,
                    dim=CAMERA_DIM_SCREENSAVER,
                )
                if SCREENSAVER_GHOST_HAND:
                    ui.draw_ghost_hand(screen, layout, ghost_hand_y)
                ui.draw_wake_cue(screen, layout, elapsed)
                ui.draw_demo_banner(screen, layout, elapsed)
                if SCREENSAVER_SHOW_CAMERA:
                    ui.draw_camera_panel(screen, frame, hand, layout)
                if SCREENSAVER_SHOW_LEADERBOARD:
                    ui.draw_leaderboard(screen, entries, layout)
                pygame.display.flip()
                continue
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
                        screen,
                        game,
                        name_buffer,
                        cursor_timer,
                        listener.listening,
                        listener.level,
                        listener.enabled,
                        layout,
                    )

            ui.draw_camera_panel(screen, frame, hand, layout)
            ui.draw_hand_status(screen, hand_y, layout)
            if state == MENU:
                ui.draw_menu_prompt(screen, camera.ok, hand_frames, layout)
            ui.draw_leaderboard(screen, entries, layout)

            pygame.display.flip()
    finally:
        worker.stop()
        camera_worker.stop()
        tracker.close()
        camera.close()
        listener.close()
        pygame.quit()
