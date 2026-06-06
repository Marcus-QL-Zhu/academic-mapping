from __future__ import annotations

import argparse
import os
import shutil
import textwrap
from pathlib import Path


DEFAULT_PROJECT_ROOT = Path(os.environ.get("ACADEMIC_MAPPING_ROOT", Path.cwd() / "academic-sourcing"))


GRAPH_BUILDER = r'''
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path


@dataclass(frozen=True)
class SourceRow:
    person: str
    title: str
    organization: str
    source_url: str
    source_kind: str


@dataclass
class Graph:
    people: set[str]
    organizations: set[str]
    works: dict[str, dict[str, str]]
    topics: set[str]
    person_organizations: set[tuple[str, str]]
    person_works: set[tuple[str, str]]
    work_topics: set[tuple[str, str]]
    collaborations: Counter[tuple[str, str]]


DEFAULT_TOPIC_RULES = (
    ("3D DRAM", ("3d dram", "three-dimensional dynamic random-access memory", "dynamic random-access memory")),
    ("DRAM", ("dram",)),
    ("Memory applications", ("memory application", "memory device", "memory cell")),
    ("Vertical transistor", ("vertical transistor", "vertical channel")),
    ("Channel-all-around", ("channel-all-around", "caa")),
    ("2T0C", ("2t0c", "two-transistor", "two transistor")),
    ("Dual-gate", ("dual-gate", "dual gate", "double-surrounding-gate")),
    ("Thermal stability", ("thermal stability",)),
    ("High-density", ("high-density", "high density")),
    ("Low-power", ("low-power", "low power")),
    ("TCAD simulation", ("tcad",)),
)


def normalize_text(value: str) -> str:
    value = value.lstrip("\ufeff")
    replacements = {
        "4F" + chr(0x00B2): "4F2",
        "4F" + chr(0x864F): "4F2",
        "<sup>2</sup>": "2",
        chr(0x03BC): "u",
        chr(0x2103): "C",
    }
    out = value
    for old, new in replacements.items():
        out = out.replace(old, new)
    return " ".join(out.split())


def split_values(value: str) -> list[str]:
    normalized = value.replace("|", ";").replace(chr(0xFF1B), ";")
    return [part.strip() for part in normalized.split(";") if part.strip()]


def parse_tsv(path: Path) -> list[SourceRow]:
    rows: list[SourceRow] = []
    with path.open(encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter="\t")
        header: list[str] | None = None
        for line in reader:
            if not line or all(not cell.strip() for cell in line):
                continue
            normalized_line = [normalize_text(cell.strip()) for cell in line]
            lowered = [cell.lower() for cell in normalized_line]
            if header is None and any(cell in {"person", "authors", "title", "work_id"} for cell in lowered):
                header = lowered
                continue
            if header:
                row = {key: normalized_line[index] for index, key in enumerate(header) if index < len(normalized_line)}
                title = row.get("title") or row.get("work title") or row.get("work_title") or row.get("work") or ""
                source_url = row.get("source_url") or row.get("source url") or row.get("url") or "local-seed"
                source_kind = row.get("type") or row.get("source_kind") or row.get("kind") or "paper"
                people = split_values(row.get("authors") or row.get("person") or row.get("inventors") or "")
                organizations = split_values(row.get("organizations") or row.get("organization") or row.get("affiliations") or "")
                for index, person in enumerate(people):
                    organization = organizations[index] if index < len(organizations) else (organizations[0] if organizations else "Unknown")
                    rows.append(SourceRow(person, title, organization or "Unknown", source_url, source_kind or "paper"))
                continue
            if len(line) not in (3, 5):
                raise ValueError(f"Expected 3 or 5 TSV columns, got {len(line)} in {path}: {line}")
            person, title, organization = (normalize_text(cell.strip()) for cell in line[:3])
            source_url = line[3].strip() if len(line) == 5 else "local-seed"
            source_kind = line[4].strip() if len(line) == 5 else "paper"
            rows.append(SourceRow(person, title, organization or "Unknown", source_url, source_kind or "paper"))
    return rows


def parse_inputs(paths: list[Path]) -> list[SourceRow]:
    rows: list[SourceRow] = []
    for path in paths:
        if path.is_dir():
            for tsv in sorted(path.glob("*.tsv")):
                rows.extend(parse_tsv(tsv))
        else:
            rows.extend(parse_tsv(path))
    return rows


def extract_topics(title: str) -> set[str]:
    lowered = title.lower()
    topics = {topic for topic, needles in DEFAULT_TOPIC_RULES if any(needle in lowered for needle in needles)}
    words = [w.strip("()[],:;/") for w in title.split()]
    for word in words:
        upper = word.upper()
        if len(upper) >= 3 and upper.isascii() and upper.isalnum() and not upper.isdigit():
            if upper not in {"THE", "AND", "FOR", "WITH", "FROM"}:
                topics.add(upper)
    return topics or {"Uncategorized technical topic"}


def infer_domain(title: str) -> str:
    lowered = title.lower()
    if "display" in lowered or "panel" in lowered:
        return "display-review-needed"
    if "memory" in lowered or "dram" in lowered:
        return "memory-device"
    if "transistor" in lowered or "fet" in lowered:
        return "semiconductor-device"
    return "technical-work"


def build_graph(rows: list[SourceRow]) -> Graph:
    people: set[str] = set()
    organizations: set[str] = set()
    works: dict[str, dict[str, str]] = {}
    topics: set[str] = set()
    person_organizations: set[tuple[str, str]] = set()
    person_works: set[tuple[str, str]] = set()
    work_topics: set[tuple[str, str]] = set()
    collaborations: Counter[tuple[str, str]] = Counter()
    work_people: dict[str, set[str]] = defaultdict(set)

    for row in rows:
        people.add(row.person)
        organizations.add(row.organization)
        works[row.title] = {
            "title": row.title,
            "work_type": row.source_kind,
            "domain": infer_domain(row.title),
            "source": "seed",
            "source_url": row.source_url,
        }
        person_organizations.add((row.person, row.organization))
        person_works.add((row.person, row.title))
        work_people[row.title].add(row.person)
        for topic in extract_topics(row.title):
            topics.add(topic)
            work_topics.add((row.title, topic))

    for people_for_work in work_people.values():
        for left, right in combinations(sorted(people_for_work), 2):
            collaborations[(left, right)] += 1

    return Graph(people, organizations, works, topics, person_organizations, person_works, work_topics, collaborations)


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def derived_rows(graph: Graph) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    topics_by_work: dict[str, set[str]] = defaultdict(set)
    for work, topic in graph.work_topics:
        topics_by_work[work].add(topic)

    person_topic_counts: Counter[tuple[str, str]] = Counter()
    for person, work in graph.person_works:
        for topic in topics_by_work[work]:
            person_topic_counts[(person, topic)] += 1

    orgs_by_person: dict[str, set[str]] = defaultdict(set)
    for person, org in graph.person_organizations:
        orgs_by_person[person].add(org)

    org_topic_counts: Counter[tuple[str, str]] = Counter()
    for (person, topic), count in person_topic_counts.items():
        for org in orgs_by_person[person]:
            org_topic_counts[(org, topic)] += count

    works_by_topic: dict[str, set[str]] = defaultdict(set)
    for work, topic in graph.work_topics:
        works_by_topic[topic].add(work)

    work_links = []
    for topic, works in sorted(works_by_topic.items()):
        for left, right in combinations(sorted(works), 2):
            work_links.append({"work_a": left, "work_b": right, "topic": topic})

    person_topics = [
        {"person": person, "topic": topic, "work_count": count}
        for (person, topic), count in sorted(person_topic_counts.items())
    ]
    org_topics = [
        {"organization": org, "topic": topic, "person_work_count": count}
        for (org, topic), count in sorted(org_topic_counts.items())
    ]
    return person_topics, org_topics, work_links


def rank_people(graph: Graph) -> list[dict[str, object]]:
    works_by_person: dict[str, set[str]] = defaultdict(set)
    topics_by_work: dict[str, set[str]] = defaultdict(set)
    topics_by_person: dict[str, set[str]] = defaultdict(set)
    orgs_by_person: dict[str, set[str]] = defaultdict(set)
    collaborators_by_person: dict[str, set[str]] = defaultdict(set)

    for work, topic in graph.work_topics:
        topics_by_work[work].add(topic)
    for person, work in graph.person_works:
        works_by_person[person].add(work)
        topics_by_person[person].update(topics_by_work[work])
    for person, org in graph.person_organizations:
        orgs_by_person[person].add(org)
    for (left, right), _count in graph.collaborations.items():
        collaborators_by_person[left].add(right)
        collaborators_by_person[right].add(left)

    rows = []
    for person in graph.people:
        works_count = len(works_by_person[person])
        topics_count = len(topics_by_person[person])
        collaborators_count = len(collaborators_by_person[person])
        repeat_bonus = 1 if works_count > 1 else 0
        score = works_count * 3 + topics_count * 2 + collaborators_count + repeat_bonus * 4
        rows.append({
            "person": person,
            "organization": "; ".join(sorted(orgs_by_person[person])),
            "score": score,
            "works_count": works_count,
            "topics_count": topics_count,
            "collaborators_count": collaborators_count,
            "repeat_work_bonus": repeat_bonus,
            "topics": "; ".join(sorted(topics_by_person[person])),
            "works": "; ".join(sorted(works_by_person[person])),
            "collaborators": "; ".join(sorted(collaborators_by_person[person])),
        })
    return sorted(rows, key=lambda row: (-int(row["score"]), -int(row["works_count"]), str(row["person"])))


def export_graph(graph: Graph, processed_dir: Path, outputs_dir: Path) -> None:
    person_topics, org_topics, work_links = derived_rows(graph)
    _write_csv(processed_dir / "people.csv", [{"name": x} for x in sorted(graph.people)], ["name"])
    _write_csv(processed_dir / "organizations.csv", [{"name": x} for x in sorted(graph.organizations)], ["name"])
    _write_csv(processed_dir / "topics.csv", [{"name": x} for x in sorted(graph.topics)], ["name"])
    _write_csv(processed_dir / "works.csv", [graph.works[x] for x in sorted(graph.works)], ["title", "work_type", "domain", "source", "source_url"])
    _write_csv(processed_dir / "person_works.csv", [{"person": a, "work": b} for a, b in sorted(graph.person_works)], ["person", "work"])
    _write_csv(processed_dir / "person_organizations.csv", [{"person": a, "organization": b} for a, b in sorted(graph.person_organizations)], ["person", "organization"])
    _write_csv(processed_dir / "work_topics.csv", [{"work": a, "topic": b} for a, b in sorted(graph.work_topics)], ["work", "topic"])
    _write_csv(processed_dir / "collaborations.csv", [{"person_a": a, "person_b": b, "work_count": c} for (a, b), c in sorted(graph.collaborations.items())], ["person_a", "person_b", "work_count"])
    _write_csv(processed_dir / "person_topics.csv", person_topics, ["person", "topic", "work_count"])
    _write_csv(processed_dir / "organization_topics.csv", org_topics, ["organization", "topic", "person_work_count"])
    _write_csv(processed_dir / "work_topic_links.csv", work_links, ["work_a", "work_b", "topic"])

    rankings = rank_people(graph)
    _write_csv(outputs_dir / "talent_rankings.csv", rankings, ["person", "organization", "score", "works_count", "topics_count", "collaborators_count", "repeat_work_bonus", "topics", "works", "collaborators"])

    clusters = defaultdict(list)
    for row in rankings:
        clusters[row["organization"]].append(row)
    _write_csv(outputs_dir / "company_clusters.csv", [
        {"organization": org, "people_count": len(rows), "top_people": "; ".join(str(r["person"]) for r in rows[:5]), "avg_score": round(sum(int(r["score"]) for r in rows) / len(rows), 2)}
        for org, rows in sorted(clusters.items())
    ], ["organization", "people_count", "top_people", "avg_score"])

    summary = {
        "people_count": len(graph.people),
        "organizations_count": len(graph.organizations),
        "works_count": len(graph.works),
        "topics_count": len(graph.topics),
        "collaboration_edges_count": len(graph.collaborations),
        "person_topic_edges_count": len(person_topics),
        "organization_topic_edges_count": len(org_topics),
        "work_topic_link_edges_count": len(work_links),
        "top_people": [row["person"] for row in rankings[:10]],
    }
    outputs_dir.mkdir(parents=True, exist_ok=True)
    (outputs_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, action="append", default=None)
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--outputs-dir", type=Path, default=Path("outputs"))
    args = parser.parse_args()
    rows = parse_inputs(args.input or [Path("data/raw")])
    graph = build_graph(rows)
    export_graph(graph, args.processed_dir, args.outputs_dir)
    print(f"Exported {len(graph.people)} people, {len(graph.works)} works, {len(graph.collaborations)} collaboration edges.")


if __name__ == "__main__":
    main()
'''


SCHEMA_CYPHER = r'''
CREATE CONSTRAINT person_name IF NOT EXISTS FOR (p:Person) REQUIRE p.name IS UNIQUE;
CREATE CONSTRAINT organization_name IF NOT EXISTS FOR (o:Organization) REQUIRE o.name IS UNIQUE;
CREATE CONSTRAINT work_title IF NOT EXISTS FOR (w:Work) REQUIRE w.title IS UNIQUE;
CREATE CONSTRAINT topic_name IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE;

MATCH (n) DETACH DELETE n;

LOAD CSV WITH HEADERS FROM 'file:///people.csv' AS row MERGE (:Person {name: row.name});
LOAD CSV WITH HEADERS FROM 'file:///organizations.csv' AS row MERGE (:Organization {name: row.name});
LOAD CSV WITH HEADERS FROM 'file:///topics.csv' AS row MERGE (:Topic {name: row.name});

LOAD CSV WITH HEADERS FROM 'file:///works.csv' AS row
MERGE (w:Work {title: row.title})
SET w.work_type = row.work_type, w.domain = row.domain, w.source = row.source, w.source_url = row.source_url;

LOAD CSV WITH HEADERS FROM 'file:///person_organizations.csv' AS row
MATCH (p:Person {name: row.person}) MATCH (o:Organization {name: row.organization})
MERGE (p)-[:AFFILIATED_WITH]->(o);

LOAD CSV WITH HEADERS FROM 'file:///person_works.csv' AS row
MATCH (p:Person {name: row.person}) MATCH (w:Work {title: row.work})
MERGE (p)-[:AUTHORED_OR_INVENTED]->(w);

LOAD CSV WITH HEADERS FROM 'file:///work_topics.csv' AS row
MATCH (w:Work {title: row.work}) MATCH (t:Topic {name: row.topic})
MERGE (w)-[:HAS_TOPIC]->(t);

LOAD CSV WITH HEADERS FROM 'file:///collaborations.csv' AS row
MATCH (a:Person {name: row.person_a}) MATCH (b:Person {name: row.person_b})
MERGE (a)-[r:COLLABORATED_WITH]-(b) SET r.work_count = toInteger(row.work_count);

LOAD CSV WITH HEADERS FROM 'file:///person_topics.csv' AS row
MATCH (p:Person {name: row.person}) MATCH (t:Topic {name: row.topic})
MERGE (p)-[r:WORKS_ON_TOPIC]->(t) SET r.work_count = toInteger(row.work_count);

LOAD CSV WITH HEADERS FROM 'file:///organization_topics.csv' AS row
MATCH (o:Organization {name: row.organization}) MATCH (t:Topic {name: row.topic})
MERGE (o)-[r:ACTIVE_IN]->(t) SET r.person_work_count = toInteger(row.person_work_count);

LOAD CSV WITH HEADERS FROM 'file:///work_topic_links.csv' AS row
MATCH (a:Work {title: row.work_a}) MATCH (b:Work {title: row.work_b})
MERGE (a)-[r:SHARES_TOPIC_WITH]-(b)
ON CREATE SET r.topics = [row.topic]
ON MATCH SET r.topics = CASE WHEN row.topic IN r.topics THEN r.topics ELSE r.topics + row.topic END;
'''


BROWSER_QUERIES = r'''
MATCH path = (:Person)-[:COLLABORATED_WITH]-(:Person)
RETURN path
LIMIT 300;

MATCH path = (:Organization)-[:ACTIVE_IN]->(:Topic)<-[:ACTIVE_IN]-(:Organization)
RETURN path
LIMIT 200;

MATCH path = (:Work)-[:SHARES_TOPIC_WITH]-(:Work)
RETURN path
LIMIT 200;

MATCH path = (:Person)-[:WORKS_ON_TOPIC]->(:Topic)<-[:WORKS_ON_TOPIC]-(:Person)
RETURN path
LIMIT 300;
'''


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


def scaffold(seed: Path, project: Path, name: str, http_port: int, bolt_port: int) -> None:
    project.mkdir(parents=True, exist_ok=True)
    for rel in ["data/raw", "data/processed", "outputs", "scripts", "cypher", "tests"]:
        (project / rel).mkdir(parents=True, exist_ok=True)
    shutil.copy2(seed, project / "data" / "raw" / "seed.tsv")
    write(project / "scripts" / "graph_builder.py", GRAPH_BUILDER)
    write(project / "cypher" / "schema.cypher", SCHEMA_CYPHER)
    write(project / "cypher" / "browser_queries.cypher", BROWSER_QUERIES)
    write(
        project / "docker-compose.yml",
        f'''
        services:
          neo4j:
            image: neo4j:5
            container_name: {name}-neo4j
            ports:
              - "{http_port}:7474"
              - "{bolt_port}:7687"
            environment:
              NEO4J_AUTH: neo4j/${{NEO4J_PASSWORD:-{name}-change-me}}
              NEO4J_server_memory_heap_initial__size: 512m
              NEO4J_server_memory_heap_max__size: 1G
              NEO4J_dbms_security_allow__csv__import__from__file__urls: "true"
            volumes:
              - ./data/processed:/var/lib/neo4j/import
              - neo4j-data:/data
              - neo4j-logs:/logs
        volumes:
          neo4j-data:
          neo4j-logs:
        ''',
    )
    write(
        project / "scripts" / "import_neo4j.ps1",
        f'''
        $ErrorActionPreference = "Stop"
        Push-Location (Split-Path -Parent $PSScriptRoot)
        try {{
            $password = if ($env:NEO4J_PASSWORD) {{ $env:NEO4J_PASSWORD }} else {{ "{name}-change-me" }}
            python .\\scripts\\graph_builder.py
            docker compose up -d
            $ready = $false
            for ($i = 0; $i -lt 36; $i++) {{
                $probe = $null
                try {{
                    $probe = & docker exec {name}-neo4j cypher-shell -u neo4j -p $password "RETURN 1 AS ok;" 2>$null
                }}
                catch {{
                    $probe = $null
                }}
                if ($LASTEXITCODE -eq 0 -and $probe) {{ $ready = $true; break }}
                Start-Sleep -Seconds 5
            }}
            if (-not $ready) {{ throw "Neo4j did not become ready within 180 seconds." }}
            Get-Content .\\cypher\\schema.cypher | docker exec -i {name}-neo4j cypher-shell -u neo4j -p $password
            Write-Host "Academic map imported. Open http://localhost:{http_port} with neo4j / $password."
        }}
        finally {{ Pop-Location }}
        ''',
    )
    write(
        project / "README.md",
        f'''
        # {name} Academic Map

        Generate outputs:

        ```powershell
        python .\\scripts\\graph_builder.py
        ```

        Import into Neo4j:

        ```powershell
        .\\scripts\\import_neo4j.ps1
        ```

        Neo4j Browser: http://localhost:{http_port}

        Username: `neo4j`
        Password: value of `NEO4J_PASSWORD`, or `{name}-change-me` if unset.

        Use `cypher/browser_queries.cypher` for graph visualization queries.
        ''',
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Scaffold a Neo4j academic mapping project from a seed TSV.")
    parser.add_argument("--seed", type=Path, required=True)
    parser.add_argument("--name", default="academic-map")
    parser.add_argument("--project", type=Path, default=None)
    parser.add_argument("--http-port", type=int, default=17474)
    parser.add_argument("--bolt-port", type=int, default=17687)
    args = parser.parse_args()
    project = args.project or (DEFAULT_PROJECT_ROOT / args.name)
    scaffold(args.seed, project, args.name, args.http_port, args.bolt_port)
    print(f"Created academic mapping project at {project}")


if __name__ == "__main__":
    main()
