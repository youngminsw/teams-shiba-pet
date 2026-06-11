# -*- coding: utf-8 -*-
"""shiba_raw.png(흰 배경)을 투명 배경 스프라이트 shiba.png로 가공.

바깥쪽 흰 배경만 제거하고 (가장자리에 닿은 흰색 덩어리),
캐릭터 내부의 흰색/크림색은 그대로 둔다.
"""
import numpy as np
from PIL import Image
from scipy import ndimage

from pathlib import Path

_BASE = Path(__file__).resolve().parent
SRC = str(_BASE / "shiba_raw.png")
DST = str(_BASE / "shiba.png")

im = Image.open(SRC).convert("RGB")
a = np.array(im)

white = (a > 235).all(axis=2)
lbl, n = ndimage.label(white)
border = set(lbl[0, :]) | set(lbl[-1, :]) | set(lbl[:, 0]) | set(lbl[:, -1])
border.discard(0)
bg = np.isin(lbl, list(border))

# 외곽선 주변의 밝은 안티앨리어싱 테두리를 살짝 깎아낸다
bg = ndimage.binary_dilation(bg, iterations=2)

alpha = np.where(bg, 0, 255).astype(np.uint8)
rgba = np.dstack([a, alpha])

# 캐릭터 영역만 크롭
ys, xs = np.where(alpha > 0)
pad = 8
y0, y1 = max(ys.min() - pad, 0), min(ys.max() + pad, a.shape[0])
x0, x1 = max(xs.min() - pad, 0), min(xs.max() + pad, a.shape[1])
out = Image.fromarray(rgba[y0:y1, x0:x1])

# 회전/축소 여유를 위해 450px 높이로 저장 (런타임에 최종 축소)
w, h = out.size
out = out.resize((int(w * 450 / h), 450), Image.LANCZOS)
out.save(DST)
print("saved", out.size)

# 어두운 배경 위 렌더 테스트 (프린지 확인용)
test = Image.new("RGB", (out.size[0] + 40, 490), "#222233")
test.paste(out, (20, 20), out)
test.save(DST.replace("shiba.png", "sprite_test.png"))
