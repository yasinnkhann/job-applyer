import os
import json
from dotenv import load_dotenv
import google.generativeai as genai
import PyPDF2
from datetime import datetime
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
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

    # Build dictionary of answers
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
    return response.text.strip()


# -------------------- PDF Helpers --------------------
def save_paragraph_pdf(filepath, title, paragraphs):
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.units import inch

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


# -------------------- Save Cover Letter PDF --------------------
def save_cover_letter_pdf(company: str, job_title: str, cover_letter: str):
    if not os.path.exists(COVER_LETTER_PDFS_DIR):
        os.makedirs(COVER_LETTER_PDFS_DIR)

    filename = f"{company}_{job_title}_CoverLetter.pdf".replace(" ", "_")
    filepath = os.path.join(COVER_LETTER_PDFS_DIR, filename)
    paragraphs = cover_letter.split("\n\n")  # Split into paragraphs
    save_paragraph_pdf(filepath, f"Cover Letter: {company} - {job_title}", paragraphs)
    print(f"📄 Saved cover letter PDF: {filepath}")


# -------------------- Save Q&A PDF --------------------
def save_qa_pdf(company: str, job_title: str, qa_pairs: list):
    if not os.path.exists(QA_PDFS_DIR):
        os.makedirs(QA_PDFS_DIR)

    filename = f"{company}_{job_title}_QA.pdf".replace(" ", "_")
    filepath = os.path.join(QA_PDFS_DIR, filename)

    paragraphs = []
    for qa in qa_pairs:
        paragraphs.append(f"<b>Q:</b> {qa['question']}")
        paragraphs.append(f"<b>A:</b> {qa['answer']}")
        paragraphs.append("")  # extra spacing

    save_paragraph_pdf(filepath, f"Q&A: {company} - {job_title}", paragraphs)
    print(f"📄 Saved Q&A PDF: {filepath}")


# -------------------- Main --------------------
def main():
    all_jobs = []

    # Load jobs from JSON
    with open(JOB_LIST_JSON, "r", encoding="utf-8") as f:
        jobs_data = json.load(f)

    for row in jobs_data:
        job_description = row.get("Job Description", "")
        company = row.get("Company", "")
        questions = row.get("Questions", [])

        if questions:
            answers_dict = generate_batch_ai_answers(
                job_description, questions, company
            )
            qa_pairs = [
                {"question": q, "answer": answers_dict.get(i, "")}
                for i, q in enumerate(questions)
            ]
        else:
            qa_pairs = []

        cover_letter = generate_cover_letter(
            job_description, row.get("Company", ""), row.get("Job Title", "")
        )

        save_cover_letter_pdf(
            row.get("Company", ""), row.get("Job Title", ""), cover_letter
        )
        if qa_pairs:
            save_qa_pdf(row.get("Company", ""), row.get("Job Title", ""), qa_pairs)

        all_jobs.append(
            {
                "Company": row.get("Company", ""),
                "Job Title": row.get("Job Title", ""),
                "Job URL": row.get("Job URL", ""),
                "Questions": qa_pairs,
                "CoverLetter": cover_letter,
            }
        )

    # Save structured JSON output
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_jobs, f, ensure_ascii=False, indent=2)

    print(f"\n✅ All AI answers saved to {OUTPUT_JSON}")
    print(f"✅ Cover letters saved in folder: {COVER_LETTER_PDFS_DIR}")
    print(f"✅ Q&A PDFs saved in folder: {QA_PDFS_DIR}")


if __name__ == "__main__":
    # main()

    # cover_letter = generate_cover_letter(
    #     """

    #    """,
    #     "Code for America",
    #     "Principal Software Engineer",
    # )
    # print(cover_letter)

    answers = generate_batch_ai_answers(
        """
          Mission

Finch was started by 2 friends (Nino & Steph 🙇🏾‍♂️🙇🏻‍♀️) who struggled with anxiety and depression and found self-care challenging to stick with. We decided to build Finch hoping to make self-care fun and accessible after seeing many others share similar struggles. Finch was launched in 2021, and our team is grateful to have helped over 20 million people on their mental health journeys.

Finch is profitable and we believe in responsible growth. We are a small but mighty team who are passionate about mental health.

Role Summary

Finch has unique product engineering opportunities as it straddles the line between wellness and gaming, and our product challenges reflect that. We’re passionate about making self-care feel easy and fun for everyone, and strive to design playful, delightful experiences we hope users will love. If those sorts of creative challenges are interesting to you, read on!

Key Responsibilities

You will play a critical role in growing and evolving our app as our 5th engineer.
You will work with high autonomy and speed, and be involved in the end-to-end product development cycle from ideation to launch decisions.
You will have significant input into the norms and tools we use in order to create a high performing engineering team.
You will work cross-functionally with product designers, creative designers, character animators, and the founders.
You will be a thought partner in building a product, company, and culture we are proud of.
Projects You Could Work On

How can we revolutionize the way people interact with their mobile devices to be mentally beneficial instead of mentally degrading?
How can we redefine social interactions that can help people support others in a way that no other product can?
How can we reimagine wellness exercises like CBT, mental health insights, and more to help people navigate the ups and downs in their lives?
How can we create playful product experiences that can make daily self care and mental health fun and sustainably engaging?
How can we create a generalizable platform of mental health tools that can cater to a wide range of experiences, from people still figuring out their self care routines to others who know exactly what they need to do?
Requirements

You have 5+ years experience building consumer products for mobile or full-stack environments.
You have a product-centric mindset and take pride in building experiences people love to use. You naturally identify tradeoffs for any product decision to inform opinions about user experience.
You can quickly derisk new ideas ranging from quick iterative changes to developing completely new product experiences. You move with a strong sense of urgency and can-do attitude in a fast-paced environment.
You have experience designing clean and maintainable APIs.
You’ve run many A/B experiments and can make data-informed decisions while balancing qualitative feedback.
You are familiar with best practices in engineering for mobile apps and web and can help build scalable and reliable products.
You enjoy disentangling ambiguous and messy problems into simple and elegant solutions.
You can work at least 6 hours within our coordination hours (8am PST - 6pm PST)
Nice to haves: Experience developing Flutter mobile apps. Experience working on products in the wellness or game industry.


                              """,
        ["What interests you about working for this company?"],
        "Finch Care",
    )
    print(list(answers.values())[0])
