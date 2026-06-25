/* ADLB_BASELINE.sas - Lab data ADaM baseline derivation */
/* BioMarin BMN-999 Study */

libname adam '/data/adam';
libname sdtm '/data/sdtm';

proc sort data=sdtm.lb out=lb_sorted; by usubjid lbtestcd lbdtc; run;

data adam.adlb;
    set lb_sorted;
    by usubjid lbtestcd;

    /* Baseline flag: last value on or before first dose */
    retain base .;
    if first.lbtestcd then base = .;

    if lbdtc <= rfstdtc then do;
        base    = lbstresn;
        ablfl   = 'Y';
    end;

    /* Change from baseline */
    if base ne . and lbstresn ne . then chg = lbstresn - base;
    else chg = .;

    /* Percent change from baseline */
    if base ne 0 and base ne . then pchg = (chg / base) * 100;
    else pchg = .;

    label
        base  = 'Baseline Value'
        chg   = 'Change from Baseline'
        pchg  = 'Percent Change from Baseline'
        ablfl = 'Baseline Record Flag';

run;

/* Summary statistics */
proc means data=adam.adlb n mean std min max;
    class lbtestcd;
    var lbstresn chg pchg;
    output out=adlb_summ mean=mean_val std=std_val;
run;
