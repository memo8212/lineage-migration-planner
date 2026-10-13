/* extract_cards.sas — clean the cards feed and export to the bridge */
libname BANK '/data/bank';

%let BATCH_ID = 20260115;
%include 'sas/common.sas';

data CARDS_STG;
    set BANK.RAW_CARDS;
    where AMOUNT > 0;
run;

proc sql;
    create table CARDS_CLEAN as
    select ACCOUNT_NO, DEPT_CODE, AMOUNT, CCY, TXN_DATE
    from   CARDS_STG
    where  STATUS ne 'REVERSAL';
quit;

proc sort data=CARDS_CLEAN out=CARDS_SORTED;
    by ACCOUNT_NO;
run;

proc export data=CARDS_SORTED
    outfile="/data/bridge/dept_txn.csv"
    dbms=csv replace;
run;
