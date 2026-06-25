/*
 * Sample data for the dashboard and the test harness. These are the two CSV
 * files the engine in ../01-cca-depreciation-engine writes, embedded as strings
 * so the page shows something on first open without needing a file. Loading your
 * own per_class_cca.csv replaces this.
 */
var SAMPLE_PER_CLASS_CSV = [
  "cca_class,rate,opening_ucc,additions,disposals,half_year_adjustment,cca_base,cca,recapture,terminal_loss,closing_ucc,net_book_value,temporary_difference",
  "10,0.30,4000.00,0.00,7000.00,0.00,0.00,0.00,3000.00,0.00,0.00,0.00,0.00",
  "12,1.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00",
  "50,0.55,1200.00,0.00,300.00,0.00,0.00,0.00,0.00,900.00,0.00,0.00,0.00",
  "8,0.20,10000.00,5000.00,0.00,2500.00,12500.00,2500.00,0.00,0.00,12500.00,5700.00,-6800.00"
].join("\n");

var SAMPLE_PER_ASSET_CSV = [
  "asset_id,description,cca_class,capital_cost,salvage_value,useful_life_years,in_service_date,disposed,annual_book_dep,prior_accum_book_dep,current_book_dep,accum_book_dep,net_book_value",
  "FA-001,Warehouse shelving,8,8000.00,0.00,10,2019-03-15,N,800.00,5600.00,800.00,6400.00,1600.00",
  "FA-002,Electric forklift,8,5000.00,500.00,5,2026-06-01,N,900.00,0.00,900.00,900.00,4100.00",
  "FA-003,Delivery van,10,9000.00,1000.00,6,2021-01-10,Y,1333.33,4000.00,0.00,4000.00,0.00",
  "FA-004,Server rack,50,2000.00,0.00,4,2022-08-01,Y,500.00,1500.00,0.00,1500.00,0.00",
  "FA-005,Hand tool set,12,1200.00,0.00,3,2018-05-01,N,400.00,1200.00,0.00,1200.00,0.00"
].join("\n");
