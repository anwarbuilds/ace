from backend.app.adapters.greenhouse import fetch_greenhouse_jobs


jobs = fetch_greenhouse_jobs(
    board_token="databricks",
    company_name="Databricks",
)

print(f"ACE fetched {len(jobs)} jobs")
print()

for job in jobs[:5]:
    print("-" * 70)
    print(job.company)
    print(job.title)
    print(job.location)
    print(job.posted_at)
    print(job.official_url)