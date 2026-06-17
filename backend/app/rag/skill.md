# skill.md — Tool responsibilities (Graph / SQL / Vector)


This system uses 3 different data backends for different kinds of information:

## 1) Graph DB (relations between 2+ entities)
**Data source:** Neo4j (tools/graph_tool.py)

**Use when the query needs relationships**, e.g.
- Relation-based questions (A relates to B)
- Multi-hop reasoning over connected entities
- “Which hotels/rooms are linked to these amenities/policies/destinations via rules or relationships?”
- “Find chains” (Hotel -> Area -> Attraction -> Guest preference)

**Store in Graph:**
- Entities as nodes
- Relationships as edges connecting 2+ nodes
- Example relationship types:
  - `(:Hotel)-[:LOCATED_IN]->(:Area)`
  - `(:Hotel)-[:OFFERS]->(:Amenity)`
  - `(:Policy)-[:APPLIES_TO]->(:RoomType)`
  - `(:Attraction)-[:NEAR]->(:Area)`

**Graph tool contract (retrieval):**
- Input: natural language query
- Output: list of matching nodes/relationships (structured dicts)

> In this project: use Graph DB for *relationship traversal / entity connectivity*, not for long policy text.

---

## 2) SQL DB (easy / structured information)
**Data source:** SQL via tools/hotel_sql_tool.py and modules/hotel_sql_utils.py

**Use when the query needs fast structured fields**, e.g.
- Exact filters and ranges
- Sorting & constraints
- Facts stored as columns:
  - price ranges
  - rating, occupancy limits
  - availability flags
  - simple “must-have” / “cannot” fields
- Queries where deterministic structured answers are required

**SQL tool contract (retrieval):**
- Input: query text (or parsed filters from planner)
- Output: rows/records (structured dicts)

> In this project: SQL is for *quick exact facts*, not for semantic policy passages.

---

## 3) Vector DB (details information of policy and description)
**Data source:** FAISS local index (scripts/build_faiss_hotels_index.py + tools/rag_tool.py)

**Use when the query needs semantic retrieval**, especially:
- Hotel/room **description** paragraphs
- **Policy** text (check-in/out, deposit rules, pet policy, family rules)
- “Find the relevant paragraph that supports the rule” (quote-level grounding)

**Vector tool contract:**
- Input: query text
- Output: top-k chunks with:
  - `content` (chunk text)
  - `metadata` (stored in sidecar; not embedded)
  - `section` (policy/description/activities/etc.)
  - `score`

**Metadata filtering rule:**
- FAISS retrieves candidates first.
- Then metadata filters are applied in Python (because FAISS built-in filtering is not natively implemented in this repo).

> In this project: Vector DB is the primary source for *long-form semantic text grounding*.

---

## Decision guide (which DB to use)
1. Does the question require **relations between multiple entities / graph traversal**?
   - ✅ Graph DB
2. Does it require **exact structured facts / filters / ranges**?
   - ✅ SQL DB
3. Does it require **policy/description passages that must be semantically matched**?
   - ✅ Vector DB (FAISS)

If the query mixes these needs, Planner can request multiple tools and `modules/total_info.py` aggregates results.
