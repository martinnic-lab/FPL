"""Bounded rolling-horizon transfer planner with banked free transfers.

This is a beam-search approximation, not a globally exact solver. Uses external
per-GW forecasts and user-confirmed live financial inputs. No chips modeled.
"""
from dataclasses import dataclass
from itertools import combinations
from engine import legal_squad, lineup, POSITIONS


@dataclass(frozen=True)
class State:
    squad: tuple
    bank: int
    free_transfers: int
    sell: tuple
    score: float
    actions: tuple


def search(squad, players, weeks, forecasts, bank, free_transfers, selling_prices,
           beam_width=12, per_position=5, max_weekly_transfers=1):
    if not legal_squad(squad, players):
        raise ValueError("Invalid starting squad")
    if any(i not in selling_prices for i in squad):
        raise ValueError("Verified current selling prices required")
    if not 0 <= free_transfers <= 5 or bank < 0:
        raise ValueError("Invalid free transfers or bank")
    if len(weeks) < 2:
        raise ValueError("Need at least two future gameweeks")
    if max_weekly_transfers != 1:
        raise ValueError("Only 0/1 weekly transfer supported")
    initial = State(tuple(sorted(squad)), bank, free_transfers,
                    tuple(sorted((i, selling_prices[i]) for i in squad)), 0., ())
    beam = [initial]
    for gw in weeks:
        pool = {}
        for pos in POSITIONS:
            available = [i for i, p in players.items() if p["element_type"] == pos
                         and p["status"] == "a"]
            available.sort(key=lambda i: forecasts[i].get(gw, 0), reverse=True)
            pool[pos] = available[:per_position]
        expanded = []
        for state in beam:
            sell = dict(state.sell)
            moves = [(None, None)]
            for out in state.squad:
                for incoming in pool[players[out]["element_type"]]:
                    if incoming not in state.squad:
                        moves.append((out, incoming))
            for out, incoming in moves:
                ids = set(state.squad)
                money = state.bank
                updated_sell = dict(sell)
                transfers = 0
                if out is not None:
                    ids.remove(out)
                    ids.add(incoming)
                    money += sell[out] - players[incoming]["now_cost"]
                    if money < 0:
                        continue
                    del updated_sell[out]
                    updated_sell[incoming] = players[incoming]["now_cost"]
                    transfers = 1
                if not legal_squad(list(ids), players):
                    continue
                hit = 4 * max(0, transfers - state.free_transfers)
                # FTs refresh once per GW, capped at 5. Spent FTs cannot be negative.
                next_ft = min(5, max(0, state.free_transfers - transfers) + 1)
                weekly = lineup(list(ids), players,
                                {i: forecasts[i].get(gw, 0) for i in ids})
                action = {"gw": gw, "out": out, "in": incoming, "hit": hit,
                          "xi": weekly["xi"], "captain": weekly["captain"],
                          "bench": weekly["bench"], "expected": weekly["expected"],
                          "bank_after_tenths": money, "free_transfers_next": next_ft}
                expanded.append(State(tuple(sorted(ids)), money, next_ft,
                                      tuple(sorted(updated_sell.items())),
                                      state.score + weekly["expected"] - hit,
                                      state.actions + (action,)))
        if not expanded:
            raise ValueError("No feasible future squad")
        # Deduplicate equivalent economic states; retain best score.
        best = {}
        for state in expanded:
            key = (state.squad, state.bank, state.free_transfers, state.sell)
            if key not in best or state.score > best[key].score:
                best[key] = state
        beam = sorted(best.values(), key=lambda x: x.score, reverse=True)[:beam_width]
    return {"status": "bounded_beam_search_no_chips",
            "horizon": weeks, "beam_width": beam_width,
            "best": {"expected_total": round(beam[0].score, 3),
                     "actions": list(beam[0].actions)},
            "alternatives": [{"expected_total": round(s.score, 3),
                              "actions": list(s.actions)}
                             for s in beam[1:4]],
            "warnings": ["Search is approximate and limited to one transfer per GW.",
                         "Uses fixed market prices and assumes new players sell for purchase price.",
                         "No chips, price changes, autosub probabilities or correlation modeling.",
                         "Only meaningful with independently calibrated multiweek forecasts.",
                         "Cumbres data is not read or used."]}
