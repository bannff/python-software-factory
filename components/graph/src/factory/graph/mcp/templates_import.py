"""Import and debug prompt templates for graph brick."""

IMPORT_DATA_TEMPLATE = """# Importing Data into Knowledge Graph

## Source Format: {source_format}

## Import Strategy

### Step 1: Prepare Your Data
Ensure your data has:
- Unique identifiers for each entity
- Clear entity types
- Relationship definitions

### Step 2: Import Entities First
```python
# For each entity in your data:
graph_add_entity(
    entity_id="unique-id",
    entity_type="{entity_type}",
    properties={{"key": "value"}},
    labels=["label1", "label2"]
)
```

### Step 3: Import Relationships
```python
# After all entities exist:
graph_add_relationship(
    relationship_id="rel-unique-id",
    relationship_type="RELATIONSHIP_TYPE",
    source_id="source-entity-id",
    target_id="target-entity-id",
    properties={{}}
)
```

### Step 4: Verify Import
```
graph_get_stats()  # Check node and edge counts
graph_health_check()  # Verify graph health
```

## Common Patterns

### JSON Import
```json
{{
  "entities": [
    {{"id": "e1", "type": "User", "properties": {{"name": "Alice"}}}}
  ],
  "relationships": [
    {{"id": "r1", "type": "KNOWS", "source": "e1", "target": "e2"}}
  ]
}}
```

### CSV Import
- One file for entities (id, type, properties as JSON)
- One file for relationships (id, type, source_id, target_id)

## Error Handling
- Check entity exists before adding relationships
- Use idempotent operations (same ID = update, not duplicate)
"""

DEBUG_GRAPH_TEMPLATE = """# Debugging Graph Issues

## Issue: {issue}
## Backend: {backend}

## Diagnostic Steps

### 1. Check Graph Health
```
graph_health_check()
```
Look for:
- `healthy: false` indicates backend issues
- Node/edge counts match expectations

### 2. Get Graph Statistics
```
graph_get_stats(backend="{backend}")
```
Verify:
- Expected number of nodes
- Expected number of edges
- Latency is reasonable

### 3. Verify Entity Exists
```
graph_get_entity(entity_id="problematic-entity-id", backend="{backend}")
```
Check:
- `found: true` if entity should exist
- Properties are correct
- Type is correct

### 4. Check Relationships
```
graph_get_neighbors(
    entity_id="entity-id",
    backend="{backend}"
)
```
Verify:
- Expected neighbors are present
- Relationship types are correct

### 5. Test Path Finding
```
graph_find_path(
    source_id="start",
    target_id="end",
    max_depth=10,
    backend="{backend}"
)
```

## Common Issues

### Missing Relationships
- Ensure both source and target entities exist before adding relationship
- Check relationship direction (source -> target)

### Duplicate Entities
- Use consistent ID generation
- Check if entity exists before adding

### Neo4j Connection Issues
- Verify NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD environment variables
- Check Neo4j server is running
- Test connection with `graph_health_check`

### Performance Issues
- Limit query results with `limit` parameter
- Use specific relationship types in neighbor queries
"""
