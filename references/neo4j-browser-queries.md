# Neo4j Browser Queries

Use these when the user wants graph visualization.

## Coauthor / Coinventor Network

```cypher
MATCH path = (:Person)-[:COLLABORATED_WITH]-(:Person)
RETURN path
LIMIT 300;
```

## Organization Topic Bridge

```cypher
MATCH path = (:Organization)-[:ACTIVE_IN]->(:Topic)<-[:ACTIVE_IN]-(:Organization)
RETURN path
LIMIT 200;
```

## Work Topic Bridge

```cypher
MATCH path = (:Work)-[:SHARES_TOPIC_WITH]-(:Work)
RETURN path
LIMIT 200;
```

## Person Topic Bridge

```cypher
MATCH path = (:Person)-[:WORKS_ON_TOPIC]->(:Topic)<-[:WORKS_ON_TOPIC]-(:Person)
RETURN path
LIMIT 300;
```
