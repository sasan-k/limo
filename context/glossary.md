# Glossary
<!-- Shared domain language. Spec maintains; every stage uses these exact terms. -->

| Term | Meaning | Code name | Not to be confused with |
|---|---|---|---|
| Action | One allowlisted resolver decision: retry, answer, edit-ticket, escalate | `ResolverAction` | Tool call |
| Agent | A configured role: prompt + reference files + model + tool allowlist | `Agent` | Run |
| Escalation | Handing a stuck ticket to a human via the repo host | `Escalation` | Retry |
| Executor | Runs commands in a workspace | `Executor` | Runner |
| Feature | A unit of requirements with its own `work/<feature>/` | `feature` | Ticket |
| Fix pass | Plan appends fix steps after review; Build runs only those | `fix_pass` | Re-plan |
| Incident | A stuck event on a ticket, with its bundle file | `Incident` | Escalation |
| Price table | $/MTok per model and token kind | `Price` | Cost |
| Project | A target project the app works on (git URL + workspace) | `Project` | Feature |
| Prompt | An agent's instruction file (`skills/<agent>/SKILL.md`) | `prompt` | Reference file |
| Re-plan | Plan rewrites the plan (`revision` +1) | `replan` | Fix pass |
| Reference file | A template a prompt links by relative path | `ref` | Prompt |
| Repo host | GitLab or GitHub, behind the RepoHost port | `RepoHost` | Remote |
| Resolver | Agent that runs only when a ticket is stuck | `resolver` | Runner |
| Run | One execution of one agent on one ticket (or feature) | `Run` | Ticket |
| Runner | Engine loop dispatching agents by ticket status | `Runner` | Scheduler |
| Scheduler | Durable loop + crash recovery behind an interface | `Scheduler` | Runner |
| Stage | Pipeline step: architecture, spec, plan, build, verify, close | `Stage` | Agent |
| Stuck | Ticket blocked / no status change / crash / timeout / limits / question | `is_stuck` | Blocked |
| Ticket | Smallest shippable set of scenarios (`TKT-n`) | `Ticket` | Issue |
| Usage | Tokens of one Messages API call and their cost | `Usage` | Run |
| Workspace | Local clone of a project the agents work in | `workspace` | Project |
