from enum import Enum


class ClueCategory(str, Enum):
    fund = "fund"
    call = "call"
    trip = "trip"
    other = "other"


class ClueRiskLevel(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"
