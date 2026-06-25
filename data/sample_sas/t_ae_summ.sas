/* ============================================================
   Program  : t_ae_summ.sas
   Study    : BMN-999-001
   Purpose  : Table 14.3.1 — Adverse Events Summary
              *** TFL PROGRAM — PROC REPORT / ODS RTF ***
   Author   : Clinical Data Engineering
   Created  : 2024-03-01
   ============================================================ */

libname adam '/data/bmn999/adam';

options nodate nonumber ls=200;

/* ── Step 1: Derive AE summary counts ── */
proc sort data=adam.adae out=adae_te;
    where trtemfl = 'Y' and saffl = 'Y';
    by usubjid aedecod aestdtc;
run;

/* Any AE */
data ae_any;
    set adae_te;
    by usubjid;
    if first.usubjid;
    category = 'Subjects with any AE';
    run;

/* Serious AEs */
data ae_ser;
    set adae_te;
    where aeser = 'Y';
    by usubjid;
    if first.usubjid;
    category = 'Subjects with any SAE';
run;

/* AEs leading to discontinuation */
data ae_disc;
    set adae_te;
    where aeacn = 'DRUG WITHDRAWN';
    by usubjid;
    if first.usubjid;
    category = 'AE leading to discontinuation';
run;

/* Grade 3+ AEs */
data ae_gr3;
    set adae_te;
    where aesevn >= 3;
    by usubjid;
    if first.usubjid;
    category = 'Grade 3 or higher AE';
run;

data ae_all;
    set ae_any ae_ser ae_disc ae_gr3;
run;

/* ── Step 2: Denominator from ADSL ── */
proc freq data=adam.adsl noprint;
    where saffl = 'Y';
    tables armcd / out=denom (rename=(count=n_total));
run;

/* ── Step 3: Counts by arm ── */
proc freq data=ae_all noprint;
    tables category * armcd / out=ae_counts (rename=(count=n_subj));
run;

/* ── Step 4: Merge and compute percentages ── */
data ae_pct;
    merge ae_counts (in=inAE)
          denom     (in=inDEN);
    by armcd;
    if inAE;
    pct = (n_subj / n_total) * 100;
    pct_fmt = put(n_subj, 3.) || ' (' || put(pct, 5.1) || '%)';
run;

/* ── Step 5: PROC REPORT output ── */
ods rtf file='/output/bmn999/tables/t_ae_summ.rtf'
        style=journal;

title1 'BMN-999-001';
title2 'Table 14.3.1';
title3 'Summary of Treatment-Emergent Adverse Events';
title4 'Safety Population';
footnote1 'AE=Adverse Event; SAE=Serious Adverse Event; N=number of subjects in safety population';
footnote2 'Percentages based on number of subjects in safety population per treatment arm';

proc report data=ae_pct nowd headline headskip;
    column category armcd, pct_fmt;
    define category / group 'AE Category' width=45;
    define armcd    / across 'Treatment Arm' width=15;
    define pct_fmt  / display 'n (%)' width=12;
    break after category / skip;
    title;
run;

ods rtf close;
