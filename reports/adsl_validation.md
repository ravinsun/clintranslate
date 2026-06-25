# ClinTranslate v4 — Validation Report
**File:** adsl.sas  
**Generated:** 2026-06-25 14:47:54  
**Tool:** ClinTranslate v4 Agentic Pipeline  
**Disclaimer:** Translated output requires IQ/OQ/PQ validation before use in any GxP/submission context.

---

## 1. Translation Decision
| Field | Value |
|---|---|
| Routing Decision | 🟡 REVIEW_REQUIRED |
| Routing Reason | Medium cosine similarity (0.575) — translation likely correct but requires reviewer confirmation |
| Cosine Similarity Score | 0.575 |
| Syntax Validation | VALID |
| Self-Correction Attempts | 0 |

---

## 2. Performance Metrics
| Metric | Value |
|---|---|
| SAS Lines of Code | 90 |
| Python Lines of Code | 268 |
| Agent Translation Time | 58.4s (1.0 min) |
| Manual Estimate (baseline) | 2.5 hrs |
| Estimated Time Saved | 2.4838 hrs (99.4%) |

---

## 3. TFL / Output Detection
✅ No TFL constructs detected

---

## 4. Translated Python Output
```python
# Translated from: adsl.sas | ClinTranslate v4 Agentic
# Study    : BMN-999-001
# Purpose  : Create ADSL - Subject Level Analysis Dataset
# Author   : Clinical Data Engineering (SAS->Python translation)
# Created  : 2024-01-15
# Translator Notes:
#   - SAS libname paths mapped to explicit parquet/csv read calls;
#     update input paths to match environment file layout.
#   - SAS date values (stored as days since 1960-01-01) converted via
#     pd.to_datetime with ISO string parsing where applicable.
#   - SAS retain + first./last. BY-group logic reproduced with
#     groupby + cumcount / transform idioms.
#   - proc freq summary reproduced with pd.crosstab; no ODS output.
# 21 CFR Part 11: All source DataFrames are treated as read-only;
#   every transformation produces a new object to prevent silent mutation.

import numpy as np
import pandas as pd
import os

# ---------------------------------------------------------------------------
# Environment / path configuration
# Update INPUT_DIR and OUTPUT_DIR to match your validated environment paths.
# ---------------------------------------------------------------------------
SDTM_DIR = "/data/bmn999/sdtm"
ADAM_DIR  = "/data/bmn999/adam"

def read_dataset(directory: str, name: str) -> pd.DataFrame:
    """
    Read a SAS-transport-equivalent dataset.
    Tries parquet first, then SAS7BDAT via pyreadstat, then CSV.
    Raises FileNotFoundError if none found — no silent fallback.
    """
    parquet_path = os.path.join(directory, f"{name}.parquet")
    sas_path     = os.path.join(directory, f"{name}.sas7bdat")
    csv_path     = os.path.join(directory, f"{name}.csv")

    if os.path.exists(parquet_path):
        return pd.read_parquet(parquet_path)
    elif os.path.exists(sas_path):
        import pyreadstat  # optional dependency; validated env must have it
        df, _ = pyreadstat.read_sas7bdat(sas_path)
        return df
    elif os.path.exists(csv_path):
        return pd.read_csv(csv_path, dtype=str)
    else:
        raise FileNotFoundError(
            f"No recognised dataset found for '{name}' in '{directory}'. "
            "Ensure parquet, sas7bdat, or csv file exists."
        )

def write_dataset(df: pd.DataFrame, directory: str, name: str) -> None:
    """
    Persist the final dataset to parquet (preferred in validated pipelines).
    Directory must exist; no auto-creation to avoid unintended writes.
    """
    out_path = os.path.join(directory, f"{name}.parquet")
    df.to_parquet(out_path, index=False, engine="pyarrow")
    print(f"[INFO] Dataset written: {out_path}  shape={df.shape}")

# ===========================================================================
# Step 1 — Base population from DM
# SAS: data adsl_base; set sdtm.dm; ...
# ===========================================================================
dm = read_dataset(SDTM_DIR, "dm")

# Work on an explicit copy — never mutate the raw source (21 CFR Part 11)
adsl_base = dm.copy()

# --- Age grouping -----------------------------------------------------------
# SAS: if / else-if chain on AGE -> AGEGR1
# pd.cut with right=False reproduces SAS half-open intervals [lo, hi)
adsl_base["AGEGR1"] = pd.cut(
    adsl_base["AGE"],
    bins=[-np.inf, 18, 40, 65, np.inf],
    labels=["<18", "18-39", "40-64", ">=65"],
    right=False           # SAS: 18 <= age < 40  =>  left-closed, right-open
)
adsl_base["AGEGR1"] = adsl_base["AGEGR1"].astype(str)

# --- BMI calculation --------------------------------------------------------
# SAS: if height > 0 and weight > 0 then bmi = weight / ((height/100)**2)
height_valid = adsl_base["HEIGHT"].gt(0)
weight_valid = adsl_base["WEIGHT"].gt(0)

adsl_base["BMI"] = np.where(
    height_valid & weight_valid,
    adsl_base["WEIGHT"] / ((adsl_base["HEIGHT"] / 100) ** 2),
    np.nan                # SAS missing (.) -> np.nan
)

# --- BMI group --------------------------------------------------------------
# SAS: series of if/else-if; np.select preserves the same priority order
bmi_conditions = [
    adsl_base["BMI"].lt(18.5),
    adsl_base["BMI"].between(18.5, 25, inclusive="left"),   # 18.5 <= bmi < 25
    adsl_base["BMI"].between(25.0, 30, inclusive="left"),   # 25   <= bmi < 30
    adsl_base["BMI"].ge(30)
]
bmi_choices = ["Underweight", "Normal", "Overweight", "Obese"]

adsl_base["BMIGRP"] = np.select(
    bmi_conditions,
    bmi_choices,
    default="Missing"     # SAS: else bmigrp = 'Missing'
)

# Variable labels stored in a dict (SAS LABEL statement equivalent)
# Used for documentation and downstream TFL tooling
ADSL_LABELS = {
    "AGEGR1": "Age Group",
    "BMI":    "Body Mass Index",
    "BMIGRP": "BMI Group",
}

# ===========================================================================
# Step 2 — Merge disposition (SDTM DS)
# SAS: proc sort + data step merge with WHERE dscat='DISPOSITION EVENT'
# ===========================================================================
ds_raw = read_dataset(SDTM_DIR, "ds")

# SAS WHERE clause on the DS dataset in the MERGE statement
ds_disp = (
    ds_raw
    .loc[ds_raw["DSCAT"] == "DISPOSITION EVENT",   # SAS: where=(dscat='...')
         ["USUBJID", "DSDECOD", "DSSTDTC"]]        # SAS: keep=
    .copy()
)

# SAS: proc sort by usubjid — sort both sides before merging
adsl_sorted = adsl_base.sort_values("USUBJID").reset_index(drop=True)
ds_sorted   = ds_disp.sort_values("USUBJID").reset_index(drop=True)

# SAS: merge adsl_sorted (in=inDM) ds_sorted (in=inDS); by usubjid; if inDM;
# -> left join preserves all DM subjects; DS rows without DM match are dropped
adsl_disp = pd.merge(
    adsl_sorted,
    ds_sorted,
    on="USUBJID",
    how="left"            # SAS: if inDM — keep all DM subjects
)

# --- Completion flag --------------------------------------------------------
# SAS: if dsdecod = 'COMPLETED' then compfl = 'Y'; else compfl = 'N';
adsl_disp["COMPFL"] = np.where(
    adsl_disp["DSDECOD"] == "COMPLETED",
    "Y",
    "N"
)

# --- Discontinuation reason -------------------------------------------------
# SAS: if dsdecod ne 'COMPLETED' and dsdecod ne '' then discrs = dsdecod;
# Subjects who completed have DISCRS left as NaN (SAS missing character)
not_completed = (
    adsl_disp["DSDECOD"].notna() &
    adsl_disp["DSDECOD"].ne("COMPLETED") &
    adsl_disp["DSDECOD"].ne("")
)
adsl_disp["DISCRS"] = np.where(
    not_completed,
    adsl_disp["DSDECOD"],
    np.nan
)

# Update label dictionary
ADSL_LABELS.update({
    "COMPFL": "Completor Flag",
    "DISCRS": "Discontinuation Reason",
})

# ===========================================================================
# Step 3 — Merge exposure for treatment dates (SDTM EX)
# SAS: proc sort by usubjid exstdtc; data step with first./last. and retain
# ===========================================================================
ex_raw = read_dataset(SDTM_DIR, "ex")

# SAS: proc sort data=sdtm.ex out=ex_first; by usubjid exstdtc;
ex_sorted = (
    ex_raw
    .sort_values(["USUBJID", "EXSTDTC"])   # ascending sort matches SAS default
    .reset_index(drop=True)
)

# SAS: if first.usubjid then trtsdt = input(exstdtc, yymmdd10.);
# -> first row per subject gives treatment start date
# SAS: if last.usubjid then trtedt = input(exendtc, yymmdd10.);
# -> last row per subject gives treatment end date

# Parse ISO date strings to pandas Timestamps (yymmdd10. informat equivalent)
ex_sorted["EXSTDTC_dt"] = pd.to_datetime(
    ex_sorted["EXSTDTC"], format="%Y-%m-%d", errors="coerce"
)
ex_sorted["EXENDTC_dt"] = pd.to_datetime(
    ex_sorted["EXENDTC"], format="%Y-%m-%d", errors="coerce"
)

# SAS RETAIN + first./last. reproduced with groupby aggregation
ex_dates = (
    ex_sorted
    .groupby("USUBJID", sort=False)
    .agg(
        TRTSDT=("EXSTDTC_dt", "first"),   # SAS: retain trtsdt; if first.usubjid
        TRTEDT=("EXENDTC_dt", "last")     # SAS: if last.usubjid
    )
    .reset_index()
)

# ===========================================================================
# Step 4 — Final ADSL merge: adsl_disp + ex_dates
# SAS: data adam.adsl; merge adsl_disp (in=inBase) ex_dates (in=inEX);
#      by usubjid; if inBase;
# ===========================================================================
adsl_final = pd.merge(
    adsl_disp.sort_values("USUBJID"),
    ex_dates,
    on="USUBJID",
    how="left"            # SAS: if inBase — all disposition subjects retained
)

# --- Treatment duration -----------------------------------------------------
# SAS: if trtsdt ne . and trtedt ne . then trtdur = trtedt - trtsdt + 1;
# SAS date arithmetic in days; Timedelta.days gives the integer equivalent
both_dates_present = adsl_final["TRTSDT"].notna() & adsl_final["TRTEDT"].notna()

adsl_final["TRTDUR"] = np.where(
    both_dates_present,
    (adsl_final["TRTEDT"] - adsl_final["TRTSDT"]).dt.days + 1,
    np.nan                # SAS: implicit missing when condition not met
)

# --- Safety population flag -------------------------------------------------
# SAS: if inEX then saffl = 'Y'; else saffl = 'N';
# A subject has exposure data when TRTSDT is non-missing after the left join
adsl_final["SAFFL"] = np.where(
    adsl_final["TRTSDT"].notna(),
    "Y",
    "N"
)

# --- ITT population flag ----------------------------------------------------
# SAS: if randdt ne . then ittfl = 'Y'; else ittfl = 'N';
# RANDDT must exist in DM; guard with .get() to surface missing column clearly
if "RANDDT" not in adsl_final.columns:
    raise KeyError(
        "RANDDT not found in DM dataset. "
        "Verify SDTM DM contains randomisation date variable before proceeding."
    )

# SAS input(randdt, yymmdd10.) implied — parse if still a string
if adsl_final["RANDDT"].dtype == object:
    adsl_final["RANDDT"] = pd.to_datetime(
        adsl_final["RANDDT"], format="%Y-%m-%d", errors="coerce"
    )

adsl_final["ITTFL"] = np.where(
    adsl_final["RANDDT"].notna(),
    "Y",
    "N"
)

# Update label dictionary with Step 4 variables
ADSL_LABELS.update({
    "TRTSDT": "Date of First Study Treatment",
    "TRTEDT": "Date of Last Study Treatment",
    "TRTDUR": "Treatment Duration (Days)",
    "SAFFL":  "Safety Population Flag",
    "ITTFL":  "ITT Population Flag",
})

# --- Final sort: proc sort data=adam.adsl; by usubjid; --------------------
adsl_final = adsl_final.sort_values("USUBJID").reset_index(drop=True)

# Attach label metadata as DataFrame attrs (accessible but non-intrusive)
adsl_final.attrs["variable_labels"] = ADSL_LABELS
adsl_final.attrs["dataset_label"]   = "Subject-Level Analysis Dataset"
adsl_final.attrs["study"]           = "BMN-999-001"

# ===========================================================================
# Persist adam.adsl
# ===========================================================================
write_dataset(adsl_final, ADAM_DIR, "adsl")

# ===========================================================================
# Summary — proc freq equivalent
# SAS: proc freq data=adam.adsl;
#      tables saffl * ittfl * compfl / list missing;
# ===========================================================================
print("\n" + "=" * 60)
print("ADSL Population Summary — BMN-999-001")
print("=" * 60)

# SAS: / list missing — include NaN cells; margins=False matches LIST option
freq_table = (
    adsl_final
    .fillna({"SAFFL": "Missing", "ITTFL": "Missing", "COMPFL": "Missing"})
    .groupby(["SAFFL", "ITTFL", "COMPFL"], dropna=False)
    .size()
    .reset_index(name="COUNT")
    .assign(
        PCT=lambda df: (df["COUNT"] / df["COUNT"].sum() * 100).round(2)
    )
    .sort_values(["SAFFL", "ITTFL", "COMPFL"])
    .reset_index(drop=True)
)

print(freq_table.to_string(index=False))
print(f"\nTotal subjects: {len(adsl_final)}")
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
