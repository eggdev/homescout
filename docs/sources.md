# Sources

Everything HomeScout uses is free and public. No login, no paid aggregator.

The Westchester prototype was built on 2026-10-11 from the 2025 assessment roll. Figures below are for that county. Another county supplies its own endpoints through a region adapter (`pipeline/adapters/`).

## Parcels and the assessment roll

1. **Westchester County GIS, DataHub tax parcels** (2025 ORPTS roll joined to parcels).
   https://giswww.westchestergov.com/ArcGIS/rest/services/DataHub_TaxParcels/MapServer/0
   Living area, bedrooms, full baths, kitchens, year built, style, acres, owner, mailing address, deed book and page, full market value.
2. **NYS ORPTS “Property Assessment Data from Local Assessment Rolls”** (data.ny.gov `7vem-aaz7`), roll year 2025.
   https://data.ny.gov/resource/7vem-aaz7
   Exemption codes, published truncated to 4 digits. The 2021–2024 rolls are used only to see who owned a trust property before the current deed.

A statewide parcel id in New York is the SWIS code plus the print key. The database key adds state and county FIPS so the same shape works outside New York.

## Place, hazard, and terrain

- **Census TIGER 2024** unified school districts and census tracts.
  https://www2.census.gov/geo/tiger/TIGER2024/UNSD/ and https://www2.census.gov/geo/tiger/TIGER2024/TRACT/
- **FEMA National Flood Hazard Layer**, layer 28.
  https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28
- **FEMA National Risk Index** v1.20, census-tract scores.
  https://hazards.fema.gov/nri/
- **USGS 3DEP** 1/3 arc-second elevation.
  https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/current/
- **OpenStreetMap**, via a Geofabrik New York extract or Overpass. Amenities, transit, and roads.
  https://www.openstreetmap.org/copyright

## Price ratios

- **NYS residential assessment ratio** (data.ny.gov `bsmp-6um6`), which ORPTS derives from RP-5217 sales studies.
- **Residential coefficient of dispersion** (data.ny.gov `4sut-q3dt`).
- **Zillow Home Value Index** for Westchester County, used only as a county-level index from July 2024 to the latest published month. https://www.zillow.com/research/data/

## What is not a source

Building permits. No Westchester municipality publishes a free bulk permit file. Yonkers has a per-address portal (https://permits.yonkersny.gov); other towns use a lookup page or FOIL. Those were not scraped. The `permits` table is empty on purpose.

Owner age and date of birth are not public on the roll. “Senior” in this dataset means a public exemption, not a known age.
