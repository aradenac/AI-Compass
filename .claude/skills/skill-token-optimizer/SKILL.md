---
name: skill-token-optimizer
description: Optimize an existing agent skill for minimum token consumption without losing actionable information. Invoke as the final step of skill authoring.
---

# Skill Token Optimizer

Optimize the target skill for maximum actionable information per token.

## Rules

- Preserve all requirements, constraints, decisions, and operationally relevant information.
- Minimize actual token count, not characters or words.
- Never sacrifice clarity, precision, or reliability for compression.
- Do not introduce new features or change intended behavior.

## Optimization

1. Remove redundancy, filler, generic LLM knowledge, and unnecessary examples.
2. Replace verbose explanations with concise, imperative instructions.
3. Consolidate repeated rules and eliminate redundant headings.
4. Prefer compact Markdown, tables, or structured syntax when token-efficient and unambiguous.
5. Eliminate information already implicit in established conventions.
6. Use progressive disclosure: move rarely needed details into referenced files only if this reduces expected context consumption.
7. Preserve explicit instructions wherever implicit interpretation could produce errors.
8. Avoid cryptic abbreviations and custom syntax unless demonstrably more efficient.

## Verification

- Compare original and optimized token counts using the target model's tokenizer when available.
- Review the changes for semantic loss, ambiguity, and altered behavior.
- Reject optimizations that compromise reliability.
- Apply improvements directly to the target files.

## Output

Report only:
- Original → optimized tokens and percentage saved (measured or estimated).
- Significant optimizations made.
- Any information that could not be safely compressed.

If no meaningful optimization is possible, leave the skill unchanged.
