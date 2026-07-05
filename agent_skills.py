from langchain_core.tools import tool

@tool
def get_cockroach_performance_best_practices(query: str) -> str:
    """Useful for answering general questions about CockroachDB performance and best practices."""
    return (
        "CockroachDB Best Practices:\n"
        "1. Primary Keys: Always use UUIDs or multi-column keys to prevent hotspotting. Avoid sequential IDs.\n"
        "2. Indexes: Add secondary indexes for columns frequently used in WHERE clauses to prevent full table scans.\n"
        "3. Transactions: Keep transactions short and retry them on 40001 (serialization failure) errors."
    )

@tool
def analyze_schema_for_bottlenecks(table_schema: str) -> str:
    """Expert skill to analyze a given SQL table schema for potential CockroachDB performance bottlenecks."""
    issues = []
    if "SERIAL" in table_schema.upper() or "AUTOINCREMENT" in table_schema.upper():
        issues.append("- WARNING: Using SERIAL or sequential IDs causes write hotspotting in distributed databases. Use UUID instead.")
    if not issues:
        return "The schema looks good and follows CockroachDB best practices."
    
    return "Found the following schema issues:\n" + "\n".join(issues)

COCKROACH_SKILLS = [get_cockroach_performance_best_practices, analyze_schema_for_bottlenecks]
