#!/usr/bin/env python3
"""
Parse Slurm REST API HTML documentation and generate OpenAPI specification
"""
import argparse
import json
import re
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Any

def fetch_html(url: str) -> str:
    """Fetch HTML content from URL"""
    response = requests.get(url)
    response.raise_for_status()
    return response.text

def extract_return_type(soup: BeautifulSoup, method: str, path: str) -> str:
    """Extract the return type for a specific endpoint from the HTML"""
    # Find all code blocks that match the endpoint
    code_blocks = soup.find_all('code')
    
    for i, code in enumerate(code_blocks):
        text = code.get_text().strip()
        # Match with optional trailing slash
        endpoint_pattern = f"{method}\\s+{re.escape(path)}/?"
        
        if re.search(endpoint_pattern, text, re.IGNORECASE):
            # Look for "Return type" heading after this code block
            current = code
            for _ in range(30):  # Search next 30 siblings
                current = current.find_next()
                if not current:
                    break
                    
                # Check if this is a "Return type" heading
                if current.name in ['h3', 'h4', 'h2'] and 'return type' in current.get_text().lower():
                    # The next element should contain the return type link
                    # It could be in a div or p tag
                    next_elem = current.find_next()
                    if next_elem:
                        # Look for a link in this element or its children
                        link = next_elem.find('a') if next_elem.name in ['div', 'p'] else None
                        if not link and next_elem.name == 'a':
                            link = next_elem
                        
                        if link:
                            # Extract schema name from the link text
                            schema_name = link.get_text().strip()
                            if schema_name:
                                return schema_name
    
    return None

def extract_query_parameters(soup: BeautifulSoup, method: str, path: str) -> List[Dict[str, Any]]:
    """Extract query parameters for a specific endpoint from the HTML"""
    parameters = []
    code_blocks = soup.find_all('code')
    
    for code in code_blocks:
        text = code.get_text().strip()
        # Match with optional trailing slash
        endpoint_pattern = f"{method}\\s+{re.escape(path)}/?"
        
        if re.search(endpoint_pattern, text, re.IGNORECASE):
            # Look for "Query parameters" heading after this code block
            current = code
            for _ in range(50):  # Search next 50 siblings
                current = current.find_next()
                if not current:
                    break
                
                # Check if this is a "Query parameters" heading
                if current.name in ['h3', 'h4', 'h2'] and 'query parameter' in current.get_text().lower():
                    # Parse parameters until we hit another heading or section
                    param_elem = current.find_next()
                    while param_elem and param_elem.name not in ['h1', 'h2', 'h3', 'h4']:
                        text_content = param_elem.get_text().strip()
                        
                        # Look for parameter definitions like "update_time (optional)"
                        param_match = re.match(r'(\w+)\s*\(([^)]+)\)', text_content)
                        if param_match:
                            param_name = param_match.group(1)
                            param_info = param_match.group(2)
                            
                            # Extract description and default value
                            description = ""
                            default_val = None
                            
                            # Look for description in the same or next element
                            desc_text = text_content[param_match.end():].strip()
                            if desc_text:
                                # Extract description and default value
                                if 'default:' in desc_text.lower():
                                    parts = re.split(r'default:\s*', desc_text, flags=re.IGNORECASE)
                                    description = parts[0].strip()
                                    if len(parts) > 1:
                                        default_val = parts[1].strip()
                                else:
                                    description = desc_text
                            
                            # Determine parameter type
                            param_type = "string"
                            if "timestamp" in description.lower() or "time" in param_name.lower():
                                param_type = "integer"
                            
                            param_def = {
                                "name": param_name,
                                "in": "query",
                                "required": "optional" not in param_info.lower(),
                                "schema": {"type": param_type},
                                "description": description if description else f"Query parameter {param_name}"
                            }
                            
                            parameters.append(param_def)
                        
                        param_elem = param_elem.find_next_sibling()
                        if not param_elem:
                            break
                    
                    break
                
                # Stop if we hit another endpoint
                if current.name == 'code' and re.search(r'^(get|post|put|delete|patch)\s+/', current.get_text().strip(), re.IGNORECASE):
                    break
    
    return parameters

def parse_example_to_schema(example_json: str) -> Dict[str, Any]:
    """Parse example JSON data to generate OpenAPI schema"""
    if not example_json:
        return {"type": "object", "properties": {}}
    
    try:
        # Clean up the JSON string (remove escaping, handle various formats)
        cleaned_json = example_json.strip()
        # Remove HTML entities if any
        cleaned_json = cleaned_json.replace('&quot;', '"').replace('&amp;', '&')
        # Try to extract JSON from code blocks or other wrappers
        if cleaned_json.startswith('```'):
            # Extract JSON from markdown code block
            lines = cleaned_json.split('\n')
            cleaned_json = '\n'.join(lines[1:-1]) if len(lines) > 2 else cleaned_json
        # Remove leading/trailing whitespace and newlines
        cleaned_json = cleaned_json.strip()
        
        data = json.loads(cleaned_json)
        
        def infer_schema(obj: Any, path: str = "") -> Dict[str, Any]:
            """Recursively infer schema from example data"""
            if isinstance(obj, dict):
                properties = {}
                required = []
                for key, value in obj.items():
                    if value is not None:  # Only add non-null values
                        properties[key] = infer_schema(value, f"{path}.{key}" if path else key)
                        # Mark as required if it's a top-level property
                        if not path:
                            required.append(key)
                
                schema = {
                    "type": "object",
                    "properties": properties
                }
                if required:
                    schema["required"] = required
                return schema
            elif isinstance(obj, list):
                if obj:
                    # Use first item as template, but check if all items are similar
                    item_schema = infer_schema(obj[0], f"{path}[]")
                    return {
                        "type": "array",
                        "items": item_schema
                    }
                else:
                    return {
                        "type": "array",
                        "items": {"type": "object"}
                    }
            elif isinstance(obj, bool):
                return {"type": "boolean"}
            elif isinstance(obj, int):
                return {"type": "integer"}
            elif isinstance(obj, float):
                return {"type": "number"}
            elif isinstance(obj, str):
                # Try to detect if it's a timestamp or date
                if obj.isdigit() and len(obj) == 10:
                    return {"type": "integer", "format": "int64", "description": "Unix timestamp"}
                return {"type": "string"}
            elif obj is None:
                return {"type": "string", "nullable": True}
            else:
                return {"type": "object"}
        
        return infer_schema(data)
    except (json.JSONDecodeError, Exception) as e:
        # If parsing fails, try to extract JSON from the string
        try:
            # Try to find JSON object in the string
            start = cleaned_json.find('{')
            end = cleaned_json.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = cleaned_json[start:end]
                data = json.loads(json_str)
                return parse_example_to_schema(json.dumps(data))
        except:
            pass
        # If all parsing fails, return empty schema
        return {"type": "object", "properties": {}}

def extract_example_data(soup: BeautifulSoup, method: str, path: str) -> str:
    """Extract example data for a specific endpoint from the HTML"""
    code_blocks = soup.find_all('code')
    
    for code in code_blocks:
        text = code.get_text().strip()
        # Match with optional trailing slash
        endpoint_pattern = f"{method}\\s+{re.escape(path)}/?"
        
        if re.search(endpoint_pattern, text, re.IGNORECASE):
            # Look for "Example data" or "Example" heading after this code block
            current = code
            found_example_heading = False
            
            for _ in range(150):  # Search more siblings
                current = current.find_next()
                if not current:
                    break
                
                # Check if this is an "Example" heading (various formats)
                if current.name in ['h3', 'h4', 'h2', 'h5']:
                    heading_text = current.get_text().lower()
                    if any(keyword in heading_text for keyword in ['example data', 'example', 'response', 'output']):
                        found_example_heading = True
                        # Look for JSON in the next few elements
                        search_elem = current
                        for _ in range(10):  # Check next 10 elements
                            search_elem = search_elem.find_next()
                            if not search_elem:
                                break
                            
                            # Get text content
                            elem_text = search_elem.get_text().strip()
                            
                            # Skip Content-Type headers
                            if 'content-type' in elem_text.lower() and 'application/json' in elem_text.lower():
                                continue
                            
                            # Look for JSON in code/pre tags
                            if search_elem.name in ['pre', 'code']:
                                example_text = elem_text
                                # Check if it looks like JSON
                                if example_text.startswith('{') or example_text.startswith('['):
                                    return example_text
                            
                            # Sometimes it's wrapped in a div or p
                            code_elem = search_elem.find('code') or search_elem.find('pre')
                            if code_elem:
                                example_text = code_elem.get_text().strip()
                                if example_text.startswith('{') or example_text.startswith('['):
                                    return example_text
                            
                            # Sometimes JSON is directly in the element text
                            if search_elem.name in ['p', 'div', 'pre']:
                                # Try to extract JSON from the text
                                json_match = re.search(r'(\{.*\}|\[.*\])', elem_text, re.DOTALL)
                                if json_match:
                                    return json_match.group(1)
                                
                                # Or check if the whole text is JSON
                                if elem_text.startswith('{') or elem_text.startswith('['):
                                    return elem_text
                        
                        if found_example_heading:
                            break
                
                # Stop if we hit another endpoint
                if current.name == 'code' and re.search(r'^(get|post|put|delete|patch)\s+/', current.get_text().strip(), re.IGNORECASE):
                    break
    
    return None

def extract_request_body_example(soup: BeautifulSoup, method: str, path: str) -> str:
    """Extract example request body data for a specific endpoint from the HTML

    The Slurm REST API docs often have separate sections for request and response
    examples. This function tries to find request-oriented examples by looking
    for headings that mention request / body / input near the endpoint.
    """
    code_blocks = soup.find_all('code')

    for code in code_blocks:
        text = code.get_text().strip()
        # Match with optional trailing slash
        endpoint_pattern = f"{method}\\s+{re.escape(path)}/?"

        if re.search(endpoint_pattern, text, re.IGNORECASE):
            current = code

            # Search forward for a heading that looks like a request example
            for _ in range(150):
                current = current.find_next()
                if not current:
                    break

                if current.name in ['h3', 'h4', 'h2', 'h5']:
                    heading_text = current.get_text().lower()

                    # Prefer headings that explicitly mention request/body/input
                    if any(keyword in heading_text for keyword in [
                        'example request',
                        'request body',
                        'request data',
                        'input data',
                        'input body',
                        'request'
                    ]):
                        search_elem = current

                        # Look at the next few elements for JSON
                        for _ in range(10):
                            search_elem = search_elem.find_next()
                            if not search_elem:
                                break

                            elem_text = search_elem.get_text().strip()

                            # Skip Content-Type headers
                            if 'content-type' in elem_text.lower() and 'application/json' in elem_text.lower():
                                continue

                            # Direct JSON in pre/code
                            if search_elem.name in ['pre', 'code']:
                                example_text = elem_text
                                if example_text.startswith('{') or example_text.startswith('['):
                                    return example_text

                            # JSON wrapped in div/p
                            code_elem = search_elem.find('code') or search_elem.find('pre')
                            if code_elem:
                                example_text = code_elem.get_text().strip()
                                if example_text.startswith('{') or example_text.startswith('['):
                                    return example_text

                            # Try to extract JSON substring
                            if search_elem.name in ['p', 'div', 'pre']:
                                json_match = re.search(r'(\{.*\}|\[.*\])', elem_text, re.DOTALL)
                                if json_match:
                                    return json_match.group(1)
                                if elem_text.startswith('{') or elem_text.startswith('['):
                                    return elem_text

                    # If we hit a generic "Example data"/"Example" heading before a
                    # specific request heading, we skip it here because that's likely
                    # the response example which is already handled by extract_example_data

                # Stop if we hit another endpoint definition
                if current.name == 'code' and re.search(r'^(get|post|put|delete|patch)\s+/', current.get_text().strip(), re.IGNORECASE):
                    break

    return None

def expand_refs_in_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Expand $ref references to inline schemas for better visibility in Swagger UI"""
    def expand_ref(obj: Any, schemas: Dict[str, Any], visited: set = None, schema_name_hint: str = None) -> Any:
        """Recursively expand $ref references"""
        if visited is None:
            visited = set()
        
        if isinstance(obj, dict):
            # Check for $ref
            if "$ref" in obj:
                ref_path = obj["$ref"]
                # Extract schema name from #/components/schemas/name
                if ref_path.startswith("#/components/schemas/"):
                    schema_name = ref_path.replace("#/components/schemas/", "")
                    if schema_name in schemas:
                        # Avoid circular references
                        if schema_name in visited:
                            return {"type": "object", "description": f"Circular reference to {schema_name}"}
                        visited.add(schema_name)
                        expanded = expand_ref(schemas[schema_name], schemas, visited, schema_name)
                        visited.remove(schema_name)
                        return expanded
                return obj
            
            # Check if this is an empty schema that should be expanded
            # Look for description that contains schema name
            if "description" in obj and "type" in obj and obj.get("type") == "object":
                desc = obj.get("description", "")
                # Try to extract schema name from description like "Schema for v0.0.44_openapi_resp"
                if "Schema for" in desc:
                    potential_schema_name = desc.replace("Schema for ", "").strip()
                    if potential_schema_name in schemas:
                        # Only expand if current schema is empty or has fewer properties
                        current_props = obj.get("properties", {})
                        schema_props = schemas[potential_schema_name].get("properties", {})
                        # If current schema is empty but we have a full schema in components
                        if (not current_props or len(current_props) == 0) and len(schema_props) > 0:
                            if potential_schema_name not in visited:
                                visited.add(potential_schema_name)
                                expanded = expand_ref(schemas[potential_schema_name], schemas, visited, potential_schema_name)
                                visited.remove(potential_schema_name)
                                # Preserve description and other metadata
                                if isinstance(expanded, dict):
                                    expanded["description"] = desc
                                    # Preserve other fields from original
                                    for key in obj:
                                        if key not in ["properties", "type", "description"]:
                                            expanded[key] = obj[key]
                                return expanded
            
            # Recursively process all values
            expanded = {}
            for key, value in obj.items():
                expanded[key] = expand_ref(value, schemas, visited, schema_name_hint)
            return expanded
        elif isinstance(obj, list):
            return [expand_ref(item, schemas, visited, schema_name_hint) for item in obj]
        else:
            return obj
    
    # Create a copy to avoid modifying the original
    expanded_spec = json.loads(json.dumps(spec))
    schemas = expanded_spec.get("components", {}).get("schemas", {})
    
    # Expand refs in paths
    if "paths" in expanded_spec:
        expanded_spec["paths"] = expand_ref(expanded_spec["paths"], schemas)
    
    return expanded_spec

def parse_slurm_api_docs(html_content: str, server_url: str = "http://localhost:6820") -> Dict[str, Any]:
    """Parse Slurm API documentation HTML and extract API information"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    openapi_spec = {
        "openapi": "3.0.0",
        "info": {
            "title": "Slurm REST API",
            "description": "REST API for Slurm Workload Manager",
            "version": "v0.0.44",
            "contact": {
                "name": "SchedMD",
                "url": "https://www.schedmd.com"
            }
        },
        "servers": [
            {
                "url": server_url,
                "description": "Slurm REST API server"
            }
        ],
        "security": [
            {"ApiKeyAuth": []},
            {"BasicAuth": []}
        ],
        "components": {
            "securitySchemes": {
                "ApiKeyAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-SLURM-USER-TOKEN",
                    "description": "Slurm user authentication token"
                },
                "BasicAuth": {
                    "type": "http",
                    "scheme": "basic"
                }
            },
            "schemas": {}
        },
        "paths": {},
        "tags": [
            {"name": "slurm", "description": "Slurm controller operations"},
            {"name": "slurmdb", "description": "Slurm database operations"}
        ]
    }
    
    # Track schemas we've seen and their example data
    schemas_seen = {}
    
    # Extract endpoints from code blocks
    code_blocks = soup.find_all('code')
    
    for code in code_blocks:
        text = code.get_text().strip()
        
        # Match HTTP method and path patterns
        method_match = re.match(r'^(get|post|put|delete|patch)\s+(/[^\s]+)', text, re.IGNORECASE)
        
        if method_match:
            method = method_match.group(1).lower()
            original_path = method_match.group(2)  # Keep original path with trailing slash
            
            # Clean up path for OpenAPI spec (remove trailing slash)
            path = original_path.rstrip('/')
            if not path:
                path = '/'
            
            # Initialize path in spec if not exists
            if path not in openapi_spec["paths"]:
                openapi_spec["paths"][path] = {}
            
            # Determine tag based on path
            tag = "slurmdb" if "/slurmdb/" in path else "slurm"
            
            # Extract return type for this endpoint (use original path)
            return_type = extract_return_type(soup, method, original_path)
            
            # Extract example response data for this endpoint (use original path)
            example_data = extract_example_data(soup, method, original_path)
            # Extract example request body data (for methods that usually have a body)
            request_example_data = None
            if method in ['post', 'put', 'patch']:
                request_example_data = extract_request_body_example(soup, method, original_path)
            
            # Create response schema
            if return_type:
                # Track this schema with its example data
                if return_type not in schemas_seen:
                    schemas_seen[return_type] = example_data
                
                # If we have example data, generate schema now and use inline
                # Otherwise use $ref (will be expanded later)
                if example_data:
                    schema = parse_example_to_schema(example_data)
                    schema["description"] = f"Schema for {return_type}"
                    # Use inline schema directly
                    response_schema = schema
                    # Also store in components for reference
                    if return_type not in openapi_spec["components"]["schemas"]:
                        openapi_spec["components"]["schemas"][return_type] = schema
                else:
                    # Use $ref, will be expanded later if schema exists
                    response_schema = {
                        "$ref": f"#/components/schemas/{return_type}"
                    }
            else:
                # Fallback to generic object
                response_schema = {
                    "type": "object"
                }
            
            # Extract query parameters for GET requests (use original path)
            query_params = []
            if method == 'get':
                query_params = extract_query_parameters(soup, method, original_path)
            
            # Create operation object
            operation = {
                "tags": [tag],
                "summary": f"{method.upper()} {path}",
                "responses": {
                    "200": {
                        "description": "Successful operation",
                        "content": {
                            "application/json": {
                                "schema": response_schema
                            }
                        }
                    },
                    "default": {
                        "description": "Error response",
                        "content": {
                            "application/json": {
                                "schema": response_schema
                            }
                        }
                    }
                }
            }
            
            # Add query parameters if any
            if query_params:
                operation["parameters"] = query_params
            
            # Add request body for POST, PUT, PATCH
            if method in ['post', 'put', 'patch']:
                request_schema = None
                # Prefer dedicated request example if available
                if request_example_data:
                    request_schema = parse_example_to_schema(request_example_data)
                # Fallback: if we at least have response example, use its structure
                elif example_data:
                    request_schema = parse_example_to_schema(example_data)
                
                if request_schema:
                    operation["requestBody"] = {
                        "content": {
                            "application/json": {
                                "schema": request_schema
                            }
                        }
                    }
                else:
                    # Final fallback: generic object
                    operation["requestBody"] = {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object"
                                }
                            }
                        }
                    }
            
            openapi_spec["paths"][path][method] = operation
    
    # Generate schemas from example data
    for schema_name, example_data in schemas_seen.items():
        if schema_name not in openapi_spec["components"]["schemas"]:
            if example_data:
                # Parse example data to generate detailed schema
                schema = parse_example_to_schema(example_data)
                schema["description"] = f"Schema for {schema_name}"
                openapi_spec["components"]["schemas"][schema_name] = schema
            else:
                # Fallback to placeholder schema
                openapi_spec["components"]["schemas"][schema_name] = {
                    "type": "object",
                    "description": f"Schema for {schema_name}",
                    "properties": {}
                }
        else:
            # If schema exists but is empty, try to populate it with example data
            existing_schema = openapi_spec["components"]["schemas"][schema_name]
            if example_data and (not existing_schema.get("properties") or len(existing_schema.get("properties", {})) == 0):
                schema = parse_example_to_schema(example_data)
                schema["description"] = existing_schema.get("description", f"Schema for {schema_name}")
                openapi_spec["components"]["schemas"][schema_name] = schema
    
    return openapi_spec


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Parse Slurm REST API documentation and generate OpenAPI specification"
    )
    parser.add_argument(
        '--server-url',
        type=str,
        default='http://localhost:6820',
        help='Slurm REST API server URL (default: http://localhost:6820)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='openapi_spec_v44.json',
        help='Output file path (default: openapi_spec_v44.json)'
    )
    parser.add_argument(
        '--expand-refs',
        action='store_true',
        help='Expand $ref references to inline schemas for better visibility in Swagger UI'
    )
    
    args = parser.parse_args()
    
    url = "https://raw.githubusercontent.com/SchedMD/slurm/master/doc/html/rest_api.shtml"
    
    print("Fetching Slurm REST API documentation...")
    html_content = fetch_html(url)
    
    print("Parsing documentation...")
    openapi_spec = parse_slurm_api_docs(html_content, server_url=args.server_url)
    
    print(f"Found {len(openapi_spec['paths'])} API endpoints")
    print(f"Found {len(openapi_spec['components']['schemas'])} schemas")
    print(f"Server URL: {args.server_url}")
    
    # Expand refs if requested
    if args.expand_refs:
        print("Expanding $ref references to inline schemas...")
        openapi_spec = expand_refs_in_spec(openapi_spec)
        print("✓ References expanded")
    
    # Save to file
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(openapi_spec, f, indent=2, ensure_ascii=False)
    
    print(f"OpenAPI specification saved to {args.output}")

if __name__ == "__main__":
    main()
