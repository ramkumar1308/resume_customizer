
import io, re
from typing import List, Dict, Tuple

# PDF
def _extract_text_pymupdf(file_bytes: bytes) -> str:
    import fitz  # PyMuPDF
    text_parts = []
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        for page in doc:
            text_parts.append(page.get_text("text"))
    return "\n".join(text_parts)

def _extract_text_pdfminer(file_bytes: bytes) -> str:
    from pdfminer.high_level import extract_text
    return extract_text(io.BytesIO(file_bytes))

def _clean_text(s: str) -> str:
    # Remove (cid:###) artifacts
    s = re.sub(r"\(cid:\d+\)", "", s)
    # Replace common ligatures and oddities
    replacements = {
        "\ufb01": "fi",
        "\ufb02": "fl",
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u00a0": " ",
        "\u200b": "",
        "•": "•",
    }
    for k,v in replacements.items():
        s = s.replace(k,v)
    # Collapse excessive spaces
    s = re.sub(r"[ \t]+", " ", s)
    # Fix broken hyphenation at line ends: "reli-\nability" -> "reliability"
    s = re.sub(r"(\w+)-\n(\w+)", r"\1\2", s)
    # Normalize newlines
    s = re.sub(r"\r\n?", "\n", s)
    # Remove duplicate blank lines
    s = re.sub(r"\n{3,}", "\n\n", s)
    # Strip weird control chars
    s = "".join(ch for ch in s if ch == "\n" or ord(ch) >= 32)
    return s.strip()

def extract_text_from_pdf(file) -> str:
    data = file.read()
    if hasattr(file, "seek"): file.seek(0)
    try:
        txt = _extract_text_pymupdf(data)
        if txt and len(txt.split()) > 20:
            return _clean_text(txt)
    except Exception:
        pass
    # fallback to pdfminer
    try:
        txt = _extract_text_pdfminer(data)
        return _clean_text(txt)
    except Exception:
        return ""

# DOCX
def extract_text_from_docx(file) -> str:
    from docx import Document
    doc = Document(file)
    lines = [p.text for p in doc.paragraphs]
    return _clean_text("\n".join(lines))

# ---- Basic parsing to JSON (hidden from UI) ----

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

def guess_header(lines: List[str]) -> Tuple[str,str,str]:
    name = lines[0] if lines else ""
    title = lines[1] if len(lines)>1 else ""
    contacts = lines[2] if len(lines)>2 else ""
    return name, title, contacts

def sectionize(lines: List[str]) -> Dict[str, List[str]]:
    sections = {"header": []}
    current = "header"
    for ln in lines:
        low = ln.lower()
        found = None
        for key, hints in SECTION_HINTS.items():
            for h in hints:
                if low == h or low.startswith(h + ":"):
                    found = key
                    break
            if found: break
        if found:
            current = found
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
        # Use sentences of reasonable length
        out = [ln for ln in lines if len(ln.split()) >= 6]
    return out[:8]

def parse_resume_to_json(text: str) -> Dict:
    lines = _clean_lines(text)
    name, title, contacts = guess_header(lines)
    sect = sectionize(lines)

    summary = [s for s in sect.get("summary", sect.get("header", [])) if len(s.split()) >= 6][:4]

    skills_raw = " ".join(sect.get("skills", []))
    skills_items = [s.strip() for s in re.split(r"[,|/]", skills_raw) if s.strip()]
    skills_groups = []
    if skills_items:
        chunk = []
        for s in skills_items:
            chunk.append(s)
            if len(chunk) >= 10:
                skills_groups.append(["Skills", chunk]); chunk = []
        if chunk: skills_groups.append(["Skills", chunk])

    exp_lines = sect.get("experience", [])
    # Split experience by blank lines
    blocks, cur = [], []
    for ln in exp_lines:
        if not ln.strip() and cur:
            blocks.append(cur); cur = []
        else:
            cur.append(ln)
    if cur: blocks.append(cur)

    experience = []
    for blk in blocks:
        header = blk[0] if blk else ""
        blts = bullets_from(blk[1:])
        # Extract parts from header
        role = ""
        company = header
        dates = ""
        mdate = re.search(r"\(([A-Za-z0-9 ,\-–]+)\)$", header)
        if mdate: dates = mdate.group(1)
        if "|" in header:
            left, right = header.split("|", 1)
            company = left.strip()
            role = re.sub(r"\([^)]+\)", "", right).strip()
        elif " - " in header:
            parts = header.split(" - ")
            company = parts[0].strip()
            role = " - ".join(parts[1:]).strip()
        experience.append({
            "company": company,
            "role": role or "Role",
            "dates": dates or "Dates",
            "bullets": [{"text": b, "tags": []} for b in blts]
        })

    projects = [{"text": p, "tags": []} for p in bullets_from(sect.get("projects", []))]
    certs = bullets_from(sect.get("certs", []))
    education = bullets_from(sect.get("education", []))

    return {
        "header": {"name": name or "YOUR NAME", "title": title or "Your Title", "contacts": contacts or "City, ST | email@example.com | 123-456-7890"},
        "summary": summary,
        "skills_groups": skills_groups,
        "experience": experience,
        "projects": projects,
        "certs": certs,
        "education": education
    }
