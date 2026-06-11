# -*- coding: utf-8 -*-
"""shiba.png에서 표정 변형 스프라이트들을 생성.

원본의 눈/입 부위를 주변 털 색으로 메우고 새 표정을 그려넣는다.
결과: shiba_pose_blink/sleep/happy/shock/worried.png + 미리보기 poses_preview.png
"""
import numpy as np
from PIL import Image, ImageDraw
from pathlib import Path

BASE = Path(__file__).resolve().parent
SRC = BASE / "shiba.png"

L_EYE = (66, 127, 111, 179)
R_EYE = (161, 145, 211, 200)
MOUTH = (99, 196, 159, 239)
DARK = (62, 42, 26, 255)

im0 = Image.open(SRC).convert("RGBA")
arr = np.array(im0)


def sample_ring(box, pad=12):
    """box 둘레의 털 색(중간값)을 샘플링 — 어두운 외곽선/흰 하이라이트 제외."""
    x0, y0, x1, y1 = box
    X0, Y0 = max(x0 - pad, 0), max(y0 - pad, 0)
    X1, Y1 = min(x1 + pad, arr.shape[1]), min(y1 + pad, arr.shape[0])
    reg = arr[Y0:Y1, X0:X1].reshape(-1, 4).astype(int)
    inner = arr[y0:y1, x0:x1].reshape(-1, 4).astype(int)
    # 링 = 바깥 박스 - 안쪽 박스 픽셀 (대충: 안쪽 픽셀 수만큼 제외하지 않고 조건으로 거름)
    ok = (reg[:, 3] > 200) & (reg[:, :3].max(axis=1) > 120) & (reg[:, :3].min(axis=1) < 245)
    px = reg[ok][:, :3]
    return tuple(int(v) for v in np.median(px, axis=0)) + (255,)


FUR_L = sample_ring(L_EYE)
FUR_R = sample_ring(R_EYE)
MUZ = sample_ring(MOUTH, pad=10)
print("sampled colors:", FUR_L, FUR_R, MUZ)


def close_eyes(img, style):
    d = ImageDraw.Draw(img)
    for box, fur in ((L_EYE, FUR_L), (R_EYE, FUR_R)):
        x0, y0, x1, y1 = box
        d.ellipse((x0 - 5, y0 - 5, x1 + 5, y1 + 5), fill=fur)
        cy = (y0 + y1) // 2
        if style == "sleep":   # ︶ 평온하게 감은 눈
            d.arc((x0, cy - 16, x1, cy + 12), 15, 165, fill=DARK, width=7)
        else:                  # ∩ 신나서 휘어진 눈
            d.arc((x0, cy - 12, x1, cy + 18), 195, 345, fill=DARK, width=8)


def shock_eyes(img):
    d = ImageDraw.Draw(img)
    for box in (L_EYE, R_EYE):
        x0, y0, x1, y1 = box
        d.ellipse((x0 - 2, y0 - 2, x1 + 2, y1 + 2), fill=(253, 252, 248, 255),
                  outline=DARK, width=5)
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        d.ellipse((cx - 6, cy - 6, cx + 6, cy + 6), fill=(25, 18, 12, 255))


def replace_mouth(img, kind):
    d = ImageDraw.Draw(img)
    d.ellipse(MOUTH, fill=MUZ)
    cx = (MOUTH[0] + MOUTH[2]) // 2
    if kind == "smile":        # 다문 채 살짝 미소
        d.arc((cx - 15, 203, cx + 15, 227), 15, 165, fill=DARK, width=6)
    else:                      # 걱정스러운 물결 입
        pts = [(cx - 22, 221), (cx - 12, 214), (cx - 2, 222),
               (cx + 8, 214), (cx + 18, 221)]
        d.line(pts, fill=DARK, width=6, joint="curve")


def worried_brows(img):
    d = ImageDraw.Draw(img)
    d.line((68, 118, 104, 107), fill=DARK, width=6)    # 왼눈썹: 안쪽이 올라감
    d.line((162, 125, 206, 137), fill=DARK, width=6)   # 오른눈썹
    for x0, y0, x1, y1 in (
        (66, 116, 72, 122), (100, 105, 106, 111),
        (160, 123, 166, 129), (202, 135, 208, 141),
    ):
        d.ellipse((x0, y0, x1, y1), fill=DARK)         # 선 끝 둥글게


poses = {}
p = im0.copy(); close_eyes(p, "sleep"); poses["blink"] = p
p = im0.copy(); close_eyes(p, "sleep"); replace_mouth(p, "smile"); poses["sleep"] = p
p = im0.copy(); close_eyes(p, "happy"); poses["happy"] = p
p = im0.copy(); shock_eyes(p); poses["shock"] = p
p = im0.copy(); worried_brows(p); replace_mouth(p, "wavy"); poses["worried"] = p

for name, img in poses.items():
    img.save(BASE / f"shiba_pose_{name}.png")

# 미리보기 그리드
all_ = [("normal", im0)] + list(poses.items())
ph = 240
pw = int(im0.width * ph / im0.height)
grid = Image.new("RGB", (pw * 3 + 40, ph * 2 + 60), (235, 235, 240))
d = ImageDraw.Draw(grid)
for i, (name, img) in enumerate(all_):
    x, y = (i % 3) * pw + 20, (i // 3) * (ph + 24) + 6
    small = img.resize((pw, ph), Image.LANCZOS)
    grid.paste(small, (x, y), small)
    d.text((x + pw // 2 - 18, y + ph + 4), name, fill=(40, 40, 40))
grid.save(BASE / "poses_preview.png")
print("saved", list(poses))
