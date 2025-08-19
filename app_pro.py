
import io, json, zipfile, re
import streamlit as st
from parser import extract_text_from_docx, extract_text_from_pdf, parse_resume_to_json
from builder import build_resume_docx, build_cover_letter_docx

st.set_page_config(page_title="SRE Resume Customizer – Pro", page_icon="🧰", layout="centered")
st.title("SRE Resume Customizer – Pro")
st.caption("Upload resume → get JSON → paste JD → download tailored resume/cover letter")

st.header("1) Upload your resume (DOCX or PDF)")
file = st.file_uploader("Upload resume", type=["docx","pdf"])

resume_text = ""
if file is not None:
    try:
        if file.name.lower().endswith(".docx"):
            resume_text = extract_text_from_docx(file)
        else:
            resume_text = extract_text_from_pdf(file)
        st.success("Resume text extracted.")
        st.text_area("Extracted Text (optional review)", resume_text, height=200)
    except Exception as e:
        st.error(f"Failed to read resume: {e}")

st.header("2) Generate/edit your JSON")
json_data = {}
if file and resume_text:
    if st.button("Generate JSON from Resume"):
        try:
            json_data = parse_resume_to_json(resume_text)
            st.session_state["parsed_json"] = json_data
            st.success("JSON generated. Review and edit below.")
        except Exception as e:
            st.error(f"Parsing failed: {e}")

if "parsed_json" in st.session_state:
    raw = json.dumps(st.session_state["parsed_json"], indent=2)
    edited = st.text_area("Edit JSON (if needed)", raw, height=350)
    if edited.strip():
        try:
            st.session_state["parsed_json"] = json.loads(edited)
            st.caption("JSON validated ✔")
        except Exception as e:
            st.error(f"JSON error: {e}")

    st.download_button(
        "Download JSON",
        data=json.dumps(st.session_state["parsed_json"], indent=2).encode("utf-8"),
        file_name="master_resume_modules.json",
        mime="application/json"
    )

st.header("3) Paste or upload the Job Description")
jd_text = st.text_area("Paste JD here", height=220, placeholder="Paste the full JD")
jd_file = st.file_uploader("Or upload JD (.txt)", type=["txt"], key="jd")

if jd_file and not jd_text.strip():
    jd_text = jd_file.read().decode("utf-8", errors="ignore")

st.header("4) Generate tailored documents")
company = st.text_input("Company", placeholder="e.g., Experian")
role = st.text_input("Role", placeholder="e.g., Senior Site Reliability Engineer (Remote)")

if st.button("Generate Apply Pack (.zip)"):
    lib = st.session_state.get("parsed_json")
    if not lib:
        st.error("Please upload a resume and generate the JSON first.")
    elif not company or not role or not jd_text.strip():
        st.error("Please provide Company, Role, and a Job Description.")
    else:
        try:
            res = build_resume_docx(lib, company, role, jd_text)
            cov = build_cover_letter_docx(lib, company, role, jd_text)
            zbuf = io.BytesIO()
            with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(f"{company}_{role}_Resume.docx", res.getvalue())
                zf.writestr(f"{company}_{role}_Cover_Letter.docx", cov.getvalue())
            zbuf.seek(0)
            st.success("Apply pack generated.")
            st.download_button("Download Apply Pack (.zip)", zbuf, f"{company}_{role}_Apply_Pack.zip", "application/zip")
        except Exception as e:
            st.error(f"Failed to generate docs: {e}")
