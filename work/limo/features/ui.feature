Feature: Live UI
  As a developer
  I want to watch agents, tickets and cost live
  So that I know what Limo is doing without asking

  Background:
    Given project "shop" was added and its feature "cart" has ticket "TKT-1" titled "Cart shows a total"
    And the user has the Limo UI open

  @SC-40 @REQ-39
  Scenario: An agent card shows the agent's details
    Given the build run for "TKT-1" attempt 1 finished after 4 minutes with 52,000 tokens and cost 0.40 USD
    And agent "build" has model "claude-haiku-5-5"
    When the user looks at the card of agent "build"
    Then it shows model "claude-haiku-5-5", state "idle", current ticket "TKT-1", cost "$0.40"
    And its last run shows 52,000 tokens, duration 4 minutes, its finish time, and tries 1

  @SC-41 @REQ-39
  Scenario: A card turns active when its agent starts
    When a build run starts for "TKT-1"
    Then without reloading, the card of agent "build" shows state "active" and current ticket "TKT-1"

  @SC-42 @REQ-39
  Scenario: A card shows stuck when its ticket has an open incident
    Given a build run for "TKT-1" failed with a Claude API error
    When an incident is opened for "TKT-1"
    Then without reloading, the card of agent "build" shows state "stuck"

  @SC-43 @REQ-40
  Scenario: The board groups tickets by status with dependencies
    Given feature "cart" also has ticket "TKT-2" depending on "TKT-1"
    And ticket "TKT-1" has status "review" and "TKT-2" has status "todo"
    When the user opens the board of feature "cart"
    Then "TKT-1" is in column "review" and "TKT-2" in column "todo"
    And "TKT-2" shows it depends on "TKT-1"

  @SC-44 @REQ-41
  Scenario: The inbox lists escalated tickets
    Given "TKT-1" was escalated with ask "Should totals include tax?"
    When the user opens the inbox
    Then it lists "TKT-1" with "Should totals include tax?" and a link to its issue

  @SC-45 @REQ-44
  Scenario: The cost view shows the four totals
    Given runs for "TKT-1" cost plan 1.00 and build 0.50
    When the user opens the cost view of project "shop"
    Then it shows per agent plan "$1.00" and build "$0.50", per ticket "TKT-1" "$1.50", build on "TKT-1" "$0.50", and overall "$1.50"
