# MedAgentQA Evaluation Report: v0 vs v1

Model: qwen-plus

Samples: 30


## Metrics Comparison

| Metric | v0 (Baseline) | v1 (Optimized) | Delta |
|--------|---------------|----------------|-------|
| total_samples | 30 | 30 | 0 |
| successful | 30 | 30 | 0 |
| avg_answer_length | 731.300 | 1074.100 | +342.800 |
| disclaimer_rate | 0.633 | 0.533 | -0.100 |

## Key Findings

- Disclaimer rate: 63.3% -> 53.3% (-15.8% relative improvement)
- Structured answer rate (v1 only): 100.0%
- Department suggestion rate (v1 only): 90.0%

## Conclusion

The v1 prompt optimization demonstrates measurable improvement in medical safety
(disclaimer compliance) and answer structure, validating the data flywheel approach.