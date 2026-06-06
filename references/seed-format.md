# Academic Mapping Seed Format

Use one TSV row per person-work-organization assertion.

```text
Person<TAB>Work title<TAB>Organization<TAB>Source URL<TAB>paper|patent
```

Rules:

- Person is an author, inventor, or named technical participant.
- Work title is the paper, patent, standard, or technical report title.
- Organization should be the affiliation from the source when available.
- Source URL should be DOI, patent URL, publisher URL, or authoritative metadata page.
- Type is `paper` or `patent`; use `paper` for conference proceedings and journal articles.

Example:

```text
Jane Doe	Vertical Memory Cell Architecture	Example Semiconductor	https://doi.org/10.example/demo	paper
```

The scaffolded parser also accepts a header-based work table with columns such as
`title`, `authors`, `organizations`, `source_url`, and `type`. Separate multiple
authors or organizations with semicolons.
