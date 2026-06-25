# ClinTranslate v4 — Pipeline Run Summary
**Run Timestamp:** 2026-06-25 14:47:54  
**Tool:** ClinTranslate v4 Agentic (LangGraph 5-Agent Pipeline)

---

## Run Statistics
| Metric | Value |
|---|---|
| Total Programs Processed | 8 |
| 🟢 Auto-Approved | 0 |
| 🟡 Review Required | 6 |
| 🔴 Rejected | 2 |
| Total SAS LOC Processed | 548 |
| Total Agent Runtime | 440.4s |
| Avg Cosine Score | 0.611 |
| Estimated Time Saved | 19.88 hrs vs 20.0 hrs manual |
| Avg % Time Reduction | 99.4% |

---

## Execution Order (Dependency-Resolved)
1. adae_merge.sas
2. adtte.sas
3. t_ae_summ.sas
4. adlb_baseline.sas
5. advs.sas
6. adcm.sas
7. sdtm_lb.sas
8. adsl.sas

---

## Per-Program Results
| File | Score | Validation | Decision | Time |
|---|---|---|---|---|
| adae_merge.sas | 0.7083 | valid | 🟡 REVIEW_REQUIRED | 45.2s |
| adtte.sas | 0.6098 | valid | 🟡 REVIEW_REQUIRED | 70.2s |
| t_ae_summ.sas | 0.6782 | valid | 🟡 REVIEW_REQUIRED | 47.9s |
| adlb_baseline.sas | 0.5342 | valid | 🔴 REJECTED | 43.1s |
| advs.sas | 0.6212 | valid | 🟡 REVIEW_REQUIRED | 82.4s |
| adcm.sas | 0.6127 | valid | 🟡 REVIEW_REQUIRED | 46.6s |
| sdtm_lb.sas | 0.5482 | valid | 🔴 REJECTED | 46.6s |
| adsl.sas | 0.575 | valid | 🟡 REVIEW_REQUIRED | 58.4s |

---

## Agent Log
- Found 8 SAS file(s) in ./data/sample_sas
- Execution order: ['adae_merge.sas', 'adtte.sas', 't_ae_summ.sas', 'adlb_baseline.sas', 'advs.sas', 'adcm.sas', 'sdtm_lb.sas', 'adsl.sas']
- No %INCLUDE dependencies detected — files are independent
- ✅ adae_merge.sas → score=0.7083, 45.2s
- ✅ adtte.sas → score=0.6098, 70.2s
- ✅ t_ae_summ.sas → score=0.6782, 47.9s
- ✅ adlb_baseline.sas → score=0.5342, 43.1s
- ✅ advs.sas → score=0.6212, 82.4s
- ✅ adcm.sas → score=0.6127, 46.6s
- ✅ sdtm_lb.sas → score=0.5482, 46.6s
- ✅ adsl.sas → score=0.575, 58.4s
- ✅ adae_merge.sas — syntax valid
- ✅ adtte.sas — syntax valid
- ✅ t_ae_summ.sas — syntax valid
- ✅ adlb_baseline.sas — syntax valid
- ✅ advs.sas — syntax valid
- ✅ adcm.sas — syntax valid
- ✅ sdtm_lb.sas — syntax valid
- ✅ adsl.sas — syntax valid
- 🟡 adae_merge.sas → REVIEW_REQUIRED | Medium cosine similarity (0.7083) — translation likely correct but requires reviewer confirmation
- 🟡 adtte.sas → REVIEW_REQUIRED | Medium cosine similarity (0.6098) — translation likely correct but requires reviewer confirmation
- 🟡 t_ae_summ.sas → REVIEW_REQUIRED | Medium cosine similarity (0.6782) — translation likely correct but requires reviewer confirmation
- 🔴 adlb_baseline.sas → REJECTED | Low cosine similarity (0.5342) — insufficient knowledge base coverage; manual translation recommended
- 🟡 advs.sas → REVIEW_REQUIRED | Medium cosine similarity (0.6212) — translation likely correct but requires reviewer confirmation
- 🟡 adcm.sas → REVIEW_REQUIRED | Medium cosine similarity (0.6127) — translation likely correct but requires reviewer confirmation
- 🔴 sdtm_lb.sas → REJECTED | Low cosine similarity (0.5482) — insufficient knowledge base coverage; manual translation recommended
- 🟡 adsl.sas → REVIEW_REQUIRED | Medium cosine similarity (0.575) — translation likely correct but requires reviewer confirmation

---

## Time Gain Story (Interview/LinkedIn Ready)
> *"On a 8-program batch using BioMarin SDTM patterns, ClinTranslate v4 reduced average 
> translation time from ~2.5 hours to under 1.0 minutes per program — 
> an estimated 99.4% reduction — with 0 of 8 programs auto-approved 
> and 6 flagged for lightweight review."*

---
*ClinTranslate v4 | github.com/ravinsun/clintranslate*
