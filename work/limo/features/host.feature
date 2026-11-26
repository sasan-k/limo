Feature: Repo host
  As a developer
  I want each ticket to reach me as a merge request I approve
  So that nothing merges without a human

  Background:
    Given project "shop" was added with repo host "github"
    And its feature "cart" has tickets "TKT-1" titled "Cart shows a total" and "TKT-2" depending on "TKT-1"
    And the Claude API answers every run by doing its stage's work and setting the next ticket status
    And the runner is turned on

  @SC-24 @REQ-29
  Scenario: A ticket ships as one merge request from its own branch
    Given ticket "TKT-1" has status "todo"
    When the close run for "TKT-1" finishes
    Then the repo host has branch "limo/cart/TKT-1" with the ticket's code and "context/" changes
    And a merge request from "limo/cart/TKT-1" to "main" is open
    And ticket "TKT-1" has status "review"

  @SC-25 @REQ-30
  Scenario: Limo enables auto-merge and never merges
    When the merge request for "TKT-1" is opened
    Then merge-when-approved-and-pipeline-succeeds is enabled on it
    And Limo has made no merge call to the repo host

  @SC-26 @REQ-31 @REQ-20
  Scenario: A merged merge request makes the ticket done
    Given ticket "TKT-1" has status "review" with an open merge request
    When a human approves it, the repo host merges it, and the next poll runs
    Then ticket "TKT-1" has status "done"

  @SC-27 @REQ-31
  Scenario: An unapproved merge request keeps the ticket in review
    Given ticket "TKT-1" has status "review" with an open merge request
    When the next poll runs and the merge request is still not approved
    Then ticket "TKT-1" has status "review"

  @SC-28 @REQ-32
  Scenario: A dependent ticket branches from the merged code
    Given the merge request of "TKT-1" was merged into "main"
    When the plan run for "TKT-2" starts
    Then branch "limo/cart/TKT-2" starts from the "main" commit that contains the "TKT-1" merge

  @SC-29 @REQ-33
  Scenario: Requested changes send the ticket back to plan
    Given ticket "TKT-1" has status "review" with an open merge request
    When a human requests changes with comment "rename total() to cart_total()" and the next poll runs
    Then "work/cart/reports/TKT-1-review-1.md" contains "rename total() to cart_total()"
    And ticket "TKT-1" has status "todo"
    And the next run for "TKT-1" is a plan run

  @SC-30 @REQ-27
  Scenario: A ticket is mirrored to an issue
    When the spec run of feature "cart" finishes
    Then the repo host has an issue titled "TKT-1: Cart shows a total"

  @SC-31 @REQ-27
  Scenario: The issue follows the ticket status
    Given ticket "TKT-1" has an issue
    When ticket "TKT-1" changes status from "planned" to "built"
    Then the issue of "TKT-1" has label "limo:built" and not "limo:planned"
