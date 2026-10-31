"""Prompt templates for graph brick MCP prompts."""

CREATE_GRAPH_TEMPLATE = """# Creating Knowledge Graph: {name}

## Description
{description}

## Backend: {backend}

## Steps

1. **Initialize the graph**
   Use `graph_get_capabilities` to verify the backend is available.

2. **Define your entity types**
   Common types: User, Document, Concept, Event, Location
   
3. **Add entities**
   ```
   graph_add_entity(
       entity_id="entity-1",
       entity_type="YourType",
       properties={{"name": "Example"}},
       backend="{backend}"
   )
   ```

4. **Define relationship types**
   Common types: KNOWS, AUTHORED, CONTAINS, RELATED_TO, DEPENDS_ON

5. **Add relationships**
   ```
   graph_add_relationship(
       relationship_id="rel-1",
       relationship_type="RELATED_TO",
       source_id="entity-1",
       target_id="entity-2",
       backend="{backend}"
   )
   ```

6. **Verify with health check**
   Use `graph_health_check` to confirm entities and relationships are stored.

## Best Practices
- Use consistent naming conventions for IDs (e.g., "user-123", "doc-456")
- Add meaningful properties to entities for later querying
- Use descriptive relationship types in UPPER_SNAKE_CASE
"""

QUERY_GRAPH_TEMPLATE = """# Querying the Knowledge Graph

## Query Type: {query_type}

## Available Query Methods

### 1. Get Entity
Retrieve a specific entity by ID:
```
graph_get_entity(entity_id="{entity_id}")
```

### 2. Find Neighbors
Get entities connected to a given entity:
```
graph_get_neighbors(
    entity_id="{entity_id}",
    relationship_type="RELATED_TO",  # optional filter
    direction="both"  # "in", "out", or "both"
)
```

### 3. Find Path
Find shortest path between two entities:
```
graph_find_path(
    source_id="entity-1",
    target_id="entity-2",
    max_depth=5
)
```

### 4. Find Entities
Search entities by type and properties:
```
graph_find_entities(
    entity_type="User",
    properties={{"status": "active"}},
    limit=100
)
```

## Tips
- Start with `graph_get_stats` to understand graph size
- Use `graph_find_entities` for broad searches
- Use `graph_find_path` for relationship discovery
"""
