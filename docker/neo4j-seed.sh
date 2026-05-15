#!/bin/bash
set -e

NEO4J_URI="${NEO4J_URI:-bolt://neo4j:7687}"
NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-mealmate}"

echo "Initialising Neo4j constraints..."
cypher-shell -a "$NEO4J_URI" -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" < /init_graph.cypher

echo "Seeding graph data (zones, restaurants, couriers)..."
cypher-shell -a "$NEO4J_URI" -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" < /seed_graph.cypher

echo "Neo4j seed complete."
