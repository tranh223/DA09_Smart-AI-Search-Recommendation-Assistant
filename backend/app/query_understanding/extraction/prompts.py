EXTRACTION_SYSTEM_PROMPT = """
Extract user entities, expectations, profile updates, and missing information
for OTA hotel search and recommendation planning.

Do not choose retrieval sources.
Do not build execution steps.
Return only data supported by the query and available profile context.
""".strip()
