"""Create a layout-checked PDF reading copy of the LaTeX research report.

This uses the same saved model tables and figures as report.tex because the
built-in LaTeX compiler on this Windows host failed before reading source.
"""
import json
from html import escape
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, Image, KeepTogether, PageBreak, Paragraph,
    SimpleDocTemplate, Spacer, Table, TableStyle,
)

ROOT=Path(__file__).resolve().parents[1]
RESULTS=ROOT/'results'
OUT=ROOT/'report/report.pdf'
HEAD=json.loads((RESULTS/'tables/headline_results.json').read_text(encoding='utf-8'))
ROBUST=pd.read_csv(RESULTS/'tables/robustness.csv')
IMPACTS=pd.read_csv(RESULTS/'tables/sdm_impacts.csv')
PROFILES=pd.read_csv(RESULTS/'tables/spatial_region_profiles.csv')
NAVY=colors.HexColor('#19354A')
TEAL=colors.HexColor('#137F8B')
PALE=colors.HexColor('#EAF2F4')
GRAY=colors.HexColor('#53636C')

styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='TitleCustom',fontName='Helvetica-Bold',fontSize=21,leading=26,
    textColor=NAVY,spaceAfter=13,alignment=TA_LEFT))
styles.add(ParagraphStyle(name='SubtitleCustom',fontName='Helvetica',fontSize=12.2,leading=17,
    textColor=TEAL,spaceAfter=17))
styles.add(ParagraphStyle(name='BodyCustom',fontName='Helvetica',fontSize=9.6,leading=14.2,
    textColor=NAVY,spaceAfter=7))
styles.add(ParagraphStyle(name='SmallCustom',fontName='Helvetica',fontSize=8.3,leading=11.3,
    textColor=GRAY,spaceAfter=6))
styles.add(ParagraphStyle(name='H1Custom',fontName='Helvetica-Bold',fontSize=14.2,leading=18,
    textColor=NAVY,spaceBefore=13,spaceAfter=8,keepWithNext=True))
styles.add(ParagraphStyle(name='H2Custom',fontName='Helvetica-Bold',fontSize=10.5,leading=14,
    textColor=TEAL,spaceBefore=10,spaceAfter=5,keepWithNext=True))
styles.add(ParagraphStyle(name='CaptionCustom',fontName='Helvetica-Oblique',fontSize=8.2,leading=11.3,
    textColor=GRAY,spaceBefore=5,spaceAfter=12))
styles.add(ParagraphStyle(name='QuoteCustom',fontName='Helvetica',fontSize=10,leading=15,
    textColor=NAVY,leftIndent=13,rightIndent=13,spaceBefore=8,spaceAfter=11,
    backColor=PALE,borderPadding=9))


def P(text,kind='BodyCustom'):
    return Paragraph(text,styles[kind])


def table(rows,widths=None,header=True):
    wrapped=[]
    for i,row in enumerate(rows):
        if i==0 and header:
            wrapped.append([P(f'<font color="#ffffff"><b>{escape(str(c))}</b></font>','SmallCustom') for c in row])
        else:
            wrapped.append([P(escape(str(c)),'SmallCustom') for c in row])
    t=Table(wrapped,colWidths=widths,repeatRows=1 if header else 0,hAlign='LEFT')
    commands=[('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),5),
       ('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),5),
       ('BOTTOMPADDING',(0,0),(-1,-1),4),('LINEBELOW',(0,-1),(-1,-1),.6,NAVY)]
    if header:commands += [('BACKGROUND',(0,0),(-1,0),NAVY),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('LINEBELOW',(0,0),(-1,0),1,NAVY)]
    for i in range(1,len(rows)):
        if i%2==0:commands.append(('BACKGROUND',(0,i),(-1,i),colors.HexColor('#F5F8F9')))
    t.setStyle(TableStyle(commands))
    return t


def figure(name,width_mm,caption):
    p=RESULTS/'figures'/name
    img=Image(str(p))
    scale=(width_mm*mm)/img.imageWidth
    img.drawWidth=width_mm*mm
    img.drawHeight=img.imageHeight*scale
    return KeepTogether([img,P(caption,'CaptionCustom')])


def footer(canvas,doc):
    canvas.saveState()
    w,h=A4
    canvas.setStrokeColor(colors.HexColor('#CBD8DC'))
    canvas.setLineWidth(.5)
    canvas.line(20*mm,17*mm,w-20*mm,17*mm)
    canvas.setFont('Helvetica',8)
    canvas.setFillColor(GRAY)
    canvas.drawString(20*mm,12*mm,'Indian district night-light growth  |  SHRUG v2.2')
    canvas.drawRightString(w-20*mm,12*mm,str(doc.page))
    canvas.restoreState()


story=[]
def add(*items):story.extend(items)
def heading(t):add(P(t,'H1Custom'))
def subheading(t):return P(t,'H2Custom')

add(Spacer(1,18*mm),P('SPATIAL PATTERNS IN INDIAN DISTRICT NIGHT-LIGHT GROWTH','TitleCustom'),
    P('Descriptive statistics, spatial econometrics, and cluster analysis','SubtitleCustom'),
    P('Nakshatra Ghosh','SubtitleCustom'),
    HRFlowable(width='100%',thickness=2,color=TEAL),Spacer(1,9*mm),
    P('Research report  |  1 October 2026','SmallCustom'))
add(P('Abstract','H1Custom'),
    P('This study analyzes 640 Indian Census 2011 districts using SHRUG v2.2 nighttime lights. '
      'The main comparison uses VIIRS 2013-2021 and fixed 2011 population to normalize district size. '
      'Lower initially lit districts show faster subsequent light growth in a conditional model, while '
      'growth is strongly spatially clustered. Spatial lag, spatial error, and spatial Durbin models '
      'separate forms of dependence. Local Moran analysis and a graph-constrained Ward typology '
      'describe regional clusters. These are associations in satellite light, not district GDP or causal spillovers.'),
    P('Key results','H1Custom'))
add(table([
    ['Measure','Estimate'],
    ['Mean annual 2013-2021 log-light growth','0.0682'],
    ['Conditional OLS initial-light coefficient','-0.0457 (HC3 SE 0.00344)'],
    ['Global Moran I for growth','0.654 (permutation p = 0.001)'],
    ['Spatial Durbin rho','0.3253'],
    ['Spatial Durbin residual Moran I','-0.0037 (p = 0.935)'],
    ['FDR-significant high-high / low-low districts','37 / 37'],
],widths=[112*mm,56*mm]),Spacer(1,6*mm),
    P('Interpretation: Light is normalized by each district\'s 2011 population, held fixed in every year. '
      'It is therefore baseline-population-normalized light, not contemporaneous per-capita income.','QuoteCustom'),
    PageBreak())

heading('1  Research question and data')
add(P('The first project in the supplied brief asks whether less initially lit Indian districts grew faster, '
      'whether growth forms spatial clusters, and whether nearby outcomes or characteristics are associated '
      'with district growth. The unit is the Census 2011 district, held fixed over time. Night lights are an '
      'imperfect economic activity proxy: electrification, lighting technology, and settlement patterns also matter.'),
    P('The source tables are SHRUG v2.2 district VIIRS annual sum, calibrated DMSP district light, the 2011 '
      'Population Census Abstract, a population/land-area key, and district polygons. The raw VIIRS table '
      'covers 2012-2023, but published metadata describes 2012-2021; the documented range is used here. '
      'VIIRS and DMSP are never spliced.'),
    P('Data audit','H2Custom'),
    table([
        ['Check','Result'],
        ['District census and area rows','640 each; population values agree'],
        ['VIIRS derived panel','12,800 rows = 640 x 10 years x 2 masks'],
        ['DMSP derived panel','12,800 rows = 640 x 20 years'],
        ['Polygon match','640 exact keys; one unlabeled district-000 placeholder removed'],
        ['Main endpoint sample','640 districts, no missing covariates, positive endpoint VIIRS light'],
    ],widths=[49*mm,119*mm]),
    P('Variable construction','H2Custom'),
    P('For district i and year t, L_it = 1,000 x VIIRS_sum_it / population_i,2011; '
      'z_it = log(L_it); and annual growth g_i = (z_i,2021 - z_i,2013) / 8. The fixed denominator '
      'means the growth rate equals growth of total district light. Baseline controls are log 2011 density, '
      'adult literacy, agricultural main-worker share, Scheduled Caste/Tribe share, and state indicators.'),
    P('The principal log comparison starts in 2013 because the 2012 VIIRS observations include zeros. '
      'For DMSP, concurrent calibrated satellite measurements are averaged within district-year. '
      'The historical log check begins in 2000, the first year positive for every district.'),
    PageBreak())

heading('2  Numerical and visual description')
add(table([
    ['District variable','Mean','Median','P10','P90'],
    ['VIIRS per 1,000 baseline residents, 2013','7.689','6.068','1.641','15.259'],
    ['VIIRS per 1,000 baseline residents, 2021','11.209','9.829','4.653','18.272'],
    ['Annual log-light growth','0.0682','0.0588','-0.0004','0.1478'],
    ['2011 density','994.0','409.8','137.7','1251.8'],
    ['2011 literacy share','0.723','0.722','0.590','0.854'],
    ['2011 agricultural worker share','0.533','0.591','0.197','0.773'],
],widths=[78*mm,23*mm,23*mm,22*mm,22*mm]),
    Spacer(1,4*mm),
    P('Mean normalized light rises 45.8% from 2013 to 2021; the median rises 62.0%. '
      'Mean annual log growth is 0.0682 and 10.5% of districts have negative endpoint growth. '
      'The distribution is right-skewed. The annual series has a noticeable 2016-2017 step, '
      'which could reflect illumination or processing as well as activity.'),
    figure('viirs_trend.png',151,'Figure 1. VIIRS district mean and median light per 1,000 fixed 2011 residents.'),
    PageBreak())

heading('3  Distribution and spatial clustering')
add(figure('distribution_convergence.png',168,
      'Figure 2. Growth distribution and unconditional OLS line with a 95% confidence band for the fitted mean.'),
    P('The fitted unconditional line is g = 0.16662 - 0.05737 x log(initial normalized VIIRS light), '
      'R-squared = 0.586. The negative slope is an association in annual log-light growth, '
      'not a line for GDP growth. The conditional fitted relation instead has an initial-light '
      'slope of -0.04569 after controls and state effects (full equation in report.tex).'),
    P('Global Moran I compares district deviations with the weighted deviations of Queen-contiguous '
      'neighbors. The Queen graph has 4.14 neighbors per district on average, 34 disconnected components, '
      'and 12 districts with no contiguous neighbor. Those 12 retain zero rows in W; no distant boundary is invented. '
      'An eight-nearest-neighbor graph is a sensitivity test.'),
    table([
        ['Moran test','I','Two-sided permutation p'],
        ['Initial normalized light','0.6124','0.001'],
        ['Annual growth','0.6544','0.001'],
        ['Conditional OLS residual','0.1693','0.001'],
        ['Spatial Durbin residual','-0.0037','0.935'],
    ],widths=[93*mm,27*mm,48*mm]),
    Spacer(1,3*mm),
    P('Local Moran statistics use 999 permutations and Benjamini-Hochberg false discovery rate control '
      'at 5% over the 628 districts with a Queen neighbor. Results: 37 high-high, 37 low-low, '
      'two low-high, 552 not significant, and 12 with no contiguous neighbor. High-high examples '
      'include districts in Bihar and Manipur. Spatial clustering does not by itself establish diffusion.'),
    PageBreak())

heading('4  Where growth clusters occur')
add(figure('growth_maps.png',168,
      'Figure 3. Annual 2013-2021 growth and Local Moran classes after FDR correction. Dark gray marks no-neighbor districts.'),
    P('The map shows broad geographic heterogeneity, including fast-growing clusters in parts of '
      'Bihar and the northeast. Neighbor definitions matter where the source polygons have gaps or '
      'inaccuracies; the supplied SHRUG map documentation cautions about boundary precision.'),
    subheading('A second cluster analysis: graph-constrained Ward grouping'))
add(P('We standardize five district features: initial log light, annual growth, log density, literacy, '
      'and agricultural employment share. Ward agglomerative clustering may merge districts only along '
      'a symmetric eight-nearest-neighbor graph. We compare two through six groups with the silhouette '
      'score. Three groups score highest (0.158), and each is connected in the graph. The low score '
      'signals modest separation, so these are a descriptive typology, not sharply defined economic regions. '
      'Growth is an input to clustering and cannot be used as an independent validation.'),
    PageBreak())

heading('5  Spatially constrained district typology')
add(figure('spatial_regions.png',146,
      'Figure 4. Three Ward groups constrained by a symmetric eight-nearest-neighbor graph.'),
    table([
        ['Group','Districts','Mean growth','Mean initial log light','Median density'],
        ['1','252','0.1023','1.443','351.6'],
        ['2','347','0.0406','1.999','495.5'],
        ['3','41','0.0924','0.997','56.6'],
    ],widths=[22*mm,28*mm,35*mm,49*mm,34*mm]),
    P('Group 1 combines relatively low initial light and fast growth; group 2 has higher initial '
      'light and slower growth; group 3 has very low density and fast growth. These profiles follow '
      'in part from the features used to form the groups.'),
    PageBreak())

heading('6  Econometric theory and implementation')
add(subheading('OLS benchmark and convergence'))
add(P('The absolute model regresses annual growth g_i on initial log light z_i,2013. The conditional '
      'model adds 2011 district characteristics and state indicators. HC3 robust standard errors allow '
      'heteroskedasticity. A negative coefficient is consistent with initially darker districts '
      'catching up in light, conditional on measured covariates. Under a restrictive transitional '
      'growth law, beta = (exp(-8 lambda)-1)/8, so lambda = -log(1+8 beta)/8 is an implied speed.'),
    P('Estimated conditional equation (state 01 as the reference): g-hat = 0.22351 '
      '- 0.04569 initial log light - 0.01563 log density + 0.01361 literacy '
      '- 0.01720 agricultural worker share - 0.01023 SC/ST share + fitted state effect. '
      'The intercept is a model reference term; the plotted line is the simpler unconditional fit.'),
    subheading('Three spatial alternatives'),
    P('<b>SAR:</b> g = rho Wg + Zb + error. The simultaneous spatial outcome term requires '
      'maximum likelihood; rho captures conditional spatial association. <b>SEM:</b> g = Zb + u, '
      'u = lambda Wu + error, attributing dependence to unobserved spatial shocks. '
      '<b>SDM:</b> g = rho Wg + Zb + WZ theta + error, adding neighbors\' initial light and '
      'other continuous characteristics. State indicators are never spatially lagged. '
      'All spatial models use Gaussian maximum likelihood with the Ord eigenvalue method.'),
    P('In the SDM, impacts require the matrix S_k = (I-rho W)^(-1)(beta_k I + theta_k W). '
      'Average direct impact is trace(S_k)/n; average total impact is 1\'S_k 1/n; '
      'indirect impact is total minus direct. Exact matrix calculations retain the zero-neighbor rows. '
      'Uncertainty intervals draw 5,000 times from the full model covariance matrix. '
      'They do not cover uncertainty about W or the source measurement.'),
    subheading('Diagnostics'),
    P('We compare AIC, a nested likelihood-ratio test for SAR versus SDM, and Moran tests on model '
      'residuals. OLS standard errors are HC3; spatial-model standard errors use the Gaussian '
      'likelihood. Neither specification delivers causal identification.'),
    PageBreak())

heading('7  Model estimates and interpretation')
add(table([
    ['Model','Initial coefficient','Spatial parameter','AIC','Residual I'],
    ['OLS: initial level only','-0.0574','--','--','--'],
    ['OLS: controls + state','-0.0457','--','-2637.6','0.1693'],
    ['SAR: controls + state','-0.0433','rho 0.1966','-2658.3','0.0690'],
    ['SEM: controls + state','-0.0459','lambda 0.3169','-2672.9','0.0114*'],
    ['SDM: controls + state','-0.0468','rho 0.3253','-2673.7','-0.0037'],
],widths=[48*mm,34*mm,34*mm,25*mm,27*mm]),
    P('* SEM reports Moran I for its filtered innovations. All models use 640 districts. '
      'The OLS conditional initial-light coefficient has HC3 SE 0.00344 and R-squared 0.800. '
      'Its implied speed is 5.69% per year (approximately 4.67%-6.80% from its coefficient interval), '
      'conditional on the transitional-growth interpretation.','SmallCustom'),
    P('SAR leaves modest residual spatial dependence (I = 0.0690, p = 0.024). '
      'SEM filtered innovations (I = 0.0114, p = 0.665) and SDM residuals '
      '(I = -0.0037, p = 0.935) do not show detectable residual clustering. '
      'SDM has the lowest AIC, but its 0.84-point advantage over SEM is small. '
      'The nested SAR-versus-SDM likelihood-ratio statistic is 25.40 on five extra '
      'spatially lagged regressors (p = 0.000117). The data support additional '
      'spatial structure compared with SAR without decisively separating covariate '
      'spillovers from spatially correlated omitted factors.'),
    subheading('Spatial Durbin impacts of initial log light'),
    table([
        ['Impact','Point estimate','95% lower','95% upper'],
        ['Average direct','-0.04652','-0.05089','-0.04221'],
        ['Average indirect','0.00428','-0.00358','0.01222'],
        ['Average total','-0.04225','-0.05107','-0.03359'],
    ],widths=[48*mm,40*mm,40*mm,40*mm]),
    P('The neighboring initial-light coefficient in the SDM is positive, but the '
      'average indirect impact interval crosses zero. It is therefore not evidence '
      'for a precisely signed average spillover. The negative direct and total '
      'impacts align with convergence in this light proxy. The outcome-spatial '
      'parameter is an association, not proof that one district caused another to grow.'),
    PageBreak())

heading('8  Robustness checks')
rows=[['Specification','Districts','Conditional OLS beta (HC3 SE)','SAR rho']]
mapping=[('VIIRS median-masked','VIIRS_median_2013_2021'),
 ('VIIRS 2014-2019','VIIRS_average_2014_2019'),
 ('VIIRS eight-neighbor graph','VIIRS_average_2013_2021_knn8'),
 ('Two-year-smoothed endpoints','VIIRS_average_smoothed_two_year_endpoints'),
 ('Queen non-islands','VIIRS_average_queen_nonislands'),
 ('Separate DMSP 2000-2013','DMSP_calibrated_2000_2013'),
 ('Trim 1% in both growth tails','VIIRS_average_trim_growth_1pct_each_tail')]
for label,key in mapping:
    r=ROBUST[ROBUST.specification==key].iloc[0]
    rho='--' if pd.isna(r.sar_rho) else f'{r.sar_rho:.3f}'
    rows.append([label,str(int(r.n)),f'{r.ols_initial_beta:.4f} ({r.ols_initial_se_HC3:.4f})',rho])
add(table(rows,widths=[66*mm,22*mm,58*mm,22*mm]),
    P('The negative initial-light association persists under alternative VIIRS masking, '
      'a pre-2020 interval, endpoint smoothing, geographic definitions, removal of '
      'Queen islands, and trimming. The DMSP result is a historical sign check only; '
      'its coefficients must not be compared numerically with VIIRS due to sensor '
      'and processing differences.'),
    figure('ols_residuals.png',148,'Figure 5. Conditional OLS residuals versus fitted annual log growth.'),
    PageBreak())

heading('9  Limits and conclusion')
add(P('First, this is an analysis of lights, not directly observed district GDP or consumption. '
      'Electrification, saturation, blooming, masking, and local economic composition '
      'can alter the lights-output relation. Second, fixed 2011 population does not '
      'measure migration or population growth by 2021. Third, state controls cannot '
      'remove district-specific omitted variables, common regional shocks, or '
      'measurement error. The growth formula reuses the initial light observation, '
      'so regression to the mean may contribute to its negative coefficient. '
      'Fourth, the spatial models rely on a chosen neighbor graph and Gaussian '
      'likelihood; geometry gaps produce disconnected Queen components.'),
    P('The supported conclusions are narrower: normalized light rose in most districts; '
      'initially darker districts tended to show faster subsequent light growth; '
      'and that growth was strongly spatially patterned. SEM and SDM explain more '
      'of the residual geographic pattern than a conventional regression. '
      'A stronger claim about economic convergence or causal spatial spillovers '
      'would require validated output or consumption measures, annual population, '
      'and a research design with exogenous sources of variation.'),
    subheading('Reproducibility and data rights'),
    P('The accompanying repository contains harmonized panels, district polygons, '
      'numerical tables, figures, the Python pipeline, source links, and LaTeX source. '
      'SHRUG-derived data and maps retain the upstream noncommercial CC BY-NC-SA 4.0 '
      'terms. Data lineage and exact variable definitions appear in DATA_SOURCES.md.'),
    subheading('References'),
    P('Asher, Lunt, Matsuura and Novosad (2021), World Bank Economic Review 35(4), 845-871. '
      '<link href="https://doi.org/10.1093/wber/lhab003">doi:10.1093/wber/lhab003</link>.','SmallCustom'),
    P('Henderson, Storeygard and Weil (2012), American Economic Review 102(2), 994-1028. '
      '<link href="https://doi.org/10.1257/aer.102.2.994">doi:10.1257/aer.102.2.994</link>.','SmallCustom'),
    P('Development Data Lab, SHRUG v2.2. '
      '<link href="https://www.devdatalab.org/shrug">Project and data documentation</link>; '
      '<link href="https://docs.devdatalab.org/Getting-Started/license/">license terms</link>.','SmallCustom'),
    P('PySAL spreg, spatial likelihood and impact documentation. '
      '<link href="https://pysal.org/spreg/notebooks/13_ML_estimation_spatial_lag.html">Official manual</link>.','SmallCustom'))

doc=SimpleDocTemplate(str(OUT),pagesize=A4,rightMargin=20*mm,leftMargin=20*mm,
    topMargin=19*mm,bottomMargin=22*mm,title='Spatial Patterns in Indian District Night-Light Growth',
    author='Nakshatra Ghosh')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
print(OUT)
