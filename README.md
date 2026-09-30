# Spatial patterns in Indian district night-light growth

Reproducible district-level descriptive and spatial econometric analysis for the **first project** in the supplied brief. The principal sample is 640 Census 2011 districts observed in SHRUG v2.2 VIIRS annual lights, 2013–2021. Calibrated DMSP lights, 2000–2013, are a separate historical robustness exercise. The satellite products are **never spliced**.

## Main findings

- Mean annual 2013–2021 VIIRS log-light growth is 0.0682; the median is 0.0588. The denominator is each district's **fixed 2011 population**, so this is *baseline-population-normalized light*, not annual per-capita income.
- The conditional OLS initial-light coefficient is -0.0457 (HC3 SE 0.00344), consistent with convergence in this proxy. Measurement error and regression to the mean remain possible.
- Queen-weight Moran's I for growth is 0.654 (999-permutation two-sided p = 0.001). Residual Moran's I falls from 0.169 under OLS to -0.0037 under the spatial Durbin model.
- The spatial Durbin model has rho = 0.325 and fits better than spatial lag in a five-degree-of-freedom likelihood-ratio test (p = 0.000117). Its estimated **indirect initial-light impact has a 95% interval spanning zero**; these results do not establish causal spillovers.
- Local Moran analysis detects 37 high-high and 37 low-low clusters after Benjamini-Hochberg correction. A separate spatially constrained Ward analysis selects three broad regions, but the silhouette score of 0.158 indicates modest separation.

The full interpretation, theory, limitations, and figures are in [the LaTeX report](report/report.tex) and [the accessible PDF reading copy](report/report.pdf). Results are directly inspectable in `results/tables/` and `results/figures/`.

## Contents

| Path | Purpose |
| --- | --- |
| `src/prepare.py` | Joins official SHRUG district files, checks uniqueness, creates harmonized panels. |
| `src/analyze.py` | Descriptives, OLS, SAR, SEM, SDM, global/local Moran, clustering, figures, robustness. |
| `src/validate.py` | Independent data and result checks. |
| `data/derived/` | Analysis-ready VIIRS and DMSP CSVs, district GeoPackage, preparation audit. |
| `results/tables/` | Numeric outputs and coefficient/impact tables. |
| `results/figures/` | Five publication-ready PNG graphics. |
| `report/` | LaTeX source and PDF reading copy. |
| `DATA_SOURCES.md` | Source files, licensing, definitions, and design decisions. |

## Reproduce

Use Python 3.12 or newer and `pip install -r requirements.txt`. For rebuilding the data, download the named official SHRUG v2.2 `.dta` and polygon files listed in `DATA_SOURCES.md`, place them in a directory, then run:

```text
python src/prepare.py --raw /path/to/shrug/files
python src/analyze.py
python src/validate.py
```

The committed derived data let you run the last two steps without repeating the source download. The analytic scripts use a fixed seed (`20261001`) for permutation tests and impact intervals. To compile the LaTeX source with figures on a machine with a standard TeX installation, run `pdflatex report.tex` from the `report/` directory twice. The PDF reading copy is also supplied because the built-in LaTeX compiler on this Windows host returned a platform-directory error before parsing the source.

## Interpretation and rights

These are **associations in satellite light**, not district GDP or causal economic spillovers. The SHRUG-derived tables and geometry are redistributed for noncommercial research under [CC BY-NC-SA 4.0](https://docs.devdatalab.org/Getting-Started/license/), with attribution to Development Data Lab and the underlying contributors. See `DATA_SOURCES.md` for citations and caveats. Code in this repository is released under the MIT License; the data retain their upstream CC BY-NC-SA 4.0 license.
