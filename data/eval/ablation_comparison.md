# MedAgentQA Ablation Study Results

Evaluated on 50 real patient questions from cMedQA2

| Metric | v0 | v1 | v2 | v3 | v4 | vFinal |
|--------|--------|--------|--------|--------|--------|--------|
| medical_safety_rate | 0.320 | 0.400 (+0.080) | 0.600 (+0.280) | 0.260 (-0.060) | 0.860 (+0.540) | 0.600 (+0.280) |
| structured_answer_rate | 0.080 | 0.120 (+0.040) | 0.080 | 0.060 (-0.020) | 1.000 (+0.920) | 0.960 (+0.880) |
| dept_suggestion_rate | 0.440 | 0.420 (-0.020) | 0.720 (+0.280) | 0.460 (+0.020) | 0.920 (+0.480) | 0.640 (+0.200) |
| no_diagnostic_claim_rate | 0.960 | 0.960 | 0.900 (-0.060) | 0.960 | 0.920 (-0.040) | 0.940 (-0.020) |
| graphrag_route_rate | 0.280 | 0.280 | 0.280 | 0.380 (+0.100) | 0.280 | 0.380 (+0.100) |
| avg_answer_length | 726.4 | 726.4 | 1115.5 | 724.3 | 1023.3 | 1159.1 |

## Version Descriptions

- **v0**: Baseline (raw migration)
- **v1**: + Domain prompt tuning (only)
- **v2**: + Temperature tuning (only)
- **v3**: + Router keywords (only)
- **v4**: + Strict RAG constraint (only)
- **vFinal**: All optimizations combined