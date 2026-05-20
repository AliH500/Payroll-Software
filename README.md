# Payroll Software

Multi-tenant payroll for an import/export firm with operations in Pakistan (PKR) and Ethiopia (ETB).
Browser-based, Django + Postgres, with company-admin and employee-self-service portals.

- **Status:** V1 complete (employee self-service, expiry alerts, CI guards, Postgres RLS).
- **Target completion:** End of August 2026, actively used by the client.
- **Owner:** Ali Hani (solo).

## Stack

- Django 5.2 LTS, Python 3.12 (pinned via `uv`).
- Postgres 16. `psycopg[binary]`.
- HTMX + Tailwind. No Node.js in production (Tailwind via CDN in dev; standalone CLI in prod).
- Argon2 password hashing + `django-axes` rate-limiting.
- Field-level encryption (Fernet, `MultiFernet` rotation) for PII identifiers and salary values.

## Multi-tenant defense (three layers)

1. `TenantManager` — default queryset auto-filters by the request's tenant ContextVar.
2. CI guards — AST scanners fail the build on `<PIIModel>.all_tenants` without an inline
   `# tenant-bypass-allowed: <reason>` marker, and on `logger.*` / `print(...)` calls that
   reference forbidden salary or PII field names.
3. Postgres RLS — policies enforce `company_id = current_setting('app.current_tenant_id')`
   on every PII table. `TenantResolutionMiddleware` sets the GUC per request.

## Dev setup

```sh
podman run -d --name payroll-postgres -p 5432:5432 \
    -e POSTGRES_USER=payroll -e POSTGRES_PASSWORD=payroll -e POSTGRES_DB=payroll \
    postgres:16

# One-time: create the non-superuser app role and re-own public objects to it
# (RLS is bypassed by superusers, so the app must connect as a demoted role).
POSTGRES_USER=payroll uv run python manage.py bootstrap_rls_role

# Subsequent runs use payroll_app (set in .env).
uv run python manage.py migrate
uv run python manage.py seed_demo
uv run python manage.py runserver
```

## Demo accounts (after `seed_demo`)

| Role                  | URL                          | Email                  | Password               |
|-----------------------|------------------------------|------------------------|------------------------|
| Super-admin           | http://localhost:8000        | ali@platform.local     | demo-platform-2026     |
| Acme admin (PKR)      | http://acme.localhost:8000   | alice@acme.local       | demo-acme-2026         |
| Acme employee (PKR)   | http://acme.localhost:8000   | mira@acme.local        | demo-employee-2026     |
| Beta admin (ETB)      | http://beta.localhost:8000   | bob@beta.local         | demo-beta-2026         |
| Beta employee (ETB)   | http://beta.localhost:8000   | tigist@beta.local      | demo-employee-2026     |

## Quality checks

```sh
uv run pytest             # 93 tests, including CI guards and RLS isolation
uv run ruff check .
uv run mypy services/ domain/
```

See `docs/SCOPE.md` for the V1 capability list and the production deployment plan.
