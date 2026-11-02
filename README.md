# subwordlist

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Recon](https://img.shields.io/badge/uso-recon%20autorizado-red)

Generador de **wordlists de subdominios a medida** para recon en bug bounty y
pentesting. En lugar de usar siempre la misma lista genérica, `subwordlist`
construye una lista adaptada al objetivo combinando lo que tú sabes de él, lo
que expone su propia web y las tecnologías que usa.

> [!WARNING]
> **Uso solo autorizado.** Ejecútalo únicamente contra dominios de tu propiedad
> o dentro del scope de un programa de bug bounty / pentest con permiso
> explícito. El crawl y las consultas a crt.sh generan tráfico atribuible a ti.

---

## ✨ Características

- **Palabras del usuario** — nombre de la empresa, productos, nombres internos,
  marcas... por argumento (`-w`) o desde fichero (`-W`).
- **Scraping del objetivo**
  - Crawl BFS limitado al dominio registrable (HTML, enlaces, `src` de
    scripts/CSS, `action` de formularios, rutas).
  - `robots.txt` y `sitemap.xml`.
  - **Certificate Transparency** vía [crt.sh](https://crt.sh) para descubrir
    subdominios reales de forma pasiva.
- **Fingerprinting de tecnologías → subdominios probables** — detecta ~30
  tecnologías por cabeceras, cookies, `<meta generator>` y firmas en HTML/JS, y
  añade los subdominios que cada stack suele llevar.
- **Mutaciones** del núcleo de alta señal con afijos de entorno (`dev`,
  `staging`, `prod`, `uat`, `v1`, `v2`, `legacy`...) y separadores
  (`devapi`, `dev-api`, `dev_api`, `dev.api`).
- **Modo combinación** (`--combine`) para cruzar palabras entre sí.
- Salida **deduplicada, ordenada y validada** como etiquetas DNS, en formato
  etiqueta (`api`) o FQDN (`api.example.com`).
- Sin resolución DNS: genera la lista y deja el bruteforce a tu herramienta
  favorita (ffuf, puredns, dnsx, massdns, gobuster...).

## 🔧 Cómo funciona

```
 ┌──────────────────┐  ┌────────────────────────┐  ┌──────────────────────┐
 │ Palabras usuario │  │ Scraping del dominio   │  │ Lista base comunes   │
 │  -w / -W         │  │ crawl · robots ·       │  │ data/common_...txt   │
 └────────┬─────────┘  │ sitemap · crt.sh       │  └──────────┬───────────┘
          │            └───────┬───────────┬────┘             │
          │                    │           │                  │
          │            labels / tokens   tecnologías          │
          │                    │           │                  │
          │                    │     ┌─────▼──────────┐       │
          │                    │     │ fingerprint.py │       │
          │                    │     │ tech → subs    │       │
          │                    │     └─────┬──────────┘       │
          ▼                    ▼           ▼                  ▼
        ┌──────────────────────────────────────────────────────────┐
        │ generator.py: núcleo + tokens + mutaciones (+ combine)  │
        │ limpieza → dedupe → orden                               │
        └────────────────────────────┬─────────────────────────────┘
                                     ▼
                              wordlist.txt
```

### Ejemplos de tecnología → subdominios

| Tecnología detectada | Subdominios que se añaden |
|---|---|
| WordPress | `blog`, `wp`, `news`, `cms` |
| AWS | `s3`, `cdn`, `assets`, `static`, `media`, `files`, `backup`... |
| GitLab | `gitlab`, `git`, `code`, `repo`, `ci` |
| Jira / Confluence | `jira`, `issues`, `tickets` / `confluence`, `wiki`, `docs`, `kb` |
| Jenkins | `jenkins`, `ci`, `build`, `cicd` |
| Grafana / Kibana | `grafana`, `metrics`, `monitor` / `kibana`, `logs`, `elk` |
| IIS | `owa`, `autodiscover`, `mail`, `exchange`, `portal` |
| Laravel | `api`, `app`, `admin`, `horizon`, `telescope` |
| Swagger / GraphQL | `api`, `docs`, `developer`, `swagger` / `graphql`, `gql` |

El mapa completo está en [`fingerprint.py`](fingerprint.py) (`TECH_SUBDOMAINS`)
y es fácil de ampliar.

## 📦 Instalación

Requiere **Python 3.10+**.

```bash
git clone https://github.com/<tu-usuario>/subwordlist.git
cd subwordlist
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

`tldextract` es opcional pero recomendado: permite separar bien dominios con TLD
compuesto (`.co.uk`, `.com.ar`...). Sin él se usa un fallback de "últimas dos
etiquetas".

## 🚀 Uso

```bash
# Básico: scrapea example.com y saca la wordlist por stdout
python generate.py example.com

# Con palabras propias y salida a fichero
python generate.py example.com -w acme widgets corp -o wordlist.txt

# Palabras desde fichero, sin crt.sh, salida como FQDN
python generate.py example.com -W keywords.txt --no-crtsh --fqdn -o subs.txt

# Sin tocar la web: solo lista base + tus palabras + mutaciones
python generate.py example.com --no-scrape -w acme -o quick.txt

# Modo agresivo: combina palabras entre sí (mucho más grande, más ruido)
python generate.py example.com --combine -o big.txt
```

Los logs de progreso van a `stderr` y la wordlist a `stdout`, así que puedes
redirigir o encadenar sin mezclarlos (`python generate.py target.com > wl.txt`).
Usa `-q` para silenciar los logs.

### Opciones

| Flag | Descripción | Por defecto |
|------|-------------|-------------|
| `domain` | Dominio objetivo (p.ej. `example.com`) | — |
| `-w, --words` | Palabras clave del usuario (varias) | — |
| `-W, --wordfile` | Fichero con palabras, una por línea | — |
| `-o, --output` | Fichero de salida | stdout |
| `--no-scrape` | No crawlear el sitio | off |
| `--no-crtsh` | No consultar Certificate Transparency | off |
| `--no-common` | No incluir la lista base de subdominios comunes | off |
| `--no-mutate` | No generar mutaciones | off |
| `--combine` | Combinar palabras entre sí (agresivo) | off |
| `--max-pages` | Máximo de páginas a crawlear | `40` |
| `--max-tokens` | Máximo de tokens del contenido a incorporar | `400` |
| `--http` | Usar http en vez de https | off |
| `--fqdn` | Salida como `label.dominio` | off |
| `-q, --quiet` | Sin logs de progreso | off |

### Ejemplo de salida

```text
$ python generate.py example.com -w acme -o wl.txt
[+] Tecnologías detectadas: cloudflare, nginx, wordpress
[+] Subdominios ya vistos: 12
[+] Subdominios probables por tecnología: assets, blog, cdn, cms, news, proxy, static, wp, www
[+] 31842 entradas escritas en wl.txt
```

## 🎯 Flujo típico en bug bounty

```bash
# 1. Genera la wordlist a partir del dominio en scope
python generate.py target.com -w marca producto -o wl.txt

# 2. Pásala a tu resolver / bruteforcer
puredns bruteforce wl.txt target.com -r resolvers.txt
# o
ffuf -w wl.txt -u https://FUZZ.target.com -mc all
```

## 🗂️ Estructura

```
subwordlist/
├── generate.py              # CLI principal
├── scraper.py               # crawl + robots/sitemap + crt.sh + extracción
├── fingerprint.py           # firmas de tecnologías + mapa tech → subdominios
├── generator.py             # mutaciones, combinaciones y ensamblado final
├── utils.py                 # parsing de dominios y normalización de etiquetas
├── data/
│   └── common_subdomains.txt  # lista base (~200 subdominios comunes)
├── requirements.txt
└── README.md
```

## 🧩 Personalización

- **Lista base**: edita `data/common_subdomains.txt` (una etiqueta por línea,
  `#` para comentarios).
- **Nuevas tecnologías**: añade un `Signature(...)` en `SIGNATURES` y su entrada
  en `TECH_SUBDOMAINS` dentro de `fingerprint.py`.
- **Afijos de entorno**: modifica `ENV_AFFIXES` en `generator.py`.

## 📝 Notas

- La herramienta **no resuelve DNS**: solo produce la wordlist. Separar
  generación y resolución es intencionado.
- Las mutaciones se aplican solo al núcleo de alta señal (palabras del usuario,
  subdominios descubiertos, subdominios por tecnología y lista base), no a todos
  los tokens scrapeados, para no disparar el tamaño con ruido.
- Con `--combine` la lista puede crecer mucho; úsalo con resolvers rápidos.

## ⚖️ Disclaimer

Esta herramienta se proporciona con fines educativos y para pruebas de seguridad
autorizadas. El autor no se hace responsable del uso indebido. Respeta siempre
el scope y las reglas de cada programa.

## 📄 Licencia

[MIT](LICENSE)
