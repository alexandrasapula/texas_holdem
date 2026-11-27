import secrets
from allauth.account.adapter import DefaultAccountAdapter
from django.contrib.auth import get_user_model


class PlayerAccountAdapter(DefaultAccountAdapter):
    def generate_unique_username(self, txts, regex=None):
        User = get_user_model()
        while True:
            name = f"player{secrets.randbelow(100000):05d}"
            if not User.objects.filter(username=name).exists():
                return name
