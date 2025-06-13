### Directory: resume-shortlister

# === backend/main.py ===
from fastapi import FastAPI, UploadFile, File, Form, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from resume_parser import parse_resume
from jd_parser import parse_jd
from matcher import query_chatgpt
from db import SessionLocal
from models import JD, Resume
from s3_helper import upload_file_to_s3, download_file_from_s3
import os
import json
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse
import re
from datetime import datetime
from twilio.rest import Client

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def extract_score(review):
    match = re.search(r"Score:\s*([0-9]+(?:\.[0-9]+)?)", review)
    return float(match.group(1)) if match else None

def send_whatsapp_message(to, body):
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_whatsapp_number = os.getenv("TWILIO_WHATSAPP_FROM")
    client = Client(account_sid, auth_token)
    message = client.messages.create(
        body=body,
        from_=f'whatsapp:{from_whatsapp_number}',
        to=f'whatsapp:{to}'
    )
    return message.sid

@app.post("/upload_jd")
async def upload_jd(text: str = Form(...), name: str = Form(...), num_shortlist: int = Form(None), application_deadline: str = Form(None), selectionType: str = Form(None), db: Session = Depends(get_db)):
    parsed = parse_jd(text)
    deadline_date = None
    if application_deadline:
        try:
            deadline_date = datetime.strptime(application_deadline, "%Y-%m-%d").date()
        except Exception:
            deadline_date = None
    jd = JD(
        text=text,
        name=name,
        parsed_json=json.dumps(parsed),
        num_shortlist=num_shortlist,
        application_deadline=deadline_date,
        selection_type=selectionType if selectionType in ["FIXED", "PERCENTAGE"] else None
    )
    db.add(jd)
    db.commit()
    db.refresh(jd)
    return {"message": "JD uploaded", "jd_id": jd.id, "parsed": parsed}

@app.post("/upload_resume")
async def upload_resume(file: UploadFile = File(...), jd_id: int = Form(...), db: Session = Depends(get_db)):
    # Check if JD exists
    jd = db.query(JD).filter(JD.id == jd_id).first()
    if not jd:
        return {"error": "JD not found"}
    
    contents = await file.read()
    filepath = f"temp/{file.filename}"
    os.makedirs("temp", exist_ok=True)
    with open(filepath, "wb") as f:
        f.write(contents)
    
    # Upload to S3
    s3_path = upload_file_to_s3(filepath, file.filename)
    
    # Parse resume
    data = parse_resume(filepath)
    
    # Save to database
    resume = Resume(
        jd_id=jd_id,
        s3_path=s3_path,
        name=data["name"],
        email=data["email"],
        phone=data["phone"],
        linkedin=data["linkedin"],
        location=data["location"],
        total_experience=data["total_experience"],
        relevant_experience=data["relevant_experience"],
        parsed_json=json.dumps(data)
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    
    return {"message": "Resume uploaded", "resume_id": resume.id, "parsed": data}

@app.get("/list_jds")
async def list_jds(db: Session = Depends(get_db)):
    jds = db.query(JD).all()
    return {"jds": [{"id": jd.id, "name": jd.name, "created_at": jd.created_at, "num_shortlist": jd.num_shortlist, "application_deadline": jd.application_deadline, "selectionType": jd.selection_type.value if jd.selection_type else None} for jd in jds]}

@app.get("/list_resumes")
async def list_resumes(jd_id: int, db: Session = Depends(get_db)):
    resumes = db.query(Resume).filter(Resume.jd_id == jd_id).all()
    return {
        "resumes": [
            {
                "id": res.id,
                "name": res.name,
                "email": res.email,
                "phone": res.phone,
                "total_experience": res.total_experience,
                "relevant_experience": res.relevant_experience,
                "ai_score": res.ai_score,
            }
            for res in resumes
        ]
    }

@app.get("/resume_details")
async def resume_details(resume_id: int, db: Session = Depends(get_db)):
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        return {"error": "Resume not found"}
    
    # If OpenAI output doesn't exist yet, generate it
    if not resume.openai_output:
        jd = db.query(JD).filter(JD.id == resume.jd_id).first()
        if jd:
            jd_data = json.loads(jd.parsed_json)
            resume_data = json.loads(resume.parsed_json)
            review = query_chatgpt(jd_data['text'], resume_data['text'])
            score = extract_score(review)
            resume.openai_output = review
            resume.ai_score = score
            db.commit()
    
    return {
        "id": resume.id,
        "name": resume.name,
        "email": resume.email,
        "phone": resume.phone,
        "linkedin": resume.linkedin,
        "location": resume.location,
        "total_experience": resume.total_experience,
        "relevant_experience": resume.relevant_experience,
        "ai_score": resume.ai_score,
        "s3_path": resume.s3_path,
        "review": resume.openai_output,
        "created_at": resume.created_at
    }

@app.get("/jd_details")
async def jd_details(jd_id: int, db: Session = Depends(get_db)):
    jd = db.query(JD).filter(JD.id == jd_id).first()
    if not jd:
        return {"error": "JD not found"}
    
    return {
        "id": jd.id,
        "name": jd.name,
        "text": jd.text,
        "num_shortlist": jd.num_shortlist,
        "application_deadline": jd.application_deadline,
        "selectionType": jd.selection_type.value if jd.selection_type else None,
        "created_at": jd.created_at
    }

@app.get("/download_resume/{resume_id}")
async def download_resume(resume_id: int, db: Session = Depends(get_db)):
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        return {"error": "Resume not found"}
    
    # Extract filename from S3 path
    s3_path = resume.s3_path
    filename = s3_path.split("/")[-1]
    
    # Download from S3
    file_content = download_file_from_s3(s3_path)
    
    # Create a response with the file content
    return StreamingResponse(
        iter([file_content]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.post("/start_ranking")
async def start_ranking(jd_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    jd = db.query(JD).filter(JD.id == jd_id).first()
    if not jd:
        return {"error": "JD not found"}
    resumes = db.query(Resume).filter(Resume.jd_id == jd_id, Resume.openai_output == None).all()
    if not resumes:
        return {"message": "No resumes to rank"}
    jd_data = json.loads(jd.parsed_json)
    for res in resumes:
        resume_data = json.loads(res.parsed_json)
        review = query_chatgpt(jd_data['text'], resume_data['text'])
        score = extract_score(review)
        res.openai_output = review
        res.ai_score = score
        db.commit()
    return {"message": f"Ranked {len(resumes)} resumes"}

@app.post("/contact_top_applicants")
def contact_top_applicants(jd_id: int, db: Session = Depends(get_db)):
    jd = db.query(JD).filter(JD.id == jd_id).first()
    if not jd:
        return {"error": "JD not found"}
    resumes = db.query(Resume).filter(Resume.jd_id == jd_id, Resume.ai_score != None).all()
    # Determine top N based on selection_type and num_shortlist
    selection_type = jd.selection_type.value if jd.selection_type else "FIXED"
    num_shortlist = jd.num_shortlist or 0
    scored = [r for r in resumes if isinstance(r.ai_score, (int, float))]
    sorted_resumes = sorted(scored, key=lambda r: r.ai_score, reverse=True)
    if selection_type == "FIXED":
        top_resumes = sorted_resumes[:num_shortlist]
    elif selection_type == "PERCENTAGE":
        n = max(1, int((num_shortlist / 100) * len(resumes)))
        top_resumes = sorted_resumes[:n]
    else:
        top_resumes = sorted_resumes
    count = 0
    for res in top_resumes:
        if res.phone:
            body = (
                f"Hi {res.name},\n"
                f"You have been shortlisted for {jd.name}.\n"
                "Please reply with your current salary, expected salary, and notice period."
            )
            try:
                send_whatsapp_message(res.phone, body)
                count += 1
            except Exception as e:
                print(f"Failed to send WhatsApp to {res.phone}: {e}")
    return {"message": f"WhatsApp messages sent to {count} applicants"}

# # === .env ===
# OPENAI_API_KEY=sk-xxxx-your-key-here

# # === requirements.txt ===
# fastapi
# uvicorn
# pdfplumber
# python-multipart
# openai
# python-dotenv

# === To run ===
# 1. cd backend
# 2. pip install -r requirements.txt
# 3. uvicorn main:app --reload
