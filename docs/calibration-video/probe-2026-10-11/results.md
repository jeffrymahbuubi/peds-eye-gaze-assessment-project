# Calibration probe P1-P3 (2026-10-11, no camera attached)

Target: Gazepoint.exe (PID 20576, `C:\Program Files (x86)\Gazepoint\Gazepoint\bin64\Gazepoint.exe`) on TCP 4242.
Script: `probe.py`; raw timestamped log: `raw_log.txt` (perf_counter_ns, ms since script start);
screenshots: `screen_A_default_mid.png`, `screen_B_fast_mid.png`.
Two calibrations were run (A: Control's current timing, B: Grid 3-fast). Note: the analysis step of the
script crashed after the run (a bug in my script, not in Control); all numbers below come from `raw_log.txt`.

Originals read by GET before the probe: CALIBRATE_SHOW STATE=0, CALIBRATE_DELAY 0.50, CALIBRATE_TIMEOUT 1.50
(not the 1.25 s the SPEC assumed), CALIBRATE_RESULT_SUMMARY AVE_ERROR=1477.47 VALID_POINTS=0 (retained).
All three were set back and confirmed by GET at the end (SHOW 0, DELAY 0.50, TIMEOUT 1.50).

| Probe | Result | Evidence |
|---|---|---|
| P1 hidden-window flow | PASS (flow); quality not testable | SHOW=0 ACKed; 5 x CALIB_START_PT + 5 x CALIB_RESULT_PT + 1 CALIB_RESULT in both runs. No Control calibration window visible in either mid-run screenshot (desktop showed only the terminal). VALID_POINTS=0, AVE_ERROR=1510.04, all LV/RV=0 and LX/LY/RX/RY=0 (no camera: meaningless). |
| P2 order/values | PASS | ADDPOINT ACKs list X1..X5 in sent order. CALIB_START_PT PT=1..5 came as (0.1,0.1) (0.9,0.9) (0.9,0.1) (0.1,0.9) (0.5,0.5) = TL, BR, TR, BL, C exactly. CALIB_RESULT CALX1..5/CALY1..5 same. CALX/CALY are 4 decimals in CAL_PT records, 5 in CALIB_RESULT. |
| P3 timing | PASS (with a +10..70 ms bias) | A (0.5+1.5=2000 ms): 2050.0, 2057.1, 2068.5, 2052.8, 2057.5 ms (mean 2057, +50..69). B (1.8+0.3=2100 ms): 2168.9, 2121.2, 2151.0, 2149.8, 2111.5 ms (mean 2140, +12..69). |

Other timings:
- CALIBRATE_START sent to first CALIB_START_PT: A 37.1 ms, B 73.2 ms (ACK at 21-27 ms).
- CALIB_RESULT_PT(n) to CALIB_START_PT(n+1): 0.08-0.19 ms (same burst; no gap between points).
- Last CALIB_RESULT_PT to CALIB_RESULT: A 0.09 ms; B 62.7 ms, because B emitted an extra
  `CALIB_RESULT_PT PT="6" CALX="0.5000" CALY="0.5000"` 62.5 ms after PT 5's result, with no matching
  CALIB_START_PT 6; CALIB_RESULT then came 0.18 ms later and still lists 5 points. An app must ignore a
  CALIB_RESULT_PT whose PT exceeds the point count and use only CALIB_RESULT as completion.
- Whole run (START sent to CALIB_RESULT): A 10 323.7 ms, B 10 838.9 ms.
- No record marks the DELAY/TIMEOUT boundary inside a point: the app must time the glide itself as
  DELAY after CALIB_START_PT.
- CALIBRATE_RESULT_SUMMARY after run B returned the exact same AVE_ERROR 1510.04 as after run A.

Not concluded without a camera: whether calibration quality holds with the window hidden (VALID_POINTS=5),
whether a 0.3 s TIMEOUT actually collects enough samples (P4), any AVE_ERROR or per-point error, P5 eye position.

Control stayed responsive: every SET/GET ACKed in 18-30 ms throughout, including after both runs and the restore.
