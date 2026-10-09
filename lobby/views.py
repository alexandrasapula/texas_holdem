from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from . import services
from .forms import CreateRoomForm
from .models import Room, RoomPlayer
from .services import RoomError


def _room_redirect(room):
    if room.status == Room.Status.PLAYING:
        return redirect("lobby:game", pk=room.pk)
    return redirect("lobby:room", pk=room.pk)


def _rooms_payload():
    rooms = (
        Room.objects.filter(status=Room.Status.WAITING).select_related("creator").annotate(players_count=Count("players")).order_by("-created_at")
    )
    return [
        {"id": r.pk, "name": r.name, "creator": r.creator.username, "players": r.players_count, "max": Room.MAX_PLAYERS} 
        for r  in rooms
    ]


def _room_state(room, user):
    players = room.players.select_related("user").order_by("joined_at")
    return {
        "in_room": True,
        "name": room.name,
        "status": room.status,
        "max_players": Room.MAX_PLAYERS,
        "players": [{"username": p.user.username, "is_me": p.user_id == user.id,} for p in players],
        "game_url": reverse("lobby:game", args=[room.pk]) if room.status == Room.Status.PLAYING else None,
    }


@login_required
def lobby_view(request):
    services.purge_stale()
    membership = RoomPlayer.objects.filter(user=request.user).select_related("room").first()
    if membership:
        return _room_redirect(membership.room)
    return render(request, "lobby/lobby.html", {
        "form": CreateRoomForm(),
        "initial_rooms": {"rooms": _rooms_payload()},
        "max_players": Room.MAX_PLAYERS,
    })


@login_required
@require_GET
def rooms_api(request):
    services.purge_stale()
    return JsonResponse({"rooms": _rooms_payload()})


@login_required
@require_POST
def create_room_view(request):
    form = CreateRoomForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Room name must be 40 character or fewer")
        return redirect("lobby:lobby")
    name = form.cleaned_data["name"].strip() or f"{request.user.username}'s room"
    try:
        room = services.create_room(request.user, name)
    except RoomError as e:
        messages.error(request, str(e))
        return redirect("lobby:lobby")
    return redirect("lobby:room", pk=room.pk)


@login_required
@require_POST
def join_room_view(request, pk):
    services.purge_stale()
    try:
        room = services.join_room(request.user, pk)
    except RoomError as e:
        messages.error(request, str(e))
        return redirect("lobby:lobby")
    return _room_redirect(room)


@login_required
@require_POST
def leave_room_view(request):
    services.leave_room(request.user)
    return redirect("lobby:lobby")


@login_required
def room_view(request, pk):
    membership = RoomPlayer.objects.filter(user=request.user, room_id=pk).select_related("room").first()
    if membership is None:
        return redirect("lobby:lobby")
    room = membership.room
    if room.status == Room.Status.PLAYING:
        return redirect("lobby:game", pk=room.pk)
    return render(request, "lobby/room.html", {"room": room, "initial_state": _room_state(room, request.user)})


@login_required
@require_GET
def room_state(request, pk):
    RoomPlayer.objects.filter(user=request.user, room_id=pk).update(last_seen=timezone.now())
    services.purge_stale()
    membership = RoomPlayer.objects.filter(user=request.user, room_id=pk).select_related("room").first()
    if membership is None:
        return JsonResponse({"in_room": False})
    return JsonResponse(_room_state(membership.room, request.user))


@login_required
def game_view(request, pk):
    membership = RoomPlayer.objects.filter(user=request.user, room_id=pk).select_related("room").first()
    if membership is None:
        return redirect("lobby:lobby")
    room = membership.room
    if room.status != Room.Status.PLAYING:
        return redirect("lobby:room", pk=room.pk)
    return render(request, "lobby/game.html", {"room": room, "players": room.players.select_related("user")})


@login_required
@require_POST
def logout_view(request):
    services.leave_room(request.user)
    logout(request)
    return redirect("auth:auth")
