# BI build guides: speed management inventory

The SQL pipeline freezes three files into `bi/exports/`, and the workbook reads them and
recomputes nothing.

- `speed_devices.geojson`, 780 point features. One feature is one speed-management
  device: 73 speed display signs plus 707 traffic control locations. It carries
  `device_id` (1 to 780), `source_layer`, `device_type`, `install_year`, and `location`.
- `speed_limits.geojson`, 13,835 line features, about 47 MB. One feature is one
  neighbourhood road segment, carrying its posted `SPEED` in km/h and its published
  `Shape__Length` in metres.
- `mart_points.csv`, 780 rows. One row is one device, carrying `source_layer`,
  `device_type`, `install_year`, `location`, and `lat` and `lon` as plain number columns
  instead of geometry. This is the readable copy and the golden mart.

The committed dashboard is the Tableau workbook
`bi/tableau/speed_management_inventory.twb`. Field meanings and Tableau types are in
`bi/exports/data_dictionary.md`.

Tableau live link: https://public.tableau.com/views/HalifaxSpeedManagementInventory/Speedmanagementmap

- [Tableau guide](#tableau-guide-layered-device-map)
- [Numbers must match](#numbers-must-match)

---

## Tableau guide: layered device map

### What this dashboard shows

One map with two marks layers: the 780 device points, coloured by `device_type` and
shaped by `source_layer`, drawn over the neighbourhood street network filtered to the
1,901 segments posted below 50 km/h and coloured by posted `SPEED`. The result reads
where the point devices cluster against where the reduced-speed streets run.

`install_year` is null on 499 of the 780 devices and the street layer carries no usable
date at all, so nothing in either export moves over time: every measure collapses to one
count per device type or one kilometre total per posted speed. The geography is the part
that varies, which is why the whole view is a map.

### Prerequisites

- Tableau Public Desktop Edition for Windows, free from https://public.tableau.com
  (Download on the top nav). Install with defaults.
- A free public.tableau.com account (Sign Up on the same page). Anything published with
  Tableau Public is public, which is fine here because the source is already open data.
- Tableau Public is extract-only: it loads each connection into an extract when you
  publish. Both data sources in the committed workbook carry an `Extract` relation.
- A `python run.py` PASS in the project folder, so `bi/exports/` holds the current files.
  `speed_limits.geojson` is about 47 MB, so the first connect and the extract build take
  a minute.

### Connect the data

The workbook uses two separate data sources, not a join. There is no key shared between a
device point and a road segment; the two layers sit on the same map by geography alone.

1. Open Tableau Public. Under **Connect > To a File**, click **Spatial file** and pick
   this repo's `bi/exports/speed_devices.geojson`. Tableau generates a `Geometry` field
   and reads the five attributes. Check the types it inferred:
   - `source_layer`, `device_type`, `location` are strings (Abc). Tableau displays them
     as **Source Layer**, **Device Type**, and **Location**.
   - `install_year` is a whole number, shown as **Install Year**. Leave it. It is not used
     on the sheet.
   - `device_id` is a whole number and keeps its raw name.
2. Click **Sheet 1** and build the base map first (next section, steps 1 to 5). The second
   layer cannot be added until the map exists.
3. Back in the workbook, add the street network as a second, independent data source:
   **Data > New Data Source > Spatial file**, and pick `bi/exports/speed_limits.geojson`.
   (The **Connections > Add** link on the Data Source tab would attach the file to
   `speed_devices` and put it on the relationship canvas; the committed workbook keeps the
   two sources apart, which is what lets the filter in step 9 trim only the street layer.)
   Tableau generates a second `Geometry` field plus the segment attributes; the two the
   map uses are `SPEED` (whole number, shown as **Speed**) and `Shape__Length` (decimal,
   keeps its raw name). The Data pane's source list should now read `speed_devices` and
   `speed_limits`.
4. On the `speed_limits` data source, create the two calculated fields the committed
   workbook carries. **Analysis > Create Calculated Field**, once per field, with the name
   typed in the box at the top of the editor and only the expression in the formula body
   below it. Name the first `Reduced Speed Street`:

       [SPEED] < 50

   Name the second `KM`:

       [Shape__Length] / 1000

   `Reduced Speed Street` returns a boolean and lands under Dimensions; it is the filter
   the street layer runs on. `KM` is a measure; set its number format to 2 decimal places
   (right-click the field > Default Properties > Number Format > Number (Custom),
   2 decimals). `KM` is defined in the workbook but is not placed on any shelf on the
   published sheet; it is what you drag to Text on a scratch sheet to read the kilometre
   figure in the Numbers must match check below.

### Sheet 1: Speed management map

The workbook's only worksheet, named `Speed management map`. Build it in this order,
because the marks-layer drop target only appears once a spatial field is driving the map.

1. Rename the sheet `Speed management map`.
2. From the `speed_devices` data source, double-click `Geometry`. Tableau plots the
   points and puts `Longitude (generated)` on **Columns** and `Latitude (generated)` on
   **Rows**. This devices layer is the base map.
3. Set the Marks card type to **Shape**.
4. Drag `device_id` to **Detail**, then set the pill to **Dimension** so it is discrete
   and unaggregated. Without a unique field on Detail, Tableau aggregates the layer with
   `COLLECT(Geometry)` and the 780 points collapse into a few dozen grouped marks.
5. Drag `device_type` to **Color** (9 values) and `source_layer` to **Shape** (2 values:
   Speed Display Sign and Traffic Control Location). Drag `location` to **Tooltip**; it
   lands as `ATTR(location)`. Add the data source's row count,
   `speed_devices.geojson (Count)`, to **Tooltip** as well.
6. Shrink the marks on the **Size** slider until the downtown cluster stops merging into
   one blob. The committed workbook sits near the low end of the slider.
7. Add the street layer. From the `speed_limits` data source, drag its `Geometry` field
   onto the map and drop it on the **Add a Marks Layer** target that appears at the
   top-left of the view. A second layer block appears on the Marks card, and the map now
   has two independent Marks cards.
8. With the new layer's Marks card selected, leave the mark type on **Automatic** (lines)
   and drag `SPEED` to **Color**. `SPEED` arrives as a measure, so set the pill to
   **Dimension** and **Discrete**; the legend then lists each posted speed as its own
   swatch instead of a continuous ramp. Set the line **Size** thin enough that the network
   does not fill the peninsula.
9. Drag `Reduced Speed Street` to **Filters** and keep **True** only. The filter belongs
   to the `speed_limits` data source, so it trims the street layer and leaves all 780
   device marks in place. With it on, the Speed legend shows exactly four swatches: 20,
   25, 30, and 40.
10. Rename the two layers in the Marks card, `Devices` for the point layer and
    `Speed limits` for the line layer, and drag `Devices` above `Speed limits` so the
    points draw on top of the streets.
11. **Map > Map Layers**, set **Washout** to 0%. The committed workbook records washout
    `0.0`, which is what keeps the basemap pale enough for the device colours to read.
12. Turn the sheet title on and set the text to:

        Halifax speed management inventory: 780 devices and 410.41 km of reduced-speed streets

### Dashboard

The committed workbook publishes the worksheet `Speed management map` directly, rather
than assembling it into a dashboard object, which is why the live link ends in the sheet
name.

What the published view carries beside the map: the typed title above, a **Source Layer**
shape legend with two entries, a **Speed** colour legend with the four reduced-speed
values, and a **Device Type** colour legend with all nine device types. Showing the
`Reduced Speed Street` filter as a card is optional; the map reads the same either way,
because the filter is only ever set to True.

### Publish and file the artifacts

Tableau Public Desktop has no local Save to disk. `File > Save` and `File > Save As` both
redirect to `Save to Tableau Public As...`, which uploads to the Tableau Public cloud.
Getting the committable `.twb` therefore runs through the cloud and a `.twbx` unzip.

1. **File > Save to Tableau Public As...**, sign in, name it
   `Halifax Speed Management Inventory`. Tableau builds the URL from the workbook name
   and the sheet name, which is what produces
   `HalifaxSpeedManagementInventory/Speedmanagementmap`.
2. On the viz page, click **Download Workbook**. It always downloads as a `.twbx`
   (packaged), never a bare `.twb`.
3. A `.twbx` is a zip. Copy it, rename the copy to `.zip`, unzip, and take the `.twb` from
   the archive root. Commit it as `bi/tableau/speed_management_inventory.twb`. Never commit
   the `.twbx`: the packaged extract duplicates the data, bloats the repo, and does not
   diff. `*.twbx` is already in this project's `.gitignore`.
4. Check the two named connections in the committed `.twb`. Both should read
   `directory='../exports'` with tables `speed_devices.geojson` and
   `speed_limits.geojson`, which is relative to `bi/tableau/` and lets the workbook reopen
   against the frozen exports in place. A `.twb` pulled straight out of a `.twbx` points at
   the packaged copies instead; repoint the two connections if yours does.
5. Screenshot the map into `bi/tableau/screenshots/`. The committed one is
   `01-speed-management-map.png`, and the project README embeds it.

---

## Numbers must match

**The inventory is 780 point devices**, and that figure is fixed by the export, not
recomputed by the workbook:

- **SQL golden** (`expected/counts_by_device.csv`): the `devices` column sums to 780
  across the nine rows, 73 on `source_layer = Speed Display Sign` and 707 across the
  eight `Traffic Control Location` types. The largest single type is Signalized
  Intersection at 310.
- **Tableau**: with `device_id` on Detail, the status bar under the map reads 780 marks
  on the Devices layer, and `speed_devices.geojson (Count)` totals 780. Ticking the Source
  Layer legend down to one value splits it 73 and 707, and the Device Type legend resolves
  to the same nine counts as the golden.

A second check, on the street layer. Filter `Reduced Speed Street` to True and drag `KM`
to Text on a scratch sheet: `SUM(KM)` reads **410.41** across **1,901** segments. In
`expected/speed_by_limit.csv` those are the four rows below the 50 km/h default, `segments`
5 + 3 + 55 + 1,838 = 1,901, and `total_km` 2.3 + 0.59 + 21.28 + 386.23. Note that the
golden rounds `total_km` per posted speed, so adding the four printed values gives 410.40
while the unrounded sum Tableau computes rounds to 410.41. The full network is 6,905.74 km
over 13,835 segments, of which 156 segments (246.78 km) carry no posted limit and drop out
of the filter.

If any tied figure differs, the export loaded is stale: re-run `python run.py` from the
project folder, then refresh the extracts in Tableau.
