# Neo4j Graph Schema — Routing Service

## Overview

The routing service uses Neo4j to model spatial relationships between couriers,
zones, and restaurants. Graph edges express which entities are co-located,
making "find couriers near restaurant X" a natural graph traversal rather than
a join across flat tables.

## Node/Relationship Diagram

```
(:Courier)-[:LOCATED_IN]->(:Zone)<-[:LOCATED_IN]-(:Restaurant)
(:Courier)-[:ASSIGNED_TO]->(:Order)
```

ASCII view:

```
[Courier] ──LOCATED_IN──► [Zone] ◄──LOCATED_IN── [Restaurant]
    │
    └──ASSIGNED_TO──► [Order]
```

## Node Properties

### Courier

| Property | Type   | Constraint | Description                          |
|----------|--------|------------|--------------------------------------|
| id       | string | UNIQUE     | UUID — primary identifier            |
| name     | string |            | Courier display name                 |
| status   | string |            | `AVAILABLE` \| `BUSY` \| `OFFLINE`  |
| lat      | float  |            | Current latitude                     |
| lng      | float  |            | Current longitude                    |

### Zone

| Property | Type   | Constraint | Description               |
|----------|--------|------------|---------------------------|
| id       | string | UNIQUE     | UUID — primary identifier |
| name     | string |            | e.g. "Podil", "Obolon"   |

### Restaurant

| Property | Type   | Constraint | Description               |
|----------|--------|------------|---------------------------|
| id       | string | UNIQUE     | UUID — primary identifier |
| name     | string |            | Restaurant display name   |
| zone_id  | string |            | FK-equivalent to Zone.id  |
| lat      | float  |            | Latitude                  |
| lng      | float  |            | Longitude                 |

## Relationships

| Relationship | From       | To         | Meaning                           |
|--------------|------------|------------|-----------------------------------|
| LOCATED_IN   | Courier    | Zone       | Courier is currently in this zone |
| LOCATED_IN   | Restaurant | Zone       | Restaurant belongs to this zone   |
| ASSIGNED_TO  | Courier    | Order      | Courier is handling this order    |

## Schema Initialization

Constraints are created by `scripts/init_graph.cypher`. Run it once on a fresh
Neo4j instance before seeding:

```bash
docker compose up neo4j -d --wait
docker compose exec neo4j cypher-shell -u neo4j -p mealmate < scripts/init_graph.cypher
```

The script uses `IF NOT EXISTS` — safe to re-run without errors.

## Pydantic Models

Python representations live in
`services/routing/src/app/domain/models.py`.

`CourierStatus` uses uppercase enum values (`AVAILABLE`, `BUSY`, `OFFLINE`)
consistent with the service's existing conventions.
