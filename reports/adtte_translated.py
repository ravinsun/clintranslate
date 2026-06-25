# Translated from: adtte.sas | ClinTranslate v4 Agentic
# Study    : BMN-999-001
# Purpose  : Create ADTTE - Time to First AE Analysis Dataset
# Source   : Clinical Data Engineering (SAS original: 2024-02-01)
# Notes    : PROC LIFETEST replaced with lifelines KaplanMeierFitter
#            21 CFR Part 11: no silent data modification — all merges audited
#            via assertion checks and row-count logging.

import pandas as pd
import numpy as np
import logging
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging setup — provides audit trail consistent with 21 CFR Part 11
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path configuration — mirrors SAS libname declarations
#   libname adam '/data/bmn999/adam'
#   libname sdtm '/data/bmn999/sdtm'
# ---------------------------------------------------------------------------
ADAM_DIR = Path("/data/bmn999/adam")
SDTM_DIR = Path("/data/bmn999/sdtm")

# ===========================================================================
# Step 1: Load source datasets
#   SAS: proc sort data=sdtm.ae out=ae_sorted; by usubjid aestdtc;
# ===========================================================================

# Load SDTM AE dataset
ae_raw = pd.read_sas(SDTM_DIR / "ae.sas7bdat", encoding="utf-8")
log.info("AE loaded: %d rows, %d cols", len(ae_raw), ae_raw.shape[1])

# Normalise column names to uppercase — CDISC convention
ae_raw.columns = ae_raw.columns.str.upper().str.strip()

# Retain only required variables before sort (mirrors SAS KEEP= later)
ae_cols_required = ["USUBJID", "AESTDTC", "AESEV", "AESER"]
missing_ae_cols = [c for c in ae_cols_required if c not in ae_raw.columns]
if missing_ae_cols:
    raise KeyError(
        f"[21CFR11-GUARD] AE dataset missing required columns: {missing_ae_cols}"
    )
ae_raw = ae_raw[ae_cols_required].copy()

# ---------------------------------------------------------------------------
# SAS: proc sort data=sdtm.ae out=ae_sorted; by usubjid aestdtc;
# Sort AE by subject then start date — ensures first.usubjid logic is correct
# ---------------------------------------------------------------------------
ae_sorted = ae_raw.sort_values(
    by=["USUBJID", "AESTDTC"],
    ascending=[True, True],
    na_position="last",          # missing dates sink to bottom, matching SAS
).reset_index(drop=True)

# ---------------------------------------------------------------------------
# SAS DATA step: ae_first — keep first record per subject (first.usubjid)
#   first_ae_dt = input(aestdtc, yymmdd10.)
# ---------------------------------------------------------------------------
ae_first = (
    ae_sorted
    .groupby("USUBJID", sort=False)   # groups already sorted above
    .first()                           # equiv: if first.usubjid;
    .reset_index()
)

# Parse ISO-8601 date string to datetime — mirrors input(aestdtc, yymmdd10.)
# Partial dates (YYYY-MM only) are coerced to NaT; flag for QC awareness
ae_first["FIRST_AE_DT"] = pd.to_datetime(
    ae_first["AESTDTC"], format="%Y-%m-%d", errors="coerce"
)

n_partial = ae_first["FIRST_AE_DT"].isna().sum()
if n_partial > 0:
    log.warning(
        "[DATE-PARSE] %d AESTDTC value(s) could not be parsed to full dates "
        "(possible partial dates). FIRST_AE_DT set to NaT for those records.",
        n_partial,
    )

# Retain only fields needed for downstream merge
ae_first = ae_first[["USUBJID", "FIRST_AE_DT", "AESEV", "AESER"]].copy()
log.info("AE first-event records: %d subjects", len(ae_first))

# ===========================================================================
# Step 2: Load ADSL and merge with ae_first
#   SAS: merge adam.adsl(keep=...) ae_first; by usubjid; if inADSL and saffl='Y'
# ===========================================================================
adsl_raw = pd.read_sas(ADAM_DIR / "adsl.sas7bdat", encoding="utf-8")
adsl_raw.columns = adsl_raw.columns.str.upper().str.strip()
log.info("ADSL loaded: %d rows", len(adsl_raw))

adsl_cols_required = ["USUBJID", "TRTSDT", "TRTEDT", "SAFFL", "ARMCD"]
missing_adsl_cols = [c for c in adsl_cols_required if c not in adsl_raw.columns]
if missing_adsl_cols:
    raise KeyError(
        f"[21CFR11-GUARD] ADSL dataset missing required columns: {missing_adsl_cols}"
    )

adsl = adsl_raw[adsl_cols_required].copy()

# Convert SAS numeric dates (days since 1960-01-01) to pandas Timestamp
# SAS epoch = 1960-01-01; pd.Timestamp("1960-01-01") + pd.to_timedelta(n, 'D')
SAS_EPOCH = pd.Timestamp("1960-01-01")

for date_col in ["TRTSDT", "TRTEDT"]:
    if pd.api.types.is_numeric_dtype(adsl[date_col]):
        adsl[date_col] = SAS_EPOCH + pd.to_timedelta(adsl[date_col], unit="D")
        log.info("Converted SAS numeric date column: %s", date_col)
    else:
        # Already a date-like string — attempt parse
        adsl[date_col] = pd.to_datetime(adsl[date_col], errors="coerce")

# ---------------------------------------------------------------------------
# Safety population filter — mirrors: if inADSL and saffl = 'Y'
# Applied BEFORE merge to avoid inadvertent subject inclusion
# ---------------------------------------------------------------------------
n_adsl_pre = len(adsl)
adsl_safe = adsl.loc[adsl["SAFFL"].str.strip() == "Y"].copy()
log.info(
    "ADSL safety filter (SAFFL='Y'): %d -> %d records",
    n_adsl_pre,
    len(adsl_safe),
)

# ---------------------------------------------------------------------------
# Left merge ADSL onto ae_first — mirrors SAS MERGE with in= flags
#   inADSL = all ADSL subjects retained (left)
#   inAE   = AE subjects that match (indicator = not-null FIRST_AE_DT)
# ---------------------------------------------------------------------------
adtte_base = adsl_safe.merge(
    ae_first,
    on="USUBJID",
    how="left",          # SAS: if inADSL — all ADSL rows retained
    indicator=False,
)
log.info("Post-merge ADTTE base: %d rows", len(adtte_base))

# Derive event flag — mirrors: if inAE then evntfl='Y'; else evntfl='N'
# A subject has an AE record when FIRST_AE_DT is not NaT
adtte_base["EVNTFL"] = np.where(
    adtte_base["FIRST_AE_DT"].notna(), "Y", "N"
)

# ---------------------------------------------------------------------------
# Derive ADT (analysis end date)
#   if inAE        then adt = first_ae_dt;
#   else if trtedt then adt = trtedt + 1;   /* censored: last dose + 1 day */
#   else                adt = trtsdt;
# ---------------------------------------------------------------------------
adtte_base["ADT"] = np.where(
    adtte_base["EVNTFL"] == "Y",
    adtte_base["FIRST_AE_DT"],                          # event: use AE date
    np.where(
        adtte_base["TRTEDT"].notna(),
        adtte_base["TRTEDT"] + pd.Timedelta(days=1),    # censored: last dose + 1
        adtte_base["TRTSDT"],                            # fallback: trt start
    ),
)
# Ensure consistent dtype — np.where with mixed types can downcast
adtte_base["ADT"] = pd.to_datetime(adtte_base["ADT"])

# ===========================================================================
# Step 3: Compute time-to-event and derived variables
#   SAS: data adam.adtte; set adtte_base;
# ===========================================================================
adtte = adtte_base.copy()

# ---------------------------------------------------------------------------
# AVAL: time to event in days — mirrors:
#   if trtsdt ne . and adt ne . then aval = adt - trtsdt + 1;
# Note: SAS date subtraction returns integer days; .days preserves that.
# ---------------------------------------------------------------------------
aval_mask = adtte["TRTSDT"].notna() & adtte["ADT"].notna()

adtte["AVAL"] = np.where(
    aval_mask,
    (adtte["ADT"] - adtte["TRTSDT"]).dt.days + 1,   # +1 inclusive, as SAS
    np.nan,
)
adtte["AVAL"] = adtte["AVAL"].astype(float)          # explicit float — no int NaN

# Guard: AVAL must be positive for interpretable time-to-event data
n_nonpositive = (adtte["AVAL"].notna() & (adtte["AVAL"] <= 0)).sum()
if n_nonpositive > 0:
    log.warning(
        "[21CFR11-GUARD] %d record(s) have AVAL <= 0. "
        "AVALOG will be NaN for these records. Investigate date discrepancies.",
        n_nonpositive,
    )

# ---------------------------------------------------------------------------
# CNSR: censoring indicator
#   SAS: if evntfl='Y' then cnsr=0; else cnsr=1;
#   CDISC ADTTE convention: 0=event, 1=censored
# ---------------------------------------------------------------------------
adtte["CNSR"] = np.where(adtte["EVNTFL"] == "Y", 0, 1).astype(int)

# ---------------------------------------------------------------------------
# AVALOG: log of analysis value — mirrors:
#   if aval > 0 then avalog = log(aval); else avalog = .;
# ---------------------------------------------------------------------------
adtte["AVALOG"] = np.where(
    adtte["AVAL"] > 0,
    np.log(adtte["AVAL"]),   # natural log — same as SAS LOG()
    np.nan,
)

# ---------------------------------------------------------------------------
# SEVN: numeric severity at first event
#   SAS: if evntfl='Y' then do; if aesev='MILD' then sevn=1; ...
# ---------------------------------------------------------------------------
sev_map = {"MILD": 1, "MODERATE": 2, "SEVERE": 3}

adtte["SEVN"] = np.where(
    adtte["EVNTFL"] == "Y",
    adtte["AESEV"].str.strip().map(sev_map),   # unmapped values -> NaN
    np.nan,
)
adtte["SEVN"] = pd.to_numeric(adtte["SEVN"], errors="coerce")

# ---------------------------------------------------------------------------
# Parameter descriptors — constant across all rows, matching SAS assignments
# ---------------------------------------------------------------------------
adtte["PARAM"]   = "Time to First Adverse Event (Days)"
adtte["PARAMCD"] = "TTFAE"                 # always uppercase per CDISC
adtte["PARAMU"]  = "Days"

# ---------------------------------------------------------------------------
# Variable labels — stored as column-level metadata in a companion dict
# (pandas does not natively support SAS-style labels; store for TFL use)
# ---------------------------------------------------------------------------
VARIABLE_LABELS = {
    "AVAL":    "Analysis Value (Days to Event)",
    "CNSR":    "Censor Flag (0=Event, 1=Censored)",
    "AVALOG":  "Log Analysis Value",
    "EVNTFL":  "Event Flag",
    "PARAM":   "Parameter",
    "PARAMCD": "Parameter Code",
    "PARAMU":  "Parameter Units",
    "SEVN":    "Numeric Severity at First Event",
    "ADT":     "Analysis End Date",
}
log.info("Variable labels defined for %d columns.", len(VARIABLE_LABELS))

# ---------------------------------------------------------------------------
# Final sort — mirrors: proc sort data=adam.adtte; by usubjid paramcd;
# ---------------------------------------------------------------------------
adtte = adtte.sort_values(
    by=["USUBJID", "PARAMCD"],
    ascending=[True, True],
    na_position="last",
).reset_index(drop=True)

# ---------------------------------------------------------------------------
# Column ordering — place key CDISC variables first for readability
# ---------------------------------------------------------------------------
lead_cols = [
    "USUBJID", "ARMCD", "SAFFL",
    "PARAMCD", "PARAM", "PARAMU",
    "TRTSDT", "TRTEDT", "ADT",
    "AVAL", "AVALOG", "CNSR",
    "EVNTFL", "AESEV", "AESER", "SEVN",
]
remaining_cols = [c for c in adtte.columns if c not in lead_cols]
adtte = adtte[lead_cols + remaining_cols]

# ===========================================================================
# Write output dataset
#   SAS: data adam.adtte; (saved to libname adam)
# Using parquet for lossless round-trip; swap to .sas7bdat via pyreadstat
# if site SOP requires SAS-native output.
# ===========================================================================
output_path = ADAM_DIR / "adtte.parquet"
adtte.to_parquet(output_path, index=False, engine="pyarrow")
log.info("ADTTE written: %d rows x %d cols -> %s", len(adtte), adtte.shape[1], output_path)

# Row-count audit — non-negotiable for GxP traceability
log.info("ADSL safety pop n=%d | ADTTE final n=%d", len(adsl_safe), len(adtte))
assert len(adtte) == len(adsl_safe), (
    "[21CFR11-GUARD] Row count mismatch: ADTTE row count does not equal "
    "ADSL safety population count. Investigate merge logic."
)

# ===========================================================================
# [REQUIRES_MANUAL_REVIEW: TFL output]
# The block below replaces PROC LIFETEST with lifelines KaplanMeierFitter.
# Output is programmatic only — ODS RTF / formatted KM tables require a
# validated TFL program. Review output against validated SAS listing before
# use in a regulatory submission.
#
# Original SAS:
#   proc lifetest data=adam.adtte notable;
#       time aval * cnsr(1);
#       strata armcd;
#       title 'Time to First AE — KM Summary BMN-999-001';
#   run;
# ===========================================================================
try:
    from lifelines import KaplanMeierFitter

    log.info("Running Kaplan-Meier analysis stratified by ARMCD.")

    # Restrict to estimable records: AVAL must be positive and non-missing
    km_data = adtte.loc[adtte["AVAL"].notna() & (adtte["AVAL"] > 0)].copy()

    # CNSR=1 means censored in SAS PROC LIFETEST cnsr(1) syntax
    # lifelines event_observed = 1 means event occurred (inverse of CNSR)
    km_data["EVENT_OBSERVED"] = (km_data["CNSR"] == 0).astype(int)

    strata_groups = km_data["ARMCD"].dropna().unique()
    kmf = KaplanMeierFitter()

    km_summary_frames = []

    for arm in sorted(strata_groups):
        arm_data = km_data.loc[km_data["ARMCD"] == arm]
        kmf.fit(
            durations=arm_data["AVAL"],
            event_observed=arm_data["EVENT_OBSERVED"],
            label=str(arm),
        )
        arm_summary = kmf.survival_function_.copy()
        arm_summary.columns = ["KM_ESTIMATE"]
        arm_summary["ARMCD"] = arm
        arm_summary.index.name = "TIME"
        arm_summary = arm_summary.reset_index()
        km_summary_frames.append(arm_summary)

        log.info(
            "KM | ARMCD=%-10s | n=%d | events=%d | median survival=%.1f days",
            arm,
            len(arm_data),
            arm_data["EVENT_OBSERVED"].sum(),
            kmf.median_survival_time_,
        )

    km_summary = pd.concat(km_summary_frames, ignore_index=True)
    km_output_path = ADAM_DIR / "adtte_km_summary.parquet"
    km_summary.to_parquet(km_output_path, index=False, engine="pyarrow")
    log.info("KM summary written -> %s", km_output_path)

except ImportError:
    log.warning(
        "[REQUIRES_MANUAL_REVIEW: TFL output] "
        "lifelines package not available. Install via: pip install lifelines. "
        "PROC LIFETEST equivalent was not executed."
    )