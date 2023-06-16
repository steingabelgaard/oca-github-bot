import contextlib
import random
from enum import Enum

from .. import github
from ..build_wheels import build_and_check_wheel, build_and_publish_wheel
from ..config import (
    GITHUB_CHECK_SUITES_IGNORED,
    GITHUB_STATUS_IGNORED,
    MERGE_BOT_INTRO_MESSAGES,
    dist_publisher,
    switchable,
)
from ..manifest import (
    bump_manifest_version,
    bump_version,
    get_manifest,
    git_modified_addon_dirs,
    is_addon_dir,
    user_can_push,
)
from ..process import CalledProcessError, call, check_call
from ..queue import getLogger, task
from ..utils import hide_secrets
from ..version_branch import make_merge_bot_branch, parse_merge_bot_branch
from .main_branch_bot import main_branch_bot_actions
from .merge_bot import MergeStrategy

_logger = getLogger(__name__)

LABEL_BETA = "beta"

def _remove_beta_label(github, gh_pr, dry_run=False):
    gh_issue = github.gh_call(gh_pr.issue)
    labels = [label.name for label in gh_issue.labels()]
    if LABEL_BETA in labels:
        if dry_run:
            _logger.info(f"DRY-RUN remove {LABEL_BETA} label from PR {gh_pr.url}")
        else:
            _logger.info(f"remove {LABEL_BETA} label from PR {gh_pr.url}")
            github.gh_call(gh_issue.remove_label, LABEL_BETA)

@task()
@switchable("beta_bot")
def beta_bot_remove_label(
    org,
    repo,
    pr,
    dry_run=False,
):
    with github.login() as gh:
        gh_pr = gh.pull_request(org, repo, pr)
        _remove_beta_label(gh, gh_pr, dry_run=False):

@task()
@switchable("beta_bot")
def beta_bot_start(
    org,
    repo,
    pr,
    username,
    dry_run=False,
    merge_strategy=MergeStrategy.merge,
):
    with github.login() as gh:
        gh_pr = gh.pull_request(org, repo, pr)
        target_branch = gh_pr.base.ref + "-beta"
        pr_branch = f"tmp-beta-{pr}"
        try:
            with github.temporary_clone(org, repo, target_branch) as clone_dir:
                # create merge bot branch from PR and rebase it on target branch
                check_call(
                    ["git", "fetch", "origin", f"pull/{pr}/head:{pr_branch}"],
                    cwd=clone_dir,
                )
                check_call(["git", "checkout", pr_branch], cwd=clone_dir)
                if not user_can_push(gh, org, repo, username, clone_dir, target_branch):
                    github.gh_call(
                        gh_pr.create_comment,
                        f"Sorry @{username} you are not allowed to merge.\n\n"
                        f"To do so you must either have push permissions on "
                        f"the repository, or be a declared maintainer of all "
                        f"modified addons.\n\n"
                        f"If you wish to adopt an addon and become it's "
                        f"[maintainer]"
                        f"(https://odoo-community.org/page/maintainer-role), "
                        f"open a pull request to add "
                        f"your GitHub login to the `maintainers` key of its "
                        f"manifest.",
                    )
                    return
                if merge_strategy == MergeStrategy.merge:
                    # nothing to do on the pr branch
                    pass
                elif merge_strategy == MergeStrategy.rebase_autosquash:
                    # rebase the pr branch onto the target branch
                    check_call(["git", "checkout", pr_branch], cwd=clone_dir)
                    check_call(["git", "rebase", "--autosquash", "-i", target_branch], cwd=clone_dir)
                # create the merge commit
                check_call(["git", "checkout", target_branch], cwd=clone_dir)
                msg = f"Merge PR #{pr} into {target_branch}\n\nSigned-off-by {username}"
                check_call(["git", "merge", "--no-ff", "-m", msg, pr_branch], cwd=clone_dir)

                # push and let tests run again; delete on origin
                check_call(["git", "push", "origin", target_branch], cwd=clone_dir)
                
                github.gh_call(
                    gh_pr.create_comment,
                    f"Merged to {target_branch}\n"
                )
                github.gh_call(gh_issue.add_labels, LABEL_BETA)
        except CalledProcessError as e:
            cmd = " ".join(e.cmd)
            github.gh_call(
                gh_pr.create_comment,
                hide_secrets(
                    f"@{username} The merge process could not start, because "
                    f"command `{cmd}` failed with output:\n```\n{e.output}\n```"
                ),
            )
            raise
        except Exception as e:
            github.gh_call(
                gh_pr.create_comment,
                hide_secrets(
                    f"@{username} The merge process could not start, because "
                    f"of exception {e}."
                ),
            )
            raise
