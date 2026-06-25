/* ============================================================
   Program  : advs.sas
   Study    : BMN-999-001
   Purpose  : Create ADVS - Vital Signs Analysis Dataset
   Author   : Clinical Data Engineering
   Created  : 2024-01-20
   ============================================================ */

libname adam '/data/bmn999/adam';
libname sdtm '/data/bmn999/sdtm';

/* ── Step 1: Sort VS by subject and timepoint ── */
proc sort data=sdtm.vs out=vs_sorted;
    by usubjid vstestcd visitnum vsdtc;
run;

/* ── Step 2: Merge with ADSL for treatment dates ── */
data advs_raw;
    merge vs_sorted  (in=inVS)
          adam.adsl  (in=inADSL keep=usubjid trtsdt saffl);
    by usubjid;
    if inVS and inADSL;

    /* Analysis timing relative to treatment */
    vsdt = input(vsdtc, yymmdd10.);
    if trtsdt ne . and vsdt ne . then
        ady = vsdt - trtsdt + (vsdt >= trtsdt);

    format vsdt date9.;
run;

/* ── Step 3: Baseline derivation ── */
proc sort data=advs_raw; by usubjid vstestcd vsdt; run;

data advs_base;
    set advs_raw;
    by usubjid vstestcd;

    retain base .;
    if first.vstestcd then base = .;

    /* Baseline = last value on or before first dose */
    if vsdt <= trtsdt and vsstresn ne . then do;
        base  = vsstresn;
        ablfl = 'Y';
    end;
    else ablfl = '';

    label
        base  = 'Baseline Value'
        ablfl = 'Baseline Record Flag'
        ady   = 'Analysis Relative Day';
run;

/* ── Step 4: Change from baseline ── */
data adam.advs;
    set advs_base;

    /* Propagate baseline to all records */
    retain base_val .;
    by usubjid vstestcd;
    if first.vstestcd then base_val = .;
    if ablfl = 'Y' then base_val = base;

    /* Change from baseline */
    if base_val ne . and vsstresn ne . then do;
        chg  = vsstresn - base_val;
        if base_val ne 0 then
            pchg = (chg / base_val) * 100;
        else pchg = .;
    end;

    /* Shift flags for blood pressure */
    if vstestcd = 'SYSBP' then do;
        if vsstresn < 90 then bpshift = 'Low';
        else if vsstresn > 140 then bpshift = 'High';
        else bpshift = 'Normal';
    end;

    /* Visit windows */
    if ady = . then avisit = 'Unscheduled';
    else if ady <= 0 then avisit = 'Baseline';
    else if 1 <= ady <= 14 then avisit = 'Week 2';
    else if 15 <= ady <= 28 then avisit = 'Week 4';
    else if 29 <= ady <= 56 then avisit = 'Week 8';
    else avisit = 'Post-treatment';

    label
        chg     = 'Change from Baseline'
        pchg    = 'Percent Change from Baseline'
        bpshift = 'Blood Pressure Shift Category'
        avisit  = 'Analysis Visit';

    drop base;
run;

/* ── Summary statistics by test and visit ── */
proc means data=adam.advs n mean std min max;
    class vstestcd avisit;
    var vsstresn chg pchg;
    output out=advs_summ
        n    = n_obs
        mean = mean_val
        std  = std_val;
    title 'ADVS Summary Statistics — BMN-999-001';
run;
