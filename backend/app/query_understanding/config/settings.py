"""
Settings and configuration for query understanding module.

This module centralizes all threshold values, parameters, and configuration
constants used across semantic mapping and tag graph expansion services.
"""

# ============================================================================
# Semantic Mapping Configuration
# ============================================================================

# Minimum similarity score threshold for semantic tag mapping
# Tags below this threshold will be filtered out
SEMANTIC_SCORE_THRESHOLD: float = 0.53

# Delta value for determining "close" scores
# Used to identify alternative tags with similar scores
SEMANTIC_CLOSE_SCORE_DELTA: float = 0.1

# Top K results to retrieve for semantic mapping
SEMANTIC_TOP_K: int = 5

# ============================================================================
# Tag Graph Expansion Configuration
# ============================================================================

# Minimum mapping score for initial tag mapping from user query
MIN_MAPPING_SCORE: float = 0.53

# Minimum score for edges in the tag similarity graph
# Edges below this threshold are not traversed for expansion
MIN_EDGE_SCORE: float = 0.72

# Minimum confidence score for expanded results
# Results below this threshold are filtered out
MIN_CONFIDENCE: float = 0.70

# Maximum number of expanded tags per category
MAX_PER_CATEGORY: int = 3

# Weight factor for expansion scoring
EXPANSION_WEIGHT: float = 0.9
