"""
Flight Strips Window — separate OS window (F2 to toggle).

Strip layout (3 rows, 4 columns):

  ┌──────────┬────────┬──────┬──────────────────────────────────────────┐
  │ CALLSIGN │ BCN    │ DEP  │ ROUTE                                    │
  │ TYP/EQ   │        │      │                                          │
  │ CID      │ ALT    │      │ REMARKS / DEST                           │
  └──────────┴────────┴──────┴──────────────────────────────────────────┘

Click any field to edit it. Enter confirms, Escape cancels.
"""

import pygame
from typing import Optional, Any

_sdl2_ok = False
try:
    from pygame._sdl2 import video as _sdlvideo  # type: ignore
    _sdl2_ok = True
except ImportError:
    pass

# ----- Fonts -----

MAIN_FONT = "data/fonts/Inconsolata_ExtraExpanded-SemiBold.ttf"  
HANDWRITING_FONT = "data/fonts/Strip_font_handwritten.ttf"

# ── Dimensions ────────────────────────────────────────────────────────────────
WIN_W    = 900
WIN_H    = 900
STRIP_H  = 90    # height of one strip (do not change)
STRIP_GAP = 6    # gap between strips
TITLE_BAR_H = 36 # height of the dark header bar
HDR_H    = TITLE_BAR_H + 6  # top padding before first strip (after title bar)
ROW_SLOT = STRIP_H // 3   # each of the 3 text rows occupies this many pixels

PAD = 5

# ── Column definitions (x, width) ────────────────────────────────────────────
C_ID    = (0,   120)   # CALLSIGN / TYPE / CID
C_BCN   = (120,  68)   # BCN / (empty) / ALT
C_DEP   = (188,  62)   # DEP airport
C_ROUTE = (250, 650)   # ROUTE / (empty) / REMARKS+DEST

# Column name → (x, w) for hit-testing
_COLS = [("id", C_ID), ("bcn", C_BCN), ("dep", C_DEP), ("route", C_ROUTE)]

# (col_name, row_slot_index) → editable field key
_FIELD_MAP = {
    ("id",    0): "callsign",
    ("id",    1): "type",
    ("id",    2): "cid",
    ("bcn",   0): "bcn",
    ("bcn",   2): "alt",
    ("dep",   0): "dep",
    ("route", 0): "route",
    ("route", 2): "remarks",
}

# ── Colours ───────────────────────────────────────────────────────────────────
C_WIN_BG      = (155, 155, 155)
C_DEP_BG      = (255, 255, 248)
C_ARR_BG      = (242, 249, 255)
C_DEP_ALT     = (248, 248, 235)
C_ARR_ALT     = (230, 243, 255)
C_TEXT        = (8,   8,   8)
C_DIM         = (160, 160, 160)
C_GRID        = (150, 150, 150)
C_SEP         = (100, 100, 100)
C_EDIT_BG     = (255, 255, 180)   # highlight for the cell being edited
C_CURSOR      = (0,   0,   180)   # text cursor colour
# Title bar — matches main window dark theme (top_menu_bar.py THEME)
C_TITLE_BG    = (24,  26,  30)
C_TITLE_TEXT  = (235, 238, 242)
C_TITLE_DIM   = (115, 120, 128)
C_TITLE_SEP   = (48,  51,  58)

STATE_BAR = {
    "PARKED":   (140, 140, 140),
    "PUSHBACK": (210, 130,   0),
    "TAXI":     (0,   155,   0),
    "HOLDING":  (210,  50,   0),
    "CROSSING": (0,   155, 155),
    "APPROACH": (0,    90, 200),
    "LANDING":  (0,    90, 200),
    "DEPARTED": (90,   90,  90),
}


def _state_label(ac) -> str:
    raw = str(getattr(ac, "state", "")).upper()
    for k in STATE_BAR:
        if k in raw:
            return k
    return raw[:10] if raw else ""


def _sort_key(ac):
    ft    = str(getattr(ac, "flight_type", "departure")).lower()
    state = _state_label(ac)
    ORD   = {"PARKED": 0, "PUSHBACK": 1, "TAXI": 2, "HOLDING": 3,
             "CROSSING": 4, "DEPARTED": 5, "APPROACH": 0, "LANDING": 1}
    return (0 if ft == "departure" else 1, ORD.get(state, 9))


class FlightStripsWindow:
    """Secondary OS window — 3-row flight strip layout. Toggle with F2.
    Click any cell to edit it; Enter confirms, Escape cancels.
    Overrides are stored per callsign and persist while the window is open.
    """

    def __init__(self):
        self._win:       Optional[Any]            = None
        self._renderer:  Optional[Any]            = None
        self._offscreen: Optional[pygame.Surface] = None
        self._font:      Optional[pygame.font.Font] = None
        self._font_sm:   Optional[pygame.font.Font] = None
        self._font_hw:   Optional[pygame.font.Font] = None   # handwriting — user edits
        self._font_hw_sm: Optional[pygame.font.Font] = None
        self.is_open = False

        # Editing state
        self._editing:   Optional[tuple[str, str]] = None  # (callsign, field)
        self._edit_text: str = ""
        self._edit_cursor: int = 0  # cursor position inside _edit_text

        # Per-callsign field overrides: {callsign: {field: value}}
        self._overrides: dict[str, dict[str, str]] = {}

        # Strip positions for hit-testing: [(y_start, callsign), ...]
        self._strip_map: list[tuple[int, str]] = []

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def toggle(self):
        self.close() if self.is_open else self.open()

    def open(self):
        if not _sdl2_ok:
            print("[FlightStrips] pygame._sdl2 unavailable.")
            return
        if self.is_open:
            return
        try:
            self._win      = _sdlvideo.Window("GroundStop — Flight Strips",
                                               size=(WIN_W, WIN_H), resizable=True)
            self._renderer = _sdlvideo.Renderer(self._win)
            self._offscreen = pygame.Surface((WIN_W, WIN_H))
            self._init_fonts()
            # Set window icon to match the main window
            import os
            icon_path = "data/images/aircraft_icon_norm.png"
            if os.path.exists(icon_path):
                try:
                    icon_surf = pygame.image.load(icon_path)
                    self._win.set_icon(icon_surf)
                except Exception:
                    pass
            self.is_open = True
        except Exception as e:
            print(f"[FlightStrips] Open failed: {e}")

    def close(self):
        if self._win:
            try:
                self._win.destroy()
            except Exception:
                pass
        self._win = self._renderer = self._offscreen = None
        self._editing = None
        self.is_open = False

    # ── Event handling ────────────────────────────────────────────────────────

    def handle_event(self, event: pygame.event.Event):
        if not self.is_open:
            return

        if event.type == pygame.WINDOWCLOSE:
            win = getattr(event, "window", None)
            if win is self._win or win is None:
                self.close()
            return

        # Only process input events directed at the strips window
        ev_win = getattr(event, "window", None)
        if ev_win is not None and ev_win is not self._win:
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._on_click(event.pos)

        elif event.type == pygame.KEYDOWN and self._editing is not None:
            self._on_key(event)

    def _on_click(self, pos):
        mx, my = pos
        hit = self._hit_test(mx, my)
        if hit is None:
            self._editing = None
            return
        callsign, field = hit
        # Start editing: pre-fill with current override or empty
        self._editing = (callsign, field)
        self._edit_text = self._overrides.get(callsign, {}).get(field, "")
        self._edit_cursor = len(self._edit_text)

    def _on_key(self, event):
        if self._editing is None:
            return
        callsign, field = self._editing

        if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
            # Confirm edit
            if callsign not in self._overrides:
                self._overrides[callsign] = {}
            if self._edit_text:
                self._overrides[callsign][field] = self._edit_text
            else:
                self._overrides[callsign].pop(field, None)
            self._editing = None

        elif event.key == pygame.K_ESCAPE:
            self._editing = None

        elif event.key == pygame.K_BACKSPACE:
            if self._edit_cursor > 0:
                self._edit_text = (self._edit_text[:self._edit_cursor - 1]
                                   + self._edit_text[self._edit_cursor:])
                self._edit_cursor -= 1

        elif event.key == pygame.K_DELETE:
            if self._edit_cursor < len(self._edit_text):
                self._edit_text = (self._edit_text[:self._edit_cursor]
                                   + self._edit_text[self._edit_cursor + 1:])

        elif event.key == pygame.K_LEFT:
            self._edit_cursor = max(0, self._edit_cursor - 1)

        elif event.key == pygame.K_RIGHT:
            self._edit_cursor = min(len(self._edit_text), self._edit_cursor + 1)

        elif event.key == pygame.K_HOME:
            self._edit_cursor = 0

        elif event.key == pygame.K_END:
            self._edit_cursor = len(self._edit_text)

        elif event.unicode and event.unicode.isprintable():
            self._edit_text = (self._edit_text[:self._edit_cursor]
                               + event.unicode
                               + self._edit_text[self._edit_cursor:])
            self._edit_cursor += 1

    def _hit_test(self, mx, my) -> Optional[tuple[str, str]]:
        for (y0, callsign) in self._strip_map:
            if y0 <= my < y0 + STRIP_H:
                row_slot = min(2, (my - y0) // ROW_SLOT)
                for col_name, (cx, cw) in _COLS:
                    if cx <= mx < cx + cw:
                        field = _FIELD_MAP.get((col_name, row_slot))
                        if field:
                            return (callsign, field)
        return None

    # ── Render ────────────────────────────────────────────────────────────────

    def update(self, aircraft_manager, airport_code: str = ""):
        if not self.is_open or self._renderer is None:
            return
        try:
            win_w, win_h = self._win.size
        except Exception:
            win_w, win_h = WIN_W, WIN_H

        if self._offscreen is None or self._offscreen.get_size() != (win_w, win_h):
            self._offscreen = pygame.Surface((win_w, win_h))

        surf = self._offscreen
        surf.fill(C_WIN_BG)
        self._draw_title_bar(surf, win_w, airport_code)

        ac_list = self._get_aircraft(aircraft_manager)
        ac_list.sort(key=_sort_key)

        self._strip_map = []
        y = HDR_H
        for idx, ac in enumerate(ac_list):
            if y + STRIP_H > win_h:
                break
            callsign = ac.get_callsign()
            self._strip_map.append((y, callsign))
            self._draw_strip(surf, ac, y, win_w, airport_code, idx)
            y += STRIP_H + STRIP_GAP

        if not ac_list and self._font:
            m = self._font.render("No aircraft", True, C_DIM)
            surf.blit(m, (win_w // 2 - m.get_width() // 2, win_h // 2))

        try:
            tex = _sdlvideo.Texture.from_surface(self._renderer, surf)
            self._renderer.clear()
            self._renderer.blit(tex, pygame.Rect(0, 0, win_w, win_h))
            self._renderer.present()
            del tex
        except Exception as e:
            print(f"[FlightStrips] Render error: {e}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _init_fonts(self):
        import os
        fallback = pygame.font.SysFont("consolas,courier new,monospace", 15)
        fallback_sm = pygame.font.SysFont("consolas,courier new,monospace", 13)

        # Main (printed) font
        try:
            if os.path.exists(MAIN_FONT):
                self._font    = pygame.font.Font(MAIN_FONT, 17)
                self._font_sm = pygame.font.Font(MAIN_FONT, 15)
            else:
                self._font    = fallback
                self._font_sm = fallback_sm
        except Exception:
            self._font    = fallback
            self._font_sm = fallback_sm

        # Handwriting font — used for user-entered overrides
        try:
            if os.path.exists(HANDWRITING_FONT):
                self._font_hw    = pygame.font.Font(HANDWRITING_FONT, 17)
                self._font_hw_sm = pygame.font.Font(HANDWRITING_FONT, 15)
            else:
                self._font_hw    = self._font
                self._font_hw_sm = self._font_sm
        except Exception:
            self._font_hw    = self._font
            self._font_hw_sm = self._font_sm

    def _get_aircraft(self, mgr) -> list:
        if mgr is None:
            return []
        raw = getattr(mgr, "aircraft", [])
        return list(raw.values()) if isinstance(raw, dict) else list(raw)

    # ── Title bar ─────────────────────────────────────────────────────────────

    def _draw_title_bar(self, surf: pygame.Surface, w: int, airport_code: str):
        """Dark header bar matching the main window's top menu theme."""
        pygame.draw.rect(surf, C_TITLE_BG, (0, 0, w, TITLE_BAR_H))
        pygame.draw.line(surf, C_TITLE_SEP, (0, TITLE_BAR_H), (w, TITLE_BAR_H), 1)

        if self._font_sm:
            cy = TITLE_BAR_H // 2
            title = self._font_sm.render("FLIGHT STRIPS", True, C_TITLE_TEXT)
            surf.blit(title, (PAD, cy - title.get_height() // 2))

            hint = self._font_sm.render("F2", True, C_TITLE_DIM)
            surf.blit(hint, (w - hint.get_width() - PAD, cy - hint.get_height() // 2))

            if airport_code:
                apt = self._font_sm.render(airport_code, True, C_TITLE_DIM)
                surf.blit(apt, (w - hint.get_width() - PAD * 2 - apt.get_width() - 8,
                                cy - apt.get_height() // 2))

    # ── Barcode ───────────────────────────────────────────────────────────────

    def _draw_barcode(self, surf: pygame.Surface, callsign: str, x: int, y: int):
        import random
        rng = random.Random(hash(callsign) & 0xFFFF_FFFF)

        # Asymmetric vertical offset and height
        y_off   = rng.randint(60 ,70)
        bar_h   = rng.randint(20, 25)
        x_start = x

        # ~22 bars, 1–3 px wide — total width stays around 40–60 px
        bx = x_start
        is_black = True
        for _ in range(22):
            bw = rng.randint(1, 3)
            if is_black:
                pygame.draw.rect(surf, (18, 18, 18), (bx, y + y_off, bw, bar_h))
            bx += bw
            is_black = not is_black

    # ── Strip ─────────────────────────────────────────────────────────────────

    def _draw_strip(self, surf: pygame.Surface, ac, y: int, w: int,
                    airport_code: str, row_idx: int):
        callsign = ac.get_callsign()
        ft       = str(getattr(ac, "flight_type", "departure")).lower()
        is_dep   = (ft == "departure")
        bg       = (C_DEP_BG if row_idx % 2 == 0 else C_DEP_ALT) if is_dep \
                   else (C_ARR_BG if row_idx % 2 == 0 else C_ARR_ALT)

        # Strip background
        pygame.draw.rect(surf, bg, (0, y, w, STRIP_H))

        # Bottom separator (extends into gap so strips look separated)
        pygame.draw.line(surf, C_SEP, (0, y + STRIP_H), (w, y + STRIP_H), 2)

        # Inner row dividers — BCN column only
        bcn_x, bcn_w = C_BCN
        for slot in (1, 2):
            ry = y + slot * ROW_SLOT
            pygame.draw.line(surf, C_GRID, (bcn_x, ry), (bcn_x + bcn_w, ry), 1)

        # Column vertical dividers — full strip height
        for col_def in (C_ID, C_BCN, C_DEP):
            cx, cw = col_def
            pygame.draw.line(surf, C_GRID, (cx + cw, y), (cx + cw, y + STRIP_H), 1)

        # ── Collect auto data ──────────────────────────────────────────────
        ac_type     = str(getattr(ac, "aircraft_type", "") or "???")
        _ac_airport = getattr(ac, "airport_data", None)
        dep_airport = str(((_ac_airport.get("airport", {}) or {}).get("icao", "") if isinstance(_ac_airport, dict) else "") or airport_code or "?")
        dep_route   = getattr(ac, "departure_route", None)
        dest        = dep_route.get("destination", "") if dep_route else ""
        dest        = dest or str(getattr(ac, "destination", "") or "")
        route       = dep_route.get("route", "")    if dep_route else ""
        exit_fix    = str(getattr(ac, "exit_fix", "") or "")
        filed_alt   = dep_route.get("altitude", 0)  if dep_route else 0

        sq = (getattr(ac, "atc_assigned_squawk", None)
              or getattr(ac, "correct_squawk_code", None)
              or getattr(ac, "current_squawk_code", None))

        auto: dict[str, str] = {
            "callsign": callsign,
            "type":     f"{ac_type}/L",
            "cid":      str((abs(hash(callsign)) % 9000) + 1000),
            "bcn":      str(sq).zfill(4) if sq else "----",
            "alt":      str(int(filed_alt) // 100) if filed_alt and int(filed_alt) > 0 else "",
            "dep":      dep_airport,
            "route":    route or exit_fix,
            "remarks":  dest,
        }

        overrides = self._overrides.get(callsign, {})

        def resolve(field: str) -> str:
            return overrides.get(field, auto.get(field, ""))

        # ── Draw helper ───────────────────────────────────────────────────
        def put(col_def, field: str, row_slot: int, dim=False, small=False):
            cx, cw = col_def
            is_editing = (self._editing == (callsign, field))
            text = self._edit_text if is_editing else resolve(field)

            # Highlight editing cell
            slot_y = y + row_slot * ROW_SLOT
            if is_editing:
                pygame.draw.rect(surf, C_EDIT_BG,
                                 (cx + 1, slot_y + 1, cw - 2, ROW_SLOT - 2))

            if not text and not is_editing:
                return

            # Use handwriting font when the field is user-edited or being typed into
            is_override = field in overrides
            use_hw = is_editing or is_override
            if use_hw:
                f = self._font_hw_sm if small else self._font_hw
            else:
                f = self._font_sm if small else self._font
            clr = C_CURSOR if is_editing else (C_DIM if dim else C_TEXT)
            rendered = f.render(text, True, clr)
            text_h = rendered.get_height()
            blit_y = slot_y + (ROW_SLOT - text_h) // 2

            old = surf.get_clip()
            surf.set_clip(pygame.Rect(cx + PAD, slot_y, cw - PAD * 2, ROW_SLOT))
            surf.blit(rendered, (cx + PAD, blit_y))

            # Draw blinking cursor
            if is_editing and (pygame.time.get_ticks() % 1000 < 500):
                pre = f.render(text[:self._edit_cursor], True, clr)
                cur_x = cx + PAD + pre.get_width()
                pygame.draw.line(surf, C_CURSOR,
                                 (cur_x, blit_y + 1),
                                 (cur_x, blit_y + text_h - 1), 1)

            surf.set_clip(old)

        # ── Rows ──────────────────────────────────────────────────────────
        # Row 0: CALLSIGN | BCN | DEP | ROUTE
        put(C_ID,    "callsign", 0)
        put(C_BCN,   "bcn",      0, dim=(resolve("bcn") == "----"))
        put(C_DEP,   "dep",      0)
        put(C_ROUTE, "route",    0)

        # Row 1: TYPE | (blank) | (blank) | (blank)
        put(C_ID,    "type",     1, small=True)

        # Row 2: CID | ALT | (blank) | REMARKS
        put(C_ID,    "cid",      2, dim=True, small=True)
        put(C_BCN,   "alt",      2, small=True)
        put(C_ROUTE, "remarks",  2, dim=not resolve("remarks"), small=True)

        # Barcode — drawn last so it layers on top
        bcn_x, bcn_w = C_BCN
        self._draw_barcode(surf, callsign, 58, y)
