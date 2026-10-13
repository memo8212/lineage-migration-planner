/* common.sas — shared macros */
%let BASE_CCY = CAD;
%let MIN_AMOUNT = 100;

%macro log(msg);
    %put NOTE: &msg;
%mend;
