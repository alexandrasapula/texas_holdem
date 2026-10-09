from django.urls import path
from . import views


app_name = "lobby"
urlpatterns = [
    path("", views.lobby_view, name="lobby"),
    path("api/rooms/", views.rooms_api, name="rooms_api"),
    path("rooms/create/", views.create_room_view, name="create"),
    path("rooms/leave/", views.leave_room_view, name="leave"),
    path("rooms/<int:pk>/", views.room_view, name="room"),
    path("rooms/<int:pk>/join/", views.join_room_view, name="join"),
    path("rooms/<int:pk>/state/", views.room_state, name="room_state"),
    path("rooms/<int:pk>/game/", views.game_view, name="game"),
    path("logout/", views.logout_view, name="logout"),
]