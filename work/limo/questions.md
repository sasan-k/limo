# Open Questions — limo
<!-- Never guess. Log it here, mark what it blocks, continue with the rest. -->
<!-- Status: open | answered. When answered, the answer is final and stages re-run on the blocked items. -->

## Q-1 [answered] What makes the UI "simple and modern" in a checkable way?
- from: REQ-37 · raised by: spec
- blocks: none (may add a styling ticket)
- options: shadcn/ui default theme, light + dark, no custom design · a reference design you provide
- answer: shadcn/ui with a good custom color theme, dark and light modes.

## Q-2 [answered] How does a user start a feature: where do its requirement files come from?
- from: REQ-15 · raised by: spec
- blocks: SC-19, SC-20, SC-21 (TKT-6)
- options: paste/upload in the UI → Limo commits `work/<feature>/requirements/` · file already in the project repo; user picks it in the UI
- answer: Pasted in a UI intake form. Stored locally (see Q-10), not committed.

## Q-3 [answered] Does the runner start by itself after spec, and can a user pause/resume a project?
- from: REQ-14 · raised by: spec
- blocks: TKT-6
- options: auto-run with pause/resume · user starts each ticket
- answer: A UI button turns the runner on/off; it starts off.

## Q-4 [answered] One ticket at a time across all projects, or per project? (same as context Q-2)
- from: REQ-16 · raised by: spec
- blocks: none yet (scenarios use one project)
- options: across all projects · per project
- answer: One ticket at a time for now; design must scale to more later (NFR-11).

## Q-5 [answered] When is a ticket's issue created, and how is its status shown on the issue?
- from: REQ-27 · raised by: spec
- blocks: SC-30, SC-31 (TKT-8)
- options: all issues at spec time, status as label `limo:<status>` · issue created when planning starts
- answer: All issues at spec time; status as label `limo:<status>`.

## Q-6 [answered] Does a human reply on an escalated issue re-run the resolver by itself, and does that count toward the 2-resolve limit?
- from: REQ-28 · raised by: spec
- blocks: SC-39 (TKT-10)
- options: reply auto-triggers the resolver, not counted · human removes `factory:needs-human` to resume
- answer: Yes, not counted. The user can also type the response in Limo's inbox and press Continue.

## Q-7 [answered] Does a price change apply to past usage or only to new usage?
- from: REQ-4 · raised by: spec
- blocks: none (SC-10 covers new usage only)
- options: only new usage (cost stored when recorded) · recompute all
- answer: Only new usage; past costs never change.

## Q-8 [answered] On the agent card, is "last run time" the duration, the finish time, or both?
- from: REQ-39 · raised by: spec
- blocks: SC-40 (TKT-12)
- options: duration + finish time · duration only
- answer: Duration + finish time.

## Q-9 [answered] Are prompts global (Limo's `skills/`), or can a project override them?
- from: REQ-42 · raised by: spec
- blocks: SC-46, SC-47, SC-48 (TKT-14)
- options: global only in v1 · per-project override stored in the workspace
- answer: Shared (global) only.

## Q-10 [answered] Requirements and spec output must be on `main` before ticket branches start. How do they get there?
- from: REQ-45 · raised by: spec
- blocks: SC-19, SC-20, SC-21, SC-49 (TKT-6)
- options: one spec merge request `limo/<feature>/spec` (requirements + spec output) a human approves before tickets start · commit straight to `main`
- answer: Not needed: `work/<feature>/` stays local in the workspace (excluded via `.git/info/exclude`), never committed or pushed; no spec merge request.

## Q-11 [answered] When the user turns the runner off while a run is active, what happens to that run?
- from: REQ-46 · raised by: spec
- blocks: SC-52 (TKT-16)
- options: the active run finishes, no new run starts · the active run is stopped now and marked interrupted
- answer: The active run finishes; no new run starts.

## Q-12 [answered] Is an agent's budget per ticket (e.g. build may spend $2 on each ticket) or a total across all tickets?
- from: REQ-49 · raised by: spec
- blocks: SC-55, SC-57 (TKT-17)
- options: per agent per ticket · total per agent across the feature
- answer: Per agent per ticket.

## Q-13 [open] (deferred by user 2026-11-26 — revisit when planning the first repo-host ticket, TKT-7) Test the GitLab and GitHub adapters against recorded HTTP fixtures, or against live sandbox repos?
- from: NFR-8 (ADR-12 proposed) · raised by: architecture
- blocks: none (ADR-12 stays proposed until answered; adapters can be built either way)
- options: recorded HTTP in every run, re-recorded on demand from sandbox repos · live sandbox repos in CI (needs tokens)
- answer:

## Q-14 [open] GitHub/GitLab do not let you approve your own merge request. Which identity opens Limo's merge requests?
- from: REQ-30 · raised by: human (TKT-1 review, 2026-11-26)
- blocks: TKT-7
- options: separate identity (GitHub App / bot account) so the human approves and auto-merge runs · solo mode: the human merging counts as approval, no auto-merge
- answer:
