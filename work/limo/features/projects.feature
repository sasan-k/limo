Feature: Projects
  As a developer
  I want to add a project by git URL
  So that agents can work on its workspace

  @SC-1 @REQ-6
  Scenario: Adding a project clones it into a workspace
    Given a git repo "shop" whose default branch "main" contains "README.md"
    When the user adds a project named "shop" with that repo's git URL and repo host "github"
    Then the project "shop" is listed with status "ready"
    And the workspace of "shop" contains "README.md" on branch "main"
