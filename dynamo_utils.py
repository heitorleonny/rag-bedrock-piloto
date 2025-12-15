import os
import boto3
from datetime import datetime, timezone
from dotenv import load_dotenv
from decimal import Decimal
from collections import defaultdict

load_dotenv()

REGION = os.getenv("AWS_REGION", "us-east-1")
TABLE = os.getenv("DYNAMO_TABLE", "finance-expenses")
MONTHLY_INCOME_DEFAULT = Decimal(os.getenv("MONTHLY_INCOME", "0"))


_session = boto3.Session(region_name=REGION)
_table = _session.resource("dynamodb").Table(TABLE)


def _to_decimal(value):
    return Decimal(str(value))

def save_expense(item: dict, currency: str = "BRL"):
    now = datetime.now(timezone.utc).isoformat()

    record = {
        "pk": "USER#default",
        "sk": f"EXPENSE#{now}",
        "amount": _to_decimal((item["amount"])),
        "description_raw": item["description_raw"],
        "description_normalized": item["description_normalized"],
        "category": item["category"],
        "confidence": _to_decimal((item["confidence"])),
        "currency": currency,
        "created_at": now,
    }

    _table.put_item(Item=record)
    return record

def list_expenses():
    """Return all expense"s for the default user."""

    resp = _table.query(
        KeyConditionExpression="pk = :pk",
        ExpressionAttributeValues={":pk": "USER#default"},
    )
    return resp.get("Items", [])

def totals_by_category():
    """Return total expenses grouped by category."""

    items = list_expenses()
    totals = defaultdict(Decimal)

    for it in items:
        totals[it["category"]] += it["amount"]

    return dict(totals)

def list_expenses_month(year: int, month: int):
    """
    Busca itens do mês (YYYY-MM) usando intervalo no sk (ISO timestamp).
    sk = 'EXPENSE#2025-12-15T...'
    """
    start = datetime(year, month, 1, tzinfo=timezone.utc).isoformat()
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc).isoformat()
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc).isoformat()

    resp = _table.query(
        KeyConditionExpression="pk = :pk AND sk BETWEEN :s AND :e",
        ExpressionAttributeValues={
            ":pk": "USER#default",
            ":s": f"EXPENSE#{start}",
            ":e": f"EXPENSE#{end}",
        },
    )
    return resp.get("Items", [])

def totals_by_category_items(items):
    totals = defaultdict(Decimal)
    for it in items:
        totals[it["category"]] += it["amount"]
    return dict(totals)

def total_amount(items):
    total = Decimal("0")
    for it in items:
        total += it["amount"]
    return total

def get_monthly_income():
    return MONTHLY_INCOME_DEFAULT

def top_n_expenses(items, n=5):
    # ordena por amount desc
    sorted_items = sorted(items, key=lambda x: x["amount"], reverse=True)
    out = []
    for it in sorted_items[:n]:
        out.append({
            "amount": float(it["amount"]),
            "category": it["category"],
            "desc": it.get("description_normalized") or it.get("description_raw", "")
        })
    return out