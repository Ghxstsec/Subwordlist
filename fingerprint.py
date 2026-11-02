"""Fingerprinting de tecnologías web y subdominios probables derivados.

Detecta tecnologías a partir de cabeceras HTTP, cookies, meta generator,
rutas conocidas y firmas en el HTML/JS, y mapea cada tecnología a los
subdominios que suele llevar asociados en un despliegue real.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Firmas: nombre_tecnologia -> cómo detectarla
#   headers: (nombre_cabecera, regex sobre el valor)
#   cookies: regex sobre el nombre de cookie
#   html:    regex sobre el cuerpo HTML/JS
#   meta:    valor esperado en <meta name=generator>
# ---------------------------------------------------------------------------
@dataclass
class Signature:
    name: str
    headers: list[tuple[str, str]] = field(default_factory=list)
    cookies: list[str] = field(default_factory=list)
    html: list[str] = field(default_factory=list)
    meta: list[str] = field(default_factory=list)


SIGNATURES: list[Signature] = [
    Signature("wordpress", html=[r"/wp-content/", r"/wp-includes/"], meta=["wordpress"]),
    Signature("drupal", headers=[("x-generator", r"drupal")], html=[r"sites/default/files"]),
    Signature("joomla", meta=["joomla"], html=[r"/media/jui/"]),
    Signature("nginx", headers=[("server", r"nginx")]),
    Signature("apache", headers=[("server", r"apache")]),
    Signature("iis", headers=[("server", r"iis|microsoft-iis")]),
    Signature("cloudflare", headers=[("server", r"cloudflare"), ("cf-ray", r".")]),
    Signature("akamai", headers=[("server", r"akamai"), ("x-akamai", r".")]),
    Signature("fastly", headers=[("x-served-by", r"cache-"), ("x-fastly", r".")]),
    Signature("aws", headers=[("server", r"amazons3|awselb"), ("x-amz-", r".")],
              html=[r"\.s3[.-]", r"amazonaws\.com"]),
    Signature("gcp", headers=[("server", r"gse|google frontend")], html=[r"googleapis\.com"]),
    Signature("azure", headers=[("x-azure-ref", r".")], html=[r"\.azurewebsites\.net"]),
    Signature("php", headers=[("x-powered-by", r"php"), ("set-cookie", r"phpsessid")]),
    Signature("aspnet", headers=[("x-powered-by", r"asp\.net"), ("x-aspnet-version", r".")],
              cookies=[r"asp\.net_sessionid"]),
    Signature("express", headers=[("x-powered-by", r"express")]),
    Signature("django", cookies=[r"csrftoken", r"django"]),
    Signature("rails", cookies=[r"_session_id", r"_rails"]),
    Signature("laravel", cookies=[r"laravel_session", r"xsrf-token"]),
    Signature("react", html=[r"react(?:-dom)?(?:\.min)?\.js", r"data-reactroot", r"__NEXT_DATA__"]),
    Signature("nextjs", html=[r"/_next/static/", r"__NEXT_DATA__"]),
    Signature("vue", html=[r"vue(?:\.min)?\.js", r"data-v-[0-9a-f]"]),
    Signature("angular", html=[r"ng-version", r"angular(?:\.min)?\.js"]),
    Signature("shopify", headers=[("x-shopify", r".")], html=[r"cdn\.shopify\.com"]),
    Signature("magento", cookies=[r"frontend"], html=[r"/static/version\d+", r"mage/"]),
    Signature("jira", html=[r"atlassian", r"jira"]),
    Signature("confluence", html=[r"confluence"]),
    Signature("jenkins", headers=[("x-jenkins", r".")]),
    Signature("gitlab", html=[r"gitlab", r"/assets/webpack/"]),
    Signature("grafana", html=[r"grafana"]),
    Signature("kibana", html=[r"kibana"]),
    Signature("wordpress_woocommerce", html=[r"/wp-content/plugins/woocommerce"]),
    Signature("graphql", html=[r"/graphql", r"__schema"]),
    Signature("swagger", html=[r"swagger-ui", r"/swagger", r"openapi\.json"]),
]

# ---------------------------------------------------------------------------
# tecnologia -> subdominios probables asociados
# ---------------------------------------------------------------------------
TECH_SUBDOMAINS: dict[str, list[str]] = {
    "wordpress": ["blog", "wp", "news", "cms"],
    "wordpress_woocommerce": ["shop", "store", "checkout", "cart"],
    "drupal": ["cms", "admin", "portal"],
    "joomla": ["cms", "admin"],
    "shopify": ["shop", "store", "checkout", "cdn"],
    "magento": ["shop", "store", "checkout", "m2", "admin"],
    "aws": ["s3", "cdn", "assets", "static", "media", "files", "backup", "elb", "ec2"],
    "gcp": ["storage", "cdn", "api", "gke", "cloud"],
    "azure": ["app", "api", "cdn", "blob", "func", "aks"],
    "cloudflare": ["cdn", "www", "proxy"],
    "akamai": ["cdn", "edge", "static", "media"],
    "fastly": ["cdn", "static", "assets"],
    "php": ["admin", "phpmyadmin", "pma"],
    "aspnet": ["portal", "app", "owa", "sharepoint"],
    "django": ["api", "admin", "app", "dashboard"],
    "rails": ["api", "app", "admin"],
    "laravel": ["api", "app", "admin", "horizon", "telescope"],
    "react": ["app", "admin", "dashboard", "portal"],
    "nextjs": ["app", "www", "api"],
    "vue": ["app", "admin", "dashboard"],
    "angular": ["app", "admin", "portal", "dashboard"],
    "jira": ["jira", "issues", "tickets", "tracker"],
    "confluence": ["confluence", "wiki", "docs", "kb"],
    "jenkins": ["jenkins", "ci", "build", "cicd"],
    "gitlab": ["gitlab", "git", "code", "repo", "ci"],
    "grafana": ["grafana", "metrics", "monitor", "stats", "dashboards"],
    "kibana": ["kibana", "logs", "elk", "elastic"],
    "graphql": ["api", "graphql", "gql"],
    "swagger": ["api", "docs", "developer", "developers", "swagger"],
    "iis": ["owa", "autodiscover", "mail", "exchange", "portal"],
    "nginx": ["www", "static", "assets"],
    "apache": ["www", "old", "legacy"],
    "express": ["api", "app", "node"],
}


def detect_technologies(status: int, headers: dict[str, str], body: str,
                        cookies: list[str]) -> set[str]:
    """Analiza una respuesta y devuelve el conjunto de tecnologías detectadas."""
    found: set[str] = set()
    lower_headers = {k.lower(): (v or "") for k, v in headers.items()}
    body_l = (body or "").lower()
    cookies_l = [c.lower() for c in cookies]

    for sig in SIGNATURES:
        hit = False
        for hname, pattern in sig.headers:
            val = lower_headers.get(hname.lower())
            # cabeceras tipo "x-amz-" se comprueban por prefijo
            if val is None:
                for hk, hv in lower_headers.items():
                    if hk.startswith(hname.lower()) and re.search(pattern, hv, re.I):
                        hit = True
                        break
            elif re.search(pattern, val, re.I):
                hit = True
            if hit:
                break
        if not hit:
            for pattern in sig.cookies:
                if any(re.search(pattern, c, re.I) for c in cookies_l):
                    hit = True
                    break
        if not hit:
            for pattern in sig.meta:
                if re.search(
                    r'<meta[^>]+name=["\']generator["\'][^>]+content=["\'][^"\']*'
                    + pattern, body_l, re.I):
                    hit = True
                    break
        if not hit:
            for pattern in sig.html:
                if re.search(pattern, body_l, re.I):
                    hit = True
                    break
        if hit:
            found.add(sig.name)
    return found


def subdomains_for_technologies(techs: set[str]) -> set[str]:
    """Dado un conjunto de tecnologías, devuelve subdominios probables."""
    labels: set[str] = set()
    for tech in techs:
        labels.update(TECH_SUBDOMAINS.get(tech, []))
    return labels
