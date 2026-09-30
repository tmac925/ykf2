#!/usr/bin/env python3
import csv, io, os, re, urllib.request, unicodedata
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
WPI_PATH = os.path.join(ROOT, "UpdatedPub150.csv")
OUT = os.path.join(ROOT, "generated")
os.makedirs(OUT, exist_ok=True)
os.makedirs(os.path.join(OUT, "regions"), exist_ok=True)

URLS = {
    "locode": "https://raw.githubusercontent.com/datasets/un-locode/main/data/code-list.csv",
    "subdiv": "https://raw.githubusercontent.com/datasets/un-locode/main/data/subdivision-codes.csv",
    "loc_country": "https://raw.githubusercontent.com/datasets/un-locode/main/data/country-codes.csv",
    "country_meta": "https://raw.githubusercontent.com/datasets/country-codes/main/data/country-codes.csv",
}

def download_text(url):
    with urllib.request.urlopen(url, timeout=120) as r:
        return r.read().decode("utf-8-sig")

def rows_from_text(text):
    return list(csv.DictReader(io.StringIO(text)))

def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.upper().replace("&", " AND ")
    return re.sub(r"[^A-Z0-9]+", " ", s).strip()

def parse_coord_pair(s):
    s=(s or "").strip().upper()
    if not s:
        return ("","")
    m=re.match(r"^(\d{2})(\d{2})([NS])\s+(\d{3})(\d{2})([EW])$", s)
    if not m:
        return ("","")
    lat=int(m.group(1))+int(m.group(2))/60
    lon=int(m.group(4))+int(m.group(5))/60
    if m.group(3)=="S": lat=-lat
    if m.group(6)=="W": lon=-lon
    return (round(lat,6),round(lon,6))

def tankorx_continent(region, subregion, a2):
    if a2 == "AQ":
        return "Antarctica"
    if region == "Europe":
        return "Europe"
    if region == "Asia":
        return "Asia"
    if region == "Africa":
        return "Africa"
    if region == "Oceania":
        return "Oceania"
    if region == "Americas":
        if subregion == "South America":
            return "South America"
        return "North America"
    return region or ""

def group_for(a2, region, subregion):
    if a2 in {"EE","LV","LT"}: return "Baltics"
    if subregion == "South America": return "South America"
    if subregion == "Central America": return "Central America"
    if subregion == "Caribbean": return "Caribbean"
    if subregion == "Northern America": return "North America"
    if region == "Europe": return subregion or "Europe"
    if a2 in {"AE","BH","IL","IQ","IR","JO","KW","LB","OM","PS","QA","SA","SY","TR","YE"}: return "Middle East"
    if subregion == "Eastern Asia": return "East Asia"
    if subregion == "South-eastern Asia": return "Southeast Asia"
    if subregion == "Southern Asia": return "South Asia"
    if subregion == "Central Asia": return "Central Asia"
    if region == "Asia": return subregion or "Asia"
    if region == "Africa": return subregion or "Africa"
    if region == "Oceania": return subregion or "Oceania"
    return subregion or region or ""

# Load sources
with open(WPI_PATH, encoding="utf-8-sig", newline="") as f:
    wpi = list(csv.DictReader(f))
    wpi_headers = list(wpi[0].keys()) if wpi else []

locode = rows_from_text(download_text(URLS["locode"]))
subdiv = rows_from_text(download_text(URLS["subdiv"]))
loc_country = rows_from_text(download_text(URLS["loc_country"]))
country_meta = rows_from_text(download_text(URLS["country_meta"]))

country_names = {r.get("CountryCode",""): r.get("CountryName","") for r in loc_country}
sub_map = {}
for r in subdiv:
    c=r.get("SUCountry",""); code=r.get("SUCode","")
    if c and code:
        sub_map[(c,code)] = (r.get("SUName",""), r.get("SUType",""))

meta = {}
for r in country_meta:
    a2=r.get("ISO3166-1-Alpha-2","")
    if not a2: continue
    meta[a2]={
        "iso3": r.get("ISO3166-1-Alpha-3",""),
        "region": r.get("Region Name",""),
        "subregion": r.get("Sub-region Name",""),
        "intermediate": r.get("Intermediate Region Name",""),
        "name": r.get("CLDR display name","") or r.get("UNTERM English Short","") or country_names.get(a2,""),
    }

# Reverse country-name lookup because the current NGA WPI column labelled
# "Country Code" actually contains country names in this release.
country_name_to_a2 = {}
for a2,name in country_names.items():
    if name:
        country_name_to_a2[norm(name)] = a2
for a2,cm in meta.items():
    for name in (cm.get("name",""), country_names.get(a2,"")):
        if name:
            country_name_to_a2[norm(name)] = a2
country_aliases = {
    "RUSSIA":"RU","TURKEY":"TR","TURKIYE":"TR","SOUTH KOREA":"KR","KOREA SOUTH":"KR",
    "NORTH KOREA":"KP","KOREA NORTH":"KP","IRAN":"IR","SYRIA":"SY","LAOS":"LA",
    "VIETNAM":"VN","BOLIVIA":"BO","VENEZUELA":"VE","TANZANIA":"TZ","MOLDOVA":"MD",
    "BRUNEI":"BN","CAPE VERDE":"CV","IVORY COAST":"CI","COTE D IVOIRE":"CI",
    "MICRONESIA":"FM","PALESTINE":"PS","TAIWAN":"TW","HONG KONG":"HK","MACAU":"MO",
    "CURACAO":"CW","REUNION":"RE","SAINT MARTIN":"MF","SINT MAARTEN":"SX"
}
country_name_to_a2.update(country_aliases)

loc_by_code = {}
sea_by_country_name = defaultdict(list)
sea_rows = []
for r in locode:
    c=(r.get("Country") or "").upper()
    l=(r.get("Location") or "").upper()
    if not c or not l: continue
    full=c+l
    loc_by_code[full]=r
    function=r.get("Function") or ""
    if function.startswith("1"):
        sea_rows.append(r)
        sea_by_country_name[(c,norm(r.get("NameWoDiacritics") or r.get("Name") or ""))].append(r)

geo_headers = [
    "Continent","Geographic Subregion","Intermediate Region","TankorX Region Group",
    "Country Name","Country ISO2","Country ISO3",
    "State/Province Name","State/Province ISO 3166-2","State/Province Type",
    "City/Locality","Maritime Region","World Water Body","IHO S-130 Sea Area","NAVAREA",
    "WPI Number","UN/LOCODE Normalized","Port Name","Alternate Port Name","Latitude","Longitude",
    "Record Coverage","UN/LOCODE Match Method","Geo Validation Status",
    "Primary Maritime Source","Geography Source"
]
headers = geo_headers + wpi_headers

def geo_for(a2, loc=None):
    cm=meta.get(a2,{})
    sub=(loc or {}).get("Subdivision","") if loc else ""
    sm=sub_map.get((a2,sub),("",""))
    region=cm.get("region",""); subregion=cm.get("subregion","")
    return {
        "Continent": tankorx_continent(region,subregion,a2),
        "Geographic Subregion": subregion,
        "Intermediate Region": cm.get("intermediate",""),
        "TankorX Region Group": group_for(a2,region,subregion),
        "Country Name": country_names.get(a2) or cm.get("name",""),
        "Country ISO2": a2,
        "Country ISO3": cm.get("iso3",""),
        "State/Province Name": sm[0],
        "State/Province ISO 3166-2": (a2+"-"+sub) if sub else "",
        "State/Province Type": sm[1],
        "City/Locality": (loc or {}).get("Name","") if loc else "",
    }

master=[]
used_locodes=set()

unmapped_wpi_countries=set()
for r in wpi:
    raw=(r.get("UN/LOCODE") or "").replace(" ","").strip().upper()
    wpi_country=(r.get("Country Code") or "").strip()
    # Prefer the country encoded in a valid UN/LOCODE. Otherwise resolve the WPI country name.
    if raw and len(raw)>=5 and raw[:2] in meta:
        a2=raw[:2]
    else:
        a2=country_name_to_a2.get(norm(wpi_country),"")
    if not a2:
        unmapped_wpi_countries.add(wpi_country)
    loc=loc_by_code.get(raw) if raw else None
    method=""
    if loc:
        method="Exact UN/LOCODE"
    else:
        cands=sea_by_country_name.get((a2,norm(r.get("Main Port Name") or "")),[])
        if len(cands)==1:
            loc=cands[0]
            raw=a2+(loc.get("Location") or "")
            method="Unique country + sea-port name"
        else:
            method="No authoritative UN/LOCODE match"
    if loc:
        used_locodes.add(a2+(loc.get("Location") or "").upper())
    g=geo_for(a2,loc)
    sub_present=bool((loc or {}).get("Subdivision"))
    sub_named=bool(g["State/Province Name"])
    if loc and (not sub_present or sub_named):
        validation="Validated against UN/LOCODE"
    elif loc:
        validation="UN/LOCODE matched; subdivision code could not be resolved to a name"
    else:
        validation="WPI port retained; administrative subdivision not authoritatively resolved"
    row={**g,
        "Maritime Region":r.get("Region Name",""),
        "World Water Body":r.get("World Water Body",""),
        "IHO S-130 Sea Area":r.get("IHO S-130 Sea Area",""),
        "NAVAREA":r.get("NAVAREA",""),
        "WPI Number":r.get("World Port Index Number",""),
        "UN/LOCODE Normalized":raw,
        "Port Name":r.get("Main Port Name",""),
        "Alternate Port Name":r.get("Alternate Port Name",""),
        "Latitude":r.get("Latitude",""),
        "Longitude":r.get("Longitude",""),
        "Record Coverage":"NGA WPI detailed port",
        "UN/LOCODE Match Method":method,
        "Geo Validation Status":validation,
        "Primary Maritime Source":"NGA World Port Index",
        "Geography Source":"UNECE UN/LOCODE + UN/ISO country/subdivision metadata",
    }
    row.update(r)
    master.append(row)

# Add official UNECE sea-port locations that are not present in the WPI set.
for loc in sea_rows:
    a2=(loc.get("Country") or "").upper()
    full=a2+(loc.get("Location") or "").upper()
    if full in used_locodes:
        continue
    g=geo_for(a2,loc)
    lat,lon=parse_coord_pair(loc.get("Coordinates",""))
    row={k:"" for k in headers}
    row.update(g)
    row.update({
        "UN/LOCODE Normalized":full,
        "Port Name":loc.get("Name",""),
        "Latitude":lat,
        "Longitude":lon,
        "Record Coverage":"UNECE sea-port location; WPI operational fields unavailable",
        "UN/LOCODE Match Method":"UNECE official sea-port record",
        "Geo Validation Status":"Official UN/LOCODE geography; no NGA WPI operational record linked",
        "Primary Maritime Source":"UNECE UN/LOCODE",
        "Geography Source":"UNECE UN/LOCODE + UN/ISO country/subdivision metadata",
        "UN/LOCODE":full,
        "Country Code":a2,
        "Main Port Name":loc.get("Name",""),
        "Latitude":lat,
        "Longitude":lon,
    })
    master.append(row)

# Deterministic sort
master.sort(key=lambda r:(r.get("Country Name",""),r.get("State/Province Name",""),r.get("Port Name",""),r.get("UN/LOCODE Normalized","")))

def write_csv(path, rows):
    with open(path,"w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=headers,extrasaction="ignore")
        w.writeheader(); w.writerows(rows)

write_csv(os.path.join(OUT,"TankorX_World_Ports_Master.csv"),master)
write_csv(os.path.join(OUT,"TankorX_WPI_Detailed_Ports.csv"),[r for r in master if r["Record Coverage"]=="NGA WPI detailed port"])

# Region files useful for staged imports.
region_filters = {
    "South_America": lambda r:r["Continent"]=="South America",
    "North_America": lambda r:r["Continent"]=="North America",
    "Europe": lambda r:r["Continent"]=="Europe",
    "Baltics": lambda r:r["TankorX Region Group"]=="Baltics",
    "Asia": lambda r:r["Continent"]=="Asia",
    "Middle_East": lambda r:r["TankorX Region Group"]=="Middle East",
    "Africa": lambda r:r["Continent"]=="Africa",
    "Oceania": lambda r:r["Continent"]=="Oceania",
    "Caribbean": lambda r:r["TankorX Region Group"]=="Caribbean",
    "Central_America": lambda r:r["TankorX Region Group"]=="Central America",
}
for name,fn in region_filters.items():
    write_csv(os.path.join(OUT,"regions",f"TankorX_Ports_{name}.csv"),[r for r in master if fn(r)])

# Country files
country_dir=os.path.join(OUT,"countries"); os.makedirs(country_dir,exist_ok=True)
by_country=defaultdict(list)
for r in master: by_country[r["Country ISO2"]].append(r)
for a2,rs in by_country.items():
    if a2: write_csv(os.path.join(country_dir,f"TankorX_Ports_{a2}.csv"),rs)

summary = {
    "world_rows":len(master),
    "wpi_detailed_rows":sum(1 for r in master if r["Record Coverage"]=="NGA WPI detailed port"),
    "unlocode_only_sea_ports":sum(1 for r in master if r["Record Coverage"].startswith("UNECE sea-port")),
    "countries":len([x for x in by_country if x]),
    "with_state_province":sum(1 for r in master if r["State/Province ISO 3166-2"]),
    "unmapped_wpi_country_names":len(unmapped_wpi_countries),
}
with open(os.path.join(OUT,"BUILD_SUMMARY.txt"),"w",encoding="utf-8") as f:
    for k,v in summary.items(): f.write(f"{k}: {v}\n")

with open(os.path.join(OUT,"CLAUDE_IMPORT_INSTRUCTIONS.txt"),"w",encoding="utf-8") as f:
    f.write("""TANKORX WORLD PORT MASTER IMPORT\n\nUse TankorX_World_Ports_Master.csv as the global master.\n\nIDENTITY / UPSERT\n1. Prefer WPI Number for rows where WPI Number is populated.\n2. Use UN/LOCODE Normalized as the secondary global location identifier.\n3. Never merge records solely by port name.\n\nGEOGRAPHY\nKeep administrative geography separate from maritime geography.\nAdministrative: Continent > Geographic Subregion > Country > State/Province > City/Locality.\nMaritime: Maritime Region > World Water Body > IHO S-130 Sea Area > NAVAREA.\n\nDATA COVERAGE\n- 'NGA WPI detailed port': full WPI operational fields are available.\n- 'UNECE sea-port location; WPI operational fields unavailable': official sea-port location exists, but depth/service/facility fields must remain NULL unless TankorX later verifies a source.\nDo not convert missing WPI operational values to false. Missing means unknown/not supplied.\n\nIMPORT\n- UTF-8-SIG CSV.\n- Blank strings / em-dashes -> NULL.\n- Yes/No/Unknown -> true/false/null only for boolean fields.\n- Depths/dimensions -> nullable decimals.\n- Latitude/Longitude -> decimal WGS84.\n- Back up DB and dry-run before commit.\n- Report inserts, updates, unchanged, rejected, duplicate WPI, duplicate UN/LOCODE, geography conflicts.\n""")

print(summary)
