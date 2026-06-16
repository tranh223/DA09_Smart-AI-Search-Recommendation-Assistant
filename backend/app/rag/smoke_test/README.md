# Smoke Tests

Quick validation for the hotel-only RAG pipeline.

## Core tests

```powershell
python smoke_test/test_structured_rag_input.py
python smoke_test/test_pipeline_smoke.py
python smoke_test/test_hotel_entity_resolver.py
python smoke_test/test_rag_tool_smoke.py
python smoke_test/test_graph_tool.py
```

## Benchmarks

```powershell
python smoke_test/benchmark_structured_pipeline.py
python smoke_test/benchmark_structured_pipeline.py --limit 3
python smoke_test/benchmark_structured_pipeline.py --case FEATURE_FAMILY_KIDS
```

Structured pipeline benchmark reports are saved under `smoke_test/results/`.
