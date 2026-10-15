# Guides & Charter — simplified prototype

Approved request reflected: no visible revision numbers, review workflow, composition/applicability tab, or quality gate before publication.

Standalone document library with search, type/publication filters; content editing and preview; publish, withdraw publication, and explicit confirm-to-delete. Demo-only in-memory state.

**Integration considerations:** The real backend currently maintains immutable guide revisions and composed recipe references. Hiding revision numbers and composition from this simplified UI does not remove those source records. Actual deletion requires a retention/reference policy and authorization review, rather than pretending a local UI deletion also deletes historical evidence.