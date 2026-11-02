"""Generación de la wordlist final: combina bases, tokens y mutaciones."""
from __future__ import annotations

import itertools
import os

from utils import clean_subdomain, clean_word

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# Afijos típicos de entornos/roles que se combinan con las bases.
ENV_AFFIXES = [
    "dev", "development", "staging", "stage", "stg", "test", "testing", "qa",
    "uat", "prod", "production", "preprod", "demo", "sandbox", "beta", "alpha",
    "int", "internal", "external", "new", "old", "legacy", "temp", "backup",
    "bak", "v1", "v2", "v3", "1", "2", "01", "02",
]

SEPARATORS = ["", "-", ".", "_"]


def load_base(filename: str) -> list[str]:
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")]


def mutate(words: set[str], *, affixes: list[str] = ENV_AFFIXES,
           separators: list[str] = SEPARATORS, max_results: int | None = None) -> set[str]:
    """Genera permutaciones base<sep>afijo y afijo<sep>base."""
    out: set[str] = set()
    for base in words:
        for aff in affixes:
            for sep in separators:
                if sep == ".":
                    # el punto crea un subdominio anidado: válido pero más raro
                    out.add(f"{aff}.{base}")
                    out.add(f"{base}.{aff}")
                else:
                    out.add(f"{base}{sep}{aff}")
                    out.add(f"{aff}{sep}{base}")
        if max_results and len(out) >= max_results:
            break
    return out


def combine(bases: set[str], extra: set[str], *, separators: list[str] = ("-", "")) -> set[str]:
    """Combina dos conjuntos de palabras entre sí (base-extra)."""
    out: set[str] = set()
    for a, b in itertools.product(bases, extra):
        if a == b:
            continue
        for sep in separators:
            out.add(f"{a}{sep}{b}")
    return out


def build_wordlist(*, user_words: set[str] | None = None,
                   scraped_labels: set[str] | None = None,
                   scraped_tokens: set[str] | None = None,
                   tech_labels: set[str] | None = None,
                   include_common: bool = True,
                   do_mutate: bool = True,
                   do_combine: bool = False,
                   max_tokens: int = 400) -> set[str]:
    """Orquesta todas las fuentes y devuelve el conjunto final de etiquetas DNS."""
    user_words = user_words or set()
    scraped_labels = scraped_labels or set()
    scraped_tokens = scraped_tokens or set()
    tech_labels = tech_labels or set()

    result: set[str] = set()

    common = set(load_base("common_subdomains.txt")) if include_common else set()
    result |= common

    # núcleo de "alta señal": lo que aporta el usuario, lo descubierto scrapeando
    # y lo derivado de la tecnología detectada.
    core = set()
    for group in (user_words, scraped_labels, tech_labels):
        for w in group:
            cw = clean_word(w)
            if cw:
                core.add(cw)
    result |= core

    # tokens sueltos del contenido (limitados para no explotar el tamaño)
    tokens = set()
    for w in sorted(scraped_tokens, key=len)[:max_tokens]:
        cw = clean_word(w)
        if cw and 2 < len(cw) <= 20:
            tokens.add(cw)
    result |= tokens

    if do_mutate:
        # muta solo el núcleo de alta señal, no todos los tokens (evita ruido)
        result |= mutate(core | common)

    if do_combine and core:
        result |= combine(core, core | tech_labels)

    # limpieza final
    # clean_subdomain conserva '.' y '_' de las mutaciones (clean_word los
    # convertiría en '-')
    cleaned = {clean_subdomain(w) for w in result}
    return {w for w in cleaned if w}
