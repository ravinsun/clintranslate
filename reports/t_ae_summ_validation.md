# ClinTranslate v4 — Validation Report
**File:** t_ae_summ.sas  
**Generated:** 2026-06-25 14:47:54  
**Tool:** ClinTranslate v4 Agentic Pipeline  
**Disclaimer:** Translated output requires IQ/OQ/PQ validation before use in any GxP/submission context.

---

## 1. Translation Decision
| Field | Value |
|---|---|
| Routing Decision | 🟡 REVIEW_REQUIRED |
| Routing Reason | Medium cosine similarity (0.6782) — translation likely correct but requires reviewer confirmation |
| Cosine Similarity Score | 0.6782 |
| Syntax Validation | VALID |
| Self-Correction Attempts | 0 |

---

## 2. Performance Metrics
| Metric | Value |
|---|---|
| SAS Lines of Code | 85 |
| Python Lines of Code | 209 |
| Agent Translation Time | 47.9s (0.8 min) |
| Manual Estimate (baseline) | 2.5 hrs |
| Estimated Time Saved | 2.4867 hrs (99.5%) |

---

## 3. TFL / Output Detection
⚠️ YES — PROC REPORT / ODS RTF detected. Manual TFL review required.

---

## 4. Translated Python Output
```python
# Translated from: t_ae_summ.sas | ClinTranslate v4 Agentic
# Study    : BMN-999-001
# Purpose  : Table 14.3.1 — Adverse Events Summary
# Author   : Clinical Data Engineering (SAS->Python translation)
# Created  : 2024-03-01
# Notes    : PROC REPORT / ODS RTF blocks flagged for manual review.
#            All variable names preserved per CDISC ADaM specification.
#            21 CFR Part 11 awareness: no silent data modification;
#            all filter/merge operations are explicit and auditable.

import pandas as pd
import numpy as np
import os

# ── Configuration ──────────────────────────────────────────────────────────────
# SAS libname adam '/data/bmn999/adam'  →  Python path constants
ADAM_DIR   = "/data/bmn999/adam"
OUTPUT_DIR = "/output/bmn999/tables"

# Input dataset paths (SAS datasets → parquet or CSV; adjust extension as needed)
ADAE_PATH = os.path.join(ADAM_DIR, "adae.parquet")
ADSL_PATH = os.path.join(ADAM_DIR, "adsl.parquet")

# ── Load source datasets ───────────────────────────────────────────────────────
# SAS: proc sort data=adam.adae ... / proc freq data=adam.adsl ...
adae_raw = pd.read_parquet(ADAE_PATH)
adsl_raw = pd.read_parquet(ADSL_PATH)

# Defensive copy — never mutate source frames (21 CFR Part 11: no silent modification)
adae_raw = adae_raw.copy()
adsl_raw = adsl_raw.copy()

# Normalise column names to uppercase to match CDISC variable naming conventions
adae_raw.columns = adae_raw.columns.str.upper()
adsl_raw.columns = adsl_raw.columns.str.upper()

# ── Step 1: Derive treatment-emergent AE working dataset ──────────────────────
# SAS: where trtemfl = 'Y' and saffl = 'Y'; by usubjid aedecod aestdtc;
adae_te = (
    adae_raw
    .loc[
        (adae_raw["TRTEMFL"] == "Y") & (adae_raw["SAFFL"] == "Y")
    ]
    # SAS proc sort: by usubjid aedecod aestdtc
    .sort_values(["USUBJID", "AEDECOD", "AESTDTC"])
    .reset_index(drop=True)
)

# ── Helper: deduplicate to one record per subject ──────────────────────────────
# SAS pattern:  by usubjid; if first.usubjid;
# Python: drop_duplicates on USUBJID keeps the first row after sort — equivalent
#         to SAS first.usubjid within a BY group.
def first_per_subject(df, category_label):
    """
    Mirror SAS 'if first.usubjid' within a sorted BY group.
    Returns one row per USUBJID with ARMCD and the category label attached.
    Only USUBJID and ARMCD are retained; no other AE variables are carried
    forward, preventing unintended data modification.
    """
    deduped = (
        df[["USUBJID", "ARMCD"]]          # retain only columns needed downstream
        .drop_duplicates(subset="USUBJID", keep="first")
        .copy()
    )
    deduped["CATEGORY"] = category_label  # SAS: category = '...'
    return deduped


# ── Any AE (all subjects in adae_te, one row per subject) ─────────────────────
# SAS data ae_any: set adae_te; by usubjid; if first.usubjid;
ae_any = first_per_subject(adae_te, "Subjects with any AE")

# ── Serious AEs ───────────────────────────────────────────────────────────────
# SAS: where aeser = 'Y'; by usubjid; if first.usubjid;
ae_ser = first_per_subject(
    adae_te.loc[adae_te["AESER"] == "Y"],
    "Subjects with any SAE"
)

# ── AEs leading to discontinuation ───────────────────────────────────────────
# SAS: where aeacn = 'DRUG WITHDRAWN'; by usubjid; if first.usubjid;
ae_disc = first_per_subject(
    adae_te.loc[adae_te["AEACN"] == "DRUG WITHDRAWN"],
    "AE leading to discontinuation"
)

# ── Grade 3+ AEs ─────────────────────────────────────────────────────────────
# SAS: where aesevn >= 3; by usubjid; if first.usubjid;
# AESEVN is the numeric severity (1=MILD, 2=MODERATE, 3=SEVERE …)
ae_gr3 = first_per_subject(
    adae_te.loc[adae_te["AESEVN"] >= 3],
    "Grade 3 or higher AE"
)

# ── Stack all category datasets ───────────────────────────────────────────────
# SAS: data ae_all; set ae_any ae_ser ae_disc ae_gr3;
ae_all = pd.concat(
    [ae_any, ae_ser, ae_disc, ae_gr3],
    ignore_index=True
)

# ── Step 2: Denominator — subjects in safety population per arm ───────────────
# SAS: proc freq data=adam.adsl where saffl='Y'; tables armcd / out=denom;
# ARMCD = planned treatment arm code (CDISC ADaM)
denom = (
    adsl_raw
    .loc[adsl_raw["SAFFL"] == "Y"]
    .groupby("ARMCD", as_index=False)
    .agg(N_TOTAL=("USUBJID", "nunique"))   # count distinct subjects per arm
)
# SAS rename=(count=n_total)  →  column already named N_TOTAL above

# ── Step 3: Subject counts by category × arm ─────────────────────────────────
# SAS: proc freq data=ae_all; tables category * armcd / out=ae_counts;
ae_counts = (
    ae_all
    .groupby(["CATEGORY", "ARMCD"], as_index=False)
    .agg(N_SUBJ=("USUBJID", "nunique"))    # SAS rename=(count=n_subj)
)

# ── Step 4: Merge counts with denominator and compute percentages ─────────────
# SAS: merge ae_counts(in=inAE) denom(in=inDEN); by armcd; if inAE;
# Python: left join keeps only ae_counts rows (mirrors 'if inAE')
ae_pct = ae_counts.merge(
    denom,
    on="ARMCD",
    how="left"          # inAE=TRUE for all left rows; rows without denom → NaN
)

# Explicit guard: flag any arm with no denominator (would be silent error in SAS)
missing_denom = ae_pct["N_TOTAL"].isna()
if missing_denom.any():
    raise ValueError(
        f"[DATA INTEGRITY] The following ARMCD values in ae_counts have no "
        f"matching denominator in adsl (SAFFL='Y'): "
        f"{ae_pct.loc[missing_denom, 'ARMCD'].unique().tolist()}"
    )

# SAS: pct = (n_subj / n_total) * 100
ae_pct["PCT"] = (ae_pct["N_SUBJ"] / ae_pct["N_TOTAL"]) * 100

# SAS: pct_fmt = put(n_subj,3.) || ' (' || put(pct,5.1) || '%)'
# Python string formatting mirrors SAS put() width/decimal specs
ae_pct["PCT_FMT"] = (
    ae_pct["N_SUBJ"].map(lambda n: f"{int(n):3d}")
    + " ("
    + ae_pct["PCT"].map(lambda p: f"{p:5.1f}")
    + "%)"
)

# Preserve canonical category order (mirrors SAS set order in ae_all)
category_order = [
    "Subjects with any AE",
    "Subjects with any SAE",
    "AE leading to discontinuation",
    "Grade 3 or higher AE",
]
ae_pct["CATEGORY"] = pd.Categorical(
    ae_pct["CATEGORY"],
    categories=category_order,
    ordered=True
)
ae_pct = ae_pct.sort_values(["CATEGORY", "ARMCD"]).reset_index(drop=True)

# ── Step 5: Pivot to wide format (mirrors PROC REPORT across ARMCD) ───────────
# SAS: column category armcd, pct_fmt;  define armcd / across ...
ae_display = ae_pct.pivot_table(
    index="CATEGORY",
    columns="ARMCD",
    values="PCT_FMT",
    aggfunc="first"         # one formatted value per cell; duplicates are a data error
).reset_index()

ae_display.columns.name = None  # remove residual MultiIndex label from pivot

# Restore row order after pivot
ae_display["CATEGORY"] = pd.Categorical(
    ae_display["CATEGORY"],
    categories=category_order,
    ordered=True
)
ae_display = ae_display.sort_values("CATEGORY").reset_index(drop=True)

# ── Save analysis-ready dataset for QC / downstream use ──────────────────────
os.makedirs(OUTPUT_DIR, exist_ok=True)
ae_pct_out     = os.path.join(OUTPUT_DIR, "ae_pct.parquet")
ae_display_out = os.path.join(OUTPUT_DIR, "ae_display.parquet")
ae_pct.to_parquet(ae_pct_out,     index=False, engine="pyarrow")
ae_display.to_parquet(ae_display_out, index=False, engine="pyarrow")

# ── Step 5 [REQUIRES_MANUAL_REVIEW: TFL output] ───────────────────────────────
# The following SAS block requires manual recreation in your reporting framework:
#
#   ods rtf file='/output/bmn999/tables/t_ae_summ.rtf' style=journal;
#   title1 'BMN-999-001';
#   title2 'Table 14.3.1';
#   title3 'Summary of Treatment-Emergent Adverse Events';
#   title4 'Safety Population';
#   footnote1 'AE=Adverse Event; SAE=Serious Adverse Event; ...';
#   footnote2 'Percentages based on number of subjects in safety population ...';
#   proc report data=ae_pct nowd headline headskip;
#       column category armcd, pct_fmt;
#       define category / group 'AE Category'   width=45;
#       define armcd    / across 'Treatment Arm' width=15;
#       define pct_fmt  / display 'n (%)'        width=12;
#       break after category / skip;
#   run;
#   ods rtf close;
#
# Recommended Python RTF/PDF rendering options (choose per site SOPs):
#   - reportlab / fpdf2         — programmatic PDF generation
#   - python-docx               — Word .docx output
#   - great_tables (via R reticulate) — publication-quality HTML/RTF
#   - Tplyr + rpy2              — CDISC-standard TFL tables via R
#
# The ae_display DataFrame above contains the pivoted, formatted data
# ready to pass directly into any of the above renderers.
#
# Metadata for table shell:
TABLE_TITLE  = [
    "BMN-999-001",
    "Table 14.3.1",
    "Summary of Treatment-Emergent Adverse Events",
    "Safety Population",
]
TABLE_FOOTNOTES = [
    "AE=Adverse Event; SAE=Serious Adverse Event; "
    "N=number of subjects in safety population",
    "Percentages based on number of subjects in safety population "
    "per treatment arm",
]
COLUMN_LABELS = {
    "CATEGORY": "AE Category",   # define category / group ... width=45
    # remaining columns are ARMCD values — labelled 'Treatment Arm' in header
}
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
