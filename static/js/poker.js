(() => {
  "use strict";
  const root = document.getElementById("game");
  if (!root) return;

  const ROOM = root.dataset.room;
  const AVATAR = root.dataset.avatar;
  const POS = ["bottom", "left", "top", "right"];
  const SUIT = { s: "♠", h: "♥", d: "♦", c: "♣" };
  const STAGE = { preflop: "Pre-flop", flop: "Flop", turn: "Turn", river: "River" };
  const $ = (id) => document.getElementById(id);
  const fmt = (n) => Number(n).toLocaleString("en-US");

  const wsUrl = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/game/${ROOM}/`;
  let socket = null, retry = 0;
  let state = null, legal = {};
  let turnEndsAt = null, nextHandAt = null;
  const lastSent = { timeout: 0, next: 0 };
  let prevHand = 0, prevBoardLen = 0, raiseKey = "";
  let activeTimer = null, finalShown = false, toastTimer = null;

  const btn = {
    fold: $("btn-fold"), call: $("btn-call"), raise: $("btn-raise"),
    range: $("raise-range"), input: $("raise-input"),
    presets: [...document.querySelectorAll("[data-preset]")],
  };

  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function cardEl(code, cls = "", delay = 0) {
    let node;
    if (code === "XX") {
      node = el("div", "pc back " + cls);
    } else {
      const rank = code[0] === "T" ? "10" : code[0];
      const suit = code[1];
      node = el("div", `pc ${suit === "h" || suit === "d" ? "red" : "black"} ${cls}`);
      const corner = (pos) => {
        const c = el("span", "c " + pos);
        c.append(el("b", null, rank), el("i", null, SUIT[suit]));
        return c;
      };
      node.append(corner("tl"), el("span", "pip", SUIT[suit]), corner("br"));
    }
    node.style.setProperty("--d", delay + "s");
    return node;
  }

  function toast(message) {
    const t = $("toast");
    t.textContent = message;
    t.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove("show"), 2600);
  }

  function setConn(up) {
    $("conn").classList.toggle("down", !up);
    $("conn-text").textContent = up ? "Live" : "Reconnecting…";
  }

  function send(payload) {
    if (socket && socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify(payload));
  }

  function connect() {
    socket = new WebSocket(wsUrl);
    socket.onopen = () => { retry = 0; setConn(true); };
    socket.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === "state") onState(msg.state);
      else if (msg.type === "error") { toast(msg.message); if (state) render(); }
    };
    socket.onclose = (e) => {
      setConn(false);
      if (e.code === 4403) { window.location.href = root.dataset.lobby; return; } // not allowed at this table
      setTimeout(connect, Math.min(1000 * ++retry, 5000));
    };
  }

  function onState(s) {
    state = s;
    legal = s.legal || {};
    const now = performance.now();
    turnEndsAt = s.turn_left == null ? null : now + s.turn_left * 1000;
    nextHandAt = s.next_hand_in == null ? null : now + s.next_hand_in * 1000;
    render();
  }

  function render() {
    const s = state;
    const newHand = s.hand_no !== prevHand;
    $("hand-label").textContent = `Hand #${s.hand_no}`;
    $("blinds-label").textContent = `Blinds ${fmt(s.sb)}/${fmt(s.bb)}`;
    $("pot-amount").textContent = fmt(s.pot);

    renderBoard(s, newHand);
    renderSeats(s, newHand);
    renderBets(s);
    renderBanner(s);
    renderActions(s);
    renderSide(s);
    prevHand = s.hand_no;
    prevBoardLen = s.board.length;
    maybeShowFinal(s);
  }

  function renderBoard(s, newHand) {
    const board = $("board");
    board.replaceChildren();
    for (let i = 0; i < 5; i++) {
      const code = s.board[i];
      if (!code) { board.append(el("div", "bslot")); continue; }
      const fresh = !newHand && i >= prevBoardLen;
      board.append(cardEl(code, fresh ? "deal" : "", fresh ? (i - prevBoardLen) * 0.14 : 0));
    }
  }

  function renderSeats(s, newHand) {
    const seats = $("seats");
    seats.replaceChildren();
    activeTimer = null;
    const n = s.players.length;
    const me = s.me ?? 0;
    const over = s.stage === "showdown" || s.stage === "finished";
    const won = new Map(over && s.result ? s.result.payouts.map((x) => [x.seat, x.amount]) : []);

    s.players.forEach((p) => {
      const seat = el("div", `seat pos-${POS[(p.seat - me + n) % n]}`);
      if (p.seat === s.me) seat.classList.add("me");
      if (p.busted) seat.classList.add("busted");
      else if (p.folded) seat.classList.add("folded");
      if (s.turn === p.seat) seat.classList.add("turn");
      if (won.has(p.seat)) seat.classList.add("winner");

      const hand = el("div", "hand");
      p.cards.forEach((c, i) => hand.append(cardEl(c, newHand ? "deal" : "", i * 0.12 + p.seat * 0.06)));

      const plate = el("div", "plate");
      const ava = el("div", "ava");
      const img = el("img");
      img.src = AVATAR;
      img.alt = "";
      ava.append(img);

      const who = el("div", "who");
      const stack = el("p", "stack");
      stack.append(el("i", "chip sm"), document.createTextNode(fmt(p.stack)));
      who.append(el("p", "name", p.seat === s.me ? `${p.name} (you)` : p.name), stack);

      plate.append(ava, who);

      if (!p.busted) {
        const badges = el("div", "badges");
        if (s.dealer === p.seat) badges.append(el("i", "badge d", "D"));
        if (s.sb_seat === p.seat) badges.append(el("i", "badge sb", "SB"));
        if (s.bb_seat === p.seat) badges.append(el("i", "badge bb", "BB"));
        if (badges.children.length) plate.append(badges);
      }

      const lastText = won.has(p.seat) ? `+${fmt(won.get(p.seat))}` : (p.busted ? "Out" : p.last);
      if (lastText) plate.append(el("span", "last", lastText));

      const timer = el("div", "timer");
      const fill = el("i");
      timer.append(fill);
      plate.append(timer);
      if (s.turn === p.seat) activeTimer = fill;

      seat.append(hand, plate);
      seats.append(seat);
    });
  }

  function renderBets(s) {
    const bets = $("bets");
    bets.replaceChildren();
    const n = s.players.length;
    const me = s.me ?? 0;
    s.players.forEach((p) => {
      if (p.bet <= 0) return;
      const bet = el("div", `bet pos-${POS[(p.seat - me + n) % n]}`);
      bet.append(el("i", "chip sm"), document.createTextNode(fmt(p.bet)));
      bets.append(bet);
    });
  }

  function renderBanner(s) {
    const banner = $("banner");
    banner.className = "banner";
    banner.replaceChildren();
    const line = (cls, text, id) => {
      const p = el("p", cls, text);
      if (id) p.id = id;
      banner.append(p);
    };

    if ((s.stage === "showdown" || s.stage === "finished") && s.result) {
      banner.classList.add("win");
      s.result.payouts.forEach((x, i) => {
        const name = s.players[x.seat].name;
        const hand = (s.result.hands.find((h) => h.seat === x.seat) || {}).name;
        const text = `${name} wins ${fmt(x.amount)}`;
        if (i === 0) line("b-main", text);
        else line("b-sub", text + (hand ? ` · ${hand}` : ""));
        if (i === 0) line("b-sub", hand ? hand : "Everyone else folded");
      });
      if (s.stage === "showdown") line("b-sub", "", "next-hand-text");
    } else if (s.turn != null) {
      line("b-main", s.turn === s.me ? "Your turn" : `${s.players[s.turn].name}'s turn`);
      line("b-sub", STAGE[s.stage] || "");
    } else {
      line("b-main", "Dealing…");
    }
  }

  function renderActions(s) {
    const mine = !!legal.is_my_turn;
    $("actions").classList.toggle("mine", mine);
    $("act-hint").textContent = mine
      ? "Your turn. Choose what to do"
      : s.turn != null ? `Waiting for ${s.players[s.turn].name}…`
      : s.stage === "finished" ? "The game is over" : "Next hand is about to start";

    btn.fold.disabled = !mine;
    btn.call.disabled = !mine;
    btn.call.textContent = !mine ? "Check"
      : legal.can_check ? "Check"
      : legal.call_is_allin ? `All-in ${fmt(legal.call_amount)}` : `Call ${fmt(legal.call_amount)}`;

    const canRaise = mine && legal.can_raise;
    [btn.range, btn.input, btn.raise, ...btn.presets].forEach((x) => { x.disabled = !canRaise; });
    if (canRaise) {
      btn.range.min = btn.input.min = legal.min_raise_to;
      btn.range.max = btn.input.max = legal.max_raise_to;
      const key = [s.hand_no, s.stage, s.turn, legal.min_raise_to, legal.max_raise_to].join("|");
      if (key !== raiseKey) { raiseKey = key; setRaise(legal.min_raise_to); }
      else updateRaiseLabel(raiseValue());
    } else {
      raiseKey = "";
      btn.raise.textContent = "Raise";
    }
  }

  function renderSide(s) {
    $("side-blinds").textContent = `Blinds: ${fmt(s.sb)} / ${fmt(s.bb)}`;
    $("side-next").textContent = `They go up to ${fmt(s.next_blinds[0])} / ${fmt(s.next_blinds[1])} in ${s.hands_to_level_up} ${s.hands_to_level_up === 1 ? "hand" : "hands"}.`;

    const log = $("log");
    log.replaceChildren(...s.log.map((t) => el("li", null, t)));
    log.scrollTop = log.scrollHeight;

    const mh = $("my-hand");
    mh.replaceChildren();
    if (s.my_hand) mh.append(document.createTextNode("Your hand: "), el("b", null, s.my_hand));
  }

  function maybeShowFinal(s) {
    if (s.stage !== "finished" || finalShown) return;
    finalShown = true;
    setTimeout(() => {
      const winner = s.winner != null ? s.players[s.winner] : null;
      const iWon = winner && s.winner === s.me;
      $("final-title").textContent = iWon ? "You won the game!" : "Game over";
      $("final-text").textContent = winner
        ? (iWon ? "You collected all the chips. Well played." : `${winner.name} collected all the chips.`)
        : "The game has ended.";
      $("final").hidden = false;
    }, 3200);
  }

  function clampRaise(v) {
    const lo = Number(legal.min_raise_to), hi = Number(legal.max_raise_to);
    if (!Number.isFinite(v)) v = lo;
    return Math.max(lo, Math.min(hi, Math.round(v)));
  }
  const raiseValue = () => clampRaise(Number(btn.input.value));

  function updateRaiseLabel(v) {
    btn.raise.textContent = v >= legal.max_raise_to
      ? `All-in ${fmt(v)}`
      : `${legal.raise_label} to ${fmt(v)}`;
  }

  function setRaise(v) {
    v = clampRaise(v);
    btn.range.value = v;
    btn.input.value = v;
    updateRaiseLabel(v);
  }

  btn.range.addEventListener("input", () => setRaise(Number(btn.range.value)));
  btn.input.addEventListener("input", () => {
    const v = raiseValue();
    btn.range.value = v;
    updateRaiseLabel(v);
  });
  btn.input.addEventListener("change", () => setRaise(Number(btn.input.value)));

  btn.presets.forEach((b) => b.addEventListener("click", () => {
    const afterCall = legal.pot + legal.to_call;
    const target = {
      min: legal.min_raise_to,
      half: legal.current_bet + Math.round(afterCall / 2),
      pot: legal.current_bet + afterCall,
      max: legal.max_raise_to,
    }[b.dataset.preset];
    setRaise(target);
  }));

  function lockButtons() {
    [btn.fold, btn.call, btn.raise].forEach((b) => { b.disabled = true; });
  }
  btn.fold.addEventListener("click", () => { lockButtons(); send({ type: "action", action: "fold" }); });
  btn.call.addEventListener("click", () => { lockButtons(); send({ type: "action", action: legal.can_check ? "check" : "call" }); });
  btn.raise.addEventListener("click", () => { lockButtons(); send({ type: "action", action: "raise", amount: raiseValue() }); });

  $("leave-form").addEventListener("submit", (e) => {
    if (!confirm("Leave the game? Your seat will keep folding automatically.")) e.preventDefault();
  });

  setInterval(() => {
    if (!state) return;
    const now = performance.now();

    if (activeTimer && turnEndsAt != null) {
      const left = (turnEndsAt - now) / 1000;
      activeTimer.style.width = Math.max(0, Math.min(1, left / state.turn_seconds)) * 100 + "%";
      activeTimer.parentElement.classList.toggle("urgent", left < 8);

      if (left < -0.3 && now - lastSent.timeout > 1500) { lastSent.timeout = now; send({ type: "timeout" }); }
    }

    if (state.stage === "showdown" && nextHandAt != null) {
      const left = (nextHandAt - now) / 1000;
      const label = $("next-hand-text");
      if (label) label.textContent = left > 0 ? `Next hand in ${Math.ceil(left)}…` : "Dealing…";
      if (left < 0.1 && now - lastSent.next > 1500) { lastSent.next = now; send({ type: "next_hand" }); }
    }
  }, 150);

  connect();
})();