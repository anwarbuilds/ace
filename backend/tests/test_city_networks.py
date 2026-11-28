"""Regional startup networks become leads (DIS-18). Every network, company and link here is fictional."""

from __future__ import annotations

from datetime import datetime, timezone
import json

import httpx
import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.base import Base
from backend.app.db.models import EmployerLead, JobSourceRecord
from backend.app.discovery.yc_names import site_hints
from backend.scripts import collect_city_networks as cn

NETWORK = {"name": "Fictional Ventures portfolio", "region": "Columbus", "base": "https://jobs.fictional.example"}


def page(name, domain, url):
    data = {"props": {"pageProps": {"initialState": {"jobs": {"currentJob": {
        "title": "Software Engineer", "url": url, "organization": {"name": name, "domain": domain}}}}}}}
    return f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script></html>'


SITEMAP = """<urlset>
<url><loc>https://jobs.fictional.example/companies</loc></url>
<url><loc>https://jobs.fictional.example/companies/zephyr/jobs/11-account-executive</loc></url>
<url><loc>https://jobs.fictional.example/companies/zephyr/jobs/12-software-engineer</loc></url>
<url><loc>https://jobs.fictional.example/companies/quill/jobs/21-designer</loc></url>
</urlset>"""

PAGES = {
    "/robots.txt": "User-agent: *\nAllow: /\nCrawl-delay: 2\n",
    "/sitemap.xml": SITEMAP,
    "/companies/zephyr/jobs/12-software-engineer": page("Zephyr Labs", "zephyrlabs.example",
                                                        "https://job-boards.greenhouse.io/zephyrlabs/jobs/4001"),
    "/companies/quill/jobs/21-designer": page("Quill Works", "quillworks.example", "https://www.linkedin.com/jobs/view/1"),
}


def fake_get(url):
    path = httpx.URL(url).path
    body = PAGES.get(path)
    return httpx.Response(200 if body is not None else 404, text=body or "", request=httpx.Request("GET", url))


def test_one_job_page_per_company_engineering_first_within_the_crawl_delay(monkeypatch):
    monkeypatch.setattr(cn, "NETWORKS", (NETWORK,))
    asked, waits = [], []

    def get(url):
        asked.append(url)
        return fake_get(url)

    data = cn.collect(get=get, sleep=waits.append)
    assert [row["company"] for row in data["companies"]] == ["Quill Works", "Zephyr Labs"]
    zephyr = data["companies"][1]
    assert zephyr["board"]["source_type"] == "greenhouse" and zephyr["board"]["source_account"] == "zephyrlabs"
    assert zephyr["host"] == "zephyrlabs.example" and data["companies"][0]["board"] is None
    assert not any("11-account-executive" in url for url in asked)
    assert waits == [2.0, 2.0]
    assert data["networks"][0]["status"] == "read" and data["networks"][0]["companies"] == 2


def test_a_network_whose_robots_refuse_is_recorded_not_read(monkeypatch):
    monkeypatch.setattr(cn, "NETWORKS", (NETWORK,))
    refused = dict(PAGES, **{"/robots.txt": "User-agent: *\nDisallow: /\n"})
    asked = []

    def get(url):
        asked.append(url)
        body = refused.get(httpx.URL(url).path)
        return httpx.Response(200, text=body or "", request=httpx.Request("GET", url))

    data = cn.collect(get=get, sleep=lambda s: None)
    assert data["companies"] == [] and data["networks"][0]["status"] == "robots refuse the sitemap"
    assert asked == ["https://jobs.fictional.example/robots.txt"]


@pytest.fixture(name="sessions")
def fixture_sessions(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    monkeypatch.setattr("backend.app.db.session.SessionLocal", factory)
    return factory


def test_companies_ace_does_not_read_become_network_leads_with_board_or_site(sessions, monkeypatch):
    monkeypatch.setattr(cn, "NETWORKS", (NETWORK,))
    data = cn.collect(get=fake_get, sleep=lambda s: None)
    data["companies"].append({"network": NETWORK["name"], "region": "Columbus", "company": "Orbit Pine",
                              "host": None, "board": {"source_type": "ashby", "source_account": "orbitpine", "source_host": None}})
    with sessions.begin() as session:
        session.add(JobSourceRecord(source_type="ashby", source_account="orbitpine", company_name="Orbit Pine",
                                    enabled=True, poll_interval_seconds=900, discovery_source="lead_ledger"))
    assert cn.import_leads(data, apply=False)["leads_new"] == 2
    with sessions() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(EmployerLead)) == 0
    counts = cn.import_leads(data, apply=True)
    assert counts == {"mode": "apply", "leads_new": 2, "read_by_ace": 1}
    with sessions() as session:
        rows = {row.company_key: row for row in session.scalars(sa.select(EmployerLead))}
    zephyr = rows["zephyr"]
    assert zephyr.origin == "network" and zephyr.boards[0]["source_account"] == "zephyrlabs"
    assert "network:Fictional Ventures portfolio" in zephyr.origin_details
    assert site_hints(rows["quill works"].origin_details) == ("quillworks.example",)
