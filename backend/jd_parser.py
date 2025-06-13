# === backend/jd_parser.py ===
def parse_jd(text):
    import re
    skills = re.findall(r"(?i)\b(Java|Python|SQL|AWS|Docker|Kubernetes|React|Node)\b", text)
    experience = re.search(r"(\d+)\+? years", text)
    education = re.search(r"(?i)(B\.Tech|M\.Tech|BSc|MSc|MBA)", text)

    return {
        "skills_required": list(set(skills)),
        "min_experience": int(experience.group(1)) if experience else 0,
        "education_required": education.group(1) if education else None,
        "text": text
    }