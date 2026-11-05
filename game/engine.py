import random
from treys import Card, Evaluator


START_STACK = 1000
BASE_SB = 10
HANDS_PER_LEVEL = 8
TURN_SECONDS = 60
SHOWDOWN_SECONDS = 9
FOLD_WIN_SECONDS = 5

RANKS = "23456789TJQA"
SUITS = "shdc"
BETTING_STAGES = ("preflop", "flop", "turn", "river")

_rng = random.SystemRandom()
_evaluator = Evaluator()


class GameError(Exception):
    pass


def blinds_for(hand_no):
    level = (hand_no - 1) // HANDS_PER_LEVEL
    sb = BASE_SB * (2 ** level)
    return sb, sb * 2


def seat_of(state, user_id):
    for p in state["players"]:
        if p["user_id"] == user_id:
            return p["seat"]
    return None


def _log(state, text):
    state["log"].append(text)
    del state["log"][:-40]


def _put(p, amount):
    amount = max(0, min(amount, p["stack"]))
    p["stack"] -= amount
    p["bet"] += amount
    p["total"] += amount
    if p["stack"] == 0:
        p["all_in"] = True
    return amount


def _pot(state):
    return sum(p["total"] for p in state["players"])


def _next_seat(state, start, pred):
    n = len(state["players"])
    for i in range(1, n+1):
        seat = (start + i) % n
        if pred(state["players"][seat]):
            return seat
    return None


def _cards_text(cards):
    return " ".join(c[0].replace("T", "10") + {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}[c[1]] for c in cards)


def new_game(users, now):
    sb, bb = blinds_for(1)
    state = {
        "hand_no": 0, "dealer": -1, "stage": "waiting",
        "sb": sb, "bb": bb, "sb_seat": None, "bb_seat": None,
        "players": [
            {"seat": i, "user_id": u["user_id"], "name": u["name"], "stack": START_STACK,
            "bet": 0, "total": 0, "folded": False, "all_in": False, "acted": False,
            "busted": False, "cards": [], "last": ""}
            for i, u in enumerate(users)
        ],
        "deck": [], "board": [], "turn": None, "current_bet": 0, "min_raise": bb,
        "turn_deadline": None, "next_hand_at": None, "result": None, "winner": None,
        "log": [],
    }
    start_hand(state, now)
    return state


def start_hand(state, now):
    players = state["players"]
    alive = [p for p in players if p["stack"] > 0]
    if len(alive) <= 1:
        state.update(stage="finished", turn=None, turn_deadline=None, next_hand_at=None, winner=alive[0]["seat"] if alive else None)
        return 
    state["hand_no"] += 1
    state["sb"], state["bb"] = blinds_for(state["hand_no"])
    for p in players:
        broke = p["stack"] == 0
        p.update(bet=0, total=0, folded=broke, busted=broke, all_in=False, acted=False, cards=[], last="")
    in_hand = lambda p: not p["busted"]
    state["dealer"] = _next_seat(state, state["dealer"], in_hand)
    dealer = state["dealer"]
    if len(alive) == 2:
        sb_seat = dealer
        bb_seat = _next_seat(state, dealer, in_hand)
    else:
        sb_seat = _next_seat(state, dealer, in_hand)
        bb_seat = _next_seat(state, sb_seat, in_hand)
    state["sb_seat"], state["bb_seat"] == sb_seat, bb_seat
    _put(players[sb_seat], state["sb"])
    _put(players[bb_seat], state["bb"])

    deck = [r + s for r in RANKS for s in SUITS]
    _rng.shuffle(deck)
    for p in players:
        if in_hand(p):
            p["cards"] = [deck.pop(), deck.pop()]
    state.update(deck=deck, board=[], stage="preflop", result=None, winner=None, next_hand_at=None, current_bet=max(p["bet"] for p in players), min_raise=state["bb"])
    _log(state, f"Hand #{state['hand_no']}. Blinds {state['sb']}/{state['bb']}")
    _advance(state, now, cursor=bb_seat)


def legal_actions(state, seat):
    if seat is None or state["stage"] not in BETTING_STAGES or state["turn"] != seat:
        return {"is_my_turn": False}
    p = state["players"][seat]
    to_call = max(0, state["current_bet"] - p["bet"])
    max_to = p["bet"] + p["stack"]
    can_raise = p["stack"] > to_call
    return {
        "is_my_turn": True,
        "can_check": to_call == 0,
        "to_call": to_call,
        "call_amount": min(to_call, p["stack"]),
        "call_is_allin": 0 < to_call >= p["stack"],
        "can_raise": can_raise,
        "min_raise_to": min(state["current_bet"] + state["min_raise"], max_to),
        "max_raise_to": max_to,
        "raise_label": "Bet" if state["current_bet"] == 0 else "Raise",
        "current_bet": state["current_bet"],
        "pot": _pot(state),
    }


def apply_action(state, seat, action, amount, now):
    if state["stage"] not in BETTING_STAGES:
        raise GameError("The hand is not in progress")
    if state["turn"] != seat:
        raise GameError("It is not your turn")
    p = state["players"][seat]
    to_call = max(0, state["current_bet"] - p["bet"])
    if action == "allin":
        action, amount = ("raise", p["bet"] + p["stack"]) if p["stack"] > to_call else ("call", None)
    if action == "fold":
        p["folded"] = True
        p["last"] = "Fold"
        _log(state, f"{p['name']} folds")
    elif action == "check":
        if to_call > 0:
            raise GameError("You can not check, there is a bet to call")
        p["acted"] = True
        p["last"] = "Check"
        _log(state, f"{p['name']} checks")
    elif action == "call":
        if to_call <= 0:
            raise GameError("There is nothing to call")
        paid = _put(p, to_call)
        p["acted"] = True
        p["last"] = "All-in" if p["all_in"] else f"Call {paid}"
        _log(state, f"{p['name']} calls {paid}" + (" (all-in)" if p["all_in"] else ""))
    elif action == "raise":
        try:
            amount = int(amount)
        except (TypeError, ValueError):
            raise GameError("Enter a valid amount")
        if p["stack"] <= to_call:
            raise GameError("You do not hane enough chips to raise. You can call or go all-in")
        max_to = p["bet"] + p["stack"]
        min_to = state["current_bet"] + state["min_raise"]
        if amount > max_to:
            raise GameError("You do not have that many chips")
        if amount < min_to and amount != max_to:
            raise GameError(f"The minimum raise is to {min_to}")
        verb = "bets" if state["current_bet"] == 0 else "raise to"
        increment = amount - state["current_bet"]
        _put(p, amount - p["bet"])
        if increment >= state["min_raise"]:
            state["min_raise"] = increment
        state["current_bet"] = amount
        p["acted"] = True
        for o in state["players"]:
            if o is not p and not o["folded"] and not o["all_in"]:
                o["acted"] = False
        p["last"] = "All-in" if p["all_in"] else ("Bet" if verb == "bets" else "Raise to" + str(amount))
        _log(state, f"{p['name']} {verb} {amount}" + (" (all-in)" if p["all_in"] else ""))
    else:
        raise GameError("Unknown action")
    _advance(state, now, cursor=seat)


def handle_timeout(state, now):
    if state["turn"] is None or state["turn_deadline"] is None or now < state["turn_deadline"]:
        return False
    seat = state["turn"]
    p = state["players"][seat]
    to_call = max(0, state["current_bet"] - p["bet"])
    apply_action(state, seat, "check" if to_call == 0 else "fold", None, now)
    p["last"] = "Check (time)" if to_call == 0 else "Fold (time)"
    return True


def maybe_next_hand(state, now):
    if state["stage"] == "showdown" and state["next_hand_at"] is not None and now >= state["next_hand_at"]:
        start_hand(state, now)
        return True
    return False


def _advance(state, now, cursor):
    players = state["players"]
    while True:
        live = [p for p in players if not p["folded"]]
        if len(live) == 1:
            _award_uncontested(state, live[0], now)
            return
        active = [p for p in live if not p["all_in"]]
        pending = [p for p in active if not p["acted"] or p["bet"] != state["current_bet"]]
        over = not pending or (len(active) <= 1 and (not active or active[0]["bet"] >= state["current_bet"]))
        if not over:
            seats = {p["seat"] for p in pending}
            state["turn"] = _next_seat(state, cursor, lambda p: p["seat"] in seats)
            state["turn_deadline"] = now + TURN_SECONDS
            return
        if state["stage"] == "river":
            _showdown(state, now)
            return
        _deal_next_street(state)
        cursor = state["dealer"]


def _deal_next_street(state):
    deck = state["deck"]
    deck.pop()
    if state["stage"] == "preflop":
        state["board"] += [deck.pop() for _ in range(3)]
        state["stage"] = "flop"
    else:
        state["board"].append(deck.pop())
        state["stage"] = "turn" if state["stage"] == "flop" else "river"
    for p in state["players"]:
        p["bet"] = 0
        p["acted"] = False
        if not p["folded"] and not p["all_in"]:
            p["last"] = ""
    state["current_bet"] = 0
    state["min_raise"] = state["bb"]
    _log(state, f"{state['stage'].capitalize()}: {_cards_text(state['board'])}")


def build_pots(players):
    pots = []
    prev = 0
    for level in sorted({p["total"] for p in players if p["total"] > 0}):
        contributors = [p for p in players if p["total"] >= level]
        amount = (level - prev) * len(contributors)
        eligible = [p["seat"] for p in contributors if not p["folded"]]
        prev = level
        if not eligible or (pots and pots[-1]["eligible"] == eligible):
            if pots:
                pots[-1]["amount"] += amount
                continue
        pots.append({"amount": amount, "eligible": eligible})
    return pots


def _split(state, amount, winners, payouts):
    share, rest = divmod(amount, len(winners))
    n = len(state["players"])
    for i, seat in enumerate(sorted(winners, key=lambda s: (s-state["dealer"] - 1) % n)):
        payouts[seat] = payouts.get(seat, 0) + share + (1 if i < rest else 0)


def _showdown(state, now):
    players = state["players"]
    board = [Card.new(c) for c in state["board"]]
    live = [p for p in players if not p["folded"]]
    scores = {p["seat"]: _evaluator.evaluate([Card.new(c) for c in p["cards"]], board) for p in live}
    names = {s: _evaluator.class_to_string(_evaluator.get_rank_class(v)) for s, v in scores.items()}
    payouts, pot_results = {}, []
    for pot in build_pots(players):
        best = min(scores[s] for s in pot["eligible"])
        winners = [s for s in pot["eligible"] if scores[s] == best]
        _split(state, pot["amount"], winners, payouts)
        pot_results.append({"amount": pot["amount"], "winners": winners, "hand": names[winners[0]]})
    result = {
        "uncontested": False, "pots": pot_results,
        "hands": [{"seat": s, "name": n} for s, n in names.items()],
        "revealed": [p["seat"] for p in live],
    }
    _finish_hand(state, now, payouts, result, SHOWDOWN_SECONDS)


def _award_uncontested(state, winner, now):
    total = _pot(state)
    result = {"uncontested": True, "pots": [{"amount": total, "winners": [winner["seat"]], "hand": None}],
              "hands": [], "revealed": []}
    _finish_hand(state, now, {winner["seat"]: total}, result, FOLD_WIN_SECONDS)


def _finish_hand(state, now, payouts, result, delay):
    players = state["players"]
    for seat, amount in payouts.items():
        players[seat]["stack"] += amount
        hand = next((h["name"] for h in result["hands"] if h["seat"] == seat), None)
        _log(state, f"{players[seat]['name']} wins {amount}" + (f" with {hand}" if hand else ""))
    result["payouts"] = [{"seat": s, "amount": a} for s, a in sorted(payouts.items())]
    state.update(result=result, turn=None, turn_deadline=None, stage="showdown", next_hand_at=now + delay)
    for p in players:
        p["bet"] = 0
    alive = [p for p in players if p["stack"] > 0]
    if len(alive) == 1:
        state.update(stage="finished", winner=alive[0]["seat"], next_hand_at=None)
        _log(state, f"{alive[0]['name']} wins the game")


def public_view(state, user_id, now):
    me = seat_of(state, user_id)
    result = state["result"]
    revealed = set(result["revealed"]) if result else set()
    players = []
    for p in state["players"]:
        if p["seat"] == me:
            cards = p["cards"]
        elif p["folded"] or not p["cards"]:
            cards = []
        elif p["seat"] in revealed:
            cards = p["cards"]
        else:
            cards = ["XX", "XX"]
        players.append({
            "seat": p["seat"], "name": p["name"], "stack": p["stack"], "bet": p["bet"],
            "folded": p["folded"], "all_in": p["all_in"], "busted": p["busted"],
            "last": p["last"], "cards": cards,
        })
    my_hand = None
    if me is not None and len(state["board"]) >= 3 and not state["players"][me]["folded"] and state["players"][me]["cards"]:
        score = _evaluator.evaluate([Card.new(c)for c in state["players"][me]["cards"]], [Card.new(c) for c in state["board"]])
        my_hand = _evaluator.class_to_string(_evaluator.get_rank_class(score))
    nxt_sb, nxt_bb = blinds_for(max(1, state["hand_no"]) + HANDS_PER_LEVEL - ((max(1, state["hand_no"]) - 1) % HANDS_PER_LEVEL))
    return {
        "stage": state["stage"], "hand_no": state["hand_no"], "sb": state["sb"], "bb": state["bb"],
        "next_blinds": [nxt_sb, nxt_bb],
        "hands_to_level_up": HANDS_PER_LEVEL - ((max(1, state["hand_no"]) - 1) % HANDS_PER_LEVEL),
        "pot": _pot(state), "board": state["board"], "dealer": state["dealer"],
        "sb_seat": state["sb_seat"], "bb_seat": state["bb_seat"], "turn": state["turn"],
        "turn_left": None if state["turn_deadline"] is None else max(0.0, state["turn_deadline"] - now),
        "turn_seconds": TURN_SECONDS,
        "next_hand_in": None if state["next_hand_at"] is None else max(0.0, state["next_hand_at"] - now),
        "me": me, "players": players, "legal": legal_actions(state, me), "result": result,
        "winner": state["winner"], "my_hand": my_hand, "log": state["log"][-14:],
    }
