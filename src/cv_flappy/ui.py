import math
from dataclasses import dataclass

import pygame

from .camera import frame_to_surface
from .config import (
    BG_DARK,
    BLACK,
    BOX_BG,
    BROWN,
    BRONZE,
    CAMERA_DIM_MENU,
    CAMERA_DIM_PLAY,
    CAM_MAX_W,
    CAM_MIN_W,
    CAM_W_FRAC,
    CLOUD,
    DARK_BROWN,
    DARK_GREEN,
    GOLD,
    GRAY,
    GRASS,
    GREEN,
    INPUT_BOX,
    LB_MAX_W,
    LB_MIN_W,
    LB_W_FRAC,
    MARGIN,
    ORANGE,
    PANEL_BORDER,
    PIPE_CAP_H,
    PIPE_LIGHT,
    PIPE_WIDTH,
    RED,
    SILVER,
    SKY_BOTTOM,
    SKY_TOP,
    SUN,
    SUN_HALO,
    TOP_N_PER_BOARD,
    VIRTUAL_PLAYFIELD_H,
    VIRTUAL_PLAYFIELD_W,
    WHITE,
    YELLOW,
    BIRD_RADIUS,
    GROUND_H,
    GROUND_Y,
)
from .leaderboard import DIFFICULTIES

PHASE_ENTRY = "entry"
PHASE_BOARD = "board"

_font_cache: dict[int, pygame.font.Font] = {}
_sky_cache: dict[tuple[int, int], pygame.Surface] = {}
_dim_cache: dict[tuple[int, int, int], pygame.Surface] = {}

CLOUDS = [
    (0.10, 90, 14.0, 1.0),
    (0.45, 170, 9.0, 0.8),
    (0.70, 70, 12.0, 1.15),
    (0.30, 250, 7.0, 0.7),
]

MEDALS = [GOLD, SILVER, BRONZE]


@dataclass
class Layout:
    pf_rect: pygame.Rect
    scale: float
    cam_rect: pygame.Rect
    lb_rect: pygame.Rect


def compute_layout(w: int, h: int) -> Layout:
    lb_w = max(LB_MIN_W, min(int(w * LB_W_FRAC), LB_MAX_W))
    cam_w = max(CAM_MIN_W, min(int(w * CAM_W_FRAC), CAM_MAX_W))
    cam_h = cam_w * 3 // 4
    left_w = cam_w + MARGIN * 2

    area_w = max(1, w - left_w - lb_w)
    scale = min(area_w / VIRTUAL_PLAYFIELD_W, h / VIRTUAL_PLAYFIELD_H)
    pf_w = int(VIRTUAL_PLAYFIELD_W * scale)
    pf_h = int(VIRTUAL_PLAYFIELD_H * scale)
    pf_rect = pygame.Rect(
        left_w + (area_w - pf_w) // 2, (h - pf_h) // 2, pf_w, pf_h
    )

    cam_rect = pygame.Rect(MARGIN, (h - cam_h) // 2, cam_w, cam_h)
    lb_rect = pygame.Rect(w - lb_w, 0, lb_w, h)
    return Layout(pf_rect, scale, cam_rect, lb_rect)


def _font(size: int) -> pygame.font.Font:
    if size not in _font_cache:
        _font_cache[size] = pygame.font.Font(None, size)
    return _font_cache[size]


def draw_text(
    surface: pygame.Surface,
    text: str,
    size: int,
    pos: tuple[float, float],
    color: tuple[int, int, int],
    align: str = "topleft",
    shadow: bool = False,
) -> pygame.Rect:
    if shadow:
        rect = draw_text(surface, text, size, (pos[0] + 2, pos[1] + 2), BLACK, align)
        draw_text(surface, text, size, pos, color, align)
        return rect
    image = _font(size).render(text, True, color)
    rect = image.get_rect()
    setattr(rect, align, (int(pos[0]), int(pos[1])))
    surface.blit(image, rect)
    return rect


def _sky(w: int, h: int) -> pygame.Surface:
    key = (w, h)
    if key not in _sky_cache:
        surface = pygame.Surface((w, h))
        top_r, top_g, top_b = SKY_TOP
        bot_r, bot_g, bot_b = SKY_BOTTOM
        for y in range(h):
            t = y / max(1, h - 1)
            color = (
                int(top_r + (bot_r - top_r) * t),
                int(top_g + (bot_g - top_g) * t),
                int(top_b + (bot_b - top_b) * t),
            )
            pygame.draw.line(surface, color, (0, y), (w, y))
        _sky_cache[key] = surface
    return _sky_cache[key]


def _dim(w: int, h: int, alpha: int) -> pygame.Surface:
    key = (w, h, alpha)
    if key not in _dim_cache:
        surface = pygame.Surface((w, h), pygame.SRCALPHA)
        surface.fill((0, 0, 0, alpha))
        _dim_cache[key] = surface
    return _dim_cache[key]


def draw_camera_background(
    surface: pygame.Surface, frame, dim: int
) -> None:
    sw, sh = surface.get_size()
    fh, fw = frame.shape[:2]
    cover = max(sw / fw, sh / fh)
    scaled = pygame.transform.smoothscale(
        frame_to_surface(frame), (int(fw * cover), int(fh * cover))
    )
    surface.blit(scaled, ((sw - scaled.get_width()) // 2, (sh - scaled.get_height()) // 2))
    surface.blit(_dim(sw, sh, dim), (0, 0))


def draw_playfield(
    surface: pygame.Surface, game, layout: Layout, elapsed: float, frame=None
) -> None:
    pf, s = layout.pf_rect, layout.scale
    if frame is not None:
        draw_camera_background(surface, frame, CAMERA_DIM_PLAY)
    else:
        surface.fill(BG_DARK)
        surface.blit(_sky(pf.width, pf.height), pf)
        _draw_sun(surface, layout)
        _draw_clouds(surface, layout, elapsed)

    clip = surface.get_clip()
    surface.set_clip(pf)

    _draw_pipes(surface, game, layout)
    _draw_ground(surface, layout)
    _draw_bird(surface, game.bird, layout, elapsed)
    _draw_score(surface, game, layout)

    surface.set_clip(clip)
    pygame.draw.rect(surface, PANEL_BORDER, pf, 3)


def _vxy(layout: Layout, x: float, y: float) -> tuple[int, int]:
    return (
        int(layout.pf_rect.x + x * layout.scale),
        int(layout.pf_rect.y + y * layout.scale),
    )


def _draw_sun(surface: pygame.Surface, layout: Layout) -> None:
    pf = layout.pf_rect
    cx, cy = _vxy(layout, pf.width / layout.scale - 90, 100)
    r = int(38 * layout.scale)
    halo = pygame.Rect(0, 0, r * 3 // 2, r * 3 // 2)
    halo.center = (cx, cy)
    pygame.draw.circle(surface, SUN_HALO, halo.center, halo.width // 2)
    pygame.draw.circle(surface, SUN, (cx, cy), r)


def _draw_clouds(
    surface: pygame.Surface, layout: Layout, elapsed: float
) -> None:
    pf_w = VIRTUAL_PLAYFIELD_W
    for x_frac, y, speed, size in CLOUDS:
        x = ((x_frac * pf_w + elapsed * speed) % (pf_w + 240)) - 120
        cx, cy = _vxy(layout, x, y)
        r = int(26 * size * layout.scale)
        pygame.draw.ellipse(surface, CLOUD, (cx - 2 * r, cy - r, 4 * r, 2 * r))
        pygame.draw.circle(surface, CLOUD, (cx - r // 2, cy - r // 2), r)
        pygame.draw.circle(surface, CLOUD, (cx + r // 2, cy - r // 3), r // 2 + 2)


def _draw_pipes(surface: pygame.Surface, game, layout: Layout) -> None:
    s = layout.scale
    w = int(PIPE_WIDTH * s)
    cap_h = int(PIPE_CAP_H * s)
    cap_w = w + int(8 * s)
    stripe_w = max(2, int(8 * s))
    for pipe in game.pipes:
        x = int(layout.pf_rect.x + pipe.x * s)
        gap_top = int(layout.pf_rect.y + pipe.gap_top * s)
        gap_bottom = int(layout.pf_rect.y + pipe.gap_bottom * s)
        pf_bottom = int(layout.pf_rect.bottom)

        pf_top = int(layout.pf_rect.y)
        top_body = pygame.Rect(x, pf_top, w, gap_top - cap_h - pf_top)
        top_cap = pygame.Rect(x - (cap_w - w) // 2, gap_top - cap_h, cap_w, cap_h)
        bottom_body = pygame.Rect(x, gap_bottom + cap_h, w, pf_bottom - gap_bottom - cap_h)
        bottom_cap = pygame.Rect(x - (cap_w - w) // 2, gap_bottom, cap_w, cap_h)

        stripe_x = max(2, int(4 * s))
        for body, cap in ((top_body, top_cap), (bottom_body, bottom_cap)):
            if body.height > 0:
                pygame.draw.rect(surface, GREEN, body)
                pygame.draw.rect(
                    surface, PIPE_LIGHT, (body.x + stripe_x, body.y, stripe_w, body.height)
                )
                pygame.draw.rect(surface, DARK_GREEN, body, 2)
            if cap.height > 0:
                pygame.draw.rect(surface, GREEN, cap)
                pygame.draw.rect(
                    surface, PIPE_LIGHT, (cap.x + stripe_x, cap.y, stripe_w, cap.height)
                )
                pygame.draw.rect(surface, DARK_GREEN, cap, 2)


def _draw_ground(surface: pygame.Surface, layout: Layout) -> None:
    pf, s = layout.pf_rect, layout.scale
    gy = int(pf.y + GROUND_Y * s)
    ground_rect = pygame.Rect(pf.x, gy, pf.width, pf.bottom - gy)
    pygame.draw.rect(surface, BROWN, ground_rect)
    pygame.draw.rect(surface, DARK_BROWN, ground_rect, 2)
    grass_rect = pygame.Rect(pf.x, gy, pf.width, int(8 * s))
    pygame.draw.rect(surface, GRASS, grass_rect)
    for gx in range(0, pf.width, max(8, int(24 * s))):
        pygame.draw.rect(
            surface, GRASS, (pf.x + gx, gy - int(4 * s), int(12 * s), int(4 * s))
        )


def _draw_bird(
    surface: pygame.Surface, bird, layout: Layout, elapsed: float
) -> None:
    s = layout.scale
    x, y = _vxy(layout, bird.x, bird.y)
    r = max(4, int(BIRD_RADIUS * s))
    wing_offset = int(math.sin(elapsed * 12) * 3 * s)

    pygame.draw.ellipse(
        surface, ORANGE, (x - int(10 * s), y - int(2 * s) + wing_offset, int(13 * s), int(8 * s))
    )
    pygame.draw.circle(surface, YELLOW, (x, y), r)
    pygame.draw.circle(surface, BLACK, (x, y), r, 2)
    pygame.draw.circle(surface, WHITE, (x + int(5 * s), y - int(5 * s)), max(3, int(5 * s)))
    pygame.draw.circle(surface, BLACK, (x + int(6 * s), y - int(5 * s)), max(2, int(2 * s)))
    beak_size = int(9 * s)
    pygame.draw.polygon(
        surface,
        ORANGE,
        [
            (x + r, y - int(2 * s)),
            (x + r + beak_size, y),
            (x + r, y + int(4 * s)),
        ],
    )


def _draw_score(surface: pygame.Surface, game, layout: Layout) -> None:
    pf = layout.pf_rect
    draw_text(
        surface,
        str(game.score),
        48,
        (pf.right - 24, pf.top + 16),
        WHITE,
        align="topright",
        shadow=True,
    )
    draw_text(
        surface,
        game.difficulty.upper(),
        20,
        (pf.right - 24, pf.top + 68),
        GOLD if game.difficulty == "hard" else WHITE,
        align="topright",
        shadow=True,
    )


def draw_camera_panel(
    surface: pygame.Surface, frame, hand_y: float | None, layout: Layout
) -> None:
    rect = layout.cam_rect
    if frame is not None:
        surface.blit(
            pygame.transform.smoothscale(frame_to_surface(frame), rect.size), rect
        )
        if hand_y is not None:
            line_y = rect.top + int(hand_y * rect.height)
            pygame.draw.line(
                surface, GREEN, (rect.left, line_y), (rect.right, line_y), 2
            )
    else:
        pygame.draw.rect(surface, GRAY, rect)
        draw_text(surface, "NO CAMERA", 22, rect.center, WHITE, align="center")
    pygame.draw.rect(surface, PANEL_BORDER, rect, 2)


def draw_hand_status(
    surface: pygame.Surface, hand_y: float | None, layout: Layout
) -> None:
    rect = layout.cam_rect
    color = GREEN if hand_y is not None else RED
    text = "HAND OK" if hand_y is not None else "NO HAND"
    dot = pygame.Rect(rect.left + 2, rect.bottom + 8, 10, 10)
    dot.centery = rect.bottom + 14
    pygame.draw.circle(surface, color, dot.center, 5)
    draw_text(surface, text, 20, (rect.left + 16, rect.bottom + 5), color)


def draw_menu_prompt(
    surface: pygame.Surface, camera_ok: bool, hand_frames: int, layout: Layout
) -> None:
    rect = layout.cam_rect
    y = rect.bottom + 34
    if camera_ok:
        if hand_frames > 0:
            draw_text(surface, "Close fist to start", 22, (rect.left, y), GREEN)
        else:
            draw_text(surface, "Show your hand", 22, (rect.left, y), WHITE)
    else:
        draw_text(surface, "No camera detected", 22, (rect.left, y), RED)


def draw_leaderboard(
    surface: pygame.Surface,
    entries: dict[str, list[dict]],
    layout: Layout,
    highlight: tuple[str, int, str] | None = None,
) -> None:
    rect = layout.lb_rect
    panel = pygame.Surface(rect.size, pygame.SRCALPHA)
    panel.fill((18, 22, 30, 210))
    surface.blit(panel, rect)
    pygame.draw.rect(surface, PANEL_BORDER, rect, 2)

    draw_text(
        surface,
        "LEADERBOARD",
        26,
        (rect.centerx, rect.top + 22),
        GOLD,
        align="center",
        shadow=True,
    )
    pygame.draw.line(
        surface,
        (90, 100, 115),
        (rect.left + 12, rect.top + 48),
        (rect.right - 12, rect.top + 48),
        2,
    )

    footer_h = 40
    section_title_h = 30
    row_h = 28
    usable = rect.height - 56 - footer_h - 2 * section_title_h
    rows_fit = max(1, min(TOP_N_PER_BOARD, usable // (2 * row_h)))

    y = rect.top + 58
    for difficulty in DIFFICULTIES:
        color = RED if difficulty == "hard" else GREEN
        draw_text(
            surface,
            f"{difficulty.upper()}  (1)" if difficulty == "easy" else f"{difficulty.upper()}  (2)",
            20,
            (rect.centerx, y),
            color,
            align="center",
        )
        y += section_title_h
        board = entries.get(difficulty, [])
        if not board:
            draw_text(
                surface, "No scores yet", 20, (rect.centerx, y + 10), GRAY,
                align="center",
            )
        else:
            for i, entry in enumerate(board[:rows_fit]):
                row_color = MEDALS[i] if i < len(MEDALS) else WHITE
                is_new = highlight is not None and (
                    highlight[2] == difficulty
                    and entry["name"] == highlight[0]
                    and entry["score"] == highlight[1]
                )
                if is_new:
                    row_bg = pygame.Rect(rect.left + 6, y - 2, rect.width - 12, row_h - 2)
                    highlight_surf = pygame.Surface(row_bg.size, pygame.SRCALPHA)
                    highlight_surf.fill((255, 215, 0, 40))
                    surface.blit(highlight_surf, row_bg)
                draw_text(surface, f"{i + 1}.", 20, (rect.left + 12, y), row_color,
                          align="midleft")
                draw_text(surface, str(entry["name"])[:12], 20, (rect.left + 46, y),
                          row_color, align="midleft")
                draw_text(surface, str(entry["score"]), 20, (rect.right - 12, y),
                          row_color, align="midright")
                y += row_h
        y += 14

    draw_text(
        surface, "F11 = fullscreen", 18, (rect.centerx, rect.bottom - 22), GRAY,
        align="center",
    )


def draw_menu(
    surface: pygame.Surface,
    camera_ok: bool,
    selected: str,
    layout: Layout,
    frame=None,
) -> None:
    sw, sh = surface.get_size()
    pf = layout.pf_rect
    if frame is not None:
        draw_camera_background(surface, frame, CAMERA_DIM_MENU)
    else:
        surface.blit(_sky(sw, sh), (0, 0))

    title_size = max(64, min(170, min(sw, sh) // 8))
    draw_text(
        surface, "FLAPPY BIRD", title_size, (sw / 2, sh * 0.15), WHITE,
        align="center", shadow=True,
    )

    option_zone_y = {
        "easy": pf.top + pf.height * 0.40,
        "hard": pf.top + pf.height * 0.56,
    }
    for difficulty in DIFFICULTIES:
        is_selected = difficulty == selected
        color = GREEN if difficulty == "easy" else RED
        text = f"[{1 if difficulty == 'easy' else 2}]  {difficulty.upper()}"
        y = option_zone_y[difficulty]
        if is_selected:
            draw_text(surface, "> " + text, 36, (pf.centerx, y), color,
                      align="center", shadow=True)
        else:
            draw_text(surface, text, 28, (pf.centerx, y), GRAY,
                      align="center")

    if camera_ok:
        controls = (
            "Bird follows your hand"
            if selected == "easy"
            else "Pipes follow your hand - close fist / pinch to flap"
        )
        draw_text(
            surface, controls, 24,
            (pf.centerx, pf.centery + 90), WHITE, align="center", shadow=True,
        )
    else:
        draw_text(
            surface, "No camera detected - SPACE to start anyway", 28,
            (pf.centerx, pf.centery + 90), RED, align="center", shadow=True,
        )
    draw_text(
        surface, "Hover hand over a mode to choose, close fist to start", 22,
        (pf.centerx, pf.bottom - 96), WHITE, align="center", shadow=True,
    )
    draw_text(
        surface, "1 / 2 = difficulty (keyboard)", 20,
        (pf.centerx, pf.bottom - 64), GRAY, align="center",
    )


def draw_countdown(surface: pygame.Surface, number: int, layout: Layout) -> None:
    pf = layout.pf_rect
    draw_text(
        surface, str(number), 120, (pf.centerx, pf.centery), WHITE,
        align="center", shadow=True,
    )


def draw_game_over(
    surface: pygame.Surface,
    game,
    phase: str,
    name_buffer: str,
    cursor_timer: float,
    saved: bool,
    layout: Layout,
) -> None:
    pf = layout.pf_rect
    overlay = pygame.Surface(pf.size, pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 170))
    surface.blit(overlay, pf)

    box = pygame.Rect(0, 0, 480, 380)
    box.w = min(box.w, pf.width - 32)
    box.h = min(box.h, pf.height - 32)
    box.center = pf.center
    pygame.draw.rect(surface, BOX_BG, box, border_radius=12)
    pygame.draw.rect(surface, WHITE, box, 2, border_radius=12)

    draw_text(surface, "GAME OVER", 52, (box.centerx, box.top + 54), RED,
              align="center", shadow=True)
    mode_color = GOLD if game.difficulty == "hard" else WHITE
    draw_text(
        surface,
        f"Score: {game.score}  ({game.difficulty.upper()})",
        34,
        (box.centerx, box.top + 118),
        mode_color,
        align="center",
    )

    if phase == PHASE_ENTRY:
        draw_text(surface, "Enter your name (max 12):", 24,
                  (box.centerx, box.top + 180), WHITE, align="center")
        input_rect = pygame.Rect(0, 0, 320, 48)
        input_rect.center = (box.centerx, box.top + 240)
        pygame.draw.rect(surface, INPUT_BOX, input_rect, border_radius=6)
        pygame.draw.rect(surface, WHITE, input_rect, 2, border_radius=6)
        cursor = "_" if int(cursor_timer * 2) % 2 == 0 else " "
        draw_text(surface, name_buffer + cursor, 30,
                  (input_rect.left + 14, input_rect.centery), WHITE,
                  align="midleft")
        draw_text(surface, "ENTER = save    ESC = skip", 22,
                  (box.centerx, box.top + 320), GRAY, align="center")
    else:
        message = "Score saved!" if saved else "Skipped"
        color = GOLD if saved else GRAY
        draw_text(surface, message, 30, (box.centerx, box.top + 200), color,
                  align="center")
        draw_text(surface, "ENTER = back to menu", 22,
                  (box.centerx, box.top + 320), GRAY, align="center")
