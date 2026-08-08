# BI layer: Land use composition by community

Both dashboards read the same frozen output the SQL export step wrote: the
per-community-and-class mart `bi/exports/mart_landuse.csv` (580 rows: `community,
zone_class, polygons, area, area_share`), and, for the Tableau map, the tagged
polygon layer `bi/exports/zoning_tagged.geojson` (11,076 features carrying
`zone_class, community, zone, description, area_km2`). Neither tool recomputes
the analysis; both aggregate the mart as written, so a figure read off one
dashboard equals the same figure on the other and in the SQL golden. `area` is
geodesic ground area in square kilometres.

Tableau covers the geography and the within-community split: a filled zoning
choropleth plus a stacked bar whose shares come from a FIXED LOD. Power BI covers
the ranking and the grid: area-share DAX measures, a RANKX ranking of the most
mixed communities, and a conditional-format matrix of class by community.

---

## Tableau (free Desktop Public Edition + a public.tableau.com account)

Extract-only from the CSV, live spatial connection for the GeoJSON. Publish for
the live link. Commit the `.twb` (diffable XML), never the `.twbx`.

**Geocoding note.** Halifax communities are not a built-in Tableau geographic
role, so this build does not bind to a named role. The choropleth reads the
polygon geometry the tagged GeoJSON carries directly, and the stacked bar uses
`community` as a plain discrete dimension.

1. **Connect the map layer.** Open Tableau Public. Connect to Spatial file and
   pick `bi/exports/zoning_tagged.geojson`. Tableau exposes a `Geometry` field
   plus the tagged attributes.

2. **Sheet "Land use map".** Double-click `Geometry` so the polygons plot. Drag
   `zone_class` to Color. This is the zoning choropleth: every polygon filled by
   its broad land use class. Optionally drag `community` and `description` to
   Tooltip. Keep borders thin so the fills read.

3. **Add the mart.** On the data source pane, add a second connection to a Text
   file and pick `bi/exports/mart_landuse.csv`; choose Extract. Set `area` and
   `area_share` to Number (decimal), `community` and `zone_class` to string
   dimensions, `polygons` to a whole number.

4. **Sheet "Composition by community".** From the mart, drag `community` to
   Columns and `SUM(area)` to Rows, then drag `zone_class` to Color. That is the
   stacked bar of zoned area by class per community. To show each class's share of
   its own community independent of any filter, add two calculated fields:

       Community Area = { FIXED [Community] : SUM([Area]) }
       Class Share of Community = SUM([Area]) / MIN([Community Area])

   The FIXED LOD fixes the community denominator, so the share stays correct even
   when a class filter is applied: tick a single class and the bars shorten while
   the labels still read the share of the whole community.

5. **Rank the communities by mix.** All 182 communities will not fit one bar, and
   sorting by area surfaces only the large rural single-zone communities, whose
   bars are one solid colour. Rank by mix instead, with two more LODs (the first
   is nested):

       Largest Class Area = { FIXED [Community] : MAX({ FIXED [Community], [Zone Class] : SUM([Area]) }) }
       Mix Index = 1 - ([Largest Class Area] / [Community Area])

   Drag `Community` to Filters, and on the **Top** tab set Top 15 by `Mix Index`,
   aggregation **Maximum**. Then sort `Community` by `Mix Index` descending, again
   with **Maximum**. Use Maximum, not Sum: `Mix Index` is a row-level LOD that
   repeats on every class row, so Sum would scale it by the class count and
   misorder the communities.

6. **Label only the dominant class.** Labelling every segment makes the thin ones
   collide. Add:

       Dominant Class Share = IF ABS(SUM([Area]) - MIN([Largest Class Area])) < 0.0001
                              THEN SUM([Area]) / MIN([Community Area]) END

   Put it on Label and format it as a percentage. That yields exactly one label
   per bar, on the largest class, which is the figure the ranking is built on.
   Keep `Class Share of Community` on Tooltip so every segment is still readable.
   Tick "Allow labels to overlap other marks" on the Label card so all 15 render.

7. **Dashboard "Land use composition".** Add both sheets, and switch Size from
   Range to a fixed Desktop Browser (1000 x 800) so the bars have room. The two
   sheets sit on different data sources, so one filter does not drive both by
   default: open Data > Edit Blend Relationships (from a worksheet tab, it is
   disabled on a dashboard), set `zoning_tagged` primary and `mart_landuse`
   secondary, Custom, and map `Zone Class` to `Zone Class`. Then right-click the
   `Zone Class` filter card and choose **Apply to Worksheets > All Using Related
   Data Sources**, and remove the duplicate filter and legend cards. Save the
   workbook as `bi/tableau/land_use_composition.twb`. Publish to Tableau Public.

Live viz: https://public.tableau.com/views/Halifaxlandusecomposition/Landusecomposition

Dashboard screenshot: `bi/tableau/screenshots/dashboard-full.png`.

---

## Power BI (free Desktop)

Turn on the `.pbip` project save option (File > Options and settings > Options >
Preview features > "Store report using enhanced metadata / Power BI Project
(.pbip) save option"). Commit the `.pbip` text folders, never a `.pbix`. Free
Desktop has no public link, so the deliverable is the committed project plus an
exported PNG or PDF.

1. **Get data.** Home > Get Data > Text/CSV, pick `bi/exports/mart_landuse.csv`,
   then Transform Data. Set the column types: `community` and `zone_class` to
   Text; `area` and `area_share` to Decimal Number (`polygons` to Whole Number).
   Close & Apply. Rename the table `mart_landuse`.

2. **Measures** (New measure, one each, verbatim):

   ```DAX
   Total Area = SUM ( mart_landuse[area] )
   ```

   ```DAX
   Community Area = CALCULATE ( [Total Area], ALLEXCEPT ( mart_landuse, mart_landuse[community] ) )
   ```

   ```DAX
   Area Share = DIVIDE ( [Total Area], [Community Area] )
   ```

   ```DAX
   Largest Class Share = MAXX ( VALUES ( mart_landuse[zone_class] ), [Area Share] )
   ```

   ```DAX
   Mix Index = 1 - [Largest Class Share]
   ```

   ```DAX
   Community Mix Rank = RANKX ( ALLSELECTED ( mart_landuse[community] ), [Mix Index], , DESC, Skip )
   ```

   `Community Area` uses `ALLEXCEPT` so the denominator is the community's total
   zoned area regardless of the current `zone_class` row context; `Area Share` is
   then each class's share of its community. `Mix Index` is one minus the largest
   class share, and `Community Mix Rank` ranks the communities by it, so rank 1 is
   the most mixed. Format `Area Share`, `Largest Class Share`, and `Mix Index` as
   percentages.

3. **Visuals.** Add a page-level filter `community is not Unassigned` first: the
   mart keeps the `Unassigned` edge bucket (zero rounded area) for completeness,
   but with zero area its `[Area Share]` is blank and its `[Mix Index]` computes
   to 100%, which would otherwise top every ranking. Excluding it matches the SQL
   golden, which ranks real communities only.
   - A **Matrix**: Rows = `zone_class`, Columns = `community`, Values =
     `[Area Share]`, with conditional formatting (background colour scale) on the
     share. This is the composition grid.
   - A **ranked bar** of `community` by `[Mix Index]`, sorted descending, with
     `[Community Mix Rank]` added to the tooltip. This surfaces the most mixed
     communities.
   - **Cards** for the top community, showing `[Mix Index]` and
     `[Largest Class Share]` (filter or drill to the rank-1 community).
   - A **zone_class slicer** on `mart_landuse[zone_class]`.

   Save the project into `bi/powerbi/` as a `.pbip` and commit the `.pbip` plus
   its `.Report` and `.SemanticModel` folders. Export a PNG or PDF for the record.

---

## Numbers match

Bedford is the most mixed community, with its largest zone class at 30.59
percent, matching across the SQL golden (`expected/community_mix_ranking.csv`,
rank 1), the Tableau stacked bar (Bedford leads the mix ranking and its
`Dominant Class Share` label reads 30.59%, computed from the FIXED LOD
`Community Area`), and the Power BI matrix (Bedford's column tops out at
`[Area Share]` 30.59%, with `[Community Mix Rank]` 1). Both tools also agree on
the rest of the ranking, Halifax 32.40% and Lower Sackville 33.21% next, and on
the municipal lead, Mixed Use at 40.20% of HRM zoned land.
