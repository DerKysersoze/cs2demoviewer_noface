#!/usr/bin/env python3
"""
CS2 Demo Viewer
Decode and display Counter-Strike 2 .dem files.

Dependencies:
    pip install awpy rich pandas
"""

import argparse
import sys
from pathlib import Path


def check_deps():
    missing = []
    try:
        import awpy  # noqa: F401
    except ImportError:
        missing.append("awpy")
    try:
        import rich  # noqa: F401
    except ImportError:
        missing.append("rich")
    try:
        import pandas  # noqa: F401
    except ImportError:
        missing.append("pandas")
    if missing:
        print(f"Missing dependencies: {', '.join(missing)}")
        print(f"Install with: pip install {' '.join(missing)}")
        sys.exit(1)


check_deps()

from awpy import Demo  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.text import Text  # noqa: E402
from rich.columns import Columns  # noqa: E402
from rich import box  # noqa: E402

console = Console()

CT_COLOR = "cyan"
T_COLOR = "yellow"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def result_style(winner: str) -> str:
    if "CT" in str(winner).upper():
        return f"[bold {CT_COLOR}]CT Win[/bold {CT_COLOR}]"
    return f"[bold {T_COLOR}]T Win[/bold {T_COLOR}]"


def fmt_money(val) -> str:
    try:
        return f"${int(val):,}"
    except Exception:
        return str(val)


def _duration(h: dict) -> str:
    try:
        return f"{h['playback_time']:.1f}"
    except Exception:
        try:
            return f"{int(h['ticks_played']) / int(h['tick_rate']):.1f}"
        except Exception:
            return "?"


# ---------------------------------------------------------------------------
# Display sections
# ---------------------------------------------------------------------------

def show_header(demo: Demo, path: Path) -> None:
    h = demo.header
    lines = [
        f"[bold]File:[/bold]      {path.name}",
        f"[bold]Map:[/bold]       {h.get('map_name', 'unknown')}",
        f"[bold]Tickrate:[/bold]  {h.get('tick_rate', '?')} Hz",
        f"[bold]Ticks:[/bold]     {h.get('ticks_played', '?')}",
        f"[bold]Duration:[/bold]  {_duration(h)} s",
        f"[bold]Client:[/bold]    {h.get('client_name', '?')}",
        f"[bold]Server:[/bold]    {h.get('server_name', '?')}",
    ]
    console.print(Panel("\n".join(lines), title="[bold magenta]Demo Header[/bold magenta]", expand=False))


def show_scoreboard(demo: Demo) -> None:
    kills_df = demo.kills
    damages_df = demo.damages

    if kills_df is None or kills_df.empty:
        console.print("[dim]No kill data available.[/dim]")
        return

    stats: dict = {}

    def inc(player, key, amount=1):
        stats.setdefault(player, {})[key] = stats[player].get(key, 0) + amount

    for _, row in kills_df.iterrows():
        attacker = row.get("attacker_name")
        victim = row.get("victim_name")
        assister = row.get("assister_name")
        if attacker and str(attacker) != "nan":
            inc(attacker, "kills")
            if row.get("headshot"):
                inc(attacker, "hs")
            stats[attacker].setdefault("team", row.get("attacker_team_name", "?"))
        if victim and str(victim) != "nan":
            inc(victim, "deaths")
            stats.setdefault(victim, {}).setdefault("team", row.get("victim_team_name", "?"))
        if assister and str(assister) != "nan":
            inc(assister, "assists")

    if damages_df is not None and not damages_df.empty:
        for _, row in damages_df.iterrows():
            attacker = row.get("attacker_name")
            if attacker and str(attacker) != "nan":
                inc(attacker, "dmg", int(row.get("hp_damage_taken", 0) or 0))

    table = Table(title="Scoreboard", box=box.SIMPLE_HEAVY, show_lines=False)
    table.add_column("Player", style="bold white", no_wrap=True)
    table.add_column("Team", justify="center")
    table.add_column("K", justify="right", style="green")
    table.add_column("A", justify="right", style="blue")
    table.add_column("D", justify="right", style="red")
    table.add_column("K/D", justify="right")
    table.add_column("HS%", justify="right", style="yellow")
    table.add_column("DMG", justify="right", style="magenta")

    rows = []
    for player, s in stats.items():
        k = s.get("kills", 0)
        d = s.get("deaths", 0)
        a = s.get("assists", 0)
        hs = s.get("hs", 0)
        dmg = s.get("dmg", 0)
        kd = k / d if d else float(k)
        hs_pct = f"{100 * hs // k}%" if k else "0%"
        team = str(s.get("team", "?"))
        rows.append((player, team, k, a, d, kd, hs_pct, dmg))

    rows.sort(key=lambda r: r[2], reverse=True)

    for player, team, k, a, d, kd, hs_pct, dmg in rows:
        ct = "CT" in team.upper()
        team_display = (
            f"[{CT_COLOR}]{team}[/{CT_COLOR}]" if ct else f"[{T_COLOR}]{team}[/{T_COLOR}]"
        )
        table.add_row(player, team_display, str(k), str(a), str(d), f"{kd:.2f}", hs_pct, f"{dmg:,}")

    console.print(table)


def show_rounds(demo: Demo) -> None:
    rounds_df = demo.rounds
    if rounds_df is None or rounds_df.empty:
        console.print("[dim]No round data available.[/dim]")
        return

    table = Table(title="Round Summary", box=box.SIMPLE, show_lines=False)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Winner", justify="center")
    table.add_column("Reason", style="dim")
    table.add_column("CT $", justify="right")
    table.add_column("T $", justify="right")
    table.add_column("CT Score", justify="right", style=CT_COLOR)
    table.add_column("T Score", justify="right", style=T_COLOR)

    for _, row in rounds_df.iterrows():
        rnum = int(row.get("round_num", 0) or 0)
        winner = str(row.get("winner_side", "?"))
        reason = str(row.get("reason", "?")).replace("_", " ").title()
        ct_eq = fmt_money(row.get("ct_eq_val", 0))
        t_eq = fmt_money(row.get("t_eq_val", 0))
        ct_score = str(int(row.get("ct_score", 0) or 0))
        t_score = str(int(row.get("t_score", 0) or 0))

        table.add_row(str(rnum), result_style(winner), reason, ct_eq, t_eq, ct_score, t_score)

    console.print(table)


def show_kills(demo: Demo, limit: int = 30) -> None:
    kills_df = demo.kills
    if kills_df is None or kills_df.empty:
        console.print("[dim]No kill data available.[/dim]")
        return

    table = Table(title=f"Kill Feed (first {limit})", box=box.MINIMAL, show_lines=False)
    table.add_column("Tick", justify="right", style="dim")
    table.add_column("Rnd", justify="right", style="dim")
    table.add_column("Attacker", style="bold white")
    table.add_column("", justify="center")
    table.add_column("Victim", style="red")
    table.add_column("Weapon", style="green")
    table.add_column("Notes", style="dim")

    for _, row in kills_df.head(limit).iterrows():
        attacker = str(row.get("attacker_name", "?"))
        victim = str(row.get("victim_name", "?"))
        weapon = str(row.get("weapon", "?"))
        hs = "[bold yellow]HS[/bold yellow]" if row.get("headshot") else ""
        tick = str(int(row.get("tick", 0) or 0))
        rnum = str(int(row.get("round_num", 0) or 0))
        notes = []
        if row.get("through_smoke"):
            notes.append("smoke")
        if row.get("no_scope"):
            notes.append("no-scope")
        if row.get("penetrated_objects"):
            notes.append("wall")
        table.add_row(tick, rnum, attacker, hs, victim, weapon, " ".join(notes))

    console.print(table)


def show_overview(demo: Demo) -> None:
    rounds_df = demo.rounds
    ct_rounds = t_rounds = total = 0
    ct_team = t_team = "?"

    if rounds_df is not None and not rounds_df.empty:
        total = len(rounds_df)
        ct_rounds = int((rounds_df["winner_side"].str.upper() == "CT").sum())
        t_rounds = total - ct_rounds
        try:
            ct_team = rounds_df["ct_team_name"].dropna().iloc[-1]
        except Exception:
            pass
        try:
            t_team = rounds_df["t_team_name"].dropna().iloc[-1]
        except Exception:
            pass

    ct_text = Text(f"{ct_team}\n{ct_rounds}", justify="center", style=f"bold {CT_COLOR}")
    score_text = Text(f"vs\n{total} rounds", justify="center", style="bold white")
    t_text = Text(f"{t_team}\n{t_rounds}", justify="center", style=f"bold {T_COLOR}")

    console.print(
        Panel(
            Columns([ct_text, score_text, t_text], equal=True, expand=True),
            title="[bold]Match Result[/bold]",
            expand=False,
            width=50,
        )
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Decode and display CS2 demo (.dem) files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Sections:
  all       Show everything (default)
  header    Demo metadata only
  score     Player scoreboard
  rounds    Round-by-round breakdown
  kills     Kill feed

Examples:
  python cs2_demo_viewer.py match.dem
  python cs2_demo_viewer.py match.dem --section rounds
  python cs2_demo_viewer.py match.dem --section kills --kill-limit 50
        """,
    )
    parser.add_argument("demo", help="Path to the .dem file")
    parser.add_argument(
        "--section",
        choices=["all", "header", "score", "rounds", "kills"],
        default="all",
        help="Which section to display (default: all)",
    )
    parser.add_argument(
        "--kill-limit",
        type=int,
        default=30,
        metavar="N",
        help="Max kills to show in kill feed (default: 30)",
    )

    args = parser.parse_args()
    path = Path(args.demo)

    if not path.exists():
        console.print(f"[red]File not found:[/red] {path}")
        sys.exit(1)

    if path.suffix.lower() != ".dem":
        console.print("[yellow]Warning:[/yellow] file does not have a .dem extension")

    console.print(f"\n[bold]Parsing demo...[/bold] [dim]{path}[/dim]")

    try:
        demo = Demo(str(path))
        demo.parse()
    except Exception as e:
        console.print(f"[red]Failed to parse demo:[/red] {e}")
        sys.exit(1)

    console.print()

    section = args.section

    if section in ("all", "header"):
        show_header(demo, path)
        console.print()

    if section in ("all", "score"):
        show_overview(demo)
        console.print()
        show_scoreboard(demo)
        console.print()

    if section in ("all", "rounds"):
        show_rounds(demo)
        console.print()

    if section in ("all", "kills"):
        show_kills(demo, limit=args.kill_limit)
        console.print()


if __name__ == "__main__":
    main()
