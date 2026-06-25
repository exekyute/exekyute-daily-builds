// The same worklist the SQL tool writes, embedded so the dashboard can load
// sample data with one click. Loading your own renewal_worklist.csv with the
// file picker uses the exact same code path.
var SAMPLE_CSV = [
    "member_id,name,tier,status,expiry_date,dues,late_fee,hst,total,action",
    "101,Ana Reyes,Professional,Paid,2026-12-31,300.00,0.00,39.00,339.00,Current",
    "102,Ben Cho,Associate,Paid,2026-12-31,112.50,0.00,14.63,127.13,Current",
    "103,Cara Diaz,Student,Paid,2026-12-31,25.00,0.00,3.25,28.25,Current",
    "104,Dan Evans,Professional,Expiring,2026-07-10,300.00,0.00,39.00,339.00,Renew now",
    "105,Erin Fox,Associate,Expiring,2026-07-02,150.00,0.00,19.50,169.50,Renew now",
    "106,Gil Haig,Retired,Lapsed,2026-06-01,90.00,0.00,11.70,101.70,Overdue",
    "107,Hana Ito,Professional,Lapsed,2026-05-22,300.00,0.00,39.00,339.00,Overdue",
    "108,Ivy Lin,Professional,Paid,2026-12-31,300.00,25.00,39.00,364.00,Current",
    "109,Jose Mata,Student,Paid,2026-12-31,6.25,0.00,0.81,7.06,Current",
    "110,Kim Noor,Associate,Paid,2026-12-31,150.00,0.00,19.50,169.50,Current",
    "110,Kim Noor,Associate,Duplicate,2026-12-31,150.00,0.00,19.50,169.50,Review",
    "111,Lee Ortiz,,Expiring,2026-07-05,,,,,Renew now"
].join("\n");
