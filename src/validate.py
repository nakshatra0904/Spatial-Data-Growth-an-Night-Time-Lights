"""Independent checks on joins, reported statistics, clusters, and the PDF."""
import json
import re
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/derived'
TABLES=ROOT/'results/tables'
FIG=ROOT/'results/figures'
KEY=['pc11_state_id','pc11_district_id']

v=pd.read_csv(DATA/'panel_viirs.csv',dtype={KEY[0]:str,KEY[1]:str})
d=pd.read_csv(DATA/'panel_dmsp.csv',dtype={KEY[0]:str,KEY[1]:str})
g=gpd.read_file(DATA/'districts.gpkg')
prep=json.loads((DATA/'preparation_checks.json').read_text(encoding='utf-8'),
                parse_constant=lambda x: (_ for _ in ()).throw(ValueError(f'Non-finite JSON: {x}')))
head=json.loads((TABLES/'headline_results.json').read_text(encoding='utf-8'))
assert len(v)==12800 and len(d)==12800 and len(g)==640
assert not v.duplicated(KEY+['year','category']).any()
assert not d.duplicated(KEY+['year']).any()
assert not g.duplicated(KEY).any()
assert set(map(tuple,v[KEY].values))==set(map(tuple,g[KEY].values))
assert set(map(tuple,d[KEY].values))==set(map(tuple,g[KEY].values))
assert sorted(v.year.unique().tolist())==list(range(2012,2022))
assert sorted(d.year.unique().tolist())==list(range(1994,2014))
assert prep['polygon_rows_excluded']==[{'pc11_state_id':'01','pc11_district_id':'000','district_name':None}]
for column in ['pop2011','area_km2','density2011']:
    assert (v[column]>0).all(),column
for column in ['literacy2011','agwork2011','scst2011']:
    assert v[column].between(0,1).all(),column
assert np.allclose(v.light_per_1000_baseline_residents,
                   v.viirs_annual_sum/v.pop2011*1000,rtol=1e-8,atol=1e-8)
q=v[(v.category=='average-masked')&(v.year.isin([2013,2021]))]
p=q.pivot(index=KEY,columns='year',values='log_light_per_1000')
growth=(p[2021]-p[2013])/8
assert np.isclose(growth.mean(),head['mean_annual_log_growth'],atol=1e-9)
assert np.isclose(growth.median(),head['median_annual_log_growth'],atol=1e-9)
assert np.isclose((growth<0).mean(),head['share_negative_growth'],atol=1e-9)
assert (q.viirs_annual_sum>0).all()

lisa=pd.read_csv(TABLES/'lisa_growth.csv',dtype={KEY[0]:str,KEY[1]:str})
assert len(lisa)==640 and not lisa.duplicated(KEY).any()
assert lisa.cluster.value_counts().to_dict()==head['lisa_clusters']
no_neighbor=lisa[lisa.cluster=='no contiguous neighbor']
assert len(no_neighbor)==head['weights']['queen_islands']==12
assert no_neighbor.p_unadjusted.isna().all()
assert (~no_neighbor.significant_fdr05).all()

regions=pd.read_csv(TABLES/'spatial_regions.csv',dtype={KEY[0]:str,KEY[1]:str})
profile=pd.read_csv(TABLES/'spatial_region_profiles.csv')
assert len(regions)==640 and profile.n.sum()==640
assert len(profile)==head['spatial_typology']['selected_k']==3
assert all(v==1 for v in head['spatial_typology']['connected_components_by_cluster'].values())

impact=pd.read_csv(TABLES/'sdm_impacts.csv')
assert np.allclose(impact.direct+impact.indirect,impact.total,atol=1e-12)
for kind in ['direct','indirect','total']:
    assert ((impact[f'{kind}_ci_low']<=impact[kind]) &
            (impact[kind]<=impact[f'{kind}_ci_high'])).all()
initial=impact[impact.term=='log_initial'].iloc[0]
assert initial.direct_ci_high<0 and initial.total_ci_high<0
assert initial.indirect_ci_low<0<initial.indirect_ci_high

robust=pd.read_csv(TABLES/'robustness.csv')
assert len(robust)==7 and (robust.ols_initial_beta<0).all()
assert (robust.n>=626).all()
assert all((FIG/f).stat().st_size>40_000 for f in [
    'viirs_trend.png','distribution_convergence.png','growth_maps.png',
    'spatial_regions.png','ols_residuals.png'])

tex=(ROOT/'report/report.tex').read_text(encoding='utf-8')
for phrase in ['640','0.654','0.0457','0.158','\n\\end{document}']:
    assert phrase in tex,phrase
assert r'\author{Nakshatra Ghosh}' in tex
assert tex.count('{')==tex.count('}')
for name in re.findall(r'\\includegraphics\[[^]]*\]\{([^}]+)\}',tex):
    assert (FIG/name).exists(),name
envs=[]
for match in re.finditer(r'\\(begin|end)\{([^}]+)\}',tex):
    if match.group(1)=='begin':envs.append(match.group(2))
    else:assert envs and envs.pop()==match.group(2),match.group(0)
assert not envs
pdf=PdfReader(ROOT/'report/report.pdf')
assert 8<=len(pdf.pages)<=20
all_text='\n'.join(page.extract_text() or '' for page in pdf.pages)
for phrase in ['Spatial Durbin','37 high-high','5,000','2011 population','CC BY-NC-SA']:
    assert phrase in all_text,phrase
assert 'Nakshatra Ghosh' in all_text

result={'status':'pass','districts':640,'viirs_panel_rows':len(v),'dmsp_panel_rows':len(d),
    'main_endpoint_rows':len(p),'lisa_islands_excluded':len(no_neighbor),
    'spatial_regions':int(len(profile)),'pdf_pages':len(pdf.pages),
    'checks':['joins','formulae','bounded covariates','reported descriptive statistics',
              'local Moran islands','regionalization','impact arithmetic and intervals',
              'robustness sign','figures','report text']}
(TABLES/'validation_checks.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
