"""Scraping del dominio objetivo: descubre subdominios, tokens y tecnologías.

Fuentes:
  - Crawl del propio sitio (HTML, enlaces, src de scripts/css, formularios).
  - robots.txt y sitemap.xml.
  - Certificate Transparency (crt.sh) -> fuente pasiva muy potente.
  - Fingerprinting de tecnologías de cada respuesta.
"""
from __future__ import annotations

import json
import re
import sys
import time
from collections import deque
from urllib.parse import urljoin, urlparse

import requests

from fingerprint import detect_technologies
from utils import clean_word, normalize_host, split_domain

# Regex para hostnames y para rutas tipo subdominio dentro de texto/JS.
_HOST_RE = re.compile(r"\b((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,})\b", re.I)
_WORD_RE = re.compile(r"[a-z][a-z0-9]{2,30}", re.I)

DEFAULT_HEADERS = {
    "User-Agent": "subwordlist/1.0 (+recon; authorized use only)",
    "Accept": "*/*",
}


class Scraper:
    def __init__(self, domain: str, *, max_pages: int = 40, timeout: float = 10.0,
                 delay: float = 0.3, use_https: bool = True, verbose: bool = True,
                 use_crtsh: bool = True):
        self.domain = normalize_host(domain)
        _, self.registrable = split_domain(self.domain)
        self.max_pages = max_pages
        self.timeout = timeout
        self.delay = delay
        self.scheme = "https" if use_https else "http"
        self.verbose = verbose
        self.use_crtsh = use_crtsh

        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

        self.subdomains: set[str] = set()   # hosts completos del dominio registrable
        self.labels: set[str] = set()       # etiquetas de subdominio (p.ej. 'api')
        self.tokens: set[str] = set()       # palabras sueltas para permutar
        self.technologies: set[str] = set()

    def _log(self, *args):
        if self.verbose:
            print("[scraper]", *args, file=sys.stderr)

    # -- registro de hallazgos ------------------------------------------------
    def _register_host(self, host: str):
        host = normalize_host(host)
        if not host or "." not in host:
            return
        if not host.endswith("." + self.registrable) and host != self.registrable:
            return
        self.subdomains.add(host)
        sub, _ = split_domain(host)
        for label in sub.split("."):
            cw = clean_word(label)
            if cw and cw not in ("www",):
                self.labels.add(cw)
                self.tokens.add(cw)

    def _harvest_tokens(self, text: str):
        for m in _WORD_RE.findall(text):
            cw = clean_word(m)
            if cw and 2 < len(cw) <= 25:
                self.tokens.add(cw)

    def _harvest_hosts(self, text: str):
        for m in _HOST_RE.findall(text):
            self._register_host(m)

    # -- fuentes --------------------------------------------------------------
    def crawl(self):
        """Crawl BFS limitado al dominio registrable."""
        start = f"{self.scheme}://{self.domain}/"
        seen: set[str] = set()
        queue: deque[str] = deque([start, urljoin(start, "/robots.txt"),
                                   urljoin(start, "/sitemap.xml")])
        pages = 0
        while queue and pages < self.max_pages:
            url = queue.popleft()
            if url in seen:
                continue
            seen.add(url)
            try:
                resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            except requests.RequestException as e:
                self._log(f"error {url}: {e}")
                continue
            pages += 1
            self._log(f"({pages}/{self.max_pages}) {resp.status_code} {url}")

            cookies = [f"{c.name}={c.value}" for c in resp.cookies]
            self.technologies |= detect_technologies(
                resp.status_code, dict(resp.headers), resp.text, cookies)

            body = resp.text or ""
            self._harvest_hosts(body)
            self._harvest_hosts(" ".join(f"{k}: {v}" for k, v in resp.headers.items()))

            # enlaces internos para seguir crawleando
            for m in re.findall(r'(?:href|src|action)=["\']([^"\']+)["\']', body, re.I):
                nxt = urljoin(url, m)
                p = urlparse(nxt)
                if p.scheme not in ("http", "https"):
                    continue
                if normalize_host(p.netloc).endswith(self.registrable):
                    self._register_host(p.netloc)
                    # recolecta palabras de la ruta (p.ej. /admin/login)
                    self._harvest_tokens(p.path.replace("/", " "))
                    if nxt not in seen and len(queue) < self.max_pages * 3:
                        queue.append(nxt)

            # palabras del contenido visible (quita etiquetas)
            self._harvest_tokens(re.sub(r"<[^>]+>", " ", body))
            if self.delay:
                time.sleep(self.delay)

    def crtsh(self):
        """Certificate Transparency: subdominios de certificados emitidos."""
        if not self.use_crtsh:
            return
        url = f"https://crt.sh/?q=%25.{self.registrable}&output=json"
        self._log(f"crt.sh -> {self.registrable}")
        try:
            resp = self.session.get(url, timeout=self.timeout + 10)
            data = json.loads(resp.text)
        except (requests.RequestException, json.JSONDecodeError) as e:
            self._log(f"crt.sh no disponible: {e}")
            return
        for entry in data:
            for name in str(entry.get("name_value", "")).splitlines():
                self._register_host(name)
        self._log(f"crt.sh aportó {len(self.subdomains)} hosts acumulados")

    def run(self):
        self.crawl()
        self.crtsh()
        return {
            "subdomains": self.subdomains,
            "labels": self.labels,
            "tokens": self.tokens,
            "technologies": self.technologies,
        }
