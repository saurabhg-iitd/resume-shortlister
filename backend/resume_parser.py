# === backend/resume_parser.py ===
import re
import pdfplumber

def parse_resume(path):
    text = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"

    # Extract skills
    skills = re.findall(r"(?i)\b(Java|Python|SQL|AWS|Docker|Kubernetes|React|Node)\b", text)
    
    # Extract experience
    experience_match = re.search(r"(\d+(?:\.\d+)?)\+?\s*years?(?:\s*of)?\s*experience", text, re.IGNORECASE)
    total_experience = float(experience_match.group(1)) if experience_match else 0
    
    # Extract relevant experience
    relevant_exp_match = re.search(r"(\d+(?:\.\d+)?)\+?\s*years?(?:\s*of)?\s*relevant\s*experience", text, re.IGNORECASE)
    relevant_experience = float(relevant_exp_match.group(1)) if relevant_exp_match else total_experience
    
    # Extract education
    education = re.search(r"(?i)(B\.Tech|M\.Tech|BSc|MSc|MBA|PhD)", text)
    
    # Extract email
    email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    email = email_match.group(0) if email_match else ""
    
    # Extract phone
    phone_match = re.search(r"(?:\+\d{1,3}[-\.\s]?)?(?:\(?\d{3}\)?[-\.\s]?)?(?:\d{3}[-\.\s]?\d{4}|\d{10})", text)
    phone = phone_match.group(0) if phone_match else ""
    
    # Extract LinkedIn
    linkedin_match = re.search(r"(?:linkedin\.com/in/|linkedin:)([a-zA-Z0-9_-]+)", text, re.IGNORECASE)
    linkedin = linkedin_match.group(0) if linkedin_match else ""
    
    # Extract location
    location_match = re.search(r"(?:Location|Address|City|State):\s*([A-Za-z\s,]+)", text, re.IGNORECASE)
    location = location_match.group(1).strip() if location_match else ""
    
    # Extract name
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    name_match = re.search(r"(?i)Name[:\s]+([A-Za-z ]+)", text)
    if name_match:
        name = name_match.group(1)
    elif lines:
        name = lines[0]  # Assume the first non-empty line is the name
    else:
        name = "Unknown"

    return {
        "name": name,
        "email": email,
        "phone": phone,
        "linkedin": linkedin,
        "location": location,
        "skills": list(set(skills)),
        "total_experience": total_experience,
        "relevant_experience": relevant_experience,
        "education": education.group(1) if education else "Unknown",
        "text": text
    }