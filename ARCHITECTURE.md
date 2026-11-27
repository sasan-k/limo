# Software Factory — Architecture

Diagrams of what this repo builds. Decisions and rules live in [DESIGN.md](DESIGN.md); this file only draws them.
Keep it in sync whenever stages, artifacts, scripts, or install layout change.

## 1. Pipeline and escalation

```mermaid
flowchart LR
    H([Human: requirements]) --> S1
    S0[0 · Architecture<br/>high model] -->|context/ snapshot + ADRs| S1
    S1[1 · Spec<br/>high model] -->|map.yaml DAG<br/>features, nfr.md| S2
    S1 -->|nfr.md| S0
    S2[2 · Plan<br/>high model] -->|plans/TKT-n.md| S3
    S3[3 · Build<br/>light model] -->|code + build report| S4
    S4{4 · Verify<br/>high model}
    S4 -->|pass: verified| S5[5 · Close<br/>light model]
    S4 -->|build failure<br/>build_tries < 2| S3
    S4 -->|plan failure<br/>plan_tries < 1| S2
    S4 -->|spec failure / limits hit<br/>blocked| R
    R{{Resolver<br/>high model}}
    R -->|high confidence:<br/>retry / answer Q / edit ticket| S2
    R -.->|gitlab-query| GL[(GitLab<br/>issue + MR per ticket)]
    R -->|not confident:<br/>factory:needs-human| H2([Human])
    H2 -.->|replies on issue| GL
    S3 -.->|step not doable: stop| S4
    S5 -->|doc updates, ADR status,<br/>ticket done| S0
    Q[(questions.md)] -.->|ambiguity: never guess| H2
    S1 -.-> Q
    S2 -.-> Q
```

## 2. Artifacts: who writes, who reads

```mermaid
flowchart TB
    subgraph CTX["context/ — snapshot = now, ADR = why"]
        IDX[INDEX.md · stack · layout · api · data<br/>code-rules · security · performance · testing<br/>glossary · questions]
        ADR[adr/INDEX.md L1<br/>adr/ADR-n.md L2 top · L3 bottom]
    end
    subgraph WORK["work/&lt;feature&gt;/"]
        REQ[reqs.md · features/*.feature<br/>nfr.md · questions.md]
        MAP[map.yaml<br/>ticket definitions + DAG]
        PLAN[plans/TKT-n.md<br/>design · quality · op matrix · FTs<br/>context pack · steps · doc updates]
        REP[reports/TKT-n-build/verify/close]
    end
    CODE[(Target code + tests)]

    Arch[Architecture] -->|writes| CTX
    Spec[Spec] -->|writes| REQ & MAP
    Spec -->|writes| IDX
    Plan[Plan] -->|reads on demand| CTX
    Plan -->|writes| PLAN
    Plan -->|proposed ADRs| ADR
    Build[Build] -->|reads only context pack| PLAN
    Build -->|writes| CODE & REP
    Verify[Verify] -->|runs tests, reviews diff| CODE
    Verify -->|writes| REP
    Close[Close] -->|applies doc updates,<br/>code wins| CTX
    Close -->|accept / reject| ADR
```

## 3. Traceability chain

```mermaid
flowchart LR
    REQ[REQ-n<br/>reqs.md] --> SC[SC-n<br/>.feature tag] --> TKT[TKT-n<br/>map.yaml] --> OP[OP-n<br/>plan operation] --> FT[FT-ticket.k<br/>plan + test name] --> STEP[STEP-n<br/>plan]
    NFR[NFR-n<br/>nfr.md] --> ADRn[ADR-n]
    SC -.->|covered by| FT
    OP -.->|op × category cell| FT
```
`fx trace-check` fails on any uncovered scenario, empty matrix cell, or FT missing from code.

## 4. Ticket lifecycle

```mermaid
stateDiagram-v2
    [*] --> todo
    todo --> planned: Plan (plan_tries +1 on revision)
    planned --> built: Build (build_tries +1)
    built --> verified: Verify pass
    built --> planned: Verify, build retry
    built --> todo: Verify, re-plan (build_tries=0)
    built --> blocked: Verify, limits hit / spec issue
    verified --> review: Close (MR/PR open)
    review --> done: MR/PR merged
    review --> planned: changes requested, fix pass
    review --> todo: changes requested, re-plan
    todo --> abandoned: Close abandon
    planned --> abandoned: Close abandon
    blocked --> [*]: human
    done --> [*]
    abandoned --> [*]
```

## 5. Runtime: standalone app (target design)

```mermaid
flowchart LR
    subgraph APP["factory repo = the app (clone and run)"]
        AG[agents/&lt;name&gt;/prompt.md<br/>+ refs/ templates]
        UI[ui/<br/>agent cards · ticket board · runner switch<br/>intake form · prompt editor<br/>inbox: escalations + budgets · cost]
        subgraph ENG["engine/ (Python)"]
            RUN[Runner<br/>dispatch by status · stuck guard]
            RT[Agent runtime<br/>claude -p per run · or Messages API loop]
            MCP[Per-run MCP endpoint<br/>run token · allowlist]
            TOOLS[Tools per agent<br/>allowlist enforced]
            FX[fx<br/>checks · status flips]
            RH[RepoHost<br/>GitLab · GitHub]
            LOG[(Event log<br/>runs · tokens · incidents)]
        end
    end
    UI <-->|REST + SSE| RUN
    UI -->|edit, versioned| AG
    RUN -->|stage run| RT
    RUN -->|stuck: incident| RT
    RT -->|system = prompt.md| AG
    RT --> TOOLS
    TOOLS --> FX
    TOOLS -->|read/write, run tests| WS[(Workspace:<br/>cloned target repo<br/>context/ + work/ + code)]
    RT -->|claude -p, user login| CC[Claude Code CLI]
    CC -->|tool calls| MCP
    MCP --> TOOLS
    RT -->|backend api: Anthropic SDK| API[Claude API]
    RUN --> LOG
    RUN --> RH
    RH -->|issues · MR/PR · labels ·<br/>approvals · CI| HOST[(GitLab / GitHub)]
```
The agent context is built only from its prompt, the task and its tools: nothing from `~/.claude`.
