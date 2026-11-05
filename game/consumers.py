import time
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.db import IntegrityError, transaction
from lobby.models import RoomPlayer, Room
from . import engine
from .engine import GameError
from .models import Game


class GameConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.room_id = int(self.scope["url_route"]["kwargs"]["room_id"])
        self.user = self.scope["user"]
        self.group = f"game_{self.room_id}"
        self.joined_group = False
        if not self.user.is_authenticated or not await self._is_player():
            await self.close(code=4403)
            return
        await self.channel_layer.group_add(self.group, self.channel_name)
        self.joined_group = True
        await self.accept()
        await self._send_state(await self._load_or_create())
 
    async def disconnect(self, code):
        if self.joined_group:
            await self.channel_layer.group_discard(self.group, self.channel_name)
 
    async def receive_json(self, content, **kwargs):
        try:
            state = await self._apply(content)
        except GameError as e:
            await self.send_json({"type": "error", "message": str(e)})
            return
        if state is not None:
            await self.channel_layer.group_send(self.group, {"type": "game.update", "state": state})
 
    async def game_update(self, event):
        await self._send_state(event["state"])
 
    async def _send_state(self, state):
        view = engine.public_view(state, self.user.id, time.time())  # hides other players' cards
        await self.send_json({"type": "state", "state": view})
 
    @database_sync_to_async
    def _is_player(self):
        return RoomPlayer.objects.filter(
            room_id=self.room_id, user=self.user, room__status=Room.Status.PLAYING
        ).exists()
 
    @database_sync_to_async
    def _load_or_create(self):
        game = Game.objects.filter(room_id=self.room_id).first()
        if game is not None:
            return game.state
        with transaction.atomic():
            room = Room.objects.select_for_update().get(pk=self.room_id)
            users = [
                {"user_id": rp.user_id, "name": rp.user.username}
                for rp in room.players.select_related("user").order_by("joined_at")
            ]
            try:
                with transaction.atomic():
                    game = Game.objects.create(room=room, state=engine.new_game(users, time.time()))
            except IntegrityError:  # another player's connection created it a moment earlier
                game = Game.objects.get(room=room)
            return game.state
 
    @database_sync_to_async
    def _apply(self, msg):
        now = time.time()
        with transaction.atomic():
            game = Game.objects.select_for_update().get(room_id=self.room_id)
            state = game.state
            seat = engine.seat_of(state, self.user.id)
            if seat is None:
                raise GameError("You are not at this table")
            kind = msg.get("type")
            changed = False
            if kind == "action":
                engine.apply_action(state, seat, msg.get("action"), msg.get("amount"), now)
                changed = True
            elif kind == "timeout":
                changed = engine.handle_timeout(state, now)
            elif kind == "next_hand":
                changed = engine.maybe_next_hand(state, now)
            if changed:
                game.state = state
                game.save(update_fields=["state", "update_at"])
            return state if changed else None
