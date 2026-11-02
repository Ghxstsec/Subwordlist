"""Utilidades compartidas: parsing de dominios y normalización."""
from __future__ import annotations

import re

# Etiqueta DNS válida: letras, dígitos y guion (no al principio/final), 1-63 chars.
_LABEL_RE = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")

# tldextract es opcional: da un split correcto de dominios registrables
# (maneja TLDs de varias partes como .co.uk). Si no está, usamos un fallback.
try:
    import tldextract  # type: ignore

    _EXTRACT = tldextract.TLDExtract(suffix_list_urls=())  # sin red: usa snapshot

    def split_domain(host: str) -> tuple[str, str]:
        """Devuelve (subdominio, dominio_registrable). Ej: a.b.example.co.uk ->
        ('a.b', 'example.co.uk')."""
        ext = _EXTRACT(host)
        registrable = ".".join(p for p in (ext.domain, ext.suffix) if p)
        return ext.subdomain, registrable

except Exception:  # pragma: no cover - fallback sin dependencia
    def split_domain(host: str) -> tuple[str, str]:
        host = host.strip(".").lower()
        parts = host.split(".")
        if len(parts) <= 2:
            return "", host
        registrable = ".".join(parts[-2:])
        return ".".join(parts[:-2]), registrable


def normalize_host(host: str) -> str:
    """Limpia un host: minúsculas, sin puerto, sin punto final, sin wildcard."""
    host = host.strip().lower()
    host = host.lstrip("*.")  # *.example.com -> example.com
    host = host.split("/")[0]
    host = host.split(":")[0]  # quita puerto
    return host.strip(".")


def is_valid_label(label: str) -> bool:
    """True si `label` es una etiqueta DNS válida. Los numéricos se aceptan
    solo si son cortos (p.ej. v2 '02'), para no meter ruido de dígitos largos."""
    if not _LABEL_RE.match(label):
        return False
    if label.isdigit():
        return len(label) <= 4
    return True


def clean_word(word: str) -> str | None:
    """Convierte un token arbitrario en una etiqueta DNS candidata, o None."""
    word = word.strip().lower()
    word = re.sub(r"[^a-z0-9-]", "-", word)  # separadores -> guion
    word = re.sub(r"-{2,}", "-", word).strip("-")
    if not word or len(word) > 63:
        return None
    if not re.match(r"^[a-z0-9-]+$", word):
        return None
    return word


def clean_subdomain(name: str) -> str | None:
    """Como clean_word, pero conserva la estructura del subdominio: los puntos
    separan etiquetas (p.ej. 'dev.api') y se permite '_' dentro de cada una
    (p.ej. 'dev_api'). Cada etiqueta se limpia por separado."""
    labels = []
    for part in name.strip().lower().strip(".").split("."):
        part = re.sub(r"[^a-z0-9_-]", "-", part)
        part = re.sub(r"-{2,}", "-", part).strip("-_")
        if not part or len(part) > 63:
            return None
        labels.append(part)
    if not labels:
        return None
    out = ".".join(labels)
    return out if len(out) <= 253 else None
