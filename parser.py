
import re, io, json
from typing import Dict, List
from docx import Document
from pdfminer.high_level import extract_text

SECTION_HINTS = {
    "summary": ["summary", "professional summary", "profile"],
    "skills": ["skills", "core skills", "technical skills", "skills & tools"],
    "experience": ["experience", "professional experience", "work experience", "employment history"],
    "projects": ["projects", "key projects"],
    "certs": ["certifications", "certs", "licenses"],
    "education": ["education", "academic"]
}

def _clean_lines(text: str) -> List[str]:
    lines = [l.strip() for l in text.splitlines()]
    return [l for l in lines if l]

def extract_text_from_docx(file) -> str:
    doc = Document(file)
    parts = []
    for p in doc.paragraphs:
        parts.append(p.text)
    return "\n".join(parts)

def extract_text_from_pdf(file) -> str:
    if hasattr(file, "read"):
        data = file.read()
        if hasattr(file, "seek"): file.seek(0)
        text = extract_text(io.BytesIO(data))
    else:
        text = extract_text(file)
    return text

def guess_name_title_contacts(lines: List[str]):
    name = ""
    title = ""
    contacts = ""
    top = lines[:6]
    if top: name = top[0].strip()
    if len(top) > 1: title = top[1].strip()
    if len(top) > 2: contacts = top[2].strip()
    return name, title, contacts

def sectionize(lines: List[str]) -> Dict[str, List[str]]:
    sections = {}
    current = "header"
    sections[current] = []
    for ln in lines:
        lower = ln.lower()
        matched = None
        for key, hints in SECTION_HINTS.items():
            for h in hints:
                if lower == h or lower.startswith(h + ":"):
                    matched = key
                    break
            if matched: break
        if matched:
            current = matched
            sections.setdefault(current, [])
        else:
            sections.setdefault(current, []).append(ln)
    return sections

def bullets_from(lines: List[str]) -> List[str]:
    out = []
    for ln in lines:
        m = re.match(r"^[\-\u2022\*\•]\s*(.+)$", ln)
        if m:
            out.append(m.group(1).strip())
    if not out:
        out = [ln.strip() for ln in lines if len(ln.split()) >= 5]
    return out

def parse_resume_to_json(text: str) -> Dict:
    lines = _clean_lines(text)
    name, title, contacts = guess_name_title_contacts(lines)
    sect = sectionize(lines)

    summary_lines = sect.get("summary", [])
    if not summary_lines and "header" in sect:
        summary_lines = sect["header"][:3]
    summary = [s for s in summary_lines if len(s.split()) >= 5][:4]

    skills_raw = " ".join(sect.get("skills", []))
    skills_list = [s.strip() for s in re.split(r"[,|]", skills_raw) if s.strip()]
    skills_groups = []
    if skills_list:
        chunk = []
        for s in skills_list:
            chunk.append(s)
            if len(chunk) >= 10:
                skills_groups.append(["Skills", chunk])
                chunk = []
        if chunk:
            skills_groups.append(["Skills", chunk])

    exp_lines = sect.get("experience", [])
    experience = []
    role = None
    role_lines = []
    for ln in exp_lines:
        if re.search(r"\b(Engineer|Developer|Manager|Lead|SRE|DevOps|Architect)\b", ln, re.IGNORECASE) and (
            "|" in ln or "–" in ln or "-" in ln
        ):
            if role and role_lines:
                experience.append({"header": role, "bullets": bullets_from(role_lines)})
                role_lines = []
            role = ln
        else:
            role_lines.append(ln)
    if role and role_lines:
        experience.append({"header": role, "bullets": bullets_from(role_lines)})

    exp_struct = []
    for item in experience:
        hdr = item["header"]
        comp = hdr
        role_ = ""
        dates = ""
        mdate = re.search(r"\(([A-Za-z0-9 ,\-–]+)\)", hdr)
        if mdate:
            dates = mdate.group(1)
        if "|" in hdr:
            left, right = hdr.split("|", 1)
            comp = left.strip()
            role_ = re.sub(r"\([^)]+\)", "", right).strip()
        elif "–" in hdr:
            parts = hdr.split("–")
            comp = parts[0].strip()
            if len(parts) > 1:
                role_ = re.sub(r"\([^)]+\)", "", "–".join(parts[1:])).strip()

        exp_struct.append({
            "company": comp,
            "role": role_ or "Role",
            "dates": dates or "Dates",
            "bullets": [{"text": b, "tags": []} for b in item["bullets"][:8]]
        })

    projects = [{"text": p, "tags": []} for p in bullets_from(sect.get("projects", []))[:6]]
    certs = bullets_from(sect.get("certs", []))[:10]
    education = bullets_from(sect.get("education", []))[:4]

    return {
        "header": {
            "name": name or "YOUR NAME",
            "title": title or "Your Title",
            "contacts": contacts or "City, ST | email@example.com | 123-456-7890"
        },
        "summary": summary,
        "skills_groups": skills_groups,
        "experience": exp_struct,
        "projects": projects,
        "certs": certs,
        "education": education
    }
