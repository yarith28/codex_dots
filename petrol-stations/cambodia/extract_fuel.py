#!/usr/bin/env python3
"""Extract amenity=fuel POIs from the pinned public Cambodia OSM PBF."""
from __future__ import annotations
import argparse, collections, csv, hashlib, importlib.metadata, json, math, pathlib, platform, sys
import osmium
from shapely import wkb
from shapely.geometry import Point, LineString, Polygon, mapping

SOURCE_URL='https://download.geofabrik.de/asia/cambodia-260930.osm.pbf'
SOURCE_PAGE='https://download.geofabrik.de/asia/cambodia.html'
LICENSE_URL='https://opendatacommons.org/licenses/odbl/1-0/'
BASE=pathlib.Path(__file__).resolve().parent
PBF=BASE/'source/cambodia-260930.osm.pbf'
ADDRESS_KEYS=['full','housename','housenumber','street','place','hamlet','village','suburb','quarter','city_district','district','city','county','province','state','postcode','country']
SELECT_KEYS={'amenity','name','name:km','name:en','brand','operator','opening_hours','access','disused','abandoned','construction','proposed','check_date','survey:date','source','source:date'}

def keep_tags(tags):
    return {k:v for k,v in tags if k in SELECT_KEYS or k.startswith(('addr:','fuel:','disused:','abandoned:','construction:','proposed:'))}

def jd(x): return json.dumps(x,ensure_ascii=False,separators=(',',':'),sort_keys=True)

def sha256(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def haversine(a,b):
    lon1,lat1=map(math.radians,(a.x,a.y));lon2,lat2=map(math.radians,(b.x,b.y))
    d=math.sin((lat2-lat1)/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 6371008.8*2*math.asin(min(1,math.sqrt(d)))

class Extractor(osmium.SimpleHandler):
    def __init__(self):
        super().__init__(); self.objects={};self.counts=collections.Counter();self.identity_repeats=0
        self.country=None;self.country_id=None;self.country_geometry_error='';self.factory=osmium.geom.WKBFactory()
    def register(self,typ,o):
        self.counts[typ]+=1; key=f'{typ}/{o.id}'
        if key in self.objects: self.identity_repeats+=1
        data={'osm_type':typ,'osm_id':o.id,'tags':keep_tags(o.tags),'geometry':None,'point':None,'coordinate_method':'','errors':[]}
        self.objects[key]=data;return data
    def node(self,o):
        if o.tags.get('amenity')!='fuel':return
        d=self.register('node',o)
        if o.location.valid(): d['geometry']=d['point']=Point(o.location.lon,o.location.lat);d['coordinate_method']='osm_node'
        else:d['errors'].append('invalid_node_location')
    def way(self,o):
        if o.tags.get('amenity')!='fuel':return
        d=self.register('way',o)
        coords=[(n.lon,n.lat) for n in o.nodes if n.location.valid()]
        if len(coords)!=len(o.nodes): d['errors'].append('missing_way_node_location');return
        if len(coords)<2:d['errors'].append('insufficient_way_nodes');return
        if o.is_closed() and len(coords)>=4 and o.tags.get('area')!='no':
            poly=Polygon(coords)
            if poly.is_valid and not poly.is_empty and poly.area>0:
                d['geometry']=poly;d['point']=poly.representative_point();d['coordinate_method']='polygon_point_on_surface';return
            d['errors'].append('invalid_polygon_using_way_midpoint')
        g=LineString(coords)
        if g.is_empty:return
        d['geometry']=g;d['point']=g.interpolate(0.5,normalized=True);d['coordinate_method']='way_length_midpoint_degrees'
        d['errors'].append('non_area_way_coordinate')
    def relation(self,o):
        if o.tags.get('amenity')=='fuel':
            d=self.register('relation',o); d['relation_type']=o.tags.get('type','')
        if o.tags.get('boundary')=='administrative' and o.tags.get('admin_level')=='2' and o.tags.get('ISO3166-1')=='KH': self.country_id=o.id
    def area(self,a):
        is_country=a.tags.get('boundary')=='administrative' and a.tags.get('admin_level')=='2' and a.tags.get('ISO3166-1')=='KH'
        is_fuel=a.tags.get('amenity')=='fuel'
        if not (is_country or is_fuel):return
        try:
            g=wkb.loads(self.factory.create_multipolygon(a),hex=True)
            if not g.is_valid or g.is_empty:raise ValueError('assembled area invalid or empty')
        except Exception as e:
            if is_country:self.country_geometry_error=type(e).__name__+': '+str(e)
            return
        if is_country:self.country=g;self.country_id=a.orig_id()
        if is_fuel:
            typ='way' if a.from_way() else 'relation';key=f'{typ}/{a.orig_id()}'
            if key not in self.objects:raise RuntimeError('assembled fuel area without original object: '+key)
            d=self.objects[key];d['geometry']=g;d['point']=g.representative_point();d['coordinate_method']='polygon_point_on_surface';d['errors']=[]

def safe_cell(v,escaped,field):
    if not isinstance(v,str):return v
    if v and (v[0] in '\t\r\n' or v.lstrip()[:1] in '=+-@'):
        escaped.append(field);return "'"+v
    return v

def write_csv(path,rows,fields):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='raise',lineterminator='\n');w.writeheader();w.writerows(rows)

def main():
    actual_md5=hashlib.md5(PBF.read_bytes()).hexdigest();published_md5=(PBF.with_name(PBF.name+'.md5').read_text().split()[0])
    if actual_md5!=published_md5:raise SystemExit('Source MD5 mismatch')
    r=osmium.io.Reader(str(PBF));timestamp=r.header().get('osmosis_replication_timestamp');r.close()
    if not timestamp:raise SystemExit('Source lacks replication timestamp')
    h=Extractor();h.apply_file(str(PBF),locations=True,idx='flex_mem')
    if h.country is None:raise SystemExit('Cambodia boundary not assembled: '+h.country_geometry_error)
    retained=[];excluded=[]
    for key,d in sorted(h.objects.items(),key=lambda kv:({'node':0,'way':1,'relation':2}[kv[1]['osm_type']],kv[1]['osm_id'])):
        p=d['point'];reason=''
        if p is None:reason='unusable_geometry'
        elif not (math.isfinite(p.x) and math.isfinite(p.y) and -180<=p.x<=180 and -90<=p.y<=90):reason='invalid_coordinate'
        elif not h.country.covers(p):reason='representative_point_outside_cambodia_osm_boundary'
        if reason:
            excluded.append({'osm_type':d['osm_type'],'osm_id':d['osm_id'],'osm_url':'https://www.openstreetmap.org/'+key,'reason':reason,'longitude':'' if p is None else f'{p.x:.7f}','latitude':'' if p is None else f'{p.y:.7f}','name':d['tags'].get('name',''),'geometry_notes':';'.join(d['errors'])});continue
        d['key']=key;d['possible_duplicates']=[];retained.append(d)
    duplicate_pairs=[]
    for i,a in enumerate(retained):
        for b in retained[i+1:]:
            distance=haversine(a['point'],b['point']);overlap=a['geometry'].intersects(b['geometry'])
            if distance<=40 or overlap:
                reason='geometry_intersection' if overlap else 'representative_points_within_40m'
                a['possible_duplicates'].append(b['key']);b['possible_duplicates'].append(a['key'])
                duplicate_pairs.append({'osm_object_1':a['key'],'osm_object_2':b['key'],'point_distance_m':round(distance,2),'reason':reason})
    rows=[];features=[];flags_count=collections.Counter();escape_count=0
    for d in retained:
        t=d['tags'];p=d['point'];addr={k:v for k,v in t.items() if k.startswith('addr:')};flags=list(d['errors'])
        if not any(t.get(k) for k in ['name','name:km','name:en']):flags.append('missing_name')
        if not any(v for v in addr.values()):flags.append('missing_address_tags')
        if d['possible_duplicates']:flags.append('potential_duplicate_site')
        if any(k in t and t[k] not in ['no','false','0'] for k in ['disused','abandoned','construction','proposed']) or any(k.startswith(('disused:','abandoned:','construction:','proposed:')) for k in t):flags.append('lifecycle_tag_present')
        if t.get('access') in ['private','no']:flags.append('restricted_access_tag')
        if not h.country.covers(d['geometry']):flags.append('geometry_extends_outside_boundary')
        # Compose only source address values; do not reverse-geocode, transliterate, or invent missing fields.
        address=t.get('addr:full','')
        if not address:
            parts=[]
            street=' '.join(filter(None,[t.get('addr:housenumber',''),t.get('addr:street','')]))
            if street:parts.append(street)
            for k in ADDRESS_KEYS:
                if k in ['full','housenumber','street']:continue
                if t.get('addr:'+k):parts.append(t['addr:'+k])
            address=', '.join(parts)
        name_key=next((k for k in ['name','name:en','name:km'] if t.get(k)), '')
        row={'display_name':t.get(name_key,''),'display_name_source_tag':name_key,'name':t.get('name',''),'name_km':t.get('name:km',''),'name_en':t.get('name:en',''),'latitude':f'{p.y:.7f}','longitude':f'{p.x:.7f}','address':address,'brand':t.get('brand',''),'operator':t.get('operator',''),'osm_type':d['osm_type'],'osm_id':d['osm_id'],'osm_url':'https://www.openstreetmap.org/'+d['key'],'coordinate_method':d['coordinate_method'],'source_geometry_type':d['geometry'].geom_type,'country_filter':'OSM_KH_boundary_'+str(h.country_id),'address_method':'addr:full' if t.get('addr:full') else ('joined_addr_tags' if address else 'missing')}
        row.update({'addr_'+k:t.get('addr:'+k,'') for k in ADDRESS_KEYS})
        row.update({'address_tags_json':jd(addr),'fuel_tags_json':jd({k:v for k,v in t.items() if k.startswith('fuel:')}),'source_tags_json':jd(t),'opening_hours':t.get('opening_hours',''),'access':t.get('access',''),'potential_duplicate_osm_objects':';'.join(sorted(d['possible_duplicates'])),'quality_flags':';'.join(flags),'source_snapshot_utc':timestamp,'source_extract_url':SOURCE_URL,'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'})
        # GeoJSON preserves original strings exactly. CSV text is prefixed if spreadsheet-risky.
        properties=dict(row);properties['osm_id']=str(d['osm_id']);properties['address_tags']=addr;properties['source_tags']=t
        features.append({'type':'Feature','id':d['key'],'geometry':{'type':'Point','coordinates':[p.x,p.y]},'properties':properties})
        escaped=[];row={k:safe_cell(v,escaped,k) for k,v in row.items()};row['csv_escaped_fields']=';'.join(escaped)
        if escaped:escape_count+=1
        rows.append(row);flags_count.update(flags)
    fields=list(rows[0]) if rows else []
    write_csv(BASE/'cambodia_fuel_stations.csv',rows,fields)
    for row in excluded:
        escaped=[]
        for k,v in row.items():row[k]=safe_cell(v,escaped,k)
    write_csv(BASE/'excluded_osm_objects.csv',excluded,['osm_type','osm_id','osm_url','reason','longitude','latitude','name','geometry_notes'])
    write_csv(BASE/'potential_duplicate_pairs.csv',duplicate_pairs,['osm_object_1','osm_object_2','point_distance_m','reason'])
    (BASE/'cambodia_fuel_stations.geojson').write_text(jd({'type':'FeatureCollection','name':'Cambodia OSM fuel station POIs','attribution':'© OpenStreetMap contributors','license':LICENSE_URL,'source_snapshot_utc':timestamp,'features':features})+'\n',encoding='utf-8')
    (BASE/'cambodia_filter_boundary.geojson').write_text(jd({'type':'Feature','properties':{'osm_type':'relation','osm_id':str(h.country_id),'osm_url':'https://www.openstreetmap.org/relation/'+str(h.country_id),'source_snapshot_utc':timestamp,'attribution':'© OpenStreetMap contributors','license':LICENSE_URL},'geometry':mapping(h.country)})+'\n',encoding='utf-8')
    manifest={'dataset':'Cambodia OSM amenity=fuel POIs','source_url':SOURCE_URL,'source_page':SOURCE_PAGE,'source_snapshot_utc':timestamp,'source_file_bytes':PBF.stat().st_size,'source_md5':actual_md5,'published_md5_verified':True,'source_sha256':sha256(PBF),'country_boundary_osm_relation':h.country_id,'country_boundary_valid':h.country.is_valid,'country_boundary_bounds_wgs84':list(h.country.bounds),'source_tagged_object_counts':{k:h.counts[k] for k in ['node','way','relation']},'source_unique_tagged_objects':len(h.objects),'repeated_exact_object_identities_removed':h.identity_repeats,'output_rows':len(rows),'output_object_counts':{k:sum(d['osm_type']==k for d in retained) for k in ['node','way','relation']},'excluded_objects':len(excluded),'excluded_reasons':dict(collections.Counter(e['reason'] for e in excluded)),'unusable_geometries':sum(e['reason']=='unusable_geometry' for e in excluded),'potential_duplicate_pairs':len(duplicate_pairs),'objects_flagged_potential_duplicate':sum(bool(d['possible_duplicates']) for d in retained),'quality_flag_counts':dict(flags_count),'coordinate_method_counts':dict(collections.Counter(d['coordinate_method'] for d in retained)),'missing_fields':{k:sum(not r[k] for r in rows) for k in ['name','name_km','name_en','brand','operator','address','addr_full','addr_street','addr_city']},'has_any_name':sum(any(r[k] for k in ['name','name_km','name_en']) for r in rows),'with_any_address_tags':sum(bool(json.loads(r['address_tags_json'])) for r in rows),'csv_rows_with_escaped_cells':escape_count,'coordinates_wgs84_bounds':{'min_longitude':min(d['point'].x for d in retained),'min_latitude':min(d['point'].y for d in retained),'max_longitude':max(d['point'].x for d in retained),'max_latitude':max(d['point'].y for d in retained)},'validation':{'all_rows_unique_osm_identity':len({(r['osm_type'],r['osm_id']) for r in rows})==len(rows),'all_output_points_inside_or_on_cambodia_boundary':all(h.country.covers(d['point']) for d in retained),'all_coordinates_finite_and_globally_valid':all(-180<=d['point'].x<=180 and -90<=d['point'].y<=90 for d in retained),'csv_geojson_row_count_equal':len(rows)==len(features),'input_reconciled':len(rows)+len(excluded)==len(h.objects),'contributor_metadata_exported':False},'software':{'python':platform.python_version(),'osmium':importlib.metadata.version('osmium'),'shapely':importlib.metadata.version('shapely')},'license':'ODbL-1.0','license_url':LICENSE_URL,'attribution':'© OpenStreetMap contributors'}
    manifest['output_sha256']={name:sha256(BASE/name) for name in ['cambodia_fuel_stations.csv','cambodia_fuel_stations.geojson','cambodia_filter_boundary.geojson','potential_duplicate_pairs.csv','excluded_osm_objects.csv']}
    (BASE/'provenance.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
