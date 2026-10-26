"""Bounded HTTPS image/page reads with public-address pinning and robots checks."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass
from http.client import HTTPSConnection, HTTPException
import ipaddress
import socket
import ssl
from threading import BoundedSemaphore, Lock
import time
from urllib.parse import urljoin, urlsplit

from backend.app.coverage.probing import robots_allows

USER_AGENT = "ACE-Company-Logos/1.0"
REFUSED = frozenset({401, 403, 405, 429})
DNS_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="logo-dns")
DNS_SLOTS = BoundedSemaphore(4)


class LogoUnavailable(Exception):
    pass


class Refused(LogoUnavailable):
    """Stop this resolution on an explicit refusal, never seek a bypass."""

    def __init__(self, status=None):
        super().__init__()
        self.status = status


def checked_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        host = parsed.hostname or ""
        if (parsed.scheme != "https" or parsed.username or parsed.password
                or parsed.port not in (None, 443) or len(value) > 4096
                or any(ord(c) < 33 for c in value) or not host or "." not in host
                or host.endswith((".localhost", ".local", ".internal"))):
            raise LogoUnavailable()
        try:
            ipaddress.ip_address(host.strip("[]"))
        except ValueError:
            return value
        raise LogoUnavailable()  # Literal addresses are not employer identities.
    except ValueError as error:
        raise LogoUnavailable() from error


def public_address(value: str) -> bool:
    address = ipaddress.ip_address(value)
    if not address.is_global or address.is_multicast or address.is_reserved:
        return False
    if address.version == 4:
        return address not in ipaddress.ip_network("192.0.0.0/24")
    return (address in ipaddress.ip_network("2000::/3")
            and address not in ipaddress.ip_network("2001::/23")
            and address not in ipaddress.ip_network("2002::/16")
            and address.ipv4_mapped is None)


def _dns(host: str):
    # OS DNS calls have no per-call deadline. Limit outstanding lookups even
    # when a resolver stalls, and release a slot only after that lookup exits.
    if not DNS_SLOTS.acquire(blocking=False):
        raise LogoUnavailable()
    def run():
        try:
            return socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        finally:
            DNS_SLOTS.release()
    try:
        return DNS_POOL.submit(run).result(timeout=2)
    except FutureTimeout as error:
        raise LogoUnavailable() from error


def resolve_public(host: str):
    answers = _dns(host)
    if not answers or any(not public_address(row[4][0]) for row in answers):
        raise LogoUnavailable()
    # The validated address is used directly, with the original TLS SNI/Host.
    # A second DNS resolution can never rebind the connection to a private IP.
    return sorted(answers, key=lambda row: row[0] != socket.AF_INET)[0][4][0]


class PinnedHTTPSConnection(HTTPSConnection):
    def connect(self):
        address = resolve_public(self.host)
        raw = socket.create_connection((address, 443), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


@dataclass(frozen=True)
class Download:
    url: str
    status: int
    data: bytes
    content_type: str = ""
    location: str = ""


def read_https(url: str, limit: int, deadline: float) -> Download:
    checked_url(url)
    parsed = urlsplit(url)
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise LogoUnavailable()
    connection = PinnedHTTPSConnection(parsed.hostname, timeout=min(3, remaining),
                                        context=ssl.create_default_context())
    try:
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        connection.request("GET", path, headers={
            "User-Agent": USER_AGENT, "Accept-Encoding": "identity",
            "Accept": "text/html,image/*;q=0.9,text/plain;q=0.8",
        })
        response = connection.getresponse()
        if response.status in REFUSED:
            raise Refused(response.status)
        if response.getheader("Content-Encoding", "identity").lower() not in ("", "identity"):
            raise LogoUnavailable()
        length = response.getheader("Content-Length")
        if length and int(length) > limit:
            raise LogoUnavailable()
        chunks, total = [], 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise LogoUnavailable()
            if connection.sock:
                connection.sock.settimeout(min(3, remaining))
            chunk = response.read1(min(65536, limit + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total > limit:
                raise LogoUnavailable()
            chunks.append(chunk)
        return Download(url, response.status, b"".join(chunks),
                        response.getheader("Content-Type", ""), response.getheader("Location", ""))
    except (OSError, ValueError, HTTPException) as error:
        raise LogoUnavailable() from error
    finally:
        connection.close()


class PublicFetcher:
    def __init__(self, reader=read_https):
        self.reader = reader
        self.robots = {}
        self.lock = Lock()

    def _read(self, url, limit, deadline, *, check_robots):
        for _ in range(4):
            checked_url(url)
            if check_robots and not robots_allows(self._robots(url, deadline), url, user_agent=USER_AGENT):
                raise Refused()
            try:
                result = self.reader(url, limit, deadline)
            except Refused as error:
                if error.status == 429:
                    self._cooldown(url)
                raise
            if result.status in REFUSED:
                if result.status == 429:
                    self._cooldown(url)
                raise Refused(result.status)
            if result.status not in (301, 302, 303, 307, 308):
                return result
            # Re-check URL, address and robots at every redirect, including CDN.
            url = urljoin(url, result.location)
        raise LogoUnavailable()

    def _cooldown(self, url):
        parts = urlsplit(url)
        with self.lock:
            self.robots[f"https://{parts.netloc}"] = (time.monotonic() + 21600, None)

    def _robots(self, url, deadline):
        parts = urlsplit(url)
        origin = f"https://{parts.netloc}"
        with self.lock:
            cached = self.robots.get(origin)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        rules = None
        try:
            result = self._read(origin + "/robots.txt", 65536, deadline, check_robots=False)
            if result.status in (404, 410):
                rules = ""
            elif result.status == 200 and not result.data.lstrip().startswith(b"<"):
                rules = result.data.decode("utf-8", "replace")
        except LogoUnavailable:
            pass
        with self.lock:
            if len(self.robots) >= 256:
                self.robots.pop(next(iter(self.robots)))
            self.robots[origin] = (time.monotonic() + (3600 if rules is not None else 21600), rules)
        return rules

    def __call__(self, url, limit, deadline):
        return self._read(url, limit, deadline, check_robots=True)
