Feature: Runner
  As a developer
  I want the runner to move tickets through the stages on its own
  So that requirements become merge requests without manual steps

  Background:
    Given project "shop" was added
    And its feature "cart" has tickets "TKT-1" and "TKT-2" where "TKT-2" depends on "TKT-1"
    And the Claude API answers every run by doing its stage's work and setting the next ticket status
    And the runner is turned on

  @SC-14 @REQ-14
  Scenario Outline: The runner starts the agent that matches the ticket status
    Given ticket "TKT-1" has status "<status>"
    When the runner takes its next step
    Then a "<agent>" run starts for "TKT-1"

    Examples:
      | status   | agent  |
      | todo     | plan   |
      | planned  | build  |
      | built    | verify |
      | verified | close  |

  @SC-15 @REQ-14
  Scenario: A ticket whose dependency is not done does not start
    Given ticket "TKT-1" has status "blocked"
    And ticket "TKT-2" has status "todo"
    When the runner takes its next step
    Then no run starts for "TKT-2"

  @SC-16 @REQ-14
  Scenario: A ticket in review waits for its merge request
    Given ticket "TKT-1" has status "review"
    And ticket "TKT-2" has status "todo"
    When the runner takes its next step
    Then no run starts

  @SC-17 @REQ-16
  Scenario: One ticket runs at a time
    Given feature "cart" also has ticket "TKT-3" with no dependencies
    And tickets "TKT-1" and "TKT-3" have status "todo"
    When the runner takes its next step
    Then exactly one run is active
    And "TKT-3" starts only after "TKT-1" reaches status "review"

  @SC-18 @REQ-16
  Scenario: Each stage is a fresh run
    Given ticket "TKT-1" has status "todo"
    When the plan run and then the build run for "TKT-1" finish
    Then the build run's first Claude API request contains no message from the plan run

  @SC-19 @REQ-15
  Scenario: A project without context runs architecture init before spec
    Given project "blog" was added and its workspace has no "context/" folder
    When the user submits the intake form for feature "posts" on project "blog"
    Then an architecture run with mode "init-existing" starts before any spec run

  @SC-20 @REQ-15
  Scenario: NFRs get ADRs before the first ticket is planned
    Given the spec run of feature "posts" wrote "nfr.md" with row "NFR-1"
    And map-check of "posts" prints OK
    When the runner takes its next step
    Then an architecture run with mode "nfr posts" starts before any plan run

  @SC-21 @REQ-15
  Scenario: No NFRs means no architecture nfr run
    Given the spec run of feature "posts" wrote "nfr.md" with no rows
    And map-check of "posts" prints OK
    When the runner takes its next step
    Then a plan run starts for the first ready ticket of "posts"

  @SC-22 @REQ-18
  Scenario: A run interrupted by a restart is retried on a clean workspace
    Given a build run for "TKT-1" is running and has changed "src/cart.py" without committing
    When the engine restarts
    Then that run shows status "interrupted"
    And "src/cart.py" in the workspace equals its last commit on the ticket branch
    And a new build run starts for "TKT-1" with attempt 2

  @SC-23 @REQ-18 @REQ-19
  Scenario: An interrupted run at its retry limit makes the ticket stuck
    Given ticket "TKT-1" has build tries 2
    And a build run for "TKT-1" is running
    When the engine restarts
    Then no new build run starts for "TKT-1"
    And an incident is opened for "TKT-1" with trigger "limits"

  @SC-49 @REQ-45
  Scenario: The intake form saves the requirements in the workspace
    When the user submits the intake form for feature "posts" on project "shop" with text "Readers can comment on posts."
    Then the workspace of "shop" has "work/posts/requirements/posts.md" containing "Readers can comment on posts."

  @SC-50 @REQ-46
  Scenario: The runner starts off
    Given ticket "TKT-1" has status "todo"
    And Limo was just started
    When the user looks at the runner switch
    Then it shows "off"
    And no run starts

  @SC-51 @REQ-46
  Scenario: Turning the runner on starts the next ticket
    Given the runner is turned off
    And ticket "TKT-1" has status "todo"
    When the user turns the runner on
    Then a plan run starts for "TKT-1"

  @SC-52 @REQ-46
  Scenario: Turning the runner off stops new runs
    Given a build run for "TKT-1" is active
    And ticket "TKT-3" has status "todo"
    When the user turns the runner off
    Then the build run for "TKT-1" finishes
    And no run starts for "TKT-3"

  @SC-59 @REQ-53
  Scenario: Feature work files never leave the workspace
    Given the intake form saved "work/cart/requirements/cart.md" in the workspace of "shop"
    When the close run for "TKT-1" finishes and its merge request is opened
    Then the workspace's git status lists nothing under "work/"
    And the merge request contains no file under "work/"
