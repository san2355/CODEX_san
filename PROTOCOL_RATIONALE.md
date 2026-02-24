# Protocol Rationale (Short)

This version implements a deterministic, safety-first Doctor Brain flow for HFrEF titration decisions.

## Goal & Deliverables
1. **Initiation priority rule:** if any medication is at dose `0`, initiate the **first** zero-dose class in fixed order:
   `RAASi -> BB -> MRA -> SGLT2i` (titration `+1`).
2. **Up-titration priority rule:** if all classes are `>=1`, up-titrate the **first** class in the same order that is `<4` (titration `+1`).

## Why this design
- **Safety first:** immediate down-titration triggers (bradycardia, hyperkalemia, hypotension) are evaluated before escalation.
- **Single-action output:** each visit returns one clear recommendation (`Sequence`, `titration`, `criteria`) to avoid conflicting simultaneous actions.
- **Predictable ordering:** fixed RAASi→BB→MRA→SGLT2i ordering removes ambiguity and keeps decisions reproducible.

## Operational interpretation
- Use the action as the next step for that visit.
- Re-evaluate at the next visit with updated labs/symptoms/vitals and repeat the same deterministic flow.
