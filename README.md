# Academic Mapping

Academic Mapping is a Codex skill for turning papers, patents, DOI links, and author lists into a Neo4j-ready talent map.

It can generate:

- author/inventor and organization graphs;
- coauthor or coinventor relationships;
- topic bridge relationships across otherwise separate teams;
- ranked candidate lists for expert mapping or recruiting research;
- A/B/D-grade public professional contact enrichment guidance.

## Install

Copy this folder into your Codex skills directory:

```powershell
Copy-Item -Recurse . "$env:CODEX_HOME\skills\academic-mapping"
```

If `CODEX_HOME` is unset, use your Codex skills directory, usually `~/.codex/skills`.

## Seed Format

Use one TSV row per person-work-organization assertion:

```text
Person<TAB>Work title<TAB>Organization<TAB>Source URL<TAB>paper|patent
```

Example:

```text
Jane Doe	Vertical Memory Cell Architecture	Example Semiconductor	https://doi.org/10.example/demo	paper
```

Header-based work tables are also accepted when they include fields such as
`title`, `authors`, `organizations`, `source_url`, and `type`. Separate multiple
authors or organizations with semicolons.

## Generate A Project

```powershell
python .\scripts\academic_map.py `
  --seed .\seed.tsv `
  --project .\academic-sourcing\example-map `
  --name example-map
```

Then:

```powershell
cd .\academic-sourcing\example-map
python .\scripts\graph_builder.py
.\scripts\import_neo4j.ps1
```

Generated Neo4j projects use username `neo4j`. Set `NEO4J_PASSWORD` before
running the import script, or use the generated fallback password shown in the
project README.

## Contact Enrichment

The skill supports public professional contact enrichment only:

- A: person-specific contact on official, publisher, paper, patent, or institutional source.
- B: person-specific contact on public professional profile, homepage, lab page, CV, or GitHub.
- D: generic lab, department, institution, or company contact.

It is not intended for private mobile-number lookup, data-broker use, account enumeration, leaked data, deep web, or dark web collection.

## License

MIT
