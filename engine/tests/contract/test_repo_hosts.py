import json
from pathlib import Path
from urllib.parse import unquote

import httpx
import pytest
from pydantic import SecretStr

from limo.hosts.github import GitHubHost
from limo.hosts.gitlab import GitLabHost
from limo.hosts.ports import HostError, HostProject, IssueComment, MergeRequestRef, MrStatus, ReviewComment
from limo.hosts.repo_url import parse_repo
from limo.hosts.router import RoutedHost
from tests.fakes.host import FakeHost

pytestmark = pytest.mark.respx(assert_all_called=False)

HOSTS = ("github", "gitlab")
GH = "https://api.github.test"
GL = "https://gitlab.test/api/v4"
GH_REPO = f"{GH}/repos/acme/shop"
GL_PROJECT = f"{GL}/projects/acme%2Fshop"
FIXTURES = Path(__file__).parent / "fixtures"
VALID_URLS = (
    "https://example.com/acme/shop.git",
    "git@example.com:acme/shop.git",
    "ssh://git@example.com/acme/shop",
)
REVIEWS = {"merged": "reviews_none", "approved": "reviews_approved", "changes": "reviews_changes"}
APPROVALS = {"merged": "approvals_none", "approved": "approvals_approved", "changes": "approvals_none"}
NOTES = {"merged": "notes_none", "approved": "notes_none", "changes": "notes_changes"}
EXPECTED = {
    "merged": ("merged", False, []),
    "approved": ("open", True, []),
    "changes": ("open", False, [ReviewComment("11", "rename")]),
}


def fx(host: str, name: str) -> dict:
    return json.loads((FIXTURES / host / f"{name}.json").read_text())


def make_host(host_kind: str, token: bool = True):
    if host_kind == "github":
        return GitHubHost(SecretStr("limo-gh-token") if token else None, GH, 5.0)
    return GitLabHost(SecretStr("limo-gl-token") if token else None, GL, 5.0)


def project_for(host_kind: str, git_url: str = "https://example.com/acme/shop.git") -> HostProject:
    return HostProject("shop", git_url, host_kind)


def body_of(route) -> dict:
    return json.loads(route.calls.last.request.content)


def _register_status(respx_mock, host_kind: str, scenario: str) -> None:
    if host_kind == "github":
        pull = "pull_merged" if scenario == "merged" else "pull"
        respx_mock.get(f"{GH_REPO}/pulls/7").mock(return_value=httpx.Response(200, json=fx("github", pull)))
        respx_mock.get(f"{GH_REPO}/pulls/7/reviews").mock(
            return_value=httpx.Response(200, json=fx("github", REVIEWS[scenario]))
        )
        return
    mr = "mr_merged" if scenario == "merged" else "mr"
    respx_mock.get(f"{GL_PROJECT}/merge_requests/7").mock(
        return_value=httpx.Response(200, json=fx("gitlab", mr))
    )
    respx_mock.get(f"{GL_PROJECT}/merge_requests/7/approvals").mock(
        return_value=httpx.Response(200, json=fx("gitlab", APPROVALS[scenario]))
    )
    respx_mock.get(f"{GL_PROJECT}/merge_requests/7/notes?sort=asc").mock(
        return_value=httpx.Response(200, json=fx("gitlab", NOTES[scenario]))
    )
    respx_mock.get(f"{GL}/user").mock(return_value=httpx.Response(200, json=fx("gitlab", "user")))


def test_ft_18_1_github_opens_mr_and_enables_auto_merge(respx_mock):
    """FT-18.1 GitHub: open the MR, then enable auto-merge through GraphQL."""
    pull = fx("github", "pull")
    pulls = respx_mock.post(f"{GH_REPO}/pulls").mock(return_value=httpx.Response(201, json=pull))
    respx_mock.get(f"{GH_REPO}/pulls/7").mock(return_value=httpx.Response(200, json=pull))
    graphql = respx_mock.post(f"{GH}/graphql").mock(
        return_value=httpx.Response(200, json=fx("github", "graphql"))
    )
    host = make_host("github")
    project = project_for("github")

    ref = host.open_merge_request(project, "limo/cart/TKT-1", "main", "TKT-1 (cart)")
    host.enable_auto_merge(project, 7)

    assert ref == MergeRequestRef(7, pull["html_url"])
    assert pulls.calls.last.request.headers["Authorization"] == "Bearer limo-gh-token"
    assert body_of(pulls)["head"] == "limo/cart/TKT-1"
    assert body_of(pulls)["base"] == "main"
    gql = body_of(graphql)
    assert gql["variables"]["id"] == "PR_1"
    assert "enablePullRequestAutoMerge" in gql["query"]


def test_ft_18_2_gitlab_opens_mr_and_merges_when_pipeline_succeeds(respx_mock):
    """FT-18.2 GitLab: open the MR, then merge when the pipeline succeeds."""
    mr = fx("gitlab", "mr")
    create = respx_mock.post(f"{GL_PROJECT}/merge_requests").mock(return_value=httpx.Response(201, json=mr))
    merge = respx_mock.put(f"{GL_PROJECT}/merge_requests/7/merge").mock(
        return_value=httpx.Response(200, json=fx("gitlab", "empty"))
    )
    host = make_host("gitlab")
    project = project_for("gitlab")

    ref = host.open_merge_request(project, "limo/cart/TKT-1", "main", "TKT-1 (cart)")
    host.enable_auto_merge(project, 7)

    assert ref == MergeRequestRef(7, mr["web_url"])
    assert create.calls.last.request.headers["PRIVATE-TOKEN"] == "limo-gl-token"
    assert body_of(create)["source_branch"] == "limo/cart/TKT-1"
    assert body_of(create)["target_branch"] == "main"
    assert body_of(merge)["merge_when_pipeline_succeeds"] is True


@pytest.mark.parametrize("host_kind", HOSTS)
@pytest.mark.parametrize("scenario", list(EXPECTED))
def test_ft_18_3_mr_status_merged_approved_and_change_requests(respx_mock, host_kind, scenario):
    """FT-18.3 MR status: merged, approved, and change-request cases."""
    _register_status(respx_mock, host_kind, scenario)
    state, approved, change_requests = EXPECTED[scenario]

    status = make_host(host_kind).merge_request_status(project_for(host_kind), 7)

    assert status == MrStatus(state, approved, change_requests)


@pytest.mark.parametrize("host_kind", HOSTS)
def test_ft_18_4_issue_create_and_status_replaces_old_limo_label(respx_mock, host_kind):
    """FT-18.4 Issue create, then status change keeps unrelated labels."""
    host = make_host(host_kind)
    project = project_for(host_kind)
    if host_kind == "github":
        respx_mock.post(f"{GH_REPO}/issues").mock(
            return_value=httpx.Response(201, json=fx("github", "issue"))
        )
        respx_mock.get(f"{GH_REPO}/issues/3/labels").mock(
            return_value=httpx.Response(200, json=fx("github", "labels"))
        )
        delete = respx_mock.delete(f"{GH_REPO}/issues/3/labels/limo:todo").mock(
            return_value=httpx.Response(200, json=[])
        )
        add = respx_mock.post(f"{GH_REPO}/issues/3/labels").mock(
            return_value=httpx.Response(200, json=fx("github", "labels"))
        )
    else:
        respx_mock.post(f"{GL_PROJECT}/issues").mock(
            return_value=httpx.Response(201, json=fx("gitlab", "issue"))
        )
        respx_mock.get(f"{GL_PROJECT}/issues/3").mock(
            return_value=httpx.Response(200, json=fx("gitlab", "issue"))
        )
        put = respx_mock.put(f"{GL_PROJECT}/issues/3").mock(
            return_value=httpx.Response(200, json=fx("gitlab", "empty"))
        )

    ref = host.create_issue(project, "TKT-1: Cart shows a total")
    host.set_issue_status(project, 3, "planned")

    assert ref.number == 3
    if host_kind == "github":
        assert delete.call_count == 1
        deleted = unquote(str(delete.calls.last.request.url))
        assert deleted.endswith("limo:todo")
        assert "bug" not in deleted
        assert body_of(add) == {"labels": ["limo:planned"]}
    else:
        assert body_of(put) == {"add_labels": "limo:planned", "remove_labels": "limo:todo"}


@pytest.mark.parametrize("host_kind", HOSTS)
def test_ft_18_5_title_and_label_updates(respx_mock, host_kind):
    """FT-18.5 Set issue title and add a label."""
    host = make_host(host_kind)
    project = project_for(host_kind)
    if host_kind == "github":
        patch = respx_mock.patch(f"{GH_REPO}/issues/3").mock(
            return_value=httpx.Response(200, json=fx("github", "issue"))
        )
        labels = respx_mock.post(f"{GH_REPO}/issues/3/labels").mock(
            return_value=httpx.Response(200, json=fx("github", "labels"))
        )
        host.set_issue_title(project, 3, "TKT-1: New")
        host.add_issue_label(project, 3, "factory:needs-human")
        assert body_of(patch) == {"title": "TKT-1: New"}
        assert body_of(labels) == {"labels": ["factory:needs-human"]}
    else:
        put = respx_mock.put(f"{GL_PROJECT}/issues/3").mock(
            return_value=httpx.Response(200, json=fx("gitlab", "empty"))
        )
        host.set_issue_title(project, 3, "TKT-1: New")
        host.add_issue_label(project, 3, "factory:needs-human")
        first, second = (json.loads(call.request.content) for call in put.calls)
        assert first == {"title": "TKT-1: New"}
        assert second == {"add_labels": "factory:needs-human"}


@pytest.mark.parametrize("host_kind", HOSTS)
def test_ft_18_6_comment_and_list_mark_own_comments(respx_mock, host_kind):
    """FT-18.6 Post a comment; list comments, marking Limo's own and skipping system notes."""
    host = make_host(host_kind)
    project = project_for(host_kind)
    respx_mock.get(f"{GH if host_kind == 'github' else GL}/user").mock(
        return_value=httpx.Response(200, json=fx(host_kind, "user"))
    )
    if host_kind == "github":
        post = respx_mock.post(f"{GH_REPO}/issues/3/comments").mock(
            return_value=httpx.Response(201, json=fx("github", "empty"))
        )
        respx_mock.get(f"{GH_REPO}/issues/3/comments").mock(
            return_value=httpx.Response(200, json=fx("github", "comments"))
        )
    else:
        post = respx_mock.post(f"{GL_PROJECT}/issues/3/notes").mock(
            return_value=httpx.Response(201, json=fx("gitlab", "empty"))
        )
        respx_mock.get(f"{GL_PROJECT}/issues/3/notes?sort=asc").mock(
            return_value=httpx.Response(200, json=fx("gitlab", "notes"))
        )

    host.comment_issue(project, 3, "hi")
    comments = host.issue_comments(project, 3)

    assert body_of(post) == {"body": "hi"}
    assert comments == [IssueComment("21", "hi", True), IssueComment("22", "done", False)]


@pytest.mark.parametrize("host_kind", HOSTS)
def test_ft_18_7_external_failures_raise_host_error_without_token(respx_mock, host_kind):
    """FT-18.7 HTTP errors and transport errors become HostError without the token in the message."""
    host = make_host(host_kind)
    project = project_for(host_kind)
    if host_kind == "github":
        respx_mock.post(f"{GH_REPO}/pulls").mock(
            return_value=httpx.Response(422, json={"message": "Validation Failed"})
        )
        respx_mock.get(f"{GH_REPO}/pulls/7").mock(
            return_value=httpx.Response(404, json={"message": "Not Found"})
        )
        respx_mock.post(f"{GH_REPO}/issues").mock(return_value=httpx.Response(500, json={}))
        respx_mock.post(f"{GH_REPO}/issues/3/comments").mock(side_effect=httpx.ConnectError("boom"))
        respx_mock.get(f"{GH_REPO}/issues/3/comments").mock(side_effect=httpx.ConnectError("boom"))
    else:
        respx_mock.post(f"{GL_PROJECT}/merge_requests").mock(
            return_value=httpx.Response(422, json={"message": "Validation Failed"})
        )
        respx_mock.get(f"{GL_PROJECT}/merge_requests/7").mock(
            return_value=httpx.Response(404, json={"message": "Not Found"})
        )
        respx_mock.post(f"{GL_PROJECT}/issues").mock(return_value=httpx.Response(500, json={}))
        respx_mock.post(f"{GL_PROJECT}/issues/3/notes").mock(side_effect=httpx.ConnectError("boom"))
        respx_mock.get(f"{GL_PROJECT}/issues/3/notes?sort=asc").mock(side_effect=httpx.ConnectError("boom"))
        respx_mock.get(f"{GL}/user").mock(return_value=httpx.Response(200, json=fx("gitlab", "user")))
    calls = [
        lambda: host.open_merge_request(project, "limo/cart/TKT-1", "main", "TKT-1 (cart)"),
        lambda: host.merge_request_status(project, 7),
        lambda: host.create_issue(project, "TKT-1: Cart shows a total"),
        lambda: host.comment_issue(project, 3, "hi"),
        lambda: host.issue_comments(project, 3),
    ]

    for call in calls:
        with pytest.raises(HostError) as error:
            call()
        assert "limo-gh-token" not in str(error.value)
        assert "limo-gl-token" not in str(error.value)


@pytest.mark.parametrize("host_kind", HOSTS)
def test_ft_18_8_missing_token_fails_before_any_http_call(respx_mock, host_kind):
    """FT-18.8 A missing token is an invalid state: HostError and no HTTP call."""
    route = respx_mock.route().mock(return_value=httpx.Response(200, json={}))
    host = make_host(host_kind, token=False)

    with pytest.raises(HostError, match="token not configured"):
        host.open_merge_request(project_for(host_kind), "limo/cart/TKT-1", "main", "TKT-1 (cart)")

    assert not route.called


@pytest.mark.parametrize("host_kind", HOSTS)
@pytest.mark.parametrize("git_url", VALID_URLS)
def test_ft_18_9_valid_git_urls_parse_to_owner_repo(host_kind, git_url):
    """FT-18.9 The three supported git URL forms parse to owner/repo."""
    assert parse_repo(git_url) == "acme/shop"


@pytest.mark.parametrize("host_kind", HOSTS)
def test_ft_18_9_file_url_is_rejected(respx_mock, host_kind):
    """FT-18.9 A file URL is rejected as unsupported before any HTTP call."""
    route = respx_mock.route().mock(return_value=httpx.Response(200, json={}))
    host = make_host(host_kind)

    with pytest.raises(HostError, match="unsupported git url"):
        host.open_merge_request(
            project_for(host_kind, "file:///tmp/shop.git"), "limo/cart/TKT-1", "main", "TKT-1 (cart)"
        )

    assert not route.called
    with pytest.raises(HostError, match="unsupported git url"):
        parse_repo("file:///tmp/shop.git")


def test_ft_18_10_router_picks_adapter_by_kind():
    """FT-18.10 RoutedHost delegates by project kind; unknown kinds are rejected."""
    github_fake = FakeHost()
    gitlab_fake = FakeHost()
    routed = RoutedHost(github=github_fake, gitlab=gitlab_fake)

    routed.create_issue(project_for("github"), "A")
    routed.create_issue(project_for("gitlab"), "B")

    assert github_fake.calls == [("create_issue", "A")]
    assert gitlab_fake.calls == [("create_issue", "B")]
    with pytest.raises(HostError, match="unknown repo host"):
        routed.create_issue(project_for("bitbucket"), "C")
