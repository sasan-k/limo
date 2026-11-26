Feature: Agents
  As a developer
  I want each agent to see only its prompt, its task and its own tools
  So that every role stays within its limits

  Background:
    Given project "shop" was added and its feature "cart" has ticket "TKT-1" with a plan
    And the plan's context pack lists only "src/cart.py"

  @SC-2 @REQ-7
  Scenario: Limo lists the seven agents with their prompt and reference files
    When the user lists the agents
    Then the agents are "architecture, spec, plan, build, verify, close, resolver"
    And agent "plan" shows prompt "skills/plan/SKILL.md" and reference file "skills/plan/templates/plan.md"

  @SC-3 @REQ-8
  Scenario: A run's context holds only the prompt, the task and the agent's tools
    Given the workspace of "shop" contains a "CLAUDE.md" with the text "secret house rules"
    When a plan run starts for "TKT-1" of feature "cart"
    Then the Claude API request's system prompt is the content of "skills/plan/SKILL.md"
    And its first message is the task "feature=cart ticket=TKT-1"
    And its tools are exactly the plan agent's allowlist
    And no part of the request contains "secret house rules"

  @SC-4 @REQ-10
  Scenario: A tool call outside the allowlist is rejected
    Given the Claude API will ask the verify run to call tool "write_file"
    When a verify run starts for "TKT-1"
    Then the tool result sent back is an error "tool not allowed: write_file"
    And the run's tool calls show "write_file" as "rejected"

  @SC-5 @REQ-11
  Scenario: Build reads a file in its context pack
    Given the Claude API will ask the build run to read "src/cart.py"
    When a build run starts for "TKT-1"
    Then the tool result contains the content of "src/cart.py"

  @SC-6 @REQ-11
  Scenario: Build cannot read a file outside its context pack
    Given the Claude API will ask the build run to read "src/payment.py"
    When a build run starts for "TKT-1"
    Then the tool result is an error "not in context pack: src/payment.py"
    And the run's tool calls show "read_file src/payment.py" as "rejected"

  @SC-7 @REQ-12
  Scenario: Resolver gets only read tools and host-query
    When a resolver run starts for "TKT-1"
    Then the Claude API request offers exactly the tools "read_file, list_files, grep, host_query"
