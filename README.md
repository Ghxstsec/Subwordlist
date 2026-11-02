# subwordlist

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Recon](https://img.shields.io/badge/use-authorized%20recon%20only-red)

**Target-tailored subdomain wordlist generator** for bug bounty and pentesting
recon. Instead of always throwing the same generic list at every target,
`subwordlist` builds a list adapted to the target by combining what you know
about it, what its own website exposes, and the technologies it runs on.

> [!WARNING]
> **Authorized use only.** Run it only against domains you own or that are in
> scope of a bug bounty program / pentest with explicit permission. Crawling
> and crt.sh queries generate traffic attributable to you.

---

## ✨ Features

- **User-supplied keywords** — company name, products, internal names,
  brands... via argument (`-w`) or from a file (`-W`).
- **Target scraping**
  - BFS crawl restricted to the registrable domain (HTML, links, script/CSS
    `src`, form `action`, paths).
  - `robots.txt` and `sitemap.xml`.
  - **Certificate Transparency** via [crt.sh](https://crt.sh) to passively
    discover real subdomains.
- **Technology fingerprinting → likely subdomains** — detects ~30 technologies
  from headers, cookies, `<meta generator>` and HTML/JS signatures, then adds
  the subdomains each stack typically comes with.
- **Mutations** of the high-signal core with environment affixes (`dev`,
  `staging`, `prod`, `uat`, `v1`, `v2`, `legacy`...) and separators
  (`devapi`, `dev-api`, `dev_api`, `dev.api`).
- **Combine mode** (`--combine`) to cross words with each other.
- **Deduplicated, sorted and DNS-validated** output, as bare labels (`api`) or
  FQDNs (`api.example.com`).
- No DNS resolution: it generates the list and leaves bruteforcing to your
  favorite tool (ffuf, puredns, dnsx, massdns, gobuster...).

## 🔧 How it works

```
 ┌──────────────────┐  ┌────────────────────────┐  ┌──────────────────────┐
 │ User keywords    │  │ Domain scraping        │  │ Common base list     │
 │  -w / -W         │  │ crawl · robots ·       │  │ data/common_...txt   │
 └────────┬─────────┘  │ sitemap · crt.sh       │  └──────────┬───────────┘
          │            └───────┬───────────┬────┘             │
          │                    │           │                  │
          │            labels / tokens   technologies         │
          │                    │           │                  │
          │                    │     ┌─────▼──────────┐       │
          │                    │     │ fingerprint.py │       │
          │                    │     │ tech → subs    │       │
          │                    │     └─────┬──────────┘       │
          ▼                    ▼           ▼                  ▼
        ┌──────────────────────────────────────────────────────────┐
        │ generator.py: core + tokens + mutations (+ combine)      │
        │ cleanup → dedupe → sort                                  │
        └────────────────────────────┬─────────────────────────────┘
                                     ▼
                              wordlist.txt
```

### Technology → subdomain examples

| Detected technology | Subdomains added |
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

The full map lives in [`fingerprint.py`](fingerprint.py) (`TECH_SUBDOMAINS`)
and is easy to extend.

## 📦 Installation

Requires **Python 3.10+**.

```bash
git clone https://github.com/Ghxstsec/Subwordlist.git
cd Subwordlist
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

`tldextract` is optional but recommended: it correctly splits domains with
multi-part TLDs (`.co.uk`, `.com.ar`...). Without it, a "last two labels"
fallback is used.

## 🚀 Usage

```bash
# Basic: scrape example.com and print the wordlist to stdout
python generate.py example.com

# With your own keywords, written to a file
python generate.py example.com -w acme widgets corp -o wordlist.txt

# Keywords from a file, no crt.sh, FQDN output
python generate.py example.com -W keywords.txt --no-crtsh --fqdn -o subs.txt

# Don't touch the website: base list + your keywords + mutations only
python generate.py example.com --no-scrape -w acme -o quick.txt

# Aggressive mode: combine words with each other (much bigger, noisier)
python generate.py example.com --combine -o big.txt
```

Progress logs go to `stderr` and the wordlist to `stdout`, so you can redirect
or pipe without mixing them (`python generate.py target.com > wl.txt`).
Use `-q` to silence the logs.

### Options

| Flag | Description | Default |
|------|-------------|---------|
| `domain` | Target domain (e.g. `example.com`) | — |
| `-w, --words` | User keywords (multiple) | — |
| `-W, --wordfile` | File with keywords, one per line | — |
| `-o, --output` | Output file | stdout |
| `--no-scrape` | Don't crawl the site | off |
| `--no-crtsh` | Don't query Certificate Transparency | off |
| `--no-common` | Don't include the common subdomains base list | off |
| `--no-mutate` | Don't generate mutations | off |
| `--combine` | Combine words with each other (aggressive) | off |
| `--max-pages` | Maximum pages to crawl | `40` |
| `--max-tokens` | Maximum content tokens to include | `400` |
| `--http` | Use http instead of https | off |
| `--fqdn` | Output as `label.domain` | off |
| `-q, --quiet` | No progress logs | off |

## 🎯 Typical bug bounty workflow

```bash
# 1. Generate the wordlist from the in-scope domain
python generate.py target.com -w brand product -o wl.txt

# 2. Feed it to your resolver / bruteforcer
puredns bruteforce wl.txt target.com -r resolvers.txt
# or
ffuf -w wl.txt -u https://FUZZ.target.com -mc all
```

## 🗂️ Project structure

```
subwordlist/
├── generate.py              # main CLI
├── scraper.py               # crawl + robots/sitemap + crt.sh + extraction
├── fingerprint.py           # technology signatures + tech → subdomain map
├── generator.py             # mutations, combinations and final assembly
├── utils.py                 # domain parsing and label normalization
├── data/
│   └── common_subdomains.txt  # base list (~200 common subdomains)
├── requirements.txt
└── README.md
```

## 🧩 Customization

- **Base list**: edit `data/common_subdomains.txt` (one label per line, `#` for
  comments).
- **New technologies**: add a `Signature(...)` to `SIGNATURES` and its entry to
  `TECH_SUBDOMAINS` in `fingerprint.py`.
- **Environment affixes**: tweak `ENV_AFFIXES` in `generator.py`.

## 📝 Notes

- The tool **does not resolve DNS**: it only produces the wordlist. Keeping
  generation and resolution separate is intentional.
- Mutations are applied only to the high-signal core (user keywords,
  discovered subdomains, technology-derived subdomains and the base list), not
  to every scraped token, to keep noise and size under control.
- With `--combine` the list can grow a lot; use it with fast resolvers.
- CLI log messages are currently in Spanish.

## ⚖️ Disclaimer

This tool is provided for educational purposes and authorized security testing
only. The author is not responsible for any misuse. Always respect the scope and
rules of each program.

## 📄 License

[MIT](LICENSE)
