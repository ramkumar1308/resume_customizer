
import io, json, zipfile
import streamlit as st
from parser_v2_1 import extract_text_from_docx, extract_text_from_pdf, parse_resume_to_json
from builder_v2_1 import build_resume_docx, build_cover_letter_docx

st.set_page_config(page_title="SRE Resume Customizer – v2.1", page_icon="🧰", layout="centered")
st.title("SRE Resume Customizer – v2.1")
st.caption("Upload resume → paste JD → get a clean, formatted resume + cover letter. JSON stays under the hood.")

st.subheader("1) Upload your resume")
file = st.file_uploader("Upload PDF or DOCX", type=["pdf","docx"])

resume_text = ""
if file is not None:
    try:
        if file.name.lower().endswith(".docx"):
            resume_text = extract_text_from_docx(file)
        else:
            resume_text = extract_text_from_pdf(file)
        if not resume_text or len(resume_text.split()) < 20:
            st.warning("Extraction looks thin. If possible, upload the DOCX version for best results.")
        else:
            st.success("Resume text extracted.")
    except Exception as e:
        st.error(f"Failed to read resume: {e}")

lib = None
if resume_text:
    try:
        lib = parse_resume_to_json(resume_text)
        if not lib.get("experience"):
            st.warning("Could not confidently detect your experience section. Try DOCX upload for better accuracy.")
        else:
            st.caption(f"Detected {len(lib['experience'])} experience block(s).")
    except Exception as e:
        st.error(f"Failed to parse resume: {e}")

st.subheader("2) Paste the Job Description")
jd_text = st.text_area("Paste JD here", height=220, placeholder="Paste the full JD")
company = st.text_input("Company", placeholder="e.g., Saviynt")
role = st.text_input("Role", placeholder="e.g., Principal SRE (Remote)")

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
