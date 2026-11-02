import re
from datetime import date


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def required(value):
    return bool(str(value or "").strip())


def valid_email(value):
    return not value.strip() or bool(EMAIL_RE.match(value.strip()))


def valid_phone(value):
    digits = re.sub(r"\D", "", value or "")
    return 8 <= len(digits) <= 15


def valid_product_name(value):
    text = value.strip()
    return bool(text) and len(text) <= 120 and not text.isdigit()


def valid_date(value):
    return value.isValid()


def not_past_date(value):
    return value >= date.today()
