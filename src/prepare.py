"""Build 2011-boundary district panels from official SHRUG v2.2 tables.

Usage: python src/prepare.py --raw PATH/TO/EXTRACTED/FILES
The script never joins DMSP and VIIRS values into a single time series.
"""
import argparse
import hashlib
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

KEY = ['pc11_state_id', 'pc11_district_id']


def read_stata(path, columns=None):
    d = pd.read_stata(path, columns=columns, convert_categoricals=False)
    for c in KEY:
        if c in d:
            d[c] = d[c].astype(str).str.zfill(2 if c == KEY[0] else 3)
    return d


def assert_unique(d, keys, label):
    if d.duplicated(keys).any():
        raise ValueError(f'{label}: duplicate keys {keys}')


def sha256_file(path):
    digest=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):
            digest.update(chunk)
    return digest.hexdigest()


def main(raw: Path, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    pca = read_stata(raw/'pc11_pca_clean_pc11dist.dta')
    area = read_stata(raw/'dist_pc11_pop_area_key.dta')
    assert_unique(pca, KEY, '2011 PCA')
    assert_unique(area, KEY, 'area key')
    assert len(pca) == len(area) == 640
    base = pca[KEY + ['pc11_pca_tot_p','pc11_pca_p_06','pc11_pca_p_lit',
                       'pc11_pca_mainwork_p','pc11_pca_main_cl_p','pc11_pca_main_al_p',
                       'pc11_pca_p_sc','pc11_pca_p_st']].merge(
        area[KEY + ['dist_pc11_pca_tot_p','dist_pc11_land_area']], on=KEY,validate='one_to_one')
    assert np.allclose(base.pc11_pca_tot_p,base.dist_pc11_pca_tot_p)
    base = base.rename(columns={'pc11_pca_tot_p':'pop2011','dist_pc11_land_area':'area_km2'})
    base['density2011'] = base.pop2011/base.area_km2
    base['literacy2011'] = base.pc11_pca_p_lit/(base.pop2011-base.pc11_pca_p_06)
    base['agwork2011'] = (base.pc11_pca_main_cl_p+base.pc11_pca_main_al_p)/base.pc11_pca_mainwork_p
    base['scst2011'] = (base.pc11_pca_p_sc+base.pc11_pca_p_st)/base.pop2011
    base = base[KEY+['pop2011','area_km2','density2011','literacy2011','agwork2011','scst2011']]
    for c in ['pop2011','area_km2','density2011']:
        assert base[c].notna().all() and (base[c]>0).all(), c

    v = read_stata(raw/'viirs_annual_pc11dist.dta')
    assert_unique(v,KEY+['year','category'],'VIIRS')
    assert set(v.category)=={'average-masked','median-masked'}
    v=v[(v.year>=2012)&(v.year<=2021)].copy()
    v=v[KEY+['year','category','viirs_annual_sum','viirs_annual_mean','viirs_annual_num_cells']].merge(base,on=KEY,validate='many_to_one')
    v['light_per_1000_baseline_residents']=v.viirs_annual_sum/v.pop2011*1000
    v['log_light_per_1000']=np.log(v.light_per_1000_baseline_residents.where(lambda x:x>0))
    v['asinh_light_per_1000']=np.arcsinh(v.light_per_1000_baseline_residents)
    assert len(v)==640*10*2 and v.viirs_annual_sum.notna().all()
    assert (v[v.year>=2013].viirs_annual_sum>0).all()
    v.to_csv(out/'panel_viirs.csv',index=False,float_format='%.10g')

    d=read_stata(raw/'dmsp_pc11dist.dta')
    assert_unique(d,KEY+['year','dmsp_f_version'],'DMSP')
    d=d[(d.year>=1994)&(d.year<=2013)]
    # Calibrated satellite measurements in multi-satellite years are averaged.
    d=d.groupby(KEY+['year'],as_index=False).agg(
        dmsp_total_light_cal=('dmsp_total_light_cal','mean'),
        n_satellites=('dmsp_f_version','size'))
    d=d.merge(base,on=KEY,validate='many_to_one')
    d['light_per_1000_baseline_residents']=d.dmsp_total_light_cal/d.pop2011*1000
    d['log_light_per_1000']=np.log(d.light_per_1000_baseline_residents.where(lambda x:x>0))
    d.to_csv(out/'panel_dmsp.csv',index=False,float_format='%.10g')
    assert len(d)==640*20

    g=gpd.read_file(raw/'district.gpkg')
    for c in KEY:g[c]=g[c].astype(str).str.zfill(2 if c==KEY[0] else 3)
    extra=g.loc[~g.set_index(KEY).index.isin(base.set_index(KEY).index),KEY+['district_name']]
    g=g[g.set_index(KEY).index.isin(base.set_index(KEY).index)].copy()
    assert len(g)==640 and not g.duplicated(KEY).any()
    assert set(map(tuple,g[KEY].values))==set(map(tuple,base[KEY].values))
    g=g[KEY+['district_name','geometry']]
    g.to_file(out/'districts.gpkg',driver='GPKG',index=False)
    meta={'district_count':640,'viirs_rows':len(v),'dmsp_rows':len(d),
          'viirs_years':[int(v.year.min()),int(v.year.max())],
          'dmsp_years':[int(d.year.min()),int(d.year.max())],
          'polygon_rows_excluded':[
              {c:(None if pd.isna(value) else value) for c,value in row.items()}
              for row in extra.to_dict(orient='records')],
          'population_denominator':'fixed Census 2011 population, not annual population',
          'dmsp_multi_satellite':'arithmetic mean of calibrated total light for satellite-years',
          'source_sha256':{name:sha256_file(raw/name) for name in [
              'viirs_annual_pc11dist.dta','dmsp_pc11dist.dta',
              'pc11_pca_clean_pc11dist.dta','dist_pc11_pop_area_key.dta','district.gpkg']}}
    (out/'preparation_checks.json').write_text(json.dumps(meta,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(meta,indent=2,allow_nan=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--raw',type=Path,required=True)
    parser.add_argument('--out',type=Path,default=Path('data/derived'))
    args=parser.parse_args()
    main(args.raw,args.out)
