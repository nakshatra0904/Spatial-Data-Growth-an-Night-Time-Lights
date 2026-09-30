"""Reproducible descriptive and spatial analysis of SHRUG district lights."""
import json
from pathlib import Path
import warnings

import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from esda.moran import Moran, Moran_Local
from libpysal.weights import KNN, Queen
from scipy import stats
from scipy.sparse.csgraph import connected_components
import spreg
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/derived'
TABLES=ROOT/'results/tables'
FIG=ROOT/'results/figures'
for p in (TABLES,FIG):p.mkdir(parents=True,exist_ok=True)
KEY=['pc11_state_id','pc11_district_id']
SEED=20261001
np.random.seed(SEED)


def load():
    v=pd.read_csv(DATA/'panel_viirs.csv',dtype={KEY[0]:str,KEY[1]:str})
    d=pd.read_csv(DATA/'panel_dmsp.csv',dtype={KEY[0]:str,KEY[1]:str})
    g=gpd.read_file(DATA/'districts.gpkg')
    for x in (v,d,g):
        x[KEY[0]]=x[KEY[0]].str.zfill(2)
        x[KEY[1]]=x[KEY[1]].str.zfill(3)
    g=g.sort_values(KEY).reset_index(drop=True)
    assert len(g)==640 and not g.duplicated(KEY).any()
    return v,d,g


def make_cross_section(panel, start, end, category=None):
    z=panel.copy()
    if category is not None:z=z[z.category==category]
    a=z[z.year==start].copy()
    b=z[z.year==end][KEY+['log_light_per_1000','light_per_1000_baseline_residents']].copy()
    x=a.merge(b,on=KEY,validate='one_to_one',suffixes=('_initial','_final'))
    x['growth_annual']=(x.log_light_per_1000_final-x.log_light_per_1000_initial)/(end-start)
    x['log_initial']=x.log_light_per_1000_initial
    x['log_density']=np.log(x.density2011)
    x=x.sort_values(KEY).reset_index(drop=True)
    return x


def make_smoothed_viirs(v):
    z=v[(v.category=='average-masked')&(v.year.isin([2013,2014,2020,2021]))]
    avg=z.groupby(KEY+['year'],as_index=False).first()
    a=avg[avg.year.isin([2013,2014])].groupby(KEY).light_per_1000_baseline_residents.mean()
    b=avg[avg.year.isin([2020,2021])].groupby(KEY).light_per_1000_baseline_residents.mean()
    x=make_cross_section(v,2013,2021,'average-masked')
    xa=np.log(a.loc[pd.MultiIndex.from_frame(x[KEY])].to_numpy())
    xb=np.log(b.loc[pd.MultiIndex.from_frame(x[KEY])].to_numpy())
    x['log_initial']=xa
    x['growth_annual']=(xb-xa)/7.0
    return x


def queen_weights(g):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        w=Queen.from_dataframe(g,use_index=False)
    w.transform='r'
    return w


def knn_weights(g,k=8):
    pts=g.to_crs(6933).representative_point()
    w=KNN.from_array(np.column_stack([pts.x,pts.y]),k=k)
    w.transform='r'
    return w


def matrix(x,controls=True,state_fe=True):
    cols=['log_initial']
    if controls:cols+=['log_density','literacy2011','agwork2011','scst2011']
    X=x[cols].astype(float).copy()
    if state_fe:
        st=pd.get_dummies(x.pc11_state_id,prefix='state',drop_first=True,dtype=float)
        X=pd.concat([X,st],axis=1)
    assert np.isfinite(X.to_numpy()).all()
    return X


def fit_ols(x,controls=True,state_fe=True):
    X=matrix(x,controls,state_fe)
    m=sm.OLS(x.growth_annual.to_numpy(),sm.add_constant(X)).fit(cov_type='HC3')
    return m,X


def model_row(label,model,names):
    bet=np.asarray(model.betas).flatten()
    se=np.asarray(model.std_err).flatten()
    z=np.asarray(model.z_stat)
    return [{'model':label,'term':str(n),'estimate':float(b),'se':float(s),'p':float(zz[1])}
            for n,b,s,zz in zip(names,bet,se,z)]


def spatial_models(x,w,suffix):
    X=matrix(x,True,True)
    y=x.growth_annual.to_numpy().reshape(-1,1)
    names=list(X.columns)
    opts=dict(y=y,x=X.to_numpy(),w=w,name_y='Annual log-light growth',name_x=names,method='ord')
    sar=spreg.ML_Lag(**opts,spat_diag=False,spat_impacts=None)
    sem=spreg.ML_Error(**opts)
    # SLX terms for all five continuous regressors, while state indicators stay local.
    sdm=spreg.ML_Lag(**opts,slx_lags=1,slx_vars=[True]*5+[False]*(X.shape[1]-5),
                     spat_diag=False,spat_impacts=None,vm=True)
    rows=[]
    for name,m in [('SAR',sar),('SEM',sem),('SDM',sdm)]:
        rows.extend(model_row(name+suffix,m,m.name_x))
    return sar,sem,sdm,pd.DataFrame(rows)


def sdm_impacts(model,w,terms):
    # Exact impacts include zero-neighbor districts. For them W has a zero row,
    # so the familiar (beta+theta)/(1-rho) shortcut is not exact.
    rho=float(model.rho)
    names=list(model.name_x)
    vals=np.asarray(model.betas).flatten()
    W=w.sparse.toarray()
    n=W.shape[0]
    inv=np.linalg.solve(np.eye(n)-rho*W,np.eye(n))
    tr_inv=float(np.trace(inv)/n)
    tr_inv_w=float(np.trace(inv@W)/n)
    mean_inv_one=float(np.mean(inv@np.ones(n)))
    mean_inv_w_one=float(np.mean(inv@W@np.ones(n)))
    # Parametric 95% intervals from the full ML covariance matrix, including rho.
    # Eigenvalues give the same traces for each draw without inverting W 5,000 times.
    eig=np.linalg.eigvals(W)
    draws=np.random.default_rng(SEED).multivariate_normal(vals,np.asarray(model.vm),size=5000)
    draws=draws[np.abs(draws[:,-1])<.99]
    rd=draws[:,-1]
    td=np.real(np.mean(1/(1-rd[:,None]*eig[None,:]),axis=1))
    tw=np.real(np.mean(eig[None,:]/(1-rd[:,None]*eig[None,:]),axis=1))
    # Geometric series for average row sums, accurate to machine precision for
    # the estimated rho and its simulated interval (all draws below |rho|=.99).
    row_powers=[]
    q=np.ones(n)
    for _ in range(1000):
        row_powers.append(q.mean())
        q=w.sparse@q
    row_powers.append(q.mean())
    powers=rd[:,None]**np.arange(1000)[None,:]
    mean_total_0=powers@np.asarray(row_powers[:-1])
    mean_total_1=powers@np.asarray(row_powers[1:])
    out=[]
    for term in terms:
        b=float(vals[names.index(term)])
        theta=float(vals[names.index('W_'+term)])
        direct=tr_inv*b+tr_inv_w*theta
        total=mean_inv_one*b+mean_inv_w_one*theta
        bd=draws[:,names.index(term)]
        thd=draws[:,names.index('W_'+term)]
        dd=td*bd+tw*thd
        tt=mean_total_0*bd+mean_total_1*thd
        ii=tt-dd
        out.append({'term':term,'direct':direct,'direct_ci_low':np.quantile(dd,.025),
                    'direct_ci_high':np.quantile(dd,.975),
                    'indirect':total-direct,'indirect_ci_low':np.quantile(ii,.025),
                    'indirect_ci_high':np.quantile(ii,.975),
                    'total':total,'total_ci_low':np.quantile(tt,.025),
                    'total_ci_high':np.quantile(tt,.975),'beta':b,'theta':theta})
    return pd.DataFrame(out)


def moran_result(y,w,permutations=999):
    m=Moran(np.asarray(y),w,permutations=permutations)
    p_two=(1+int(np.sum(np.abs(m.sim-m.EI)>=abs(m.I-m.EI))))/(permutations+1)
    return {'I':float(m.I),'expected_I':float(m.EI),'p_permutation_two_sided':float(p_two),
            'p_permutation_upper':float(m.p_sim),'z_normal':float(m.z_norm)}


def diagnostics(x,w,ols):
    return {'growth':moran_result(x.growth_annual,w),
            'initial':moran_result(x.log_initial,w),
            'ols_residual':moran_result(ols.resid,w)}


def descriptives(v,x,w):
    p=v[v.category=='average-masked'].copy()
    annual=p.groupby('year').agg(median_light_per_1000=('light_per_1000_baseline_residents','median'),
        mean_light_per_1000=('light_per_1000_baseline_residents','mean'),
        total_light=('viirs_annual_sum','sum'),n=('pc11_district_id','size')).reset_index()
    annual.to_csv(TABLES/'annual_viirs.csv',index=False)
    cols=['light_per_1000_baseline_residents_initial','light_per_1000_baseline_residents_final',
          'growth_annual','log_initial','density2011','literacy2011','agwork2011','scst2011']
    desc=x[cols].agg(['count','mean','std','min','median','max']).T
    desc['p10']=x[cols].quantile(.1)
    desc['p90']=x[cols].quantile(.9)
    desc.to_csv(TABLES/'descriptive_statistics.csv')
    corr=x[['growth_annual','log_initial','log_density','literacy2011','agwork2011','scst2011']].corr()
    corr.to_csv(TABLES/'correlations.csv')
    x['growth_quintile']=pd.qcut(x.growth_annual,5,labels=False)+1
    x[KEY+['growth_annual','log_initial','growth_quintile']].to_csv(TABLES/'district_growth.csv',index=False)
    return annual,desc,corr


def lisa(x,w):
    m=Moran_Local(x.growth_annual.to_numpy(),w,permutations=999,seed=SEED,n_jobs=1)
    eligible=np.ones(len(x),dtype=bool)
    eligible[w.islands]=False
    sig=np.zeros(len(x),dtype=bool)
    sig[eligible]=multipletests(m.p_sim[eligible],alpha=.05,method='fdr_bh')[0]
    labels=np.array(['not significant']*len(x),dtype=object)
    classes={1:'high-high',2:'low-high',3:'low-low',4:'high-low'}
    for code,label in classes.items():labels[(m.q==code)&sig]=label
    labels[~eligible]='no contiguous neighbor'
    z=x[KEY+['growth_annual']].copy()
    z['local_I']=m.Is
    z['p_unadjusted']=np.where(eligible,m.p_sim,np.nan)
    z['significant_fdr05']=sig
    z['cluster']=labels
    z.to_csv(TABLES/'lisa_growth.csv',index=False)
    return z


def spatial_clusters(x,g,w8):
    # Ward clustering can merge districts only along the symmetric 8-NN graph.
    # These are descriptive regions, not estimated spillovers or causal groups.
    vars_=['log_initial','growth_annual','log_density','literacy2011','agwork2011']
    Z=StandardScaler().fit_transform(x[vars_])
    conn=w8.sparse.maximum(w8.sparse.T).tocsr()
    scores=[]
    fits={}
    for k in range(2,7):
        lab=AgglomerativeClustering(n_clusters=k,connectivity=conn,linkage='ward').fit_predict(Z)
        scores.append({'k':k,'silhouette':float(silhouette_score(Z,lab)),
                       'smallest_cluster':int(np.bincount(lab).min())})
        fits[k]=lab
    best=max(scores,key=lambda t:t['silhouette'])['k']
    labels=fits[best]
    z=x[KEY+vars_+['density2011']].copy()
    z['cluster']=labels+1
    z.to_csv(TABLES/'spatial_regions.csv',index=False)
    profile=z.groupby('cluster').agg(n=('growth_annual','size'),
        median_annual_growth=('growth_annual','median'),mean_annual_growth=('growth_annual','mean'),
        mean_initial_log_light=('log_initial','mean'),
        median_density=('density2011','median'),mean_literacy=('literacy2011','mean'),
        mean_agwork=('agwork2011','mean')).reset_index()
    profile.to_csv(TABLES/'spatial_region_profiles.csv',index=False)
    components={int(c):int(connected_components(conn[labels==c-1,:][:,labels==c-1],directed=False)[0])
                for c in range(1,best+1)}
    result={'selected_k':int(best),'candidate_scores':scores,'connected_components_by_cluster':components,
            'features':vars_,'graph':'symmetric 8-nearest centroid neighbors in EPSG:6933'}
    (TABLES/'spatial_cluster_assessment.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return z,result


def figures(v,x,g,annual,lisa_df,ols,ols_u,cluster_df):
    plt.rcParams.update({'font.size':9,'figure.dpi':160,'savefig.dpi':200})
    fig,ax=plt.subplots(figsize=(8,4.5))
    ax.plot(annual.year,annual.median_light_per_1000,marker='o',label='Median district')
    ax.plot(annual.year,annual.mean_light_per_1000,marker='s',label='Mean district')
    ax.set(xlabel='Year',ylabel='VIIRS sum per 1,000 2011 residents',title='Annual VIIRS lights, 2012–2021')
    ax.legend();fig.tight_layout();fig.savefig(FIG/'viirs_trend.png');plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(9,3.7))
    axs[0].hist(x.growth_annual*100,bins=35,color='#276b82',edgecolor='white')
    axs[0].axvline(x.growth_annual.median()*100,color='#a83232',label='Median')
    axs[0].set(xlabel='Annual log growth × 100',ylabel='Districts',title='Growth distribution')
    axs[1].scatter(x.log_initial,x.growth_annual*100,s=9,alpha=.45,color='#276b82')
    xx=np.linspace(x.log_initial.min(),x.log_initial.max(),100)
    xpred=sm.add_constant(pd.DataFrame({'log_initial':xx}),has_constant='add')
    pred=ols_u.get_prediction(xpred)
    ci=pred.conf_int(alpha=.05)
    axs[1].fill_between(xx,ci[:,0]*100,ci[:,1]*100,color='#a83232',alpha=.16,
                        label='95% CI for fitted mean')
    axs[1].plot(xx,pred.predicted_mean*100,color='#a83232',lw=2,label='OLS fitted line')
    equation=(f'g = {ols_u.params["const"]:.4f} '
              f'{ols_u.params["log_initial"]:+.5f} log L0\n'
              f'R² = {ols_u.rsquared:.3f}')
    axs[1].text(.03,.96,equation,transform=axs[1].transAxes,va='top',fontsize=8,
                bbox={'facecolor':'white','alpha':.9,'edgecolor':'none'})
    axs[1].legend(loc='lower left',fontsize=7,frameon=False)
    axs[1].set(xlabel='Log initial VIIRS per 1,000 2011 residents',ylabel='Annual log growth × 100',title='Unconditional OLS regression')
    fig.tight_layout();fig.savefig(FIG/'distribution_convergence.png');plt.close(fig)
    mapped=g.merge(x[KEY+['growth_annual','log_initial']],on=KEY,validate='one_to_one')
    mapped=mapped.merge(lisa_df[KEY+['cluster']],on=KEY,validate='one_to_one')
    fig,axs=plt.subplots(1,2,figsize=(13,6.8))
    mapped.plot(column='growth_annual',cmap='RdYlBu',legend=True,ax=axs[0],
                legend_kwds={'shrink':.55,'label':'Annual log growth'},edgecolor='none')
    axs[0].set_title('VIIRS growth, 2013–2021')
    colors={'high-high':'#ae3434','low-low':'#3269a8','high-low':'#e7a452',
            'low-high':'#81a8c9','not significant':'#dddddd',
            'no contiguous neighbor':'#333333'}
    for label,color in colors.items():
        mapped[mapped.cluster==label].plot(ax=axs[1],color=color,edgecolor='none',label=label)
    axs[1].set_title('Local Moran clusters (BH FDR 5%)')
    for ax in axs:ax.set_axis_off()
    axs[1].legend(loc='lower left',fontsize=7,frameon=False)
    fig.tight_layout(rect=[0,0,1,.91]);fig.savefig(FIG/'growth_maps.png');plt.close(fig)
    regions=g.merge(cluster_df[KEY+['cluster']],on=KEY,validate='one_to_one')
    fig,ax=plt.subplots(figsize=(7.4,6.8))
    regions.plot(column='cluster',categorical=True,cmap='Set2',legend=True,ax=ax,edgecolor='none',
                 legend_kwds={'title':'Region'})
    ax.set_title('Spatially constrained district typology')
    ax.set_axis_off();fig.tight_layout();fig.savefig(FIG/'spatial_regions.png');plt.close(fig)
    fig,ax=plt.subplots(figsize=(7,4))
    ax.scatter(ols.fittedvalues,ols.resid*100,s=9,alpha=.4)
    ax.axhline(0,color='black',lw=.8)
    ax.set(xlabel='Fitted annual log growth',ylabel='OLS residual × 100',title='Conditional OLS residuals')
    fig.tight_layout();fig.savefig(FIG/'ols_residuals.png');plt.close(fig)


def main():
    v,d,g=load()
    x=make_cross_section(v,2013,2021,'average-masked')
    assert len(x)==640 and set(map(tuple,x[KEY].values))==set(map(tuple,g[KEY].values))
    w=queen_weights(g)
    w8=knn_weights(g,8)
    weights={'queen_islands':len(w.islands),'queen_components':int(w.n_components),
             'queen_mean_neighbors':float(w.mean_neighbors),
             'knn8_components':int(w8.n_components)}
    annual,desc,corr=descriptives(v,x,w)
    lisa_df=lisa(x,w)
    clusters,cluster_assessment=spatial_clusters(x,g,w8)
    ols_u,Xu=fit_ols(x,False,False)
    ols_c,Xc=fit_ols(x,True,True)
    ols_rows=[]
    for label,m in [('OLS_unconditional',ols_u),('OLS_conditional_state_FE',ols_c)]:
        for n,b,s,p in zip(m.params.index,m.params,m.bse,m.pvalues):
            ols_rows.append({'model':label,'term':n,'estimate':b,'se':s,'p':p})
    pd.DataFrame(ols_rows).to_csv(TABLES/'ols_coefficients.csv',index=False)
    sar,sem,sdm,sp_rows=spatial_models(x,w,'_queen')
    sp_rows.to_csv(TABLES/'spatial_coefficients.csv',index=False)
    impacts=sdm_impacts(sdm,w,['log_initial','log_density','literacy2011','agwork2011','scst2011'])
    impacts.to_csv(TABLES/'sdm_impacts.csv',index=False)
    diag=diagnostics(x,w,ols_c)
    diag['sar_residual']=moran_result(np.asarray(sar.u).flatten(),w)
    diag['sdm_residual']=moran_result(np.asarray(sdm.u).flatten(),w)
    diag['sem_filtered_residual']=moran_result(np.asarray(sem.e_filtered).flatten(),w)
    figures(v,x,g,annual,lisa_df,ols_c,ols_u,clusters)

    robustness=[]
    keep=np.ones(len(g),dtype=bool)
    keep[w.islands]=False
    x_nonisland=x.loc[keep].reset_index(drop=True)
    w_nonisland=queen_weights(g.loc[keep].reset_index(drop=True))
    for label,z,weights_obj in [
        ('VIIRS_median_2013_2021',make_cross_section(v,2013,2021,'median-masked'),w),
        ('VIIRS_average_2014_2019',make_cross_section(v,2014,2019,'average-masked'),w),
        ('VIIRS_average_2013_2021_knn8',x,w8),
        ('VIIRS_average_smoothed_two_year_endpoints',make_smoothed_viirs(v),w),
        ('VIIRS_average_queen_nonislands',x_nonisland,w_nonisland),
        ('DMSP_calibrated_2000_2013',make_cross_section(d,2000,2013),w)]:
        m,_=fit_ols(z,True,True)
        row={'specification':label,'n':int(m.nobs),'ols_initial_beta':float(m.params['log_initial']),
             'ols_initial_se_HC3':float(m.bse['log_initial']),
             'ols_initial_p':float(m.pvalues['log_initial']),
             'ols_R2':float(m.rsquared),
             'growth_moran_I':moran_result(z.growth_annual,weights_obj)['I']}
        sar_r=spreg.ML_Lag(z.growth_annual.to_numpy().reshape(-1,1),
            matrix(z,True,True).to_numpy(),weights_obj,method='ord',spat_diag=False,spat_impacts=None)
        row['sar_rho']=float(sar_r.rho)
        row['sar_initial_beta']=float(np.asarray(sar_r.betas).flatten()[1])
        robustness.append(row)
    lo,hi=x.growth_annual.quantile([.01,.99])
    xt=x[(x.growth_annual>=lo)&(x.growth_annual<=hi)].copy()
    mt,_=fit_ols(xt,True,True)
    robustness.append({'specification':'VIIRS_average_trim_growth_1pct_each_tail',
        'n':int(mt.nobs),'ols_initial_beta':float(mt.params['log_initial']),
        'ols_initial_se_HC3':float(mt.bse['log_initial']),
        'ols_initial_p':float(mt.pvalues['log_initial']),
        'ols_R2':float(mt.rsquared)})
    pd.DataFrame(robustness).to_csv(TABLES/'robustness.csv',index=False)
    basic={'n_districts':len(x),'period':[2013,2021],'interval_years':8,
           'mean_annual_log_growth':float(x.growth_annual.mean()),
           'median_annual_log_growth':float(x.growth_annual.median()),
           'share_negative_growth':float((x.growth_annual<0).mean()),
           'ols_unconditional_beta':float(ols_u.params['log_initial']),
           'ols_unconditional_intercept':float(ols_u.params['const']),
           'ols_unconditional_R2':float(ols_u.rsquared),
           'ols_unconditional_p':float(ols_u.pvalues['log_initial']),
           'ols_conditional_beta':float(ols_c.params['log_initial']),
           'ols_conditional_se':float(ols_c.bse['log_initial']),
           'ols_conditional_p':float(ols_c.pvalues['log_initial']),
           'ols_conditional_R2':float(ols_c.rsquared),
           'sar_rho':float(sar.rho),'sem_lambda':float(sem.lam),'sdm_rho':float(sdm.rho),
           'sar_aic':float(sar.aic),'sem_aic':float(sem.aic),'sdm_aic':float(sdm.aic),
           'sdm_vs_sar_LR':float(2*(sdm.logll-sar.logll)),
           'sdm_vs_sar_LR_p_chi2_df5':float(stats.chi2.sf(2*(sdm.logll-sar.logll),5)),
           'ols_aic':float(ols_c.aic),'weights':weights,'moran':diag,
           'lisa_clusters':lisa_df.cluster.value_counts().to_dict()}
    basic['spatial_typology']=cluster_assessment
    (TABLES/'headline_results.json').write_text(json.dumps(basic,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(basic,indent=2))


if __name__=='__main__':main()
