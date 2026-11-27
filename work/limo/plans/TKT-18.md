---
ticket: TKT-18
feature: limo
scenarios: [SC-60, SC-61]
scope: [host, testing]
revision: 0
run: all
read: [work/limo/map.yaml, work/limo/features/host_adapters.feature, work/limo/questions.md#Q-13#Q-14, context/adr/ADR-12.md, context/adr/ADR-9.md, context/security.md, context/performance.md, context/testing.md, engine/limo/hosts/ports.py, engine/limo/config.py, engine/limo/app.py (3 uses of UnconfiguredHost), engine/pyproject.toml]
---
# TKT-18: GitHub and GitLab adapters act as Limo's identity

## Design
- where: new `limo/hosts/repo_url.py`, `limo/hosts/github.py`, `limo/hosts/gitlab.py`, `limo/hosts/router.py`; settings gain host tokens/URLs; `app.py` uses `RoutedHost` as the default host; contract suite `engine/tests/contract/` with JSON fixtures (ADR-12)
- responsibilities:
  - `parse_repo(git_url) -> str` — `owner/repo` path from `https://host/a/b(.git)`, `ssh://git@host/a/b(.git)`, `git@host:a/b(.git)`; anything else → `HostError("unsupported git url")`
  - `GitHubHost(token: SecretStr | None, api_url: str, timeout_s: float, client: httpx.Client | None = None)` — implements `RepoHost` on the GitHub REST + GraphQL API
  - `GitLabHost(token, api_url, timeout_s, client=None)` — implements `RepoHost` on the GitLab REST v4 API
  - `RoutedHost(github: RepoHost, gitlab: RepoHost)` — picks by `project.kind` (`github` / `gitlab`); other kinds → `HostError("unknown repo host")`
  - each adapter: missing token → `HostError("<host> token not configured")`; any `httpx.HTTPError` or status ≥ 400 → `HostError(f"<host> <METHOD> <path> failed: <status>")` (never includes the token); `mine` comments = author login equals `GET /user` login (fetched once per adapter instance and cached)
- reuse: port types in `hosts/ports.py`; `SecretStr` (ADR-9)
- contracts (paths relative to `api_url`; `{p}` = `owner/repo` for GitHub, URL-encoded `owner%2Frepo` for GitLab):

  | Port method | GitHub | GitLab |
  |---|---|---|
  | auth header | `Authorization: Bearer <token>`, `Accept: application/vnd.github+json` | `PRIVATE-TOKEN: <token>` |
  | `open_merge_request` | `POST /repos/{p}/pulls` `{title, head: branch, base}` → `number`, `html_url` | `POST /projects/{p}/merge_requests` `{source_branch, target_branch, title}` → `iid`, `web_url` |
  | `enable_auto_merge` | `GET /repos/{p}/pulls/{n}` → `node_id`; `POST /graphql` `{"query": "mutation($id: ID!) { enablePullRequestAutoMerge(input: {pullRequestId: $id, mergeMethod: MERGE}) { clientMutationId } }", "variables": {"id": node_id}}`; a GraphQL `errors` array → `HostError` | `PUT /projects/{p}/merge_requests/{n}/merge` `{merge_when_pipeline_succeeds: true}` |
  | `merge_request_status` | `GET /repos/{p}/pulls/{n}` (`merged` true → merged; else `state` open/closed); `GET /repos/{p}/pulls/{n}/reviews` → approved if any `state` `APPROVED`; change requests = reviews with `state` `CHANGES_REQUESTED` → `ReviewComment(str(id), body)` | `GET /projects/{p}/merge_requests/{n}` (`state` opened→open, merged, closed); `GET …/approvals` → `approved`; change requests = `GET …/notes?sort=asc` notes with `system` false and author ≠ Limo → `ReviewComment(str(id), body)` |
  | `create_issue` | `POST /repos/{p}/issues` `{title}` → `number`, `html_url` | `POST /projects/{p}/issues` `{title}` → `iid`, `web_url` |
  | `set_issue_status` | `GET /repos/{p}/issues/{n}/labels`; `DELETE /repos/{p}/issues/{n}/labels/{name}` for each `limo:*` other than the new one; `POST /repos/{p}/issues/{n}/labels` `{labels: ["limo:<status>"]}` | `GET /projects/{p}/issues/{n}` → `labels`; `PUT /projects/{p}/issues/{n}` `{add_labels: "limo:<status>", remove_labels: "<other limo:* comma-joined>"}` |
  | `set_issue_title` | `PATCH /repos/{p}/issues/{n}` `{title}` | `PUT /projects/{p}/issues/{n}` `{title}` |
  | `add_issue_label` | `POST /repos/{p}/issues/{n}/labels` `{labels: [label]}` | `PUT /projects/{p}/issues/{n}` `{add_labels: label}` |
  | `comment_issue` | `POST /repos/{p}/issues/{n}/comments` `{body}` | `POST /projects/{p}/issues/{n}/notes` `{body}` |
  | `issue_comments` | `GET /repos/{p}/issues/{n}/comments` → `IssueComment(str(id), body, user.login == me)` | `GET /projects/{p}/issues/{n}/notes?sort=asc` (skip `system` true) → `IssueComment(str(id), body, author.username == me)` |
  | me | `GET /user` → `login` | `GET /user` → `username` |
- settings: `github_token: SecretStr | None` (env `GITHUB_TOKEN`), `gitlab_token: SecretStr | None` (env `GITLAB_TOKEN`), `github_api_url = "https://api.github.com"`, `gitlab_api_url = "https://gitlab.com/api/v4"`, `host_timeout_s = 10.0`
- decisions: follows ADR-12 (accepted: one contract suite, recorded HTTP via respx, both hosts), ADR-9 (tokens as SecretStr, never logged or in errors), ADR-4, Q-14 (Limo's own identity) · no new ADR

## Quality
### Security
- authn: host tokens from env only (ADR-9); never in errors, logs or responses
- authz (permission/ownership): Limo uses its own identity; the port still has no merge call (auto-merge only)
- input validation: git url parsed strictly; numbers are ints
- injection: paths built from parsed `owner/repo` (GitLab: URL-encoded) and ints; JSON bodies via httpx
- data exposure / PII: none beyond issue/MR text
- secrets: `SecretStr.get_secret_value()` only when building headers
- rate limit / abuse: one call per port operation (+ cached `GET /user`)
- audit: n/a (calls are already recorded by callers)
### Performance
- queries (N+1, indexes): `set_issue_status` makes ≤ 3 calls; `/user` cached
- pagination / limits: n/a for v1 (default page sizes); noted in Do not
- payload size: n/a
- caching: `me` login cached per adapter
- external calls (timeouts/retries): `httpx.Client(timeout=host_timeout_s)`; no retries in v1 (performance.md allows GET retries later)
- sync vs async: sync httpx inside existing sync flows
- NFR targets: NFR-8 → FT-18.3 … FT-18.10 run for both hosts

## Operation matrix
| Op | happy | validation | not-found | conflict | invalid-state | idempotency | boundary | external-failure |
|---|---|---|---|---|---|---|---|---|
| OP-1 open MR + auto-merge | FT-18.1, FT-18.2 | FT-18.9 | n/a: repo checked by host (404 → external-failure) | n/a: host rejects duplicates (external-failure) | FT-18.8 | n/a: callers open once (TKT-7) | n/a: single call | FT-18.7 |
| OP-2 MR status | FT-18.3 | n/a: ints | n/a: 404 → external-failure | n/a: read only | n/a: read only | n/a: read only | FT-18.3 | FT-18.7 |
| OP-3 issues (create, status label, title, label) | FT-18.4, FT-18.5 | n/a: titles validated upstream | n/a: 404 → external-failure | n/a: labels idempotent on hosts | n/a: any state | FT-18.4 | n/a: one label | FT-18.7 |
| OP-4 comments (post, list with `mine`) | FT-18.6 | FT-18.6 | n/a: 404 → external-failure | n/a: append only | n/a: any state | n/a: read only | n/a: default page | FT-18.7 |
| OP-5 routing by kind | FT-18.10 | FT-18.10 | n/a: kinds fixed | n/a: stateless | n/a: stateless | n/a: stateless | n/a: two kinds | n/a: delegates |

## Functional tests
Contract tests (ADR-12) in `engine/tests/contract/test_repo_hosts.py`; `engine/tests/contract/__init__.py` empty. Every test is parametrized over `host_kind in ("github", "gitlab")` unless it names one host. A fixture `adapter(host_kind, respx_mock)` builds `GitHubHost(SecretStr("limo-gh-token"), "https://api.github.test", 5.0)` or `GitLabHost(SecretStr("limo-gl-token"), "https://gitlab.test/api/v4", 5.0)`; `project = HostProject("shop", "https://example.com/acme/shop.git", host_kind)`. Responses come from JSON files `engine/tests/contract/fixtures/<host>/<name>.json` loaded by a helper `fx(host, name)`; register routes with `respx_mock.<method>(url).mock(return_value=httpx.Response(status, json=fx(...)))`. Read requests from `route.calls.last.request` (`.headers`, `json.loads(.content)`).

| FT | Covers | File | Given (via production action) | When | Then (observable) |
|---|---|---|---|---|---|
| FT-18.1 | SC-60, OP-1:happy | `engine/tests/contract/test_repo_hosts.py` | github only; routes: `POST /repos/acme/shop/pulls` → `{number: 7, html_url, node_id: "PR_1"}`, `GET /repos/acme/shop/pulls/7` → same, `POST /graphql` → `{"data": {...}}` | `open_merge_request(project, "limo/cart/TKT-1", "main", "TKT-1 (cart)")` then `enable_auto_merge(project, 7)` | ref `(7, html_url)`; pulls request header `Authorization` == `Bearer limo-gh-token`, body `head` "limo/cart/TKT-1", `base` "main"; graphql body `variables.id` == "PR_1" and `query` contains `enablePullRequestAutoMerge` |
| FT-18.2 | SC-61, OP-1:happy | `engine/tests/contract/test_repo_hosts.py` | gitlab only; routes `POST /projects/acme%2Fshop/merge_requests` → `{iid: 7, web_url}`, `PUT /projects/acme%2Fshop/merge_requests/7/merge` → `{}` | same calls | header `PRIVATE-TOKEN` == "limo-gl-token"; MR body `source_branch` "limo/cart/TKT-1", `target_branch` "main"; merge body `merge_when_pipeline_succeeds` true |
| FT-18.3 | OP-2:happy, OP-2:boundary | `engine/tests/contract/test_repo_hosts.py` | both; parametrize: merged MR → `MrStatus("merged", …)`; open MR with one approval → `approved` True, no change requests; open MR with one change request (GitHub review `CHANGES_REQUESTED` id 11 body "rename"; GitLab note id 11 body "rename" by user `alice`, plus a system note that is ignored) | `merge_request_status(project, 7)` | expected `state`, `approved`, `change_requests == [ReviewComment("11", "rename")]` in the third case |
| FT-18.4 | OP-3:happy, OP-3:idempotency | `engine/tests/contract/test_repo_hosts.py` | both; create-issue route returns number/iid 3; labels currently `["limo:todo", "bug"]` | `create_issue(project, "TKT-1: Cart shows a total")`; `set_issue_status(project, 3, "planned")` | ref number 3; GitHub: a `DELETE …/labels/limo:todo` call and a `POST …/labels` with `["limo:planned"]`, no call touching `bug`; GitLab: `PUT …/issues/3` body `add_labels` "limo:planned", `remove_labels` "limo:todo" |
| FT-18.5 | OP-3:happy | `engine/tests/contract/test_repo_hosts.py` | both | `set_issue_title(project, 3, "TKT-1: New")`; `add_issue_label(project, 3, "factory:needs-human")` | GitHub: `PATCH …/issues/3` `{title}` and `POST …/labels` `{labels: ["factory:needs-human"]}`; GitLab: `PUT …/issues/3` with `title`, then with `add_labels` |
| FT-18.6 | OP-4:happy, OP-4:validation | `engine/tests/contract/test_repo_hosts.py` | both; `GET /user` → login/username `limo-bot`; comments: one by `limo-bot`, one by `alice` (GitLab also a system note) | `comment_issue(project, 3, "hi")`; `issue_comments(project, 3)` | post body `{body: "hi"}`; list == `[IssueComment(<id1>, …, True), IssueComment(<id2>, …, False)]` (system notes skipped) |
| FT-18.7 | OP-1:external-failure, OP-2:external-failure, OP-3:external-failure, OP-4:external-failure | `engine/tests/contract/test_repo_hosts.py` | both; the open-MR route returns 422; status route 404; issues route 500; comments route raises `httpx.ConnectError` | each call | `HostError` each; `str(error)` does not contain the token |
| FT-18.8 | OP-1:invalid-state | `engine/tests/contract/test_repo_hosts.py` | both; adapter built with token `None` | `open_merge_request(...)` | `HostError` with "token not configured"; no HTTP call made |
| FT-18.9 | OP-1:validation | `engine/tests/contract/test_repo_hosts.py` | both; project git_url parametrized: `https://example.com/acme/shop.git`, `git@example.com:acme/shop.git`, `ssh://git@example.com/acme/shop` (all valid → path `acme/shop`) and `file:///tmp/shop.git` (invalid) | `parse_repo(url)` / `open_merge_request` for the invalid one | `"acme/shop"` for the valid ones; `HostError("unsupported git url")` for the file URL |
| FT-18.10 | OP-5:happy, OP-5:validation | `engine/tests/contract/test_repo_hosts.py` | `RoutedHost(github=FakeHost(), gitlab=FakeHost())` (fakes from `tests/fakes/host.py`) | `create_issue` with kind `github`, then `gitlab`, then `bitbucket` | the github fake got the first call, the gitlab fake the second; `bitbucket` → `HostError("unknown repo host")` |

## Context pack
- `engine/pyproject.toml` — STEP-1 edit
- `engine/limo/config.py` — STEP-2 edit
- `engine/limo/hosts/ports.py` — read
- `engine/limo/app.py` — STEP-8 edit
- `engine/tests/fakes/host.py` — read (FakeHost)

## Steps
### STEP-1 dependencies
- file: `engine/pyproject.toml` (edit)
- do: add `"httpx"` to `dependencies`; add `"respx"` to the `dev` group; run `mise run setup`
- verify: `cd engine && uv run python -c "import httpx, respx"` → exit 0

### STEP-2 settings
- file: `engine/limo/config.py` (edit)
- do: add `github_token: SecretStr | None = Field(default=None, validation_alias=AliasChoices("GITHUB_TOKEN", "github_token"))`, the same for `gitlab_token` (`GITLAB_TOKEN`), `github_api_url: str = "https://api.github.com"`, `gitlab_api_url: str = "https://gitlab.com/api/v4"`, `host_timeout_s: float = 10.0`
- verify: `cd engine && uv run python -c "from limo.config import Settings; print(Settings(_env_file=None).github_api_url)"` → `https://api.github.com`

### STEP-3 fixtures and contract tests (test first)
- file: `engine/tests/contract/__init__.py` (create, empty), `engine/tests/contract/fixtures/github/*.json`, `engine/tests/contract/fixtures/gitlab/*.json` (create), `engine/tests/contract/test_repo_hosts.py` (create)
- do: write the JSON response bodies the tests need (shapes per Design › contracts: GitHub `pull.json` `{number, html_url, node_id, state, merged}`, `pull_merged.json`, `reviews_*.json`, `issue.json`, `labels.json`, `comments.json`, `user.json`; GitLab `mr.json` `{iid, web_url, state}`, `mr_merged.json`, `approvals_*.json` `{approved}`, `notes_*.json` (with `system`, `author.username`), `issue.json` `{iid, web_url, labels}`, `user.json`); no tokens in fixtures. Write FT-18.1 … FT-18.10; names `test_ft_18_<k>_<behavior>`, docstring starts `"""FT-18.<k> `. Use the `respx_mock` pytest fixture from respx.
- verify: `mise run test:engine -- -k ft_18` → FAIL (`ModuleNotFoundError: limo.hosts.github`)

### STEP-4 repo url parser
- file: `engine/limo/hosts/repo_url.py` (create)
- do: `parse_repo(git_url: str) -> str` per Design (regexes for the three forms; strip a trailing `.git`; require exactly `owner/repo` or deeper GitLab groups `a/b/c`)
- verify: `mise run test:engine -- -k ft_18_9` → passed

### STEP-5 GitHub adapter
- file: `engine/limo/hosts/github.py` (create)
- do: `GitHubHost` per the table. One private `_request(method, path, json_body=None) -> Any` builds headers, sends via `self._client` (`httpx.Client(base_url=api_url, timeout=timeout_s)` unless one is passed), raises `HostError` per Design, returns `response.json()` (or `None` for 204). `_me()` caches `GET /user` `login`. Each public method ≤ 40 lines.
- verify: `mise run test:engine -- -k "ft_18 and github"` → github cases pass

### STEP-6 GitLab adapter
- file: `engine/limo/hosts/gitlab.py` (create)
- do: `GitLabHost` per the table; project path = `urllib.parse.quote(parse_repo(url), safe="")`; `_me()` caches `GET /user` `username`; same `_request` pattern as GitHub (no shared base class unless jscpd reports a clone — then extract `limo/hosts/http.py` with the shared `_request`/error handling)
- verify: `mise run test:engine -- -k "ft_18 and gitlab"` → gitlab cases pass

### STEP-7 router
- file: `engine/limo/hosts/router.py` (create)
- do: `RoutedHost(github: RepoHost, gitlab: RepoHost)`; each port method → `self._pick(project).<same method>(...)`; `_pick` raises `HostError("unknown repo host")` for other kinds
- verify: `mise run test:engine -- -k ft_18_10` → passed

### STEP-8 default host wiring
- file: `engine/limo/app.py` (edit)
- do: at the top of `create_app` after `deps` is resolved: `host = deps.host or RoutedHost(GitHubHost(settings.github_token, settings.github_api_url, settings.host_timeout_s), GitLabHost(settings.gitlab_token, settings.gitlab_api_url, settings.host_timeout_s))`; replace every `deps.host or UnconfiguredHost()` with `host` (keep `UnconfiguredHost` in the codebase, unused by the app)
- verify: `mise run test:engine` → all passed

### STEP-9 format, gates, full suite
- file: none new (edit only lines a gate reports, in files this plan created or edited)
- do: `mise run fmt`, `mise run gates` (up to 3 fix rounds), `mise run test`; never add `# noqa`
- verify: gates exit 0; `mise run test` all passed

## Do not
- call real GitHub/GitLab in tests
- put tokens in fixtures, logs, errors or responses
- add a merge method to the port; add pagination or retries (later)
- add `# noqa`

## Doc updates
- context/INDEX.md: `hosts` line — real adapters `GitHubHost`, `GitLabHost` behind `RoutedHost` (default); `UnconfiguredHost` kept for reference
- context/stack.md: Key libraries — httpx is a runtime dependency; respx for contract tests
- context/testing.md: contract suite `engine/tests/contract/` (respx + JSON fixtures, both hosts)
- context/security.md: Data — host tokens `GITHUB_TOKEN`, `GITLAB_TOKEN` as SecretStr
- .env.example: already lists both token names (no change)
- context/glossary.md: none
- context/code-rules.md: none
- adr: none
- adr/INDEX.md: none
