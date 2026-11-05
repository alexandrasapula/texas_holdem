from django.db import models


class Game(models.Model):
    room = models.OneToOneField("lobby.Room", on_delete=models.CASCADE, related_name="game")
    state = models.JSONField(default=dict)
    update_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Game in {self.room}"
