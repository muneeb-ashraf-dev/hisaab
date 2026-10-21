from fastapi import APIRouter, Depends

from app.api.routes import (
    accounts,
    baseline,
    budgets,
    categories,
    dashboard,
    goals,
    imports,
    recurring,
    reports,
    system,
    transactions,
    transfers,
)
from app.core.security import require_auth

api_router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_auth)])
api_router.include_router(accounts.router)
api_router.include_router(categories.router)
api_router.include_router(transactions.router)
api_router.include_router(transfers.router)
api_router.include_router(budgets.router)
api_router.include_router(goals.router)
api_router.include_router(dashboard.router)
api_router.include_router(reports.router)
api_router.include_router(baseline.router)
api_router.include_router(recurring.router)
api_router.include_router(imports.router)
api_router.include_router(system.router)

__all__ = ["api_router"]
