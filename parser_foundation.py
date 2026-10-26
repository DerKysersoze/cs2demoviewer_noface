"""
parser_foundation.py — Demo wrapper for the CS2 viewer, built on demoparser2.

Provides the stable, app-facing interface that ``app.py`` consumes:

    demo = Demo(path)
    demo.parse()

    demo.header       # dict — map name, tick rate, ticks, playback time, client/server
    demo.rounds       # pd.DataFrame — round_num, winner, reason
    demo.kills        # pd.DataFrame — player_death events (round_num, victim, assister, ...)
    demo.damages      # pd.DataFrame — player_hurt events (round_num, victim, dmg, ...)
    demo.ticks        # pd.DataFrame (lazy) — per-player X/Y/Z, health, armor, helmet,
                      #               side, alive + round_num
    demo.shots        # pd.DataFrame (lazy) — weapon_fire events (aim-accuracy counts)
    demo.player_info  # pd.DataFrame — steamid, name, team_number (final demo state)

Column names verified against demoparser2 0.41.1 (do not "fix" without re-probing):

  * Events carry the round in column ``round`` (not ``round_num``), and only
    round_start / round_end carry it.  All other events (kills, damages, shots,
    grenades, buys) are assigned to rounds via their tick against the round
    index built from round_start ticks.
  * The victim of player_death / player_hurt is ``user_name`` /
    ``user_steamid`` — there is no ``victim_name`` column.
  * player_hurt has ``dmg_health`` / ``dmg_armor`` but no
    ``dmg_health_real`` and no ``distance`` (those exist on player_death).
  * parse_ticks silently DROPS unknown props.  Per-tick team is ``team_num``
    (2 = T, 3 = CT); ``side`` / ``round_num`` / ``weapon`` are NOT tick props.
    Accepted props: name, steamid, X, Y, Z, health, armor_value, has_helmet,
    is_alive, team_num, is_scoped, is_defusing, life_state, weapon_name, ...

    ``weapon_name`` re-verified 2026-10-26 against demoparser2 0.41.1 on the
    canonical de_nuke demo: 1,257,360 tick rows, ~75 % non-null, real names
    (AK-47, M4A1-S, AWP, knives, Smoke Grenade).  NaN during buy/respawn
    windows — consumers must treat it as optional.  Ammo is NOT available:
    ammo, ammo_count, clip_ammo, primary_ammo, secondary_ammo, reserve_clip,
    m_iAmmo, bullets, magazine, clip, reserve, ammo_left, primary_reserve_ammo
    are all silently dropped (probed same day).
  * Assists: player_death has ``assister_name`` / ``assister_steamid`` (NaN if
    no assist).
  * weapon_fire gives one row per shot fired (grenades included) — filter by
    weapon where needed.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

log = logging.getLogger("cs2viewer")

# CS2 (and Valve) servers run at 128 tick since mid-2023.  The demo header does
# not carry the tick rate, so we assume the CS2 default.  Only affects the
# displayed duration — positions, rounds and stats are tick-based and correct
# either way.  Rare 64-tick custom servers would show a 2x duration.
CS2_TICK_RATE = 128

# team_num values (Source engine team numbers)
TEAM_T = 2
TEAM_CT = 3


def _safe_int(val, default=0):
    try:
        if val is None or (isinstance(val, float) and val != val):
            return default
        return int(val)
    except (TypeError, ValueError):
        return default


def _safe_str(val, default="?"):
    if val is None or (isinstance(val, float) and val != val):
        return default
    s = str(val)
    return s if s.lower() not in ("nan", "none", "") else default


def _to_df(rows: list, columns: list) -> Optional[pd.DataFrame]:
    """Convert a list-of-dicts to a DataFrame; return None if empty."""
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=columns)
    return df if not df.empty else None


# ── Demo class ──────────────────────────────────────────────────────────────────


class Demo:
    """Demo parser wrapper backed by demoparser2."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._parser = None
        self.header: Dict[str, object] = {}
        self.rounds: Optional[pd.DataFrame] = None
        self.kills: Optional[pd.DataFrame] = None
        self.damages: Optional[pd.DataFrame] = None
        self.round_index: List[Tuple[int, int, int]] = []  # (round, start_tick, end_tick)
        self._round_starts: Optional[np.ndarray] = None    # sorted start ticks
        self._round_nums: Optional[np.ndarray] = None      # parallel round numbers
        self._ticks_df: Optional[pd.DataFrame] = None
        self._shots_df: Optional[pd.DataFrame] = None

    # ── parse() ───────────────────────────────────────────────────────────────

    def parse(self) -> None:
        """Parse the demo file and populate header/rounds/kills/damages.

        ticks and shots are lazy — parsed on first access.
        """
        from demoparser2 import DemoParser  # type: ignore

        self._parser = DemoParser(self.path)
        self._build_round_index()
        self._parse_header()
        self._parse_rounds()
        self._parse_kills()
        self._parse_damages()

    # ── round index (shared by all extractors) ────────────────────────────────

    def _build_round_index(self) -> None:
        """Build (round, start_tick, end_tick) from round_start/round_end events."""
        starts: Dict[int, int] = {}
        ends: Dict[int, int] = {}
        for ev, target in (("round_start", starts), ("round_end", ends)):
            try:
                df = self._parser.parse_event(ev)
            except Exception as e:
                log.debug("round index: %s failed — %s", ev, e)
                continue
            if df is None or df.empty:
                continue
            for _, row in df.iterrows():
                r = _safe_int(row.get("round"), 0)
                t = _safe_int(row.get("tick"), -1)
                if r <= 0 or t < 0:
                    continue
                if ev == "round_start":
                    starts[r] = min(starts.get(r, t), t)
                else:
                    ends[r] = t

        all_rounds = sorted(set(starts) | set(ends))
        self.round_index = []
        for i, r in enumerate(all_rounds):
            if r in starts:
                start = starts[r]
            elif i > 0:
                start = ends.get(all_rounds[i - 1], 0) + 1
            else:
                start = 0
            if r in ends:
                end = ends[r]
            elif i + 1 < len(all_rounds):
                end = starts.get(all_rounds[i + 1], 0) - 1
            else:
                end = 0  # unknown (last round still running) — open-ended below
            self.round_index.append((r, start, end))

        if self.round_index:
            self._round_starts = np.array([ri[1] for ri in self.round_index], dtype=np.int64)
            self._round_nums = np.array([ri[0] for ri in self.round_index], dtype=np.int64)
        else:
            self._round_starts = None
            self._round_nums = None

    def assign_rounds(self, df: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
        """Return a copy of ``df`` with a vectorized ``round_num`` column added.

        A tick belongs to the round whose start_tick is the greatest start
        <= tick (rounds are open-ended at the tail, which is correct: the last
        round runs to the end of the demo).  Ticks before the first round
        (preamble) get round_num = 0.
        """
        if df is None or df.empty or "tick" not in df.columns:
            return df
        if self._round_starts is None:
            df = df.copy()
            df["round_num"] = 0
            return df
        idx = np.searchsorted(self._round_starts, df["tick"].to_numpy(), side="right") - 1
        df = df.copy()
        df["round_num"] = np.where(idx >= 0, self._round_nums[np.clip(idx, 0, len(self._round_nums) - 1)], 0)
        return df

    # ── header ────────────────────────────────────────────────────────────────

    def _parse_header(self) -> None:
        try:
            raw = self._parser.parse_header() or {}
        except Exception as e:
            log.warning("parse_header failed: %s", e)
            raw = {}

        # Total ticks played: end tick of the last finished round (or last start).
        ticks_played = 0
        for _, _, end in self.round_index:
            ticks_played = max(ticks_played, end)
        if ticks_played == 0 and self.round_index:
            ticks_played = self.round_index[-1][1]

        self.header = {
            "map_name":       _safe_str(raw.get("map_name"), "unknown"),
            "tick_rate":      CS2_TICK_RATE,
            "ticks_played":   ticks_played,
            "playback_time":  round(ticks_played / CS2_TICK_RATE, 2) if ticks_played else 0,
            "client_name":    _safe_str(raw.get("client_name"), "?"),
            "server_name":    _safe_str(raw.get("server_name"), "?"),
            "patch_version":  str(raw.get("patch_version", "") or ""),
            "demo_file_stamp": str(raw.get("demo_file_stamp", "") or ""),
            "demo_version_guid": str(raw.get("demo_version_guid", "") or ""),
            "fullpackets_version": str(raw.get("fullpackets_version", "") or ""),
            "allow_clientside_entities": str(raw.get("allow_clientside_entities", "") or ""),
            "allow_clientside_particles": str(raw.get("allow_clientside_particles", "") or ""),
            "demo_version_name": str(raw.get("demo_version_name", "") or ""),
            "game_directory": str(raw.get("game_directory", "") or ""),
            "addons":         str(raw.get("addons", "") or ""),
        }

    # ── rounds ─────────────────────────────────────────────────────────────────

    def _parse_rounds(self) -> None:
        try:
            df = self._parser.parse_event("round_end")
        except Exception as e:
            log.warning("parse rounds (round_end) failed: %s", e)
            df = None

        rows = []
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                rows.append({
                    "round_num": _safe_int(row.get("round"), 0),
                    "winner":    _safe_str(row.get("winner"), "?").upper(),
                    "reason":    _safe_str(row.get("reason"), "?").replace("_", " ").title(),
                })
        self.rounds = _to_df(rows, ["round_num", "winner", "reason"])

    # ── kills (player_death) ───────────────────────────────────────────────────

    def _parse_kills(self) -> None:
        try:
            df = self._parser.parse_event("player_death")
        except Exception as e:
            log.warning("parse kills (player_death) failed: %s", e)
            df = None

        rows = []
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                rows.append({
                    "tick":             _safe_int(row.get("tick")),
                    "round_num":        0,  # filled in by assign_rounds()
                    "attacker_name":    _safe_str(row.get("attacker_name"), "?"),
                    "attacker_steamid": str(_safe_int(row.get("attacker_steamid"), 0)),
                    "victim_name":      _safe_str(row.get("user_name"), "?"),
                    "victim_steamid":   str(_safe_int(row.get("user_steamid"), 0)),
                    "weapon":           _safe_str(row.get("weapon"), "?"),
                    "headshot":         bool(row.get("headshot", False)),
                    "thrusmoke":        bool(row.get("thrusmoke", False)),
                    "noscope":          bool(row.get("noscope", False)),
                    "penetrated":       bool(_safe_int(row.get("penetrated"), 0)),
                    "assister_name":    _safe_str(row.get("assister_name"), ""),
                })

        df_out = _to_df(rows, [
            "tick", "round_num",
            "attacker_name", "attacker_steamid",
            "victim_name", "victim_steamid",
            "weapon", "headshot", "thrusmoke", "noscope", "penetrated",
            "assister_name",
        ])
        if df_out is not None:
            df_out = self.assign_rounds(df_out)
        self.kills = df_out

    # ── damages (player_hurt) ──────────────────────────────────────────────────

    def _parse_damages(self) -> None:
        try:
            df = self._parser.parse_event("player_hurt")
        except Exception as e:
            log.warning("parse damages (player_hurt) failed: %s", e)
            df = None

        rows = []
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                rows.append({
                    "tick":             _safe_int(row.get("tick")),
                    "round_num":        0,
                    "attacker_name":    _safe_str(row.get("attacker_name"), "?"),
                    "attacker_steamid": str(_safe_int(row.get("attacker_steamid"), 0)),
                    "victim_name":      _safe_str(row.get("user_name"), "?"),
                    "victim_steamid":   str(_safe_int(row.get("user_steamid"), 0)),
                    "dmg_health":       _safe_int(row.get("dmg_health"), 0),
                    "dmg_armor":        _safe_int(row.get("dmg_armor"), 0),
                    "hitgroup":         _safe_str(row.get("hitgroup"), "generic"),
                    "weapon":           _safe_str(row.get("weapon"), "?"),
                })

        df_out = _to_df(rows, [
            "tick", "round_num",
            "attacker_name", "attacker_steamid",
            "victim_name", "victim_steamid",
            "dmg_health", "dmg_armor", "hitgroup", "weapon",
        ])
        if df_out is not None:
            df_out = self.assign_rounds(df_out)
        self.damages = df_out

    # ── ticks (lazy) ───────────────────────────────────────────────────────────

    @property
    def ticks(self) -> Optional[pd.DataFrame]:
        """Player position/state per tick, with ``round_num`` and ``side`` added.

        Parsed lazily on first access.  ``side`` comes from the ``team_num``
        tick prop (2 → "T", 3 → "CT"); ``round_num`` is assigned from the
        round index.
        """
        if self._ticks_df is not None:
            return self._ticks_df
        if self._parser is None:
            return None
        try:
            props = [
                "name", "steamid",
                "X", "Y", "Z",
                "health", "armor_value", "has_helmet", "is_alive",
                "team_num",
                "weapon_name",  # per-tick weapon (NaN in buy/respawn — optional downstream)
            ]
            df = self._parser.parse_ticks(props)
            if df is None or df.empty:
                self._ticks_df = None
                return None

            df = self.assign_rounds(df)

            # team_num → side label
            if "team_num" in df.columns:
                tn = df["team_num"]
                df["side"] = np.where(tn == TEAM_CT, "CT",
                             np.where(tn == TEAM_T, "T", "?"))
            else:  # unexpected — keep a column so downstream code finds it
                df["side"] = "?"

            self._ticks_df = df
        except Exception as e:
            log.warning("parse ticks failed: %s", e)
            self._ticks_df = None
        return self._ticks_df

    # ── shots (lazy) — weapon_fire, for aim accuracy ──────────────────────────

    @property
    def shots(self) -> Optional[pd.DataFrame]:
        """All shots fired (one row per weapon_fire event).

        Columns: tick, player_name, steamid, weapon (+ round_num).
        Grenade throws are included — filter by ``weapon`` where needed.
        """
        if self._shots_df is not None:
            return self._shots_df
        if self._parser is None:
            return None
        try:
            df = self._parser.parse_event("weapon_fire")
            if df is None or df.empty:
                self._shots_df = None
                return None
            if "user_name" in df.columns:
                df = df.rename(columns={"user_name": "player_name",
                                        "user_steamid": "steamid"})
            self._shots_df = self.assign_rounds(df)
        except Exception as e:
            log.warning("parse shots (weapon_fire) failed: %s", e)
            self._shots_df = None
        return self._shots_df

    # ── player info (final state) ──────────────────────────────────────────────

    @property
    def player_info(self) -> Optional[pd.DataFrame]:
        """steamid, name, team_number (final state of the demo)."""
        if self._parser is None:
            return None
        try:
            df = self._parser.parse_player_info()
            return df if df is not None and not df.empty else None
        except Exception as e:
            log.warning("parse_player_info failed: %s", e)
            return None
