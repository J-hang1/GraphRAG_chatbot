"""
Neo4j schema loading and management
"""
import json
import os
from flask import current_app
from .connection import execute_query
from ..utils.logger import log_info, log_error

# Global schema cache
_schema = None

def load_neo4j_schema():
    """Load Neo4j schema from database or default schema"""
    global _schema

    try:
        # Try to get schema from Neo4j
        _schema = get_schema_from_neo4j()

        if _schema:
            log_info("Loaded schema from Neo4j")
            # Save schema to file for caching
            save_schema_to_file(_schema)
            return _schema
        else:
            log_info("Could not load schema from Neo4j, trying cached schema")
            _schema = load_schema_from_file()

            if _schema:
                log_info("Loaded schema from cache file")
                return _schema
            else:
                log_info("Could not load schema from cache, using default schema")
                _schema = get_default_schema()
                return _schema
    except Exception as e:
        log_error(f"Error loading Neo4j schema: {str(e)}")
        _schema = get_default_schema()
        return _schema

def get_schema_from_neo4j():
    """Get schema directly from Neo4j database"""
    try:
        # Query to get node labels
        node_query = """
        CALL db.schema.nodeTypeProperties()
        YIELD nodeType, propertyName, propertyTypes, mandatory
        RETURN nodeType, collect({name: propertyName, types: propertyTypes, mandatory: mandatory}) as properties
        """

        # Query to get relationship types
        rel_query = """
        CALL db.schema.relTypeProperties()
        YIELD relType, propertyName, propertyTypes, mandatory
        RETURN relType, collect({name: propertyName, types: propertyTypes, mandatory: mandatory}) as properties
        """

        # Query to get relationship patterns
        pattern_query = """
        CALL db.schema.visualization()
        YIELD nodes, relationships
        UNWIND relationships as rel
        RETURN rel.startNodeLabels as source, rel.type as relationship, rel.endNodeLabels as target
        """

        # Execute queries
        nodes = execute_query(node_query)
        relationships = execute_query(rel_query)
        patterns = execute_query(pattern_query)

        # Format schema
        schema = {
            "nodes": {},
            "relationships": {},
            "patterns": []
        }

        # Process nodes
        for node in nodes:
            label = node["nodeType"]
            props = node["properties"]
            schema["nodes"][label] = {
                "properties": {p["name"]: p["types"][0] for p in props}
            }

        # Process relationships
        for rel in relationships:
            rel_type = rel["relType"]
            props = rel["properties"]
            schema["relationships"][rel_type] = {
                "properties": {p["name"]: p["types"][0] for p in props}
            }

        # Process patterns
        for pattern in patterns:
            source = pattern["source"][0] if pattern["source"] else "Unknown"
            target = pattern["target"][0] if pattern["target"] else "Unknown"
            rel_type = pattern["relationship"]

            schema["patterns"].append({
                "source": source,
                "relationship": rel_type,
                "target": target
            })

        return schema
    except Exception as e:
        log_error(f"Error getting schema from Neo4j: {str(e)}")
        return None

def save_schema_to_file(schema):
    """Save schema to file for caching"""
    try:
        # Create data directory if it doesn't exist
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

        # Save schema to file
        schema_file = os.path.join(data_dir, 'graph_schema.json')
        with open(schema_file, 'w', encoding='utf-8') as f:
            json.dump(schema, f, indent=2, ensure_ascii=False)

        log_info(f"Schema saved to {schema_file}")
        return True
    except Exception as e:
        log_error(f"Error saving schema to file: {str(e)}")
        return False

def load_schema_from_file():
    """Load schema from cached file or default schema file"""
    try:
        # First try to load from cached file
        schema_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'graph_schema.json')

        # Check if cached file exists
        if not os.path.exists(schema_file):
            log_info(f"Cached schema file not found: {schema_file}")

            # Try to load from current schema file in app/data
            current_schema_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'neo4j_current_schema.json')

            if os.path.exists(current_schema_file):
                log_info(f"Loading current schema from: {current_schema_file}")
                with open(current_schema_file, 'r', encoding='utf-8') as f:
                    schema_data = json.load(f)
                    # Convert string schema to structured format
                    schema = convert_string_schema_to_structured(schema_data.get("schema", ""))
                log_info(f"Current schema loaded from {current_schema_file}")
                return schema

            # Try to load from default schema file in app/data
            default_schema_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'default_neo4j_schema.json')

            if os.path.exists(default_schema_file):
                log_info(f"Loading default schema from: {default_schema_file}")
                with open(default_schema_file, 'r', encoding='utf-8') as f:
                    schema = json.load(f)
                log_info(f"Default schema loaded from {default_schema_file}")
                return schema
            else:
                log_info(f"Default schema file not found: {default_schema_file}")
                return None

        # Load schema from cached file
        with open(schema_file, 'r', encoding='utf-8') as f:
            schema = json.load(f)

        log_info(f"Schema loaded from cached file: {schema_file}")
        return schema
    except Exception as e:
        log_error(f"Error loading schema from file: {str(e)}")
        return None

def convert_string_schema_to_structured(schema_str):
    """Convert string schema to structured format"""
    try:
        lines = schema_str.split('\n')

        schema = {
            "nodes": {},
            "relationships": {},
            "patterns": []
        }

        current_node = None
        in_relationships = False

        for line in lines:
            line = line.strip()

            if not line:
                continue

            # Check if this is a relationship line
            if line.startswith('- (') and ')-[' in line and ']->' in line:
                in_relationships = True
                # Extract source, relationship, and target
                parts = line.replace('- ', '').split(')-[')
                source = parts[0].replace('(', '').strip()

                rel_target = parts[1].split(']->')
                relationship = rel_target[0].replace(':', '').strip()
                target = rel_target[1].replace('(', '').replace(')', '').strip()

                schema["patterns"].append({
                    "source": source,
                    "relationship": relationship,
                    "target": target
                })

                # Add relationship if not exists
                if relationship not in schema["relationships"]:
                    schema["relationships"][relationship] = {
                        "properties": {}
                    }

            # Check if this is a node line
            elif line.startswith('- ') and not in_relationships:
                current_node = line.replace('- ', '').strip()
                schema["nodes"][current_node] = {
                    "properties": {}
                }
            # Check if this is a property line
            elif line.startswith('  - ') and current_node and not in_relationships:
                parts = line.replace('  - ', '').split(':')
                prop_name = parts[0].strip()
                prop_type = "STRING"  # Default type

                if len(parts) > 1:
                    prop_type = parts[1].strip().upper()

                schema["nodes"][current_node]["properties"][prop_name] = prop_type

        return schema
    except Exception as e:
        log_error(f"Error converting string schema to structured format: {str(e)}")
        return get_default_schema()

def get_default_schema():
    """Get default schema"""
    return {
        "nodes": {
            "Brand": {
                "properties": {
                    "id": "INTEGER",
                    "name": "STRING"
                }
            },
            "Product": {
                "properties": {
                    "id": "INTEGER",
                    "name_product": "STRING",
                    "descriptions": "STRING",
                    "brand_id": "INTEGER",
                    "categories_id": "INTEGER"
                }
            },
            "Variant": {
                "properties": {
                    "id": "INTEGER",
                    "product_id": "INTEGER",
                    "Beverage_Option": "STRING",
                    "price": "FLOAT",
                    "calories": "FLOAT",
                    "caffeine_mg": "FLOAT",
                    "protein_g": "FLOAT",
                    "sugars_g": "FLOAT",
                    "dietary_fibre_g": "FLOAT",
                    "vitamin_a": "STRING",
                    "vitamin_c": "STRING",
                    "sales_rank": "INTEGER"
                }
            },
            "Category": {
                "properties": {
                    "id": "INTEGER",
                    "name_cat": "STRING",
                    "description": "STRING"
                }
            },
            "ExtractedEntity": {
                "properties": {
                    "id": "STRING",
                    "name": "STRING",
                    "type": "STRING",
                    "description": "STRING"
                }
            },
            "Customer": {
                "properties": {
                    "id": "INTEGER",
                    "name": "STRING",
                    "age": "INTEGER",
                    "sex": "STRING",
                    "location": "STRING",
                    "face_embedding": "LIST"
                }
            },
            "Order": {
                "properties": {
                    "id": "INTEGER",
                    "customer_id": "INTEGER",
                    "store_id": "INTEGER",
                    "order_date": "DATETIME"
                }
            },
            "OrderDetail": {
                "properties": {
                    "id": "INTEGER",
                    "order_id": "INTEGER",
                    "variant_id": "INTEGER",
                    "quantity": "INTEGER",
                    "rate": "FLOAT"
                }
            },
            "Store": {
                "properties": {
                    "id": "INTEGER",
                    "name_store": "STRING",
                    "address": "STRING",
                    "phone": "STRING",
                    "open_close": "STRING"
                }
            },
            "ProductCommunity": {
                "properties": {
                    "id": "INTEGER",
                    "name": "STRING",
                    "description": "STRING"
                }
            },
            "VariantCommunity": {
                "properties": {
                    "id": "INTEGER",
                    "name": "STRING",
                    "description": "STRING"
                }
            },
            "ChatHistory": {
                "properties": {
                    "id": "INTEGER",
                    "customer_id": "INTEGER",
                    "timestamp": "DATETIME",
                    "message": "STRING",
                    "response": "STRING"
                }
            }
        },
        "relationships": {
            "BRAND_ID": {
                "properties": {}
            },
            "PRODUCT_ID": {
                "properties": {}
            },
            "CATEGORIES_ID": {
                "properties": {}
            },
            "BELONGS_TO_CATEGORY": {
                "properties": {}
            },
            "HAS_EXTRACTED_ENTITY": {
                "properties": {}
            },
            "EXTRACTED_RELATIONSHIP": {
                "properties": {}
            },
            "CUSTOMER_ID": {
                "properties": {}
            },
            "STORE_ID": {
                "properties": {}
            },
            "ORDER_ID": {
                "properties": {}
            },
            "VARIANT_ID": {
                "properties": {}
            },
            "BELONGS_TO_PRODUCT_COMMUNITY": {
                "properties": {}
            },
            "BELONGS_TO_VARIANT_COMMUNITY": {
                "properties": {}
            },
            "CONTAINS_PRODUCT": {
                "properties": {}
            },
            "CONTAINS_VARIANT": {
                "properties": {}
            }
        },
        "patterns": [
            {
                "source": "Product",
                "relationship": "BRAND_ID",
                "target": "Brand"
            },
            {
                "source": "Variant",
                "relationship": "PRODUCT_ID",
                "target": "Product"
            },
            {
                "source": "Product",
                "relationship": "CATEGORIES_ID",
                "target": "Category"
            },
            {
                "source": "Product",
                "relationship": "BELONGS_TO_CATEGORY",
                "target": "Category"
            },
            {
                "source": "Product",
                "relationship": "HAS_EXTRACTED_ENTITY",
                "target": "ExtractedEntity"
            },
            {
                "source": "ExtractedEntity",
                "relationship": "EXTRACTED_RELATIONSHIP",
                "target": "ExtractedEntity"
            },
            {
                "source": "Order",
                "relationship": "CUSTOMER_ID",
                "target": "Customer"
            },
            {
                "source": "Order",
                "relationship": "STORE_ID",
                "target": "Store"
            },
            {
                "source": "OrderDetail",
                "relationship": "ORDER_ID",
                "target": "Order"
            },
            {
                "source": "OrderDetail",
                "relationship": "VARIANT_ID",
                "target": "Variant"
            },
            {
                "source": "Product",
                "relationship": "BELONGS_TO_PRODUCT_COMMUNITY",
                "target": "ProductCommunity"
            },
            {
                "source": "Variant",
                "relationship": "BELONGS_TO_VARIANT_COMMUNITY",
                "target": "VariantCommunity"
            },
            {
                "source": "ChatHistory",
                "relationship": "CUSTOMER_ID",
                "target": "Customer"
            },
            {
                "source": "ProductCommunity",
                "relationship": "CONTAINS_PRODUCT",
                "target": "Product"
            },
            {
                "source": "VariantCommunity",
                "relationship": "CONTAINS_VARIANT",
                "target": "Variant"
            },
            {
                "source": "VariantCommunity",
                "relationship": "BELONGS_TO_PRODUCT_COMMUNITY",
                "target": "ProductCommunity"
            }
        ]
    }

def get_schema():
    """Get the current schema"""
    global _schema

    if _schema is None:
        _schema = load_neo4j_schema()

    return _schema
