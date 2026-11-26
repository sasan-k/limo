Feature: Budgets
  As a developer
  I want every ticket and agent to have a spending limit I can raise
  So that no run spends more than I allowed

  Background:
    Given project "shop" was added and its feature "cart" has ticket "TKT-1" with a plan
    And the runner is turned on
    And the price of "claude-opus-5-5" is input 4.00 and output 20.00 USD per million tokens

  @SC-55 @REQ-49
  Scenario: New tickets and agents get the default budgets
    Given the user set the default ticket budget to 5.00 USD and the default agent budget to 2.00 USD
    When the user looks at ticket "TKT-1" and agent "build"
    Then ticket "TKT-1" shows budget "$5.00"
    And agent "build" shows budget "$2.00" for "TKT-1"

  @SC-56 @REQ-50
  Scenario: Reaching the ticket budget stops work and asks the user
    Given ticket "TKT-1" has budget 5.00 USD and has spent 4.90 USD
    And the Claude API will answer the next build call with usage of 50,000 output tokens
    When that build call finishes
    Then the build run stops without another Claude API call
    And the inbox lists "TKT-1" with reason "ticket budget reached: $5.90 of $5.00"
    And no resolver run starts

  @SC-57 @REQ-50
  Scenario: Reaching an agent's budget stops that agent and asks the user
    Given agent "build" has budget 2.00 USD for "TKT-1" and has spent 1.95 USD on it
    And the Claude API will answer the next build call with usage of 5,000 output tokens
    When that build call finishes
    Then the build run stops without another Claude API call
    And the inbox lists "TKT-1" with reason "build budget reached: $2.05 of $2.00"

  @SC-58 @REQ-51
  Scenario: Raising a reached budget lets the ticket continue
    Given the inbox lists "TKT-1" with reason "ticket budget reached: $5.90 of $5.00"
    When the user raises the budget of "TKT-1" to 8.00 USD and presses Continue
    Then a build run starts for "TKT-1"
    And "TKT-1" is no longer in the inbox
