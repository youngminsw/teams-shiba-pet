# -*- coding: utf-8 -*-
"""시바견 캐릭터를 코드로 그리는 모듈 — 포즈/표정 자유 조합.

원본 AI 그림(shiba_raw.png)의 팔레트와 비율을 따라 그린다.
포즈: stand(wave), walk(4프레임 네발 걷기), sit, lie, jump, panic
표정: normal, blink, sleep, happy, shock, worried

python draw_shiba.py 로 실행하면 전체 미리보기 시트를 만든다.
"""
from PIL import Image, ImageDraw

SS = 3            # 슈퍼샘플링 배율 (계단 현상 방지)
CW, CH = 460, 470  # 논리 캔버스 크기

BODY = (244, 164, 84, 255)
CREAM = (253, 241, 216, 255)
OUT = (74, 49, 34, 255)
BLUSH = (246, 160, 150, 255)
RED = (214, 66, 44, 255)
GOLD = (245, 184, 70, 255)
EAR_IN = (248, 230, 220, 255)
TONGUE = (233, 105, 92, 255)
EYE = (46, 31, 21, 255)
WHITE = (255, 255, 255, 255)
OW = 3.4          # 외곽선 두께 (논리 단위)


class P:
    """좌표를 논리 단위로 받아 SS배로 그려주는 페인터."""

    def __init__(self, w=CW, h=CH):
        self.w, self.h = w, h
        self.img = Image.new("RGBA", (round(w * SS), round(h * SS)), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)

    def E(self, x0, y0, x1, y1, fill=None, outline=None, width=OW):
        self.d.ellipse([x0 * SS, y0 * SS, x1 * SS, y1 * SS],
                       fill=fill, outline=outline, width=round(width * SS))

    def RR(self, x0, y0, x1, y1, r, fill=None, outline=None, width=OW):
        self.d.rounded_rectangle([x0 * SS, y0 * SS, x1 * SS, y1 * SS], r * SS,
                                 fill=fill, outline=outline, width=round(width * SS))

    def PG(self, pts, fill=None, outline=None, width=OW):
        self.d.polygon([(x * SS, y * SS) for x, y in pts],
                       fill=fill, outline=outline, width=round(width * SS))

    def ARC(self, x0, y0, x1, y1, a0, a1, fill=OUT, width=OW):
        self.d.arc([x0 * SS, y0 * SS, x1 * SS, y1 * SS], a0, a1,
                   fill=fill, width=round(width * SS))

    def PIE(self, x0, y0, x1, y1, a0, a1, fill=None, outline=None, width=OW):
        self.d.pieslice([x0 * SS, y0 * SS, x1 * SS, y1 * SS], a0, a1,
                        fill=fill, outline=outline, width=round(width * SS))

    def L(self, pts, fill=OUT, width=OW):
        sp = [(x * SS, y * SS) for x, y in pts]
        self.d.line(sp, fill=fill, width=round(width * SS), joint="curve")

    def stroke_limb(self, x0, y0, x1, y1, w, fill=BODY):
        """둥근 끝 굵은 선 = 팔다리. 외곽선 포함."""
        for color, ww in ((OUT, w + OW * 2), (fill, w)):
            self.d.line([(x0 * SS, y0 * SS), (x1 * SS, y1 * SS)],
                        fill=color, width=round(ww * SS))
            for x, y in ((x0, y0), (x1, y1)):
                r = ww / 2
                self.d.ellipse([(x - r) * SS, (y - r) * SS,
                                (x + r) * SS, (y + r) * SS], fill=color)

    def out(self):
        img = self.img.resize((round(self.w), round(self.h)), Image.LANCZOS)
        bbox = img.getbbox()
        if bbox:
            x0, y0, x1, y1 = bbox
            img = img.crop((max(0, x0 - 4), max(0, y0 - 4),
                            min(round(self.w), x1 + 4), min(round(self.h), y1 + 4)))
        return img


# ------------------------------------------------------------------ 부위
def ears(p, hx, hy, k):
    for s in (-1, 1):  # s=-1 왼쪽
        b_in = (hx + s * 24 * k, hy - 88 * k)
        b_out = (hx + s * 92 * k, hy - 46 * k)
        tip = (hx + s * 76 * k, hy - 132 * k)
        p.PG([b_in, tip, b_out], fill=BODY, outline=OUT)
        m = 0.42
        c = ((b_in[0] + b_out[0] + tip[0]) / 3, (b_in[1] + b_out[1] + tip[1]) / 3)
        small = [(c[0] + (q[0] - c[0]) * (1 - m), c[1] + (q[1] - c[1]) * (1 - m))
                 for q in (b_in, tip, b_out)]
        p.PG(small, fill=EAR_IN)


def face(p, hx, hy, k, kind):
    # 크림색 주둥이
    p.E(hx - 64 * k, hy + 2 * k, hx + 64 * k, hy + 82 * k, fill=CREAM)
    # 눈썹 점
    p.E(hx - 62 * k, hy - 58 * k, hx - 36 * k, hy - 42 * k, fill=CREAM)
    p.E(hx + 36 * k, hy - 58 * k, hx + 62 * k, hy - 42 * k, fill=CREAM)
    # 볼터치
    p.E(hx - 102 * k, hy + 16 * k, hx - 64 * k, hy + 42 * k, fill=BLUSH)
    p.E(hx + 64 * k, hy + 16 * k, hx + 102 * k, hy + 42 * k, fill=BLUSH)

    exl, exr, ey = hx - 52 * k, hx + 52 * k, hy - 10 * k
    if kind in ("normal", "worried"):
        for ex in (exl, exr):
            # 글로시 눈: 진갈색 바탕 + 아래 가장자리 초승달 빛 + 하이라이트 2개
            p.E(ex - 24 * k, ey - 26 * k, ex + 24 * k, ey + 26 * k, fill=EYE)
            p.E(ex - 15 * k, ey + 2 * k, ex + 15 * k, ey + 23 * k,
                fill=(152, 100, 58, 255))
            p.E(ex - 17 * k, ey - 18 * k, ex + 17 * k, ey + 13 * k, fill=EYE)
            p.E(ex - 17 * k, ey - 20 * k, ex + 1 * k, ey - 2 * k, fill=WHITE)
            p.E(ex + 6 * k, ey + 4 * k, ex + 14 * k, ey + 12 * k, fill=WHITE)
    elif kind in ("blink", "sleep"):
        for ex in (exl, exr):
            p.ARC(ex - 22 * k, ey - 18 * k, ex + 22 * k, ey + 12 * k,
                  20, 160, width=5.5 * k)
    elif kind == "happy":
        for ex in (exl, exr):
            p.ARC(ex - 22 * k, ey - 14 * k, ex + 22 * k, ey + 20 * k,
                  200, 340, width=6 * k)
    elif kind == "shock":
        for ex in (exl, exr):
            p.E(ex - 24 * k, ey - 26 * k, ex + 24 * k, ey + 26 * k,
                fill=WHITE, outline=OUT, width=4 * k)
            p.E(ex - 7 * k, ey - 7 * k, ex + 7 * k, ey + 7 * k, fill=EYE)

    if kind == "worried":
        p.L([(hx - 70 * k, hy - 52 * k), (hx - 34 * k, hy - 62 * k)], width=5 * k)
        p.L([(hx + 34 * k, hy - 62 * k), (hx + 70 * k, hy - 52 * k)], width=5 * k)

    # 코
    p.E(hx - 11 * k, hy + 12 * k, hx + 11 * k, hy + 28 * k, fill=OUT)
    # 입
    if kind == "shock":
        p.E(hx - 19 * k, hy + 32 * k, hx + 19 * k, hy + 68 * k, fill=OUT)
        p.E(hx - 11 * k, hy + 50 * k, hx + 11 * k, hy + 66 * k, fill=TONGUE)
    elif kind == "sleep":
        p.ARC(hx - 14 * k, hy + 34 * k, hx + 14 * k, hy + 54 * k, 20, 160,
              width=4.5 * k)
    elif kind == "worried":
        p.L([(hx - 20 * k, hy + 46 * k), (hx - 10 * k, hy + 40 * k),
             (hx, hy + 47 * k), (hx + 10 * k, hy + 40 * k),
             (hx + 20 * k, hy + 46 * k)], width=4.5 * k)
    else:  # normal / blink / happy: 벌린 미소
        p.PIE(hx - 26 * k, hy + 18 * k, hx + 26 * k, hy + 62 * k, 15, 165,
              fill=OUT)
        p.E(hx - 13 * k, hy + 40 * k, hx + 13 * k, hy + 62 * k, fill=TONGUE)


def head_img(kind, r=105, tilt=0.0):
    """머리를 별도 캔버스에 그려서 기울일 수 있게 한다 (SS 해상도 RGBA 반환)."""
    k = r / 105
    size = 2 * r + 150 * k       # 귀/회전 여유
    hp = P(size, size)
    c = size / 2
    ears(hp, c, c, k)
    hp.E(c - r, c - r, c + r, c + r, fill=BODY, outline=OUT)
    face(hp, c, c, k, kind)
    img = hp.img
    if tilt:
        img = img.rotate(tilt, resample=Image.BICUBIC, expand=True)
    return img


def head(p, hx, hy, r, kind, tilt=0.0):
    img = head_img(kind, r, tilt)
    p.img.paste(img, (round(hx * SS - img.width / 2),
                      round(hy * SS - img.height / 2)), img)


def tail(p, cx, cy, r=40):
    p.E(cx - r, cy - r, cx + r, cy + r, fill=BODY, outline=OUT)
    p.E(cx - r * 0.15, cy - r * 0.65, cx + r * 0.7, cy + r * 0.2, fill=CREAM)


def collar(p, cx, cy, w=70):
    p.RR(cx - w, cy - 12, cx + w, cy + 12, 12, fill=RED, outline=OUT, width=2.6)
    p.E(cx - 15, cy + 6, cx + 15, cy + 36, fill=GOLD, outline=OUT, width=2.6)
    p.L([(cx - 8, cy + 26), (cx + 8, cy + 26)], width=2.4)
    p.E(cx - 3, cy + 27, cx + 3, cy + 33, fill=OUT)


def foot(p, x, y, w=24):
    p.E(x - w, y - 14, x + w, y + 14, fill=CREAM, outline=OUT, width=2.8)


def paw_up(p, x, y, r=26):
    """들어올린 발바닥 (분홍 패드)."""
    p.E(x - r, y - r, x + r, y + r, fill=CREAM, outline=OUT, width=2.8)
    pr = r * 0.30
    p.E(x - pr * 1.1, y - pr * 0.2, x + pr * 1.1, y + pr * 1.8, fill=BLUSH)
    for i, (dx, dy) in enumerate(((-1.9, -1.0), (0, -1.7), (1.9, -1.0))):
        p.E(x + dx * pr - pr * 0.55, y + dy * pr - pr * 0.55,
            x + dx * pr + pr * 0.55, y + dy * pr + pr * 0.55, fill=BLUSH)


# ------------------------------------------------------------------ 포즈
def pose_stand(face_kind="normal", wave=False):
    p = P()
    cx = 230
    tail(p, cx + 100, 334)
    # 몸통
    p.E(cx - 82, 240, cx + 82, 408, fill=BODY, outline=OUT)
    p.E(cx - 50, 290, cx + 50, 400, fill=CREAM)
    # 다리
    foot(p, cx - 38, 396)
    foot(p, cx + 38, 396)
    # 팔
    if wave:
        p.stroke_limb(cx + 62, 290, cx + 116, 222, 26)
        paw_up(p, cx + 120, 212)
        p.stroke_limb(cx - 66, 286, cx - 78, 330, 26)
        p.E(cx - 95, 318, cx - 61, 350, fill=CREAM, outline=OUT, width=2.8)
    else:
        for s in (-1, 1):
            p.stroke_limb(cx + s * 64, 286, cx + s * 78, 332, 26)
            p.E(cx + s * 78 - 17, 320, cx + s * 78 + 17, 352,
                fill=CREAM, outline=OUT, width=2.8)
    head(p, cx, 150, 105, face_kind)
    collar(p, cx, 252, 66)
    return p.out()


def pose_arms_up(face_kind="shock", spread=False):
    """만세 — jump(신남)와 panic(놀람) 겸용."""
    p = P()
    cx = 230
    tail(p, cx + 100, 332)
    p.E(cx - 82, 238, cx + 82, 406, fill=BODY, outline=OUT)
    p.E(cx - 50, 288, cx + 50, 398, fill=CREAM)
    dx = 22 if spread else 0
    foot(p, cx - 40 - dx, 394)
    foot(p, cx + 40 + dx, 394)
    for s in (-1, 1):
        p.stroke_limb(cx + s * 60, 285, cx + s * 122, 212, 26)
        paw_up(p, cx + s * 128, 202, 24)
    head(p, cx, 148, 105, face_kind)
    collar(p, cx, 250, 66)
    return p.out()


def pose_walk(face_kind="normal", phase=0):
    """네발 걷기 (왼쪽을 보고 걸음). phase 0~3."""
    p = P()
    bx, by = 258, 322  # 몸통 중심
    tail(p, bx + 108, by - 58, 38)
    # 다리 4개 (대각선 보행: 0&2 전진, 1&3 후진)
    sw = [14, 0, -14, 0][phase]
    lift = [6, 0, 6, 0][phase]
    legs = [(bx - 78, sw, lift), (bx - 34, -sw, 0),
            (bx + 44, -sw, 0), (bx + 88, sw, lift)]
    for i, (lx, dx, dy) in enumerate(legs):
        p.stroke_limb(lx, by + 30, lx + dx, by + 86 - dy, 24)
        foot(p, lx + dx, by + 88 - dy, 19)
    # 몸통
    p.E(bx - 112, by - 62, bx + 112, by + 62, fill=BODY, outline=OUT)
    p.E(bx - 70, by - 6, bx + 70, by + 56, fill=CREAM)
    # 머리 (몸 앞쪽, 정면 얼굴)
    bob = 3 if phase % 2 == 0 else 0
    head(p, bx - 124, by - 78 + bob, 88, face_kind)
    collar(p, bx - 124, by + 8 + bob, 56)
    return p.out()


def pose_sit(face_kind="normal", tilt=0.0):
    p = P()
    cx = 230
    tail(p, cx + 102, 362)
    # 엉덩이/몸
    p.E(cx - 90, 250, cx + 90, 420, fill=BODY, outline=OUT)
    p.E(cx - 52, 300, cx + 52, 412, fill=CREAM)
    # 뒷다리 허벅지
    for s in (-1, 1):
        p.E(cx + s * 96 - 34, 330, cx + s * 96 + 34, 408,
            fill=BODY, outline=OUT)
    # 앞다리 (곧게)
    for s in (-1, 1):
        p.stroke_limb(cx + s * 30, 320, cx + s * 34, 396, 22)
        foot(p, cx + s * 34, 400, 20)
    head(p, cx, 152, 102, face_kind, tilt=tilt)
    collar(p, cx, 250, 64)
    return p.out()


def pose_lie(face_kind="sleep"):
    """엎드려 잠 (머리를 앞발에 얹음)."""
    p = P()
    bx, by = 250, 380
    tail(p, bx + 118, by - 38, 36)
    p.E(bx - 120, by - 52, bx + 120, by + 52, fill=BODY, outline=OUT)
    p.E(bx - 70, by - 6, bx + 80, by + 46, fill=CREAM)
    # 앞발 두 개
    foot(p, bx - 118, by + 34, 26)
    foot(p, bx - 66, by + 40, 26)
    head(p, bx - 96, by - 50, 86, face_kind)
    return p.out()


def pose_run(face_kind="happy", phase=0):
    """전력질주 (왼쪽으로). phase 0=다리 쭉 뻗기, 1=다리 모으기."""
    p = P()
    bx, by = 268, 300
    tail(p, bx + 116, by - 50, 36)
    if phase == 0:
        p.stroke_limb(bx - 70, by + 24, bx - 148, by + 56, 23)
        p.stroke_limb(bx - 36, by + 28, bx - 98, by + 72, 23)
        p.stroke_limb(bx + 58, by + 22, bx + 130, by + 44, 23)
        p.stroke_limb(bx + 88, by + 14, bx + 154, by + 16, 23)
        for fx_, fy_ in ((-152, 58), (-102, 76), (132, 46), (158, 16)):
            foot(p, bx + fx_, by + fy_, 17)
    else:
        p.stroke_limb(bx - 64, by + 26, bx - 84, by + 64, 23)
        p.stroke_limb(bx - 30, by + 30, bx - 22, by + 68, 23)
        p.stroke_limb(bx + 52, by + 26, bx + 32, by + 64, 23)
        p.stroke_limb(bx + 86, by + 22, bx + 72, by + 62, 23)
        for fx_, fy_ in ((-86, 66), (-22, 70), (30, 66), (70, 64)):
            foot(p, bx + fx_, by + fy_, 17)
    p.E(bx - 118, by - 54, bx + 118, by + 50, fill=BODY, outline=OUT)
    p.E(bx - 72, by - 4, bx + 76, by + 44, fill=CREAM)
    head(p, bx - 132, by - 66, 86, face_kind, tilt=-7)
    collar(p, bx - 130, by + 16, 52)
    return p.out()


def pose_bow(face_kind="happy", wag=0):
    """플레이 바우 — 앞다리 쭉 뻗고 엉덩이 들기 (놀자!). wag로 꼬리 흔들."""
    p = P()
    bx, by = 240, 330
    tail(p, bx + 100 + (10 if wag else -6), by - 124 + (8 if wag else 0), 34)
    # 엉덩이 (높이 들림)
    p.E(bx - 6, by - 96, bx + 138, by + 18, fill=BODY, outline=OUT)
    # 뒷다리
    p.stroke_limb(bx + 98, by - 8, bx + 102, by + 54, 26)
    foot(p, bx + 102, by + 60, 19)
    p.stroke_limb(bx + 50, by - 4, bx + 52, by + 54, 26)
    foot(p, bx + 52, by + 60, 19)
    # 가슴 (낮춤)
    p.E(bx - 96, by - 42, bx + 56, by + 64, fill=BODY, outline=OUT)
    p.E(bx - 60, by - 4, bx + 36, by + 56, fill=CREAM)
    # 앞다리 앞으로 쭉
    p.stroke_limb(bx - 48, by + 26, bx - 132, by + 56, 22)
    foot(p, bx - 136, by + 58, 18)
    p.stroke_limb(bx - 18, by + 36, bx - 102, by + 66, 22)
    foot(p, bx - 106, by + 68, 18)
    head(p, bx - 92, by - 58, 84, face_kind, tilt=8)
    return p.out()


def pose_roll(face_kind="happy", phase=0):
    """벌러덩 — 배 보이고 누워서 다리 버둥버둥."""
    p = P()
    bx, by = 250, 360
    tail(p, bx + 124, by + 14, 32)
    p.E(bx - 108, by - 52, bx + 108, by + 52, fill=BODY, outline=OUT)
    p.E(bx - 76, by - 36, bx + 84, by + 32, fill=CREAM)   # 큰 배
    w = 10 if phase else -10
    p.stroke_limb(bx - 62, by - 40, bx - 84, by - 94 + w, 22)
    paw_up(p, bx - 88, by - 102 + w, 19)
    p.stroke_limb(bx - 20, by - 44, bx - 24, by - 104 - w, 22)
    paw_up(p, bx - 24, by - 112 - w, 19)
    p.stroke_limb(bx + 42, by - 42, bx + 52, by - 98 + w, 22)
    paw_up(p, bx + 54, by - 106 + w, 19)
    p.stroke_limb(bx + 80, by - 36, bx + 98, by - 86 - w, 22)
    paw_up(p, bx + 100, by - 94 - w, 19)
    head(p, bx - 132, by - 4, 84, face_kind, tilt=-72)
    return p.out()


def pose_dig(face_kind="normal", phase=0):
    """땅파기 — 앞다리를 번갈아 휘적휘적."""
    p = P()
    bx, by = 256, 320
    tail(p, bx + 108, by - 62, 36)
    p.stroke_limb(bx + 50, by + 28, bx + 56, by + 82, 24)
    foot(p, bx + 56, by + 84, 19)
    p.stroke_limb(bx + 92, by + 24, bx + 100, by + 78, 24)
    foot(p, bx + 100, by + 80, 19)
    p.E(bx - 112, by - 50, bx + 112, by + 58, fill=BODY, outline=OUT)
    p.E(bx - 66, by, bx + 70, by + 50, fill=CREAM)
    if phase == 0:
        p.stroke_limb(bx - 74, by + 20, bx - 122, by, 23)
        paw_up(p, bx - 126, by - 6, 18)
        p.stroke_limb(bx - 40, by + 30, bx - 62, by + 82, 23)
        foot(p, bx - 62, by + 84, 18)
    else:
        p.stroke_limb(bx - 74, by + 20, bx - 118, by + 68, 23)
        foot(p, bx - 120, by + 74, 18)
        p.stroke_limb(bx - 40, by + 30, bx - 82, by + 12, 23)
        paw_up(p, bx - 86, by + 6, 18)
    head(p, bx - 124, by - 58, 84, face_kind, tilt=-10)
    collar(p, bx - 122, by + 24, 52)
    return p.out()


_CACHE = {}


def render(pose, face_kind="normal", **kw):
    key = (pose, face_kind, tuple(sorted(kw.items())))
    if key not in _CACHE:
        fn = {"stand": pose_stand, "arms_up": pose_arms_up,
              "walk": pose_walk, "sit": pose_sit, "lie": pose_lie,
              "run": pose_run, "bow": pose_bow, "roll": pose_roll,
              "dig": pose_dig}[pose]
        _CACHE[key] = fn(face_kind, **kw)
    return _CACHE[key]


if __name__ == "__main__":
    from pathlib import Path
    cells = [
        ("stand", "normal", {}), ("stand", "normal", {"wave": True}),
        ("sit", "normal", {}), ("sit", "normal", {"tilt": 14}),
        ("walk", "normal", {"phase": 0}), ("walk", "normal", {"phase": 2}),
        ("run", "happy", {"phase": 0}), ("run", "happy", {"phase": 1}),
        ("bow", "happy", {"wag": 1}), ("roll", "happy", {"phase": 0}),
        ("dig", "normal", {"phase": 0}), ("lie", "sleep", {}),
        ("arms_up", "happy", {}), ("arms_up", "shock", {"spread": True}),
        ("stand", "worried", {}), ("stand", "blink", {}),
    ]
    ch = 230
    grid = Image.new("RGB", (4 * 240 + 20, 4 * (ch + 26) + 20), (236, 236, 242))
    from PIL import ImageDraw as _ID
    d = _ID.Draw(grid)
    for i, (pose, fk, kw) in enumerate(cells):
        img = render(pose, fk, **kw)
        w = int(img.width * ch / img.height)
        img = img.resize((w, ch), Image.LANCZOS)
        x = (i % 4) * 240 + 10 + (240 - w) // 2
        y = (i // 4) * (ch + 26) + 10
        grid.paste(img, (x, y), img)
        d.text(((i % 4) * 240 + 90, y + ch + 4), f"{pose}/{fk}"
               + (f" {kw}" if kw else ""), fill=(40, 40, 40))
    out = Path(__file__).parent / "vector_preview.png"
    grid.save(out)
    print("saved", out)
