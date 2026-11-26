Feature: Resolver
  As a developer
  I want stuck tickets diagnosed and fixed when the evidence is clear
  So that I am only asked when really needed

  Background:
    Given project "shop" was added with repo host "github"
    And its feature "cart" has tickets "TKT-1" and "TKT-3" with no dependencies, each with an issue
    And the runner is turned on

  @SC-32 @REQ-19 @REQ-22
  Scenario Outline: A stuck ticket opens an incident and runs the resolver
    Given <situation>
    When the runner takes its next step
    Then an incident is opened for "TKT-1" with trigger "<trigger>"
    And "work/cart/incidents/TKT-1-1.md" exists
    And a resolver run starts for "TKT-1"

    Examples:
      | situation                                                        | trigger       |
      | ticket "TKT-1" was set to "blocked" by its plan run              | blocked       |
      | a build run for "TKT-1" finished without changing the status     | no-transition |
      | a build run for "TKT-1" failed with a Claude API error           | crash         |
      | a build run for "TKT-1" ran past a run timeout set to 30 minutes | timeout       |
      | open question "Q-3" blocks ticket "TKT-1"                        | question      |

  @SC-33 @REQ-23
  Scenario: A retry action reruns the stage
    Given an incident is open for "TKT-1" after a build run failed with a timeout
    When the resolver run returns action retry with stage "build"
    Then a build run starts for "TKT-1"
    And the incident shows action "retry"

  @SC-34 @REQ-23
  Scenario: An answer action records the answer and unblocks the ticket
    Given ticket "TKT-1" is blocked by open question "Q-3"
    When the resolver run returns action answer for "Q-3" with "use EUR" and source "context/data.md:12"
    Then "work/cart/questions.md" shows "Q-3" as answered with "use EUR"
    And ticket "TKT-1" has status "todo"

  @SC-35 @REQ-23
  Scenario: An edit-ticket action retitles the ticket and re-plans it
    Given an incident is open for "TKT-1"
    When the resolver run returns action edit-ticket with title "Cart total includes tax"
    Then "work/cart/map.yaml" shows "TKT-1" titled "Cart total includes tax"
    And the issue of "TKT-1" is titled "TKT-1: Cart total includes tax"
    And the next run for "TKT-1" is a plan run

  @SC-36 @REQ-23
  Scenario: An action outside the allowlist escalates
    Given an incident is open for "TKT-1"
    When the resolver run returns action "merge"
    Then the action is rejected
    And the issue of "TKT-1" has label "factory:needs-human"

  @SC-37 @REQ-24
  Scenario: A third incident escalates without running the resolver
    Given the resolver already handled 2 incidents for "TKT-1"
    When "TKT-1" gets stuck again
    Then no resolver run starts
    And the issue of "TKT-1" has label "factory:needs-human"

  @SC-38 @REQ-25
  Scenario: Escalation asks a human and the runner moves on
    Given ticket "TKT-3" has status "todo"
    And an incident is open for "TKT-1"
    When the resolver run returns action escalate with ask "Should totals include tax?"
    Then the issue of "TKT-1" has label "factory:needs-human" and a comment containing "Should totals include tax?"
    And a plan run starts for "TKT-3"

  @SC-39 @REQ-28
  Scenario: A human reply reaches the resolver
    Given "TKT-1" was escalated with ask "Should totals include tax?"
    When a human replies "Yes, 21% VAT" on the issue of "TKT-1" and the next poll runs
    Then a resolver run starts for "TKT-1"
    And its incident bundle contains "Yes, 21% VAT"

  @SC-53 @REQ-48
  Scenario: The user answers in the inbox and continues
    Given the resolver already handled 2 incidents for "TKT-1"
    And "TKT-1" was escalated with ask "Should totals include tax?"
    When the user types "Yes, 21% VAT" for "TKT-1" in the inbox and presses Continue
    Then the issue of "TKT-1" has a comment "Yes, 21% VAT"
    And a resolver run starts for "TKT-1" whose incident bundle contains "Yes, 21% VAT"
