from django.apps import apps
from django.core.management import BaseCommand, CommandError, call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


LOCK_KEY = 782_435_162_042


class Command(BaseCommand):
    help = "Inspect, verify, or apply release migrations on PostgreSQL."

    def add_arguments(self, parser):
        action = parser.add_mutually_exclusive_group()
        action.add_argument("--apply", action="store_true", help="Apply the reviewed migration plan.")
        action.add_argument("--verify", action="store_true", help="Fail on pending migrations or missing schema objects.")

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            raise CommandError("A PostgreSQL DATABASE_URL is required.")

        if options["verify"]:
            self.verify_schema()
            return
        if not options["apply"]:
            self.show_plan()
            return

        host = connection.settings_dict["HOST"]
        db_options = connection.settings_dict["OPTIONS"]
        if "-pooler." in host.lower() or db_options.get("pool"):
            raise CommandError("Use an unpooled PostgreSQL endpoint for --apply.")

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_try_advisory_lock(%s)", [LOCK_KEY])
                if not cursor.fetchone()[0]:
                    raise CommandError("Another release migration holds the database lock.")
                cursor.execute("SET lock_timeout = '5s'")
            self.show_plan()
            call_command("migrate", interactive=False, stdout=self.stdout)
            self.verify_schema()
        finally:
            # Closing the direct session also releases its advisory lock.
            connection.close()

    def show_plan(self):
        executor = MigrationExecutor(connection)
        executor.loader.check_consistent_history(connection)
        applied = executor.loader.applied_migrations
        with connection.cursor() as cursor:
            table = "store_product"
            columns = set()
            if table in connection.introspection.table_names(cursor):
                columns = {
                    column.name for column in connection.introspection.get_table_description(cursor, table)
                }
        for migration in ("0042_product_variant_sort_order", "0043_repair_product_variant_sort_order"):
            self.stdout.write(f"store.{migration[:4]} recorded: {('store', migration) in applied}")
        self.stdout.write(f"store_product.variant_sort_order present: {'variant_sort_order' in columns}")
        call_command("migrate", plan=True, interactive=False, stdout=self.stdout)

    def verify_schema(self):
        executor = MigrationExecutor(connection)
        executor.loader.check_consistent_history(connection)
        pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if pending:
            names = ", ".join(f"{migration.app_label}.{migration.name}" for migration, _ in pending)
            raise CommandError("Pending migrations: " + names)
        self.check_columns()

    def check_columns(self):
        missing = []
        with connection.cursor() as cursor:
            tables = set(connection.introspection.table_names(cursor))
            for model in apps.get_models(include_auto_created=True):
                if not model._meta.can_migrate(connection):
                    continue
                table = model._meta.db_table
                if table not in tables:
                    missing.append(table)
                    continue
                actual = {
                    column.name for column in connection.introspection.get_table_description(cursor, table)
                }
                expected = {field.column for field in model._meta.local_concrete_fields}
                missing.extend(f"{table}.{column}" for column in sorted(expected - actual))
        if missing:
            raise CommandError("Missing tables or columns: " + ", ".join(missing))
        self.stdout.write(self.style.SUCCESS("All managed tables and columns are present."))
