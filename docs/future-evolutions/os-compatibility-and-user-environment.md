# Future evolution — OS Compatibility & User Environment

> **Status:** Proposed **small, independent** product enhancement; no implementation, migrations, issues or release plan approved by this page.  
> **Decision context:** October 2026 refinement.  
> **Scope:** User self-declared Windows/Linux environments; mandatory supported-OS declaration for Harness and Framework catalog records; practical compatibility filtering and opportunity discovery.  
> **Related future experience:** [Role-Based User Experience & Guided Navigation](role-based-user-experience-and-guided-navigation.md).  
> **Other dependencies:** [Product Definition](../product-definition.md) · [Technology Catalog](../product-definition.md#4-catalog-and-definition-of-an-ai-solution) · [Platform Architecture & Data Governance](../platform-architecture-and-data-governance.md) · [Composable Setup Guides](composable-setup-guides.md) · [Deployment & Adoption Planning](deployment-and-adoption-planning.md) · [Technology Accessibility & Pricing Management](technology-accessibility-and-pricing.md) · [Users & Access](../users-and-access.md).

## 1. Motivation and precise product decisions

AI Compass should not recommend or deploy a Harness/Framework as if it were usable in the engineer's environment when that software does not support the available operating system. Conversely, **a compelling candidate must not disappear from discovery** merely because the engineer does not currently use its operating system — learning about the benefit may encourage them to install or obtain it.

For the initial scope, support **only two OS families: Windows and Linux**. No macOS, Android, iOS, BSD, distribution-by-distribution support or version-specific feature matrix is required now.

**Confirmed decisions:**

1. Each regular user can **declare which operating systems they have available**, through simple **Windows** and **Linux** checkboxes in their own profile. Save the choices so the user does not have to repeat them on every visit or Task.
2. Each **Harness** and each **Framework** in the technology catalog must declare **which of Windows/Linux it supports**, using the same two-option vocabulary. This becomes a **required classification for newly completed/edited records**; supported set cannot be empty for a record asserted usable.
3. **Both checked = OS-agnostic for this simple feature** (same supported functionality is presumed across Windows and Linux). This is **not** a separate third platform or an additional runtime profile.
4. If practical experience finds a tool too limiting on a particular OS, a Workgroup catalog maintainer may simply **remove that OS from the tool's declared supported set** in a new version. **No extra feature-level exception model, partial-compatibility score, special issue workflow or granular feature matrix.**
5. The regular user's primary tool recommendations prioritize candidates compatible with at least one of the user's currently available OSs, alongside Task relevance, quality, publication, actual access and other established criteria.
6. Interesting tools that only work on the **other OS** remain discoverable in a **clearly distinguished secondary recommendation or candidate list**, stating e.g. **"Requires Linux"** or **"Requires Windows"**. The user may decide to add that OS later.
7. OS compatibility is not the same as **technology catalog accessibility**, a **user's entitlements/permissions**, having a **validated Setup Guide** or having **confirmed first use**. All remain separately represented.
8. This OS enhancement is a **separate future feature page**, even though its fields are consumed by My AI Workspace and later Deployment & Access.
9. Preserve historical benchmark/Run/guide references and existing versions when editing compatibility metadata. This classification does not automatically alter observed results.

## 2. Functional scope and supported states

### 2.1 User environment: available operating systems

User profile field, conceptually **available_os = {windows?, linux?}**:

| Selection | Meaning | Recommendation behavior |
| --- | --- | --- |
| Windows checked, Linux unchecked | User has a Windows environment available. | Windows-supported candidates first; Linux-only candidates secondary but visible. |
| Linux checked, Windows unchecked | User has a Linux environment available. | Linux-supported candidates first; Windows-only candidates secondary but visible. |
| Both checked | Both OS environments available. | Either compatible subset can be considered in the normal recommendations. |
| No preference recorded yet / unset | OS availability **unknown**, e.g. profile not yet configured. | Do **not** invent Windows/Linux from a browser User-Agent. Explain that setting the profile improves recommendations. |
| User deliberately unchecks an OS | The person no longer declares it available. | Recalculate relevance/compatibility view without deleting former sources or assuming tool licenses were revoked. |

Keep **unknown/unconfigured** distinct from "this person has no usable computer"; the UI may require at least one selection on explicit save of a completed OS profile while allowing older incomplete user records to remain marked **unknown**. This is a profile-level, **self-service** setting; normal users should not need a Workgroup member or User Administrator to choose Windows/Linux.

**Do not require one OS per Task** in the first increment. The question is **which OS environments the person can use**, not an exhaustive assignment of 40 tasks to computers. When both systems are available, individual Tasks may happen on either. Task-specific enforced OS, OS versions, virtual machines/containers, employer device inventories and remote workstation management are **out of scope**.

Do not conflate user-selected OS with server deployment platform. Running the AI Compass website on Linux has nothing to do with whether a given collaborator has Windows available for an AI Harness.

### 2.2 Technology Catalog compatibility: Harness and Framework

A Harness or Framework gets a **required supported OS set** over the same universe:

| Harness / Framework compatibility | Representation |
| --- | --- |
| Windows only | **{Windows}** |
| Linux only | **{Linux}** |
| Agnostic / usable on both | **{Windows, Linux}** |
| Not yet researched on older catalog records | Explicit **unknown/unclassified** legacy state, requiring review rather than silently assuming either OS. |

**Supported vs unknown:** require an explicit choice for **new** entries and for normal compatible edits where missing classification is not grandfathered. Existing historical legacy revisions with no classification remain **readable**; do not insert a false "agnostic" default during migration. Where a legacy record's current compatibility is unknown, My AI Workspace indicates **not verified** and does not assert it can run on the person's OS.

A simple Workgroup editing UI can show two toggles/checkboxes:
- [x] Windows
- [x] Linux

A record with both selected is treated as **feature-equivalent** across the two. Do not make separate Windows/Linux versions of every feature, usage capability, task-suitability assessment, success score or billing profile just because a technology supports both.

**Compatibility is editable evidence-backed product metadata**, not a statement that an OS is technologically impossible: the Workgroup may narrow declared availability for product-quality reasons with no additional "partially supported" machinery. Since catalog records are versioned, edits create a new revision, leaving earlier revision identity and original measurements intact.

**Model/Provider:** the user explicitly scoped **mandatory OS declaration to Harnesses and Frameworks**. Do not add duplicate compulsory Windows/Linux fields to Model and Provider catalogs in this increment. A provider or model might have unrelated environmental requirements; those remain normal setup/integration constraints, not a fabricated additional OS field.

### 2.3 Assembled configuration / AI Solution compatibility

An assembled candidate typically includes Model + Provider + Harness and may include a **Framework** with several participant Harnesses. Under this feature's deliberately simple assumption, effective supported OS is the **intersection of the declared OS sets of OS-dependent components** in the configuration.

Examples:

| Harness | Framework | Effective Windows/Linux |
| --- | --- | --- |
| Windows + Linux | No Framework | Windows + Linux |
| Windows only | No Framework | Windows |
| Windows + Linux | Linux only | Linux |
| Windows only | Linux only | **No common supported OS** — cannot claim this assembled setup is supported as-is. |
| Several Harness participants | Framework | Intersect relevant declared sets for components that must operate in the same environment; avoid assigning an individual participant's support to the entire workflow incorrectly. |

**Distributed/remote multi-machine Frameworks:** the simple intersection applies only where the effective configuration is intended to share an OS environment. Some real orchestration might use participants on separate machines/OSs; that is a **future refinement**. Do not invent a cross-OS compatible collective workflow based on unknown topology.

If an essential Harness/Framework's support is **unknown**, the assembled solution must not automatically be labeled supported on both systems. Show **compatibility unknown/not classified**, with clear context. If component sets are disjoint, mark the candidate **not currently runnable as one supported local configuration** and do not recommend it as immediately deployable.

**Scope:** this logic says nothing about Model API availability, Provider entitlements, setup recipe completeness, specific Python versions, Linux distributions or hardware architecture. It is only the simplified Windows/Linux facet. Existing [Setup Guide applicability](composable-setup-guides.md) still determines whether exact setup instructions exist for the chosen versions/environment.

## 3. Engineer experience: rank locally usable tools without hiding alternatives

Integration point: [My AI Workspace](role-based-user-experience-and-guided-navigation.md#4-engineer--my-ai-workspace), **By Task** (primary) and **By Tool** (inverse) projections of job/specialty-relevant work.

1. First determine **Task relevance** and viable measured quality/recommendation status; OS is one necessary constraint, **not** a replacement for evidence quality or Task suitability.
2. Put relevant **OS-compatible** tools in the normal shortlist, using the person's declared available set; highlight actual tool entitlement/access separately.
3. If a high-potential relevant tool is **only supported on an OS the person does not currently have**, show a secondary, nonintrusive entry: "Alternative available with Linux" (or Windows) and the value/Tasks it may unlock. **Do not discard or permanently disqualify it.**
4. If no compatible measured option exists, do not claim "no possible AI"; show the evidence gap, applicable theoretical alternatives if appropriately labeled, and any potentially interesting other-OS option.
5. If the user's OS is unknown, show an explicit **"Set your OS"** affordance, not a false "unsupported" diagnosis; ranking may omit OS priority with a transparent note rather than guessing.
6. In **By Tool** mode, show the same compatible vs other-OS distinction and all profile-relevant Tasks for each candidate.
7. In **AI Solution Detail**, show supported OS, actual profile selection, what platform would be needed, link to matching Setup Guide or applicable variant when available, and existing access status.
8. The global full catalog/Results Explorer remains accessible as **secondary exploration**; do not fill the default engineer page with every unsupported catalog component.

**Accessibility vs OS:** e.g. a Linux-only Harness may be technically compatible with the user's Linux but enterprise-inaccessible due to licensing; conversely an enterprise-accessible Windows-only Harness is not ready for a Linux-only user. Distinguish:
- **OS compatible?**
- **Enterprise technology accessible?**
- **Individual access verified?**
- **Complete configuration and guide ready?**

A user changing their OS profile is **not automatically granted a new license**, equipped, provisioned, or counted as having confirmed first use. The compatibility layer can inform later DAP eligibility checks without doing those actions.

**Data maturity:** an OS-compatible Forecast is still theoretical; a Windows-compatible measured solution does not become a positive recommendation merely by supporting Windows; a failed Benchmark remains visible evidence when appropriate.

## 4. Workgroup catalog editing and lifecycle

- In **Technology Catalog → Harnesses** and **→ Frameworks**, provide two plainly labeled **Windows/Linux supported** checkboxes; clear that both implies OS-agnostic for initial feature purposes.
- On creation of a new classified Harness/Framework, require at least one declared supported OS; avoid a separate required "platform agnostic" switch that contradicts the checkboxes.
- For existing data imported from old schema with no supported_os information, show an **Unknown / needs classification** state and guide the Workgroup to fill it when editing; preserve exact historical data and report incompatibilities through existing schema/data-health mechanisms rather than destructive defaults.
- Remove a supported OS simply by **unchecking** it and saving a new immutable catalog revision. No extra workflow, quality-exception field, reason-code bureaucracy or per-feature compatibility map is required.
- Compatibility metadata can be re-evaluated with updated knowledge, but **old Runs and historical guides keep the environment/version they actually captured**. An updated current compatibility projection may affect future recommendations, never silently rewrite a past experiment as having used a different OS.
- The classification should be visible in relevant catalog views and allow filtering by **Windows, Linux, both, unknown** where needed; do not extend every form/site menu without an actual discovery purpose.
- Avoid changing the technical **AI Solution fingerprint** on the sole basis of a catalog *label* update that did not modify the actual tested executable configuration. A genuine component/configuration version or setup change follows existing exact technical-identity and evidence rules.

**User-managed OS selections** are separate from external Provider entitlement management and from privileged AI Compass account/permission administration. The user edits their own profile under existing authenticated permissions; the Workgroup edits catalog component compatibility under its catalog permission. No automatic self-declaration may escalate access privileges.

## 5. Integration with deployment, forecasts, comparisons and guides

### 5.1 Deployment & Access

The future [DAP](deployment-and-adoption-planning.md) can use profile OS availability and effective configuration compatibility to identify **additional environmental prerequisites** when targeting a person:

- **Compatible and eligible:** normal entitlement, guide and first-use checks still required.
- **Relevant but OS not available:** show "Requires Windows/Linux environment" as a **planning gap**, not as a deployed/verified or immediately runnable target.
- **User later adds OS:** recompute future fit/readiness projections based on their new declaration; don't silently create access requests or overwrite previously selected/historic deployment decisions.

The stated business goal includes *encouraging adoption* of useful AI features by showing the benefit of acquiring the other OS. That is **informational**, not a workflow for purchasing PCs, reimaging workstations, remote installers or credentials.

### 5.2 Technology Watch and Forecasts

Watch entries and task-linked Forecasts may involve proposed configurations requiring an OS. Their existing evidence classification (theoretical) is independent of platform support; use the same Harness/Framework OS sets to explain which audiences could run the candidate. A forecast can still demonstrate theoretical value for a Linux-only candidate in a Windows-heavy organization — show the environmental gap rather than hiding its potential.

Do **not** automatically rewrite Forecasts/Run results or manually asserted benefits because current catalog compatibility changes. Scenario projections can use current OS declarations prospectively while retaining immutable historical references.

### 5.3 Benchmark execution and Setup Guides

- A controlled Run's environment should remain represented by its **exact historically recorded setup**, with versions and deviations; it is evidence, not a replacement for cross-product OS compatibility metadata.
- Composable Setup Guide applicability already considers OS/version/environment. This new feature is **only a coarse two-option catalog availability filter**; it does not certify that every guide works on both declared OSs.
- A Harness declared Windows+Linux may have a shared high-level capability description, but its setup recipe can still contain OS-specific installation steps and prerequisites **when needed**. "Same feature set" does **not** require byte-identical setup instructions.
- When a user switches or adds an OS, present a matching versioned guide/recipe if actually known; missing guide remains missing rather than inventing compatibility.

## 6. Data contract and architecture — additive and minimal

Conceptual, not prescribed table/field names:

| Entity | Suggested information | Data ownership |
| --- | --- | --- |
| **User OS Profile** | Two booleans or enumerated set for Windows/Linux, plus clear unconfigured state; associated with authenticated person or self-service profile and change attribution where appropriate. | Personal profile domain; distinct from User Admin credential fields. |
| **Harness supported_os** | Non-empty Windows/Linux subset for newly completed/edited records, explicit unknown on legacy unclassified revisions. | Versioned Technology Catalog Harness metadata. |
| **Framework supported_os** | Same semantics as Harness. | Versioned Technology Catalog Framework metadata. |
| **Configuration effective_os** | Read-time **derived intersection** and known/unknown flags, referencing exact selected component/configuration revisions. | Shared read projection; **not** a separately hand-maintained product compatibility field. |
| **Personal relevance** | Per Task/per solution compatible/other-OS/unknown label and actual access category, with score/source where relevant. | My AI Workspace / DAP read projection, not duplicated Business Unit catalog. |

**Implementation direction:**
- Use existing Django/PostgreSQL identity, versioned catalog records, JSON Schema evolution and additive migrations as necessary. Do not destroy old fields/revisions or backfill unknowns with false values.
- Reuse the common Demo/Server frontend/data-provider contracts. The real user OS preference in Server mode is stored authoritatively in Server; the independent Demo can simulate it only within its own namespace.
- Self-service profile update requires authentication/CSRF; catalog edits require appropriate existing Workgroup permissions; both need server-side validation and safe optimistic concurrency where entity revisions are shared.
- No external OS detection service, host enumeration, privileged desktop agent, workstation inventory sync or browser User-Agent trust requirement.
- If device compatibility metadata is unavailable because an upstream domain/endpoint is not yet implemented, display **Unknown**, do not silently fall back to Demo guesses.
- The OS choice changes future recommendations/read-model classifications; it should not trigger a new Campaign, Forecast, Test Case, license request or technical solution creation.

## 7. Examples / edge cases to preserve

| Situation | Correct behavior |
| --- | --- |
| User uses Windows; Harness supports Windows+Linux | Harness qualifies for normal OS-based shortlist (assuming other criteria). |
| User uses Windows; Harness supports Linux only | Relevant solution still shown as a **secondary "Requires Linux"** possibility, with its benefits when evidence exists. |
| User uses both | Normal recommendations can include Windows-only, Linux-only and both-supported tools. |
| User has not configured profile OS | Prompt discreetly to set OS; don't pretend compatibility has been verified. |
| Harness both; Framework Linux only | Full assembled configuration marked **Linux** only. |
| Harness Windows only; Framework Linux only | **No common local OS**; don't claim immediate executable compatibility. |
| One component legacy/unknown | Outcome is **unknown or partially constrained**, not automatically both-supported. |
| Workgroup finds Linux experience poor on an otherwise cross-platform Harness | Uncheck Linux; new current catalog revision, **no special defect schema**; old evidence unchanged. |
| Two OSs enabled but setup steps differ | Capability list remains OS-agnostic; guide renders relevant OS-specific procedure if known. |
| User adds Linux to profile | Recommendation prioritization updates, but first-use/access rights do not update automatically. |
| A Linux-compatible tool is enterprise-inaccessible | It is **OS-compatible** and **enterprise-inaccessible** simultaneously; neither property overrides the other. |
| Framework composite Run used Windows, while catalog later expands to Linux | No claim the original Run measured Linux performance; future compatibility classification is prospective. |
| Only a Forecast exists for a Linux-only candidate | Remains clearly theoretical, usable for opportunity exploration without claiming qualified measured solution. |

## 8. Preliminary impact analysis

| Area | Expected impact | Why |
| --- | --- | --- |
| **User Profile UI** | Low–medium | Add 2 self-service checkboxes, persistence and unknown state; no detailed per-Task OS form. |
| **Harness / Framework Catalog** | Low–medium | Required Windows/Linux supported set and versioned validation; no feature-by-OS matrix. |
| **Schema and migrations** | Low–medium | Additive registered attributes, safe handling of legacy unclassified records, no fake "both" backfill. |
| **Compatibility derivation** | Medium | Intersection for single and composite configurations, unknown/contradiction handling. |
| **My AI Workspace ranking** | Medium | OS-aware primary shortlist with a secondary relevant other-OS explanation. |
| **Solution detail and guides** | Low–medium | Clear OS availability and links to valid environment-specific docs. |
| **Deployment / Budget Planning** | Low–medium dependency | Inform eligibility/environmental gaps without entitlement automation. |
| **Benchmarks / Forecasts** | Low | Reuse OS labels prospectively; never rewrite original evidence/maturity. |
| **Authorization and Demo/Server parity** | Cross-cutting | Self-only profile editing, catalog permissions, separated data providers. |

## 9. Draft acceptance criteria

1. A logged-in regular user can open their **own profile** and check **Windows**, **Linux** or **both**; selections persist and appear again at the next visit.
2. A legacy/unconfigured user profile is shown as **OS unknown**, not defaulted from browser/device heuristics.
3. Unchecking one OS later updates the person's preference while retaining other profile/workload attributes.
4. A new Harness requires an explicit Windows/Linux supported selection with **at least one checked**.
5. A new Framework requires the same; both checked is labeled **agnostic** with no separate mandatory switch.
6. Existing old Harness/Framework revisions with no OS information remain readable and marked **unclassified** rather than silently claiming both.
7. Unchecking an OS on a Harness/Framework saves an authorized **new catalog revision**; old record history and exact Run evidence remain accessible.
8. A user with only Windows sees Task-relevant **Windows-compatible** measured solutions in the normal shortlist; Task-relevant Linux-only solutions can still be found as secondary **"Requires Linux"** options.
9. Symmetrically, a Linux-only user can discover relevant Windows-only options without those dominating the default shortlist.
10. A dual-OS user receives normal viable candidates from **both** OS-supported sets.
11. An unconfigured user's unknown OS does not cause an erroneous all-tools-incompatible label or a fabricated OS selection.
12. An individual Harness+Framework candidate obtains supported OS by **intersection**; disjoint sets cannot yield a claimed supported combination.
13. Composite Framework participant constraints are not misattributed to a single participant's measured score, and unknown deployment topology is not automatically assumed cross-OS.
14. A solution remains explicitly **enterprise-inaccessible or person-without-access** when applicable even if its OS is compatible.
15. Changes to OS declarations do **not** automatically grant credentials, create a license request, create a deployment record or mark first use as confirmed.
16. A relevant OS-incompatible candidate still shows its theoretical or measured maturity correctly; "OS works" is not equated with "Benchmark passed".
17. A solution detail can identify a supported OS and link to an existing valid environment-specific Setup Guide without assuming all Windows/Linux recipes are equivalent.
18. No new per-OS feature table, OS-specific performance score, enforced per-Task OS assignment, desktop inventory integration or extra quality exception form is introduced.
19. Ordinary users cannot modify the supported_os of Catalog components; Workgroup catalog editors cannot impersonate users to arbitrarily change their personal OS preferences.
20. Server and Demo have separate OS data and cannot silently exchange/mock-fallback values.
21. An established prior Run, Forecast, Recommendation or frozen DAP snapshot retains its historical version references after compatibility metadata changes.
22. Unsupported/missing compatibility data are surfaced explicitly rather than misrepresented as zero capability or full agnosticism.

## 10. Deliberately deferred design questions

- Whether a user can save an explicitly empty OS set vs only remain **unconfigured**; first version can permit unknown legacy state while requiring >=1 choice when an OS preference is consciously submitted.
- UI wording "agnostic" vs "Windows & Linux": both are one underlying supported-set concept.
- Mixed local/remote Framework orchestration where different participants run on different OSs: do not infer universal execution support from simple set intersection.
- Additional OS families, OS releases, Linux distributions, hardware or containers — future extension, not today's fields.
- Precise ranking interaction between OS compatibility, evidence suitability and access. **Preserve clear categorical semantics** before defining complex scoring weights.
- Classification process for existing unclassified catalog components: light inline review on next maintenance/edit, without destructive migration or mandatory extensive requalification.

These are **implementation refinements**, not reasons to introduce a broader environment modeling product now.

## 11. Non-goals and release/approval boundary

- No per-version/per-OS capability variants or distinction between "good but limited" and "partially supported": simply check or uncheck the supported OS.
- No OS-specific benchmarking obligation, no automatic rerun, no reinterpretation of failed/published historical evidence.
- No credential management, renewal, external account provisioning, purchasing, license allocation or user computer provisioning.
- No authority gained by selecting an OS; technical compatibility does not imply enterprise/provider entitlement.
- No changes to Product Definition or approved issue backlog simply because this proposal exists. A separate explicit issue/implementation plan must be approved; only then update baseline docs as features ship.

This page records the **small, distinct Windows/Linux compatibility evolution**, cross-linked to but **not merged with** the broader Role-Based UX proposal.
