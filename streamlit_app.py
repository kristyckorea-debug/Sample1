import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Job Market Search", page_icon="🔎", layout="wide")

st.title("🔎 Job Market Search")
st.write("Search JobsDB vacancies from one place.")

keyword = st.text_input(
    "Keywords",
    placeholder="e.g. Assistant Sales Manager"
)

max_results = st.number_input(
    "Maximum results",
    min_value=1,
    max_value=100,
    value=10
)

if st.button("🔍 Search Jobs", type="primary"):

    if not keyword:
        st.warning("Please enter a keyword.")

    else:
        with st.spinner("Searching JobsDB..."):

            try:
                # Get your private Apify token
                token = st.secrets["APIFY_TOKEN"]

                # JobsDB Actor we tested
                url = (
                    "https://api.apify.com/v2/acts/"
                    "hkdatafeeds~hong-kong-jobs-scraper/"
                    "run-sync-get-dataset-items"
                )

                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                }

                search_input = {
                    "keywords": keyword,
                    "maxItems": int(max_results),
                    "requestDelaySeconds": 1,
                }

                response = requests.post(
                    url,
                    headers=headers,
                    json=search_input,
                    timeout=180,
                )

                response.raise_for_status()

                jobs = response.json()

                if not jobs:
                    st.info("No jobs found.")

                else:
                    results = []

                    for job in jobs:

                        salary = job.get("salary_label")

                        if not salary:
                            salary = "Not disclosed"

                        results.append({
                            "Job Title": job.get("title", ""),
                            "Company": job.get("company", ""),
                            "Salary": salary,
                            "Min Salary": job.get("salary_min"),
                            "Max Salary": job.get("salary_max"),
                            "Industry": job.get("classification", ""),
                            "Posted": job.get("listing_date", ""),
                            "Link": job.get("url", ""),
                        })

                    df = pd.DataFrame(results)

                    st.success(f"Found {len(df)} JobsDB vacancies")

                    st.dataframe(
                        df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Link": st.column_config.LinkColumn(
                                "Job Link",
                                display_text="Open vacancy"
                            )
                        },
                    )

                    csv = df.to_csv(index=False).encode("utf-8-sig")

                    st.download_button(
                        "⬇️ Download results",
                        csv,
                        "jobsdb_results.csv",
                        "text/csv",
                    )

            except Exception as e:
                st.error(f"Something went wrong: {e}")