from .models import Client

def get_singleton_client() -> Client | None:
    return Client.objects.order_by("id").first()
