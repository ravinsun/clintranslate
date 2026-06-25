/* ADAE_MERGE.sas - Adverse Events ADaM merge */
/* BioMarin BMN-999 Study — ADAE derivation */

libname adam '/data/adam';
libname sdtm '/data/sdtm';

data adam.adae;
    merge sdtm.ae (in=inAE)
          sdtm.dm (in=inDM keep=usubjid age sex race armcd);
    by usubjid;
    if inAE;

    /* Severity grade mapping */
    if aesev = 'MILD'     then aesevn = 1;
    else if aesev = 'MODERATE' then aesevn = 2;
    else if aesev = 'SEVERE'   then aesevn = 3;

    /* Treatment-emergent flag */
    if aestdtc >= rfstdtc then TRTEMFL = 'Y';
    else TRTEMFL = 'N';

    label
        aesevn  = 'Severity Grade (Numeric)'
        TRTEMFL = 'Treatment-Emergent Flag';

run;

proc sort data=adam.adae; by usubjid aestdtc; run;
