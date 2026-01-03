from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("planner", "0002_keyword_state"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            # DB: crear índices con nombres cortos (si no existen)
            database_operations=[
                migrations.RunSQL(
                    sql=[
                        "CREATE INDEX IF NOT EXISTS pk_kw_pr_stat_idx ON projects_keyword(project_id, status);",
                        "CREATE INDEX IF NOT EXISTS pk_kw_kw_idx ON projects_keyword(keyword);",
                    ],
                    reverse_sql=[
                        "DROP INDEX IF EXISTS pk_kw_pr_stat_idx;",
                        "DROP INDEX IF EXISTS pk_kw_kw_idx;",
                    ],
                )
            ],
            # STATE: sacar índices “largos” del estado y poner los cortos
            state_operations=[
                migrations.RemoveIndex(model_name="keyword", name="projects_ke_project__a2f7a4_idx"),
                migrations.RemoveIndex(model_name="keyword", name="projects_ke_keyword_4d1c1b_idx"),
                migrations.AddIndex(
                    model_name="keyword",
                    index=models.Index(fields=["project", "status"], name="pk_kw_pr_stat_idx"),
                ),
                migrations.AddIndex(
                    model_name="keyword",
                    index=models.Index(fields=["keyword"], name="pk_kw_kw_idx"),
                ),
            ],
        ),
    ]
