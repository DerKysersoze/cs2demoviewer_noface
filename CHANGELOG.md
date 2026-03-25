# Changelog

## [Unreleased]

### Fixed
- **Incorrect/zero field values** (`app.py`, `index.html`): Corrected all column name mappings to match the actual `awpy` v2 schema revealed by debug logging:
  - **Rounds**: `winner_side` → `winner`; CT/T winner resolved by comparing winner name against `ct_side`/`t_side` from the kills DataFrame; `ct_score`/`t_score` now computed cumulatively (not read from rounds, which has no score columns); equipment value columns removed entirely — not present in this schema.
  - **Kills**: `through_smoke` → `thrusmoke`; `no_scope` → `noscope`; team names derived from `ct_side`/`t_side` + `attacker_side`/`victim_side` per round, replacing the nonexistent `attacker_team_name`/`victim_team_name`.
  - **Damages**: `hp_damage_taken` → `dmg_health_real` (with `dmg_health` as fallback).
  - **Frontend**: Removed CT/T Equipment columns from the Rounds table header and row renderer.

- **`KeyError` on first-seen player names** (`app.py`): The `inc()` helper evaluated `stats[player]` on the right-hand side before `stats.setdefault(player, {})` on the left-hand side had a chance to insert the key, raising a `KeyError` for any player encountered for the first time. Fixed by capturing the `setdefault` return value and reading from it on the same line.

- **Polars compatibility** (`app.py`): Resolved `AttributeError: 'DataFrame' object has no attribute 'empty'` caused by `awpy` v2.x switching from pandas to Polars DataFrames as its internal format.
  - Added `_to_pd()` helper that detects whether a DataFrame is a Polars or pandas instance and normalises it to pandas before any further processing.
  - Polars DataFrames are checked with `.is_empty()` and converted via `.to_pandas()`; pandas DataFrames continue to use `.empty` as before.
  - Applied `_to_pd()` to all three DataFrame reads: `demo.rounds`, `demo.kills`, and `demo.damages`.
  - Guarded `.iloc[-1]` accesses on team-name columns with an explicit `len()` check to prevent index errors on empty series after conversion.
