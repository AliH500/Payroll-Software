"""Root conftest: relaxes Postgres RLS so the test suite can read any tenant's data.

Test code (factories, ORM setup, assertions) crosses tenant boundaries constantly
to set up isolated scenarios. Without this fixture, every `django_db`-marked test
would see empty querysets because the RLS policies block reads when no tenant GUC
is set. The super-admin bypass policy is the documented escape hatch.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _rls_super_admin_for_tests(request: pytest.FixtureRequest) -> None:
    """Mark the test DB connection as super-admin so RLS policies allow all reads.

    Only activates for tests that touch the database (i.e. opt in to the `db`
    or `transactional_db` fixture). Static-analysis tests skip this entirely.
    """
    if not {"db", "transactional_db"}.intersection(request.fixturenames):
        return
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT set_config('app.is_super_admin', 'true', false), "
            "set_config('app.current_tenant_id', '', false)"
        )
