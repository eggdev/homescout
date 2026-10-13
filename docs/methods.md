# Methods

The app extract is single-family homes (New York property class 210) that have likely been in the same hands for 20 years or more, plus homes held by a trust, estate, or life estate at any tenure. Westchester’s 2025 roll has about 164,000 class-210 parcels. The committed extract has 65,011 of them: the long-tenure slice and the trust/estate slice.

## Deed date and tenure

Westchester County Clerk control numbers encode the recording date:

`book = (year - 1960) * 1000 + day-of-year`

Example: 46123 is 2006, day 123, which is 2006-05-03. This was checked on parcels whose book changed between consecutive rolls from 2021 to 2025. The new book was always in the 61xxx–65xxx range for that year. The decoder lives on `WestchesterNY` and is not assumed for other counties.

`tenure_20plus`:

- **yes** — estimated deed date is on or before 2006-10-11 (20 years before the 2026-10-11 build date).
- **no** — a decoded deed is more recent than that.
- **likely** — the roll has no deed reference. In most towns that means the deed predates the town’s earliest reported control number (`blank_deed_means_before_year`, about 2003). Greenburgh is weaker (about 2010), North Castle about 2013, Lewisboro about 2014.
- **unknown** — the town reports deed references on fewer than half its class-210 parcels, so a blank book is not evidence of a long hold.

The date is the **last recorded deed**. A non-sale transfer (into a trust, removing a spouse, an estate) resets the clock even when the family has not changed. `trust_or_estate_owner` and the prior-roll surname check exist for that reason.

## Exemptions

`senior_signal` is an aged exemption (4180x, that is 41800–41809) or Enhanced STAR (4183x, published as 4183, which is 41834: age 65 and income-qualified). Newer owners often receive STAR as an income-tax credit instead of an exemption, so a missing STAR exemption does not mean the owner is not 65.

`owner_occupied_est` is true when the mailing address matches the property address, or the parcel has Basic or Enhanced STAR. `absentee_owner` is the opposite.

## Owner type and family tenure

Owner names from the GIS roll and the ORPTS name fields are classified as an individual, a revocable/living trust, an irrevocable trust, another trust, a life estate, an estate, or an LLC/corporation. The patterns are in `pipeline/enrich/owner_type.py`.

For trust and estate owners, the 2021–2024 rolls are scanned for a different deed book. If the prior owner shares a surname (after dropping words like TRUST, ESTATE, TRUSTEE), `family_confidence` is `same surname` and `family_tenure_years` runs from that earlier deed, or from the town’s “blank means before” year when the prior book cannot be decoded. `family_tenure_combined_yrs` is the longer of family tenure and the current deed tenure in that case.

## Enrichment

- **Location.** Parcel representative point from the county polygon.
- **School district.** Census TIGER 2024 unified district containing the point, plus the district name on the assessment roll (missing for most of Cortlandt). No NYSED performance metrics.
- **Walk proxy (`walk_proxy_0_100`).** Not Walk Score. OpenStreetMap groceries, dining, errands, schools, parks, bus stops, and rail stations. A place counts fully within 400 m and declines linearly to 0 at 1.6 km. Weights: grocery 3, dining 3, errands 2, transit 2, school 1, park 1. Counts within 800 m are stored separately. Bus-stop completeness in OSM varies.
- **Metro-North.** Straight-line distance to the nearest Metro-North station, not a walking route. Stations whose network tag also says NJ Transit are excluded.
- **Flood.** FEMA NFHL zone at the parcel point. AE, A, and VE are the 100-year special flood hazard area. “X shaded” is the 500-year zone. A parcel that is only partly in a zone can still show X. This is not an official flood determination.
- **National Risk Index.** Tract-level scores and ratings (overall, inland and coastal flood, hurricane, winter weather, ice storm, wind, heat, cold, landslide, tornado). Every home in a tract shares the value.
- **Terrain.** USGS 3DEP 1/3 arc-second (about 10 m). Elevation, slope smoothed over about 50 m, aspect (downslope direction; “flat” below 2 degrees).
- **Sun (`solar_terrain_index`).** Clear-sky annual irradiance on the ground at the parcel versus a flat, unobstructed site (100). Uses pvlib sun positions (every 4th day, hourly), slope, aspect, and a terrain horizon in 16 directions out to 3 km. Terrain only: trees, buildings, roof direction, and clouds are ignored. Most homes land between 95 and 102. The useful cases are north-facing slopes and valley shade.
- **Price.** Total assessed value divided by the town’s 2025 NYS residential assessment ratio is about a mid-2024 market value. That is multiplied by the change in the Zillow Westchester single-family index from 2024-07-31 to the latest month in the file used for the prototype (through 2026-08-31 in the committed extract, factor 1.113). The low/high band is ±1.5 times the town’s residential coefficient of dispersion (county median where the town is missing). The row stores the recipe string and a method version (`rar-zhvi-westchester-2025-v1`) so a later recipe can sit beside it.

`est_price_per_sqft` is the mid estimate divided by living area, and is blank where living area is missing.

## Who is in the app

A home is included when `tenure_20plus` is `yes` or `likely`, or it is `unknown` and has a senior signal, or the owner type is a trust, estate, or life estate. `why_included` records which rule fired.
