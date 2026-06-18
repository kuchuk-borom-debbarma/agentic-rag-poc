# Sub-step 1: Infrastructure Setup

This folder contains the `docker-compose.yml` required to spin up the local Neo4j graph database for the query/RAG pipeline.

## What it does
- Pulls the official Neo4j 5.x Docker image.
- Installs the APOC plugin (Awesome Procedures on Cypher) which gives us advanced Graph algorithms and JSON handling capabilities.
- Mounts local volumes so your graph data persists even if the container turns off.

## Instructions
1. Open your terminal and navigate to this specific directory:
   ```bash
   cd "query/step 2/substep1_infrastructure"
   ```
2. Spin up the database in the background:
   ```bash
   docker-compose up -d
   ```
3. Open your browser and go to `http://localhost:7474`.
   - **Username:** `neo4j`
   - **Password:** `password123`

Once the database is running and you can log in to the browser interface, you are ready to move on to **Sub-step 2** (Graph Ingestion).

From the `query/` directory, the full pipeline starts Neo4j automatically:
```bash
./run_pipeline.sh
```
