from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from apps.accounts.models import Role
from apps.compensation.forms import BonusForm, DeductionForm, ReimbursementForm
from apps.compensation.models import Bonus, Deduction, ExpenseReimbursement


def _require_tenant(request: HttpRequest) -> None:
    if getattr(request, "tenant", None) is None:
        raise PermissionDenied("Tenant subdomain required.")
    if request.user.is_authenticated and request.user.role == Role.EMPLOYEE:
        raise PermissionDenied("Employee self-service is not allowed here.")


@login_required
def compensation_list(request: HttpRequest) -> HttpResponse:
    _require_tenant(request)
    bonuses = list(Bonus.objects.select_related("employee", "period"))
    deductions = list(Deduction.objects.select_related("employee", "period"))
    reimbursements = list(ExpenseReimbursement.objects.select_related("employee", "period"))
    return render(request, "compensation/list.html", {
        "bonuses": bonuses,
        "deductions": deductions,
        "reimbursements": reimbursements,
    })


@login_required
def compensation_create(request: HttpRequest, kind: str) -> HttpResponse:
    _require_tenant(request)
    form_class = {
        "bonus": BonusForm,
        "deduction": DeductionForm,
        "reimbursement": ReimbursementForm,
    }.get(kind)
    if form_class is None:
        raise PermissionDenied("Unknown compensation type.")
    if request.method == "POST":
        form = form_class(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.company = request.tenant
            obj.save()
            messages.success(request, f"Added {kind}.")
            return redirect("compensation:list")
    else:
        form = form_class(tenant=request.tenant)
    return render(request, "compensation/form.html", {"form": form, "kind": kind})
