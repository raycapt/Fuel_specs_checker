import streamlit as st
import openai
import os
import pandas as pd
from PyPDF2 import PdfReader
from fpdf import FPDF
import tempfile
from datetime import datetime
from dateutil import parser
import re

# Streamlit UI Setup
st.set_page_config(page_title="Fuel Specs Checker", layout="wide")
st.title("ISO 8217:2010 Fuel Specification Checker")

# Option to enter OpenAI API Key manually
openai_api_key = st.text_input("Enter your OpenAI API Key", type="password")

if openai_api_key:
    client = openai.OpenAI(api_key=openai_api_key)
else:
    st.stop()

# Load ISO 8217:2010 reference Excel
@st.cache_data
def load_reference_limits():
    xlsx_path = "ISO_8217_2010_Specs.xlsx"
    distillate_df = pd.read_excel(xlsx_path, sheet_name=0)
    residual_df = pd.read_excel(xlsx_path, sheet_name=1)
    return distillate_df, residual_df

distillate_df, residual_df = load_reference_limits()

# Determine parameter spec status
def check_parameter(value, limit_str):
    try:
        value = float(re.findall(r"[-+]?[0-9]*\.?[0-9]+", str(value))[0])
    except:
        return "❓", "Check manually"

    if pd.isna(limit_str) or limit_str == "-":
        return "✅", "No limit"

    if "-" in limit_str:
        parts = limit_str.split("-")
        min_val, max_val = float(parts[0]), float(parts[1])
        return ("✅" if min_val <= value <= max_val else "❌", "Within" if min_val <= value <= max_val else "Off Spec")
    if "≤" in limit_str:
        max_val = float(limit_str.replace("≤", ""))
        return ("✅" if value <= max_val else "❌", "Within" if value <= max_val else "Off Spec")
    if "≥" in limit_str:
        min_val = float(limit_str.replace("≥", ""))
        return ("✅" if value >= min_val else "❌", "Within" if value >= min_val else "Off Spec")
    return "✅", "Within"

# Extract text from uploaded PDF
def extract_text_from_pdf(uploaded_file):
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name
    reader = PdfReader(tmp_path)
    text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
    return text

# Ask OpenAI to parse the report
@st.cache_data
def parse_with_gpt(text):
    prompt = f"""
    Extract the following from the text:
    - Vessel Name
    - IMO Number
    - Bunker Port
    - Bunkering Date
    - Product/Fuel Grade
    - A dictionary of parameters and values (only numerical values)

    Format output as:
    {{
      "Vessel": "",
      "IMO": "",
      "Port": "",
      "Date": "",
      "Grade": "",
      "Parameters": {{ "Viscosity": "4.5", ... }}
    }}

    Text:
    {text}
    """
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return eval(response.choices[0].message.content)

# Generate PDF report
def generate_pdf_report(parsed_data, results):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 12)
    if os.path.exists("Oldendorff_logo_RGB.jpg"):
        pdf.image("Oldendorff_logo_RGB.jpg", 10, 8, 33)
    pdf.cell(200, 10, f"Fuel Specs Compliance Report", ln=True, align="C")
    pdf.set_font("Arial", size=10)
    pdf.ln(10)

    for k in ["Vessel", "IMO", "Port", "Date", "Grade"]:
        pdf.cell(200, 8, f"{k}: {parsed_data.get(k, '')}", ln=True)

    pdf.ln(5)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(90, 8, "Parameter", border=1)
    pdf.cell(40, 8, "Value", border=1)
    pdf.cell(60, 8, "Status", border=1)
    pdf.set_font("Arial", size=10)

    all_within = True
    for param, (value, status, symbol) in results.items():
        if symbol == "❌":
            all_within = False
        pdf.cell(90, 8, param, border=1)
        pdf.cell(40, 8, str(value), border=1)
        pdf.set_text_color(255, 0, 0) if symbol == "❌" else pdf.set_text_color(0, 128, 0)
        pdf.set_font("Arial", "B", 10)
        pdf.cell(60, 8, f"{symbol} {status}", border=1)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", size=10)

    pdf.ln(10)
    pdf.set_font("Arial", "B", 12)
    if all_within:
        pdf.set_text_color(0, 128, 0)
        pdf.cell(200, 10, "✔ WITHIN SPECS", ln=True, align="C")
    else:
        pdf.set_text_color(255, 0, 0)
        pdf.cell(200, 10, "❌ OFF SPEC FUEL", ln=True, align="C")
    pdf.set_text_color(0, 0, 0)

    fname = f"{parsed_data['Vessel']}_{parsed_data['IMO']}_{parsed_data['Date']}_{parsed_data['Grade']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    out_path = f"/mnt/data/{fname}"
    pdf.output(out_path)
    return out_path

# File uploader
uploaded_file = st.file_uploader("Upload Fuel Specification PDF", type="pdf")

if uploaded_file:
    text = extract_text_from_pdf(uploaded_file)
    parsed = parse_with_gpt(text)
    st.subheader("Extracted Info")
    st.json(parsed)

    parameters = parsed["Parameters"]
    grade = parsed["Grade"].strip().upper()
    ref_df = pd.concat([distillate_df, residual_df], ignore_index=True)
    if 'Grade' not in ref_df.columns:
        st.error("'Grade' column not found in the reference sheet.")
        st.stop()

    ref_df['Grade'] = ref_df['Grade'].astype(str).str.upper()
    ref_row = ref_df[ref_df['Grade'] == grade]

    if ref_row.empty:
        st.error(f"Fuel Grade '{grade}' not found in reference sheet.")
    else:
        spec_dict = dict(zip(ref_row["Parameter"], ref_row["Limit"]))
        result_dict = {}
        for param, val in parameters.items():
            limit = spec_dict.get(param)
            if limit is None:
                result_dict[param] = (val, "No reference found", "❓")
                continue
            symbol, status = check_parameter(val, limit)
            result_dict[param] = (val, status, symbol)

        df_out = pd.DataFrame.from_dict(result_dict, orient="index", columns=["Value", "Status", "Symbol"])
        df_out["Result"] = df_out["Symbol"] + " " + df_out["Status"]
        st.dataframe(df_out[["Value", "Result"]])

        pdf_path = generate_pdf_report(parsed, result_dict)
        st.success("PDF report generated:")
        st.download_button("Download PDF Report", open(pdf_path, "rb"), file_name=os.path.basename(pdf_path))
