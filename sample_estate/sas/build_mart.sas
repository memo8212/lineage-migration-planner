/* build_mart.sas — segment x dept mart from the clean cards feed */
%include 'sas/common.sas';

proc sql;
    create table GOLD_SEGMENT as
    select c.ACCOUNT_NO, d.SEGMENT, sum(c.AMOUNT) as TOTAL
    from   CARDS_CLEAN c
    inner join CUSTOMER_DIM d
        on c.ACCOUNT_NO = d.ACCOUNT_NO
    group by c.ACCOUNT_NO, d.SEGMENT;
quit;

proc export data=GOLD_SEGMENT
    outfile="/out/gold_segment.csv"
    dbms=csv replace;
run;
