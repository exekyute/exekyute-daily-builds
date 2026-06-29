"use strict";

// Synthetic sample data, the same content as cost_by_team.csv and model_scorecard.csv
// in this folder. Embedding it lets the dashboard load a populated view with one click,
// without picking a file. The "Load sample data" button reads these strings.

Dashboard.SAMPLE_TEAM = [
  "team,requests,input_tokens,output_tokens,direct_cost,allocated_shared,loaded_cost,monthly_budget,remaining,utilization_pct,status,forecast_loaded,forecast_status",
  "DataScience,3600,62000000,10500000,125.50,135.88,261.38,400.00,138.62,65.3,Within budget,324.13,Within budget",
  "Engineering,2600,125000000,26000000,549.10,594.50,1143.60,1000.00,-143.60,114.4,Over budget,1418.15,Over budget",
  "Sales,8000,85000000,19500000,66.19,71.66,137.85,150.00,12.15,91.9,Near limit,170.95,Over budget",
  "Support,25600,194000000,37500000,35.06,37.96,73.02,200.00,126.98,36.5,Within budget,90.55,Within budget",
].join("\n");

Dashboard.SAMPLE_SCORECARD = [
  "rank,model,accuracy,precision,recall,f1,p50_latency_ms,p95_latency_ms,cost_usd,cost_per_correct,score",
  "1,frontier-mini,0.6000,0.6000,0.6000,0.6000,250,500,0.10,0.0167,80.00",
  "2,balanced-mid,0.8000,0.8000,0.8000,0.8000,500,900,0.40,0.0500,74.08",
  "3,frontier-large,0.9000,0.8333,1.0000,0.9091,1100,2000,1.00,0.1111,45.45",
].join("\n");
