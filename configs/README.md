# Crawl profiles (`.seospiderconfig`)

Files with the `.seospiderconfig` extension are **binary project files** produced by the **Screaming Frog SEO Spider desktop application**. They are not hand-edited text; you configure a crawl in the desktop UI, then export or save the project as a config file and place it in this directory (or upload to the artifact bucket in cloud environments).

## Profiles referenced by the platform

| File | Purpose |
|------|---------|
| `standard-audit.seospiderconfig` | Balanced technical SEO audit: standard spider settings, typical resource limits, and core issue detection suitable for most sites. |
| `full-js-rendering.seospiderconfig` | Heavier crawl with JavaScript rendering enabled for SPAs and pages that require execution to see real DOM and links. Expect higher CPU, memory, and runtime on workers. |
| `content-focus.seospiderconfig` | Emphasizes on-page and content signals (titles, meta, headings, word counts, indexability) with crawl scope tuned for content QA rather than maximal link discovery. |
| `links-only.seospiderconfig` | Lightweight mode oriented toward link graph discovery and status codes with reduced rendering and content extraction — fastest and smallest footprint on workers. |

## How to add or refresh configs

1. Open **Screaming Frog SEO Spider** on a licensed workstation.
2. Adjust **Configuration** and **Spider** settings for the profile you want.
3. Save or export the **`.seospiderconfig`** file with one of the names above (or a new name, then register it in the app/database).
4. Copy the file into this `configs/` directory for local development, or sync to your private GCS profile prefix for Phase 4+ workers.

Do not commit proprietary or tenant-specific configs if your license or policy forbids it; use `.gitignore` and distribute via secure storage instead.
