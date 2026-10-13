"""Nearest drivable road point per parcel, for a Street View camera position.

Reads centroids.csv and the regional .osm.pbf in data/enrich/<region>/.
Writes streetview_cam.csv. The app build picks that file up when it is present.
"""
from pipeline.adapters import get_adapter
from pipeline.config import enrich_dir
import os

if __name__ == "__main__":
    _adapter = get_adapter()
    os.chdir(enrich_dir(_adapter.key, create=True))

    # Nearest drivable road point per parcel -> Street View camera position + heading toward house
    import osmium, numpy as np, pandas as pd
    from scipy.spatial import cKDTree
    from pyproj import Transformer
    W,S,E,N=_adapter.bbox()
    OK={'residential','unclassified','tertiary','secondary','primary','living_street','service','tertiary_link','secondary_link','road','trunk'}
    pts=[]
    class H(osmium.SimpleHandler):
        def way(self,w):
            h=w.tags.get('highway')
            if h not in OK or (h=='service' and w.tags.get('service') in ('parking_aisle','driveway')): return
            try: c=[(n.lon,n.lat) for n in w.nodes]
            except Exception: return
            if not any(W<x<E and S<y<N for x,y in c): return
            for (x1,y1),(x2,y2) in zip(c,c[1:]):
                k=max(1,int(((x2-x1)**2+(y2-y1)**2)**.5/0.0001))  # ~10 m spacing
                for t in np.linspace(0,1,k+1)[:-1]: pts.append((x1+(x2-x1)*t,y1+(y2-y1)*t))
    H().apply_file('ny.osm.pbf',locations=True)
    R=np.array(pts); T=Transformer.from_crs(4326,_adapter.metric_crs(),always_xy=True)
    rx,ry=T.transform(R[:,0],R[:,1]); tree=cKDTree(np.c_[rx,ry])
    c=pd.read_csv('centroids.csv',dtype=str); lat=c.lat.astype(float).values; lon=c.lon.astype(float).values
    px,py=T.transform(lon,lat); d,i=tree.query(np.c_[px,py])
    c['sv_lat']=R[i,1].round(6); c['sv_lon']=R[i,0].round(6); c['road_dist_m']=d.round(0)
    c['sv_heading']=((np.degrees(np.arctan2(px-rx[i],py-ry[i])))%360).round(0)  # bearing road->house (UTM approx)
    c[['SWIS','PRINT_KEY','sv_lat','sv_lon','sv_heading','road_dist_m']].to_csv('streetview_cam.csv',index=False); print(len(R),c.road_dist_m.describe())
