from django.db import models
from django.conf import settings


class Room(models.Model):
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="created_rooms", on_delete=models.CASCADE)
    guest = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="joined_rooms", null=True, blank=True, on_delete=models.SET_NULL)

    @property
    def is_open(self):
        return self.guest_id is None
