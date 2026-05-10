"""
Voice command parser for ATC voice input.

Converts Deepgram transcripts like:
  "Envoy seventy nine forty seven pushback approved"
into ATC command strings:
  "7947 pa"

Airline callsigns are loaded live from airlines.json.
"""

from __future__ import annotations

import json
import os
import re
import logging
from typing import Optional

logger = logging.getLogger("VoiceParser")


# ── Load airlines dynamically from airlines.json ──────────────────────────────

def _load_airline_map() -> dict[str, str]:
    """
    Build a spoken-word → ICAO-prefix lookup from airlines.json.

    For each airline we register:
      • Every word of the callsign (e.g. "SPIRIT WINGS" → both "spirit" and "spirit wings")
      • The first word of the airline name (e.g. "American Airlines" → "american")

    Multi-word callsigns are tried first (longest match wins in the parser).
    """
    mapping: dict[str, str] = {}

    paths = ["airlines.json", os.path.join("data", "airlines.json")]
    data = []
    for path in paths:
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                break
            except Exception as e:
                logger.warning(f"Could not load airlines.json from {path}: {e}")

    for airline in data:
        icao = airline.get("airline_icao", "").strip().upper()
        if not icao:
            continue

        callsign = airline.get("callsign", "").strip().lower()
        name     = airline.get("name", "").strip().lower()

        # Full callsign (may be multi-word like "spirit wings")
        if callsign:
            mapping[callsign] = icao
            # Also register just the first word if multi-word
            first_word = callsign.split()[0]
            if first_word not in mapping:
                mapping[first_word] = icao

        # First word of the airline name as a fallback
        if name:
            first_name_word = name.split()[0]
            if first_name_word not in mapping:
                mapping[first_name_word] = icao

    logger.info(f"Loaded {len(mapping)} airline callsign entries")
    return mapping


AIRLINE_MAP: dict[str, str] = _load_airline_map()

# Sort keys longest-first so multi-word callsigns are matched before single words
_AIRLINE_KEYS_SORTED = sorted(AIRLINE_MAP.keys(), key=len, reverse=True)


# ── Number words → single digit ───────────────────────────────────────────────

DIGIT_WORDS: dict[str, str] = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "niner": "9",
}

# Deepgram sometimes transcribes individual ATC digits as tens words.
# "seventy nine" in ATC context = digits 7 and 9 → "79"
TENS_WORDS: dict[str, str] = {
    "twenty": "2", "thirty": "3", "forty": "4", "fifty": "5",
    "sixty": "6", "seventy": "7", "eighty": "8", "ninety": "9",
}

# Teen numbers produce two digits directly ("sixteen" → "16")
TEEN_WORDS: dict[str, str] = {
    "eleven": "11", "twelve": "12", "thirteen": "13", "fourteen": "14",
    "fifteen": "15", "sixteen": "16", "seventeen": "17", "eighteen": "18",
    "nineteen": "19",
}

# ── Phonetic alphabet → letter ────────────────────────────────────────────────

PHONETIC: dict[str, str] = {
    "alpha": "a", "bravo": "b", "charlie": "c", "delta": "d",
    "echo": "e", "foxtrot": "f", "golf": "g", "hotel": "h",
    "india": "i", "juliet": "j", "kilo": "k", "lima": "l",
    "mike": "m", "november": "n", "oscar": "o", "papa": "p",
    "quebec": "q", "romeo": "r", "sierra": "s", "tango": "t",
    "uniform": "u", "victor": "v", "whiskey": "w",
    "x-ray": "x", "xray": "x", "yankee": "y", "zulu": "z",
}

# ── Filler / address words to strip ──────────────────────────────────────────

FILLERS = {
    "uh", "um", "erm", "uhh", "umm", "ah", "er", "like", "so", "okay", "ok",
    # ATC address words (pilot calling ATC)
    "ground", "tower", "approach", "departure", "center", "radar",
}

# ── Command phrase patterns ───────────────────────────────────────────────────
# Applied to normalised text (digits and phonetics already resolved).
# Patterns tried in order; first match wins.

_RWY = r"(\d{1,2}[lrcLRC]?)"      # runway: 2, 02, 20, 14R …
_VIA = r"((?:[a-z]\s*)+)"          # taxiway letters: "a u b"
_VW  = r"(?:via|taxiway)"          # "via" or "taxiway" are both used by STT

# fmt: off
COMMAND_PATTERNS = [

    # ── Pushback ──────────────────────────────────────────────────────────────
    # "pushback approved", "push and start", "push back approved",
    # "cleared for pushback", "pushback clearance approved"
    (r"(?:cleared\s+(?:for\s+)?)?push(?:\s*back)?(?:\s+and\s+start)?(?:\s+approved)?(?:\s+clearance)?",
     "pa"),

    # ── Taxi to runway ────────────────────────────────────────────────────────

    # "taxi to runway 20 via/taxiway alpha uniform"
    (r"taxi\s+to\s+runway\s+" + _RWY + r"\s+" + _VW + r"\s+" + _VIA,          "taxi_via"),
    # "cleared to taxi runway 20 via/taxiway alpha"
    (r"cleared\s+to\s+taxi\s+runway\s+" + _RWY + r"\s+" + _VW + r"\s+" + _VIA,"taxi_via"),
    # "taxi via/taxiway alpha uniform to runway 20"
    (r"taxi\s+" + _VW + r"\s+" + _VIA + r"\s+to\s+runway\s+" + _RWY,          "taxi_via_inv"),
    # "runway 20 taxi/cleared via/taxiway alpha uniform"  (STT sometimes flips order)
    (r"runway\s+" + _RWY + r"\s+(?:taxi|cleared)(?:\s+to)?\s+" + _VW + r"\s+" + _VIA, "taxi_via"),
    # "runway 20 taxiway alpha uniform"  (no taxi/cleared prefix)
    (r"runway\s+" + _RWY + r"\s+" + _VW + r"\s+" + _VIA,                      "taxi_via"),
    # "taxi to runway 20" (no via)
    (r"taxi\s+to\s+runway\s+" + _RWY,                                  "taxi_norwy"),
    # "cleared to taxi runway 20"
    (r"cleared\s+to\s+taxi\s+runway\s+" + _RWY,                        "taxi_norwy"),
    # "runway 20 taxi" (no via, flipped order)
    (r"runway\s+" + _RWY + r"\s+(?:taxi|cleared)",                     "taxi_norwy"),

    # ── Taxi to parking/ramp/gate (arrivals) ──────────────────────────────────
    # "taxi to parking via/taxiway alpha uniform"
    (r"taxi\s+to\s+(?:parking|ramp|gate|terminal|the\s+ramp|the\s+gate)\s+" + _VW + r"\s+" + _VIA, "taxi_parking_via"),
    # "cleared to taxi to parking via/taxiway alpha"
    (r"cleared\s+(?:to\s+)?taxi\s+(?:to\s+)?(?:parking|ramp|gate|terminal)\s+" + _VW + r"\s+" + _VIA, "taxi_parking_via"),
    # "taxi to parking" (no via)
    (r"taxi\s+to\s+(?:parking|ramp|gate|terminal|the\s+ramp|the\s+gate)\b",  "taxi_parking"),

    # ── Hold short ────────────────────────────────────────────────────────────
    # "hold short of runway 20", "hold short runway 20"
    (r"hold\s+short\s+(?:of\s+)?runway\s+" + _RWY,                    "hold_short"),

    # ── Hold position ─────────────────────────────────────────────────────────
    # "hold position", "stop", "hold"
    (r"hold\s+position",                                               "hold_pos"),
    (r"\bstop\b",                                                      "hold_pos"),

    # ── Cross runway ──────────────────────────────────────────────────────────
    # "cross runway 20", "cleared to cross runway 20"
    (r"(?:cleared\s+to\s+)?cross\s+runway\s+" + _RWY,                 "cross"),

    # ── Expect runway ─────────────────────────────────────────────────────────
    # "expect runway 20", "plan on runway 20", "anticipate runway"
    (r"(?:expect|plan\s+(?:on|for)|anticipate)\s+runway\s+" + _RWY,   "expect"),

    # ── Contact tower ─────────────────────────────────────────────────────────
    # "contact tower", "switch to tower", "frequency change approved"
    (r"contact\s+tower",                                               "ct"),
    (r"switch\s+(?:to\s+)?tower",                                      "ct"),
    (r"frequency\s+change\s+approved",                                 "ct"),
    (r"tower\s+frequency",                                             "ct"),

    # ── Squawk ────────────────────────────────────────────────────────────────
    (r"squawk\s+(\d{4})",                                              "squawk"),
    (r"squawk\s+(?:mode\s+)?(?:charlie|c)\b",                         "sqc"),
]
# fmt: on


class VoiceParser:
    """Parse a Deepgram transcript into an ATC command string."""

    def __init__(self, aircraft_manager=None):
        self.aircraft_manager = aircraft_manager

    # ── Public ────────────────────────────────────────────────────────────────

    def parse(self, transcript: str) -> list[str]:
        """Return a list of ATC command strings like ['7947 pa', '7947 ex02'].
        Returns an empty list if nothing was recognised."""
        if not transcript:
            return []

        logger.debug(f"Raw transcript: '{transcript}'")
        text = transcript.lower().strip()

        # 1. Strip filler words and punctuation
        text = self._clean(text)

        # 2. Resolve phonetic alphabet words (alpha → a, etc.)
        #    Do this BEFORE digit resolution so "november" stays "n" not a phonetic
        text = self._resolve_phonetics(text)

        # 3. Resolve spoken digits (seven nine → 79, seventy nine → 79)
        text = self._resolve_digits(text)

        logger.debug(f"Normalised: '{text}'")

        # 4. Extract callsign from the front of the text
        callsign_id, rest = self._extract_callsign(text)
        if not callsign_id:
            logger.warning(f"No callsign found in: '{text}'")
            return []

        logger.debug(f"Callsign='{callsign_id}'  rest='{rest}'")

        # 5. Match ALL command phrases (handles compound transmissions like
        #    "pushback approved expect runway 20")
        cmds = self._match_all_commands(rest, callsign_id)
        if cmds:
            logger.info(f"Voice → {cmds}")
        else:
            logger.warning(f"No command matched in: '{rest}'")
        return cmds

    # ── Text cleaning ─────────────────────────────────────────────────────────

    def _clean(self, text: str) -> str:
        text = re.sub(r"[,.'!?\-]", " ", text)
        words = [w for w in text.split() if w not in FILLERS]
        return " ".join(words)

    def _resolve_phonetics(self, text: str) -> str:
        words = text.split()
        out = []
        i = 0
        while i < len(words):
            two = f"{words[i]} {words[i+1]}" if i + 1 < len(words) else ""
            if two in PHONETIC:
                out.append(PHONETIC[two])
                i += 2
            elif words[i] in PHONETIC:
                out.append(PHONETIC[words[i]])
                i += 1
            else:
                out.append(words[i])
                i += 1
        return " ".join(out)

    def _resolve_digits(self, text: str) -> str:
        """Convert spoken digit/tens/teen words to digit characters.

        Handles:
          • Individual: "seven nine four seven" → "7947"
          • Compound:   "seventy nine forty seven" → "7947"
          • Teens:      "sixteen eighty seven" → "1687"
        """
        words = text.split()
        result = []
        i = 0
        while i < len(words):
            w = words[i]
            if w in DIGIT_WORDS or w in TENS_WORDS or w in TEEN_WORDS:
                digits = []
                while i < len(words):
                    w = words[i]
                    if w in TEEN_WORDS:
                        digits.append(TEEN_WORDS[w])
                        i += 1
                    elif w in DIGIT_WORDS:
                        digits.append(DIGIT_WORDS[w])
                        i += 1
                    elif w in TENS_WORDS:
                        tens_d = TENS_WORDS[w]
                        i += 1
                        if i < len(words) and words[i] in DIGIT_WORDS:
                            digits.append(tens_d)
                            digits.append(DIGIT_WORDS[words[i]])
                            i += 1
                        else:
                            digits.append(tens_d + "0")
                    else:
                        break
                result.append("".join(digits))
            else:
                result.append(w)
                i += 1
        return " ".join(result)

    # ── Callsign extraction ───────────────────────────────────────────────────

    def _extract_callsign(self, text: str) -> tuple[Optional[str], str]:
        """
        Find a callsign anywhere in the text — everything before it is preamble
        and is ignored, so the controller can say "hey Envoy 659, pushback approved"
        or "alright Envoy six fifty nine go ahead and push" and it still works.

        Tries (in order):
          1. Multi-word airline callsign + digits anywhere  ("hey spirit wings 79 47" → NKS7947)
          2. Single-word airline callsign + digits anywhere ("hey envoy 7947"         → ENY7947)
          3. Bare digits anywhere                           ("7947 pa"                → "7947")
          4. Any digit sequence matched uniquely to a live aircraft flight number
        """
        words = text.split()
        if not words:
            return None, text

        # 1 & 2. Try airline callsigns longest-first, scanning anywhere in words
        best: tuple[int, str, str] | None = None  # (word_pos, callsign, rest)
        for key in _AIRLINE_KEYS_SORTED:
            key_words = key.split()
            n = len(key_words)
            icao = AIRLINE_MAP[key]
            for i in range(len(words) - n + 1):
                if words[i:i + n] == key_words:
                    rest_words = words[i + n:]
                    if rest_words and re.match(r"^\d+$", rest_words[0]):
                        flight_num = rest_words[0]
                        if best is None or i < best[0]:
                            best = (i, icao + flight_num, " ".join(rest_words[1:]))
                    break  # only first occurrence per key

        if best:
            return best[1], best[2]

        # 3. Bare digits anywhere (controller shorthand: "7947 pa")
        for i, w in enumerate(words):
            if re.match(r"^\d+$", w):
                return w, " ".join(words[i + 1:])

        if self.aircraft_manager:
            ac_list = getattr(self.aircraft_manager, "aircraft", [])
            if isinstance(ac_list, dict):
                ac_list = list(ac_list.values())

            # 4. Scan for any digit sequence and match uniquely against aircraft
            #    flight numbers — handles garbled airline name ("arroy 17 …")
            ACTIVE_STATES = {"TAXI", "PUSHBACK", "HOLDING", "CROSSING", "TAXIING"}
            for digits in re.findall(r"\d+", text):
                matches = []
                for ac in ac_list:
                    cs_upper = ac.get_callsign().upper()
                    fn = str(getattr(ac, "flight_number", ""))
                    num_suffix = re.sub(r"^[A-Z]+", "", cs_upper)
                    if fn == digits or num_suffix == digits:
                        matches.append(ac)

                winner = None
                if len(matches) == 1:
                    winner = matches[0]
                elif len(matches) > 1:
                    active = [
                        ac for ac in matches
                        if str(getattr(ac, "state", "")).upper() in ACTIVE_STATES
                    ]
                    if len(active) == 1:
                        winner = active[0]

                if winner:
                    idx = text.find(digits)
                    rest = text[idx + len(digits):].strip()
                    logger.debug(
                        f"Flight-number fuzzy match: '{digits}' → {winner.get_callsign()}"
                    )
                    return winner.get_callsign(), rest

        return None, text

    # ── Command matching ──────────────────────────────────────────────────────

    def _match_all_commands(self, text: str, callsign_id: str) -> list[str]:
        """Find every non-overlapping command pattern in *text* (left to right).
        Allows compound transmissions like 'pushback approved expect runway 20'
        to produce multiple commands in one utterance."""
        text = text.strip()

        # Collect all pattern matches with their span
        candidates: list[tuple[int, int, re.Match, str]] = []
        for pattern, tag in COMMAND_PATTERNS:
            m = re.search(pattern, text)
            if m:
                candidates.append((m.start(), m.end(), m, tag))

        # Sort by start position; greedily pick non-overlapping spans
        candidates.sort(key=lambda x: x[0])
        selected: list[tuple[re.Match, str]] = []
        last_end = -1
        for start, end, m, tag in candidates:
            if start >= last_end:
                selected.append((m, tag))
                last_end = end

        # Build a command string for each selected match
        cmds: list[str] = []
        for m, tag in selected:
            cmd = self._build_command(m, tag, callsign_id)
            if cmd:
                cmds.append(cmd)
        return cmds

    def _build_command(self, m: re.Match, tag: str, callsign_id: str) -> Optional[str]:
        """Translate a single regex match + tag into an ATC command string."""
        if tag == "pa":
            return f"{callsign_id} pa"

        elif tag == "taxi_via":
            rwy = m.group(1).replace(" ", "")
            via = self._extract_taxiways(m.group(2))
            return f"{callsign_id} r{rwy}{via}" if via else f"{callsign_id} r{rwy}"

        elif tag == "taxi_via_inv":
            via = self._extract_taxiways(m.group(1))
            rwy = m.group(2).replace(" ", "")
            return f"{callsign_id} r{rwy}{via}" if via else f"{callsign_id} r{rwy}"

        elif tag == "taxi_norwy":
            rwy = m.group(1).replace(" ", "")
            return f"{callsign_id} r{rwy}"

        elif tag == "taxi_parking_via":
            via = self._extract_taxiways(m.group(1))
            return f"{callsign_id} rp{via}" if via else f"{callsign_id} rp"

        elif tag == "taxi_parking":
            return f"{callsign_id} rp"

        elif tag == "hold_short":
            rwy = m.group(1).replace(" ", "")
            return f"{callsign_id} h{rwy}"

        elif tag == "hold_pos":
            return f"{callsign_id} h"

        elif tag == "cross":
            rwy = m.group(1).replace(" ", "")
            return f"{callsign_id} cr{rwy}"

        elif tag == "expect":
            rwy = m.group(1).replace(" ", "")
            return f"{callsign_id} ex{rwy}"

        elif tag == "ct":
            return f"{callsign_id} ct"

        elif tag == "squawk":
            return f"{callsign_id} sq{m.group(1)}"

        elif tag == "sqc":
            return f"{callsign_id} sqc"

        return None

    def _extract_taxiways(self, raw: str) -> str:
        """Pull single-letter taxiway IDs from a string like 'a u '."""
        return "".join(re.findall(r"\b([a-z])\b", raw))


# ── Convenience ───────────────────────────────────────────────────────────────

def parse_voice_command(transcript: str, aircraft_manager=None) -> list[str]:
    return VoiceParser(aircraft_manager).parse(transcript)
