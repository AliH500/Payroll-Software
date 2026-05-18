# Payroll Software — Scope

Browser-based, multi-tenant payroll software built for a real import/export client with operations in Pakistan and Ethiopia. Solo development project; production target end of August 2026.

## What It Does

A web app that lets HR payroll admins:

- Provision multiple companies under a single platform (super-admin role)
- Manage employee records, including labour-specific fields like visa and passport expiry
- Run monthly payroll across mixed pay bases — fixed salary, hourly, or unit-based
- Generate and distribute payslips (PDF, email, and in-app view)
- Track attendance with policies that vary by staff type (timed check-in, hour-based, unit-based)
- Handle leave, bonuses, expense reimbursements, and statutory deductions
- Give employees a self-service portal to view their payslips and salary history

## Status

**Planning → scaffolding** (May 2026). Tech stack locked; entity model drafted; v1 implementation in progress.

## Tech Stack

- **Backend:** Django (Python)
- **Frontend:** Django templates + HTMX + Tailwind CSS (no separate JS toolchain or Node runtime)
- **Database:** PostgreSQL with single-DB multi-tenancy (`tenant_id` column on every multi-tenant table)
- **Background jobs:** Django-Q2 (Postgres as broker — no Redis required)
- **Authentication:** Django built-in auth with Argon2 password hashing; `django-axes` for login rate-limiting
- **Object storage:** Backblaze B2 (payslip PDFs, CSV exports)
- **Transactional email:** AWS SES (payslip delivery, password reset, expiry alerts)
- **Tooling:** `uv`, `ruff`, `pytest` + `pytest-django`, `mypy`
- **Hosting:** Render (managed web + Postgres)

## Multi-Tenancy & Data Isolation

The platform serves multiple companies from a single application instance. Cross-tenant data isolation is treated as a hard requirement and enforced by three layers:

1. **Default `TenantManager`** on every multi-tenant model. Every queryset is auto-scoped to the current tenant. Tenant is resolved from the request context via middleware.
2. **CI guard.** An automated test scans for queries on PII-sensitive models (Employee, Salary, Payslip, Bonus, Deduction, AuditLogEntry) that bypass the TenantManager. The build fails on violations.
3. **Postgres Row-Level Security (RLS).** Defense in depth on the most sensitive tables (salary, passport, visa, bank account).

## Security & Data Handling

- **Field-level encryption at rest** on sensitive PII: national ID, passport, visa, bank account, salary, and all salary-derived figures (deductions, bonuses, reimbursements, net pay, payslip line items).
- **Logging policy:** salary figures and salary-derived figures are never written to logs, error messages, traces, or any output channel. A logging filter masks sensitive keys; model `__repr__` redacts amount fields; CI scans for logger and print calls referencing forbidden field names.
- **Password storage:** Argon2 (OWASP current standard).
- **Backups:** managed daily backups via Render Postgres + weekly `pg_dump` → Backblaze B2 as a second copy.

## MVP Scope (V1)

- Super-admin creates multiple companies
- CSV bulk import of employee data per company
- Add and remove employees
- Run payroll calculations
- View and download all payslips in one click
- Role assignment (company admin and others)
- Employee self-service portal (salary calculation + payment history)
- Password reset flow (email-based)
- Notification panel for visa / passport expiry (nice-to-have)

## Out of Scope (V1)

- Tax calculation rules (rule-driven framework exists; no rules ship in v1)
- 2FA (planned for v1.1)
- Contractor / 1099-style pay flows
- Accounting integrations beyond CSV
- Compliance filings and year-end statements

## Architecture

Single Django monolith. Internal organisation by Django apps:

- `accounts/` — auth, roles, permissions, password reset
- `tenants/` — Company model, tenant resolution middleware, TenantManager
- `employees/` — Employee, Contractor, Intern variants and PII storage
- `attendance/` — AttendancePolicy, AttendanceRecord (timed / hourly / unit-based)
- `payroll/` — PayPeriod, Payslip, PaymentInstruction, calculation services
- `compensation/` — Deduction, Bonus, ExpenseReimbursement
- `tax/` — TaxRule engine (no rules in v1)
- `audit/` — per-company AuditLogEntry
- `notifications/` — Django-Q2 jobs for emails and expiry alerts

## Currencies

PKR (Pakistan) and Birr (Ethiopia). Each company is bound to a single currency.

## Roadmap

- **Q2 2026 (current):** scaffolding, core entity model, tenant resolution, super-admin company-provisioning flow
- **Q3 2026:** payroll calculation engine, payslip generation, employee self-service portal, password reset, deployment to production
- **By end of August 2026:** v1 actively used by the client company

## Background

This is the developer's first real-client engagement — built solo for an import/export firm with employees in Pakistan and Ethiopia. The detailed design decisions and project brief are tracked privately; this scope doc is the public-facing summary.
