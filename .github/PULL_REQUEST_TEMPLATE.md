## What does this change?

<!-- One or two sentences on what and why. -->

## Checklist

- [ ] `ruff check rocqet tests scripts` passes
- [ ] `pytest -q` passes
- [ ] `cd web && npx tsc --noEmit` passes (if the UI changed)
- [ ] Added/updated tests for behavior changes
- [ ] Serving stays LLM-free (no model calls in the `/search` request path)

## Related issues

<!-- Closes #... -->
