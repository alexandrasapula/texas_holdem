from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from .models import Room, RoomPlayer


class RoomError(Exception):
    pass


def purge_stale():
    cutoff = timezone.now() - timedelta(seconds=Room.STALE_AFTER)
    RoomPlayer.objects.filter(room__status=Room.Status.WAITING, last_seen__lt=cutoff).delete()
    Room.objects.filter(players__isnull=True).delete()


@transaction.atomic
def create_room(user, name):
    if RoomPlayer.objects.filter(user=user).exists():
        raise RoomError("You are already in a room. Leave it first")
    room = Room.objects.create(name=name, creator=user)
    RoomPlayer.objects.create(room=room, user=user)
    return room


@transaction.atomic
def join_room(user, room_id):
    room = Room.objects.select_for_update().filter(pk=room_id).first()
    if room is None:
        raise RoomError("This room no longer exists")
    if RoomPlayer.objects.filter(user=user, room=room).exists():
        return room
    if RoomPlayer.objects.filter(user=user).exists():
        raise RoomError("You are already in a room. Leave it first")
    if room.status != Room.Status.WAITING or room.players.count() >= Room.MAX_PLAYERS:
        raise RoomError("This room is already full")
    RoomPlayer.objects.create(room=room, user=user)
    if room.players.count() >= Room.MAX_PLAYERS:
        room.status = Room.Status.PLAYING
        room.save(update_fields=["status"])
    return room


@transaction.atomic
def leave_room(user):
    RoomPlayer.objects.filter(user=user).delete()
    Room.objects.filter(players__isnull=True).delete()
