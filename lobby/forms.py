from django import forms


class CreateRoomForm(forms.Form):
    name = forms.CharField(label="Room name", max_length=40, required=False, widget=forms.TextInput(attrs={"placeholder": "Option, e.g. Friday night",  "autocomplete": "off"}))
