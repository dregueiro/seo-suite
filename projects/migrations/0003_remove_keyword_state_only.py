# projects/migrations/0003_remove_keyword_state_only.py
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0002_remove_project_google_ads_customer_id_and_more"),
        ("planner", "0002_keyword_state"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(name="Keyword"),
            ],
        ),
    ]
