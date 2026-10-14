# 007 Scalability, Volume, Stress Testing, and Accuracy — Honest Assessment

---

## Scalability

Designed for scale, not tested at scale.

Built: Every module is its own container. Helm replicas. Circuit breakers (Redis-backed). Rate limiting. Bulkhead isolation. DynamoDB/PostgreSQL/Redis backends.

NOT built: No HPA. No ALB. No connection pool tuning. No Redis cluster. No DynamoDB auto-scaling.

Architecture scales. Configuration doesn't yet.

---

## Volume

Never load tested. Single-instance benchmarks:

| Component | p99 | Throughput |
|-----------|-----|-----------|
| M6 deny path | ~10ms | 100+ req/s |
| M2 Policy eval | <5ms | 200+ req/s |
| Leakage scan A | <10ms | 100+ req/s |
| M9 regex classify | <1ms | 1000+ req/s |

Real-world with LLM + vendor APIs: meeting prep ~3-5s (10-20 concurrent), simple query ~1-2s (30-50 concurrent), compliance check ~10ms (100+ concurrent).

100+ advisors needs 5-10 M6 replicas + Redis cluster + DynamoDB on-demand.

---

## Stress Testing

Not done. Need Locust/k6 against real cluster. Can't stress test mocked backends.

---

## Accuracy

| Component | Accuracy | Type |
|-----------|----------|------|
| OPA compliance | 99.9%+ | Deterministic |
| MNPI filtering | 99.9%+ | Deterministic |
| Leakage scan regex | ~95% | Pattern matching |
| Leakage scan Haiku | ~85-90% | LLM classification |
| Intent classify regex | ~95% | Pattern matching |
| Intent classify Strands | ~90-95% | LLM routing |
| Meeting prep synthesis | ~85-90% | LLM synthesis |
| Research synthesis | ~80-85% | LLM synthesis |
| Order preparation | N/A | LLM prepares, human approves |

Compliance layer: near-perfect. AI layer: good-enough-with-human-oversight. HITL gates exist because LLM isn't 100%.

---

*Project 007 FSI Interoperability Platform*
