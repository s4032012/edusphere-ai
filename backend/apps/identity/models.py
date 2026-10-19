import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models

class Account(AbstractUser):
    """Global identity: school memberships are a separate scoped relation."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    display_name = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)

    def __str__(self):
        return self.display_name or self.username
