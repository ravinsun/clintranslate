# ClinTranslate v4 — Validation Report
**File:** sdtm_lb.sas  
**Generated:** 2026-06-25 14:47:54  
**Tool:** ClinTranslate v4 Agentic Pipeline  
**Disclaimer:** Translated output requires IQ/OQ/PQ validation before use in any GxP/submission context.

---

## 1. Translation Decision
| Field | Value |
|---|---|
| Routing Decision | 🔴 REJECTED |
| Routing Reason | Low cosine similarity (0.5482) — insufficient knowledge base coverage; manual translation recommended |
| Cosine Similarity Score | 0.5482 |
| Syntax Validation | VALID |
| Self-Correction Attempts | 0 |

---

## 2. Performance Metrics
| Metric | Value |
|---|---|
| SAS Lines of Code | 74 |
| Python Lines of Code | 214 |
| Agent Translation Time | 46.6s (0.8 min) |
| Manual Estimate (baseline) | 2.5 hrs |
| Estimated Time Saved | 2.4871 hrs (99.5%) |

---

## 3. TFL / Output Detection
⚠️ YES — PROC REPORT / ODS RTF detected. Manual TFL review required.

---

## 4. Translated Python Output
```python
# Translated from: sdtm_lb.sas | ClinTranslate v4 Agentic
# Study    : BMN-999-001
# Purpose  : SDTM LB Domain — Laboratory Results
# Author   : Clinical Data Engineering (Python Translation)
# Created  : 2024-01-10
# NOTE     : 21 CFR Part 11 — No silent data modification; all transformations
#            are explicit and auditable. Any unexpected values are preserved
#            and flagged rather than silently overwritten.

import pandas as pd
import numpy as np
import os

# ── Path configuration (mirrors SAS libname statements) ──
SDTM_PATH = "/data/bmn999/sdtm"
RAW_PATH  = "/data/bmn999/raw"

# ── Load raw lab data (mirrors: set raw.lab_results) ──
lb_raw = pd.read_csv(os.path.join(RAW_PATH, "lab_results.csv"))

# ---------------------------------------------------------------------------
# Step 1: Standardize test codes to CDISC LBTESTCD
# Mirrors SAS SELECT/WHEN block on upcase(test_name)
# ---------------------------------------------------------------------------

# Build lookup for LBTESTCD and LBTEST — mirrors SAS WHEN branches
testcode_map = {
    "HEMOGLOBIN": ("HGB",   "Hemoglobin"),
    "HGB":        ("HGB",   "Hemoglobin"),
    "HEMATOCRIT": ("HCT",   "Hematocrit"),
    "HCT":        ("HCT",   "Hematocrit"),
    "PLATELETS":  ("PLAT",  "Platelets"),
    "PLT":        ("PLAT",  "Platelets"),
    "WBC":        ("WBC",   "Leukocytes"),
    "LEUKOCYTES": ("WBC",   "Leukocytes"),
    "CREATININE": ("CREAT", "Creatinine"),
    "CREAT":      ("CREAT", "Creatinine"),
    "ALT":        ("ALT",   "Alanine Aminotransferase"),
    "SGPT":       ("ALT",   "Alanine Aminotransferase"),
    "AST":        ("AST",   "Aspartate Aminotransferase"),
    "SGOT":       ("AST",   "Aspartate Aminotransferase"),
    "GLUCOSE":    ("GLUC",  "Glucose"),
    "GLUC":       ("GLUC",  "Glucose"),
}

# Uppercase key column for matching — mirrors upcase(test_name)
_test_upper = lb_raw["test_name"].str.strip().str.upper()

# Map to (LBTESTCD, LBTEST) tuples; otherwise-branch uses upcase(test_name)
# and original test_name — mirrors SAS OTHERWISE block
lb_raw["lbtestcd"] = _test_upper.map(
    lambda x: testcode_map[x][0] if x in testcode_map else x
)
lb_raw["lbtest"] = _test_upper.map(
    lambda x: testcode_map[x][1] if x in testcode_map else lb_raw.loc[
        _test_upper == x, "test_name"
    ].values[0]
)

# Safer vectorised approach for lbtest otherwise-branch (avoids label mismatch)
# Overwrite only: avoids the multi-index issue in the lambda above
_mapped_lbtest = _test_upper.map(
    {k: v[1] for k, v in testcode_map.items()}
)
# For unmatched rows, fall back to original test_name — mirrors OTHERWISE
lb_raw["lbtest"] = _mapped_lbtest.combine_first(lb_raw["test_name"].str.strip())

# ---------------------------------------------------------------------------
# Standardize units
# Mirrors SAS IF/ELSE IF chain on lborresu
# ---------------------------------------------------------------------------

# lborresu — mirrors: lborresu = strip(unit)
lb_raw["lborresu"] = lb_raw["unit"].str.strip()

# lbstresu — mirrors SAS conditional unit normalization
def _map_lbstresu(unit):
    """Mirror SAS IF/ELSE IF unit standardization logic."""
    if unit == "g/dL":
        return "g/dL"
    elif unit in ("U/L", "IU/L"):
        return "U/L"
    elif unit == "mg/dL":
        return "mg/dL"
    else:
        return unit  # Otherwise — preserve original; no silent modification

lb_raw["lbstresu"] = lb_raw["lborresu"].map(_map_lbstresu)

# ---------------------------------------------------------------------------
# Result variables
# Mirrors SAS: lborres, lbstresn, lbstresc assignments
# ---------------------------------------------------------------------------

# lborres — mirrors: lborres = strip(result_text)
lb_raw["lborres"] = lb_raw["result_text"].str.strip()

# lbstresn — mirrors: lbstresn = input(result_numeric, best12.)
# Coerce to numeric; non-numeric become NaN (equivalent to SAS missing .)
lb_raw["lbstresn"] = pd.to_numeric(lb_raw["result_numeric"], errors="coerce")

# lbstresc — mirrors: lbstresc = strip(result_text)
lb_raw["lbstresc"] = lb_raw["result_text"].str.strip()

# ---------------------------------------------------------------------------
# Normal range flags — mirrors SAS IF/ELSE IF on lbstresn
# 21 CFR Part 11: Only assign flag when lbstresn is non-missing
# ---------------------------------------------------------------------------

def _assign_lbnrind(row):
    """
    Mirror SAS normal range flag logic:
        if lbstresn ne . then do;
            if lbstresn < low_normal  then lbnrind = 'LOW';
            else if lbstresn > high_normal then lbnrind = 'HIGH';
            else lbnrind = 'NORMAL';
        end;
    Returns NaN (SAS missing) when lbstresn is missing.
    """
    if pd.isna(row["lbstresn"]):
        return np.nan  # Missing — no flag assigned; mirrors SAS implicit missing
    if row["lbstresn"] < row["low_normal"]:
        return "LOW"
    elif row["lbstresn"] > row["high_normal"]:
        return "HIGH"
    else:
        return "NORMAL"

lb_raw["lbnrind"] = lb_raw.apply(_assign_lbnrind, axis=1)

# ---------------------------------------------------------------------------
# SDTM required constant variables
# Mirrors SAS: domain = 'LB'; studyid = 'BMN-999-001'; lbcat = 'HEMATOLOGY'
# ---------------------------------------------------------------------------

lb_raw["domain"]  = "LB"
lb_raw["studyid"] = "BMN-999-001"
lb_raw["lbcat"]   = "HEMATOLOGY"

# ---------------------------------------------------------------------------
# Date standardization to ISO 8601
# Mirrors SAS: lbdtc = put(collect_date, yymmdd10.)
# Assumes collect_date is parseable; format enforced as YYYY-MM-DD
# ---------------------------------------------------------------------------

lb_raw["lbdtc"] = pd.to_datetime(
    lb_raw["collect_date"], errors="coerce"
).dt.strftime("%Y-%m-%d")

# 21 CFR Part 11: Flag rows where date conversion failed (SAS would produce .)
_date_failures = lb_raw["lbdtc"].isna().sum()
if _date_failures > 0:
    import warnings
    warnings.warn(
        f"[DATA QUALITY] {_date_failures} row(s) have unparseable collect_date; "
        "lbdtc set to NaT — review source data before final submission.",
        UserWarning,
        stacklevel=2,
    )

# ---------------------------------------------------------------------------
# Variable labels — Python equivalent of SAS LABEL statement
# Stored as DataFrame attrs for downstream documentation/metadata use
# ---------------------------------------------------------------------------

_lb_labels = {
    "lbtestcd": "Lab Test Short Name",
    "lbtest":   "Lab Test Name",
    "lbstresn": "Numeric Result/Finding in Standard Units",
    "lbnrind":  "Reference Range Indicator",
}
lb_raw.attrs["variable_labels"] = _lb_labels

# ---------------------------------------------------------------------------
# KEEP — mirrors SAS KEEP statement; retain only SDTM-required columns
# ---------------------------------------------------------------------------

_keep_cols = [
    "studyid", "domain", "usubjid", "lbseq", "lbtestcd", "lbtest", "lbcat",
    "lborres", "lborresu", "lbstresn", "lbstresc", "lbstresu",
    "lbnrind", "lbdtc", "visitnum", "visit",
]

# 21 CFR Part 11: Verify all expected columns exist before subsetting
_missing_cols = [c for c in _keep_cols if c not in lb_raw.columns]
if _missing_cols:
    raise KeyError(
        f"[DATA INTEGRITY ERROR] Expected SDTM LB columns missing from source: "
        f"{_missing_cols}. Pipeline halted — no partial output written."
    )

lb_raw = lb_raw[_keep_cols].copy()

# ---------------------------------------------------------------------------
# Step 2: Assign sequence numbers (LBSEQ)
# Mirrors SAS PROC SORT + DATA step with RETAIN lbseq / BY usubjid / first.usubjid
# ---------------------------------------------------------------------------

# Sort — mirrors: proc sort data=lb_raw; by usubjid lbdtc lbtestcd
lb_raw = lb_raw.sort_values(
    by=["usubjid", "lbdtc", "lbtestcd"],
    ascending=True,
    na_position="last",
).reset_index(drop=True)

# Assign cumulative sequence per subject — mirrors RETAIN lbseq + lbseq + 1
# groupby cumcount() is 0-based; +1 mirrors SAS lbseq starting at 1
lb_raw["lbseq"] = (
    lb_raw.groupby("usubjid").cumcount() + 1
)

# ---------------------------------------------------------------------------
# Write final SDTM LB dataset — mirrors: data sdtm.lb; set lb_raw
# ---------------------------------------------------------------------------

_out_path = os.path.join(SDTM_PATH, "lb.csv")
lb_raw.to_csv(_out_path, index=False)
print(f"[INFO] SDTM LB dataset written: {_out_path} | Rows: {len(lb_raw)}")

# ---------------------------------------------------------------------------
# Validation checks
# ---------------------------------------------------------------------------

# [REQUIRES_MANUAL_REVIEW: TFL output]
# Mirrors: proc freq data=sdtm.lb; tables lbtestcd * lbnrind / list missing
print("\n=== LB Domain — Test Code by Normal Range Flag ===")
_freq_table = (
    lb_raw
    .groupby(["lbtestcd", "lbnrind"], dropna=False)  # dropna=False mirrors / missing
    .size()
    .reset_index(name="COUNT")
    .sort_values(["lbtestcd", "lbnrind"])
)
print(_freq_table.to_string(index=False))

# [REQUIRES_MANUAL_REVIEW: TFL output]
# Mirrors: proc means data=sdtm.lb n nmiss mean std min max; class lbtestcd; var lbstresn
print("\n=== LB Domain — Numeric Results Summary ===")
_means_table = (
    lb_raw
    .groupby("lbtestcd", dropna=False)["lbstresn"]
    .agg(
        N=lambda x: x.notna().sum(),           # mirrors N
        NMISS=lambda x: x.isna().sum(),        # mirrors NMISS
        MEAN="mean",                           # mirrors MEAN
        STD="std",                             # mirrors STD (ddof=1, SAS default)
        MIN="min",                             # mirrors MIN
        MAX="max",                             # mirrors MAX
    )
    .reset_index()
)
print(_means_table.to_string(index=False))
```

---

## 5. GxP Review Checklist
- [ ] Reviewer verified variable names match source SAS
- [ ] Output dataset structure confirmed equivalent
- [ ] Logic verified against CDISC SDTM/ADaM specification
- [ ] Parallel run comparison completed (SAS vs Python outputs match)
- [ ] Reviewer signature / date: _______________

---
*ClinTranslate v4 | github.com/ravinsun/clintranslate | 21 CFR Part 11 Awareness*
