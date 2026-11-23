# Historical election results: source note

| | |
|---|---|
| File | `kura254_historical_results.csv` |
| Downloaded | 22 November 2026, from https://www.kura254.com/open-data ("Historical election results", CSV) |
| Size | 11,207,212 bytes; 46,607 candidate rows; 6,069 contests |
| SHA-256 | `cfe1351d0ecae9118ee8b2a06d5db44f629694975b00a70e13ef02059651f51a` |
| Used by | Targets design `TD-R7` (competitive target) |

## Coverage

| Office | 2013 | 2017 | 2022 |
|---|---|---|---|
| Governor | 47 counties | 47 counties | 47 counties |
| Senator | 47 counties | 47 counties | 47 counties |
| Women rep | 47 counties | 47 counties | 47 counties |
| MP | 290 constituencies | 288 constituencies | 290 constituencies |
| MCA | 1,450 wards | 1,447 wards | 1,450 wards |
| President | 290 constituencies | 47 counties (August and October, separate) | 47 counties |

Every row carries the candidate's votes and the contest's total votes (`contest_total_votes`).
Registered voters are filled only for presidential rows.

## Columns

`record_id, year, election, race, county, county_code, constituency, constituency_code, ward,
ward_code, candidate, party, votes, share_fraction, registered_voters, turnout_fraction,
contest_total_votes, source_reference, data_note, election_status`

## Original sources (per Kura254)

- 2013: IEBC, "4th March 2013 General Election: Election Data".
- 2017: IEBC, "Data Report of 2017 Elections" (April 2020). IEBC later recalled this report
  citing errors in the data; 2017 contests are checked on load and inconsistent ones are left out.
- 2022: "2022 GE RESULTS.xlsx", described by Kura254 as the final supplied results.

## Terms

Kura254 names no licence. Credit Kura254 and the original IEBC sources wherever this data is
shown; the original sources' terms apply. Import geography codes as text to keep leading zeros.
Contest totals repeat on every candidate row: do not sum them across candidates. Empty values mean
unavailable, not zero.
