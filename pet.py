# -*- coding: utf-8 -*-
"""Teams 교수님 알림 데스크탑 펫 (벡터 시바견).

캐릭터는 draw_shiba.py가 코드로 그린다 — 포즈(두발 서기/네발 걷기/앉기/
엎드려 자기/만세)와 표정(기본/깜빡/잠/신남/패닉/걱정)을 자유 조합.

평소: 산책(네발), 앉아서 쉬기, 낮잠, 손 흔들기, 클릭 반응.
- 1차 감지: Windows 알림 센터 (보낸 사람 확인) → 교수님이면 거대화 + 풀 난동
- 2차 감지: Teams 작업표시줄 배지 → 순한 "확인해줘" 모드
클릭하면 진정한다.

실행:  pythonw pet.py        (백그라운드 상주)
테스트: python pet.py --test  (4초 뒤 가짜 교수님 알림)
"""

import asyncio
import ctypes
import json
import math
import os
import queue
import random
import re
import socket
import sys
import threading
import time
import tkinter as tk
import winsound
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageTk

from draw_shiba import render

if getattr(sys, "frozen", False):      # PyInstaller 실행파일로 배포된 경우
    BASE = Path(sys.executable).resolve().parent
else:
    BASE = Path(__file__).resolve().parent
CONFIG_PATH = BASE / "config.json"
POS_PATH = BASE / "pos.json"
LOG_PATH = BASE / "pet.log"

STARTUP_VBS = (Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows"
               / "Start Menu" / "Programs" / "Startup" / "teams_pet.vbs")


def set_autostart(enable):
    """Windows 시작 시 자동 실행 등록/해제."""
    try:
        if not enable:
            if STARTUP_VBS.exists():
                STARTUP_VBS.unlink()
            return
        if getattr(sys, "frozen", False):
            target = f'"""{sys.executable}"""'
        else:
            pyw = Path(sys.executable).with_name("pythonw.exe")
            target = f'"""{pyw}"" ""{Path(__file__).resolve()}"""'
        STARTUP_VBS.write_text(
            f'CreateObject("WScript.Shell").Run {target}, 0, False\n',
            encoding="utf-16")
    except OSError as e:
        log(f"자동 시작 설정 실패: {e}")

KEY = "#ff00fe"            # 투명 처리되는 색 (클릭도 통과)
ALERT_RED = "#e53935"
SOFT_BLUE = "#1e88e5"

DEFAULTS = {
    "keywords": [],            # 교수님 성함. 비우면 모든 Teams 알림에 반응
    "watch_apps": ["teams"],
    "poll_seconds": 3,         # 알림 센터 확인 주기
    "badge_poll_seconds": 45,  # 작업표시줄 배지 확인 주기
    "sound": True,
    "always_on_top": False,    # False = 평소엔 모든 창 뒤(바탕화면 위)에 있음
}

W, H = 370, 410            # 펫 창 크기 (거대 패닉까지 수용)
FW, FH = 356, 352          # 스프라이트 프레임 크기


def log(msg):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    try:
        print(line, flush=True)
    except Exception:
        pass
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def load_config():
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig")))
    except (OSError, json.JSONDecodeError) as e:
        log(f"config.json 읽기 실패, 기본값 사용: {e}")
    return cfg


def acquire_single_instance_lock():
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", 48613))
        return s
    except OSError:
        return None


# ---------------------------------------------------------------- 감지 채널 1
class NotificationWatcher(threading.Thread):
    """Windows 알림 센터를 폴링해 Teams 알림을 큐로 보낸다 (보낸 사람 포함)."""

    def __init__(self, cfg, out_queue):
        super().__init__(daemon=True)
        self.cfg = cfg
        self.q = out_queue

    def run(self):
        try:
            asyncio.run(self._main())
        except Exception as e:
            log(f"알림 감시 스레드 오류: {e!r}")

    async def _main(self):
        from winsdk.windows.ui.notifications.management import (
            UserNotificationListener,
            UserNotificationListenerAccessStatus,
        )
        from winsdk.windows.ui.notifications import NotificationKinds

        listener = UserNotificationListener.current
        status = await listener.request_access_async()
        if status != UserNotificationListenerAccessStatus.ALLOWED:
            log(f"알림 접근 거부됨 (status={status})")
            self.q.put(("bubble", "알림 접근 차단됨!"))
            return
        log("알림 감시 시작")

        seen = set()
        first_pass = True
        while True:
            try:
                notifs = await listener.get_notifications_async(NotificationKinds.TOAST)
                current_ids = set()
                for n in notifs:
                    current_ids.add(n.id)
                    if n.id in seen:
                        continue
                    seen.add(n.id)
                    if not first_pass:
                        self._check(n)
                if len(seen) > 4000:
                    seen &= current_ids
                first_pass = False
            except Exception as e:
                log(f"알림 조회 실패: {e!r}")
            await asyncio.sleep(self.cfg["poll_seconds"])

    def _check(self, n):
        try:
            app = n.app_info.display_info.display_name or ""
        except Exception:
            app = ""
        texts = []
        try:
            for b in n.notification.visual.bindings:
                texts += [t.text for t in b.get_text_elements()]
        except Exception:
            pass

        if not any(w.lower() in app.lower() for w in self.cfg["watch_apps"]):
            return
        joined = " ".join(texts).lower()
        keywords = self.cfg["keywords"]
        if keywords and not any(k.lower() in joined for k in keywords):
            log(f"Teams 알림이지만 키워드 불일치: {texts[:1]}")
            return

        title = texts[0] if texts else app
        log(f"!! 알림 매칭: {app} / {texts[:2]}")
        self.q.put(("alert", title))


# ---------------------------------------------------------------- 감지 채널 2
class BadgeWatcher(threading.Thread):
    """Teams 배지(안 읽은 알림 수)를 감시한다.

    1순위: Windows 알림 DB(wpndatabase.db)에서 Teams의 badge 레코드 직접 읽기
           — Teams 창이 닫혀 있어도 동작하고 수 ms면 끝난다.
    2순위: 작업표시줄 버튼 이름 (pywinauto UIA, 매번 새로 스캔 — 캐시 금지:
           pywinauto가 element 이름을 캐시해서 변화를 못 보는 버그가 있었음)
    누가 보냈는지는 알 수 없으므로 '순한 알림'만 발생시킨다.
    """

    WPN_DB = (Path.home() / "AppData/Local/Microsoft/Windows/Notifications"
              / "wpndatabase.db")

    def __init__(self, cfg, out_queue):
        super().__init__(daemon=True)
        self.cfg = cfg
        self.q = out_queue
        self._desktop = None
        self._last_logged = None
        self._db_dead = False

    def run(self):
        log("배지 감시 시작 (알림 DB 1순위, 작업표시줄 2순위)")
        while True:
            try:
                count, src = self._read_badge()
                if (count, src) != self._last_logged:
                    log(f"Teams 배지: {count}개 (via {src})")
                    self._last_logged = (count, src)
                self.q.put(("badge", count))
            except Exception as e:
                log(f"배지 읽기 오류: {e!r}")
            time.sleep(self.cfg["badge_poll_seconds"])

    def _read_badge(self):
        if not self._db_dead:
            try:
                return self._read_db(), "db"
            except Exception as e:
                log(f"알림 DB 읽기 실패, 작업표시줄로 전환: {e!r}")
                self._db_dead = True
        return self._read_taskbar(), "taskbar"

    def _read_db(self):
        import sqlite3
        con = sqlite3.connect(f"file:{self.WPN_DB}?mode=ro", uri=True, timeout=2)
        try:
            row = con.execute(
                "SELECT n.Payload FROM Notification n "
                "JOIN NotificationHandler h ON n.HandlerId=h.RecordId "
                "WHERE h.PrimaryId='MSTeams_8wekyb3d8bbwe!MSTeams' "
                "AND n.Type='badge' ORDER BY n.ArrivalTime DESC LIMIT 1"
            ).fetchone()
        finally:
            con.close()
        if not row:
            return 0
        payload = row[0]
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8", "ignore")
        m = re.search(r'value="(\d+)', payload)
        if m:
            return int(m.group(1))
        return 1 if re.search(r'value="\w', payload) else 0

    def _read_taskbar(self):
        if self._desktop is None:
            from pywinauto import Desktop
            self._desktop = Desktop(backend="uia")
        tb = self._desktop.window(class_name="Shell_TrayWnd")
        name = None
        for b in tb.descendants(control_type="Button"):
            n = b.window_text() or ""
            if "teams" in n.lower():
                name = n
                break
        if not name:
            return 0
        clean = re.sub(r"\d+\s*running windows?", "", name, flags=re.I)
        nums = re.findall(r"\d+", clean)
        if nums:
            return int(nums[0])
        if re.search(r"new notification|새 알림", clean, re.I):
            return 1
        return 0


# ---------------------------------------------------------------- 프레임
def build_frames():
    """draw_shiba로 모든 동작 프레임을 시작 시 렌더링해둔다."""

    def mk(pose, face="normal", h=150, rot=0.0, sx=1.0, sy=1.0,
           mirror=False, **kw):
        im = render(pose, face, **kw)
        if mirror:
            im = im.transpose(Image.FLIP_LEFT_RIGHT)
        w0 = max(1, int(im.width * (h / im.height) * sx))
        im = im.resize((w0, int(h * sy)), Image.LANCZOS)
        if rot:
            im = im.rotate(rot, expand=True, resample=Image.BICUBIC)
        return im

    spec = {
        # 서기 (숨쉬기 2프레임 + 깜빡 + 손 흔들기)
        "idle0": mk("stand"),
        "idle1": mk("stand", sy=0.965),
        "blink": mk("stand", "blink"),
        "wave0": mk("stand", wave=True),
        "wave1": mk("stand", sy=0.97, wave=True),
        "stretch": mk("stand", sx=1.06, sy=0.92),
        # 앉기
        "sit0": mk("sit"),
        "sit1": mk("sit", sy=0.97),
        "sit_blink": mk("sit", "blink"),
        "drowsy": mk("sit", "sleep"),
        # 네발 걷기 (R=오른쪽으로 이동)
        **{f"walkR{i}": mk("walk", phase=i, h=118, mirror=True) for i in range(4)},
        **{f"walkL{i}": mk("walk", phase=i, h=118) for i in range(4)},
        # 전력질주 (먼 거리 이동·줌인)
        **{f"runR{i}": mk("run", "happy", phase=i, h=118, mirror=True) for i in range(2)},
        **{f"runL{i}": mk("run", "happy", phase=i, h=118) for i in range(2)},
        # 플레이바우 (놀자 자세, 꼬리 흔들기)
        **{f"bowR{i}": mk("bow", "happy", wag=i, h=128, mirror=True) for i in range(2)},
        **{f"bowL{i}": mk("bow", "happy", wag=i, h=128) for i in range(2)},
        # 벌러덩 (배 보이고 버둥버둥)
        "roll0": mk("roll", "happy", phase=0, h=128),
        "roll1": mk("roll", "happy", phase=1, h=128),
        # 땅파기
        **{f"digR{i}": mk("dig", phase=i, h=122, mirror=True) for i in range(2)},
        **{f"digL{i}": mk("dig", phase=i, h=122) for i in range(2)},
        # 고개 갸우뚱
        "sit_tilt": mk("sit", tilt=14),
        # 잠 (엎드림)
        "sleep": mk("lie", "sleep", h=112),
        # 신남
        "happy0": mk("arms_up", "happy"),
        "happy1": mk("arms_up", "happy", sy=0.96),
        "jump": mk("arms_up", "happy", sx=0.96, sy=1.06),
        # 깜짝 (잠 깰 때)
        "startle": mk("stand", "shock"),
        # 걱정 (배지 알림)
        "soft0": mk("stand", "worried", rot=-5),
        "soft1": mk("stand", "worried", rot=5),
        # 거대 패닉 (커지는 2단계 + 좌우 요동)
        "alert_g0": mk("arms_up", "shock", h=185, spread=True),
        "alert_g1": mk("arms_up", "shock", h=235, spread=True),
        "alert0": mk("arms_up", "shock", h=285, rot=-13, spread=True),
        "alert1": mk("arms_up", "shock", h=285, rot=13, spread=True),
    }
    frames, heights = {}, {}
    for k, im in spec.items():
        bg = Image.new("RGB", (FW, FH), KEY)
        mask = im.getchannel("A").point(lambda a: 255 if a >= 128 else 0)
        bg.paste(im, ((FW - im.width) // 2, FH - im.height), mask)
        frames[k] = ImageTk.PhotoImage(bg)
        heights[k] = im.height
    return frames, heights


# ---------------------------------------------------------------- 펫 본체
class Pet:
    def __init__(self, root, cfg, in_queue, test_mode=False):
        self.root = root
        self.cfg = cfg
        self.q = in_queue
        self.frames, self.fh = build_frames()

        self.state = "idle"
        self.posture = "stand"           # stand | sit
        self.tick_n = 0
        self.frame_key = "idle0"
        self.bubble = ""
        self.facing = 1
        self.last_interaction = time.time()
        self.next_act = time.time() + random.uniform(5, 12)
        self.react_kind = ""
        self.react_t0 = 0.0
        self.react_until = 0.0
        self.sleep_t0 = 0.0
        self.wake_at = 0.0
        self.alert_t0 = 0.0
        self.anchor = None
        self.last_beep = 0.0
        self.badge_count = 0
        self.badge_acked = 0
        self.alert_badge_seen = False   # 난동 중 배지가 올라간 적 있는지
        self.dragging = False
        self.walk_target = 0

        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        self.home = self._load_pos(sw, sh) or (sw - W - 120, sh - H - 50)
        self.pos = list(self.home)

        root.overrideredirect(True)
        root.attributes("-transparentcolor", KEY)
        self.sound_var = tk.BooleanVar(value=bool(cfg["sound"]))
        self.topmost_var = tk.BooleanVar(value=bool(cfg["always_on_top"]))
        root.attributes("-topmost", self.topmost_var.get())
        root.geometry(f"{W}x{H}+{int(self.pos[0])}+{int(self.pos[1])}")

        self.canvas = tk.Canvas(root, width=W, height=H, bg=KEY, highlightthickness=0)
        self.canvas.pack()
        self.img_item = self.canvas.create_image(W // 2, H - 2, anchor="s",
                                                 image=self.frames["idle0"])

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

        menu = tk.Menu(root, tearoff=0)
        menu.add_command(label="설정...", command=self.open_settings)
        menu.add_separator()
        menu.add_command(label="알림 테스트 (날뛰기)",
                         command=lambda: self.enter_alert(
                             (self.cfg["keywords"][0] if self.cfg["keywords"]
                              else "테스트") + " (테스트)"))
        menu.add_command(label="배지 알림 테스트", command=lambda: self.enter_soft(1))
        menu.add_checkbutton(label="소리", variable=self.sound_var)
        menu.add_checkbutton(label="항상 위", variable=self.topmost_var,
                             command=self._apply_topmost)
        menu.add_separator()
        menu.add_command(label="종료", command=root.destroy)
        self.canvas.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))

        if test_mode:
            root.after(4000, lambda: self.enter_alert("교수님 (테스트)"))

        root.after(600, self._push_bottom)   # 시작하자마자 맨 뒤로
        self.poll_queue()
        self.tick()

    # ----- 설정 창 -----
    def open_settings(self):
        if getattr(self, "_sett", None) is not None and self._sett.winfo_exists():
            self._sett.lift()
            return
        w = tk.Toplevel(self.root)
        self._sett = w
        w.title("시바펫 설정")
        w.attributes("-topmost", True)
        w.resizable(False, False)
        w.geometry(f"+{self.root.winfo_screenwidth() // 2 - 180}+220")

        tk.Label(w, text="누구의 메시지에 날뛸까요?",
                 font=("Malgun Gothic", 11, "bold")).pack(anchor="w", padx=14, pady=(12, 0))
        tk.Label(w, text="Teams에 표시되는 이름을 한 줄에 한 명씩 적으세요.\n"
                         "이름의 일부만 적어도 됩니다 (예: 홍길동, Gildong).\n"
                         "비워두면 모든 Teams 알림에 반응합니다.",
                 fg="#666666", justify="left",
                 font=("Malgun Gothic", 9)).pack(anchor="w", padx=14, pady=(2, 4))
        txt = tk.Text(w, width=36, height=6, font=("Malgun Gothic", 10))
        txt.pack(padx=14, pady=4)
        txt.insert("1.0", "\n".join(self.cfg["keywords"]))

        auto_var = tk.BooleanVar(value=STARTUP_VBS.exists())
        tk.Checkbutton(w, text="소리 (알림 경고음)",
                       variable=self.sound_var).pack(anchor="w", padx=14)
        tk.Checkbutton(w, text="항상 위 (평소에도 모든 창 위에 떠 있기)",
                       variable=self.topmost_var,
                       command=self._apply_topmost).pack(anchor="w", padx=14)
        tk.Checkbutton(w, text="Windows 시작 시 자동 실행",
                       variable=auto_var).pack(anchor="w", padx=14)

        def save():
            names = [ln.strip() for ln in txt.get("1.0", "end").splitlines()
                     if ln.strip()]
            self.cfg["keywords"] = names
            self.cfg["sound"] = bool(self.sound_var.get())
            self.cfg["always_on_top"] = bool(self.topmost_var.get())
            try:
                CONFIG_PATH.write_text(
                    json.dumps(self.cfg, ensure_ascii=False, indent=2),
                    encoding="utf-8")
            except OSError as e:
                log(f"설정 저장 실패: {e}")
            set_autostart(auto_var.get())
            log(f"설정 저장: keywords={names or '전체 Teams 알림'}, "
                f"autostart={auto_var.get()}")
            self.show_bubble("설정 저장 완료!", 4)
            w.destroy()

        tk.Button(w, text="저장", width=14, command=save).pack(pady=(8, 12))

    # ----- 유틸 -----
    def _apply_topmost(self):
        if self.state != "alert":
            self.root.attributes("-topmost", self.topmost_var.get())
            self._push_bottom()

    def _push_bottom(self):
        """창을 z순서 맨 아래로 — 평소엔 모든 창 뒤(바탕화면 위)에 있게."""
        if self.topmost_var.get() or self.state == "alert":
            return
        if not getattr(self, "_hwnd", None):
            self._hwnd = ctypes.windll.user32.FindWindowW(None, "teams-pet")
        if self._hwnd:
            # HWND_BOTTOM=1, SWP_NOSIZE|SWP_NOMOVE|SWP_NOACTIVATE=0x13
            ctypes.windll.user32.SetWindowPos(self._hwnd, 1, 0, 0, 0, 0, 0x13)

    def beep(self, kind):
        if self.sound_var.get():
            winsound.MessageBeep(kind)
            self.last_beep = time.time()

    def set_frame(self, key):
        if key != self.frame_key:
            self.frame_key = key
            self.canvas.itemconfig(self.img_item, image=self.frames[key])

    def move_to(self, x, y):
        self.pos = [x, y]
        self.root.geometry(f"+{int(x)}+{int(y)}")

    def _band_y(self, y):
        """집(home)의 y는 항상 화면 맨 아래 띠 안으로."""
        sh = self.root.winfo_screenheight()
        return min(max(y, sh - H - 115), sh - H - 35)

    def _load_pos(self, sw, sh):
        try:
            p = json.loads(POS_PATH.read_text(encoding="utf-8"))
            return (min(max(int(p[0]), 0), sw - W),
                    min(max(int(p[1]), sh - H - 115), sh - H - 35))
        except Exception:
            return None

    def _save_pos(self):
        try:
            POS_PATH.write_text(json.dumps([int(self.home[0]), int(self.home[1])]),
                                encoding="utf-8")
        except OSError:
            pass

    # ----- 마우스 -----
    def on_press(self, e):
        self.dragging = False
        self._press_xy = (e.x_root, e.y_root)
        self._press_win = tuple(self.pos)

    def on_drag(self, e):
        if self.state == "alert":
            return
        dx, dy = e.x_root - self._press_xy[0], e.y_root - self._press_xy[1]
        if abs(dx) + abs(dy) > 6:
            self.dragging = True
            self.move_to(self._press_win[0] + dx, self._press_win[1] + dy)

    def on_release(self, e):
        if self.dragging:
            # 좌우 위치는 그대로, 집의 높이는 화면 아래 띠로 (다음 산책 때 내려옴)
            self.home = (self.pos[0], self._band_y(self.pos[1]))
            self._save_pos()
            self.enter_idle()
            return
        self.last_interaction = time.time()
        if self.state == "alert":
            self.calm()
        elif self.state == "soft":
            self.badge_acked = max(self.badge_count, self.badge_acked)
            log(f"배지 알림 확인됨 (count={self.badge_count})")
            self.enter_react("hearts")
        elif self.state == "sleep":
            log("자다 깸 (클릭)")
            self.enter_react("startle")
        else:
            kind = random.choice(["hearts", "bark", "spin", "jump", "wave", "roll"])
            log(f"클릭 반응: {kind}")
            self.enter_react(kind)

    # ----- 상태 진입 -----
    def enter_idle(self):
        self.state = "idle"
        self.bubble = ""
        self.posture = "sit" if random.random() < 0.35 else "stand"
        self.next_act = time.time() + random.uniform(6, 18)
        self.set_frame("sit0" if self.posture == "sit" else "idle0")

    def _rand_point(self, near_home=False):
        """산책 목적지 — 화면 맨 아래쪽 띠 안에서만 (좌우는 화면 전체)."""
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        if near_home:
            x = self.home[0] + random.uniform(-400, 400)
        else:
            x = random.uniform(10, sw - W - 10)
        y = random.uniform(sh - H - 115, sh - H - 35)
        return (min(max(x, 10), sw - W - 10), y)

    def enter_walk(self, run=False, waypoints=None):
        if waypoints is None:
            waypoints = [self._rand_point(near_home=random.random() < 0.3)]
        self.way = list(waypoints)
        d = math.hypot(self.way[0][0] - self.pos[0], self.way[0][1] - self.pos[1])
        self.running = run or d > 900       # 먼 거리는 뛰어간다
        self.state = "walk"
        self._next_waypoint()

    def _next_waypoint(self):
        self.walk_target = self.way.pop(0)
        dx = self.walk_target[0] - self.pos[0]
        if abs(dx) > 12:
            self.facing = 1 if dx > 0 else -1

    def enter_zoomies(self):
        log("신나서 질주! (zoomies)")
        self.enter_walk(run=True,
                        waypoints=[self._rand_point() for _ in range(random.randint(2, 3))])

    def enter_sleep(self):
        self.state = "sleep"
        self.sleep_t0 = time.time()
        self.wake_at = self.sleep_t0 + random.uniform(60, 180)
        self.set_frame("drowsy")

    REACT_DUR = {"startle": 1.2, "roll": 2.6, "bow": 1.8, "dig": 2.2, "tilt": 1.6}

    def enter_react(self, kind):
        self.state = "react"
        self.react_kind = kind
        self.react_t0 = time.time()
        self.react_until = self.react_t0 + self.REACT_DUR.get(kind, 1.7)
        if kind == "bark":
            self.bubble = "멍멍!"

    def enter_soft(self, count):
        if self.state == "alert":
            return
        log(f"순한 알림: Teams 배지 {count}개 (토스트 없이 감지)")
        self.state = "soft"
        self.bubble = "Teams 확인!"
        self.beep(winsound.MB_OK)

    def enter_alert(self, title):
        self.bubble = title if len(title) <= 22 else title[:22] + "…"
        if self.state != "alert":
            log(f"ALERT 시작: {title}")
            self.state = "alert"
            self.alert_t0 = time.time()
            self.anchor = None
            self.alert_badge_seen = self.badge_count > 0
            self.root.attributes("-topmost", True)
        self.beep(winsound.MB_ICONEXCLAMATION)

    def calm(self, reason="클릭"):
        log(f"진정됨 ({reason})")
        self.bubble = ""
        self.root.attributes("-topmost", self.topmost_var.get())
        self.move_to(*self.home)
        self.enter_react("hearts")
        self._push_bottom()

    # ----- 이벤트 큐 -----
    def poll_queue(self):
        try:
            while True:
                kind, data = self.q.get_nowait()
                if kind == "alert":
                    self.enter_alert(data)
                elif kind == "badge":
                    self.badge_count = data
                    if self.state == "alert" and data > 0:
                        self.alert_badge_seen = True
                    if data == 0:
                        self.badge_acked = 0
                        if self.state == "soft":
                            self.enter_idle()
                        elif self.state == "alert" and self.alert_badge_seen:
                            # 배지가 올라갔다가 0이 됨 = Teams에서 읽음
                            self.calm("Teams에서 읽음 확인, 자동")
                    elif data > self.badge_acked and self.state in ("idle", "walk", "sleep"):
                        self.enter_soft(data)
                elif kind == "bubble":
                    self.bubble = data
        except queue.Empty:
            pass
        self.root.after(400, self.poll_queue)

    # ----- 메인 루프 (상태별 프레임 주기) -----
    TICK_MS = {"idle": 150, "walk": 100, "sleep": 280,
               "react": 90, "soft": 130, "alert": 50}

    def tick(self):
        self.tick_n += 1
        now = time.time()
        getattr(self, "tick_" + self.state)(now)
        self.draw_fx()
        if self.state != "alert" and self.tick_n % 12 == 0:
            self._push_bottom()   # 클릭 등으로 떠올랐어도 다시 맨 뒤로
        self.root.after(self.TICK_MS[self.state], self.tick)

    def tick_idle(self, now):
        sit = self.posture == "sit"
        if self.tick_n % 28 == 0:       # 약 4초마다 눈 깜빡
            self.set_frame("sit_blink" if sit else "blink")
        elif sit:
            self.set_frame("sit0" if (self.tick_n // 4) % 2 else "sit1")
        else:
            self.set_frame("idle0" if (self.tick_n // 4) % 2 else "idle1")
        if now < self.next_act:
            return
        r = random.random()
        if r < 0.18 and now - self.last_interaction > 90:
            self.enter_sleep()
        elif r < 0.30:
            self.enter_zoomies()
        elif r < 0.72:
            self.enter_walk()
        else:
            self.enter_react(random.choice(["wave", "dig", "tilt", "bow"]))

    def tick_walk(self, now):
        tx, ty = self.walk_target
        dx, dy = tx - self.pos[0], ty - self.pos[1]
        dist = math.hypot(dx, dy)
        sp = 10.5 if self.running else 3.6
        if dist <= sp:
            self.move_to(tx, ty)
            if self.way:
                self._next_waypoint()
            elif self.running:
                self.enter_react("bow")   # 질주가 끝나면 놀자 자세
            else:
                self.enter_idle()
            return
        self.move_to(self.pos[0] + dx / dist * sp, self.pos[1] + dy / dist * sp)
        d = "R" if self.facing > 0 else "L"
        if self.running:
            self.set_frame(f"run{d}{(self.tick_n // 2) % 2}")
        else:
            self.set_frame(f"walk{d}{(self.tick_n // 2) % 4}")

    def tick_sleep(self, now):
        # 1.5초간 앉아서 졸다가 엎드린다
        self.set_frame("drowsy" if now - self.sleep_t0 < 1.5 else "sleep")
        if now > self.wake_at:
            self.enter_idle()

    def tick_react(self, now):
        k = self.react_kind
        if k == "startle":   # 자다 깨면 화들짝 → 이내 신남
            if now - self.react_t0 < 0.5:
                self.set_frame("startle")
            else:
                self.set_frame("happy0" if (self.tick_n // 2) % 2 else "happy1")
        elif k == "hearts":
            self.set_frame("happy0" if (self.tick_n // 2) % 2 else "happy1")
        elif k == "jump":
            self.set_frame("jump" if (self.tick_n // 2) % 2 else "happy0")
        elif k == "bark":
            self.set_frame("stretch" if (self.tick_n // 2) % 2 else "idle0")
        elif k == "spin":
            seq = ["walkR0", "walkR2", "walkL0", "walkL2"]
            self.set_frame(seq[self.tick_n % 4])
        elif k == "wave":
            self.set_frame("wave0" if (self.tick_n // 3) % 2 else "wave1")
        elif k == "roll":
            self.set_frame("roll0" if (self.tick_n // 3) % 2 else "roll1")
        elif k == "bow":
            d = "R" if self.facing > 0 else "L"
            self.set_frame(f"bow{d}{(self.tick_n // 3) % 2}")
        elif k == "dig":
            d = "R" if self.facing > 0 else "L"
            self.set_frame(f"dig{d}{(self.tick_n // 2) % 2}")
        elif k == "tilt":
            self.set_frame("sit_tilt")
        else:
            self.set_frame("stretch" if (self.tick_n // 3) % 2 else "idle0")
        if now > self.react_until:
            self.bubble = ""
            self.enter_idle()

    def tick_soft(self, now):
        # 제자리에서 안절부절 서성거림
        sway = math.sin(self.tick_n * 0.35) * 22
        self.move_to(self.home[0] + sway, self.home[1])
        self.set_frame("soft0" if (self.tick_n // 3) % 2 else "soft1")

    def tick_alert(self, now):
        el = now - self.alert_t0
        if el < 0.20:                    # 커지는 연출
            self.set_frame("alert_g0")
            return
        if el < 0.40:
            self.set_frame("alert_g1")
            return
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        if self.anchor is None or self.tick_n % 40 == 0:
            self.anchor = (random.randint(30, max(31, sw - W - 30)),
                           random.randint(30, max(31, sh - H - 80)))
        x = self.pos[0] + (self.anchor[0] - self.pos[0]) * 0.25 + random.uniform(-9, 9)
        y = self.pos[1] + (self.anchor[1] - self.pos[1]) * 0.25 + random.uniform(-9, 9)
        self.move_to(x, y)
        self.set_frame("alert0" if (self.tick_n // 2) % 2 else "alert1")
        if self.tick_n % 10 == 0:
            self.root.attributes("-topmost", True)
            self.root.lift()
        if now - self.last_beep > 12:
            self.beep(winsound.MB_ICONEXCLAMATION)

    # ----- 효과 (말풍선, 하트, 느낌표 등) — 스프라이트 키 높이에 맞춰 배치
    def draw_fx(self):
        c = self.canvas
        c.delete("fx")
        st = self.state
        cx = W // 2
        top = H - 2 - self.fh.get(self.frame_key, 150)   # 스프라이트 머리 위 y

        if st == "alert":
            jy = math.sin(self.tick_n * 0.7) * 6
            c.create_text(cx - 70, top + 26 + jy, text="!", fill=ALERT_RED,
                          font=("Segoe UI", 34, "bold"), tags="fx")
            c.create_text(cx + 72, top + 34 - jy, text="!", fill=ALERT_RED,
                          font=("Segoe UI", 25, "bold"), tags="fx")
        elif st == "soft":
            qy = math.sin(self.tick_n * 0.3) * 4
            c.create_text(cx + 58, top + 16 + qy, text="?", fill=SOFT_BLUE,
                          font=("Segoe UI", 24, "bold"), tags="fx")
        elif st == "sleep":
            ph = (self.tick_n // 3) % 3
            for i in range(ph + 1):
                c.create_text(cx + 40 + i * 17, top + 26 - i * 24, text="z",
                              fill="#7986cb", font=("Segoe UI", 12 + i * 4, "bold"),
                              tags="fx")
        elif st == "react" and self.react_kind in ("hearts", "startle", "roll"):
            p = (time.time() - self.react_t0) * 30
            c.create_text(cx - 52, top + 36 - p, text="♥", fill="#e91e63",
                          font=("Segoe UI", 16), tags="fx")
            c.create_text(cx + 54, top + 48 - p * 0.8, text="♥", fill="#f48fb1",
                          font=("Segoe UI", 12), tags="fx")

        if self.bubble:
            t = self.bubble
            color = ALERT_RED if st == "alert" else (
                SOFT_BLUE if st == "soft" else "#555555")
            bw = min(W - 6, 13 * len(t) + 26)
            x0 = max(3, min(cx - bw / 2, W - 3 - bw))
            y0 = max(2, top - 38)
            c.create_rectangle(x0, y0, x0 + bw, y0 + 30, fill="white",
                               outline=color, width=2, tags="fx")
            c.create_text(x0 + bw / 2, y0 + 15, text=t, fill=color,
                          font=("Malgun Gothic", 10, "bold"), tags="fx")


def main():
    lock = acquire_single_instance_lock()
    if lock is None:
        log("이미 실행 중이라 종료합니다")
        return

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    first_run = not CONFIG_PATH.exists()
    cfg = load_config()
    q = queue.Queue()
    NotificationWatcher(cfg, q).start()
    BadgeWatcher(cfg, q).start()

    root = tk.Tk()
    root.title("teams-pet")
    pet = Pet(root, cfg, q, test_mode="--test" in sys.argv)
    log(f"펫 시작 (keywords={cfg['keywords'] or '전체 Teams 알림'})")
    if first_run:
        pet.show_bubble("안녕하세요! 설정을 해주세요", 12)
        root.after(1500, pet.open_settings)
    root.mainloop()


if __name__ == "__main__":
    main()
