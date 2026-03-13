from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from .models import Shop

@receiver(post_save, sender=User)
def create_user_shop(sender, instance, created, **kwargs):
    if created:
        Shop.objects.create(
            name=f"{instance.username}'s Shop",
            owner=instance
        )