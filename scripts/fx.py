#!/usr/bin/env python3
"""Factory helper: deterministic checks and status flips. Stdlib only.

usage:
  fx.py map-check   <work/feature>                 validate map.yaml + features, print build order and ready tickets
  fx.py trace-check <work/feature> [TKT-n] [--repo DIR]
                                                   REQ→SC coverage; with ticket: plan tests cover scenarios + full operation matrix (+ FT ids in code)
  fx.py status      <work/feature> [TKT-n]         print status + tries per ticket
  fx.py set         <work/feature> TKT-n key=value…  set status / build_tries / plan_tries (inc: key=+1)
  fx.py ready       <work/feature>                 list tickets ready to plan (status todo, deps done)
  fx.py tickets    <work/feature>                 print id<TAB>title per ticket
  fx.py board      <work/feature>                 print tickets (map + state) as a JSON array
  fx.py retitle    <work/feature> TKT-n <title>   rewrite that ticket's title in map.yaml
  fx.py adr         <context dir> ADR-n <status>   flip ADR status in ADR file and adr/INDEX.md
Ticket definitions live in map.yaml; status + tries live in SQLite at $FX_DB
(default <project>/.factory/state.db). Tickets missing from the DB start as todo, 0, 0.
Exit code 0 = ok, 1 = check failed, 2 = usage/parse error.
"""
import json, os, re, sqlite3, sys
from pathlib import Path

STATUSES = {"todo", "planned", "built", "verified", "review", "done", "blocked", "abandoned"}
ADR_STATUSES = {"proposed", "accepted", "rejected"}
KEYS = ["id", "title", "scope", "scenarios", "depends_on"]
STATE_KEYS = ["status", "build_tries", "plan_tries"]
LIST_KEYS = {"scope", "scenarios", "depends_on"}
INT_KEYS = {"build_tries", "plan_tries"}
MAX_SCENARIOS = 6


def die(msg, code=2):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


# ---------- map.yaml (strict subset) ----------
def parse_value(key, raw):
    raw = raw.strip()
    if key in LIST_KEYS:
        if not (raw.startswith("[") and raw.endswith("]")):
            die(f"map.yaml: {key} must be [a, b]")
        return [x.strip() for x in raw[1:-1].split(",") if x.strip()]
    return raw


def load_map(work):
    path = Path(work) / "map.yaml"
    if not path.exists():
        die(f"missing {path}")
    feature, tickets, cur = None, [], None
    for n, line in enumerate(path.read_text().splitlines(), 1):
        s = line.split(" #")[0].rstrip() if not line.lstrip().startswith("#") else ""
        if not s.strip():
            continue
        if s.startswith("feature:"):
            feature = s.split(":", 1)[1].strip()
        elif s.strip() == "tickets:":
            continue
        elif s.lstrip().startswith("- id:"):
            cur = {"id": s.split(":", 1)[1].strip()}
            tickets.append(cur)
        elif cur is not None and ":" in s:
            k, v = s.strip().split(":", 1)
            if k not in KEYS:
                die(f"map.yaml:{n}: unknown key '{k}'")
            cur[k] = parse_value(k, v)
        else:
            die(f"map.yaml:{n}: cannot parse '{line}'")
    for t in tickets:
        for k in KEYS:
            t.setdefault(k, [] if k in LIST_KEYS else "")
    return feature, tickets


# ---------- ticket state (SQLite) ----------
def db(work):
    path = Path(os.environ.get("FX_DB") or Path(work).resolve().parents[1] / ".factory" / "state.db")
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("""CREATE TABLE IF NOT EXISTS tickets (feature TEXT, id TEXT, status TEXT NOT NULL,
        build_tries INTEGER NOT NULL, plan_tries INTEGER NOT NULL, PRIMARY KEY (feature, id))""")
    return con


def load_tickets(work):
    """map.yaml definitions merged with DB state."""
    feature, tickets = load_map(work)
    scope = os.environ.get("FX_SCOPE")
    if scope:
        feature = f"{scope}/{feature}"
    with db(work) as con:
        for t in tickets:
            con.execute("INSERT OR IGNORE INTO tickets VALUES (?, ?, 'todo', 0, 0)", (feature, t["id"]))
            row = con.execute("SELECT status, build_tries, plan_tries FROM tickets WHERE feature=? AND id=?",
                              (feature, t["id"])).fetchone()
            t.update(zip(STATE_KEYS, row))
    return feature, tickets


# ---------- features / reqs ----------
def load_scenarios(work):
    """Return {SC-id: {"reqs": [...], "file": str}}; errors list."""
    scs, errs = {}, []
    for f in sorted((Path(work) / "features").glob("*.feature")):
        tags = []
        for n, line in enumerate(f.read_text().splitlines(), 1):
            s = line.strip()
            if s.startswith("@"):
                tags += s.split()
            elif re.match(r"Scenario( Outline)?:", s):
                sc = [t[1:] for t in tags if re.fullmatch(r"@SC-\d+", t)]
                rq = [t[1:] for t in tags if re.fullmatch(r"@REQ-\d+", t)]
                where = f"{f.name}:{n}"
                if len(sc) != 1:
                    errs.append(f"{where}: scenario needs exactly one @SC tag")
                elif sc[0] in scs:
                    errs.append(f"{where}: duplicate {sc[0]}")
                else:
                    if not rq:
                        errs.append(f"{where}: {sc[0]} has no @REQ tag")
                    scs[sc[0]] = {"reqs": rq, "file": where}
                tags = []
            elif s and not s.startswith("#"):
                tags = []
    return scs, errs


def load_reqs(work):
    p = Path(work) / "reqs.md"
    if not p.exists():
        die(f"missing {p}")
    return dict(re.findall(r"^- (REQ-\d+) \[([FNQ]|removed)\]", p.read_text(), re.M))


def topo(tickets):
    ids = {t["id"] for t in tickets}
    deps = {t["id"]: [d for d in t["depends_on"] if d in ids] for t in tickets}
    order, state = [], {}

    def visit(i, path):
        if state.get(i) == 1:
            return f"cycle: {' → '.join(path + [i])}"
        if state.get(i) == 2:
            return None
        state[i] = 1
        for d in sorted(deps[i]):
            e = visit(d, path + [i])
            if e:
                return e
        state[i] = 2
        order.append(i)
        return None

    for t in tickets:
        e = visit(t["id"], [])
        if e:
            return None, e
    return order, None


# ---------- commands ----------
def cmd_map_check(work):
    _, tickets = load_tickets(work)
    scs, errs = load_scenarios(work)
    ids = [t["id"] for t in tickets]
    owner = {}
    for t in tickets:
        if ids.count(t["id"]) > 1:
            errs.append(f"{t['id']}: duplicate ticket id")
        if not t["scenarios"]:
            errs.append(f"{t['id']}: no scenarios")
        if len(t["scenarios"]) > MAX_SCENARIOS:
            errs.append(f"{t['id']}: {len(t['scenarios'])} scenarios > {MAX_SCENARIOS}")
        for d in t["depends_on"]:
            if d not in ids:
                errs.append(f"{t['id']}: depends on unknown {d}")
        for sc in t["scenarios"]:
            if sc not in scs:
                errs.append(f"{t['id']}: unknown scenario {sc}")
            elif sc in owner:
                errs.append(f"{sc}: in both {owner[sc]} and {t['id']}")
            else:
                owner[sc] = t["id"]
    for sc in sorted(scs, key=lambda x: int(x[3:])):
        if sc not in owner:
            errs.append(f"{sc} ({scs[sc]['file']}): not in any ticket")
    order, cyc = topo(tickets)
    if cyc:
        errs.append(cyc)
    for e in errs:
        print(f"FAIL {e}")
    if errs:
        sys.exit(1)
    print("OK map")
    print("order:", " ".join(order))
    cmd_ready(work)


def cmd_ready(work):
    _, tickets = load_tickets(work)
    done = {t["id"] for t in tickets if t["status"] == "done"}
    ready = [t["id"] for t in tickets if t["status"] == "todo" and set(t["depends_on"]) <= done]
    print("ready:", " ".join(ready) or "-")


def cmd_tickets(work):
    _, tickets = load_map(work)
    for t in tickets:
        print(f"{t['id']}\t{t['title']}")


def cmd_board(work):
    _, tickets = load_tickets(work)
    keys = ["id", "title", "status", "depends_on", "build_tries", "plan_tries"]
    print(json.dumps([{k: t.get(k, [] if k == "depends_on" else "") for k in keys} for t in tickets]))


def cmd_retitle(work, ticket, title):
    if not 1 <= len(title) <= 120 or "\n" in title:
        die("bad title")
    path = Path(work) / "map.yaml"
    lines = path.read_text().splitlines(keepends=True)
    start = next((i for i, l in enumerate(lines) if l.strip() == f"- id: {ticket}"), None)
    if start is None:
        die(f"unknown ticket {ticket}")
    idx = next((j for j in range(start + 1, len(lines)) if lines[j].startswith("    title:")), None)
    if idx is None:
        die(f"map.yaml: no title for {ticket}")
    lines[idx] = f"    title: {title}\n"
    path.write_text("".join(lines))


def cmd_trace_check(work, ticket=None, repo=None):
    reqs = load_reqs(work)
    scs, errs = load_scenarios(work)
    covered = {r for s in scs.values() for r in s["reqs"]}
    nfr = (Path(work) / "nfr.md").read_text() if (Path(work) / "nfr.md").exists() else ""
    qs = (Path(work) / "questions.md").read_text() if (Path(work) / "questions.md").exists() else ""
    for sc, s in scs.items():
        for r in s["reqs"]:
            if r not in reqs:
                errs.append(f"{sc}: tags unknown {r}")
    for r, kind in sorted(reqs.items(), key=lambda x: int(x[0][4:])):
        if kind == "F" and r not in covered:
            errs.append(f"{r} [F]: no scenario")
        if kind == "N" and not re.search(rf"\b{r}\b", nfr):
            errs.append(f"{r} [N]: not in nfr.md")
        if kind == "Q" and not re.search(rf"\b{r}\b", qs):
            errs.append(f"{r} [Q]: not in questions.md")
    if ticket:
        _, tickets = load_map(work)
        t = next((t for t in tickets if t["id"] == ticket), None)
        if not t:
            die(f"unknown ticket {ticket}")
        plan = Path(work) / "plans" / f"{ticket}.md"
        if not plan.exists():
            errs.append(f"{ticket}: no plan at {plan}")
        else:
            errs += check_plan(work, t, plan.read_text(), repo)
    for e in errs:
        print(f"FAIL {e}")
    if errs:
        sys.exit(1)
    print("OK trace" + (f" {ticket}" if ticket else ""))


def load_categories(work):
    f = Path(work).resolve().parents[1] / "context" / "testing.md"
    m = re.search(r"^categories:\s*(.+)$", f.read_text(), re.M) if f.exists() else None
    return [c.strip() for c in m.group(1).split(",")] if m else None


def cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def check_plan(work, t, text, repo):
    errs, tid, num = [], t["id"], t["id"].split("-")[1]
    # functional tests: | FT-<ticket>.<k> | covers | …
    fts = {}
    for line in text.splitlines():
        if re.match(r"^\|\s*FT-", line):
            c = cells(line)
            if c[0] in fts:
                errs.append(f"{tid}: duplicate {c[0]}")
            if not re.fullmatch(rf"FT-{num}\.\d+", c[0]):
                errs.append(f"{tid}: bad test id {c[0]} (want FT-{num}.<k>)")
            fts[c[0]] = set(re.findall(r"SC-\d+|OP-\d+:[a-z-]+", c[1] if len(c) > 1 else ""))
    covered = set().union(*fts.values()) if fts else set()
    for sc in t["scenarios"]:
        if sc not in covered:
            errs.append(f"{tid}: {sc} has no functional test")
    for f, cov in fts.items():
        for sc in (x for x in cov if x.startswith("SC-")):
            if sc not in t["scenarios"]:
                errs.append(f"{f}: covers {sc}, not in {tid}")
    # operation matrix: header `| Op | <categories> |`, rows `| OP-n … |`
    lines = text.splitlines()
    head = next((cells(l) for l in lines if re.match(r"^\|\s*Op\s*\|", l)), None)
    ops = [cells(l) for l in lines if re.match(r"^\|\s*OP-\d+", l)]
    if not head or not ops:
        errs.append(f"{tid}: operation matrix missing or empty")
    else:
        cats = load_categories(work)
        if cats and head[1:] != cats:
            errs.append(f"{tid}: matrix columns {head[1:]} != testing.md categories {cats}")
        op_ids = set()
        for row in ops:
            op = re.match(r"OP-\d+", row[0]).group(0)
            op_ids.add(op)
            if len(row) != len(head):
                errs.append(f"{op}: {len(row) - 1} cells, want {len(head) - 1}")
                continue
            for cat, cell in zip(head[1:], row[1:]):
                where = f"{op}:{cat}"
                if not cell:
                    errs.append(f"{where}: empty cell")
                elif cell.lower().startswith("n/a"):
                    if not re.match(r"n/a:\s*\S", cell, re.I):
                        errs.append(f"{where}: n/a needs ': <reason>'")
                else:
                    ids = [x.strip() for x in cell.split(",")]
                    for i in ids:
                        if i not in fts:
                            errs.append(f"{where}: {i} not in functional tests table")
                        elif where not in fts[i]:
                            errs.append(f"{where}: {i} does not list {where} in Covers")
        for f, cov in fts.items():
            for x in (x for x in cov if x.startswith("OP-")):
                if x.split(":")[0] not in op_ids:
                    errs.append(f"{f}: covers unknown {x}")
    # FT ids present in code
    if repo:
        root = Path(repo).resolve()
        skip = {"work", "context", ".git", "node_modules"}
        code = "\n".join(p.read_text(errors="ignore") for p in root.rglob("*")
                         if p.is_file() and not skip & set(p.relative_to(root).parts))
        for f in fts:
            if not re.search(rf"{re.escape(f)}(?![\d.])", code):
                errs.append(f"{f}: not found in code under {repo}")
    return errs


def cmd_status(work, ticket=None):
    _, tickets = load_tickets(work)
    rows = [t for t in tickets if ticket in (None, t["id"])]
    if not rows:
        die(f"unknown ticket {ticket}")
    for t in rows:
        print(f"{t['id']}: " + " ".join(f"{k}={t[k]}" for k in STATE_KEYS))


def cmd_set(work, ticket, pairs):
    feature, tickets = load_tickets(work)
    t = next((t for t in tickets if t["id"] == ticket), None)
    if not t:
        die(f"unknown ticket {ticket}")
    for p in pairs:
        k, _, v = p.partition("=")
        if k == "status":
            if v not in STATUSES:
                die(f"bad status {v}")
            t[k] = v
        elif k in INT_KEYS:
            t[k] = t[k] + int(v[1:]) if v.startswith("+") else int(v)
        else:
            die(f"cannot set {k}")
    with db(work) as con:
        con.execute("UPDATE tickets SET status=?, build_tries=?, plan_tries=? WHERE feature=? AND id=?",
                    (t["status"], t["build_tries"], t["plan_tries"], feature, ticket))
    print(f"{ticket}: " + " ".join(f"{k}={t[k]}" for k in STATE_KEYS))


def cmd_adr(ctx, adr, status):
    if status not in ADR_STATUSES and not re.fullmatch(r"superseded by ADR-\d+", status):
        die(f"bad ADR status {status}")
    f = Path(ctx) / "adr" / f"{adr}.md"
    idx = Path(ctx) / "adr" / "INDEX.md"
    if not f.exists() or not idx.exists():
        die(f"missing {f} or {idx}")
    f.write_text(re.sub(r"^status: .*$", f"status: {status}", f.read_text(), count=1, flags=re.M))
    short = status.split()[0]
    new, n = re.subn(rf"^(- {adr}) \[[^\]]+\]", rf"\1 [{short}]", idx.read_text(), flags=re.M)
    if n != 1:
        die(f"{adr} not found once in {idx}")
    idx.write_text(new)
    print(f"{adr}: {status}")


def main(a):
    if len(a) < 2 or a[0] in ("-h", "--help"):
        die(__doc__)
    c, rest = a[0], a[1:]
    if c == "map-check":
        cmd_map_check(rest[0])
    elif c == "status":
        cmd_status(rest[0], rest[1] if len(rest) > 1 else None)
    elif c == "ready":
        cmd_ready(rest[0])
    elif c == "tickets":
        cmd_tickets(rest[0])
    elif c == "board":
        cmd_board(rest[0])
    elif c == "trace-check":
        repo = rest[rest.index("--repo") + 1] if "--repo" in rest else None
        pos = [x for i, x in enumerate(rest) if x != "--repo" and (i == 0 or rest[i - 1] != "--repo")]
        cmd_trace_check(pos[0], pos[1] if len(pos) > 1 else None, repo)
    elif c == "retitle" and len(rest) >= 3:
        cmd_retitle(rest[0], rest[1], " ".join(rest[2:]))
    elif c == "set" and len(rest) >= 3:
        cmd_set(rest[0], rest[1], rest[2:])
    elif c == "adr" and len(rest) >= 3:
        cmd_adr(rest[0], rest[1], " ".join(rest[2:]))
    else:
        die(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
