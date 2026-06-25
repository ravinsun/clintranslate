/* ============================================================
   Program  : adsl.sas
   Study    : BMN-999-001
   Purpose  : Create ADSL - Subject Level Analysis Dataset
   Author   : Clinical Data Engineering
   Created  : 2024-01-15
   ============================================================ */

libname adam '/data/bmn999/adam';
libname sdtm '/data/bmn999/sdtm';

/* ── Step 1: Base population from DM ── */
data adsl_base;
    set sdtm.dm;

    /* Age grouping */
    if age < 18 then agegr1 = '<18';
    else if 18 <= age < 40 then agegr1 = '18-39';
    else if 40 <= age < 65 then agegr1 = '40-64';
    else agegr1 = '>=65';

    /* BMI calculation */
    if height > 0 and weight > 0 then
        bmi = weight / ((height/100) ** 2);
    else bmi = .;

    if bmi < 18.5 then bmigrp = 'Underweight';
    else if 18.5 <= bmi < 25 then bmigrp = 'Normal';
    else if 25 <= bmi < 30 then bmigrp = 'Overweight';
    else if bmi >= 30 then bmigrp = 'Obese';
    else bmigrp = 'Missing';

    label
        agegr1 = 'Age Group'
        bmi    = 'Body Mass Index'
        bmigrp = 'BMI Group';

run;

/* ── Step 2: Merge disposition ── */
proc sort data=sdtm.ds out=ds_sorted; by usubjid; run;
proc sort data=adsl_base out=adsl_sorted; by usubjid; run;

data adsl_disp;
    merge adsl_sorted (in=inDM)
          ds_sorted   (in=inDS keep=usubjid dsdecod dsstdtc
                       where=(dscat='DISPOSITION EVENT'));
    by usubjid;
    if inDM;

    /* Completion flag */
    if dsdecod = 'COMPLETED' then compfl = 'Y';
    else compfl = 'N';

    /* Discontinuation reason */
    if dsdecod ne 'COMPLETED' and dsdecod ne '' then discrs = dsdecod;

    label
        compfl = 'Completor Flag'
        discrs = 'Discontinuation Reason';
run;

/* ── Step 3: Merge exposure for treatment dates ── */
proc sort data=sdtm.ex out=ex_first;
    by usubjid exstdtc;
run;

data ex_dates;
    set ex_first;
    by usubjid;
    if first.usubjid then trtsdt = input(exstdtc, yymmdd10.);
    if last.usubjid  then trtedt = input(exendtc, yymmdd10.);
    retain trtsdt;
    if last.usubjid;
    keep usubjid trtsdt trtedt;
    format trtsdt trtedt date9.;
run;

data adam.adsl;
    merge adsl_disp (in=inBase)
          ex_dates  (in=inEX);
    by usubjid;
    if inBase;

    /* Treatment duration */
    if trtsdt ne . and trtedt ne . then
        trtdur = trtedt - trtsdt + 1;

    /* Safety population flag */
    if inEX then saffl = 'Y';
    else saffl = 'N';

    /* ITT population flag */
    if randdt ne . then ittfl = 'Y';
    else ittfl = 'N';

    label
        trtsdt = 'Date of First Study Treatment'
        trtedt = 'Date of Last Study Treatment'
        trtdur = 'Treatment Duration (Days)'
        saffl  = 'Safety Population Flag'
        ittfl  = 'ITT Population Flag';
run;

proc sort data=adam.adsl; by usubjid; run;

/* ── Summary ── */
proc freq data=adam.adsl;
    tables saffl * ittfl * compfl / list missing;
    title 'ADSL Population Summary — BMN-999-001';
run;
