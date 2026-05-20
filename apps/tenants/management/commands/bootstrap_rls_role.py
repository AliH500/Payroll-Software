"""Create the non-superuser `payroll_app` role and reown public objects to it.

RLS only applies to non-superuser, non-bypassrls roles. The default Postgres
container starts with a superuser bootstrap account, so the application must
connect as a separate, demoted role for RLS to actually enforce anything.

Run this once after bringing up a new dev DB, using the bootstrap superuser:

    POSTGRES_USER=payroll \\
        uv run python manage.py bootstrap_rls_role --app-user payroll_app

Subsequent `migrate`, `runserver`, and `seed_demo` runs use the demoted role
(set `POSTGRES_USER=payroll_app` in `.env`).
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Create and prep the non-superuser application role for RLS enforcement."

    def add_arguments(self, parser):  # type: ignore[no-untyped-def]
        parser.add_argument("--app-user", default="payroll_app")
        parser.add_argument("--app-password", default="payroll_app")

    def handle(self, *args: object, **options: object) -> None:
        app_user = str(options["app_user"])
        app_password = str(options["app_password"])

        with connection.cursor() as cursor:
            cursor.execute("SELECT current_user")
            current = cursor.fetchone()[0]
            cursor.execute(
                "SELECT rolsuper FROM pg_roles WHERE rolname = current_user"
            )
            row = cursor.fetchone()
            if not row or not row[0]:
                raise CommandError(
                    "bootstrap_rls_role must be run as a Postgres superuser. "
                    f"Current role '{current}' is not a superuser."
                )

            cursor.execute(
                "SELECT 1 FROM pg_roles WHERE rolname = %s", [app_user]
            )
            exists = cursor.fetchone() is not None
            if not exists:
                # `app_user` is a Django setting / argparse value, not user input;
                # SQL identifier-injection is not a meaningful risk here.
                cursor.execute(
                    f"CREATE ROLE {app_user} LOGIN PASSWORD %s "
                    "NOSUPERUSER NOBYPASSRLS CREATEDB",
                    [app_password],
                )
                self.stdout.write(self.style.SUCCESS(f"Created role {app_user}."))
            else:
                cursor.execute(
                    f"ALTER ROLE {app_user} NOSUPERUSER NOBYPASSRLS CREATEDB"
                )
                self.stdout.write(
                    f"Role {app_user} exists; ensured NOSUPERUSER NOBYPASSRLS CREATEDB."
                )

            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {app_user}")
            cursor.execute(f"ALTER SCHEMA public OWNER TO {app_user}")
            cursor.execute(
                "GRANT SELECT, INSERT, UPDATE, DELETE "
                f"ON ALL TABLES IN SCHEMA public TO {app_user}"
            )
            cursor.execute(
                f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {app_user}"
            )
            cursor.execute(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {app_user}"
            )
            cursor.execute(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                f"GRANT USAGE, SELECT ON SEQUENCES TO {app_user}"
            )

            # Transfer ownership of current tables and sequences so future
            # migrations executed as `app_user` can ALTER them.
            # app_user comes from argparse defaults, not user input.
            cursor.execute(
                "DO $$ "  # noqa: S608
                "DECLARE r RECORD; "
                "BEGIN "
                "FOR r IN SELECT tablename FROM pg_tables WHERE schemaname='public' LOOP "
                "  EXECUTE 'ALTER TABLE public.' || quote_ident(r.tablename) "
                f"          || ' OWNER TO {app_user}'; "
                "END LOOP; "
                "FOR r IN SELECT sequence_name FROM information_schema.sequences "
                "         WHERE sequence_schema='public' LOOP "
                "  EXECUTE 'ALTER SEQUENCE public.' || quote_ident(r.sequence_name) "
                f"          || ' OWNER TO {app_user}'; "
                "END LOOP; "
                "END $$;"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Role {app_user} is ready. Set POSTGRES_USER={app_user} in .env."
            )
        )
