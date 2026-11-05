from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from lobby.models import Room, RoomPlayer


@login_required
def table_view(request, pk):
    membership = RoomPlayer.objects.filter(user=request.user, room_id=pk).select_related("room").first()
    if membership is None:
        return redirect("lobby:lobby")
    room = membership.room
    if room.status != Room.Status.PLAYING:
        return redirect("lobby:room", pk=room.pk)
    return render(request, "game/table.html", {"room": room})
