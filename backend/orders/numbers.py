"""Resolve the order reference already displayed in the storefront."""
import re
from uuid import UUID

from django.db.models import Q


def number_filter(number):
    value = number.strip().removeprefix("#")
    if re.fullmatch(r"[0-9a-fA-F]{8}", value):
        first = int(value, 16) << 96
        return Q(pk__range=(UUID(int=first), UUID(int=first + (1 << 96) - 1)))
    try:
        return Q(pk=UUID(value))
    except ValueError:
        return None
