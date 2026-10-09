(() => {
    const root = document.getElementById("room");
    if (!root) return;

    const stateUrl = root.dataset.state;
    const lobbyUrl = root.dataset.lobby;
    const avatarUrl = root.dataset.avatar;
    const POLL_MS = 2000;

    const $ = (id) => document.getElementById(id);
    const slotsEl = $("slots"), progressEl = $("progress");
    let knownPlayers = null;
    let redirecting = false;

    function el(tag, cls, text) {
        const node = document.createElement(tag);
        if (cls) node.className = cls;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    function render(s) {
        $("room-name").textContent = s.name;
        $("count").textContent = s.players.length;
        $("max").textContent = s.max_players;
        progressEl.style.width = (s.players.length / s.max_players * 100) + "%";

        const missing = s.max_players - s.players.length;
        $("status-text").textContent = missing ? "Waiting for players" : "Table is full";
        $("hint").textContent = missing
            ? `${missing} more ${missing === 1 ? "player is" : "players are"} needed to start.`
            : "All seats are taken.";

        slotsEl.replaceChildren();
        for (let i = 0; i < s.max_players; i++) {
            const p = s.players[i];
            const slot = el("div", "slot" + (p ? "" : " empty") + (p && p.is_me ? " me" : ""));
            if (p && knownPlayers && !knownPlayers.has(p.username)) slot.classList.add("joined");
            const face = el("div", "face");
        if (p) {
        const img = el("img");
        img.src = avatarUrl;
        img.alt = "";
        face.append(img);
        }
        slot.append(
        face,
        el("p", "slot-name", p ? p.username : "Free seat"),
        el("p", "slot-tag", p && p.is_me ? "You" : "")
        );
            slotsEl.append(slot);
        }
        knownPlayers = new Set(s.players.map((p) => p.username));
    }

    function startCountdown(url) {
        redirecting = true;
        $("leave-form").hidden = true;
        $("countdown").hidden = false;
        let n = 3;
        $("countdown-num").textContent = n;
        const timer = setInterval(() => {
            n -= 1;
            if (n <= 0) { clearInterval(timer); window.location.href = url; return; }
            $("countdown-num").textContent = n;
        }, 1000);
    }

    async function poll() {
        try {
            const res = await fetch(stateUrl, { credentials: "same-origin", headers: { Accept: "application/json" } });
        if (res.ok) {
            const s = await res.json();
            if (!s.in_room) { window.location.href = lobbyUrl; return; } // kicked (inactive) or room was deleted
            render(s);
            if (s.status === "playing") { startCountdown(s.game_url); return; }
        }
        } catch (_) { /* ignore, retry */ }
        if (!redirecting) setTimeout(poll, POLL_MS);
    }

    render(JSON.parse($("room-initial").textContent));
  setTimeout(poll, POLL_MS);
})();