# MedAgentQA Ablation Study Results

Evaluated on 15 real patient questions from cMedQA2

| Metric | v0 | v1 | v2 | v3 | v4 | vFinal |
|--------|--------|--------|--------|--------|--------|--------|
| medical_safety_rate | 0.200 | 0.133 (-0.067) | 0.600 (+0.400) | 0.267 (+0.067) | 0.867 (+0.667) | 0.600 (+0.400) |
| structured_answer_rate | 0.000 | 0.000 | 0.067 (+0.067) | 0.000 | 1.000 (+1.000) | 0.933 (+0.933) |
| dept_suggestion_rate | 0.267 | 0.133 (-0.134) | 0.600 (+0.333) | 0.267 | 0.933 (+0.666) | 0.467 (+0.200) |
| no_diagnostic_claim_rate | 1.000 | 1.000 | 0.933 (-0.067) | 1.000 | 0.800 (-0.200) | 1.000 |
| graphrag_route_rate | 0.267 | 0.267 | 0.267 | 0.400 (+0.133) | 0.267 | 0.400 (+0.133) |
| avg_answer_length | 745.4 | 726.9 | 1177.6 | 742.7 | 1058.8 | 1195.7 |

## Version Descriptions

- **v0**: Baseline (raw migration)
- **v1**: + Domain prompt tuning (only)
- **v2**: + Temperature tuning (only)
- **v3**: + Router keywords (only)
- **v4**: + Strict RAG constraint (only)
- **vFinal**: All optimizations combined