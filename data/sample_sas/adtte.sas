/* ============================================================
   Program  : adtte.sas
   Study    : BMN-999-001
   Purpose  : Create ADTTE - Time to First AE Analysis Dataset
   Author   : Clinical Data Engineering
   Created  : 2024-02-01
   ============================================================ */

libname adam '/data/bmn999/adam';
libname sdtm '/data/bmn999/sdtm';

/* ── Step 1: Get first AE date per subject ── */
proc sort data=sdtm.ae out=ae_sorted;
    by usubjid aestdtc;
run;

data ae_first;
    set ae_sorted;
    by usubjid;
    if first.usubjid;
    first_ae_dt = input(aestdtc, yymmdd10.);
    keep usubjid first_ae_dt aesev aeser;
    format first_ae_dt date9.;
run;

/* ── Step 2: Merge with ADSL ── */
data adtte_base;
    merge adam.adsl  (in=inADSL
                      keep=usubjid trtsdt trtedt saffl armcd)
          ae_first   (in=inAE);
    by usubjid;
    if inADSL and saffl = 'Y';

    /* Event indicator */
    if inAE then evntfl = 'Y';
    else evntfl = 'N';

    /* Analysis end date */
    if inAE then adt = first_ae_dt;
    else if trtedt ne . then adt = trtedt + 1;  /* censored at last dose + 1 */
    else adt = trtsdt;

    format adt date9.;
run;

/* ── Step 3: Compute time to event ── */
data adam.adtte;
    set adtte_base;

    /* Time to event in days */
    if trtsdt ne . and adt ne . then
        aval = adt - trtsdt + 1;
    else aval = .;

    /* Censoring flag (0=censored, 1=event) */
    if evntfl = 'Y' then cnsr = 0;
    else cnsr = 1;

    /* Parametric values */
    if aval > 0 then avalog = log(aval);
    else avalog = .;

    /* Severity at first event */
    if evntfl = 'Y' then do;
        if aesev = 'MILD'     then sevn = 1;
        else if aesev = 'MODERATE' then sevn = 2;
        else if aesev = 'SEVERE'   then sevn = 3;
        else sevn = .;
    end;

    param    = 'Time to First Adverse Event (Days)';
    paramcd  = 'TTFAE';
    paramu   = 'Days';

    label
        aval   = 'Analysis Value (Days to Event)'
        cnsr   = 'Censor Flag (0=Event, 1=Censored)'
        avalog = 'Log Analysis Value'
        evntfl = 'Event Flag'
        param  = 'Parameter'
        paramcd = 'Parameter Code';
run;

proc sort data=adam.adtte; by usubjid paramcd; run;

/* ── Kaplan-Meier summary ── */
proc lifetest data=adam.adtte notable;
    time aval * cnsr(1);
    strata armcd;
    title 'Time to First AE — KM Summary BMN-999-001';
run;
