# Translated from: adlb_baseline.sas | ClinTranslate v4 Agentic
# Study: BioMarin BMN-999 — ADLB Baseline Derivation
# Source SAS program: ADLB_BASELINE.sas
# 21 CFR Part 11 Notice: All transformations are explicit and auditable.
#   No silent imputation or overwrite occurs without conditional guard.

import pandas as pd
import numpy as np
from pathlib import Path

# ---------------------------------------------------------------------------
# Library path configuration
# Mirrors SAS: libname adam '/data/adam'; libname sdtm '/data/sdtm';
# ---------------------------------------------------------------------------
SDTM_PATH = Path("/data/sdtm")
ADAM_PATH = Path("/data/adam")

# ---------------------------------------------------------------------------
# Load source SDTM LB dataset
# Mirrors SAS: proc sort data=sdtm.lb out=lb_sorted; by usubjid lbtestcd lbdtc;
# ---------------------------------------------------------------------------
lb_sorted = pd.read_sas(SDTM_PATH / "lb.sas7bdat", encoding="utf-8")

# Preserve all CDISC variable names exactly as loaded from source.
# Sort ascending by USUBJID, LBTESTCD, LBDTC — mirrors SAS PROC SORT key order.
lb_sorted = lb_sorted.sort_values(
    by=["USUBJID", "LBTESTCD", "LBDTC"],
    ascending=True,
    na_position="last",        # NaN dates sort last, consistent with SAS behavior
    ignore_index=True
)

# ---------------------------------------------------------------------------
# Baseline Derivation — mirrors SAS DATA step with RETAIN BASE .;
#
# SAS logic:
#   retain base .;
#   if first.lbtestcd then base = .;           <- reset at group boundary
#   if lbdtc <= rfstdtc then base = lbstresn;  <- last qualifying value wins
#   ablfl = 'Y' for each qualifying row
#
# Python strategy:
#   Because SAS processes row-by-row with RETAIN and overwrites BASE on each
#   qualifying row within the group, the effective baseline is the LAST
#   LBSTRESN where LBDTC <= RFSTDTC within each (USUBJID, LBTESTCD) group.
#   We derive this explicitly without mutation inside a loop to avoid silent
#   row-order dependency errors (21 CFR Part 11 safe).
# ---------------------------------------------------------------------------

# Step 1: Identify rows on or before first dose (LBDTC <= RFSTDTC).
# Both columns are string ISO-8601 dates from SDTM; compare lexicographically.
# If your environment stores these as Python datetime objects, the same
# comparison operator applies without modification.
lb_sorted["_pre_dose_flag"] = (
    lb_sorted["LBDTC"].notna()
    & lb_sorted["RFSTDTC"].notna()
    & (lb_sorted["LBDTC"] <= lb_sorted["RFSTDTC"])
)

# Step 2: Mark ABLFL = 'Y' for every qualifying pre-dose row.
# SAS sets ablfl = 'Y' on all rows where lbdtc <= rfstdtc within the group.
lb_sorted["ABLFL"] = np.where(lb_sorted["_pre_dose_flag"], "Y", np.nan)

# Step 3: Derive BASE as the LAST non-missing LBSTRESN on or before first dose,
# per (USUBJID, LBTESTCD) group.
# SAS RETAIN overwrites on each qualifying row in sort order, so the last
# qualifying row's value persists as the baseline for the whole group.
_baseline_candidates = lb_sorted.loc[
    lb_sorted["_pre_dose_flag"] & lb_sorted["LBSTRESN"].notna()
].copy()

_baseline_per_group = (
    _baseline_candidates
    .groupby(["USUBJID", "LBTESTCD"], sort=False)["LBSTRESN"]
    .last()                   # last() mirrors SAS RETAIN final-value-wins logic
    .reset_index()
    .rename(columns={"LBSTRESN": "BASE"})
)

# Step 4: Merge BASE back onto all rows for the subject-parameter group.
# Mirrors SAS RETAIN broadcasting the retained value across all rows in group.
adlb = lb_sorted.merge(
    _baseline_per_group,
    on=["USUBJID", "LBTESTCD"],
    how="left"                # subjects with no pre-dose values get BASE = NaN
)

# ---------------------------------------------------------------------------
# Change from Baseline (CHG)
# Mirrors SAS: if base ne . and lbstresn ne . then chg = lbstresn - base;
#              else chg = .;
# np.nan propagates naturally in arithmetic, so explicit guard is still
# applied to match SAS conditional intent precisely.
# ---------------------------------------------------------------------------
adlb["CHG"] = np.where(
    adlb["BASE"].notna() & adlb["LBSTRESN"].notna(),
    adlb["LBSTRESN"] - adlb["BASE"],
    np.nan                    # explicit NaN, not 0 — no silent data modification
)

# ---------------------------------------------------------------------------
# Percent Change from Baseline (PCHG)
# Mirrors SAS: if base ne 0 and base ne . then pchg = (chg / base) * 100;
#              else pchg = .;
# Guard against division by zero explicitly, consistent with SAS condition.
# ---------------------------------------------------------------------------
adlb["PCHG"] = np.where(
    adlb["BASE"].notna() & (adlb["BASE"] != 0),
    (adlb["CHG"] / adlb["BASE"]) * 100,
    np.nan
)

# ---------------------------------------------------------------------------
# Variable labels — stored as column-level metadata in the DataFrame attrs
# dict for downstream documentation and dataset export.
# Mirrors SAS LABEL statement inside DATA step.
# ---------------------------------------------------------------------------
_variable_labels = {
    "BASE":  "Baseline Value",
    "CHG":   "Change from Baseline",
    "PCHG":  "Percent Change from Baseline",
    "ABLFL": "Baseline Record Flag",
}
adlb.attrs["variable_labels"] = _variable_labels

# ---------------------------------------------------------------------------
# Drop internal working column — not part of ADaM spec output.
# ---------------------------------------------------------------------------
adlb = adlb.drop(columns=["_pre_dose_flag"])

# ---------------------------------------------------------------------------
# Final sort to mirror SAS dataset output order.
# Mirrors SAS: by usubjid lbtestcd lbdtc (carried through from PROC SORT)
# ---------------------------------------------------------------------------
adlb = adlb.sort_values(
    by=["USUBJID", "LBTESTCD", "LBDTC"],
    ascending=True,
    na_position="last",
    ignore_index=True
)

# ---------------------------------------------------------------------------
# Write ADLB output dataset
# Mirrors SAS: data adam.adlb; ... run;
# Using pyreadstat to write .sas7bdat with variable labels if available.
# ---------------------------------------------------------------------------
try:
    import pyreadstat
    pyreadstat.write_sas7bdat(
        adlb,
        str(ADAM_PATH / "adlb.sas7bdat"),
        column_labels=[
            _variable_labels.get(col, col) for col in adlb.columns
        ]
    )
except ImportError:
    # Fallback: write to CSV with audit trail note — do not silently skip
    adlb.to_csv(ADAM_PATH / "adlb.csv", index=False)
    import warnings
    warnings.warn(
        "pyreadstat not available — ADLB written to CSV. "
        "Replace with SAS7BDAT output before GxP submission.",
        UserWarning,
        stacklevel=2
    )

# ---------------------------------------------------------------------------
# Summary Statistics
# Mirrors SAS: proc means data=adam.adlb n mean std min max;
#              class lbtestcd;
#              var lbstresn chg pchg;
#              output out=adlb_summ mean=mean_val std=std_val;
#
# [REQUIRES_MANUAL_REVIEW: TFL output]
# The PROC MEANS output dataset (adlb_summ) is replicated here as a
# pandas groupby aggregation. If this feeds an ODS RTF/PDF table, the
# formatting layer must be rebuilt separately using a TFL tool
# (e.g., Tplyr, pharmaRTF, or an internal SAS macro equivalent).
# ---------------------------------------------------------------------------
_summary_vars = ["LBSTRESN", "CHG", "PCHG"]

adlb_summ = (
    adlb
    .groupby("LBTESTCD", sort=True, dropna=False)[_summary_vars]
    .agg(
        n=("LBSTRESN", "count"),        # SAS N statistic — non-missing count only
        mean_val=("LBSTRESN", "mean"),  # mirrors output mean=mean_val
        std_val=("LBSTRESN", "std"),    # mirrors output std=std_val
        min_val=("LBSTRESN", "min"),
        max_val=("LBSTRESN", "max"),
    )
    .reset_index()
)

# Compute mean/std for CHG and PCHG as separate columns to fully mirror
# PROC MEANS multi-variable output across CLASS levels.
for _var in ["CHG", "PCHG"]:
    _agg = (
        adlb
        .groupby("LBTESTCD", sort=True, dropna=False)[_var]
        .agg(
            n="count",
            mean_val="mean",
            std_val="std",
            min_val="min",
            max_val="max",
        )
        .reset_index()
        .rename(columns={
            "n":        f"n_{_var}",
            "mean_val": f"mean_{_var}",
            "std_val":  f"std_{_var}",
            "min_val":  f"min_{_var}",
            "max_val":  f"max_{_var}",
        })
    )
    adlb_summ = adlb_summ.merge(_agg, on="LBTESTCD", how="left")

# Write summary output — mirrors SAS: output out=adlb_summ
adlb_summ.to_csv(ADAM_PATH / "adlb_summ.csv", index=False)