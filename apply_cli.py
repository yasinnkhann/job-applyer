import asyncio
from playwright.async_api import Page
from urllib.parse import urlparse
import google.generativeai as genai
import os
from dotenv import load_dotenv

# -------------------- Config --------------------
load_dotenv()
gemini_api_key = os.environ.get("GEMINI_API_KEY")
if not gemini_api_key:
    raise RuntimeError("GEMINI_API_KEY not found in environment.")
genai.configure(api_key=gemini_api_key)
gmodel = genai.GenerativeModel("gemini-2.0-flash")


# -------------------- AI Answer Generator --------------------
async def generate_batch_ai_answers(job_description: str, questions: list):
    prompt = f"""
    Resume summary:
    - Software engineer with 3 years experience in Python, React, and cloud systems.
    - Built scalable APIs, automated workflows, and improved reliability at scale.

    Job description:
    {job_description}

    Questions:
    {chr(10).join([f'{i+1}. {q}' for i, q in enumerate(questions)])}

    Write concise, natural answers (2–3 sentences) for each question.
    Return them in numbered format (1., 2., 3., etc).
    """
    response = gmodel.generate_content(prompt)
    output = response.text.strip()
    answers = {}
    for line in output.split("\n"):
        if line.strip() and line[0].isdigit() and "." in line:
            idx, ans = line.split(".", 1)
            answers[int(idx) - 1] = ans.strip()
    return answers


# -------------------- General Autofill --------------------
async def general_autofill(page: Page, applicant: dict):
    try:
        await page.fill('input[name*="name" i]', applicant["name"])
    except:
        pass
    try:
        await page.fill('input[name*="email" i]', applicant["email"])
    except:
        pass
    try:
        await page.fill('input[name*="phone" i]', applicant["phone"])
    except:
        pass
    try:
        await page.set_input_files('input[type="file"]', applicant["resume_path"])
    except:
        pass

    questions_elements = await page.query_selector_all("textarea, input[type='text']")
    empty_questions, element_mapping = [], []
    for q in questions_elements:
        value = await q.input_value()
        if not value.strip():
            label = (
                await q.get_attribute("aria-label")
                or await q.get_attribute("placeholder")
                or "Why do you want this role?"
            )
            empty_questions.append(label)
            element_mapping.append(q)

    return empty_questions, element_mapping


# -------------------- Platform-Specific Overrides --------------------
async def fill_greenhouse(page: Page, applicant: dict):
    selects = await page.query_selector_all("select")
    for sel in selects:
        try:
            options = await sel.query_selector_all("option")
            if options:
                await sel.select_option(index=1)  # pick first non-empty option
        except:
            continue


async def fill_lever(page: Page, applicant: dict):
    try:
        await page.fill(
            'input[name*="linkedin" i]', "https://linkedin.com/in/yourprofile"
        )
    except:
        pass
    try:
        await page.fill('input[name*="github" i]', "https://github.com/yourprofile")
    except:
        pass


# -------------------- Unified Apply Method --------------------
async def apply_to_job(job_url: str, job_description: str, applicant: dict):
    await page.goto(job_url)

    # Step 1: General autofill
    empty_questions, element_mapping = await general_autofill(page, applicant)

    # Step 2: AI-generated answers
    if empty_questions:
        print(
            f"\nFound {len(empty_questions)} empty questions. Generating AI answers..."
        )
        answers = await generate_batch_ai_answers(job_description, empty_questions)

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

        for q_elem, ans in zip(element_mapping, final_answers):
            await q_elem.fill(ans)

    # Step 3: Platform-specific overrides
    domain = urlparse(job_url).netloc
    if "greenhouse.io" in domain:
        await fill_greenhouse(page, applicant)
    elif "lever.co" in domain:
        await fill_lever(page, applicant)
