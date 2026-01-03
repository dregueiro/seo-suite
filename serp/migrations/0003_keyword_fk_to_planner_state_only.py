# serp/migrations/0003_keyword_fk_to_planner_state_only.py
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("serp", "0002_serprun_cache_expires_at_serprun_cache_key_and_more"),
        ("planner", "0002_keyword_state"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name="serpresult",
                    name="keyword",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="serp_results",
                        to="planner.keyword",
                    ),
                ),
                migrations.AlterField(
                    model_name="serpkeywordsnapshot",
                    name="keyword",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="snapshots",
                        to="planner.keyword",
                    ),
                ),
            ],
        ),
    ]
