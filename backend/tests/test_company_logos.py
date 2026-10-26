"""Automatic branding for fictional future employers, without external requests."""
from datetime import datetime, timezone
import io
import json
import socket
import threading
import time

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.routers import companies
from backend.app.branding.cache import LogoCache
from backend.app.branding.discovery import discover_logo, raster_png
from backend.app.branding.sources import LogoPage, LogoSeed, company_logo_seed
from backend.app.branding.transport import Download, LogoUnavailable, PublicFetcher, Refused, checked_url, public_address
from backend.app.config import get_settings
from backend.app.db.base import Base
from backend.app.db.models import JobRecord, JobSourceRecord
from backend.tests.test_auth import _app, _pair, _login, EMAIL, NOW, PASSWORD
from backend.app.auth import service
from backend.tests.test_web_api import add_job

COMPANY = "Future Fictional Labs"
PAGE = "https://careers.future.example/jobs/1"
ICON = "https://assets.future.example/logo.png"


def image_bytes(format="PNG", size=(64, 64)):
    im = Image.new("RGBA", size, "white")
    ImageDraw.Draw(im).rectangle((8, 8, 50, 50), fill="purple")
    out = io.BytesIO()
    im.save(out, format=format)
    return out.getvalue()


def seed(*, owned=True, company=COMPANY, url=PAGE, key="a" * 64):
    return LogoSeed(company, key, (LogoPage(url, owned),))


def fake_fetch(pages):
    calls = []
    def fetch(url, limit, deadline):
        calls.append(url)
        if url not in pages:
            return Download(url, 404, b"")
        value = pages[url]
        if isinstance(value, Exception):
            raise value
        if isinstance(value, str):
            return Download(url, 200, value.encode(), "text/html")
        return Download(url, 200, value, "image/png")
    fetch.calls = calls
    return fetch


@pytest.fixture
def factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def registered(session, *, company=COMPANY, kind="jobposting_sitemap", account="careers.future.example", verified=True):
    source = JobSourceRecord(company_name=company, source_type=kind, source_account=account,
        source_host="careers.future.example", enabled=True,
        last_verified_at=datetime.now(timezone.utc) if verified else None)
    session.add(source)
    job = add_job(session, external_id="future-1", company=company, source=kind)
    job.source_account = account
    job.official_url = PAGE + "?tracking=discarded#fragment"
    session.commit()
    return source, job


def test_new_company_is_derived_from_registered_identity_without_a_logo_allowlist(factory):
    with factory() as session:
        registered(session)
        result = company_logo_seed(session, COMPANY)
        assert result.pages[0] == LogoPage(PAGE, True)
        assert result.company == COMPANY
        assert company_logo_seed(session, "Future Fictional").pages == ()
        assert company_logo_seed(session, "careers.future.example").pages == ()
        assert session.scalar(select(func.count()).select_from(JobRecord)) == 1


def test_unregistered_disabled_mismatched_and_feed_sources_do_not_authorize_a_fetch(factory):
    with factory() as session:
        source, job = registered(session)
        source.enabled = False
        session.commit()
        assert not company_logo_seed(session, COMPANY).pages
        source.enabled = True
        source.company_name = "Another Fictional Employer"
        session.commit()
        assert not company_logo_seed(session, COMPANY).pages
        source.company_name = COMPANY
        source.source_type = job.source = "simplify"
        session.commit()
        assert not company_logo_seed(session, COMPANY).pages


def test_verified_board_metadata_can_seed_a_future_company_before_job_storage(factory):
    with factory() as session:
        session.add(JobSourceRecord(company_name=COMPANY, source_type="greenhouse", source_account="future-fictional",
            enabled=True, last_verified_at=datetime.now(timezone.utc)))
        session.commit()
        result = company_logo_seed(session, COMPANY)
        assert result.pages == (LogoPage("https://job-boards.greenhouse.io/future-fictional"),)


def test_unverified_source_without_job_evidence_cannot_supply_a_brand(factory):
    with factory() as session:
        session.add(JobSourceRecord(company_name=COMPANY, source_type="greenhouse", source_account="future-fictional", enabled=True))
        session.commit()
        assert not company_logo_seed(session, COMPANY).pages


def test_first_pulled_job_refreshes_earlier_board_only_lookup(factory):
    with factory() as session:
        source = JobSourceRecord(company_name=COMPANY, source_type="greenhouse", source_account="future-fictional",
            enabled=True, last_verified_at=datetime.now(timezone.utc))
        session.add(source);session.commit()
        earlier = company_logo_seed(session, COMPANY)
        job = add_job(session, external_id="first-pull", company=COMPANY)
        job.source_account = source.source_account
        job.official_url = 'https://job-boards.greenhouse.io/future-fictional/jobs/1'
        session.commit()
        after = company_logo_seed(session, COMPANY)
        assert earlier.identity != after.identity


def test_employer_icons_are_discovered_and_reencoded_with_provenance():
    fetch = fake_fetch({PAGE: f'<html><link rel="icon" href="{ICON}"></html>', ICON: image_bytes()})
    asset = discover_logo(seed(), fetch)
    assert asset and asset.source == ICON and asset.evidence == PAGE
    assert Image.open(io.BytesIO(asset.png)).format == "PNG"
    assert fetch.calls == [PAGE, ICON]


def test_board_favicon_and_platform_logos_are_never_used_as_employer_branding():
    page = "https://jobs.lever.co/future-fictional/1"
    fetch = fake_fetch({page: '<link rel="icon" href="/lever.ico"><img id="logo" alt="Lever logo" src="/lever.png">'})
    assert discover_logo(seed(owned=False, url=page), fetch) is None
    assert fetch.calls == [page]


def test_explicit_tenant_logo_is_supported_without_hardcoded_employer_names():
    page = "https://job-boards.greenhouse.io/future-fictional"
    fetch = fake_fetch({page: f'<img alt="Company Logo" src="{ICON}">', ICON: image_bytes()})
    assert discover_logo(seed(owned=False, url=page), fetch).source == ICON


def test_lever_tenant_header_survives_an_employer_rebrand_without_borrowing_provider_logo():
    page = "https://jobs.lever.co/future-fictional/1"
    html = (f'<meta property="og:image" content="https://assets.future.example/preview.png">'
            f'<a class="main-header-logo" href="https://future.example/"><img alt="Renamed Fictional logo" src="{ICON}"></a>'
            '<footer><img alt="Lever logo" src="/provider.png"></footer>')
    fetch = fake_fetch({page: html, ICON: image_bytes()})
    asset = discover_logo(seed(owned=False, url=page), fetch)
    assert asset and asset.source == ICON and asset.evidence == page
    assert fetch.calls == [page, ICON]
    # The same CSS class on a different shared provider is not evidence.
    other = "https://jobs.ashbyhq.com/future-fictional/1"
    fetch = fake_fetch({other: html, ICON: image_bytes()})
    assert discover_logo(seed(owned=False, url=other), fetch) is None


def test_lever_footer_and_arbitrary_social_preview_remain_excluded():
    page = "https://jobs.lever.co/future-fictional"
    fetch = fake_fetch({page: f'<meta property="og:image" content="{ICON}">'
                        '<a class="main-header-logo"></a>'
                        f'<footer><img alt="Lever logo" src="{ICON}"></footer>', ICON: image_bytes()})
    assert discover_logo(seed(owned=False, url=page), fetch) is None
    assert fetch.calls == [page]


def test_workday_tenant_branding_does_not_require_a_matching_payroll_organization_name():
    page = "https://fictional.wd12.myworkdayjobs.com/External/job/Seattle/Engineer_123"
    icon = "https://fictional.wd12.myworkdayjobs.com/External/assets/logo"
    html = (f'<meta name="image" property="og:image" content="{icon}">'
            '<script type="application/ld+json">' + json.dumps({"hiringOrganization": {
                "name": "7 Fictional Payroll Entity Inc.", "sameAs": ""}}) + '</script>')
    fetch = fake_fetch({page: html, icon: image_bytes(size=(2395, 1087))})
    asset = discover_logo(seed(owned=False, url=page), fetch)
    assert asset and asset.source == icon and asset.evidence == page
    assert max(Image.open(io.BytesIO(asset.png)).size) == 96
    assert fetch.calls == [page, icon]


@pytest.mark.parametrize("icon", [
    "https://another.wd12.myworkdayjobs.com/External/assets/logo",
    "https://fictional.wd12.myworkdayjobs.com/OtherSite/assets/logo",
    "https://fictional.wd12.myworkdayjobs.com/External/preview.png",
    "https://fictional.wd12.myworkdayjobs.com/External/assets/logo?redirect=1",
    "https://fictional.wd12.myworkdayjobs.com.evil.example/External/assets/logo",
    "http://fictional.wd12.myworkdayjobs.com/External/assets/logo",
])
def test_workday_social_metadata_cannot_supply_another_tenant_or_arbitrary_image(icon):
    page = "https://fictional.wd12.myworkdayjobs.com/External/job/1"
    fetch = fake_fetch({page: f'<meta property="og:image" content="{icon}">', icon: image_bytes()})
    assert discover_logo(seed(owned=False, url=page), fetch) is None
    assert fetch.calls == [page]


@pytest.mark.parametrize("page,icon", [
    ("https://jobs.ashbyhq.com/future-fictional/1", "https://app.ashbyhq.com/api/images/org-theme-logo/abc-123/def-456/abc-789.png"),
    ("https://apply.workable.com/future-fictional/j/1", "https://workablehr.s3.amazonaws.com/uploads/account/open_graph_logo/1234/social?12345"),
])
def test_verified_boards_expose_tenant_specific_logo_metadata(page, icon):
    fetch = fake_fetch({page:f'<meta property="og:image" content="{icon}">',icon:image_bytes()})
    asset = discover_logo(seed(owned=False,url=page),fetch)
    assert asset and asset.source == icon and asset.evidence == page
    assert fetch.calls == [page,icon]


@pytest.mark.parametrize("page,icon", [
    ("https://jobs.ashbyhq.com/future-fictional", "https://app.ashbyhq.com/job-preview.png"),
    ("https://jobs.ashbyhq.com/future-fictional", "https://app.ashbyhq.com.evil.example/api/images/org-theme-logo/a/b/c.png"),
    ("https://apply.workable.com/future-fictional", "https://workablehr.s3.amazonaws.com/static/provider-logo.png"),
    ("https://careers.other.example/1", "https://workablehr.s3.amazonaws.com/uploads/account/open_graph_logo/1234/social"),
])
def test_provider_previews_and_other_sites_cannot_claim_tenant_metadata(page, icon):
    fetch = fake_fetch({page:f'<meta property="og:image" content="{icon}">',icon:image_bytes()})
    assert discover_logo(seed(owned=False,url=page),fetch) is None
    assert fetch.calls == [page]


def test_greenhouse_branding_class_accepts_legal_name_variants_without_matching_other_images():
    page = "https://job-boards.greenhouse.io/future-fictional/jobs/123"
    icon = "https://recruiting.cdn.greenhouse.io/external_greenhouse_job_boards/logos/1/original/brand.png?12"
    markup = f'<img class="logo" alt="Future Fictional Labs - Corporate Logo" src="{icon}">'
    fetch = fake_fetch({page:markup,icon:image_bytes()})
    assert discover_logo(seed(owned=False,url=page),fetch).source == icon
    for wrong in ["https://recruiting.cdn.greenhouse.io/provider-logo.png","https://recruiting.cdn.greenhouse.io.evil.example/external_greenhouse_job_boards/logos/1/logo.png"]:
        fetch = fake_fetch({page:markup.replace(icon,wrong),wrong:image_bytes()})
        assert discover_logo(seed(owned=False,url=page),fetch) is None
        assert fetch.calls == [page]


def test_structured_hiring_organization_must_match_the_exact_employer():
    def html(name):
        return '<script type="application/ld+json">' + json.dumps({"@type":"JobPosting", "hiringOrganization":{"name":name, "logo":{"url":ICON}}}) + '</script>'
    fetch = fake_fetch({PAGE: html(COMPANY), ICON: image_bytes()})
    assert discover_logo(seed(owned=False), fetch).source == ICON
    fetch = fake_fetch({PAGE: html("Future Fictional Labs Consulting"), ICON: image_bytes()})
    assert discover_logo(seed(owned=False), fetch) is None
    assert fetch.calls == [PAGE]


def test_matched_hiring_organization_can_lead_to_its_official_website():
    website = "https://future.example/"
    html = '<script type="application/ld+json">' + json.dumps({"hiringOrganization":{"name":COMPANY,"sameAs":website}}) + '</script>'
    fetch = fake_fetch({PAGE: html, website: f'<link rel="apple-touch-icon" href="{ICON}">', ICON: image_bytes()})
    assert discover_logo(seed(owned=False), fetch).source == ICON


def test_social_profiles_do_not_become_employer_favicon_sources():
    html = '<script type="application/ld+json">' + json.dumps({"hiringOrganization":{"name":COMPANY,"sameAs":"https://www.linkedin.com/company/fictional"}}) + '</script>'
    fetch = fake_fetch({PAGE: html})
    assert discover_logo(seed(owned=False), fetch) is None
    assert fetch.calls == [PAGE]


@pytest.mark.parametrize("data", [b"<html>challenge</html>", b'<svg><script>alert(1)</script></svg>', b"not an image", image_bytes(size=(4,4))])
def test_unsafe_non_image_and_tracking_assets_are_not_served(data):
    assert raster_png(data) is None


def test_favicon_ico_decodes_to_a_bounded_png():
    result = raster_png(image_bytes(format="ICO", size=(128,128)))
    assert result and max(Image.open(io.BytesIO(result)).size) <= 96


def test_transparent_and_solid_placeholders_are_not_accepted_as_logos():
    for color in ["white", (0,0,0,0)]:
        out = io.BytesIO()
        Image.new("RGBA", (32,32), color).save(out, "PNG")
        assert raster_png(out.getvalue()) is None


@pytest.mark.parametrize("url", ["http://future.example/", "https://127.0.0.1/", "https://2130706433/", "https://[::1]/", "https://a:b@future.example/", "https://future.example:8443/", "https://host.local/x", "file:///etc/passwd", "https://future.example/\nsecret"])
def test_unsafe_urls_are_rejected(url):
    with pytest.raises(LogoUnavailable):
        checked_url(url)


@pytest.mark.parametrize("address", ["127.0.0.1","10.0.0.1","169.254.169.254","172.16.0.1","192.168.1.1","100.64.0.1","192.0.0.8","224.0.0.1","::1","fc00::1","fe80::1","::ffff:8.8.8.8","2002:7f00:1::1","2001:db8::1"])
def test_non_public_and_transition_addresses_are_rejected(address):
    assert not public_address(address)


def test_mixed_dns_answers_are_rejected_and_public_address_is_pinned(monkeypatch):
    from backend.app.branding import transport
    monkeypatch.setattr(transport, "_dns", lambda host: [(socket.AF_INET,1,6,"",("8.8.8.8",443)),(socket.AF_INET,1,6,"",("127.0.0.1",443))])
    with pytest.raises(LogoUnavailable):
        transport.resolve_public("future.example")
    monkeypatch.setattr(transport, "_dns", lambda host: [(socket.AF_INET,1,6,"",("8.8.8.8",443))])
    connected, wrapped = [], []
    monkeypatch.setattr(transport.socket, "create_connection", lambda address,timeout: connected.append(address) or object())
    connection = transport.PinnedHTTPSConnection("future.example")
    class Context:
        def wrap_socket(self, raw, server_hostname):
            wrapped.append(server_hostname)
            return raw
    connection._context = Context()
    connection.connect()
    assert connected == [("8.8.8.8",443)]
    assert wrapped == ["future.example"]


def test_redirects_and_robots_are_checked_before_each_destination():
    calls = []
    def reader(url, limit, deadline):
        calls.append(url)
        if url.endswith("robots.txt"):
            return Download(url,200,b"User-agent: *\nDisallow: /private\n", "text/plain")
        return Download(url,302,b"",location="https://future.example/private/logo.png")
    with pytest.raises(Refused):
        PublicFetcher(reader)(PAGE,1000,time.monotonic()+10)
    assert "https://future.example/private/logo.png" not in calls


def test_redirect_to_private_address_is_rejected_before_connection():
    calls=[]
    def reader(url,limit,deadline):
        calls.append(url)
        if url.endswith("robots.txt"):
            return Download(url,404,b"")
        return Download(url,302,b"",location="https://127.0.0.1/secret")
    with pytest.raises(LogoUnavailable):
        PublicFetcher(reader)(PAGE,1000,time.monotonic()+10)
    assert len(calls)==2


@pytest.mark.parametrize("status", [401,403,405,429])
def test_explicit_refusal_does_not_try_another_icon_or_page(status):
    calls=[]
    def reader(url,limit,deadline):
        calls.append(url)
        if url.endswith("robots.txt"):
            return Download(url,404,b"")
        return Download(url,status,b"")
    assert discover_logo(seed(), PublicFetcher(reader)) is None
    assert calls==["https://careers.future.example/robots.txt",PAGE]


def test_cache_reuses_success_across_requests_and_process_restarts(tmp_path):
    fetch=fake_fetch({PAGE:f'<link rel="icon" href="{ICON}">',ICON:image_bytes()})
    cache=LogoCache(fetch=fetch,directory=tmp_path)
    first=cache.request(seed()).result(3)
    assert first and cache.request(seed()).result(3)==first
    assert len(fetch.calls)==2
    restarted=LogoCache(fetch=lambda *args:pytest.fail("Disk hit must not fetch"),directory=tmp_path)
    assert restarted.request(seed()).result(3)==first
    assert next(tmp_path.glob("*.json")).stat().st_mode & 0o077 == 0
    cache.pool.shutdown();restarted.pool.shutdown()


def test_negative_cache_expires_and_later_published_icons_are_discovered(tmp_path):
    now=[1000]
    fetch=fake_fetch({PAGE:"<html></html>"})
    cache=LogoCache(fetch=fetch,directory=tmp_path,clock=lambda:now[0])
    assert cache.request(seed()).result(3) is None
    count=len(fetch.calls)
    assert cache.request(seed()).result(3) is None and len(fetch.calls)==count
    cache.fetch=fake_fetch({PAGE:f'<link rel="icon" href="{ICON}">',ICON:image_bytes()})
    now[0]+=21601
    assert cache.request(seed()).result(3)
    cache.pool.shutdown()


def test_simultaneous_rows_share_one_company_lookup(tmp_path):
    entered,release=threading.Event(),threading.Event()
    calls=[]
    def fetch(url,limit,deadline):
        calls.append(url);entered.set();release.wait(3)
        return Download(url,200,f'<link rel="icon" href="{ICON}">'.encode(),"text/html") if url==PAGE else Download(url,200,image_bytes(),"image/png")
    cache=LogoCache(fetch=fetch,directory=tmp_path)
    first=cache.request(seed());assert entered.wait(2)
    assert all(cache.request(seed()) is first for _ in range(20))
    release.set();assert first.result(3)
    assert calls==[PAGE,ICON]
    cache.pool.shutdown()


def test_api_is_owner_only_preserves_totals_and_handles_future_sources(factory,monkeypatch,tmp_path):
    with factory.begin() as session:
        service.create_owner(session,email=EMAIL,password=PASSWORD,now=NOW)
    fetch=fake_fetch({PAGE:f'<link rel="icon" href="{ICON}">',ICON:image_bytes()})
    cache=LogoCache(fetch=fetch,directory=tmp_path)
    monkeypatch.setattr(companies,"logo_cache",cache)
    client=TestClient(_app(factory,monkeypatch))
    assert client.get('/api/company-logo',params={'name':COMPANY}).status_code==401
    assert not fetch.calls
    assert _login(client).status_code==200
    assert client.get('/api/company-logo',params={'name':COMPANY}).status_code==204
    with factory() as session:
        registered(session)
    before=client.get('/api/marks').json()['applications_total']
    response=client.get('/api/company-logo',params={'name':COMPANY})
    assert response.status_code==200 and response.headers['content-type']=='image/png'
    assert response.headers['x-ace-logo-status']=='verified'
    assert 'no-store'in response.headers['cache-control']
    assert Image.open(io.BytesIO(response.content)).format=='PNG'
    assert client.get('/api/company-logo',params={'name':'Future Fictional Labs Consulting'}).status_code==204
    assert client.get('/api/marks').json()['applications_total']==before
    token=_pair(client)
    client.cookies.clear()
    assert client.get('/api/company-logo',params={'name':COMPANY},headers={'Authorization':'Bearer '+token}).status_code==403
    assert len(fetch.calls)==2
    cache.pool.shutdown();get_settings.cache_clear()


def test_a_cancelled_image_request_does_not_cancel_another_rows_shared_lookup(tmp_path,monkeypatch):
    import asyncio
    entered,release=threading.Event(),threading.Event()
    def fetch(url,limit,deadline):
        entered.set();release.wait(3)
        return Download(url,200,f'<link rel="icon" href="{ICON}">'.encode(),"text/html") if url==PAGE else Download(url,200,image_bytes(),"image/png")
    cache=LogoCache(fetch=fetch,directory=tmp_path)
    monkeypatch.setattr(companies,"logo_cache",cache)
    async def run():
        abandoned=asyncio.create_task(companies.company_logo(seed()))
        assert await asyncio.to_thread(entered.wait,2)
        abandoned.cancel()
        with pytest.raises(asyncio.CancelledError):
            await abandoned
        remaining=asyncio.create_task(companies.company_logo(seed()))
        release.set()
        response=await remaining
        assert response.status_code==200
    asyncio.run(run());cache.pool.shutdown()


def test_rate_limited_host_is_not_retried_for_another_company():
    calls=[]
    def reader(url,limit,deadline):
        calls.append(url)
        return Download(url,404,b'') if url.endswith('robots.txt') else Download(url,429,b'')
    fetch=PublicFetcher(reader)
    with pytest.raises(Refused):
        fetch(PAGE,1000,time.monotonic()+10)
    with pytest.raises(Refused):
        fetch('https://careers.future.example/another-employer',1000,time.monotonic()+10)
    assert calls==['https://careers.future.example/robots.txt',PAGE]
