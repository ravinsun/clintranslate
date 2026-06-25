/* ============================================================
   Program  : adcm.sas
   Study    : BMN-999-001
   Purpose  : ADCM - Concomitant Medications Analysis Dataset
   Author   : Clinical Data Engineering
   Created  : 2024-02-10
   ============================================================ */

libname adam '/data/bmn999/adam';
libname sdtm '/data/bmn999/sdtm';

/* ── Step 1: Prepare CM domain ── */
data cm_prep;
    set sdtm.cm;

    /* Parse dates */
    cmstdt = input(cmstdtc, yymmdd10.);
    cmendt = input(cmendtc, yymmdd10.);
    format cmstdt cmendt date9.;

    /* ATC class grouping */
    atc1 = upcase(substr(cmatc, 1, 1));
    select (atc1);
        when ('A') atcgrp = 'Alimentary/Metabolism';
        when ('B') atcgrp = 'Blood/Blood Forming';
        when ('C') atcgrp = 'Cardiovascular';
        when ('J') atcgrp = 'Anti-infectives';
        when ('L') atcgrp = 'Antineoplastic';
        when ('M') atcgrp = 'Musculoskeletal';
        when ('N') atcgrp = 'Nervous System';
        when ('R') atcgrp = 'Respiratory';
        otherwise atcgrp = 'Other';
    end;

    label atcgrp = 'ATC Therapeutic Group';
run;

/* ── Step 2: Merge with ADSL ── */
proc sort data=cm_prep;   by usubjid cmstdt; run;
proc sort data=adam.adsl out=adsl_sub
    (keep=usubjid trtsdt trtedt saffl armcd);
    by usubjid;
run;

data adcm_merge;
    merge cm_prep   (in=inCM)
          adsl_sub  (in=inADSL);
    by usubjid;
    if inCM and inADSL and saffl = 'Y';
run;

/* ── Step 3: Treatment-emergent flag ── */
data adam.adcm;
    set adcm_merge;

    /* On-treatment flag: started during treatment window */
    if cmstdt ne . and trtsdt ne . and trtedt ne . then do;
        if cmstdt >= trtsdt and cmstdt <= trtedt + 30 then
            trtemfl = 'Y';
        else trtemfl = 'N';
    end;
    else trtemfl = 'N';

    /* Duration of medication */
    if cmstdt ne . and cmendt ne . then
        cmdur = cmendt - cmstdt + 1;
    else if cmstdt ne . and cmendt = . then
        cmdur = .;  /* ongoing */

    /* Relative start day */
    if trtsdt ne . and cmstdt ne . then
        astdy = cmstdt - trtsdt + (cmstdt >= trtsdt);

    /* Ongoing flag */
    if cmendt = . then ongofl = 'Y';
    else ongofl = 'N';

    label
        trtemfl = 'Treatment Emergent Flag'
        cmdur   = 'Medication Duration (Days)'
        astdy   = 'Analysis Start Relative Day'
        ongofl  = 'Ongoing at End of Study Flag';
run;

proc sort data=adam.adcm; by usubjid cmstdt cmtrt; run;

/* ── Frequency tables ── */
proc freq data=adam.adcm;
    where trtemfl = 'Y';
    tables atcgrp / order=freq;
    title 'ADCM — Treatment-Emergent Medications by ATC Group';
run;

proc freq data=adam.adcm;
    where trtemfl = 'Y';
    tables armcd * atcgrp / list missing;
    title 'ADCM — Medications by Treatment Arm and ATC Group';
run;
