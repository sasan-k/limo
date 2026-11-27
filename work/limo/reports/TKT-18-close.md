---
ticket: TKT-18
result: done
---
# Close report TKT-18

## Applied
- context/INDEX.md: real adapters + router
- context/stack.md: httpx runtime, respx
- context/testing.md: contract suite
- context/security.md: token env names
- ADRs: ADR-12 accepted earlier (Q-13)

## Drift (code differs from plan — code wins)
- shared `limo/hosts/http.py` (plan allowed it if jscpd found a clone; it did)
