# Copyright 2019 Tecnativa - Pedro M. Baeza
# Copyright 2021 Tecnativa - Víctor Martínez
# Distributed under the MIT License (http://opensource.org/licenses/MIT).

import re

from .. import github
from ..config import switchable
from ..manifest import user_can_push
from ..process import check_call
from ..queue import task
from ..utils import hide_secrets


def _create_or_find_branch_milestone(gh_repo, branch):
    for milestone in gh_repo.milestones():
        if milestone.title == branch:
            return milestone
    return gh_repo.create_milestone(branch)


def _find_issue(gh_repo, milestone, target_branch):
    issue_title = f"Migration to version {target_branch}"
    issue = False
    for i in gh_repo.issues(milestone=milestone.number):
        if i.title == issue_title:
            issue = i
            break
    return issue


def _set_lines_issue(gh_pr_user_login, gh_pr_number, issue_body, module):
    lines = []
    added = False
    module_list = False
    old_pr_number = False
    new_line = f"- [ ] {module} - By @{gh_pr_user_login} - #{gh_pr_number}"
    for line in issue_body.split("\n"):
        if added:  # Bypass the checks for faster completion
            lines.append(line)
            continue
        groups = re.match(rf"^- \[( |x)\] \b{module}\b", line)
        if groups:  # Line found
            # Get the Old PR value
            regex = r"\#(\d*)"
            old_pr_result = re.findall(regex, line)
            if old_pr_result:
                old_pr_number = int(old_pr_result[0])
            # Respect check mark status if existing
            new_line = new_line[:3] + groups[1] + new_line[4:]
            lines.append(new_line)
            added = True
            continue
        else:
            splits = re.split(r"- \[[ |x]\] ([0-9a-zA-Z_]*)", line)
            if len(splits) >= 2:
                # Flag for detecting if we have passed already module list
                module_list = True
                line_module = splits[1]
                if line_module > module:
                    lines.append(new_line)
                    added = True
            elif module_list:
                lines.append(new_line)
                added = True
        lines.append(line)

    # make the addition working on an empty migration issue
    if not added:
        lines.append(new_line)
    return "\n".join(lines), old_pr_number


@task()
@switchable("migration_issue_bot")
def migration_issue_start(org, repo, pr, username, module=None, dry_run=False):
    with github.login() as gh:
        gh_pr = gh.pull_request(org, repo, pr)
        gh_repo = gh.repository(org, repo)
        target_branch = gh_pr.base.ref
        pr_branch = f"tmp-pr-{pr}"
        try:
            with github.temporary_clone(org, repo, target_branch) as clone_dir:
                # Create merge bot branch from PR and rebase it on target branch
                # This only serves for checking permissions
                check_call(
                    ["git", "fetch", "origin", f"pull/{pr}/head:{pr_branch}"],
                    cwd=clone_dir,
                )
                check_call(["git", "checkout", pr_branch], cwd=clone_dir)
                if not user_can_push(gh, org, repo, username, clone_dir, target_branch):
                    github.gh_call(
                        gh_pr.create_comment,
                        f"Sorry @{username} you are not allowed to mark the addon to"
                        f"be migrated.\n\n"
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
            # Assign milestone to PR
            milestone = _create_or_find_branch_milestone(gh_repo, target_branch)
            gh_pr.issue().edit(milestone=milestone.number)
            # Find issue
            issue = _find_issue(gh_repo, milestone, target_branch)
            if not issue:
                issue_title = f"Migration to version {target_branch}"
                github.gh_call(
                    gh_pr.create_comment,
                    f"There's no issue in this repo with the title '{issue_title}' "
                    f"and the milestone {target_branch}, so not possible to add "
                    f"the comment.",
                )
                return
            # Change issue to add the PR in the module list
            new_body, old_pr_number = _set_lines_issue(
                gh_pr.user.login, gh_pr.number, issue.body, module
            )
            issue.edit(body=new_body)
            if old_pr_number and old_pr_number != pr:
                old_pr = gh.pull_request(org, repo, old_pr_number)
                github.gh_call(
                    gh_pr.create_comment,
                    f"The migration issue (#{issue.number}) has been updated"
                    f" to reference the current pull request.\n"
                    f"however, a previous pull request was referenced :"
                    f" #{old_pr_number}.\n"
                    f"Perhaps you should check that there is no duplicate work.\n"
                    f"CC : @{old_pr.user.login}",
                )
        except Exception as e:
            github.gh_call(
                gh_pr.create_comment,
                hide_secrets(
                    f"@{username} The migration issue commenter process could not "
                    f"start, because of exception {e}."
                ),
            )
            raise
