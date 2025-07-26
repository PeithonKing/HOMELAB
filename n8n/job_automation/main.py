import requests, time, os, random, json
from bs4 import BeautifulSoup
import pandas as pd
from models import Models
from tqdm import tqdm, trange
from flask import Flask, Response, jsonify, request

app = Flask(__name__)

queries = [
  { "job_title": "Machine Learning Engineer", "location": "India", "take": 4 },
  { "job_title": "Data Scientist",            "location": "India", "take": 4 },
  { "job_title": "Python Developer",          "location": "India", "take": 2 },
]


llm = Models()
with open("system_prompts/salary") as sp:
    salary_system_prompt = sp.read()
with open("system_prompts/exp") as ep:
    exp_system_prompt = ep.read()
with open("system_prompts/classify") as cf:
    classify_system_prompt = cf.read()


def LinkedIn_scraper(job_title, location):
    url = f"https://www.linkedin.com/jobs/search?f_AL=true&f_E=2&f_JT=F&f_TPR=r86400&keywords={job_title}&location={location}&origin=JOB_SEARCH_PAGE_JOB_FILTER&sortBy=DD"
    html = requests.get(url).text
    soup = BeautifulSoup(html, "html.parser")
    job_ids = []
    for li in soup.select("ul.jobs-search__results-list li"):
        base_card = li.find("div", class_="base-card")
        if base_card and base_card.has_attr("data-entity-urn"):
            urn = base_card["data-entity-urn"]
            parts = urn.split(":")
            if len(parts) > 3:
                job_id = parts[3]
                job_ids.append(job_id)
    return job_ids

def get_done_job_ids(csv_path="parsed_jobs.csv"):
    if not os.path.exists(csv_path):
        return []
    df = pd.read_csv(csv_path)
    return df["job_id"].dropna().astype(str).tolist()

def get_job_description(job_id):
    url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
    html = requests.get(url).text
    if "No longer accepting applications" in html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    details_div = soup.find("div", class_="decorated-job-posting__details")
    if not details_div:
        return ""
    raw_text = details_div.get_text().strip()
    # Clean the text
    cleaned = (
        raw_text.replace('\r', '')
        .replace('\n', ' ')
        .replace('\t', ' ')
    )
    cleaned = ' '.join(cleaned.split())
    return cleaned

def run_job_automation():
    job_ids = []
    done_job_ids = set(get_done_job_ids())
    for q in queries:
        ids = LinkedIn_scraper(q["job_title"], q["location"])
        ids = [job_id for job_id in ids if job_id not in done_job_ids]
        job_ids.extend(ids[:q["take"]])
    job_ids = list(set(job_ids))

    if os.path.exists("parsed_jobs.csv"):
        jobs = pd.read_csv("parsed_jobs.csv").to_dict(orient="records")
    else:
        jobs = []

    for job_id in tqdm(job_ids):
        jd = get_job_description(job_id)
        if not jd: continue

        salary = llm.get_response(
            system_prompt=salary_system_prompt,
            prompt=jd+"\nExtract just the mentioned salary or pay range for this job?"
        )

        exp = llm.get_response(
            system_prompt=exp_system_prompt,
            prompt=jd+"\nExtract just the required experience for this job?"
        )

        classify = llm.get_response(
            system_prompt=classify_system_prompt,
            prompt = f"""
Inputs to Evaluate:
- Salary: {salary}
- Experience: {exp}

Return only the category name (e.g., "Perfect Match") based on the above rules."""
        )

        jobs.append({
            "job_id": job_id,
            "classification": classify,
            "link": f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}",
            "time": int(time.time()),
            # "job_description": jd,
            "salary": salary,
            "experience": exp,
            "done": False,
        })

        pd.DataFrame(jobs).to_csv("parsed_jobs.csv", index=False)
    return jobs

@app.route('/', methods=['GET'])
def index():
    # return Response("Job Automation Service is running", status=200)
    return jsonify(pd.read_csv("parsed_jobs.csv").to_dict(orient="records")), 200

@app.route('/refresh-jobs', methods=['GET'])
def get_jobs_endpoint():
    jobs = get_done_job_ids()
    removed_jobs = []
    if not os.path.exists("parsed_jobs.csv"):
        return "0 jobs removed", 200
    df = pd.read_csv("parsed_jobs.csv")
    for job in jobs:
        jd = get_job_description(job)
        if jd is None:
            removed_jobs.append(job)
    if removed_jobs:
        df = df[~df["job_id"].astype(str).isin(removed_jobs)]
        df.to_csv("parsed_jobs.csv", index=False)
    return f"{len(removed_jobs)} jobs removed", 200

is_job_automation_running = False

@app.route('/get-new-jobs', methods=['GET'])
def run_job_automation_endpoint():
    global is_job_automation_running
    if is_job_automation_running:
        return jsonify({"error": "Job automation already running"}), 429
    is_job_automation_running = True
    jobs = run_job_automation()
    is_job_automation_running = False
    return jsonify(jobs), 200

@app.route('/mark-done', methods=['POST'])
def mark_done_endpoint():
    job_id = str(request.get_json().get('job_id'))
    if not os.path.exists("parsed_jobs.csv"):
        return jsonify({"error": "parsed_jobs.csv not found"}), 404
    df = pd.read_csv("parsed_jobs.csv")
    if job_id not in df['job_id'].astype(str).values:
        return jsonify({"error": "job_id doesn't exist"}), 404
    df.loc[df['job_id'].astype(str) == job_id, 'done'] = True
    df.to_csv("parsed_jobs.csv", index=False)
    return jsonify({"success": True, "job_id": job_id})


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8084, debug=False)
