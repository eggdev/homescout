"""Extract amenity points inside the county bbox from a Geofabrik .osm.pbf.

Place ny.osm.pbf (or another extract the adapter's bbox covers) in data/enrich/<region>/.
"""
from pipeline.adapters import get_adapter
from pipeline.config import enrich_dir
import os

if __name__ == "__main__":
    _adapter = get_adapter()
    os.chdir(enrich_dir(_adapter.key, create=True))

    # Extract amenity points in Westchester bbox from Geofabrik NY extract
    import osmium, pandas as pd, re
    W,S,E,N=_adapter.bbox()
    def cat(t):
        sh=t.get('shop',''); am=t.get('amenity',''); le=t.get('leisure','')
        if sh in('supermarket','grocery','greengrocer','convenience','bakery','butcher','deli'): return 'grocery'
        if am in('restaurant','cafe','fast_food','bar','pub'): return 'dining'
        if am in('pharmacy','library','bank','post_office') or sh: return 'errands'
        if am in('school','kindergarten'): return 'school'
        if le in('park','playground','nature_reserve'): return 'park'
        if t.get('railway') in ('station','halt') and t.get('station')!='subway': return 'rail_station'
        if t.get('highway')=='bus_stop' or (t.get('public_transport')=='platform' and t.get('bus')=='yes'): return 'bus_stop'
        return None
    rows=[]
    class H(osmium.SimpleHandler):
        def node(self,n):
            if n.tags and n.location.valid() and W<n.location.lon<E and S<n.location.lat<N:
                c=cat(dict(n.tags))
                if c: rows.append((c,n.location.lat,n.location.lon,n.tags.get('name',''),n.tags.get('operator',''),n.tags.get('network','')))
        def area(self,a):
            t=dict(a.tags); c=cat(t)
            if not c: return
            try:
                lats=[];lons=[]
                for ring in a.outer_rings():
                    for nd in ring: lats.append(nd.lat); lons.append(nd.lon)
                la=sum(lats)/len(lats); lo=sum(lons)/len(lons)
                if W<lo<E and S<la<N: rows.append((c,la,lo,t.get('name',''),t.get('operator',''),t.get('network','')))
            except Exception: pass
    H().apply_file("ny.osm.pbf",locations=True)
    d=pd.DataFrame(rows,columns=['cat','lat','lon','name','operator','network']); d.to_csv('osm_pois.csv',index=False); print(d.cat.value_counts())
    print(d[d.cat=='rail_station'][['name','operator','network']].to_string())
