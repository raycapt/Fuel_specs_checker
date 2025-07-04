# Fuel Specs Checker (ISO 8217:2010)

This Streamlit app lets you upload a marine fuel analysis report (PDF), auto-extract key values using OpenAI GPT, and evaluates whether the parameters are within ISO 8217:2010 spec.

## Features
- Auto-extract vessel, IMO, bunker port, date, grade, and test parameters
- Compare against ISO 8217:2010 limits using an Excel reference
- Highlight off-spec values in red with ❌
- Generate branded PDF report with timestamp and ship info

## Usage
```bash
pip install -r requirements.txt
streamlit run Fuel_specs_checker.py
```

Ensure these files are in the same folder:
- Fuel_specs_checker.py
- ISO_8217_2010_Specs.xlsx
- Oldendorff_logo_RGB.jpg
