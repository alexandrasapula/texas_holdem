(() => {
    const list = document.getElementById("rooms");
    if (!list) return;

    const apiUrl = list.dataset.api;
    const joinTemplate = list.dataset.joinUrl; // e.g. /lobby/rooms/0/join/
    const csrf = document.querySelector("[name=csrfmiddlewaretoken]").value;
    const counter = document.getElementById("rooms-count");

    function el(tag, cls, text) {
        const node = document.createElement(tag);
        if (cls) node.className = cls;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    function renderRoom(r) {
        const row = el("div", "room");

        const info = el("div");
        info.append(el("p", "room-name", r.name), el("p", "room-by", "by " + r.creator));

        const seats = el("div", "seats");
    for (let i = 0; i < r.max; i++) seats.append(el("i", "seat" + (i < r.players ? " on" : "")));
    seats.append(el("span", "seats-num", `${r.players}/${r.max}`));

    const form = el("form");
    form.method = "post";
    form.action = joinTemplate.replace("/0/", `/${r.id}/`);
    const token = el("input");
    token.type = "hidden";
    token.name = "csrfmiddlewaretoken";
    token.value = csrf;
    const btn = el("button", "btn btn-sm", "Join");
    btn.type = "submit";
    form.append(token, btn);

    row.append(info, seats, form);
    return row;
    }

    function render(rooms) {
        counter.textContent = rooms.length;
        if (!rooms.length) {
            const empty = el("div", "empty-state");
            empty.append(el("strong", null, "No open rooms yet"), el("span", null, "Create one and wait for friends to join."));
            list.replaceChildren(empty);
            return;
        }
        list.replaceChildren(...rooms.map(renderRoom));
    }

    async function refresh() {
        try {
          const res = await fetch(apiUrl, { credentials: "same-origin", headers: { Accept: "application/json" } });
          if (!res.ok) return;
          render((await res.json()).rooms);
        } catch (_) { /* network hiccup: try again on the next tick */ }
    }

    render(JSON.parse(document.getElementById("rooms-initial").textContent).rooms);
    setInterval(() => { if (!document.hidden) refresh(); }, 3000);
    document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
})();