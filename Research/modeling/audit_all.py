"""Run every validator against its recorded baseline and refuse to regress.

    ./venv/bin/python Research/modeling/audit_all.py            # all seventeen (about seven minutes)
    ATLAS_PORT=8152 ./venv/bin/python Research/modeling/audit_all.py   # from a second checkout, on its own port
    ./venv/bin/python Research/modeling/audit_all.py --quick    # skip the ones that need a browser

A build or a publish calls this and stops if a check moved backwards.

The baselines are not all zero and should not be: a known, stated disagreement belongs in the
baseline with a note. The rule is that none may move BACKWARDS. When one legitimately improves,
tighten the baseline IN THE SAME COMMIT, so the ratchet turns one way only.

The browser checks drive headless Chromium through Playwright, which lives in the Modeling Studio
venv; they need the dev server, which this script starts if nothing is listening on 8150.

SKIP_AUDIT=1 overrides. Deliberately awkward.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
PY = os.path.join(ROOT, "venv", "bin", "python")
STUDIO = os.path.expanduser("~/Modeling Studio")
SPY = os.path.join(STUDIO, ".venv", "bin", "python")
PORT = int(os.environ.get("ATLAS_PORT", "8150"))   # a second checkout (a git worktree) serves and audits itself on its own port
M = lambda f: os.path.join(HERE, f)
B = lambda f: os.path.join(ROOT, "build", f)

# name, commands (each run in order; the LAST one reports), baseline, needs a browser?, what it catches.
# A baseline of {"failures": 0} means "the command must exit 0". Every other metric: lower is better.
CHECKS = [
    ("frames", [[PY, B("test_frames.py")]], {"failures": 0}, False,
     "a source converted into the canonical frame shifted, flipped or mis-registered"),
    ("app-math", [["node", B("test_app_math.mjs")]], {"failures": 0}, False,
     "Sun and Moon against the almanac and against NASA EPIC's own vectors; projection and camera round trips"),
    ("shaders", [[PY, B("check_shaders.py")]], {"failures": 0}, False,
     "a shader that does not compile (the black canvas with working panels)"),
    ("selftests", [[PY, "-W", "ignore", M("epic_compare.py"), "--selftest"], [PY, "-W", "ignore", M("epic_clearsky.py"), "--selftest"], [PY, "-W", "ignore", M("cloud_texture.py"), "--selftest"],
                   [PY, M("audit_ice.py"), "--selftest"], [PY, M("audit_population.py"), "--selftest"], [PY, "-W", "ignore", B("cloud_grain.py"), "--selftest"],
                   [PY, M("audit_water.py"), "--selftest"], [PY, M("audit_lakeice.py"), "--selftest"], [SPY, M("audit_gpu.py"), "--selftest"],
                   [PY, "-W", "ignore", M("audit_closewater.py"), "--selftest"], [PY, B("units.py")],
                   [PY, "-W", "ignore", M("s2_transfer.py"), "--selftest"], [PY, "-W", "ignore", M("audit_closecolour.py"), "--selftest"], [PY, "-W", "ignore", M("closewater_witness.py"), "--selftest"],
                   [PY, "-W", "ignore", M("cloud_budget.py"), "--selftest"]],
     {"failures": 0}, False, "an audit that has stopped measuring what it says it measures"),
    # The water mask against ETOPO 2022's ocean-connected sea, north of 60 S (register A5). Before the mask was
    # rebuilt from a coastline (2026-11-10) these were 5.27, 0.11 and 460: Blue Marble paints every shelf sea in a
    # colour of its own, and "sea is wherever the picture is fill" classed the bright ones as land. What is left
    # is the coast itself at 5 km (fjords, lagoons, polders); the register file lists the patches.
    # Sixth round (2026-11-10): rivers. rivers_undrawn is new: the mean share of nine wide reaches' centrelines
    # that the mask does not draw as water (0.996 before MODIS's river water was added, 0.131 after; the Parana
    # at 50% and the Congo at 71% are the rest: channels narrower than half a cell between their islands).
    # sea_as_land tightened 0.309 -> 0.287: river mouths that were land.
    ("water", [[PY, M("audit_water.py"), "--json"]], {"sea_as_land_Mkm2": 0.287, "land_as_sea_Mkm2": 0.568, "worst_patch_kkm2": 12.1, "rivers_undrawn": 0.131}, False,
     "sea drawn as land or land as sea: the water mask drifting from the coast"),
    # Lake ice against 174 lakes' own freeze and thaw records (NSIDC G01377). test_*: the model on the half of
    # the lakes it was not fitted to (given each lake's recorded depth where there is one). shipped_*: what the
    # field draws, at the lakes that are THEMSELVES water in the atlas's mask.
    # THE SHIPPED SCORE CHANGED MEANING on 2026-11-10 (fifth round) and earlier numbers do not compare. It used
    # to take every lake in a cell with ice (106 of them); but the ice in a cell is the ice of whatever body the
    # mask draws there, and for a pond beside Lake Ontario that is Lake Ontario. Once lakes freeze by their depth
    # that scores the wrong lake. On the 23 lakes that are themselves drawn: release 1.1 (no lake model) 120 days
    # a year out, release 1.2 (no depth) 17.2 and 0.065, now 12.7 and 0.048. undrawn = the other 151.
    ("lake-ice", [[PY, "-W", "ignore", M("audit_lakeice.py"), "--json"]],
     # Sixth round: the rivers brought the lakes strung along them into the mask, so 25 recorded lakes are now
     # themselves water (23 before) and what is drawn is 11.6 days out (12.7). Tightened.
     {"lakeice_test_mae": 0.0385, "lakeice_test_days": 9.8, "lakeice_shipped_mae": 0.0443, "lakeice_shipped_days": 11.6, "lakeice_undrawn": 149}, False,
     "lake ice drifting from the lakes' own records"),
    # Rebuilt from NSIDC's 720 monthly grids (register C1). The edge is PLACED so the extent matches NSIDC's
    # mean, so these three are a regression guard, not evidence; the evidence is the per-year check the
    # build asserts (fields_climate.step_ocean) and audit_ice.py --peryear. Ice AREA is not solved for:
    # mean concentration inside the edge is diluted by open years, up to 15.5% under in Antarctic February.
    ("sea-ice", [[PY, M("audit_ice.py"), "--json"]],
     # RE-SET 2026-11-10 (fourth round) with the new water mask: arctic 0.1 -> 0.2 and mean 0.0 -> 0.1, BACKWARDS by
     # a rounding step. The edge is solved cell by cell and lands within 0.16% of NSIDC's mean extent in the worst
     # month (the build asserts 0.5%); the coast now has more cells and the solver's last step is coarser there.
     # Area improved, 15.5 -> 15.3.
     {"arctic_max_over_pct": 0.2, "antarctic_max_over_pct": 0.0, "mean_abs_pct": 0.1, "area_max_under_pct": 15.3}, False,
     "sea-ice extent or area drifting from the NSIDC Sea Ice Index"),
    # 26 units differ by more than 10% (vintage, small islands, city states); register F2 lists them.
    ("population", [[PY, M("audit_population.py"), "--json"]], {"units_off_10pct": 26, "total_err_pct": 0.37}, False,
     "the population field against World Bank national totals"),
    # Names of states, as the label layer actually placed them, on 24 framings and in the sheet's two insets
    # (register F1). The count of states is 198 (193 UN members plus Vatican, Taiwan, Kosovo, N. Cyprus,
    # Somaliland). overlaps, under_9px, misplaced (a name mostly on another country, tested against geometry),
    # hit_wrong and under_panel must stay ZERO: coverage bought with any of them is not coverage.
    # THE COUNT CHANGED MEANING on 2026-11-10 (third round), and the numbers before it do not compare. Names
    # are no longer placed under the panels, and a state whose own ground is under a panel is counted `hidden`,
    # not unnamed. By the old count the whole-Earth sheet named 129, 22 of them under the dashboard where no
    # one could read them. By the new one it named 106 of 176 in view and now names 125 of 177 (107 on the map,
    # 18 more in the insets). Of all 198: 73 unnamed, 21 of those hidden.
    # Land or water inside the streamed window (registers A12, A15), at 23 places.
    # THE SCORE CHANGED MEANING on 2026-11-11 (ninth round) and the numbers before it do not compare. The page's
    # source is now JRC Global Surface Water itself (its map tiles), which until then was this check's witness; the
    # witness is ESA WorldCover 2021 (10 m, class 80). By the old witness release 1.6's rule was 2.50% wrong; by the
    # new one it is 3.21% (rule_wrong_pct: it is still the stand-in polewards of the record), NASA's mask alone
    # 5.58%, the shipped 5 km field 11.2%, and the tiles 2.19%. tiles_vs_file_pct is the FRAME check: the tiles
    # taken onto the grid against the record's own 30 m file, the worst place. Needs reference/closewater
    # (closewater_fetch.py, closewater_fetch.py --jrc, closewater_witness.py).
    ("close-water", [[PY, "-W", "ignore", M("audit_closewater.py"), "--json", "--register"]],
     {"wrong_pct": 2.19, "iou_short_pct": 18.3, "worse_than_mask": 0, "manhattan_false_pct": 0.4, "tiles_vs_file_pct": 1.28, "rule_wrong_pct": 3.21}, False,
     "close in, water drawn where the land is or land where the water is; the water record read in the wrong frame"),
    # Close in, is a grey thing grey (register A13)? Sentinel-2's own table (s2_transfer.py) against the shader's
    # constants, and what the join does to ground Sentinel-2 photographs grey, at eleven city places: 5.2% off grey
    # in scene light (release 1.6: 48.4%, the worst place 66%). air_drift and table_drift are tolerances of one
    # thousandth (the constants are printed to three places): retune the shader's air and forget the table, and
    # air_drift fails. Needs reference/s2global (s2_transfer.py --fetch) and reference/closewater.
    ("close-colour", [[PY, "-W", "ignore", M("audit_closecolour.py"), "--json"]],
     {"air_drift_e3": 1.0, "table_drift_e3": 1.0, "fit_outside_pct": 22.8, "grey_cast_pct": 5.2, "grey_cast_worst_pct": 7.3, "mean_shift_pct": 1.1}, False,
     "close in, grey ground drawn in colour; the Sentinel-2 table drifting from the shader's own air"),
    ("labels", [[SPY, M("audit_labels.py"), "--selftest"], [SPY, M("audit_labels.py"), "--json", "--port", str(PORT)]],
     {"sheet_states198_unnamed": 52, "globe_states198_unnamed": 59, "regional12_states198_unnamed": 300, "regional6_states198_unnamed": 38,
      "overlaps": 0, "under_9px": 0, "misplaced": 0, "hit_wrong": 0, "under_panel": 0, "sheet_drag_flips": 0, "sheet_zoom_in_losses": 4}, True,
     "states losing their names, or names overlapping, shrinking below 9 px or landing on the wrong country"),
    # Eight NASA EPIC frames, software GL. Register A1 holds the per-frame table and what each number means.
    # limb_err rose from 0.063 to 0.103 in the build round and that is a CANCELLATION, recorded in A1: the old
    # frame matched the ring-to-centre ratio because the whole outer disc was 5-15 levels dim. disc_err is the
    # measure that sees it (9.3 before, on the same renders).
    ("epic", [[SPY, M("epic_render.py"), "cur"], [PY, "-W", "ignore", M("epic_compare.py"), "--tag", "cur", "--json", "--no-figures"]],
     # RE-SET 2026-11-10 (second build round), five of them BACKWARDS, on purpose and written down in MODEL-GAPS
     # (APPLIED, second build round): lum_err 1.94 -> 2.47, white_err 0.015 -> 0.018, limb_err 0.103 -> 0.107,
     # ocean_rgb_err 4.9 -> 5.1, land_rgb_err 13.1 -> 13.8. The old values came from a cloud opacity curve fitted
     # to these very photographs. Cloud light now comes from ISCCP and is confirmed by VIIRS; EPIC is no longer
     # what it is tuned to.
     # RE-SET AGAIN 2026-11-10 (third round), in two steps, both in MODEL-GAPS (APPLIED, third round).
     # 1. THE INSTRUMENT. to_common() shrank both pictures 2.3 times by reading single points, and averaged in
     #    display values; it now averages light over each common pixel. The SAME renders as the last baseline
     #    (tag r9) score on it: 2.63, 1.68, 0.021, 4.17, 0.105, 5.7, 13.1, halo 0.20, glint 0.11.
     # 2. THE MODEL (cloud grain; sheet light from ISCCP). Against those: contrast 1.68 -> 1.54, disc 4.17 -> 4.13
     #    and ocean 5.7 -> 5.0 better; lum 2.63 -> 2.66, white 0.021 -> 0.027, limb 0.105 -> 0.118, land 13.1 -> 13.2
     #    and glint 0.11 -> 0.13 WORSE. Classified TRUE, small: sheet cloud was a third brighter than ISCCP says
     #    (and 0.12 brighter than VIIRS off Peru); at ISCCP's figure the two December frames, already 2-6 points
     #    short of EPIC's white share, are a point or two shorter. The old excess was covering for that.
     # RE-SET 2026-11-10 (fourth round: the water mask). The mask is in the scene and in this audit's own sorting of
     # pixels into sea and land, so both moved. Better and tightened: lum 2.66 -> 2.62, contrast 1.54 -> 1.53, white
     # 0.027 -> 0.026, ocean 5.0 -> 4.7, land 13.2 -> 13.1. BACKWARDS by a last digit: disc 4.13 -> 4.16, limb 0.118 ->
     # 0.119 (every frame's ring-to-centre ratio rose 0.001-0.002: the Arctic shelf seas at the limb are sea now, with
     # the sea's sky reflection at a grazing angle), glint 0.13 -> 0.14 (the pixels counted as water round the
     # specular point changed by 0-22 of about 5000). Classified CANCELLATION: none is a change to the light model.
     # RE-SET 2026-11-10 (fifth round: cumulus over land). A fifth of the "all other cloud" light over heated wet
     # land is drawn as cumulus fields (LAND_CU_SHARE, fitted to this audit's own clear-ground medians over the
     # Amazon and the Congo; VIIRS is its check). Better and tightened: land 13.1 -> 11.9, limb 0.119 -> 0.118, glint
     # 0.14 -> 0.13. BACKWARDS, on purpose: contrast 1.53 -> 1.85, lum 2.62 -> 2.67, white 0.026 -> 0.028, disc 4.16 ->
     # 4.17. Classified TRUE. The disc's contrast falls by up to one level in six of eight frames because light
     # moves from bright clusters to thin fields. Taken for what it buys. EPIC's four clear-forest medians, atlas
     # minus EPIC, before and now: Amazon December -31 -> -13, Congo March -13 -> +6, Amazon March -5 -> +9, and
     # Congo December +10 -> +22, which is WORSE (sum of sizes 59 -> 50). And at 2 km VIIRS's Amazon scene now
     # matches in mean light (0.167 against 0.171).
     # RE-SET 2026-11-11 (tenth round: the Southern Ocean's cloud). Two changes, both in the register (B1) with their
     # tables. (1) Sheet cloud of a middling share is weather and is drawn through the cloud photograph's systems, not
     # as a veil over everything. (2) The slant that closes the gaps in broken cloud is for heaped cloud only; layered
     # cloud gets none, and a Sun-side gain of its own (CLOUD_OPP_FLAT, fitted to the storm belts' level).
     # Better and tightened: lum 2.67 -> 2.31, contrast 1.85 -> 1.64, white 0.028 -> 0.018, disc 4.17 -> 3.74, limb
     # 0.118 -> 0.109, ocean 4.7 -> 4.6. December's white share, EPIC / atlas: 23 / 15 -> 17 and 22 / 18 -> 21.
     # BACKWARDS, two:
     #   glint 0.13 -> 0.16. ONE frame, 21 December 17:16 (1.72 -> 1.90 where EPIC has 1.51); the other four moved by
     #     0.00-0.04. Its specular point lies under the margin of the Peruvian deck, where a sheet share of 0.3-0.45
     #     was a veil that dimmed the glint. Classified CANCELLATION: in the four frames whose glint is under clear
     #     sky the atlas's is 0.00-0.14 UNDER EPIC's, and the veil was hiding one that is not too strong.
     #   land 11.9 -> 12.0. Classified TRUE, small: cloud over cool ground reads brighter from the Sun's side now
     #     (the Sahara and Arabia in December, Australia in September: 0.4-0.9 each); the other eight values moved
     #     by 0.1 or less.
     # By frame, 47 measures moved past a tolerance: 32 better, 15 worse. The worse ones not above: p50 in three
     # frames (1-3 levels: light gathered into systems leaves the middle of the distribution darker; December's
     # median was 5-7 short and is 8), 21 June 22:35's top (p95 185 -> 192 where EPIC has 186, contrast 45 -> 47 for
     # 44: the North Pacific's sheet share is weather too, and that day EPIC's was thinner), and the two December
     # discs (disc 4.6 -> 5.1, 4.7 -> 5.4; clear ocean 2.7 -> 5.1, 3.2 -> 3.8: the darkest fifth of December's water
     # is 2-4 levels darker than EPIC's without the veil). TRUE, each of them; taken for the white share and the
     # spread (the Southern Ocean's standard deviation in December: EPIC 41-42, the atlas 31 -> 38-41).
     # RE-SET again in the tenth round (cumulus read along the wind; the grain is at 37% of its weight at the centre
     # of these discs, 6 km a pixel). Ocean 4.6 -> 4.5. BACKWARDS: land 12.0 -> 12.3, and by a last digit lum 2.31 ->
     # 2.32, contrast 1.64 -> 1.65, disc 3.74 -> 3.75, limb 0.109 -> 0.111. Land is the forest medians, atlas minus
     # EPIC in luminance: Congo March +6.5 -> +7.2, Amazon March +9.0 -> +9.5, Congo December +22.7 -> +23.5, Amazon
     # December -13.5 unmoved. Classified TRUE, small, and it is the fade: where two layouts of the cumulus grain meet
     # the old cross-fade covered 0.257 of the sky when asked for 0.3; the new one (rankMix1) covers what is asked,
     # so cumulus over wet land sends back a little more. LAND_CU_SHARE was fitted through the old fade and is left
     # as it is: it should come from data, not be fitted a second time (register B1).
     {"lum_err": 2.32, "contrast_err": 1.65, "white_err": 0.018, "disc_err": 3.75, "limb_err": 0.111, "ocean_rgb_err": 4.5,
      "land_rgb_err": 12.3, "halo_err": 0.2, "glint_err": 0.16, "epic_shift_px": 2}, True,
     "the lit globe moving away from the photograph: exposure, contrast, cloud, the disc profile, ocean, ground, glint"),
    # The ground alone: clouds off, against a cloud-free composite of about a hundred EPIC frames (register A7).
    # Needs reference/epic/clearsky (epic_clearsky.py --fetch, 300 MB). instrument_bias is the numpy copy of the
    # shader against the shader's own render: if it grows, shader_model.py has drifted and nothing here means anything.
    ("clear-sky", [[SPY, M("epic_render.py"), "clr", "air,daylight,ice"], [PY, "-W", "ignore", M("land_transfer.py"), "--json"]],
     # Sixth round, RE-SET 0.7 -> 0.8 on clearsky_land_bias, and it is the instrument's population, not the picture:
     # this audit sorts pixels into land and water by the water mask, and the mask gained rivers and the lakes along
     # them, so 825 part-water pixels of 168,716 left the land set. The SAME renders scored with the old mask for
     # sorting give 0.7; with the new one 0.8. Mean absolute difference and the instrument check did not move.
     {"instrument_bias": 1.1, "clearsky_land_abs": 4.9, "clearsky_land_bias": 0.8}, True,
     "the cloud-free ground moving away from EPIC's, or the audit's copy of the shader drifting from the shader"),
    # Where the cloud's light is and how it is seen (register B1; cloud_budget.py; tenth round). It reads the `cur`
    # renders the epic check has just made. so_sheet_gap: the sheet light the shader draws at twelve places of the
    # summer Southern Ocean against the room 48 VIIRS scenes leave for it, seen straight down (0.070 against 0.065).
    # storm_level_err, storm_limb_err: the atlas's light over EPIC's across the two storm belts (45-65 degrees), less
    # one, at view cosines 0.5-0.9 and 0.3-0.5. Before the slant was made the heaped cloud's alone: 0.005 and 0.143.
    # tropics_level_err: the same for 8 S - 8 N. It was 0.066 and is 0.084, BACKWARDS and recorded: the sheet share
    # of the equatorial cold tongues is weather now and draws a little more light. TRUE, small.
    # Needs reference/gibs_clouds/so_survey (cloud_budget.py --survey --fetch, 6 MB) and the ISCCP cache.
    ("cloud-light", [[PY, "-W", "ignore", M("cloud_budget.py"), "--json"]],
     {"so_sheet_gap": 0.005, "storm_level_err": 0.010, "storm_limb_err": 0.048, "tropics_level_err": 0.084}, True,
     "the Southern Ocean's sheet light drifting from what VIIRS leaves room for; layered cloud brightening toward the limb"),
    # Cloud at the zoom floor: five regimes at 2 km a pixel against three VIIRS days each (register B1). Each
    # number is how far the atlas sits OUTSIDE the day-to-day spread of the photographs, summed over the
    # regimes: 0 would mean indistinguishable by that measure. Needs reference/gibs_clouds (cloud_texture.py
    # --fetch, 5 MB). Before the cloud-kinds round these were 1.005, 0.453, 0.558, 0.078; after it 0.621, 0.052,
    # 0.423, 0.026. Third round (cloud grain from real scenes): three better, and CONTRAST BACKWARDS, 0.026 -> 0.088,
    # re-set on purpose. By scene: North Atlantic and SE Pacific now inside the photographs' spread; Amazon, Congo
    # and trades outside it by 0.02-0.03 each. Congo is PRE-EXISTING (0.14 too much light there in both states;
    # resolved pieces show it where flat grey ones hid it). Amazon and trades are TRUE: fewer, larger, brighter
    # pieces than the real fine cumulus. Amazon's size spectrum also went backwards (bands 0.38 -> 0.53). In B1.
    # Fifth round (a land-cumulus grain; a fifth of wet-land cloud light as cumulus fields; grains in two rows):
    # bands 0.226 -> 0.152, cover 0.253 -> 0.159, contrast 0.088 -> 0.059 better. DIRECTION BACKWARDS, 0.032 -> 0.078,
    # re-set on purpose: the trades went from 0.06 to 0.10 off (floor 0.03). The cumulus grain has little direction
    # of its own (0.03-0.07 where VIIRS's trades have 0.13), and which part of the tile falls on a scene moved when
    # the texture took a second row; scores here carry about 0.05 of that. TRUE: cumulus does not line up along
    # the wind (B1).
    ("cloud-texture", [[SPY, M("cloud_scenes_render.py"), "cur"], [PY, "-W", "ignore", M("cloud_texture.py"), "--tag", "cur", "--json"]],
     # Sixth round: sizes 0.152 -> 0.122 and contrast 0.059 -> 0.058 with no change to the cloud. The Amazon and
     # Congo scenes now have rivers in them, and the cumulus rank is mixed by the water fraction. Tightened, as the
     # rule says; it is within the 0.05 a scene that the tile layout alone is known to move this audit by.
     # Tenth round (weather sheets through the photograph). COVER 0.159 -> 0.167 and CONTRAST 0.058 -> 0.070, BACKWARDS,
     # re-set on purpose. Cover: the North Atlantic scene, 0.12 -> 0.13 off (its sheet share of 0.15 now draws 0.004 of
     # light; TRUE, small). Contrast: the SE Pacific deck, 0.012 -> 0.030 off (floor 0.018): the deck's margins, where
     # the share falls below a half, are the photograph's broken systems now and not an even pavement. TRUE. Sizes
     # and direction did not move.
     # Two scenes more, scored APART so that the four sums above keep their history: the Southern Ocean in summer
     # (Indian and Pacific sectors, three days each, rendered without the air). socean_light_excess: mean reflectance
     # outside the photographs' day-to-day spread (0.000 before this round, 0.025 now: the Pacific scene carries
     # 0.083 more light than VIIRS's three days against a spread of 0.058; the Indian one 0.068 less, inside its
     # 0.089). socean_cover_excess 0.039 -> 0.033. NOT scored and wrong: both scenes are half again as contrasty as
     # VIIRS at 2 km (0.30 against 0.20-0.23), before and after; in the register.
     # Tenth round, second change (cumulus along the wind: earth.frag.glsl streetAt). The two cumulus grains are read
     # with the tile's east along the shipped wind and pressed together across it, cell by cell. Better and
     # tightened: sizes 0.122 -> 0.040, direction 0.078 -> 0.021, contrast 0.070 -> 0.033, and a new number,
     # street_off_wind_deg: how far the axis of the 4-32 km structure lies from the wind's, mean of the trades and
     # the Amazon, 36.8 -> 11.6 degrees (the trades 63 -> 8; VIIRS's own days there are 10, 41 and 1 off).
     # COVER BACKWARDS, 0.167 -> 0.204, re-set on purpose: the Congo scene, 0.15 -> 0.19 off (floor 0.05), its mean
     # light 0.308 -> 0.323 against VIIRS's 0.216. PRE-EXISTING and now plainer: the scene carried 0.09 too much
     # light before (ISCCP's April mean against three afternoons), and the cross-fade between layouts no longer
     # loses a seventh of the cover asked for (see the epic note). By scene, also worse: the North Atlantic's
     # direction 0.05 -> 0.07 off (floor 0.05; its cumulus lies along the westerlies now and the scene as a whole
     # is less one-directional, 0.03 for VIIRS's 0.11: TRUE), the SE Pacific's sizes 0.42 -> 0.46 (floor 0.45).
     {"texture_bands_excess": 0.04, "texture_aniso_excess": 0.021, "texture_cover_excess": 0.204, "texture_contrast_excess": 0.033,
      "street_off_wind_deg": 11.6, "socean_light_excess": 0.022, "socean_cover_excess": 0.031}, True,
     "close-in cloud drifting from real cloud's grain, direction, cover or contrast"),
    ("visual", [[SPY, os.path.join(STUDIO, "tools", "frame_baseline.py"), "check", "--project", ROOT]], {"failures": 0}, True,
     "any of the six canonical frames changing without a recorded reason (Research/baselines/FRAME-LOG.md)"),
    # The same six frames on the machine's own GPU (ANGLE Metal) against the accepted software frames, and the one
    # GL path the frames do not reach (register G7). gpu_broken: frames that are blank, errored or beyond what two
    # rasterisers differ by, plus 1 if the lights-into-alpha write is wrong. The other two are the worst frame's
    # difference: measured 0.73 levels and 0.59% of pixels on 2026-11-10 (Apple M5 Ultra). Those two are printed and
    # written to REGISTER-gpu.md but are NOT ratcheted here: hardware frames are not the same bits after a system
    # update. The audit gates them itself, by a tolerance set five to ten times above the measurement ("broken" is
    # tens of levels), and counts a frame beyond it in gpu_broken.
    # It runs AFTER "visual", so the software frames it compares against are the accepted ones.
    ("gpu", [[SPY, M("audit_gpu.py"), "--json", "--port", str(PORT)]], {"gpu_broken": 0}, True,
     "the page failing on real hardware while every software-GL audit passes (a seventeenth sampler, a driver's stricter GLSL)"),
]
TOL = 1e-9


def listening(port):
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main():
    if os.environ.get("SKIP_AUDIT") == "1":
        print("SKIP_AUDIT=1 - validators skipped. Say so out loud, and say why.")
        return 0

    quick = "--quick" in sys.argv
    failed, server = [], None
    if not quick and not listening(PORT):
        server = subprocess.Popen(["/usr/bin/python3", B("serve.py"), str(PORT)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            if listening(PORT):
                break
            time.sleep(0.1)
        else:
            print("  ERROR could not start the dev server; the browser checks cannot run")
            return 1
    try:
        for name, cmds, baseline, browser, catches in CHECKS:
            if quick and browser:
                print(f"  skip  {name:11} (needs a browser)")
                continue
            t0 = time.time()
            r = None
            for cmd in cmds:
                r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
                if r.returncode != 0:
                    break
            if list(baseline) == ["failures"]:
                got = {"failures": 0 if r.returncode == 0 else 1}
                if r.returncode != 0:
                    tail = (r.stdout + r.stderr).strip().splitlines()[-12:]
                    failed.append((name, "failed:\n      " + "\n      ".join(tail)))
                    print(f"  FAIL  {name:11} exit {r.returncode}")
                    continue
            else:
                # A check that cannot report its numbers has FAILED. Silence is not a pass.
                got = _parse(r.stdout) if r.returncode == 0 else None
                if got is None:
                    failed.append((name, f"could not run or produced no parsable result: {(r.stderr or r.stdout).strip()[-400:]}"))
                    print(f"  ERROR {name:11} no result")
                    continue
            regressed = [k for k, v in baseline.items() if _worse(got.get(k), v)]
            better = [k for k, v in baseline.items() if got.get(k) is not None and got[k] < v - TOL]
            if regressed:
                failed.append((name, "moved backwards on " + ", ".join(f"{k}: {got.get(k)} (baseline {baseline[k]})" for k in regressed)))
                print(f"  FAIL  {name:11} {regressed}")
            else:
                shown = {k: got.get(k) for k in baseline}
                note = f"   <- improved on {better}: tighten the baseline in this commit" if better else ""
                print(f"  ok    {name:11} {shown}  ({time.time() - t0:.0f}s){note}")
    finally:
        if server:
            server.terminate()

    if failed:
        print("\nREFUSING TO PUBLISH:")
        for name, why in failed:
            print(f"  {name}: {why}")
        return 1
    print("\nall validators at or better than baseline")
    return 0


def _parse(stdout):
    for line in reversed(stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def _worse(got, base):
    """Lower is better for every metric here."""
    if got is None:
        return True
    return got > base + TOL


if __name__ == "__main__":
    sys.exit(main())
