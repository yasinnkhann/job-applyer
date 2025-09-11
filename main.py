import os
import csv
from dotenv import load_dotenv
import google.generativeai as genai
import PyPDF2

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
JOB_LIST_CSV = "jobs_to_apply.csv"
OUTPUT_CSV = "ai_answers.csv"


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
    # Call Gemini AI
    response = gmodel.generate_content(prompt)
    output = response.text.strip()

    # Parse numbered answers robustly
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


# -------------------- CSV Output --------------------
def write_answers_to_csv(jobs, output_file):
    with open(output_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        max_questions = max(len(job["Questions"]) for job in jobs)
        header = ["Company", "Job Title", "Job URL"]
        for i in range(max_questions):
            header.append(f"Question {i+1}")
            header.append(f"Answer {i+1}")
        writer.writerow(header)

        for job in jobs:
            row = [job["Company"], job["Job Title"], job["Job URL"]]
            for q, a in zip(job["Questions"], job["Answers"]):
                row.append(q)
                row.append(a)
            writer.writerow(row)


# -------------------- Main --------------------
def main():
    jobs = []
    with open(JOB_LIST_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            job_description = row.get("Job Description", "")
            raw_questions = row.get("Questions", "")
            questions = [q.strip() for q in raw_questions.split("|") if q.strip()]

            if questions:
                answers_dict = generate_batch_ai_answers(job_description, questions)
                answers = [answers_dict.get(i, "") for i in range(len(questions))]
            else:
                answers = []

            jobs.append(
                {
                    "Company": row.get("Company", ""),
                    "Job Title": row.get("Job Title", ""),
                    "Job URL": row.get("Job URL", ""),
                    "Questions": questions,
                    "Answers": answers,
                }
            )

    write_answers_to_csv(jobs, OUTPUT_CSV)
    print(f"\n✅ AI-generated answers saved to {OUTPUT_CSV}. Ready for copy-paste!")


if __name__ == "__main__":
    main()
