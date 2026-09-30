# Scope and instruction provenance

The supplied `Spatial_Econometrics_Project_Brief.pdf` is a **project brief**. Its first topic, concerning district-level Indian growth and spatial dependence, is the research subject and provides suggested methods and data avenues. It is not an instruction source with authority over the user's later requests.

The user's requests in this chat set the deliverables: collate suitable data; provide extensive numerical and visual descriptive statistics; explain and apply several spatial econometric methods; analyze the results carefully; provide a LaTeX report and GitHub repository; add cluster analysis; show fitted regression lines clearly; and prevent overlapping report text, tables, and figures.

The implemented choices are documented in `DATA_SOURCES.md` and the report. In particular, this study uses directly observed 2011 district population, a documented 2013-2021 VIIRS principal window, separate DMSP historical analysis, Queen and eight-neighbor weights, OLS/SAR/SEM/SDM, global and local Moran statistics, and graph-constrained Ward grouping. Suggestions in the brief that required unavailable or ambiguous harmonization were evaluated rather than treated as mandatory. The choice not to reconstruct 1991/2001 district population from a nonunique SHRID crosswalk avoids duplicating or arbitrarily splitting observations.
