from __future__ import annotations

import csv
import io
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError
from app.models.account import Account
from app.models.category import Category
from app.models.enums import AuditAction, CategoryType, LedgerEntryKind, TransactionType
from app.models.import_batch import ImportBatch
from app.models.transaction import Transaction
from app.schemas.imports import ImportCommitResult, ImportPreview, ImportRowResult
from app.schemas.transaction import TransactionCreate
from app.services.audit import record_audit
from app.services.ledger import query_ledger
from app.services.transactions import create_transaction

EXPECTED_COLUMNS = [
    "transaction_date",
    "transaction_type",
    "amount",
    "account",
    "category",
    "description",
    "merchant_or_payee",
    "payment_method",
    "notes",
]

REQUIRED_COLUMNS = ["transaction_date", "transaction_type", "amount", "account", "description"]

ALLOWED_IMPORT_TYPES = {
    "income": TransactionType.INCOME,
    "expense": TransactionType.EXPENSE,
    "adjustment_increase": TransactionType.ADJUSTMENT_INCREASE,
    "adjustment_decrease": TransactionType.ADJUSTMENT_DECREASE,
}

SAMPLE_CSV = (
    "transaction_date,transaction_type,amount,account,category,description,"
    "merchant_or_payee,payment_method,notes\n"
    "2026-11-02,income,95000.00,salary-M,Salary,November salary,Employer,"
    "Bank transfer,\n"
    "2026-11-03,expense,2450.50,salary-M,Food & Groceries,Weekly groceries,"
    "Metro Cash & Carry,Debit card,\n"
    "2026-11-05,expense,12000.00,salary-M,Bills & Utilities,Electricity bill,"
    "K-Electric,Online,\n"
    "2026-11-10,income,15000.00,salary-A,Freelance,Landing page project,Client,,\n"
)

MAX_ROWS = 5000
MAX_BYTES = 5 * 1024 * 1024


def _decode(content: bytes) -> str:
    if len(content) > MAX_BYTES:
        raise ValidationError("CSV file is larger than 5 MB.")
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationError("CSV must be UTF-8 encoded.") from exc


def _normalize_header(value: str) -> str:
    return value.strip().lower().replace(" ", "_")


def _parse_date(value: str) -> date:
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError("date must be YYYY-MM-DD (or DD/MM/YYYY)")


def _parse_amount(value: str) -> Decimal:
    cleaned = value.replace(",", "").replace("PKR", "").replace("Rs.", "").strip()
    try:
        amount = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError("amount must be a number") from exc
    if amount <= 0:
        raise ValueError("amount must be greater than zero")
    if amount.as_tuple().exponent < -2:
        raise ValueError("amount may have at most 2 decimal places")
    return amount.quantize(Decimal("0.01"))


def _fingerprint(
    txn_date: date,
    txn_type: TransactionType,
    amount: Decimal,
    account_name: str,
    description: str,
    merchant: str | None,
) -> tuple:
    return (
        txn_date.isoformat(),
        txn_type.value,
        str(amount),
        account_name.strip().lower(),
        description.strip().lower(),
        (merchant or "").strip().lower(),
    )


def _existing_fingerprints(
    db: Session, start_date: date, end_date: date
) -> set[tuple]:
    stmt = (
        select(
            Transaction.transaction_date,
            Transaction.transaction_type,
            Transaction.amount,
            Account.name,
            Transaction.description,
            Transaction.merchant_or_payee,
        )
        .join(Account, Account.id == Transaction.account_id)
        .where(
            Transaction.deleted_at.is_(None),
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date,
        )
    )
    return {
        _fingerprint(
            row.transaction_date,
            row.transaction_type,
            Decimal(row.amount),
            row.name,
            row.description,
            row.merchant_or_payee,
        )
        for row in db.execute(stmt)
    }


def _prepare(
    db: Session,
    content: bytes,
    filename: str,
    *,
    create_missing_categories: bool = False,
) -> tuple[ImportPreview, list[tuple], dict[str, Account], dict[str, Category]]:
    text = _decode(content)
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValidationError("CSV file has no header row.")
    headers = [_normalize_header(name) for name in reader.fieldnames]
    detected_columns = [name for name in headers if name]
    missing = [name for name in REQUIRED_COLUMNS if name not in headers]
    if missing:
        raise ValidationError(f"CSV is missing required columns: {', '.join(missing)}.")

    accounts = {
        account.name.lower(): account for account in db.scalars(select(Account))
    }
    categories = {
        category.name.lower(): category for category in db.scalars(select(Category))
    }

    raw_rows: list[tuple[int, dict[str, str]]] = []
    for index, row in enumerate(reader, start=2):
        if len(raw_rows) >= MAX_ROWS:
            raise ValidationError(f"CSV has more than {MAX_ROWS} rows. Split the file.")
        normalized = {
            _normalize_header(key): (value or "").strip()
            for key, value in row.items()
            if key is not None
        }
        if not any(normalized.values()):
            continue
        raw_rows.append((index, normalized))

    if create_missing_categories:
        created = 0
        for _, values in raw_rows:
            txn_type = ALLOWED_IMPORT_TYPES.get(values.get("transaction_type", "").strip().lower())
            if txn_type not in (TransactionType.INCOME, TransactionType.EXPENSE):
                continue
            category_name = values.get("category", "").strip()
            if not category_name or category_name.lower() in categories:
                continue
            category = Category(
                name=category_name[:80],
                category_type=(
                    CategoryType.INCOME
                    if txn_type == TransactionType.INCOME
                    else CategoryType.EXPENSE
                ),
                icon="Circle",
                color="#6366F1",
                is_essential=True,
                notes="Created during CSV import.",
            )
            db.add(category)
            db.flush()
            categories[category_name.lower()] = category
            created += 1
        if created:
            record_audit(
                db,
                entity_type="category",
                entity_id=None,
                action=AuditAction.IMPORT,
                summary=f"Created {created} categories during CSV import",
            )

    dates: list[date] = []
    for _, values in raw_rows:
        try:
            dates.append(_parse_date(values.get("transaction_date", "")))
        except ValueError:
            continue
    existing = _existing_fingerprints(db, min(dates), max(dates)) if dates else set()

    results: list[ImportRowResult] = []
    valid_rows: list[tuple[tuple, int, dict]] = []
    file_seen: dict[tuple, int] = {}

    for row_number, values in raw_rows:
        errors: list[str] = []
        normalized: dict[str, str | None] = {}
        fingerprint = None
        duplicate_reason = None

        try:
            txn_date = _parse_date(values.get("transaction_date", ""))
            normalized["transaction_date"] = txn_date.isoformat()
        except ValueError as exc:
            errors.append(str(exc))
            txn_date = None

        raw_type = values.get("transaction_type", "").strip().lower()
        txn_type = ALLOWED_IMPORT_TYPES.get(raw_type)
        if txn_type is None:
            errors.append(
                "transaction_type must be income, expense, "
                "adjustment_increase or adjustment_decrease"
            )
        normalized["transaction_type"] = txn_type.value if txn_type else raw_type or None

        try:
            amount = _parse_amount(values.get("amount", ""))
            normalized["amount"] = str(amount)
        except ValueError as exc:
            errors.append(str(exc))
            amount = None

        account_name = values.get("account", "").strip()
        account = accounts.get(account_name.lower())
        if account is None:
            errors.append(f"unknown account '{account_name}'")
        elif not account.is_active:
            errors.append(f"account '{account_name}' is inactive")
        normalized["account"] = account.name if account else account_name
        normalized["account_id"] = str(account.id) if account else None

        category_name = values.get("category", "").strip()
        category = categories.get(category_name.lower()) if category_name else None
        normalized["category"] = category.name if category else (category_name or None)
        normalized["category_id"] = str(category.id) if category else None

        if txn_type in (TransactionType.INCOME, TransactionType.EXPENSE):
            if not category_name:
                errors.append("category is required for income and expenses")
            elif category is None:
                errors.append(f"unknown category '{category_name}'")
            else:
                expected = (
                    CategoryType.INCOME
                    if txn_type == TransactionType.INCOME
                    else CategoryType.EXPENSE
                )
                if category.category_type != expected:
                    errors.append(
                        f"category '{category.name}' is not an {expected.value} category"
                    )
        elif txn_type in (
            TransactionType.ADJUSTMENT_INCREASE,
            TransactionType.ADJUSTMENT_DECREASE,
        ):
            if category_name:
                errors.append("adjustments must not have a category")
            normalized["category"] = None
            normalized["category_id"] = None

        description = values.get("description", "").strip()
        if not description:
            errors.append("description is required")
        normalized["description"] = description or None
        normalized["merchant_or_payee"] = values.get("merchant_or_payee") or None
        normalized["payment_method"] = values.get("payment_method") or None
        normalized["notes"] = values.get("notes") or None

        if not errors and txn_date and amount and account and txn_type:
            fingerprint = _fingerprint(
                txn_date,
                txn_type,
                amount,
                account.name,
                description,
                values.get("merchant_or_payee"),
            )
            if fingerprint in existing:
                duplicate_reason = (
                    "Matches an existing transaction "
                    "(date, type, amount, account, description, merchant)."
                )
            elif fingerprint in file_seen:
                duplicate_reason = f"Duplicate of row {file_seen[fingerprint]} in this file."
            else:
                file_seen[fingerprint] = row_number

        is_valid = not errors
        results.append(
            ImportRowResult(
                row_number=row_number,
                values=values,
                normalized=normalized,
                errors=errors,
                is_duplicate=duplicate_reason is not None,
                duplicate_reason=duplicate_reason,
                is_valid=is_valid,
            )
        )
        if is_valid:
            valid_rows.append((fingerprint, row_number, values))  # type: ignore[arg-type]

    preview = ImportPreview(
        filename=filename[:255],
        total_rows=len(results),
        valid_rows=len([row for row in results if row.is_valid and not row.is_duplicate]),
        invalid_rows=len([row for row in results if not row.is_valid]),
        duplicate_rows=len([row for row in results if row.is_duplicate]),
        rows=results,
        detected_columns=detected_columns,
        expected_columns=EXPECTED_COLUMNS,
    )
    return preview, valid_rows, accounts, categories


def preview_import(db: Session, *, content: bytes, filename: str) -> ImportPreview:
    preview, _, _, _ = _prepare(db, content, filename)
    return preview


def commit_import(
    db: Session,
    *,
    content: bytes,
    filename: str,
    skip_duplicates: bool = True,
    create_missing_categories: bool = False,
) -> ImportCommitResult:
    preview, valid_rows, accounts, categories = _prepare(
        db, content, filename, create_missing_categories=create_missing_categories
    )

    batch = ImportBatch(
        filename=filename[:255],
        status="committed",
        row_count=preview.total_rows,
        created_count=0,
        skipped_count=preview.duplicate_rows if skip_duplicates else 0,
        rejected_count=preview.invalid_rows,
        notes=(
            "Duplicates skipped."
            if skip_duplicates
            else "Duplicate rows were left unimported and reported."
        ),
    )
    db.add(batch)
    db.flush()

    created_ids: list[uuid.UUID] = []
    errors: list[dict] = []
    skipped = 0

    for _fp, row_number, _values in valid_rows:
        result = next(row for row in preview.rows if row.row_number == row_number)
        if result.is_duplicate:
            if skip_duplicates:
                skipped += 1
                continue
            errors.append(
                {
                    "row": row_number,
                    "errors": [result.duplicate_reason],
                }
            )
            continue
        normalized = result.normalized or {}
        account_name = normalized.get("account") or ""
        category_name = normalized.get("category")
        account = accounts.get(account_name.lower())
        category = categories.get(category_name.lower()) if category_name else None
        if account is None or (category_name and category is None):
            errors.append({"row": row_number, "errors": ["Unresolved account or category"]})
            continue
        savepoint = db.begin_nested()
        try:
            transaction = create_transaction(
                db,
                TransactionCreate(
                    transaction_date=date.fromisoformat(normalized["transaction_date"]),
                    transaction_type=TransactionType(normalized["transaction_type"]),
                    amount=Decimal(normalized["amount"]),
                    account_id=account.id,
                    category_id=category.id if category else None,
                    description=normalized["description"],
                    merchant_or_payee=normalized.get("merchant_or_payee"),
                    payment_method=normalized.get("payment_method"),
                    notes=normalized.get("notes"),
                ),
                source="import",
                commit=False,
            )
            transaction.import_batch_id = batch.id
            savepoint.commit()
            created_ids.append(transaction.id)
        except Exception as exc:  # AppError messages are safe; unexpected errors are not
            from app.core.exceptions import AppError

            savepoint.rollback()
            errors.append(
                {
                    "row": row_number,
                    "errors": [
                        exc.message
                        if isinstance(exc, AppError)
                        else "Row could not be imported."
                    ],
                }
            )

    batch.created_count = len(created_ids)
    batch.skipped_count = skipped
    batch.rejected_count = preview.invalid_rows + len(errors)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValidationError("Import failed because of a database constraint.") from exc

    return ImportCommitResult(
        import_batch_id=str(batch.id),
        filename=filename,
        total_rows=preview.total_rows,
        created_count=len(created_ids),
        skipped_count=skipped,
        rejected_count=preview.invalid_rows + len(errors),
        errors=errors,
    )


def export_transactions_csv(
    db: Session,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    account_id: uuid.UUID | None = None,
    include_transfers: bool = True,
) -> str:
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        [
            "entry_kind",
            "date",
            "transaction_type",
            "amount",
            "account",
            "from_account",
            "to_account",
            "category",
            "description",
            "merchant_or_payee",
            "payment_method",
            "notes",
            "related_transaction_id",
        ]
    )
    page = 1
    while True:
        entries, total = query_ledger(
            db,
            page=page,
            page_size=500,
            start_date=start_date,
            end_date=end_date,
            account_id=account_id,
            sort_by="entry_date",
            sort_dir="desc",
        )
        for entry in entries:
            if entry.entry_kind == LedgerEntryKind.TRANSFER and not include_transfers:
                continue
            writer.writerow(
                [
                    entry.entry_kind.value,
                    entry.entry_date.isoformat(),
                    entry.transaction_type.value if entry.transaction_type else "",
                    f"{entry.amount:.2f}",
                    entry.account_name or "",
                    entry.from_account_name or "",
                    entry.to_account_name or "",
                    entry.category_name or "",
                    entry.description,
                    entry.merchant_or_payee or "",
                    entry.payment_method or "",
                    (entry.notes or "").replace("\n", " "),
                    str(entry.related_transaction_id or ""),
                ]
            )
        if page * 500 >= total:
            break
        page += 1
    return output.getvalue()


def report_csv(report) -> str:  # type: ignore[no-untyped-def]
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["section", "label", "value"])
    for label, value in [
        ("Period", f"{report.start_date} to {report.end_date}"),
        ("Opening balance", f"{report.opening_balance:.2f}"),
        ("Baseline effect", f"{report.baseline_effect:.2f}"),
        ("Income", f"{report.income:.2f}"),
        ("Gross expenses", f"{report.expenses_gross:.2f}"),
        ("Refunds", f"{report.refunds:.2f}"),
        ("Net expenses", f"{report.expenses_net:.2f}"),
        ("Net cash flow", f"{report.net_cash_flow:.2f}"),
        ("Adjustments net", f"{report.adjustments_net:.2f}"),
        ("Closing balance", f"{report.closing_balance:.2f}"),
        ("Savings rate %", "" if report.savings_rate_pct is None else report.savings_rate_pct),
    ]:
        writer.writerow(["summary", label, value])
    writer.writerow([])
    writer.writerow(
        [
            "section",
            "account",
            "opening",
            "income",
            "expenses",
            "refunds",
            "transfers_in",
            "transfers_out",
            "closing",
        ]
    )
    for account in report.accounts:
        writer.writerow(
            [
                "account",
                account.account_name,
                f"{account.opening_balance:.2f}",
                f"{account.income:.2f}",
                f"{account.expenses_gross:.2f}",
                f"{account.refunds:.2f}",
                f"{account.transfers_in:.2f}",
                f"{account.transfers_out:.2f}",
                f"{account.closing_balance:.2f}",
            ]
        )
    writer.writerow([])
    writer.writerow(["section", "category", "net_amount", "percentage", "transactions"])
    for category in report.categories:
        writer.writerow(
            [
                "category",
                category.name,
                f"{category.amount:.2f}",
                category.percentage,
                category.transaction_count,
            ]
        )
    return output.getvalue()


def sample_csv() -> str:
    return SAMPLE_CSV
