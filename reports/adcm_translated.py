# Translated from: adcm.sas | ClinTranslate v4 Agentic
# ============================================================
# Program  : adcm.py
# Study    : BMN-999-001
# Purpose  : ADCM - Concomitant Medications Analysis Dataset
# Author   : Clinical Data Engineering (translated)
# Created  : 2024-02-10
# 21 CFR Part 11 Note: All transformations are explicit and
#   traceable. No silent data modification. Source records
#   are preserved; derived variables are additive only.
# ============================================================

import pandas as pd
import numpy as np
import os

# ── Path configuration (mirrors SAS libname assignments) ──
ADAM_PATH = "/data/bmn999/adam"
SDTM_PATH = "/data/bmn999/sdtm"

# ── Load source datasets ──────────────────────────────────────────────────────
# SAS: set sdtm.cm
cm = pd.read_sas(os.path.join(SDTM_PATH, "cm.sas7bdat"), encoding="utf-8")

# SAS: adam.adsl (keep=usubjid trtsdt trtedt saffl armcd)
adsl = pd.read_sas(os.path.join(ADAM_PATH, "adsl.sas7bdat"), encoding="utf-8")
adsl_sub = adsl[["USUBJID", "TRTSDT", "TRTEDT", "SAFFL", "ARMCD"]].copy()

# ── Step 1: Prepare CM domain ─────────────────────────────────────────────────
# SAS: data cm_prep; set sdtm.cm;

cm_prep = cm.copy()

# SAS: cmstdt = input(cmstdtc, yymmdd10.);
# SAS: cmendt = input(cmendtc, yymmdd10.);
# Convert ISO 8601 character dates to datetime; coerce invalid/missing to NaT
cm_prep["CMSTDT"] = pd.to_datetime(
    cm_prep["CMSTDTC"], format="%Y-%m-%d", errors="coerce"
)
cm_prep["CMENDT"] = pd.to_datetime(
    cm_prep["CMENDTC"], format="%Y-%m-%d", errors="coerce"
)

# SAS: atc1 = upcase(substr(cmatc, 1, 1));
# Extract and uppercase the first character of ATC code
cm_prep["ATC1"] = (
    cm_prep["CMATC"]
    .astype(str)
    .str.strip()
    .str[:1]
    .str.upper()
)

# SAS: select (atc1) / when ... / otherwise;
# Map ATC first-level code to therapeutic group label
# SAS label: atcgrp = 'ATC Therapeutic Group'
atc_map = {
    "A": "Alimentary/Metabolism",
    "B": "Blood/Blood Forming",
    "C": "Cardiovascular",
    "J": "Anti-infectives",
    "L": "Antineoplastic",
    "M": "Musculoskeletal",
    "N": "Nervous System",
    "R": "Respiratory",
}
cm_prep["ATCGRP"] = cm_prep["ATC1"].map(atc_map).fillna("Other")
# CDISC label preserved via column-level metadata comment:
# ATCGRP label: 'ATC Therapeutic Group'

# ── Step 2: Sort and merge with ADSL ─────────────────────────────────────────
# SAS: proc sort data=cm_prep; by usubjid cmstdt;
cm_prep = cm_prep.sort_values(
    by=["USUBJID", "CMSTDT"], na_position="last"
).reset_index(drop=True)

# SAS: proc sort data=adam.adsl out=adsl_sub (keep=...); by usubjid;
adsl_sub = adsl_sub.sort_values(by="USUBJID").reset_index(drop=True)

# SAS: merge cm_prep (in=inCM) adsl_sub (in=inADSL); by usubjid;
# SAS: if inCM and inADSL and saffl = 'Y';
# Left-merge CM onto ADSL subset; inner join preserves only matched USUBJID
# Then filter to safety population (SAFFL = 'Y')
adcm_merge = pd.merge(
    cm_prep,
    adsl_sub,
    on="USUBJID",
    how="inner",          # inCM and inADSL both required
    suffixes=("", "_ADSL"),
)

# 21 CFR Part 11: Explicit filter — no records silently dropped without trace
adcm_merge = adcm_merge[adcm_merge["SAFFL"].str.strip() == "Y"].copy()
adcm_merge = adcm_merge.reset_index(drop=True)

# ── Step 3: Derive analysis variables ────────────────────────────────────────
# SAS: data adam.adcm; set adcm_merge;

adcm = adcm_merge.copy()

# Ensure treatment window dates are datetime for arithmetic
for col in ["TRTSDT", "TRTEDT", "CMSTDT", "CMENDT"]:
    if adcm[col].dtype != "datetime64[ns]":
        adcm[col] = pd.to_datetime(adcm[col], errors="coerce")

# ── Treatment-emergent flag ───────────────────────────────────────────────────
# SAS: if cmstdt >= trtsdt and cmstdt <= trtedt + 30 then trtemfl = 'Y';
# SAS label: trtemfl = 'Treatment Emergent Flag'

# Identify records where all three dates are non-missing
dates_present = (
    adcm["CMSTDT"].notna()
    & adcm["TRTSDT"].notna()
    & adcm["TRTEDT"].notna()
)

# Within-window condition: medication started on or after treatment start
# and no more than 30 days after treatment end
within_window = (
    (adcm["CMSTDT"] >= adcm["TRTSDT"])
    & (adcm["CMSTDT"] <= adcm["TRTEDT"] + pd.Timedelta(days=30))
)

# TRTEMFL defaults to 'N'; set 'Y' only when dates present AND within window
adcm["TRTEMFL"] = "N"
adcm.loc[dates_present & within_window, "TRTEMFL"] = "Y"
# TRTEMFL label: 'Treatment Emergent Flag'

# ── Medication duration ───────────────────────────────────────────────────────
# SAS: if cmstdt ne . and cmendt ne . then cmdur = cmendt - cmstdt + 1;
# SAS: else if cmstdt ne . and cmendt = . then cmdur = .;  /* ongoing */
# SAS label: cmdur = 'Medication Duration (Days)'

both_dates = adcm["CMSTDT"].notna() & adcm["CMENDT"].notna()
start_only = adcm["CMSTDT"].notna() & adcm["CMENDT"].isna()

adcm["CMDUR"] = np.nan  # initialise to missing (mirrors SAS missing numeric)
adcm.loc[both_dates, "CMDUR"] = (
    (adcm.loc[both_dates, "CMENDT"] - adcm.loc[both_dates, "CMSTDT"]).dt.days + 1
)
# Records where only start is present remain NaN — ongoing, as per SAS intent
# CMDUR label: 'Medication Duration (Days)'

# ── Relative analysis start day ───────────────────────────────────────────────
# SAS: if trtsdt ne . and cmstdt ne . then
#          astdy = cmstdt - trtsdt + (cmstdt >= trtsdt);
# SAS label: astdy = 'Analysis Start Relative Day'
# Note: SAS date arithmetic skips day 0 (adds 1 for post-baseline days)

has_both_trts = adcm["TRTSDT"].notna() & adcm["CMSTDT"].notna()

delta_days = (
    adcm.loc[has_both_trts, "CMSTDT"] - adcm.loc[has_both_trts, "TRTSDT"]
).dt.days

# SAS: (cmstdt >= trtsdt) evaluates to 1 if True, 0 if False
post_flag = (adcm.loc[has_both_trts, "CMSTDT"] >= adcm.loc[has_both_trts, "TRTSDT"]).astype(int)

adcm["ASTDY"] = np.nan
adcm.loc[has_both_trts, "ASTDY"] = delta_days + post_flag
# ASTDY label: 'Analysis Start Relative Day'

# ── Ongoing flag ──────────────────────────────────────────────────────────────
# SAS: if cmendt = . then ongofl = 'Y'; else ongofl = 'N';
# SAS label: ongofl = 'Ongoing at End of Study Flag'

adcm["ONGOFL"] = np.where(adcm["CMENDT"].isna(), "Y", "N")
# ONGOFL label: 'Ongoing at End of Study Flag'

# ── Final sort (mirrors proc sort) ────────────────────────────────────────────
# SAS: proc sort data=adam.adcm; by usubjid cmstdt cmtrt;
adcm = adcm.sort_values(
    by=["USUBJID", "CMSTDT", "CMTRT"], na_position="last"
).reset_index(drop=True)

# ── Write output dataset ──────────────────────────────────────────────────────
# SAS: data adam.adcm (write to adam libname)
output_path = os.path.join(ADAM_PATH, "adcm.parquet")
adcm.to_parquet(output_path, index=False, engine="pyarrow")
print(f"ADCM written: {output_path} | Rows: {len(adcm):,}")

# ── Frequency tables (replaces PROC FREQ output) ─────────────────────────────
# [REQUIRES_MANUAL_REVIEW: TFL output]
# SAS: proc freq data=adam.adcm; where trtemfl = 'Y'; tables atcgrp / order=freq;
# Title: 'ADCM — Treatment-Emergent Medications by ATC Group'

print("\n" + "=" * 65)
print("ADCM — Treatment-Emergent Medications by ATC Group")
print("=" * 65)

trtem_filter = adcm[adcm["TRTEMFL"] == "Y"].copy()

freq_atcgrp = (
    trtem_filter["ATCGRP"]
    .value_counts()                         # order=freq equivalent
    .reset_index()
)
freq_atcgrp.columns = ["ATCGRP", "COUNT"]
freq_atcgrp["PERCENT"] = (
    freq_atcgrp["COUNT"] / freq_atcgrp["COUNT"].sum() * 100
).round(2)

print(freq_atcgrp.to_string(index=False))

# [REQUIRES_MANUAL_REVIEW: TFL output]
# SAS: proc freq; where trtemfl='Y'; tables armcd * atcgrp / list missing;
# Title: 'ADCM — Medications by Treatment Arm and ATC Group'

print("\n" + "=" * 65)
print("ADCM — Medications by Treatment Arm and ATC Group")
print("(list missing: all combinations including missing cells shown)")
print("=" * 65)

# Replicate SAS 'list' option: explicit cross-tabulation as a flat frequency
freq_arm_atc = (
    trtem_filter
    .groupby(["ARMCD", "ATCGRP"], dropna=False)   # dropna=False mirrors 'missing'
    .size()
    .reset_index(name="COUNT")
    .sort_values(["ARMCD", "ATCGRP"])
    .reset_index(drop=True)
)
total = freq_arm_atc["COUNT"].sum()
freq_arm_atc["PERCENT"] = (freq_arm_atc["COUNT"] / total * 100).round(2)

print(freq_arm_atc.to_string(index=False))