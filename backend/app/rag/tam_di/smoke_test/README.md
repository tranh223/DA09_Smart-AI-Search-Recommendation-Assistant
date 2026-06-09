# Smoke Tests

Quick validation tests for core modules.

## Running the tests

### Test graph_tool with Anaconda env vinvuong2

From the project root in Anaconda Prompt:

```bat
conda run -n vinvuong2 python smoke_test\test_graph_tool.py
```

The graph test reads `GRAPH_DB_URL`, `GRAPH_DB_USER`, `GRAPH_DB_PASSWORD`, and
`GRAPH_DB_DATABASE` from `.env`.

### Test user_profile_tool

```powershell
cd smoke_test
python test_user_profile_tool.py
```

Expected output:
```
============================================================
SMOKE TEST: user_profile_tool
============================================================
TEST: Load all users
✓ Loaded N users

TEST: Get user by ID
✓ Found user: Name (user_id)

...

============================================================
✓ ALL TESTS PASSED
============================================================
```

## Benchmark user_profile_tool

Focused benchmark specifically for `user_profile_tool.py` with 12 performance scenarios.

```powershell
cd smoke_test
python benchmark_user_profile_tool.py
```

### Coverage

Tests all core operations:
- **Load operations** (2): Cold start, cached access
- **Search by ID** (3): Direct lookup, profile search
- **Destination search** (3): Exact & partial matching
- **Preference extraction** (2): User preferences retrieval
- **Complex filters** (3): Budget, traveler type, amenities

### Performance Metrics

Collects:
- **Latency**: Min, Max, Average, Median, P95, P99 (ms)
- **Per-operation breakdown**: Individual operation performance
- **Throughput**: Iterations per scenario
- **Threshold validation**: Checks against expected metrics

### Sample Output

```
[1/12] LOAD_001: Load all users (cold start)
  Latency: 245.32ms (avg over 1 iterations)
  Result: 15
  Expected: latency < 500ms
  ✓ PASS

[2/12] LOAD_002: Load all users (cached)
  Latency: 2.15ms (avg over 100 iterations)
  Result: 15
  Expected: latency < 5ms (avg)
  ✓ PASS

...

================================================================================
BENCHMARK SUMMARY
================================================================================

Total Scenarios: 12
Successful: 12
Failed: 0

--- LATENCY STATISTICS (ms) ---
  Average:     28.45ms
  Min:         2.15ms
  Max:         245.32ms
  Median:      18.50ms
  P95:         125.00ms
  P99:         200.00ms

--- BREAKDOWN BY OPERATION ---
  load_all:
    Calls:   2
    Avg:     123.74ms
    Min/Max: 2.15ms / 245.32ms
  get_by_id:
    Calls:   2
    Avg:     5.32ms
    Min/Max: 4.21ms / 6.43ms
  ...
```

Results saved as JSON to `results/user_profile_tool_benchmark_*.json`.

## Benchmark graph_tool

Runs graph smoke tests first, then measures Neo4j metadata, count, and retrieval latency.

```bat
conda run -n vinvuong2 python smoke_test\benchmark_graph_tool.py
```

Results saved as JSON to `results/graph_tool_benchmark_*.json`.

## Benchmark RAG Pipeline

Comprehensive benchmark with ~20 diverse use cases evaluating latency, accuracy, and end-to-end performance.

```powershell
cd smoke_test
python benchmark_rag_pipeline.py
```


### Benchmark Coverage

The benchmark includes 20 use cases across 7 categories:

1. **Simple Factual Queries** (3 cases)
   - Destination info, hotel search, activity recommendations

2. **User Profile-Based Queries** (3 cases)
   - Personalized recommendations, budget constraints, traveler type matching

3. **Complex Multi-Step Queries** (3 cases)
   - Multi-criteria search, comparisons, trip planning

4. **Constraint-Based Queries** (3 cases)
   - Group travel, pet-friendly, family-friendly

5. **Preference Refinement** (3 cases)
   - Negative preferences, safety-focused, amenity-focused

6. **Context-Aware Queries** (3 cases)
   - Real estate integration, seasonal planning, transport integration

7. **Advanced Reasoning** (2 cases)
   - Cross-destination comparison, hidden gems discovery

### Metrics Collected

- **Latency**: Min, Max, Average, P95 (in ms)
- **Accuracy**: Keyword matching + response length scoring (0-1 scale)
- **Category Breakdown**: Metrics by use case category
- **Detailed Results**: Saved to `results/benchmark_YYYYMMDD_HHMMSS.json`

### Sample Output

```
================================================================================
RAG PIPELINE BENCHMARK
================================================================================
Running 20 use cases...

[1/20] UC01: Simple destination info
  ✓ 245.3ms | Accuracy: 0.85

[2/20] UC02: Hotel search
  ✓ 312.1ms | Accuracy: 0.78

...

================================================================================
BENCHMARK RESULTS SUMMARY
================================================================================

Total Use Cases: 20

--- LATENCY (ms) ---
  Average:  298.5ms
  Min:      185.2ms
  Max:      456.8ms
  P95:      421.3ms

--- ACCURACY (0-1) ---
  Average:  0.812
  Min:      0.645
  Max:      0.950

--- BREAKDOWN BY CATEGORY ---
  factual:
    Cases:    3
    Avg Lat:  256.4ms
    Avg Acc:  0.845
  personalized:
    Cases:    3
    Avg Lat:  312.1ms
    Avg Acc:  0.798
  complex:
    Cases:    3
    Avg Lat:  387.2ms
    Avg Acc:  0.756
  ...

Detailed results saved to: results/benchmark_20260605_143022.json
```

## Tests included

- **test_load_users**: Verify user data loads from `data/vinsmartfuture_users.json`
- **test_get_user_by_id**: Find a specific user by user_id
- **test_search_user_profile**: Search users by ID or query
- **test_get_user_preferences**: Extract user preferences (long-term + session)
- **test_search_by_destination**: Find users by destination
- **test_user_data_structure**: Validate required data fields

## Adding more tests/benchmarks

1. Add test functions to `test_user_profile_tool.py` and call them from `main()`
2. Add use cases to `BENCHMARK_CASES` list in `benchmark_rag_pipeline.py`
3. Update accuracy evaluation logic in `evaluate_accuracy()` for custom scoring

## Results Analysis

Benchmark results are saved as JSON and can be analyzed with:

```python
import json
with open("results/benchmark_YYYYMMDD_HHMMSS.json") as f:
    data = json.load(f)
    print(data["summary"])
```

