/* ============================================================
   Program  : sdtm_lb.sas
   Study    : BMN-999-001
   Purpose  : SDTM LB Domain — Laboratory Results
   Author   : Clinical Data Engineering
   Created  : 2024-01-10
   ============================================================ */

libname sdtm  '/data/bmn999/sdtm';
libname raw   '/data/bmn999/raw';

/* ── Step 1: Read raw lab data ── */
data lb_raw;
    set raw.lab_results;

    /* Standardize test codes to CDISC LBTESTCD */
    select (upcase(test_name));
        when ('HEMOGLOBIN', 'HGB')    do; lbtestcd = 'HGB';    lbtest = 'Hemoglobin'; end;
        when ('HEMATOCRIT', 'HCT')    do; lbtestcd = 'HCT';    lbtest = 'Hematocrit'; end;
        when ('PLATELETS', 'PLT')     do; lbtestcd = 'PLAT';   lbtest = 'Platelets'; end;
        when ('WBC', 'LEUKOCYTES')    do; lbtestcd = 'WBC';    lbtest = 'Leukocytes'; end;
        when ('CREATININE', 'CREAT')  do; lbtestcd = 'CREAT';  lbtest = 'Creatinine'; end;
        when ('ALT', 'SGPT')          do; lbtestcd = 'ALT';    lbtest = 'Alanine Aminotransferase'; end;
        when ('AST', 'SGOT')          do; lbtestcd = 'AST';    lbtest = 'Aspartate Aminotransferase'; end;
        when ('GLUCOSE', 'GLUC')      do; lbtestcd = 'GLUC';   lbtest = 'Glucose'; end;
        otherwise do; lbtestcd = upcase(test_name); lbtest = test_name; end;
    end;

    /* Standardize units */
    lborresu = strip(unit);
    if lborresu = 'g/dL' then lbstresu = 'g/dL';
    else if lborresu in ('U/L', 'IU/L') then lbstresu = 'U/L';
    else if lborresu = 'mg/dL' then lbstresu = 'mg/dL';
    else lbstresu = lborresu;

    /* Numeric result */
    lborres  = strip(result_text);
    lbstresn = input(result_numeric, best12.);
    lbstresc = strip(result_text);

    /* Normal range flags */
    if lbstresn ne . then do;
        if lbstresn < low_normal then lbnrind = 'LOW';
        else if lbstresn > high_normal then lbnrind = 'HIGH';
        else lbnrind = 'NORMAL';
    end;

    /* SDTM required variables */
    domain   = 'LB';
    studyid  = 'BMN-999-001';
    lbcat    = 'HEMATOLOGY';

    /* Date standardization to ISO 8601 */
    lbdtc = put(collect_date, yymmdd10.);

    label
        lbtestcd = 'Lab Test Short Name'
        lbtest   = 'Lab Test Name'
        lbstresn = 'Numeric Result/Finding in Standard Units'
        lbnrind  = 'Reference Range Indicator';

    keep studyid domain usubjid lbseq lbtestcd lbtest lbcat
         lborres lborresu lbstresn lbstresc lbstresu
         lbnrind lbdtc visitnum visit;
run;

/* ── Step 2: Assign sequence numbers ── */
proc sort data=lb_raw; by usubjid lbdtc lbtestcd; run;

data sdtm.lb;
    set lb_raw;
    by usubjid;
    retain lbseq 0;
    if first.usubjid then lbseq = 0;
    lbseq + 1;
run;

/* ── Validation checks ── */
proc freq data=sdtm.lb;
    tables lbtestcd * lbnrind / list missing;
    title 'LB Domain — Test Code by Normal Range Flag';
run;

proc means data=sdtm.lb n nmiss mean std min max;
    class lbtestcd;
    var lbstresn;
    title 'LB Domain — Numeric Results Summary';
run;
