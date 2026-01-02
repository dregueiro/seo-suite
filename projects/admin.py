from django.contrib import admin

from projects.models import Client, Project, Keyword, ProjectCompetitor


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_at")
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "domain", "client", "is_active", "created_at")
    list_filter = ("is_active", "device", "country", "language")
    search_fields = ("name", "domain")
    ordering = ("-created_at",)


@admin.register(Keyword)
class KeywordAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "keyword", "status", "priority", "created_at")
    list_filter = ("status", "priority")
    search_fields = ("keyword",)
    ordering = ("-created_at",)


@admin.register(ProjectCompetitor)
class ProjectCompetitorAdmin(admin.ModelAdmin):
    list_display = ("project", "competitor_domain")
    search_fields = ("competitor_domain",)
    ordering = ("project_id",)
