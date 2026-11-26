# One file per capability: features/<capability>.feature
# Tags: every Scenario has exactly one @SC-<n> (unique within the feature, never reused)
#       and one or more @REQ-<n>. Terms must come from context/glossary.md.
# Given = state reached through production actions · When = one action · Then = externally observable
# Concrete values only. One behavior per scenario. Use Scenario Outline + Examples for variations.

Feature: <capability in glossary terms>
  As a <actor>
  I want <goal>
  So that <value>

  Background:
    Given <shared precondition reached via a production action>

  @SC-1 @REQ-1
  Scenario: <behavior in one sentence>
    Given <customer "Ana" has a balance of 100.00 EUR>
    When <Ana pays 30.00 EUR for order "O-1">
    Then <order "O-1" is "PAID">
    And <Ana's balance is 70.00 EUR>

  @SC-2 @REQ-1 @REQ-4
  Scenario Outline: <behavior with variations>
    Given <…<input>…>
    When <…>
    Then <…<result>…>

    Examples:
      | input | result |
      | <v1>  | <r1>   |
