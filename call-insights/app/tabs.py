"""Endpoints for the Summary boxes as their own tabs (Neil, 16 Oct review): each lists every item in its category,
grouped by signal, and takes the filter bar (program, stage, payer, specialty pharmacy, period)."""
from fastapi import APIRouter, Depends, HTTPException

from app import engines
from app.analytics import Filters
from app.cache import cached
from app.dashboard import _base, filters, get_data
from app.engines import capped

router = APIRouter(prefix="/v1")


@router.get("/dashboard/stuck")
@cached
@capped
def stuck(f: Filters = Depends(filters)):
    d = get_data(f)
    return {**_base(d), **engines.stuck(d)}


@router.get("/dashboard/access-issues")
@cached
@capped
def access_issues(f: Filters = Depends(filters)):
    d = get_data(f)
    return {**_base(d), **engines.issues_page(d)}


@router.get("/dashboard/access-issues/{key}")
@cached
@capped
def access_issue(key: str, f: Filters = Depends(filters)):
    d = get_data(f)
    row = engines.issue_detail(d, key)
    if not row:
        raise HTTPException(status_code=404, detail="Issue not heard in this period")
    return {**_base(d), **row}


@router.get("/dashboard/at-risk")
@cached
@capped
def at_risk(f: Filters = Depends(filters)):
    d = get_data(f)
    return {**_base(d), **engines.risk_page(d)}


@router.get("/dashboard/call-summary")
@cached
@capped
def call_summary(direction: str | None = None, party: str | None = None, f: Filters = Depends(filters)):
    d = get_data(f)
    return {**_base(d), **engines.call_summary(d, (direction or "").lower() or None, party or None)}
