from django.contrib import admin
from .models import Client

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "gsc_website_link",
        "google_analytics_id",
        "gads_login_customer_id",
        "country",
        "region",
        "city",
        "updated_at",
    )
    search_fields = (
        "name",
        "gsc_website_link",
        "google_analytics_id",
        "gads_login_customer_id",
    )
    list_filter = ("country", "region")

    def has_add_permission(self, request):
        if Client.objects.exists():
            return False
        return super().has_add_permission(request)
