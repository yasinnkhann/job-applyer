import asyncio
import csv
from datetime import datetime
from playwright.async_api import async_playwright
import os
import google.generativeai as genai
from dotenv import load_dotenv
import aiofiles


# -------------------- Configuration --------------------
load_dotenv()
gemini_api_key = os.environ.get("GEMINI_API_KEY")
if not gemini_api_key:
    raise RuntimeError("GEMINI_API_KEY not found in environment.")
genai.configure(api_key=gemini_api_key)
gmodel = genai.GenerativeModel("gemini-2.0-flash")


APPLICATION_LOG = "applications_log.csv"
JOB_LIST_CSV = "jobs_to_apply.csv"


# -------------------- AI Answer Generator --------------------
def generate_batch_ai_answers(job_description: str, questions: list):
    """
    Generate AI draft answers for multiple questions at once.
    """
    question_text = "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions)])
    prompt = f"""
    Here is my resume summary:
    - Software engineer with 3 years experience in Python, React, and cloud systems.
    - Built scalable APIs, automated workflows, and improved reliability at scale.

    Job description:
    {job_description}

    Here are the application questions that need answers:
    {question_text}

    Draft concise, natural answers (2-3 sentences) for each question.
    Return them in the same numbered format.
    """
    response = gmodel.generate_content(prompt)
    output = response.text.strip()
    answers = {}
    for line in output.split("\n"):
        if line.strip() and line[0].isdigit() and "." in line:
            idx, ans = line.split(".", 1)
            answers[int(idx) - 1] = ans.strip()
    return answers


# -------------------- CSV Logging --------------------
async def log_application(company: str, job_title: str, job_url: str):
    date_applied = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with aiofiles.open(
        APPLICATION_LOG, mode="a", newline="", encoding="utf-8"
    ) as file:
        writer = csv.writer(await file.__aenter__())
        await asyncio.to_thread(
            writer.writerow, [date_applied, company, job_title, job_url]
        )


# -------------------- Apply to Single Job --------------------
async def apply_to_job(
    page, company: str, job_title: str, job_url: str, job_description: str
):
    await page.goto(job_url)

    # Autofill basic info (update selectors per site)
    await page.fill('input[name="name"]', APPLICANT["name"])
    await page.fill('input[name="email"]', APPLICANT["email"])
    await page.fill('input[name="phone"]', APPLICANT["phone"])
    await page.set_input_files('input[type="file"]', APPLICANT["resume_path"])

    # Detect empty text questions
    questions_elements = await page.query_selector_all("textarea, input[type='text']")
    empty_questions = []
    element_mapping = []

    for q in questions_elements:
        value = await q.input_value()
        if not value.strip():  # Only empty fields
            label = await q.get_attribute("aria-label") or "Why do you want this role?"
            empty_questions.append(label)
            element_mapping.append(q)

    if empty_questions:
        print(
            f"\nFound {len(empty_questions)} empty questions. Generating AI answers..."
        )
        answers = await generate_batch_ai_answers(job_description, empty_questions)

        # Review and edit all answers in one go
        final_answers = []
        for idx, question_text in enumerate(empty_questions):
            ai_answer = answers.get(idx, "")
            print(f"\nQuestion: {question_text}\nSuggested answer:\n{ai_answer}\n")
            user_input = await asyncio.to_thread(
                input, "Edit answer or press Enter to use as-is: "
            )
            final_answers.append(
                user_input.strip() if user_input.strip() else ai_answer
            )

        # Fill answers into fields
        for q_elem, ans in zip(element_mapping, final_answers):
            await q_elem.fill(ans)
    else:
        print("\nNo empty questions detected.")

    # Log application
    await log_application(company, job_title, job_url)
    print(f"\n✅ {company} - {job_title} logged. Review before submitting.\n")
    await page.pause()  # Manual review/submit


# -------------------- Main Loop --------------------
async def main():
    # Ensure log CSV has headers
    if not os.path.exists(APPLICATION_LOG):
        async with aiofiles.open(
            APPLICATION_LOG, mode="w", newline="", encoding="utf-8"
        ) as file:
            writer = csv.writer(await file.__aenter__())
            await asyncio.to_thread(
                writer.writerow, ["Date Applied", "Company", "Job Title", "Job URL"]
            )

    # Read jobs from CSV
    jobs = []
    async with aiofiles.open(JOB_LIST_CSV, newline="", encoding="utf-8") as file:
        reader = csv.DictReader(await file.__aenter__())
        jobs = await asyncio.to_thread(list, reader)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        for job in jobs:
            print(
                f"\n🚀 Starting application for {job['Company']} - {job['Job Title']}"
            )
            await apply_to_job(
                page,
                company=job["Company"],
                job_title=job["Job Title"],
                job_url=job["Job URL"],
                job_description=job["Job Description"],
            )


if __name__ == "__main__":
    asyncio.run(main())
