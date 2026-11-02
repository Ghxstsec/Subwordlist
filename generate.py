#!/usr/bin/env python3
"""subwordlist - Generador de wordlists de subdominios.

Combina tres fuentes:
  1. Información aportada por el usuario (palabras clave, nombre de empresa...).
  2. Scraping del dominio objetivo (crawl + Certificate Transparency).
  3. Tecnologías detectadas en la web -> subdominios probables asociados.

Luego aplica mutaciones (dev/staging/prod, v1/v2, separadores...) para
producir una wordlist amplia y deduplicada.

USO SOLO AUTORIZADO: ejecútalo contra dominios de tu propiedad o dentro del
scope de un programa de bug bounty / pentest con permiso explícito.
"""
from __future__ import annotations

import argparse
import sys

from fingerprint import subdomains_for_technologies
from generator import build_wordlist
from scraper import Scraper
from utils import clean_subdomain, clean_word, normalize_host


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Genera wordlists de subdominios (recon autorizado).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("domain", help="Dominio objetivo, p.ej. example.com")
    p.add_argument("-o", "--output", help="Fichero de salida (por defecto: stdout)")
    p.add_argument("-w", "--words", nargs="*", default=[],
                   help="Palabras clave aportadas por el usuario (empresa, productos...)")
    p.add_argument("-W", "--wordfile",
                   help="Fichero con palabras del usuario, una por línea")
    p.add_argument("--no-scrape", action="store_true",
                   help="No crawlear el sitio (solo base + palabras del usuario)")
    p.add_argument("--no-crtsh", action="store_true",
                   help="No consultar Certificate Transparency (crt.sh)")
    p.add_argument("--no-common", action="store_true",
                   help="No incluir la lista base de subdominios comunes")
    p.add_argument("--no-mutate", action="store_true",
                   help="No generar mutaciones (dev/staging/v1...)")
    p.add_argument("--combine", action="store_true",
                   help="Combinar palabras entre sí (genera muchas más, con ruido)")
    p.add_argument("--max-pages", type=int, default=40,
                   help="Máximo de páginas a crawlear")
    p.add_argument("--max-tokens", type=int, default=400,
                   help="Máximo de tokens del contenido a incorporar")
    p.add_argument("--http", action="store_true", help="Usar http en vez de https")
    p.add_argument("--fqdn", action="store_true",
                   help="Salida como FQDN (label.dominio) en vez de solo etiquetas")
    p.add_argument("-q", "--quiet", action="store_true", help="Sin logs de progreso")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    domain = normalize_host(args.domain)
    if not domain or "." not in domain:
        print(f"Dominio no válido: {args.domain!r}", file=sys.stderr)
        return 2

    # 1) palabras del usuario
    user_words: set[str] = set()
    for w in args.words:
        cw = clean_word(w)
        if cw:
            user_words.add(cw)
    if args.wordfile:
        try:
            with open(args.wordfile, encoding="utf-8") as fh:
                for ln in fh:
                    cw = clean_word(ln)
                    if cw:
                        user_words.add(cw)
        except OSError as e:
            print(f"No se pudo leer {args.wordfile}: {e}", file=sys.stderr)
            return 2

    # 2) scraping del objetivo
    scraped_labels: set[str] = set()
    scraped_tokens: set[str] = set()
    technologies: set[str] = set()
    discovered_hosts: set[str] = set()
    if not args.no_scrape:
        scraper = Scraper(domain, max_pages=args.max_pages, use_https=not args.http,
                          verbose=not args.quiet, use_crtsh=not args.no_crtsh)
        data = scraper.run()
        scraped_labels = data["labels"]
        scraped_tokens = data["tokens"]
        technologies = data["technologies"]
        discovered_hosts = data["subdomains"]
        if not args.quiet:
            print(f"[+] Tecnologías detectadas: "
                  f"{', '.join(sorted(technologies)) or '(ninguna)'}", file=sys.stderr)
            print(f"[+] Subdominios ya vistos: {len(discovered_hosts)}", file=sys.stderr)

    # 3) subdominios probables según tecnología
    tech_labels = subdomains_for_technologies(technologies)
    if tech_labels and not args.quiet:
        print(f"[+] Subdominios probables por tecnología: "
              f"{', '.join(sorted(tech_labels))}", file=sys.stderr)

    # 4) construir la wordlist
    wordlist = build_wordlist(
        user_words=user_words,
        scraped_labels=scraped_labels,
        scraped_tokens=scraped_tokens,
        tech_labels=tech_labels,
        include_common=not args.no_common,
        do_mutate=not args.no_mutate,
        do_combine=args.combine,
        max_tokens=args.max_tokens,
    )

    # etiquetas de subdominios reales ya descubiertos también entran tal cual
    for host in discovered_hosts:
        if host.endswith("." + domain):
            label = host[: -(len(domain) + 1)]
            cw = clean_subdomain(label)
            if cw:
                wordlist.add(cw)

    ordered = sorted(wordlist)
    if args.fqdn:
        ordered = [f"{w}.{domain}" for w in ordered]

    out_text = "\n".join(ordered) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(out_text)
        if not args.quiet:
            print(f"[+] {len(ordered)} entradas escritas en {args.output}",
                  file=sys.stderr)
    else:
        try:
            sys.stdout.write(out_text)
            sys.stdout.flush()
        except BrokenPipeError:
            # salida truncada por el proceso lector (p.ej. | head): no es error
            try:
                sys.stdout.close()
            except BrokenPipeError:
                pass
            return 0
        if not args.quiet:
            print(f"[+] {len(ordered)} entradas generadas", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
