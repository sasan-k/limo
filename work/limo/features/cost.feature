Feature: Cost
  As a developer
  I want every run's tokens and dollars recorded and totaled
  So that I see what each agent and ticket costs

  Background:
    Given project "shop" was added and its feature "cart" has tickets "TKT-1" and "TKT-2" with plans
    And the price of "claude-opus-5-5" is input 4.00, output 20.00, cache read 0.20, cache write 5.00 USD per million tokens

  @SC-11 @REQ-34
  Scenario: Each Claude API call's usage is recorded on the run
    Given the Claude API will answer a plan run for "TKT-1" in 2 calls with usage:
      | input  | output | cache_read | cache_write |
      | 10,000 | 2,000  | 0          | 8,000       |
      | 3,000  | 1,000  | 8,000      | 0           |
    When the plan run finishes
    Then the run shows model "claude-opus-5-5" and tokens input 13,000, output 3,000, cache read 8,000, cache write 8,000

  @SC-12 @REQ-35
  Scenario: A run's cost is its tokens times the price table
    Given the Claude API will answer a plan run for "TKT-1" with usage of 1,000,000 input and 100,000 output tokens
    When the plan run finishes
    Then that run's cost is 6.000000 USD

  @SC-13 @REQ-36
  Scenario: Cost totals per agent, ticket, agent and ticket, and overall
    Given these runs finished with costs:
      | agent | ticket | cost |
      | plan  | TKT-1  | 1.00 |
      | build | TKT-1  | 0.20 |
      | build | TKT-1  | 0.30 |
      | plan  | TKT-2  | 2.00 |
    When the user opens the cost totals of project "shop"
    Then the total per agent is plan 3.00, build 0.50
    And the total per ticket is TKT-1 1.50, TKT-2 2.00
    And the total for build on TKT-1 is 0.50
    And the overall total is 3.50

  @SC-54 @REQ-52
  Scenario: A price change leaves past costs unchanged
    Given a plan run for "TKT-1" finished with cost 6.000000 USD
    When the user sets the price of "claude-opus-5-5" to input 8.00 and output 40.00 USD per million tokens
    Then that plan run's cost is still 6.000000 USD
