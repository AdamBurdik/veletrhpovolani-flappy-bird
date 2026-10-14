import random
from dataclasses import dataclass

from .config import (
    BIRD_RADIUS,
    BIRD_X,
    FLAP_STRENGTH,
    GRAVITY,
    GROUND_Y,
    HAND_SMOOTHING,
    MAX_FALL_SPEED,
    PIPE_FOLLOW_SMOOTHING,
    PIPE_GAP,
    PIPE_GAP_MARGIN,
    PIPE_SPEED,
    PIPE_SPEEDUP_PER_POINT,
    PIPE_SPEED_MAX,
    PIPE_SPACING,
    PIPE_WIDTH,
    PIPE_HARD_Y_RANDOM,
    PLAYFIELD_MAP_MARGIN,
    VIRTUAL_PLAYFIELD_H,
    VIRTUAL_PLAYFIELD_W,
)
from .hand_tracker import map_hand_to_playfield

GAP_MIN = PIPE_GAP / 2 + PIPE_GAP_MARGIN
GAP_MAX = GROUND_Y - PIPE_GAP / 2 - PIPE_GAP_MARGIN


@dataclass
class Bird:
    x: float
    y: float
    vy: float = 0.0
    radius: int = BIRD_RADIUS


@dataclass
class Pipe:
    x: float
    gap_y: float
    scored: bool = False
    follow_offset: float = 0.0

    @property
    def gap_top(self) -> float:
        return self.gap_y - PIPE_GAP / 2

    @property
    def gap_bottom(self) -> float:
        return self.gap_y + PIPE_GAP / 2


class FlappyGame:
    def __init__(self, difficulty: str = "easy"):
        self.difficulty = difficulty
        self.reset()

    def reset(self) -> None:
        self.bird = Bird(BIRD_X, VIRTUAL_PLAYFIELD_H / 2)
        self.pipes: list[Pipe] = []
        self.score = 0
        self.alive = True
        self.pipe_speed = PIPE_SPEED
        self._spawn_pipe(VIRTUAL_PLAYFIELD_W + 200)

    def update(self, dt: float, hand_y: float | None, flap: bool = False) -> None:
        if not self.alive:
            return
        self._update_bird(dt, hand_y, flap)
        self._update_pipes(dt, hand_y)
        if self._collides():
            self.alive = False

    def _update_bird(self, dt: float, hand_y: float | None, flap: bool) -> None:
        bird = self.bird
        if self.difficulty == "hard":
            bird.vy = min(bird.vy + GRAVITY * dt, MAX_FALL_SPEED)
            if flap:
                bird.vy = FLAP_STRENGTH
            bird.y += bird.vy * dt
        elif hand_y is not None:
            target_y = map_hand_to_playfield(
                hand_y,
                float(PLAYFIELD_MAP_MARGIN),
                float(GROUND_Y - PLAYFIELD_MAP_MARGIN),
            )
            previous_y = bird.y
            bird.y += (target_y - bird.y) * HAND_SMOOTHING
            bird.vy = (bird.y - previous_y) / dt if dt > 0 else 0.0
        else:
            bird.vy = 0.0
        bird.y = max(bird.radius, min(GROUND_Y - bird.radius, bird.y))

    def _update_pipes(self, dt: float, hand_y: float | None) -> None:
        bird = self.bird
        self.pipe_speed = min(
            PIPE_SPEED + self.score * PIPE_SPEEDUP_PER_POINT, PIPE_SPEED_MAX
        )
        target_gap = None
        if self.difficulty == "hard" and hand_y is not None:
            target_gap = map_hand_to_playfield(hand_y, GAP_MIN, GAP_MAX)
        for pipe in self.pipes:
            pipe.x -= self.pipe_speed * dt
            if target_gap is not None:
                desired = target_gap + pipe.follow_offset
                desired = max(GAP_MIN, min(GAP_MAX, desired))
                pipe.gap_y += (desired - pipe.gap_y) * PIPE_FOLLOW_SMOOTHING
                pipe.gap_y = max(GAP_MIN, min(GAP_MAX, pipe.gap_y))
            if not pipe.scored and pipe.x + PIPE_WIDTH < bird.x - bird.radius:
                pipe.scored = True
                self.score += 1
        self.pipes = [p for p in self.pipes if p.x + PIPE_WIDTH > 0]
        if not self.pipes or self.pipes[-1].x < VIRTUAL_PLAYFIELD_W - PIPE_SPACING:
            self._spawn_pipe()

    def _spawn_pipe(self, x: float | None = None) -> None:
        gap_y = random.uniform(GAP_MIN, GAP_MAX)
        follow_offset = (
            random.uniform(-PIPE_HARD_Y_RANDOM, PIPE_HARD_Y_RANDOM)
            if self.difficulty == "hard"
            else 0.0
        )
        self.pipes.append(
            Pipe(x if x is not None else float(VIRTUAL_PLAYFIELD_W), gap_y, follow_offset=follow_offset)
        )

    def _collides(self) -> bool:
        bird = self.bird
        if bird.y + bird.radius >= GROUND_Y:
            return True
        if bird.y - bird.radius <= 0:
            return True
        for pipe in self.pipes:
            if pipe.x > bird.x + bird.radius or pipe.x + PIPE_WIDTH < bird.x - bird.radius:
                continue
            if self._circle_hits_rect(
                bird.x, bird.y, bird.radius, pipe.x, 0, PIPE_WIDTH, pipe.gap_top
            ):
                return True
            if self._circle_hits_rect(
                bird.x,
                bird.y,
                bird.radius,
                pipe.x,
                pipe.gap_bottom,
                PIPE_WIDTH,
                GROUND_Y - pipe.gap_bottom,
            ):
                return True
        return False

    @staticmethod
    def _circle_hits_rect(
        cx: float, cy: float, r: float, rx: float, ry: float, rw: float, rh: float
    ) -> bool:
        nearest_x = max(rx, min(cx, rx + rw))
        nearest_y = max(ry, min(cy, ry + rh))
        dx = cx - nearest_x
        dy = cy - nearest_y
        return dx * dx + dy * dy <= r * r
