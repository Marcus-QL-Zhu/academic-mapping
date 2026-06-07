---
name: academic-mapping
description: Build academic or patent talent maps from one or more papers, patents, DOI links, title/author lists, TSV/CSV seed files, or research leads. Use when Codex should expand scholarly/technical leads into a Neo4j knowledge graph, coauthor/inventor network, topic bridge map, organization clusters, ranked candidate list, and A/B/D-grade public professional contact enrichment for recruiting, expert mapping, technology scouting, or academic landscape analysis.
---

# Academic Mapping

## Overview

Use this skill to turn paper or patent leads into a local Neo4j-ready talent graph and candidate list. The workflow is optimized for recruiting and technical landscape mapping: preserve evidence, avoid unverified people, separate coauthorship from topic similarity, and make every output reproducible.

## Core Workflow

1. **Clarify scope**
   - Confirm domain boundaries and exclusions, such as "include semiconductor memory, exclude display-panel work".
   - Ask whether ranking should prioritize technical core strength, hiring reachability, evidence completeness, or organization coverage.

2. **Collect evidence**
   - Prefer authoritative or structured sources: DOI/Crossref, IEEE/ACM/Springer/Nature pages, Google Patents, Patentscope, Lens, institutional pages, conference proceedings, and publisher metadata.
   - Use web search when leads, authors, affiliations, patent inventors, or current metadata may have changed or are not locally supplied.
   - Keep source URLs for every added work.

3. **Create seed TSV**
   - Use five tab-separated columns:

```text
Person<TAB>Work title<TAB>Organization<TAB>Source URL<TAB>paper|patent
```

   - If organization is unknown, use `Unknown` and keep the source URL.
   - Do not add display/irrelevant-domain papers unless the user explicitly wants them.
   - Normalize obvious aliases only when evidence supports it; otherwise preserve the source name.

4. **Generate project**
   - Use `scripts/academic_map.py` to scaffold or update a project with data, scripts, Cypher files, Docker Compose, outputs, and Browser queries.
   - If starting from an existing mapping project, reuse and patch that local project instead of regenerating from scratch.

5. **Build graph and reports**
   - Generate Neo4j import CSVs under `data/processed/`.
   - Generate recruiting outputs under `outputs/`:
     - `talent_rankings.csv`
     - `company_clusters.csv`
     - `summary.json`

6. **Ask about outreach after first-stage mapping**
   - After the candidate graph, ranking, and first contact enrichment outputs are complete, proactively ask whether the user wants tailored outreach email drafts.
   - Default outreach language is English unless the user specifies another language.
   - If the user wants outreach, collect or infer the client context, role mission, value proposition, confidentiality level, recruiter identity, and preferred tone before drafting.
   - Write email drafts into the contact enrichment CSV as an `email draft` column for A/B-grade contacts only, unless the user explicitly asks for another grade policy.

7. **Enrich public professional contacts when requested**
   - Read `references/contact-enrichment.md` before collecting contact information.
   - Collect only A/B/D-grade public professional contacts:
     - A: person-specific contact on official/institutional/publisher/paper/patent source.
     - B: person-specific contact on public professional profile, homepage, CV, lab page, or GitHub.
     - D: generic lab, department, institution, or company contact when no person-specific contact exists.
   - Do not provide private mobile-number search methods, data-broker workflows, account enumeration, credentialed lookup, deep web, or dark web collection.

8. **Draft tailored outreach emails when requested**
   - Read `references/outreach-email-drafts.md` before drafting.
   - Use candidate-specific evidence from `talent_rankings.csv`, including works, topics, organization, rank, and score.
   - Make each email feel like a targeted invitation, not a generic campaign.
   - Do not invent titles, compensation numbers, client names, private details, or contact data.
   - Keep the client anonymous unless the user explicitly provides and approves the name.
   - Preserve a deterministic template fallback even when using an external LLM.
   - If using an API provider, load keys from environment variables or a user-supplied local `.env`; never copy secrets into the project or commit them.

9. **Import Neo4j**
   - Use Docker Neo4j when local Neo4j is unavailable.
   - Avoid port conflicts; if `7474/7687` are occupied, use `17474/17687` or the next clear pair.
   - Rebuild idempotently: clear graph, load nodes, load direct relationships, then derived bridge relationships.

10. **Verify**
   - Run tests if the generated project has them.
   - Verify Neo4j counts for `Person`, `Work`, `Organization`, `Topic`, `COLLABORATED_WITH`, `WORKS_ON_TOPIC`, `ACTIVE_IN`, and `SHARES_TOPIC_WITH`.
   - Run at least one Browser-friendly path query before telling the user the graph is usable.

## Graph Model

Nodes:

```text
(:Person {name})
(:Organization {name})
(:Work {title, work_type, domain, source, source_url})
(:Topic {name})
```

Direct relationships:

```text
(:Person)-[:AUTHORED_OR_INVENTED]->(:Work)
(:Person)-[:AFFILIATED_WITH]->(:Organization)
(:Work)-[:HAS_TOPIC]->(:Topic)
(:Person)-[:COLLABORATED_WITH {work_count}]-(:Person)
```

Derived bridge relationships:

```text
(:Person)-[:WORKS_ON_TOPIC {work_count}]->(:Topic)
(:Organization)-[:ACTIVE_IN {person_work_count}]->(:Topic)
(:Work)-[:SHARES_TOPIC_WITH {topics}]-(:Work)
```

Interpretation:

- `COLLABORATED_WITH` means the people shared a paper or patent.
- `WORKS_ON_TOPIC`, `ACTIVE_IN`, and `SHARES_TOPIC_WITH` connect otherwise separate coauthor clusters through technical themes.
- Separate coauthor clusters do not prove independent technology development; use topic bridges and citations/patent-family evidence before making that claim.

## Ranking

Use an explainable technical-core score by default:

```text
score =
  works_count * 3
+ topics_count * 2
+ collaborators_count
+ repeat_work_bonus * 4
```

Report the evidence titles and source URLs alongside ranked people.

## Bundled Script

Use `scripts/academic_map.py` for generic project generation:

```powershell
python "$env:CODEX_HOME\skills\academic-mapping\scripts\academic_map.py" `
  --seed ".\seed.tsv" `
  --project ".\academic-sourcing\my-topic-map" `
  --name my-topic-map
```

If `--project` is omitted, the script creates the project under `$ACADEMIC_MAPPING_ROOT\<name>` when `ACADEMIC_MAPPING_ROOT` is set, otherwise under the current working directory:

```text
.\academic-sourcing\<name>
```

After generation:

```powershell
cd .\academic-sourcing\my-topic-map
python .\scripts\graph_builder.py
.\scripts\import_neo4j.ps1
```

Use `scripts/generate_email_drafts.py` inside a generated mapping project after contact enrichment exists:

```powershell
python "$env:CODEX_HOME\skills\academic-mapping\scripts\generate_email_drafts.py" `
  --project ".\academic-sourcing\my-topic-map" `
  --contact-csv ".\outputs\contact_enrichment_topN.csv" `
  --rankings ".\outputs\talent_rankings.csv" `
  --provider template `
  --write
```

For an OpenAI-compatible provider such as MiniMax, set `MINIMAX_API_KEY` or provide a local `.env` path via `--env`. Generated outputs add `email draft` for A/B contacts and leave D/X contacts blank by default.

## Browser Queries

Give the user graph-view queries, not only table queries:

```cypher
MATCH path = (:Person)-[:COLLABORATED_WITH]-(:Person)
RETURN path
LIMIT 300;
```

```cypher
MATCH path = (:Organization)-[:ACTIVE_IN]->(:Topic)<-[:ACTIVE_IN]-(:Organization)
RETURN path
LIMIT 200;
```

```cypher
MATCH path = (:Work)-[:SHARES_TOPIC_WITH]-(:Work)
RETURN path
LIMIT 200;
```

## Quality Rules

- Cite or record every source URL used to add people.
- For contact enrichment, store source URL, contact grade, confidence, and a short evidence note.
- Do not silently mix uncertain aliases; record uncertainty or keep separate names.
- Keep raw seed files under `data/raw/`.
- Make imports idempotent.
- Distinguish coauthor evidence from topic similarity in the final explanation.
- Distinguish public professional contact details from private personal contact details.
- Draft outreach only from supplied or verified evidence; do not add unverified honorifics such as Dr. or Prof.
