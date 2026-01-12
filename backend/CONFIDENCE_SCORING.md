# Confidence Scoring Methodology

## Overview

The Contract Analyzer's confidence scores (0-100) reflect the system's certainty in its compliance determinations. These scores are computed by the LLM and then adjusted based on quote validation results.

## How Confidence is Determined

### 1. Initial LLM-Generated Confidence

The LLM generates an initial confidence score based on:

**Rubric Coverage Analysis:**
- How many of the required criteria from the rubric are explicitly addressed in the evidence
- Strength and specificity of the contract language
- Presence of explicit requirements vs. vague mentions

**Evidence Quality:**
- Number of relevant evidence chunks retrieved (out of top-5 BM25 chunks)
- Alignment between evidence and compliance criteria
- Presence of explicit policy language vs. implied requirements

**Contradiction Detection:**
- Conflicting statements in the contract
- Ambiguous or conditional language ("may", "should" vs. "must", "shall")
- Exceptions or carve-outs that weaken requirements

### 2. Quote Validation Adjustments

After LLM analysis, the system validates all quoted text against source evidence:

**Full Quote Validation (No Adjustment):**
- All LLM-generated quotes found verbatim in evidence
- Confidence score unchanged

**Partial Quote Removal (Proportional Penalty):**
```python
removed_count = original_quotes - validated_quotes
confidence_penalty = min(20, removed_count * 10)  # 10% per removed quote, max 20%
adjusted_confidence = max(20, original_confidence - confidence_penalty)
```

**All Quotes Removed (Severe Penalty):**
```python
adjusted_confidence = min(original_confidence, 30)  # Cap at 30%
```

**Rationale Annotation:**
- System appends note to rationale: `[X of Y quotes removed during validation]`
- This provides audit trail and transparency

### 3. Confidence Score Ranges

| Range | Interpretation | Typical Scenarios |
|-------|---------------|-------------------|
| **90-100%** | Very High Confidence | Multiple explicit requirements found, all quotes validated, no contradictions |
| **70-89%** | High Confidence | Most requirements found, minor gaps or implied requirements, quotes validated |
| **50-69%** | Moderate Confidence | Some requirements found, significant gaps, or some quotes removed |
| **30-49%** | Low Confidence | Few requirements found, mostly implied, or many quotes removed |
| **0-29%** | Very Low Confidence | Minimal/no requirements found, or all quotes failed validation |

### 4. Failure Modes and Adjustments

**OCR-Needed Documents:**
- If `needs_ocr=true` (low text density detected), confidence may be lower
- Scanned/image-based PDFs have reduced text extraction quality
- System logs warning but proceeds with analysis

**Short Evidence:**
- If document is very short (< 3 pages), confidence may be lower
- Less context available for LLM analysis
- Higher risk of missing requirements

**Ambiguous Contract Language:**
- Use of "should", "may", "strives to" reduces confidence vs. "must", "shall", "requires"
- Conditional requirements ("if applicable", "where feasible") reduce confidence
- LLM trained to detect and penalize weak language

## Examples

### Example 1: High Confidence (95%)

**Requirement:** Password Management  
**Evidence Found:**
- "All passwords MUST be at least 12 characters"
- "Salted hashing (bcrypt) SHALL be used for password storage"
- "Account lockout after 5 failed attempts"
- "Privileged credentials stored in HashiCorp Vault"

**Analysis:**
- 4/8 rubric criteria explicitly covered
- Strong mandatory language ("MUST", "SHALL")
- All 4 quotes validated
- **Confidence: 95%** (no adjustment needed)

### Example 2: Moderate Confidence with Quote Removal (55%)

**Requirement:** IT Asset Management  
**Initial LLM Output:** Confidence 75%  
**Quotes Generated:** 3 quotes  
**Validation Result:** 1 quote validated, 2 removed (hallucinated)

**Adjustment:**
```python
removed = 2
penalty = min(20, 2 * 10) = 20%
adjusted = max(20, 75 - 20) = 55%
```

**Final Confidence: 55%** with note `[2 of 3 quotes removed during validation]`

### Example 3: Low Confidence - All Quotes Removed (28%)

**Requirement:** TLS Encryption  
**Initial LLM Output:** Confidence 80%  
**Quotes Generated:** 4 quotes  
**Validation Result:** 0 quotes validated (all hallucinated)

**Adjustment:**
```python
all_removed = True
adjusted = min(80, 30) = 30%
# Further reduced due to lack of evidence support
final = 28%
```

**Final Confidence: 28%** with note `[4 quotes removed - not found in retrieved evidence]`

## Transparency and Auditability

All confidence adjustments are:
1. **Logged** with job_id and requirement
2. **Annotated in rationale** (user-visible in UI)
3. **Tracked in metadata** (timings_ms, removed_count)
4. **Deterministic** (same input → same adjustment)

## Best Practices for Interpretation

**For Reviewers:**
- Confidence < 50% → Manual review recommended
- Confidence < 30% → High risk, likely missing requirements
- Check rationale for quote removal notes
- Verify OCR warning flag if present

**For System Tuning:**
- Adjust BM25 retrieval if many low-confidence results
- Review LLM prompts if frequent quote hallucination
- Consider OCR preprocessing for scanned contracts
- Tune confidence penalties based on validation patterns

## Future Enhancements

**Potential Improvements:**
- Multi-model ensemble scoring (average multiple LLM outputs)
- Calibration against human-labeled ground truth
- Evidence coverage percentage (% of rubric criteria found)
- Consistency checking across multiple document sections
- Confidence intervals (e.g., 75% ± 10%)
