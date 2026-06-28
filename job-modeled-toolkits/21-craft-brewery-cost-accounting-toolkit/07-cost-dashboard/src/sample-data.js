/*
 * Bundled sample data, the CSV output of the upstream tools, embedded as text so
 * the dashboard renders on the spot when you click "Load sample data". Loading
 * your own files with the file picker overrides this; nothing is uploaded
 * anywhere either way.
 */
var SAMPLE_DATA = {
  perpetual:
    "sku,description,category,on_hand_qty,unit,wac_unit_cost,inventory_value,integrity_flag\n" +
    "RM-MALT,2-row pale malt,raw_material,3670,kg,1.2625,4633.37,\n" +
    "RM-HOPS,Cascade hops,raw_material,180,kg,19.6800,3542.40,\n" +
    "PKG-CAN-355,355 mL can,packaging_material,36000,each,0.0938,3375.00,\n" +
    "PKG-KEG-50L,50 L keg,packaging_material,85,each,45.7642,3889.96,\n" +
    "PKG-LABEL,can label,packaging_material,36000,each,0.0203,732.22,\n" +
    "RM-FININGS,clarifying finings,raw_material,-2,kg,4.0000,-8.00,negative on-hand\n" +
    "FG-LAGER-CAN,Harbourview Lager 355 mL can,finished_goods,500,each,0.4343,217.16,\n" +
    "FG-LAGER-KEG,Harbourview Lager 50 L keg,finished_goods,3,each,90.8667,272.60,\n" +
    "FG-IPA-CAN,Headland IPA 355 mL can,finished_goods,300,each,0.6589,197.68,\n" +
    "FG-IPA-KEG,Headland IPA 50 L keg,finished_goods,2,each,122.5000,245.00,\n" +
    "FG-RADLER-CAN,Shoreline Radler 355 mL can,finished_goods,500,each,0.2868,143.40,\n",
  batches:
    "batch_id,beer,product_line,abv_class,brewed_litres,finished_litres,yield_pct,ingredient_cost,labour_cost,overhead_cost,brew_cost,packaging_material_cost,total_batch_cost,cost_per_finished_litre,volume_flag\n" +
    "BATCH-L01,Harbourview Lager,Lager,over_2_5,1900,1815,95.53,637.19,600.00,400.00,1637.19,1028.73,2665.92,0.902033,\n" +
    "BATCH-I01,Headland IPA,IPA,over_2_5,1300,1210,93.08,1007.03,500.00,350.00,1857.03,685.82,2542.85,1.534736,\n" +
    "BATCH-R01,Shoreline Radler,Radler,over_1_2_to_2_5,1500,1420,94.67,190.86,300.00,200.00,690.86,456.36,1147.22,0.486521,\n",
  margins:
    "fg_sku,product_line,channel,units_sold,unit_price,revenue,cogs_production,cogs_excise,cogs_total,gross_margin,margin_pct\n" +
    "FG-LAGER-CAN,Lager,retail,2500,2.50,6250.00,1085.78,33.45,1119.23,5130.77,82.09\n" +
    "FG-LAGER-KEG,Lager,on_premise,12,220.00,2640.00,1090.38,22.61,1112.99,1527.01,57.84\n" +
    "FG-IPA-CAN,IPA,retail,1200,2.95,3540.00,790.70,16.06,806.76,2733.24,77.21\n" +
    "FG-IPA-CAN,IPA,distributor,500,2.60,1300.00,329.46,6.69,336.15,963.85,74.14\n" +
    "FG-IPA-KEG,IPA,on_premise,8,260.00,2080.00,980.01,15.08,995.09,1084.91,52.16\n" +
    "FG-RADLER-CAN,Radler,retail,3500,2.75,9625.00,1003.82,30.77,1034.59,8590.41,89.25\n",
  excise:
    "abv_class,hectolitres,excise_duty\n" +
    "over_2_5,30.25,114.01\n" +
    "over_1_2_to_2_5,14.20,35.16\n",
  physical:
    "sku,counted_qty\n" +
    "RM-MALT,3655\n" +
    "RM-HOPS,172\n" +
    "PKG-CAN-355,36000\n" +
    "PKG-KEG-50L,85\n" +
    "PKG-LABEL,35500\n" +
    "RM-FININGS,0\n" +
    "FG-LAGER-CAN,500\n" +
    "FG-LAGER-KEG,3\n" +
    "FG-IPA-CAN,290\n" +
    "FG-IPA-KEG,2\n" +
    "FG-RADLER-CAN,520\n",
};

if (typeof module !== "undefined" && module.exports) {
  module.exports = SAMPLE_DATA;
}
