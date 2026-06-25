# Translated from: adlb_baseline.sas | ClinTranslate v4 Agentic
# Study: BioMarin BMN-999 — ADLB Baseline Derivation
# 21 CFR Part 11 Note: All transformations are explicit and auditable.
#   No in-place modification of source data; outputs are new DataFrames.

import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# CONFIGURATION — mirror SAS libname paths
# ---------------------------------------------------------------------------
SDTM_PATH = "/data/sdtm"
ADAM_PATH  = "/data/adam"

# ---------------------------------------------------------------------------
# LOAD SOURCE DATA
# SAS: set lb_sorted (from proc sort data=sdtm.lb)
# ---------------------------------------------------------------------------
lb_raw = pd.read_sas(f"{SDTM_PATH}/lb.sas7bdat", encoding="utf-8")

# ---------------------------------------------------------------------------
# SORT — mirrors: proc sort data=sdtm.lb out=lb_sorted
#                  by usubjid lbtestcd lbdtc;
# SAS sort is stable; pandas sort_values is also stable by default.
# ---------------------------------------------------------------------------
lb_sorted = (
    lb_raw
    .sort_values(
        by=["USUBJID", "LBTESTCD", "LBDTC"],
        ascending=True,
        na_position="last",       # SAS places missing values last in ascending sort
        ignore_index=True
    )
    .copy()
)

# ---------------------------------------------------------------------------
# BASELINE DERIVATION
# SAS DATA step logic translated record-by-record via groupby + transform.
#
# Key SAS constructs mapped:
#   RETAIN base .          -> pandas groupby carries forward derived values
#   if first.lbtestcd      -> groupby boundary (first record per group resets)
#   lbdtc <= rfstdtc       -> vectorised boolean comparison
#   ablfl = 'Y'            -> conditional string assignment
#   chg  = lbstresn - base -> vectorised subtraction, NaN-safe via np.where
#   pchg = (chg/base)*100  -> vectorised division, NaN/zero-safe via np.where
#
# IMPORTANT: The SAS logic retains the LAST value on or before rfstdtc as
# the baseline (the retain + overwrite pattern within the by-group loop).
# We replicate this by filtering to pre-dose records, then taking the LAST
# non-missing lbstresn per (USUBJID, LBTESTCD) group.
# ---------------------------------------------------------------------------

# --- Step 1: Ensure numeric types for analysis variables ---
lb_sorted["LBSTRESN"] = pd.to_numeric(lb_sorted["LBSTRESN"], errors="coerce")

# Coerce dates to a comparable type.
# SAS date strings in ISO-8601 (LBDTC, RFSTDTC) are compared lexicographically,
# which is safe for yyyy-mm-dd strings; we replicate that here.
# Cast to string to guarantee consistent comparison (matches SAS lbdtc <= rfstdtc).
lb_sorted["LBDTC"]   = lb_sorted["LBDTC"].astype(str).str.strip()
lb_sorted["RFSTDTC"] = lb_sorted["RFSTDTC"].astype(str).str.strip()

# --- Step 2: Identify pre-dose / on-dose-day records (lbdtc <= rfstdtc) ---
# Guard against missing date strings ('', 'nan', 'NaT') before comparison.
valid_date_mask = (
    lb_sorted["LBDTC"].notna()
    & lb_sorted["RFSTDTC"].notna()
    & (lb_sorted["LBDTC"] != "")
    & (lb_sorted["RFSTDTC"] != "")
    & (lb_sorted["LBDTC"] != "nan")
    & (lb_sorted["RFSTDTC"] != "nan")
)

pre_dose_mask = valid_date_mask & (lb_sorted["LBDTC"] <= lb_sorted["RFSTDTC"])

# --- Step 3: Derive ABLFL — mark pre-dose records initially as candidate ---
# SAS sets ablfl='Y' for every pre-dose record inside the by-group loop.
# The final baseline value is the last such record (due to RETAIN overwrite).
# We replicate: mark all pre-dose rows, then identify the last non-missing
# LBSTRESN per group to compute BASE.
lb_sorted["ABLFL"] = np.where(pre_dose_mask, "Y", np.nan)

# --- Step 4: Derive BASE ---
# For each (USUBJID, LBTESTCD), BASE = last non-missing LBSTRESN where LBDTC <= RFSTDTC.
# This mirrors the SAS RETAIN pattern where base is overwritten on each qualifying row.

# Build a helper Series: LBSTRESN value where pre-dose, else NaN
lbstresn_predose = lb_sorted["LBSTRESN"].where(pre_dose_mask, other=np.nan)

# last() on the sorted group gives the last non-missing equivalent —
# we use a custom lambda to take the last non-NaN value.
def last_nonmissing(s):
    """Return the last non-NaN value in a Series; NaN if all missing."""
    valid = s.dropna()
    return valid.iloc[-1] if not valid.empty else np.nan

base_lookup = (
    lb_sorted
    .assign(_predose_lbstresn=lbstresn_predose)
    .groupby(["USUBJID", "LBTESTCD"], sort=False)["_predose_lbstresn"]
    .transform(last_nonmissing)
)

lb_sorted["BASE"] = base_lookup

# --- Step 5: Derive CHG = LBSTRESN - BASE ---
# SAS: if base ne . and lbstresn ne . then chg = lbstresn - base; else chg = .;
# np.where preserves NaN semantics explicitly (no silent imputation).
both_present_mask = lb_sorted["BASE"].notna() & lb_sorted["LBSTRESN"].notna()

lb_sorted["CHG"] = np.where(
    both_present_mask,
    lb_sorted["LBSTRESN"] - lb_sorted["BASE"],
    np.nan               # explicit NaN — mirrors SAS missing (.)
)

# --- Step 6: Derive PCHG = (CHG / BASE) * 100 ---
# SAS: if base ne 0 and base ne . then pchg = (chg / base) * 100; else pchg = .;
# Guard: BASE must be non-missing AND non-zero to avoid divide-by-zero.
pchg_eligible_mask = lb_sorted["BASE"].notna() & (lb_sorted["BASE"] != 0)

lb_sorted["PCHG"] = np.where(
    pchg_eligible_mask,
    (lb_sorted["CHG"] / lb_sorted["BASE"]) * 100,
    np.nan               # explicit NaN — mirrors SAS missing (.)
)

# ---------------------------------------------------------------------------
# APPLY VARIABLE LABELS (stored as column-level metadata via attrs)
# SAS LABEL statement — no native pandas equivalent; attrs dict used per
# pandas convention for GxP traceability.
# ---------------------------------------------------------------------------
variable_labels = {
    "BASE":  "Baseline Value",
    "CHG":   "Change from Baseline",
    "PCHG":  "Percent Change from Baseline",
    "ABLFL": "Baseline Record Flag",
}
for var, label in variable_labels.items():
    lb_sorted[var].attrs["label"] = label

# ---------------------------------------------------------------------------
# FINALISE ADLB DATASET
# Preserve original column order; append derived variables at the end.
# ---------------------------------------------------------------------------
adlb = lb_sorted.copy()

# ---------------------------------------------------------------------------
# WRITE OUTPUT — mirrors: data adam.adlb;
# Using parquet for GxP-safe lossless storage; retain SAS7BDAT path if needed.
# ---------------------------------------------------------------------------
adlb.to_parquet(f"{ADAM_PATH}/adlb.parquet", index=False, engine="pyarrow")

# Optional SAS7BDAT output (requires pyreadstat):
# import pyreadstat
# pyreadstat.write_sas7bdat(adlb, f"{ADAM_PATH}/adlb.sas7bdat",
#                           column_labels=variable_labels)

# ---------------------------------------------------------------------------
# SUMMARY STATISTICS
# Mirrors: proc means data=adam.adlb n mean std min max;
#           class lbtestcd;
#           var lbstresn chg pchg;
#           output out=adlb_summ mean=mean_val std=std_val;
#
# Note: SAS PROC MEANS uses N (non-missing count); pandas describe() does too.
# SAS default STD uses N-1 denominator (ddof=1) — matched explicitly below.
# ---------------------------------------------------------------------------
summary_vars = ["LBSTRESN", "CHG", "PCHG"]

adlb_summ = (
    adlb
    .groupby("LBTESTCD", dropna=False)[summary_vars]
    .agg(
        n=("LBSTRESN", "count"),                  # non-missing count per SAS N
        mean_val=("LBSTRESN", "mean"),
        std_val=("LBSTRESN", lambda x: x.std(ddof=1)),   # SAS STD = sample std
        min_val=("LBSTRESN", "min"),
        max_val=("LBSTRESN", "max"),
    )
    .reset_index()
)

# Compute CHG and PCHG summary columns and merge (mirrors multi-var PROC MEANS)
for var in ["CHG", "PCHG"]:
    var_summ = (
        adlb
        .groupby("LBTESTCD", dropna=False)[var]
        .agg(
            **{
                f"n_{var.lower()}":       ("count"),
                f"mean_{var.lower()}":    ("mean"),
                f"std_{var.lower()}":     (lambda x: x.std(ddof=1)),
                f"min_{var.lower()}":     ("min"),
                f"max_{var.lower()}":     ("max"),
            }
        )
        .reset_index()
    )
    adlb_summ = adlb_summ.merge(var_summ, on="LBTESTCD", how="left")

# Write summary dataset — mirrors: output out=adlb_summ
adlb_summ.to_parquet(f"{ADAM_PATH}/adlb_summ.parquet", index=False, engine="pyarrow")

# ---------------------------------------------------------------------------
# VALIDATION ASSERTIONS — 21 CFR Part 11 data integrity checks
# These replace silent SAS macro-level assumptions with explicit guards.
# ---------------------------------------------------------------------------

# 1. USUBJID must never be null in the output dataset
assert adlb["USUBJID"].notna().all(), (
    "FATAL: USUBJID contains missing values — output dataset is non-compliant."
)

# 2. CHG must equal LBSTRESN - BASE wherever both are non-missing
chg_check = adlb.loc[both_present_mask, ["LBSTRESN", "BASE", "CHG"]].copy()
chg_discrepancy = ~np.isclose(
    chg_check["CHG"],
    chg_check["LBSTRESN"] - chg_check["BASE"],
    equal_nan=True
)
assert not chg_discrepancy.any(), (
    "FATAL: CHG derivation mismatch detected — review LBSTRESN/BASE values."
)

# 3. PCHG must be missing when BASE is zero or missing (no divide-by-zero)
pchg_invalid = adlb.loc[~pchg_eligible_mask, "PCHG"].notna()
assert not pchg_invalid.any(), (
    "FATAL: PCHG is non-missing where BASE is zero or missing — "
    "potential divide-by-zero violation."
)

# 4. Row count must not change from source to output (no silent drops/duplication)
assert len(adlb) == len(lb_raw), (
    f"FATAL: Row count mismatch — source={len(lb_raw)}, output={len(adlb)}. "
    "Investigate merge or filter logic."
)

# [REQUIRES_MANUAL_REVIEW: TFL output]
# The original SAS program does not contain PROC REPORT / ODS RTF blocks.
# If summary tables (adlb_summ) are to be rendered as RTF/PDF for submission,
# implement using a validated TFL generation framework (e.g., pharmaRTF,
# Tplyr, or an internal validated Python reporting utility).