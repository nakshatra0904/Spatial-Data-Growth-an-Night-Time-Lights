# Data sources, processing, and rights

## Official source

All included data derive from the [SHRUG v2.2 platform](https://www.devdatalab.org/shrug), Development Data Lab. Download access is through its [download page](https://www.devdatalab.org/shrug_download/). We obtained the district-level Stata files and district GeoPackage below on 30 September 2026. The files are keyed by zero-padded Census 2011 state and district IDs.

| Source file | Relevant columns | Source documentation | Role |
| --- | --- | --- | --- |
| `viirs_annual_pc11dist.dta` | `pc11_state_id`, `pc11_district_id`, `year`, `category`, `viirs_annual_sum` | [VIIRS metadata](https://docs.devdatalab.org/SHRUG-Metadata/Night-time%20lights/Tables/viirs-annual-metadata/) | Main light outcome; `average-masked` main and `median-masked` sensitivity. |
| `dmsp_pc11dist.dta` | district IDs, `year`, `dmsp_f_version`, `dmsp_total_light_cal` | [DMSP metadata](https://docs.devdatalab.org/SHRUG-Metadata/Night-time%20lights/Tables/dmsp-metadata/) | Separate historical check. |
| `pc11_pca_clean_pc11dist.dta` | 2011 population, age 0-6, literacy, main worker occupation, SC/ST counts | [2011 Census abstract metadata](https://docs.devdatalab.org/SHRUG-Metadata/Population%20Census/Tables/pca11-metadata/) | Fixed baseline population and controls. |
| `dist_pc11_pop_area_key.dta` | 2011 population, land area | [SHRUG documentation](https://docs.devdatalab.org/) | Density and population consistency check. |
| `district.gpkg` | 2011 district identifiers, name, polygon | [Open polygon metadata](https://docs.devdatalab.org/SHRUG-Metadata/Open%20Polygons%20and%20Spatial%20Statistics/open-poly-metadata/) | Spatial weights and maps. |

The raw VIIRS district file has 15,360 rows, comprising 640 districts, 12 years (2012-2023), and two masks. The metadata page is titled 2012-2021, so the main derived panel uses only those ten documented years. The raw DMSP district table has 20,480 satellite-year rows, 640 districts, and years 1994-2013. Averaging calibrated light within district-year across available satellites yields a 12,800-row panel; this avoids double counting districts when two satellite products exist in one year. It does **not** eliminate all inter-satellite measurement concerns.

The 2011 Census and population/area key each have 640 records. Their population counts agree exactly after joining. The polygon file has one extra polygon with `pc11_state_id=01`, `pc11_district_id=000`, and no district name; it has no matching census or light record and is excluded. The remaining 640 polygon keys match the data. No rows are lost from the principal endpoint analysis.

We also inspected the SHRUG 1991/2001 village/town abstract tables and `shrid_pc11dist_key.dta` but did not use a reconstructed historical district population in the main analysis. The crosswalk is not strictly many-to-one: 108 SHRIDs map to multiple 2011 districts. Naive aggregation would duplicate people; arbitrary equal splitting would create measurement error. A fixed, directly observed 2011 denominator is a more transparent choice for this study. Accordingly, the variable is called **light per 1,000 baseline residents**, not contemporaneous per-capita light.

## Derived definitions

- `light_per_1000_baseline_residents = 1000 * annual_light_sum / pop2011`.
- `log_light_per_1000 = log(light_per_1000_baseline_residents)` for strictly positive light. The `asinh` column is preserved for zero-compatible extensions; it is not the primary regression outcome.
- `growth_annual = (log_light_2021 - log_light_2013) / 8` in the main specification.
- `density2011 = pop2011 / area_km2`; `literacy2011 = literate / (total population - population age 0-6)`; `agwork2011 = (main cultivators + main agricultural laborers) / all main workers`; `scst2011 = (Scheduled Caste + Scheduled Tribe population) / total population`.
- The main spatial weights use Queen polygon contiguity, row standardized. Twelve districts have no Queen neighbor and keep zero rows. The sensitivity weights use eight nearest representative points projected to EPSG:6933.

The light sums from DMSP and VIIRS have different sensors, calibration, and units. We never place them in one regression time series or calculate a growth rate spanning the sensor change. DMSP 2000-2013 is a separate sign check only.

## Rights and attribution

The source and derived data and polygons are for **noncommercial use** under [Creative Commons Attribution-NonCommercial-ShareAlike 4.0](https://docs.devdatalab.org/Getting-Started/license/). Attribute Development Data Lab and the data contributors. The included maps also derive from the source geometry and inherit those data terms. Commercial reuse requires a separate license from Development Data Lab. The accompanying *analysis code* is MIT-licensed, as stated in `LICENSE`.

Suggested platform citation: Asher, Sam; Lunt, Tobias; Matsuura, Ryu; and Novosad, Paul (2021), “Development Research at High Geographic Resolution: An Analysis of Night-Lights, Firms, and Poverty in India Using the SHRUG Open Data Platform,” *World Bank Economic Review* 35(4), 845-871, [doi:10.1093/wber/lhab003](https://doi.org/10.1093/wber/lhab003). For night lights as an economic proxy, see Henderson, Storeygard, and Weil (2012), [doi:10.1257/aer.102.2.994](https://doi.org/10.1257/aer.102.2.994). See the SHRUG [citation guidance](https://docs.devdatalab.org/Getting-Started/citation/) for component-specific attribution.
