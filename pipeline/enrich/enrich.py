"""School district, walk proxy, flood, NRI, terrain, and terrain-sun enrichment.

Run from any directory. Inputs and outputs live in data/enrich/<region>/.
The numeric recipe is the prototype enrich.py; county CRS, tiles, and filenames come from the adapter.
"""
from pipeline.adapters import get_adapter
from pipeline.config import enrich_dir
import os

if __name__ == "__main__":
    _adapter = get_adapter()
    os.chdir(enrich_dir(_adapter.key, create=True))

    # Enrich all class-210 parcels with school district, walk proxy, flood/NRI, terrain, solar proxy, price estimate
    import pandas as pd, numpy as np, geopandas as gpd, json, rasterio, pvlib
    from scipy.spatial import cKDTree
    from scipy.ndimage import map_coordinates
    from pyproj import Transformer
    c=pd.read_csv('centroids.csv',dtype={'SWIS':str,'PRINT_KEY':str}).dropna().drop_duplicates(['SWIS','PRINT_KEY'])
    pts=gpd.GeoDataFrame(c,geometry=gpd.points_from_xy(c.lon,c.lat),crs=4326)
    # 1 school district (Census TIGER 2024 unified)
    sd=gpd.read_file('zip://'+_adapter.tiger_unsd_filename())[['NAME','GEOID','geometry']].to_crs(4326).rename(columns={'NAME':'school_district_tiger','GEOID':'school_district_geoid'})
    pts=gpd.sjoin(pts,sd,how='left',predicate='within').drop(columns='index_right').drop_duplicates(['SWIS','PRINT_KEY'])
    # 3a NRI by tract
    tr=gpd.read_file('zip://'+_adapter.tiger_tract_filename())[['GEOID','geometry']].to_crs(4326).rename(columns={'GEOID':'tract_geoid'})
    pts=gpd.sjoin(pts,tr,how='left',predicate='within').drop(columns='index_right').drop_duplicates(['SWIS','PRINT_KEY'])
    nri=pd.DataFrame([f['attributes'] for f in json.load(open('nri.json'))['features']])
    keep={'RISK_SCORE':'nri_overall_score','RISK_RATNG':'nri_overall_rating','SOVI_RATNG':'nri_social_vuln_rating','RESL_RATNG':'nri_community_resilience_rating'}
    for h,n in [('IFLD','inland_flood'),('CFLD','coastal_flood'),('HRCN','hurricane'),('WNTW','winter_weather'),('ISTM','ice_storm'),('SWND','strong_wind'),('HWAV','heat_wave'),('CWAV','cold_wave'),('LNDS','landslide'),('TRND','tornado')]:
        keep[h+'_RISKS']=f'nri_{n}_score'; keep[h+'_RISKR']=f'nri_{n}_rating'
    nri=nri[['TRACTFIPS']+list(keep)].rename(columns=keep).rename(columns={'TRACTFIPS':'tract_geoid'})
    pts=pts.merge(nri,on='tract_geoid',how='left')
    # 3b FEMA NFHL flood zone
    fz=gpd.read_file('nfhl.geojson')[['FLD_ZONE','ZONE_SUBTY','SFHA_TF','STATIC_BFE','geometry']]
    fz['rank']=fz.SFHA_TF.eq('T').astype(int)*2+fz.ZONE_SUBTY.fillna('').str.contains('0.2').astype(int)
    j=gpd.sjoin(pts[['SWIS','PRINT_KEY','geometry']],fz,how='left',predicate='within').sort_values('rank',ascending=False).drop_duplicates(['SWIS','PRINT_KEY'])
    j['fema_flood_zone']=j.FLD_ZONE.fillna('X (minimal) / outside mapped hazard')
    j.loc[j.ZONE_SUBTY.fillna('').str.contains('0.2'),'fema_flood_zone']='X shaded (0.2% / 500-yr)'
    j['fema_sfha_100yr']=j.SFHA_TF.eq('T')
    j['fema_bfe_ft']=pd.to_numeric(j.STATIC_BFE,errors='coerce').where(lambda x:x>-9000)
    pts=pts.merge(j[['SWIS','PRINT_KEY','fema_flood_zone','fema_sfha_100yr','fema_bfe_ft']],on=['SWIS','PRINT_KEY'],how='left')
    # 2 walk proxy (OSM)
    T=Transformer.from_crs(4326,_adapter.metric_crs(),always_xy=True)
    px,py=T.transform(pts.lon.values,pts.lat.values); P=np.c_[px,py]
    poi=pd.read_csv('osm_pois.csv'); qx,qy=T.transform(poi.lon.values,poi.lat.values); poi['x']=qx; poi['y']=qy
    decay=lambda d:np.clip((1600-d)/1200,0,1)  # full credit <=400 m, zero at 1.6 km (~20 min walk)
    spec={'grocery':(3,[1]),'dining':(3,[.75,.45,.25,.25,.225,.225,.225,.225,.2,.2]),'errands':(2,[.5,.45,.4,.35,.3]),'school':(1,[1]),'park':(1,[1]),'transit':(2,[.5,.3,.2])}
    total=np.zeros(len(P)); wsum=0
    poi.loc[poi.cat.isin(['bus_stop','rail_station']),'cat2']='transit'; poi['cat2']=poi.cat2.fillna(poi.cat)
    for k,(w,ws) in spec.items():
        s=poi[poi.cat2==k]; d,_=cKDTree(s[['x','y']].values).query(P,k=len(ws)); d=d.reshape(len(P),-1)
        total+=w*(decay(d)*np.array(ws)).sum(1)/sum(ws); wsum+=w
        pts[f'n_{k}_within_800m']=cKDTree(s[['x','y']].values).query_ball_point(P,800,return_length=True)
    pts['walk_proxy_0_100']=(100*total/wsum).round(0)
    mn=poi[(poi.cat=='rail_station')&(poi.network.fillna('').str.contains('Metro-North'))&~poi.network.fillna('').str.contains('NJ Transit')]
    d,i=cKDTree(mn[['x','y']].values).query(P); pts['metro_north_station']=mn.name.values[i]; pts['metro_north_dist_mi']=(d/1609.34).round(2)
    # 4 terrain from USGS 3DEP 1/3"
    src=rasterio.open('dem.tif'); Z=src.read(1).astype('float32'); Z[Z<-1000]=np.nan
    tr_=src.transform; rows,cols=rasterio.transform.rowcol(tr_,pts.lon.values,pts.lat.values); rows=np.array(rows,float); cols=np.array(cols,float)
    lat0=_adapter.solar_site()[0]; dy=abs(tr_.e)*111320; dx=tr_.a*111320*np.cos(np.radians(lat0))
    gy,gx=np.gradient(Z); dzdx=gx/dx; dzdn=-gy/dy  # north-positive
    slope=np.degrees(np.arctan(np.hypot(dzdx,dzdn))); aspect=(np.degrees(np.arctan2(-dzdx,-dzdn))+360)%360  # downslope direction, 0=N
    samp=lambda A:map_coordinates(A,[rows,cols],order=1,mode='nearest')
    pts['elevation_ft']=(samp(Z)*3.28084).round(0)
    # smooth slope/aspect over ~30 m (3x3 mean of gradient) for stability
    from scipy.ndimage import uniform_filter
    sx=uniform_filter(np.nan_to_num(dzdx),5); sn=uniform_filter(np.nan_to_num(dzdn),5)
    s_=samp(sx); n_=samp(sn)
    pts['slope_deg']=np.degrees(np.arctan(np.hypot(s_,n_))).round(1)
    asp=(np.degrees(np.arctan2(-s_,-n_))+360)%360; pts['aspect_deg']=np.where(pts.slope_deg<2,np.nan,asp.round(0))
    pts['aspect_dir']=np.where(pts.slope_deg<2,'flat',np.array(['N','NE','E','SE','S','SW','W','NW'])[((asp+22.5)//45).astype(int)%8])
    # 5 solar: horizon angles (16 azimuths, rays to 3 km) + clear-sky hourly sun path
    AZ=np.arange(0,360,22.5); H=np.zeros((len(P),len(AZ)),'float32'); z0=samp(np.nan_to_num(Z,nan=0))
    for a_i,az in enumerate(AZ):
        best=np.zeros(len(P),'float32')
        for dist in np.r_[np.arange(20,500,20),np.arange(500,3001,75)]:
            rr=rows-dist*np.cos(np.radians(az))/dy; cc=cols+dist*np.sin(np.radians(az))/dx
            z=map_coordinates(np.nan_to_num(Z,nan=0),[rr,cc],order=1,mode='nearest')
            best=np.maximum(best,np.degrees(np.arctan((z-z0-2)/dist)))  # 2 m observer height
        H[:,a_i]=best
    pts['horizon_max_deg']=H.max(1).round(1); pts['horizon_south_deg']=H[:,[6,7,8,9,10]].mean(1).round(1)
    times=pd.date_range('2026-01-01',periods=365*24,freq='h',tz='America/New_York'); times=times[(times.dayofyear%4)==0]
    _lat,_lon,_alt=_adapter.solar_site(); loc=pvlib.location.Location(_lat,_lon,altitude=_alt); sp=loc.get_solarposition(times); cs=loc.get_clearsky(times,model='simplified_solis')
    up=sp.apparent_elevation>0; sp=sp[up]; cs=cs[up]
    zen=np.radians(sp.apparent_zenith.values); saz=sp.azimuth.values; sel=sp.apparent_elevation.values; dni=cs.dni.values; dhi=cs.dhi.values
    flat=(dni*np.cos(zen)+dhi).sum()
    sl=np.radians(np.nan_to_num(pts.slope_deg.values)); asr=np.radians(np.nan_to_num(asp))
    svf=np.clip(1-np.sin(np.radians(np.clip(H,0,90))).mean(1),0,1)
    out=np.zeros(len(P))
    for i0 in range(0,len(P),5000):
        s=slice(i0,i0+5000)
        cosi=np.cos(zen)[None]*np.cos(sl[s])[:,None]+np.sin(zen)[None]*np.sin(sl[s])[:,None]*np.cos(np.radians(saz)[None]-asr[s][:,None])
        hidx=np.interp(saz,np.r_[AZ,360],np.r_[AZ,360]) ; hz=np.stack([np.interp(saz,np.r_[AZ,360],np.r_[H[k],H[k][0]]) for k in range(*s.indices(len(P)))])
        vis=sel[None]>hz
        beam=(dni[None]*np.clip(cosi,0,None)*vis).sum(1); diff=dhi.sum()*svf[s]*(1+np.cos(sl[s]))/2
        out[s]=(beam+diff)/flat
    pts['solar_terrain_index']=(out*100).round(0)  # 100 = flat, unobstructed site
    pts['sky_view_factor']=svf.round(2)
    pts.drop(columns=['geometry']).to_csv('enrich_fields.csv',index=False); print(len(pts)); print(pts.describe().T[['count','mean','min','max']].to_string())
