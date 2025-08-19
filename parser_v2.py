
import io, re
from typing import List, Dict, Tuple

def _extract_text_pymupdf(file_bytes: bytes) -> str:
    import fitz
    text_parts = []
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        for page in doc:
            text_parts.append(page.get_text("text"))
    return "\n".join(text_parts)

def _extract_text_pdfminer(file_bytes: bytes) -> str:
    from pdfminer.high_level import extract_text
    return extract_text(io.BytesIO(file_bytes))

def _clean_text(s: str) -> str:
    s = re.sub(r"\(cid:\d+\)", "", s)
    replacements = {"\ufb01":"fi","\ufb02":"fl","\u00a0":" ","\u2010":"-","\u2011":"-","\u2012":"-","\u2013":"-","\u2014":"-","\u200b":""}
    for k,v in replacements.items(): s = s.replace(k,v)
    s = re.sub(r"(\w+)-\n(\w+)", r"\1\2", s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\r\n?", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = "".join(ch for ch in s if ch == "\n" or ord(ch) >= 32)
    return s.strip()

def extract_text_from_pdf(file) -> str:
    data = file.read()
    if hasattr(file, "seek"): file.seek(0)
    try:
        txt = _extract_text_pymupdf(data)
        if txt and len(txt.split()) > 20: return _clean_text(txt)
    except Exception: pass
    try:
        txt = _extract_text_pdfminer(data)
        return _clean_text(txt)
    except Exception:
        return ""

def extract_text_from_docx(file) -> str:
    from docx import Document
    doc = Document(file)
    parts = [p.text for p in doc.paragraphs]
    return _clean_text("\n".join(parts))

SECTION_HINTS = {
    "summary": ["summary", "professional summary", "profile"],
    "skills": ["skills", "core skills", "technical skills", "skills & tools"],
    "experience": ["experience", "professional experience", "work experience", "employment history"],
    "projects": ["projects", "key projects"],
    "certs": ["certifications", "certs", "licenses"],
    "education": ["education", "academic"]
}

ROLE_WORDS = r"(Engineer|Developer|Manager|Lead|SRE|DevOps|Architect|Administrator|Specialist|Consultant)"
DATE_PAT = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{4}|\d{4}"

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
                    found = key; break
            if found: break
        if found:
            current = found; sections.setdefault(current, [])
        else:
            sections.setdefault(current, []).append(ln)
    return sections

def bullets_from(lines: List[str]) -> List[str]:
    out = []
    for ln in lines:
        m = re.match(r"^[\-\u2022\*\•]\s*(.+)$", ln)
        if m: out.append(m.group(1).strip())
    if not out:
        out = [ln for ln in lines if len(ln.split()) >= 7]
    return out[:8]

def _looks_like_role_header(ln: str) -> bool:
    if re.search(ROLE_WORDS, ln, re.IGNORECASE):
        if "|" in ln or " - " in ln or "–" in ln or " at " in ln.lower(): return True
    if re.search(r"\((" + DATE_PAT + r"[^)]*)\)$", ln, re.IGNORECASE): return True
    return False

def parse_experience_blocks(exp_lines: List[str]) -> List[Dict]:
    blocks, cur = [], []
    for ln in exp_lines:
        if not ln.strip():
            if cur: blocks.append(cur); cur = []
        else:
            cur.append(ln)
    if cur: blocks.append(cur)

    exp = []
    for blk in blocks:
        header = blk[0] if blk else ""
        if not _looks_like_role_header(header):
            joined = " ".join(blk[:2])
            if _looks_like_role_header(joined):
                header = joined; rest = blk[2:]
            else:
                rest = blk[1:]
        else:
            rest = blk[1:]

        dates = ""
        mdate = re.search(r"\((" + DATE_PAT + r"[^)]*)\)$", header, re.IGNORECASE)
        if mdate: dates = mdate.group(1)

        company = header; role = ""
        if "|" in header:
            left, right = header.split("|", 1); company = left.strip(); role = re.sub(r"\([^)]+\)", "", right).strip()
        elif " – " in header:
            left, right = header.split(" – ", 1); company = left.strip(); role = re.sub(r"\([^)]+\)", "", right).strip()
        elif " - " in header:
            left, right = header.split(" - ", 1); company = left.strip(); role = re.sub(r"\([^)]+\)", "", right).strip()
        elif " at " in header.lower():
            parts = re.split(r"\bat\b", header, flags=re.IGNORECASE, maxsplit=1)
            role = parts[0].strip(); company = parts[1].strip() if len(parts)>1 else company

        bullets = bullets_from(rest)
        exp.append({"company": company, "role": role or "Role", "dates": dates or "Dates",
                    "bullets": [{"text": b, "tags": []} for b in bullets]})
    return [e for e in exp if any(b.get("text") for b in e.get("bullets", []))]

def aggressive_fallback(lines: List[str]) -> List[Dict]:
    idxs = [i for i,ln in enumerate(lines) if _looks_like_role_header(ln)]
    exp = []
    for j,start in enumerate(idxs):
        end = idxs[j+1] if j+1 < len(idxs) else len(lines)
        blk = lines[start:end]
        exp.extend(parse_experience_blocks(blk))
    seen, out = set(), []
    for e in exp:
        key = (e["company"], e["role"], e["dates"])
        if key not in seen:
            out.append(e); seen.add(key)
    return out[:6]

def parse_resume_to_json(text: str) -> Dict:
    lines = _clean_lines(text)
    name, title, contacts = guess_header(lines)
    sect = sectionize(lines)

    summary = [s for s in sect.get("summary", sect.get("header", [])) if len(s.split()) >= 6][:4]

    skills_raw = " ".join(sect.get("skills", []))
    skills_items = [s.strip() for s in re.split(r"[,|/]", skills_raw) if s.strip()]
    skills_groups = []
    if skills_items:
        group = []
        for s in skills_items:
            group.append(s)
            if len(group) >= 10:
                skills_groups.append(["Skills", group]); group = []
        if group: skills_groups.append(["Skills", group])

    exp_lines = sect.get("experience", [])
    experience = parse_experience_blocks(exp_lines)
    if not experience:
        experience = aggressive_fallback(lines)

    def bullets_from_section(key):
        return [{"text": x, "tags": []} for x in bullets_from(sect.get(key, []))]

    projects = bullets_from_section("projects")
    certs = [x for x in bullets_from(sect.get("certs", []))]
    education = [x for x in bullets_from(sect.get("education", []))]

    return {
        "header": {"name": name or "YOUR NAME", "title": title or "Your Title", "contacts": contacts or "City, ST | email@example.com | 123-456-7890"},
        "summary": summary,
        "skills_groups": skills_groups,
        "experience": experience,
        "projects": projects,
        "certs": certs,
        "education": education
    }
