# === backend/matcher.py ===
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    raise Exception('OPENAI_API_KEY not set in environment variables.')
client = OpenAI(api_key=api_key)

def query_chatgpt(jd_text, resume_text):
    prompt = f"""
You are a resume reviewer. Given a job description and a candidate's resume, rate the resume from 0 to 100 based on relevance. Provide a short justification with top strengths and gaps.

Job Description:
{jd_text}

Resume:
{resume_text}

Output format:
Score: <numeric score>
Strengths: <list>
Gaps: <list>
"""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

if __name__ == "__main__":
    jd_text = "You are a resume reviewer. Given a job description and a candidate's resume, rate the resume from 0 to 100 based on relevance. Provide a short justification with top strengths and gaps."
    resume_text = "Engineering Manager from IIT Delhi with 8.5 years of experience in building scalable software solutions using Java, Spring Boot, Kafka, and AWS. Currently leading infrastructure modernization at WheelsEye Technology, a logistics platform focused on empowering fleet owners. Skilled in distributed systems, database design, and high-throughput architectures."
    print(query_chatgpt(jd_text, resume_text))