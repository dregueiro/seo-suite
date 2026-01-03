# keyword_research/migrations/0002_keyword_state.py
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("planner", "0001_initial"),
        ("projects", "0002_remove_project_google_ads_customer_id_and_more"),
        ("geo", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="Keyword",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("keyword", models.CharField(max_length=255)),
                        ("city", models.CharField(blank=True, default="", max_length=120)),
                        ("device", models.CharField(blank=True, default="", max_length=10)),
                        ("target_url", models.URLField(blank=True, default="")),
                        ("intent", models.CharField(blank=True, default="", max_length=40)),
                        ("status", models.CharField(choices=[("active", "Active"), ("paused", "Paused")], default="active", max_length=10)),
                        ("priority", models.PositiveSmallIntegerField(default=3, help_text="1=low cost, 5=high priority")),
                        ("notes", models.TextField(blank=True, default="")),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        ("country", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="geo.country")),
                        ("language", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="geo.language")),
                        ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="keywords", to="projects.project")),
                    ],
                    options={
                        "db_table": "projects_keyword",
                        "ordering": ["project__client__name", "project__name", "keyword"],
                        "indexes": [
                            models.Index(fields=["project", "status"], name="projects_ke_project__a2f7a4_idx"),
                            models.Index(fields=["keyword"], name="projects_ke_keyword_4d1c1b_idx"),
                        ],
                        "constraints": [
                            models.UniqueConstraint(fields=["project", "keyword", "country", "city", "language", "device"], name="uniq_keyword_scope"),
                        ],
                    },
                ),
            ],
        ),
    ]
