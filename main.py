import os
import json
from dotenv import load_dotenv
import google.generativeai as genai
import PyPDF2
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import LETTER
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
JOB_LIST_JSON = "jobs_to_apply.json"
OUTPUT_JSON = "output.json"
COVER_LETTER_PDFS_DIR = "cover_letters"
QA_PDFS_DIR = "qa_pdfs"


# -------------------- Resume Extraction --------------------
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
def generate_batch_ai_answers(job_description: str, questions: list, company: str):
    """
    Generates AI answers for a list of application questions,
    tailored to the applicant's resume and the specific company.
    """
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

Company: {company}

Application questions:
{question_text}

Draft concise, natural answers (4-5 sentences each) for each question,
tailored to my resume, experience, and the specific company.
Make the answers reflect why I am interested in this company and position.
Return them in the same numbered format.
Make sure they are complete, professional, non AI, and ready-to-send answers.
I don't want to see any placeholders like [Your Name] or [Company].
No dashes.
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
You are an expert career coach. Write a **complete, professional, ready-to-send cover letter** for {APPLICANT['name']} applying to the position of {job_title} at {company}.
Use the resume below to highlight relevant skills, experience, and measurable achievements.
The cover letter must:

- Be fully polished and natural.
- Do NOT include any placeholders like [Your Name], [Date], [Company Address], or [Platform].
- Use {APPLICANT['name']}’s real name, but omit address, phone, or email headers.
- Explain why the applicant is excited about this company and role.
- Include relevant technical skills (Python, React, Node.js, PostgreSQL, MongoDB, AWS, Docker, testing frameworks, etc.).
- Be concise, tailored to the applicant's experience, and ready to send.
Resume content:
{RESUME_TEXT}

Job description:
{job_description}

Write the final cover letter directly, starting with:
"Dear {company} Hiring Team," and ending with a professional closing including the applicant's name.
"""
    response = gmodel.generate_content(prompt)
    cover_letter_content = response.text.strip()

    save_cover_letter_pdf(company, job_title, cover_letter_content)

    return cover_letter_content


# -------------------- Save Cover Letter PDF --------------------
def save_cover_letter_pdf(company: str, job_title: str, cover_letter: str):
    # Ensure the output folder exists
    if not os.path.exists(COVER_LETTER_PDFS_DIR):
        os.makedirs(COVER_LETTER_PDFS_DIR)

    # File name includes company and job title (kept for organization)
    filename = f"{company}_{job_title}_CoverLetter.pdf".replace(" ", "_")
    filepath = os.path.join(COVER_LETTER_PDFS_DIR, filename)

    # Split cover letter into paragraphs
    paragraphs = cover_letter.split("\n\n")

    # Pass empty string for title to avoid the bold heading in the PDF
    save_paragraph_pdf(filepath, "", paragraphs)

    print(f"📄 Saved cover letter PDF: {filepath}")


# -------------------- PDF Helpers --------------------
def save_paragraph_pdf(filepath, title, paragraphs):

    doc = SimpleDocTemplate(
        filepath,
        pagesize=LETTER,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()
    story = []

    if title:
        story.append(Paragraph(f"<b>{title}</b>", styles["Heading2"]))
        story.append(Spacer(1, 0.2 * inch))

    for para in paragraphs:
        para = para.replace("\n", "<br/>")
        story.append(Paragraph(para, styles["Normal"]))
        story.append(Spacer(1, 0.15 * inch))

    doc.build(story)


# -------------------- Save Q&A PDF --------------------
def save_qa_pdf(company: str, job_title: str, qa_pairs: list):
    if not os.path.exists(QA_PDFS_DIR):
        os.makedirs(QA_PDFS_DIR)

    # Keep the filename descriptive
    filename = f"{company}_{job_title}_QA.pdf".replace(" ", "_")
    filepath = os.path.join(QA_PDFS_DIR, filename)

    paragraphs = []
    for qa in qa_pairs:
        paragraphs.append(f"<b>Q:</b> {qa['question']}")
        paragraphs.append(f"<b>A:</b> {qa['answer']}")
        paragraphs.append("")  # extra spacing

    # Pass empty string for title to avoid bold heading
    save_paragraph_pdf(filepath, "", paragraphs)

    print(f"📄 Saved Q&A PDF: {filepath}")


# -------------------- Main --------------------
def main():
    all_jobs = []

    with open(JOB_LIST_JSON, "r", encoding="utf-8") as f:
        jobs_data = json.load(f)

    for row in jobs_data:
        company = row.get("Company", "")
        title = row.get("Job Title", "")
        job_url = row.get("Job URL", "")
        job_description = row.get("Job Description", "")
        questions = row.get("Questions", [])

        qa_pairs = []
        if questions:
            answers = generate_batch_ai_answers(job_description, questions, company)
            qa_pairs = [
                {"question": q, "answer": answers.get(i, "")}
                for i, q in enumerate(questions)
            ]

        cover_letter_content = generate_cover_letter(job_description, company, title)

        if qa_pairs:
            save_qa_pdf(company, title, qa_pairs)

        all_jobs.append(
            {
                "Company": company,
                "Job Title": title,
                "Job URL": job_url,
                "Questions": qa_pairs,
                "CoverLetter": cover_letter_content,
            }
        )

    # Save structured JSON output
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_jobs, f, ensure_ascii=False, indent=2)

    print(f"\n✅ All AI answers saved to {OUTPUT_JSON}")
    print(f"✅ Cover letters saved in folder: {COVER_LETTER_PDFS_DIR}")
    print(f"✅ Q&A PDFs saved in folder: {QA_PDFS_DIR}")


if __name__ == "__main__":
    main()

    # generate_cover_letter(
    #     """
    # CLICS is a beauty tech company located in San Diego, CA and has invented the industry’s first hair color digital studio that completely optimizes the way salons formulate, dispense, and manage hair color. With an innovative mobile app and computer-controlled platform, CLICS allows hair colorists to create any shade of demi or permanent color with the touch of a button. CLICS is a leader in industry-first beauty salon automation technologies and proud to be an equal opportunity employer.
    #         """,
    #     "CLICS",
    #     "Senior Software Engineer",
    # )

    # answers = generate_batch_ai_answers(
    #     """
    #     job description: Finch Care is seeking a passionate and skilled Senior Software Engineer to join our dynamic team. As a key member of our engineering department, you will play a crucial role in designing, developing, and maintaining our cutting-edge healthcare platform. You will collaborate with cross-functional teams to deliver high-quality software solutions that enhance patient care and streamline healthcare operations.

    #                         """,
    #     ["What interests you about working for this company?"],
    #     "Finch Care",
    # )
    # print(list(answers.values())[0])

    print("Done ✅")
