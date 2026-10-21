from __future__ import annotations

import enum


class AccountType(str, enum.Enum):
    CHECKING = "checking"
    SAVINGS = "savings"
    CASH = "cash"
    OTHER = "other"


class CategoryType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"


class TransactionType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"
    REFUND = "refund"
    ADJUSTMENT_INCREASE = "adjustment_increase"
    ADJUSTMENT_DECREASE = "adjustment_decrease"


class GoalStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class RecurringFrequency(str, enum.Enum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class OccurrenceStatus(str, enum.Enum):
    PENDING = "pending"
    POSTED = "posted"
    SKIPPED = "skipped"


class BudgetPeriodType(str, enum.Enum):
    MONTHLY = "monthly"


class ExpenseNature(str, enum.Enum):
    FIXED = "fixed"
    VARIABLE = "variable"
    MIXED = "mixed"


class AuditAction(str, enum.Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    RESTORE = "restore"
    IMPORT = "import"


class LedgerEntryKind(str, enum.Enum):
    TRANSACTION = "transaction"
    TRANSFER = "transfer"
