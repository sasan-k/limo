Feature: Repo host adapters
  As a developer
  I want Limo to talk to GitHub and GitLab as its own identity
  So that a human approver can approve its merge requests

  @SC-60 @REQ-54 @REQ-26
  Scenario: Opening a merge request on GitHub uses the GitHub API as Limo
    Given project "shop" uses repo host "github" with Limo's token "limo-gh-token"
    When Limo opens the merge request for "TKT-1" from "limo/cart/TKT-1" to "main"
    Then the GitHub API receives a pull request create call authorized with "limo-gh-token"
    And auto-merge is requested for that pull request

  @SC-61 @REQ-54 @REQ-26
  Scenario: Opening a merge request on GitLab uses the GitLab API as Limo
    Given project "shop" uses repo host "gitlab" with Limo's token "limo-gl-token"
    When Limo opens the merge request for "TKT-1" from "limo/cart/TKT-1" to "main"
    Then the GitLab API receives a merge request create call authorized with "limo-gl-token"
    And merge-when-pipeline-succeeds is set on that merge request
