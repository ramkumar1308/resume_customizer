
import io, json, zipfile
import streamlit as st
from parser_v2 import extract_text_from_docx, extract_text_from_pdf, parse_resume_to_json
from builder_v2 import build_resume_docx, build_cover_letter_docx

st.set_page_config(page_title="SRE Resume Customizer – Clean UI", page_icon="🧰", layout="centered")
st.title("SRE Resume Customizer – Clean UI")
st.caption("Upload your resume (PDF/DOCX) → paste JD → get tailored resume + cover letter. JSON stays under the hood.")

# Upload resume
st.subheader("1) Upload your resume")
file = st.file_uploader("Upload resume (PDF or DOCX)", type=["pdf","docx"])

resume_text = ""
if file is not None:
    try:
        if file.name.lower().endswith(".docx"):
            resume_text = extract_text_from_docx(file)
        else:
            resume_text = extract_text_from_pdf(file)
        if not resume_text or len(resume_text.split()) < 20:
            st.warning("Text extraction looks thin. If possible, upload the DOCX version for best results.")
        else:
            st.success("Resume text extracted.")
    except Exception as e:
        st.error(f"Failed to read resume: {e}")

# Hidden JSON
lib = None
if resume_text:
    try:
        lib = parse_resume_to_json(resume_text)
        st.caption("Parsed resume into structured data ✔")
    except Exception as e:
        st.error(f"Failed to parse resume into structured data: {e}")

# Optional download of parsed JSON (off by default)
with st.expander("Optional: Download parsed JSON (advanced)", expanded=False):
    if lib:
        st.download_button("Download JSON", data=json.dumps(lib, indent=2).encode("utf-8"),
                           file_name="master_resume_modules.json", mime="application/json")
    else:
        st.caption("Upload a resume first.")

# Job Description
st.subheader("2) Paste the Job Description")
jd_text = st.text_area("Paste JD here", height=220, placeholder="Paste the full JD")
company = st.text_input("Company", placeholder="e.g., Experian")
role = st.text_input("Role", placeholder="e.g., Senior Site Reliability Engineer (Remote)")

# Generate
st.subheader("3) Generate your apply pack")
if st.button("Generate Apply Pack (.zip)"):
    if not lib:
        st.error("Please upload a resume first.")
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
