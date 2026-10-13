# Caveats

These limits are properties of the public records, not of the database. The in-app About panel includes this page.

## Tenure is the last deed, not the last sale

A transfer into a trust, a deed that removes a spouse, or an estate filing records a new book and restarts `tenure_years_est` even when the household did not change. Use owner type and, when it is filled in, family tenure. `family_tenure_is_min` means the prior deed is older than the county’s digital books, so the year is a lower bound (`<2003` in most towns).

Towns that rarely report deed books are marked `unknown` rather than `likely`. A blank book there is not evidence of a 20-year hold. Lewisboro’s earliest reported books are around 2014, so “likely” would be a weak claim and those rows stay unknown unless a senior exemption is present.

## Senior means an exemption

There are no birth dates. Aged (41800s) or Enhanced STAR on the roll means some owner qualified as 65 or older. Owners who take STAR as a tax credit do not appear. Absence of the flag is not evidence that the owner is young.

Exemption codes on data.ny.gov are truncated to 4 digits. The boolean flags are stored separately so 41834 (Enhanced STAR) is not confused with a different 4183x code beyond what the source can show.

Cortlandt’s exemption rows are mostly missing from the ORPTS file (on the order of 900 rows for the town), so Cortlandt senior flags undercount.

## Price is not an appraisal

The estimate inherits any error in that house’s assessment: condition, renovations, stale inventory. It uses the town ratio. Village-assessed parcels can be off. Values under about $150,000 are usually partial or special assessments; the app hides them unless the filter is turned off. Raw RP-5217 sales were not used. SalesWeb has no bulk download.

The index adjustment is county-wide. It does not know whether one town appreciated faster than another.

## Building facts are incomplete

Living area, beds, and baths are missing where the assessor did not publish inventory: Greenburgh, Lewisboro, North Castle, North Salem, Ossining, and sparsely in Bedford, Cortlandt, Eastchester, Mount Vernon, and Peekskill. County-wide coverage of living area on the full class-210 roll is about 58 percent.

## Hazard and walk scores are proxies

Flood zone is the zone under a point, not a survey of the lot. National Risk Index values are for the whole census tract. The walk score is an OpenStreetMap count with distance decay, not Walk Score, and bus stops are under-mapped in places. Metro-North distance is straight-line. The sun index ignores trees and roofs. School district is the TIGER polygon around the point; the name on the tax roll can differ, and it is missing for most of Cortlandt.

## Permits

`permits` is an empty table. `permits_matched` and `permit_flags` on the flat extract are blank. Nothing in the app should be read as “no permits on this house.”

## Coverage of this repository

The committed file is the app extract (65,011 homes), not the full class-210 roll. Rebuilding the full roll requires the GIS pull, the ORPTS pull, and the enrichment inputs listed in [sources](sources.md). Those files are gitignored.
