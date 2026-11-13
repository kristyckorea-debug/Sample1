from difflib import SequenceMatcher
import re
import pandas as pd
import requests
import streamlit as st

# -----------------------------
# PAGE SETUP
# -----------------------------

st.set_page_config(
    page_title="Job Market Search",
    page_icon="🔎",
    layout="wide"
)

st.title("🔎 Job Market Search")
st.write("Search and prioritize job vacancies from JobsDB and Indeed with clean layout and formatting.")


# -----------------------------
# HELPER FUNCTIONS
# -----------------------------

def clean_text(text):
    if not text:
        return ""
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def calculate_title_score(search_title, job_title):
    search = clean_text(search_title)
    title = clean_text(job_title)

    if not search or not title:
        return 0
    if search == title:
        return 70
    if search in title:
        return 65

    search_words = set(search.split())
    title_words = set(title.split())

    if not search_words:
        return 0

    matched_words = search_words.intersection(title_words)
    word_ratio = len(matched_words) / len(search_words)
    phrase_similarity = SequenceMatcher(
        None,
        search,
        title
    ).ratio()

    score = (
        word_ratio * 45
        +
        phrase_similarity * 25
    )

    return min(round(score, 2), 70)


def calculate_industry_score(
    preferred_industries,
    job_industry
):
    if not preferred_industries:
        return 0

    industry = clean_text(job_industry)

    if not industry:
        return 0

    preferred_list = [
        clean_text(item)
        for item in preferred_industries.split(",")
        if clean_text(item)
    ]

    for preferred in preferred_list:
        if (
            preferred in industry
            or industry in preferred
        ):
            return 25

        preferred_words = set(preferred.split())
        industry_words = set(industry.split())

        if preferred_words.intersection(industry_words):
            return 15

    return 0


def relevance_label(score):
    if score >= 75:
        return "🟢 High"
    elif score >= 50:
        return "🟡 Medium"
    else:
        return "⚪ Broad"


# -----------------------------
# SEARCH FORM & FILTERS
# -----------------------------

keyword = st.text_input(
    "Job Title / Keywords",
    placeholder="e.g. Assistant Sales Manager"
)

industry_preference = st.text_input(
    "Preferred Industry (optional)",
    placeholder="e.g. Beverage, FMCG, Wine & Spirits"
)

# Standardized label matching the input fields style
st.markdown("Platforms to Search")
col1, col2 = st.columns(2)
with col1:
    search_jobsdb = st.checkbox("JobsDB (Hong Kong)", value=True)
with col2:
    search_indeed = st.checkbox("Indeed", value=True)

max_results = st.number_input(
    "Maximum results per platform",
    min_value=1,
    max_value=100,
    value=20,
    step=10
)

if st.button("🔍 Search Jobs", type="primary"):

    if not keyword.strip():
        st.warning("Please enter a job title or keyword.")
    elif not search_jobsdb and not search_indeed:
        st.warning("Please select at least one platform to search.")
    else:

        with st.spinner("Searching job boards and parsing all records..."):

            try:
                token = st.secrets["APIFY_TOKEN"]
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                }
                all_raw_jobs = []

                # 1. FETCH JOBSDB
                if search_jobsdb:
                    try:
                        jobsdb_url = (
                            "https://api.apify.com/v2/acts/"
                            "hkdatafeeds~hong-kong-jobs-scraper/"
                            "run-sync-get-dataset-items"
                        )
                        jobsdb_input = {
                            "keywords": keyword,
                            "maxItems": int(max_results),
                            "requestDelaySeconds": 1,
                        }
                        res = requests.post(
                            jobsdb_url,
                            headers=headers,
                            json=jobsdb_input,
                            timeout=180,
                        )
                        res.raise_for_status()
                        for job in res.json():
                            job["_platform"] = "JobsDB"
                            all_raw_jobs.append(job)
                    except Exception as e:
                        st.warning(f"Could not fetch from JobsDB: {e}")

                # 2. FETCH INDEED
                if search_indeed:
                    try:
                        indeed_url = (
                            "https://api.apify.com/v2/acts/"
                            "borderline~indeed-scraper/"
                            "run-sync-get-dataset-items"
                        )
                        indeed_input = {
                            "country": "hk",
                            "query": keyword,
                            "maxRows": int(max_results),
                        }
                        res = requests.post(
                            indeed_url,
                            headers=headers,
                            json=indeed_input,
                            timeout=180,
                        )
                        res.raise_for_status()
                        for job in res.json():
                            job["_platform"] = "Indeed"
                            all_raw_jobs.append(job)
                    except Exception as e:
                        st.warning(f"Could not fetch from Indeed: {e}")


                # -----------------------------
                # PROCESS & PARSE RESULTS
                # -----------------------------

                if not all_raw_jobs:
                    st.info("No jobs found across selected platforms.")
                else:
                    results = []

                    for job in all_raw_jobs:
                        platform = job.get("_platform", "Unknown Platform")

                        job_title = (
                            job.get("title")
                            or job.get("positionName")
                            or "Untitled Role"
                        )
                        company = (
                            job.get("company")
                            or job.get("companyName")
                            or "Confidential / Unnamed Company"
                        )

                        industry = (
                            job.get("classification")
                            or job.get("industry")
                            or job.get("jobCategory")
                            or "General / Unclassified"
                        )

                        # --- ROBUST SALARY PARSER ---
                        raw_salary = (
                            job.get("salary_label")
                            or job.get("salary")
                            or job.get("salaryText")
                        )
                        
                        if isinstance(raw_salary, dict):
                            salary = (
                                raw_salary.get("text")
                                or raw_salary.get("formatted")
                                or raw_salary.get("display")
                                or ""
                            )
                            if not salary:
                                min_val = raw_salary.get("min") or raw_salary.get("minValue")
                                max_val = raw_salary.get("max") or raw_salary.get("maxValue")
                                currency = raw_salary.get("salaryCurrency") or raw_salary.get("currency") or ""
                                interval = raw_salary.get("interval") or ""
                                
                                if min_val and max_val:
                                    salary = f"{currency} {min_val} - {max_val} ({interval})".strip()
                                elif min_val:
                                    salary = f"{currency} {min_val} ({interval})".strip()
                                else:
                                    salary = "Not disclosed"
                        elif raw_salary:
                            salary = str(raw_salary)
                        else:
                            salary = "Not disclosed"

                        # --- SMART DISTRICT PARSER ---
                        raw_district = (
                            job.get("districts")
                            or job.get("district")
                            or job.get("location")
                        )
                        if isinstance(raw_district, dict):
                            district = (
                                raw_district.get("formattedAddressShort")
                                or raw_district.get("city")
                                or raw_district.get("fullAddress")
                                or "Hong Kong"
                            )
                        elif isinstance(raw_district, list):
                            district = (
                                ", ".join(str(item) for item in raw_district)
                                if raw_district
                                else "Hong Kong"
                            )
                        elif raw_district:
                            district = str(raw_district)
                        else:
                            district = "Hong Kong (Not specified)"

                        posted_date = (
                            job.get("listing_date")
                            or job.get("listingDate")
                            or job.get("postedDate")
                            or job.get("date")
                            or "Recent"
                        )
                        if posted_date and "T" in str(posted_date):
                            posted_date = str(posted_date).split("T")[0]

                        job_link = (
                            job.get("url")
                            or job.get("link")
                            or job.get("jobUrl")
                            or "#"
                        )

                        # Relevance score
                        title_score = calculate_title_score(
                            keyword,
                            job_title
                        )
                        industry_score = calculate_industry_score(
                            industry_preference,
                            industry
                        )
                        total_score = title_score + industry_score
                        relevance = relevance_label(total_score)

                        results.append({
                            "Platform": platform,
                            "Relevance": relevance,
                            "Company": company,
                            "Job Title": job_title,
                            "Salary": salary,
                            "District": district,
                            "Industry": industry,
                            "Posted Date": posted_date,
                            "Job Link": job_link,
                            "_score": total_score,
                        })

                    # -----------------------------
                    # CREATE TABLE
                    # -----------------------------
                    df = pd.DataFrame(results)

                    df["_date_sort"] = pd.to_datetime(
                        df["Posted Date"],
                        errors="coerce"
                    )

                    df = df.sort_values(
                        by=[
                            "_score",
                            "_date_sort"
                        ],
                        ascending=[
                            False,
                            False
                        ],
                        na_position="last"
                    )
                    df = df.drop(
                        columns=[
                            "_score",
                            "_date_sort"
                        ]
                    )

                    # -----------------------------
                    # DISPLAY
                    # -----------------------------
                    st.success(
                        f"Found {len(df)} total vacancies with matching typography layout!"
                    )

                    st.dataframe(
                        df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Platform": st.column_config.TextColumn("Platform"),
                            "Relevance": st.column_config.TextColumn("Relevance"),
                            "Company": st.column_config.TextColumn("Company"),
                            "Job Title": st.column_config.TextColumn("Job Title"),
                            "Salary": st.column_config.TextColumn("Salary"),
                            "District": st.column_config.TextColumn("District"),
                            "Industry": st.column_config.TextColumn("Industry"),
                            "Posted Date": st.column_config.TextColumn("Posted Date"),
                            "Job Link": st.column_config.LinkColumn(
                                "Job Link",
                                display_text="Open ↗"
                            ),
                        },
                    )

                    # -----------------------------
                    # DOWNLOAD
                    # -----------------------------
                    csv = df.to_csv(
                        index=False
                    ).encode("utf-8-sig")

                    st.download_button(
                        "⬇️ Download combined results",
                        csv,
                        f"combined_jobs_{keyword}.csv",
                        "text/csv",
                    )

            except Exception as e:
                st.error(
                    f"Something went wrong: {e}"
                )