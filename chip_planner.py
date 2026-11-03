"""Chip opportunity screening, NOT a complete sequential chip optimizer."""
from itertools import permutations


def chip_screen(lineups, used_chips, first_half_end=19):
    """Compare per-week incremental values and feasible distinct-week assignments.

    Bench Boost and TC have computable static-squad increments; Free Hit needs
    an optimized temporary squad and is deliberately NOT estimated as zero.
    """
    used = {x["name"] for x in used_chips if x["event"] <= first_half_end}
    remaining = [c for c in ("bboost", "3xc", "freehit") if c not in used]
    weeks = [int(w) for w in lineups if int(w) <= first_half_end]
    increments = {
        "bboost": {w: lineups[str(w)]["bench_boost_increment"] for w in weeks},
        "3xc": {w: lineups[str(w)]["triple_captain_increment"] for w in weeks},
        "freehit": {w: None for w in weeks}
    }
    computable = [c for c in remaining if c != "freehit"]
    options = []
    for assignments in permutations(weeks, len(computable)):
        value = sum(increments[chip][gw] for chip, gw in zip(computable, assignments))
        options.append({"chip_weeks": dict(zip(computable, assignments)),
                        "incremental_points_before_setup": round(value, 3)})
    options.sort(key=lambda x: x["incremental_points_before_setup"], reverse=True)
    return {"remaining_first_half_chips": remaining,
            "weeks_considered": weeks,
            "top_static_assignments": options[:5],
            "free_hit_status": "unmodeled_requires_temporary_squad_optimizer" if "freehit" in remaining else "used",
            "warnings": ["Chip history must be verified from refreshed official API.",
                         "This is a static squad screening, not a chip-aware transfer plan.",
                         "First-half chips expire at the GW19 deadline; do not treat missing future GWs as zero.",
                         "Only one chip per GW; no chip is committed by this output."]}


if __name__ == "__main__":
    raise SystemExit("Import chip_screen from engine reporting; no standalone chip recommendation.")
