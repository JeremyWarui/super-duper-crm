# Targets Design: vote targets from the last winning share (Release 7)

| | |
|---|---|
| Document ID | `TD-R7` |
| Version | 0.4, 23 November 2026 |
| Status | **Draft, awaiting approval** |
| Mockups | [`design/R7_Mockups.html`](design/R7_Mockups.html): `M3` Targets page |
| Applies to | Every installation: one candidate contesting one seat |
| Release | 7 (tickets `R7-0` to `R7-6`) |
| Related | `CD-R6` Communications Design |

How to use this document: every ticket in section 9 names the decisions (`T`) and sections it
implements. A ticket is done when its "Done when" line holds and its row in the tracker
(section 11) is ticked. Changes to an approved version get a new amendment (`A`) entry in
section 12 and a version bump.

---

## 1. Purpose

Every target in the CRM is set today at 50% + 1 of the projected turnout. That is the least a
candidate could win with, not what winners in the seat actually poll. In Laikipia the 2022
governor won with 113,783 votes (67.86% of valid votes), while the CRM's figure for the seat is
about 85,000. This document sets each seat's target at **the share the last winner took**, applied
to the votes expected in the seat, and shares it out to wards.

### Decisions for approval

| ID | Decision | Approved |
|---|---|---|
| T1 | The seat target is the 2022 winner's share of valid votes in that race, applied to projected valid votes (section 4). It replaces 50% + 1. | [ ] |
| T2 | The weighted share of the 2013, 2017 and 2022 winners (weights 0.2, 0.3, 0.5) is shown beside the target as "Typical winner", for reference. It sets the target only when the 2022 result is unusable (T8). | [ ] |
| T3 | In two-candidate seats the target never falls below the majority line (50% + 1). In crowded seats there is no lower limit; the majority line is shown for reference only. | [ ] |
| T4 | The Kura254 historical results file is the single source of past results. No PDF extraction. 2017 figures carry a caution (section 3.3). | [ ] |
| T5 | The seat target is shared out to wards by each ward's share of the seat's 2022 valid votes, with largest-remainder rounding so the wards add up exactly. MCA seats share out to polling centres the same way. | [ ] |
| T6 | Targets are recalculated on every refresh and never edited by hand. The result is saved in `Target.votes_needed`. Only the turnout scenario or turnout figure may be changed, and the change is recorded. | [ ] |
| T7 | Every target shows how reliable its data is: seat data, typical winner, or proxy. | [ ] |
| T8 | Fallbacks: no usable 2022 result for the seat → the weighted share (T2); no history at all → the national median winning share for that office, marked "proxy". | [ ] |
| T9 | The register is the 2022 register already held for every ward. The 2027 register is loaded in a later release, once IEBC publishes it. | [ ] |
| T10 | Turnout has three scenarios from the seat's own history: low, expected (default) and high (section 4, step 3). | [ ] |
| T11 | All calculations use exact fractions, not floating-point decimals, so results match a hand calculation to the vote. | [ ] |
| T12 | Trying a turnout scenario is a preview that saves nothing. Setting a scenario for the team is a separate step, open to the candidate and the manager only, confirmed, audited and notified to everyone whose target changes (section 6.1, amendment A4). | [ ] |

---

## 2. Definitions

| Term | Meaning |
|---|---|
| Seat | The office and area contested (for example Laikipia governor) |
| Register `R` | The seat's 2022 registered voters: the sum of its wards |
| Share `S` | The 2022 winner's votes ÷ valid votes in that race |
| Turnout `T` | Valid votes in that race ÷ `R` |
| Projected valid votes `P` | `R × (T + scenario adjustment)`, rounded to the nearest vote |
| Majority line `F` | `⌊P / 2⌋ + 1` |
| Two-candidate seat | In 2022 the top two candidates took 90% or more of valid votes |
| Crowded seat | Any other seat |
| Typical winner | `50% + Σ w_e (S_e − 50%)` over 2013, 2017 and 2022, weights 0.2, 0.3, 0.5 |

Share and turnout are always measured **on the same race**. Each ballot has its own rejected
votes; in Laikipia in 2022 the MCA ballot had 171,321 valid votes and the governor ballot 167,662.

---

## 3. Data

### 3.1 Source

`backend/data/history/kura254_historical_results.csv`, documented in `SOURCE.md` beside it
(download date, SHA-256 checksum, coverage, columns and terms). The 2022 ward register is the
existing `backend/data/ke_ge22_01_grv_caw_v100.csv`.

| Office | Level in the results file | Years |
|---|---|---|
| President | County (with registered voters) | 2013, 2017 (August and October), 2022 |
| Governor, Senator, Women Representative | County | 2013, 2017, 2022 |
| MP | Constituency | 2013, 2017, 2022 |
| MCA | Ward | 2013, 2017, 2022 |

Ward, constituency and county codes match the CRM's geography for every year.

### 3.2 Tables (built)

| Table | Holds |
|---|---|
| `elections` | One row per election (name, year) |
| `contests` | One row per office and area in an election: valid votes, registered voters, links to today's county, constituency and ward, flags for unopposed or excluded, and a note |
| `contest_candidates` | Each candidate in a contest: name, party, votes, rank, winner |

Loads are recorded in the existing import log (`ImportRun`, kind `results`) with the file's
checksum, so an unchanged file is not reloaded.

### 3.3 Quality rules

- A contest is **excluded** when candidate votes miss the stated total by more than 1% (and at
  least one vote), when the total is missing, or when any votes are missing. 25 of 6,069 contests
  are excluded in the current file.
- A tie at the top produces no winner. Unopposed contests (15) give no share and use T8.
- **2017 caution.** The 2017 figures come from IEBC's April 2020 data report, which IEBC later
  withdrew citing errors. They are used only in the typical winner and the high turnout scenario.
- **2013 county registers.** Some 2013 county figures in the file look incomplete (Laikipia shows
  83,267 registered). 2013 registers are not used for turnout.

---

## 4. The calculation

Five steps for every seat.

**Step 1. Share.** `S = winner's 2022 votes ÷ valid votes in that race`.

**Step 2. Turnout.** `T = valid votes in that race ÷ R`.

**Step 3. Projected valid votes.** `P = R × (T + adjustment)`, rounded to the nearest vote.

| Scenario | Adjustment |
|---|---|
| Low | −3 points |
| **Expected (default)** | 0 |
| High | + half the fall in the county's turnout from 2017 (August presidential) to 2022; 0 if turnout rose |

County turnout for the high scenario is presidential valid votes ÷ registered voters in each year.

**Step 4. Seat target.** `C = ⌈P × S⌉`. Two-candidate seat: target = `max(C, F)`. Crowded seat:
target = `C`, with `F` shown for reference.

**Step 5. Ward targets.** Each ward's weight is its share of the seat's 2022 valid votes, from the
MCA race (the only race with ward results). `ward target = seat target × weight`, then
largest-remainder rounding: every ward takes the whole part, and the votes left over go one each
to the wards with the largest fractions until the wards add up to the seat target. For MP seats
the wards are the constituency's wards. For MCA seats the ward is the seat and the target is
shared to polling centres by their 2022 valid votes (R7-5).

Wards are weighted by where the votes are, not by the winner's strength in each ward: the
results file has no ward-level results for offices above MCA, and the MCA party vote is not a
reliable stand-in (in Tigithi, Laikipia, UDA took 0.5% of the MCA vote in 2022). Every ward is
therefore asked for the same share.

### 4.1 Worked example: Laikipia governor

`R` = 263,012; `S` = 113,783 ÷ 167,662 = 67.86%; `T` = 167,662 ÷ 263,012 = 63.75%.
Two-candidate seat (top two took 96.8%). Typical winner: 59.83%.

| Scenario | Turnout | `P` | Target `C` | Majority line `F` | Seat target |
|---|---|---|---|---|---|
| Low | 60.75% | 159,772 | 108,429 | 79,887 | 108,429 |
| **Expected** | **63.75%** | **167,662** | **113,783** | 83,832 | **113,783** |
| High (+8.32) | 72.07% | 189,553 | 128,640 | 94,777 | 128,640 |

Ward targets, expected scenario (exact fractions, largest-remainder rounding):

| Ward | 2022 valid votes (MCA) | Weight | Ward target |
|---|---|---|---|
| Igwamiti | 26,907 | 15.71% | 17,870 |
| Marmanet | 17,948 | 10.48% | 11,920 |
| Nanyuki | 17,578 | 10.26% | 11,674 |
| Tigithi | 15,018 | 8.77% | 9,974 |
| Ngobit | 12,218 | 7.13% | 8,115 |
| Thingithu | 12,001 | 7.00% | 7,970 |
| Githiga | 11,181 | 6.53% | 7,426 |
| Sosian | 9,928 | 5.79% | 6,594 |
| Rumuruti Township | 9,219 | 5.38% | 6,123 |
| Umande | 8,108 | 4.73% | 5,385 |
| Mugogodo East | 7,418 | 4.33% | 4,927 |
| Ol-Moran | 6,737 | 3.93% | 4,474 |
| Segera | 6,420 | 3.75% | 4,264 |
| Salama | 6,262 | 3.66% | 4,159 |
| Mugogodo West | 4,378 | 2.56% | 2,908 |
| **Total** | **171,321** | | **113,783** |

### 4.2 Worked example: Marsabit governor

`R` = 166,912; `S` = 38,803 ÷ 114,789 = 33.80%; `T` = 114,789 ÷ 166,912 = 68.77%.
Crowded seat (top two took 58.4% among 6 candidates). Typical winner: 42.95%.

| Scenario | Turnout | `P` | Target `C` | Majority line `F` (reference) | Seat target |
|---|---|---|---|---|---|
| Low | 65.77% | 109,782 | 37,111 | 54,892 | 37,111 |
| **Expected** | **68.77%** | **114,789** | **38,803** | 57,395 | **38,803** |
| High (+4.69) | 73.46% | 122,614 | 41,449 | 61,308 | 41,449 |

---

## 5. Changes to the code

| Area | Change |
|---|---|
| `services/win_model.py` (new) | Share, turnout, scenarios, two-candidate test, typical winner, fallbacks, reliability; exact fractions throughout |
| `models/target.py` | `compute_win_number` replaced; new fields `turnout_scenario`, `turnout_overridden`, `ward_weight`, `reliability` |
| `models/campaign.py` | New fields `turnout_scenario` (default expected), `turnout_scenario_set_by_id`, `turnout_scenario_set_at` |
| API | `GET /campaigns/{id}/targets/preview/?scenario=` returns seat and ward figures without saving; `POST /campaigns/{id}/targets/scenario/` sets the scenario, recalculates and notifies |
| `services/permissions.py` | New permission `targets.set_scenario` for candidate and manager; previewing needs the existing targets view permission held by candidate, manager and comms |
| `services/targets.py` | `generate_targets` and `refresh_targets` call the new model; weight-based ward allocation with largest-remainder rounding |
| `models/geography.py` | `County.turnout_2022_pct` no longer drives targets; turnout comes from the results tables |
| Migration | Adds the fields and recalculates every existing target |
| Setup | The Target step previews the target, the scenarios and the ward split before the campaign is created |

---

## 6. Screens

- **Targets page (`M3`):** seat target; the share and the 2022 result behind it; turnout
  scenario buttons (Low, Expected, High); majority line; seat type; typical winner; reliability
  badge; "Team is working to" label showing the set scenario.
- **Ward list (`M3`):** each ward's target, supporters recorded and progress; while previewing,
  each ward's change from the set target.
- **Field app ward card (`M3`):** coordinators and mobilizers see the set target for their ward
  or area and their progress, with no scenario buttons and no preview.
- **Setup preview:** the same seat summary, shown before the campaign is created.
- **Strategy slides and reports:** always read the set scenario, never a preview.

### 6.1 Trying and setting a scenario

| | Trying (preview) | Setting (commitment) |
|---|---|---|
| Who | Candidate, manager, comms | Candidate and manager only |
| What happens | The page recalculates on screen, on the server, with exact fractions | The campaign's scenario changes; every ward target is recalculated and saved |
| What is saved | Nothing; refreshing returns to the set scenario | `turnout_scenario`, who set it and when; `votes_needed` on every target |
| On screen | Banner: "Previewing High turnout. Your team is working to Expected. Nothing is saved." with Back and Use this scenario | Confirmation listing the seat target change and the number of wards affected |
| Record | None | Audit entry with the old and new scenario and both seat targets |
| Team | Unaffected | Each coordinator and mobilizer whose target changed gets an inbox note (and a push notification once `CD-R6` R6-2 is built) |

Supporters recorded never change with the scenario; only the targets, and so the progress
percentages, do.

---

## 7. Rules

1. Targets are never typed in; they are calculated (T6).
2. Every target shows its reliability; figures that use 2017 data show the caution.
3. A change of scenario or turnout is audited with who changed it and when.
4. Ward targets always add up exactly to the seat target.
5. Previewing a scenario never changes saved targets (T12).
6. Only the candidate or the manager can set a scenario; setting it recalculates every ward,
   records an audit entry and notifies everyone whose target changed.
7. Everyone except the candidate, manager and comms sees only the set targets.
8. The targets page always shows which scenario the team is working to.
9. Setting a scenario within 30 days of the election shows a warning in the confirmation step;
   it does not block the change.

---

## 8. Out of scope

The 2027 register (a later release, once IEBC publishes it); ward-level strength weighting;
by-election results; party primary results; opinion polls.

---

## 9. Release plan

| Ticket | Work | Implements | Done when |
|---|---|---|---|
| R7-0 Data | Kura254 file and `SOURCE.md` in `backend/data/history` | T4; 3.1 | File and checksum in the project |
| R7-1 Tables and loader | `elections`, `contests`, `contest_candidates`; migration; `seed-results` command; quality rules; tests | T4; 3.2, 3.3 | All 6,069 contests load, none unlinked; Laikipia figures match the published results |
| R7-2 Seat model | `win_model.py`: share, turnout, scenarios, two-candidate test, typical winner, fallbacks, exact fractions | T1, T2, T3, T8, T10, T11; 4 | Laikipia and Marsabit give every figure in 4.1 and 4.2 |
| R7-3 Target engine | Seat target, ward weights and largest-remainder rounding, reliability, new fields, recalculation migration | T5, T6, T7, T9; 4, 5 | Every existing campaign's targets are recalculated; ward targets add up exactly to the seat target; the Laikipia ward table in 4.1 is reproduced |
| R7-4 API and screens | Targets page, preview and set routes, permission, confirmation, team notices, field app ward card, setup preview, strategy slides | T12; 6, 6.1, 7; `M3` | The Laikipia demo shows 67.86%, the three scenarios and the ward table. Previewing High saves nothing and a refresh returns to Expected. A mobilizer can neither preview nor set. Setting High records an audit entry, notifies the affected wards and the ward targets add up to 128,640 |
| R7-5 MCA polling centres | Share-out below ward level for MCA seats | T5 | An MCA campaign's centre targets add up to its seat target |
| R7-6 Documentation | `SYSTEM.md` section on targets; Vercel replaces Fly.io throughout | | No reference to 50% + 1 as the target remains |

---

## 10. Risks and open questions

| ID | Item | Proposed handling | Resolved |
|---|---|---|---|
| Q1 | Kura254 names no licence | Credit the source; ask the maintainers for written permission before commercial sale | [ ] |
| Q2 | 2017 data was withdrawn by IEBC | Used only in the typical winner and the high scenario, with a caution | [ ] |
| Q3 | Boundary changes before 2027 | Contests link to today's areas by code; re-check after any IEBC boundary review | [ ] |
| Q4 | A landslide in 2022 sets a high bar in an open seat | The typical winner is shown beside the target so the campaign sees both | [ ] |
| Q5 | The register grows by 2027 | Targets on the 2022 register are a minimum; load the 2027 register when IEBC publishes it (T9) | [ ] |
| Q6 | A scenario change late in the campaign unsettles the team | Warning in the confirmation step within 30 days of the election (rule 9); revisit after the pilot | [ ] |

---

## 11. Implementation tracker

| Ticket | Status | Branch or PR | Contract updated (and mockup checked) | Tests pass |
|---|---|---|---|---|
| R7-0 | Done | `targets-history` | n/a | n/a |
| R7-1 | Done | `targets-history` (migration re-based after `president`) | n/a | [x] 7 new tests |
| R7-2 | Done | `targets-history` | n/a | [x] `test_win_model.py`: every figure in 4.1 and 4.2 |
| R7-3 | Done | `targets-history` | [x] `GET /api/targets/` reads `ward_weight`, `reliability`; turnout no longer written | [x] Laikipia ward table, High sums to 128,640 |
| R7-4 | Done | `demo-comms` | [x] `M3` (preview, set, notices under the bell, Your ward card) | [x] `test_target_scenarios.py` |
| R7-5 | Done (centres weighted by register: the results file has no centre results) | `demo-comms` | n/a | [x] centre targets add up to the seat target |
| R7-6 | Done | `demo-comms` (SYSTEM.md, DEPLOY.md for Vercel; fly.toml removed; "win number" wording replaced) | n/a | n/a |

Status values: Not started, In progress, In review, Done.

R7-3 notes: the recalculation runs in `campaign-crm seed-results` (the results tables are empty
when the migration runs), and the refresh route reworks one campaign. A seat with no usable 2022
race keeps the majority line as its floor. With no results loaded at all, targets fall back to
50% + 1 of the register at each county's turnout, marked "Proxy". MCA centres share the seat
target by register until R7-5. The per-ward turnout slider is removed (T6); R7-4 adds the
scenario buttons.

Known gaps after the R7-3 critic pass (for R7-4 or later):
- A county whose 2017 August presidential result is excluded (Kisumu) gets no High adjustment,
  so High equals Expected there, without a flag.
- The national "Projected votes cast" in `services/strategy.py` adds each target's register at
  its stored 2-decimal turnout, so it can differ from `P` by a few votes.
- The typical winner rescales its weights over the years present; section 2 does not say so.
- Closed campaigns are not reworked by `seed-results`.
- Refresh targets is not serialised with setting a scenario; a refresh at the same moment as a
  set can make the set's "units changed" count off by the refresh's changes.
- Notices are per login, not per campaign (one installation holds one campaign).
- An MCA mobilizer recorded on the ward but on no centre sees no ward card.

---

## 12. Amendments

| ID | Date | Change | Sections |
|---|---|---|---|
| A1 | 22 November 2026 | The majority line is a lower limit only in two-candidate seats; in crowded seats it is shown for reference (T3) | 1, 2, 4 |
| A2 | 23 November 2026 | Kura254 adopted as the single source for all three years; tables simplified to `elections`, `contests`, `contest_candidates`; T6 reworded; R7-0 and R7-1 recorded as done | 1, 3, 5, 9, 11 |
| A3 | 23 November 2026 | Target set at the 2022 winner's share instead of the weighted share, which becomes the "Typical winner" reference and fallback (T1, T2, T8); 2022 register only (T9); three turnout scenarios (T10); ward share-out by 2022 valid votes (T5); exact fractions (T11); worked examples redone | 1, 2, 3, 4, 5, 6, 8, 9, 10 |
| A4 | 23 November 2026 | Trying a scenario is a preview; setting it is a separate, confirmed, audited and notified step for candidate and manager only (T12); preview and set routes, permission, field app ward card, rules 5 to 9, Q6; mockup `M3` added | Header, 1, 5, 6, 6.1, 7, 9, 10, 11 |
