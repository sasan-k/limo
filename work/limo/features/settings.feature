Feature: Settings
  As a developer
  I want to choose each agent's model and the prices per model
  So that I control quality and cost

  Background:
    Given project "shop" was added and its feature "cart" has ticket "TKT-1" with a plan

  @SC-8 @REQ-5
  Scenario: Setting an agent's model shows on that agent
    When the user sets the model of agent "build" to "claude-haiku-5-5"
    Then agent "build" shows model "claude-haiku-5-5"

  @SC-9 @REQ-5
  Scenario: A run uses the agent's configured model
    Given the user set the model of agent "build" to "claude-haiku-5-5"
    When a build run starts for "TKT-1"
    Then the Claude API request uses model "claude-haiku-5-5"

  @SC-10 @REQ-4 @REQ-35
  Scenario: A changed price applies to new usage
    Given the user set the price of "claude-haiku-5-5" to input 0.10 and output 0.50 USD per million tokens
    And the Claude API will answer the build run with usage of 2,000,000 input and 200,000 output tokens
    When a build run for "TKT-1" finishes
    Then that run's cost is 0.300000 USD
