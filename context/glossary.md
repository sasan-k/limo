# Glossary
<!-- Shared domain language. Spec maintains; every stage uses these exact terms. -->

| Term | Meaning | Code name | Not to be confused with |
|---|---|---|---|
| Action | One allowlisted resolver decision: retry, answer, edit-ticket, escalate | `ResolverAction` | Tool call |
| Agent | A configured role: prompt + reference files + model + tool allowlist | `Agent` | Run |
| Agent card | UI tile for one agent: model, state, current ticket, cost, last run | `AgentCard` | Board |
| Agent state | idle (no run), active (a run in progress), stuck (its ticket has an open incident) | `AgentState` | Ticket status |
| Allowlist | Tool names an agent may call; anything else is rejected | `allowlist` | Action |
| Attempt | Number of a run for the same ticket and stage (1, 2, …) | `attempt` | Tries |
| Board | UI view of tickets grouped by ticket status, with dependencies | `Board` | Agent card |
| Budget | USD limit per ticket and per agent; reaching it stops work until the user raises it | `Budget` | Price table |
| Context pack | Files a plan lets Build read (`## Context pack`) | `context_pack` | Workspace |
| Escalation | Handing a stuck ticket to a human via the repo host | `Escalation` | Retry |
| Executor | Runs commands in a workspace | `Executor` | Runner |
| Feature | A unit of requirements with its own `work/<feature>/` | `feature` | Ticket |
| Fix pass | Plan appends fix steps after review; Build runs only those | `fix_pass` | Re-plan |
| Inbox | UI list of escalated tickets waiting for a human | `Inbox` | Board |
| Incident | A stuck event on a ticket, with its bundle file | `Incident` | Escalation |
| Intake form | UI form where a user pastes a feature's requirements | `IntakeForm` | Inbox |
| Issue | Repo-host issue mirroring one ticket | `Issue` | Ticket |
| Merge request | GitLab MR or GitHub PR for one ticket branch | `MergeRequest` | Issue |
| Poll | Periodic check of the repo host for approvals, merges, CI and replies | `poll` | Run |
| Price table | $/MTok per model and token kind | `Price` | Cost |
| Project | A target project the app works on (git URL + workspace) | `Project` | Feature |
| Prompt | An agent's instruction file (`skills/<agent>/SKILL.md`) | `prompt` | Reference file |
| Re-plan | Plan rewrites the plan (`revision` +1) | `replan` | Fix pass |
| Reference file | A template a prompt links by relative path | `ref` | Prompt |
| Repo host | GitLab or GitHub, behind the RepoHost port | `RepoHost` | Remote |
| Resolver | Agent that runs only when a ticket is stuck | `resolver` | Runner |
| Review report | `reports/TKT-n-review-<k>.md`: reviewer comments for Plan | `review_report` | Resolve report |
| Run | One execution of one agent on one ticket (or feature) | `Run` | Ticket |
| Runner | Engine loop dispatching agents by ticket status | `Runner` | Scheduler |
| Runner switch | UI on/off control for the runner; starts off | `runner_enabled` | Agent state |
| Scheduler | Durable loop + crash recovery behind an interface | `Scheduler` | Runner |
| Stage | Pipeline step: architecture, spec, plan, build, verify, close | `Stage` | Agent |
| Stuck | Ticket blocked / no status change / crash / timeout / limits / question | `is_stuck` | Blocked |
| Task | What a run is asked to do: agent, feature, ticket | `Task` | Ticket |
| Ticket | Smallest shippable set of scenarios (`TKT-n`) | `Ticket` | Issue |
| Ticket status | todo, planned, built, verified, review, done, blocked, abandoned | `status` | Agent state |
| Trigger | Why an incident opened: blocked, no-transition, crash, timeout, limits, question | `trigger` | Action |
| Usage | Tokens of one Messages API call and their cost | `Usage` | Run |
| Workspace | Local clone of a project the agents work in | `workspace` | Project |
