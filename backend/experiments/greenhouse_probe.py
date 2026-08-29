import httpx


URL = "https://boards-api.greenhouse.io/v1/boards/databricks/jobs"

response = httpx.get(URL)

print("Status:", response.status_code)

data = response.json()

jobs = data["jobs"]

print("Total jobs:", len(jobs))
print()

for job in jobs[:5]:
    print("-" * 70)
    print("ID:", job["id"])
    print("Requisition:", job.get("requisition_id"))
    print("Title:", job["title"])
    print("Location:", job["location"]["name"])
    print("Published:", job.get("first_published"))
    print("Updated:", job.get("updated_at"))
    print("Official URL:", job["absolute_url"])