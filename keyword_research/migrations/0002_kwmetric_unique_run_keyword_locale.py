from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("keyword_research", "0001_initial"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="keywordmetric",
            constraint=models.UniqueConstraint(
                fields=("run", "keyword", "locale"),
                name="uniq_kwmetric_run_keyword_locale",
            ),
        ),
    ]
