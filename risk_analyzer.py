"""
Pure, testable functions for the Pharma Shipment Risk Analyzer.
No Streamlit imports. Processing is local/in-memory.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re
import pandas as pd


TEMP_MIN_DEFAULT = 2.0
TEMP_MAX_DEFAULT = 8.0
TEMP_WEIGHT = 50
DELAY_WEIGHT = 25
QUALITY_WEIGHT = 25


@dataclass
class Profile:
    sheets: list[str]
    sheet_profiles: dict[str, dict[str, Any]]
    candidate_fields: dict[str, list[str]]


def profile_workbook(file_obj) -> Profile:
    xls = pd.ExcelFile(file_obj, engine="openpyxl")
    sheet_profiles = {}
    candidates = {"temperature": [], "delay": [], "quality_compliance": []}

    for sheet in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet)
        dtypes = {c: str(df[c].dtype) for c in df.columns}
        missing = {c: int(df[c].isna().sum()) for c in df.columns}
        sheet_profiles[sheet] = {
            "rows": len(df),
            "columns": list(df.columns),
            "dtypes": dtypes,
            "missing": missing,
        }
        for col in df.columns:
            s = str(col).strip().lower()
            if re.search(r"temp|temperature|thermal|excursion", s):
                candidates["temperature"].append(f"{sheet}: {col}")
            if re.search(r"delay|late|delivery|expected|actual", s):
                candidates["delay"].append(f"{sheet}: {col}")
            if re.search(r"quality|compliance|deviation|issue|flag|violation", s):
                candidates["quality_compliance"].append(f"{sheet}: {col}")

    return Profile(xls.sheet_names, sheet_profiles, candidates)


def _find_col(df, patterns):
    for col in df.columns:
        s = str(col).strip().lower()
        if any(re.search(p, s) for p in patterns):
            return col
    return None


def _numeric_series(s):
    return pd.to_numeric(s.astype(str).str.extract(r"(-?\d+(?:\.\d+)?)")[0], errors="coerce")


def _boolish(s):
    true_values = {"yes", "y", "true", "1", "flagged", "failed", "fail", "issue", "non-compliant", "noncompliant", "bad"}
    false_values = {"no", "n", "false", "0", "clear", "pass", "ok", "compliant", "none", "good"}
    out = []
    for x in s:
        if pd.isna(x):
            out.append(pd.NA)
        elif isinstance(x, bool):
            out.append(x)
        else:
            v = str(x).strip().lower()
            if v in true_values:
                out.append(True)
            elif v in false_values:
                out.append(False)
            else:
                out.append(pd.NA)
    return pd.Series(out, index=s.index, dtype="boolean")


def _delay_mask(df):
    delay_col = _find_col(df, [r"\bdelay\b", r"late", r"delay.*days", r"days.*late"])
    if delay_col:
        nums = _numeric_series(df[delay_col])
        return nums.ge(1), f"{delay_col} >= 1 day"

    expected = _find_col(df, [r"expected.*deliver", r"planned.*deliver", r"promised.*deliver"])
    actual = _find_col(df, [r"actual.*deliver", r"delivered.*date", r"delivery.*actual"])
    if expected and actual:
        e = pd.to_datetime(df[expected], errors="coerce")
        a = pd.to_datetime(df[actual], errors="coerce")
        return a.gt(e), f"{actual} > {expected}"

    return pd.Series(pd.NA, index=df.index, dtype="boolean"), None


def _temperature_mask(df):
    excursion = _find_col(df, [r"temperature.*excursion", r"temp.*excursion", r"\bexcursion\b"])
    if excursion:
        b = _boolish(df[excursion])
        if b.notna().any():
            return b, f"{excursion} indicates an excursion"

    min_col = _find_col(df, [r"min.*temp", r"temp.*min", r"minimum.*temp"])
    max_col = _find_col(df, [r"max.*temp", r"temp.*max", r"maximum.*temp"])
    temp_col = _find_col(df, [r"temperature", r"\btemp\b"])

    if min_col or max_col:
        low = _numeric_series(df[min_col]) if min_col else pd.Series(TEMP_MIN_DEFAULT, index=df.index)
        high = _numeric_series(df[max_col]) if max_col else pd.Series(TEMP_MAX_DEFAULT, index=df.index)
        return (low.lt(TEMP_MIN_DEFAULT) | high.gt(TEMP_MAX_DEFAULT)), \
               f"default cold-chain range {TEMP_MIN_DEFAULT}-{TEMP_MAX_DEFAULT}°C"
    if temp_col:
        t = _numeric_series(df[temp_col])
        return t.lt(TEMP_MIN_DEFAULT) | t.gt(TEMP_MAX_DEFAULT), \
               f"default cold-chain range {TEMP_MIN_DEFAULT}-{TEMP_MAX_DEFAULT}°C"

    return pd.Series(pd.NA, index=df.index, dtype="boolean"), None


def _quality_mask(df):
    col = _find_col(df, [r"quality", r"compliance", r"deviation", r"non.?compliant", r"quality.*flag"])
    if not col:
        return pd.Series(pd.NA, index=df.index, dtype="boolean"), None
    return _boolish(df[col]), f"{col} indicates a quality/compliance issue"


def analyze_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[str]]:
    if df.empty:
        return df.copy(), [], ["The selected sheet is empty."]

    result = df.copy()
    temp, temp_reason = _temperature_mask(df)
    delay, delay_reason = _delay_mask(df)
    quality, quality_reason = _quality_mask(df)

    # A row is scored only if every available scoring signal is either known
    # or the corresponding signal is entirely absent from the dataset.
    signal_specs = [
        ("temperature", temp, temp_reason, TEMP_WEIGHT),
        ("delay", delay, delay_reason, DELAY_WEIGHT),
        ("quality", quality, quality_reason, QUALITY_WEIGHT),
    ]
    score = pd.Series(0.0, index=df.index)
    reasons = [[] for _ in df.index]
    unscored = pd.Series(False, index=df.index)

    for name, mask, reason, weight in signal_specs:
        if reason is None:
            continue
        missing = mask.isna()
        unscored |= missing
        score = score + mask.fillna(False).astype(int) * weight
        for pos, flagged in enumerate(mask.fillna(False).tolist()):
            if flagged:
                reasons[pos].append(name)

    # If no usable risk signals exist, no rows can be meaningfully scored.
    usable = [x for _, _, x, _ in signal_specs if x is not None]
    if not usable:
        unscored[:] = True

    def classify(i):
        if unscored.iloc[i]:
            return "Unscored"
        s = score.iloc[i]
        return "High" if s >= 50 else ("Medium" if s >= 25 else "Low")

    result["Risk Score"] = score
    result["Risk Level"] = [classify(i) for i in range(len(result))]
    result["Risk Reasons"] = [", ".join(r) if r else "No detected risk signals" for r in reasons]

    if temp_reason is not None:
        result["Temperature Excursion"] = temp
    if delay_reason is not None:
        result["Significant Delay"] = delay
    if quality_reason is not None:
        result["Quality/Compliance Issue"] = quality

    result["_unscored_reason"] = [
        "Missing value in a detected risk-signal field" if unscored.iloc[i] else ""
        for i in range(len(result))
    ]

    assumptions = []
    if temp_reason and "default cold-chain" in temp_reason:
        assumptions.append("No explicit temperature range was found; 2-8°C cold-chain range was used.")
    if delay_reason and ">= 1 day" in delay_reason:
        assumptions.append("A delay of 1 or more days is treated as significant.")
    if temp_reason is None:
        assumptions.append("No temperature-related field was detected.")
    if delay_reason is None:
        assumptions.append("No usable delay or expected-vs-actual delivery fields were detected.")
    if quality_reason is None:
        assumptions.append("No usable quality/compliance flag was detected.")

    return result, assumptions, [x for x in [temp_reason, delay_reason, quality_reason] if x]


def recommendations(result: pd.DataFrame) -> list[str]:
    if result.empty:
        return ["Upload a non-empty workbook sheet to generate recommendations."]

    recs = []
    high = int((result["Risk Level"] == "High").sum())
    temp = int(result.get("Temperature Excursion", pd.Series(False, index=result.index)).fillna(False).sum())
    delayed = int(result.get("Significant Delay", pd.Series(False, index=result.index)).fillna(False).sum())
    quality = int(result.get("Quality/Compliance Issue", pd.Series(False, index=result.index)).fillna(False).sum())

    if high:
        recs.append(f"Prioritize review of the {high} high-risk shipment(s).")
    if temp:
        recs.append(f"Investigate {temp} shipment(s) with temperature excursions.")
    if delayed:
        recs.append(f"Review {delayed} shipment(s) with significant delivery delay.")
    if quality:
        recs.append(f"Escalate {quality} shipment(s) with quality/compliance issues.")
    if not recs:
        recs.append("No high-risk pattern was detected under the configured rules.")
    return recs[:5]
