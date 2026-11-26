Feature: Prompt editor
  As a developer
  I want to edit agent prompts and reference files with history
  So that I can tune agents and undo bad changes

  Background:
    Given project "shop" was added and its feature "cart" has ticket "TKT-1" with a plan

  @SC-46 @REQ-42 @REQ-43
  Scenario: A saved prompt is used by the next run
    When the user saves agent "build"'s prompt with the added line "Always run the formatter last."
    Then the prompt history of "build" has a new version
    And the next build run's system prompt contains "Always run the formatter last."

  @SC-47 @REQ-42 @REQ-43
  Scenario: Editing a reference file
    When the user saves reference file "templates/build-report.md" of agent "build" with the added line "- duration: <minutes>"
    Then the history of "templates/build-report.md" has a new version
    And reading that reference file returns the added line

  @SC-48 @REQ-43
  Scenario: Rolling back a prompt restores an earlier version
    Given agent "build"'s prompt was saved twice, as version A and then version B
    When the user rolls the prompt back to version A
    Then the prompt of "build" equals version A
    And the prompt history of "build" has a new version on top of B
