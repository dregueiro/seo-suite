from django.db import models

# Create your models here.
from django.db import models


class Client(models.Model):
    name = models.CharField(max_length=200, unique=True)
    notes = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name
