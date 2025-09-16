import os
from langchain.prompts import PromptTemplate
from courses.neo4j_driver import driver as graph
from .groqllm import GroqLLM

# --- Configuration ---
API_KEY = os.getenv("GROQ_API_KEY")
if not API_KEY:
    raise RuntimeError("GROQ_API_KEY is not set in your environment")

MODEL_NAME = "llama-3.1-8b-instant"
llm = GroqLLM(api_key=API_KEY, model=MODEL_NAME)

# --- Schema (raw) ---
SCHEMA_RAW = """
Graph Schema:
- (:Course {code: String, title: String, credits: Integer, level: Integer})
- (:PrerequisiteGroup {id: UUID, type: "AND"/"OR"/"CUSTOM", recommended: Boolean/Null})
- (:Course)-[:REQUIRES]->(:PrerequisiteGroup)
- (:PrerequisiteGroup)-[:HAS]->(:Course)
"""

# Escape { } so Python's formatter doesn't think they're placeholders.
SCHEMA_SAFE = SCHEMA_RAW.replace("{", "{{").replace("}", "}}")

# --- Prompt (keep ONLY {{question}} as a real variable) ---
CYPHER_PROMPT = PromptTemplate(
    input_variables=["question"],
    template=f"""
You are an assistant that generates Cypher queries for a Neo4j course prerequisite graph.

{SCHEMA_SAFE}

Rules:
- Output only a valid Cypher query, nothing else.
- Use the exact property names and labels.
- If asking about prerequisites: return prerequisite course codes.
- If asking about course details: return code, title, credits, level.
- If asking to list courses: return code, title, credits, level.

Question: {{question}}
Cypher:
"""
)

def run_query(query: str):
    try:
        # If your Aura DB requires a specific database name, set it here:
        # with graph.session(database="neo4j") as session:
        with graph.session() as session:
            res = session.run(query)
            return [r.data() for r in res]
    except Exception as e:
        return [{"error": str(e)}]

def _strip_code_fences(text: str) -> str:
    """
    If the LLM returns ```cypher ...``` or ```...```, strip the fences.
    """
    t = text.strip()
    if t.startswith("```"):
        # remove opening fence
        t = t.split("```", 2)
        if len(t) == 3:
            # t[1] could be a language hint like 'cypher'
            return t[2].strip()
        # fallback
        return text.replace("```", "").strip()
    return text

def advisor_response(question: str):
    # Generate query text from the prompt template
    prompt_text = CYPHER_PROMPT.format(question=question)
    cypher_query = llm(prompt_text).strip()
    cypher_query = _strip_code_fences(cypher_query)
    print("[DEBUG] Generated Cypher:\n", cypher_query)

    if not cypher_query:
        return "Failed to generate a Cypher query."

    # Run query
    results = run_query(cypher_query)
    if not results:
        return "No results found."
    if isinstance(results, list) and results and isinstance(results[0], dict) and "error" in results[0]:
        return "Query failed: " + results[0]["error"]

    # Simple formatting
    return "\n".join(str(r) for r in results)


# Example usage (manual test)
if __name__ == "__main__":
    print(advisor_response("What are the prerequisites for CS201?"))
    print(advisor_response("List all entry-level courses"))
    print(advisor_response("Show details of CS101"))
