import os
import json
from dotenv import load_dotenv
import google.generativeai as genai
import PyPDF2
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch

# -------------------- Load Environment --------------------
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not found in environment.")

genai.configure(api_key=GEMINI_API_KEY)
gmodel = genai.GenerativeModel("gemini-2.0-flash")

# -------------------- Applicant Info --------------------
APPLICANT = {
    "name": os.getenv("FULL_NAME"),
    "email": os.getenv("EMAIL"),
    "phone": os.getenv("PHONE"),
    "resume_path": os.getenv("RESUME_PATH"),
    "linkedin": os.getenv("LINKEDIN_URL"),
    "github": os.getenv("GITHUB_URL"),
    "portfolio": os.getenv("PORTFOLIO_URL"),
}

# -------------------- File Paths --------------------
JOB_LIST_JSON = "input.json"
OUTPUT_JSON = "output.json"
COVER_LETTER_PDFS_DIR = "cover_letters"


# -------------------- PDF Resume Reader (PyPDF2) --------------------
def extract_resume_text(path):
    if not path or not os.path.exists(path):
        return ""
    text = ""
    with open(path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text.strip()


RESUME_TEXT = extract_resume_text(APPLICANT["resume_path"])


# -------------------- AI Answer Generator --------------------
def generate_batch_ai_answers(job_description: str, questions: list):
    question_text = "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions)])
    prompt = f"""
Here is my profile and resume:
- Name: {APPLICANT['name']}
- Email: {APPLICANT['email']}
- Phone: {APPLICANT['phone']}
- LinkedIn: {APPLICANT.get('linkedin', '')}
- GitHub: {APPLICANT.get('github', '')}
- Portfolio: {APPLICANT.get('portfolio', '')}

Resume Content:
{RESUME_TEXT}

Job description:
{job_description}

Application questions:
{question_text}

Draft concise, natural answers (2-3 sentences) for each question,
tailored to my resume and experience.
Return them in the same numbered format.
"""
    response = gmodel.generate_content(prompt)
    output = response.text.strip()

    answers = {}
    current_idx = None
    buffer = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        if line[0].isdigit() and "." in line:
            if current_idx is not None:
                answers[current_idx] = " ".join(buffer).strip()
            current_idx = int(line.split(".")[0]) - 1
            buffer = [".".join(line.split(".")[1:]).strip()]
        else:
            if current_idx is not None:
                buffer.append(line)
    if current_idx is not None:
        answers[current_idx] = " ".join(buffer).strip()
    return answers


# -------------------- Cover Letter Generator --------------------
def generate_cover_letter(job_description: str, company: str, job_title: str):
    prompt = f"""
Here is my profile and resume:
- Name: {APPLICANT['name']}
- LinkedIn: {APPLICANT.get('linkedin', '')}
- GitHub: {APPLICANT.get('github', '')}
- Portfolio: {APPLICANT.get('portfolio', '')}

Resume Content:
{RESUME_TEXT}

Now, write a concise, professional cover letter tailored for:
- Company: {company}
- Role: {job_title}
- Job Description: {job_description}

Guidelines:
- Max one page.
- Natural tone, not too formal or robotic.
- Highlight relevant skills and alignment with the role.
"""
    response = gmodel.generate_content(prompt)
    return response.text.strip()


# -------------------- Save Job PDF --------------------
def save_job_pdf(
    company: str,
    job_title: str,
    questions: list,
    answers: list,
    cover_letter: str = None,
):
    if not os.path.exists(COVER_LETTER_PDFS_DIR):
        os.makedirs(COVER_LETTER_PDFS_DIR)

    filename = f"{company}_{job_title}_Application.pdf".replace(" ", "_")
    filepath = os.path.join(COVER_LETTER_PDFS_DIR, filename)

    c = canvas.Canvas(filepath, pagesize=LETTER)
    width, height = LETTER
    margin = 0.75 * inch
    textobject = c.beginText()
    textobject.setTextOrigin(margin, height - margin)
    textobject.setFont("Helvetica", 12)

    # Optional cover letter first
    if cover_letter:
        textobject.textLine("Cover Letter:")
        textobject.textLine("")
        for line in cover_letter.split("\n"):
            textobject.textLine(line)
        textobject.textLine("")
        textobject.textLine("-" * 70)
        textobject.textLine("")

    # Questions & Answers
    for q, a in zip(questions, answers):
        textobject.textLine(f"Q: {q}")
        textobject.textLine(f"A: {a}")
        textobject.textLine("")

    c.drawText(textobject)
    c.showPage()
    c.save()
    print(f"📄 Saved job application PDF: {filepath}")


# -------------------- Main --------------------
def main():
    all_jobs = []

    # Load jobs from JSON
    with open(JOB_LIST_JSON, "r", encoding="utf-8") as f:
        jobs_data = json.load(f)

    for row in jobs_data:
        job_description = row.get("Job Description", "")
        questions = row.get("Questions", [])

        if questions:
            answers_dict = generate_batch_ai_answers(job_description, questions)
            answers = [answers_dict.get(i, "") for i in range(len(questions))]
        else:
            answers = []

        cover_letter = generate_cover_letter(
            job_description, row.get("Company", ""), row.get("Job Title", "")
        )

        save_job_pdf(
            row.get("Company", ""),
            row.get("Job Title", ""),
            questions,
            answers,
            cover_letter,
        )

        all_jobs.append(
            {
                "Company": row.get("Company", ""),
                "Job Title": row.get("Job Title", ""),
                "Job URL": row.get("Job URL", ""),
                "Questions": questions,
                "Answers": answers,
                "CoverLetter": cover_letter,
            }
        )

    # Save structured JSON output
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_jobs, f, ensure_ascii=False, indent=2)

    print(f"\n✅ All AI answers saved to {OUTPUT_JSON}")
    print(f"✅ Individual PDFs saved in folder: {COVER_LETTER_PDFS_DIR}")


if __name__ == "__main__":
    main()
