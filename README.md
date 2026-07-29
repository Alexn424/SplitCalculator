# splitcalc.run — Running Split Calculator

Upload a Garmin .FIT file and get lap splits without ever pressing the lap button.

**Live at:** https://splitcalc.run

## What it does
Calculates distance splits (200m, 400m, 1600m etc.) and time splits from Garmin FIT record data. Each split includes a confidence score based on GPS quality.

## Known limitations
- First lap tends to read slightly fast due to accelerometer calibration lag at standing start
- GPS spikes mid-lap can lower confidence score even when the split is accurate
- Confidence weights tuned on limited data — more validation in progress

## Requirements
Python 3.9+, Flask, fitparse, gunicorn

## Run locally
git clone https://github.com/Alexn424/SplitCalculator
cd SplitCalculator
pip install -r requirements.txt
python app.py

## Supported devices
Garmin Forerunner series (55, 165, 255, 265, 745, 945 and similar). Any device writing enhanced_speed to FIT record messages should work.
