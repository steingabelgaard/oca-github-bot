# Copyright 2019 Simone Rubino - Agile Business Group
# Distributed under the MIT License (http://opensource.org/licenses/MIT).

from .. import config, github, odoo_client
from ..config import switchable
from ..manifest import (
    addon_dirs_in,
    get_manifest,
    git_modified_addon_dirs,
    is_addon_dir,
    git_modified_addons,
)
from ..process import check_call
from ..queue import getLogger, task

_logger = getLogger(__name__)


@task()
@switchable("add_modified_addons_to_ogir")
def add_modified_addons_to_ogir(org, repo, pr, dry_run=False):
    with github.login() as gh:
        gh_pr = gh.pull_request(org, repo, pr)
        target_branch = gh_pr.base.ref
        with github.temporary_clone(org, repo, target_branch) as clonedir:
            # Get existing addons
            addon_dirs = addon_dirs_in(clonedir, installable_only=True)
            
            # Get list of addons modified in the PR.
            pr_branch = f"tmp-pr-{pr}"
            check_call(
                ["git", "fetch", "origin", f"refs/pull/{pr}/head:{pr_branch}"],
                cwd=clonedir,
            )
            check_call(["git", "checkout", pr_branch], cwd=clonedir)
            modified_addons, _= git_modified_addons(clonedir, target_branch)

            # Remove not installable addons
            # (case where an addon becomes no more installable).
            # modified_addon_dirs = [
            #    d for d in modified_addon_dirs if is_addon_dir(d, installable_only=True)
            # ]
            with odoo_client.login() as odoo:
                PRs = odoo.env['project.git.pullrequest']
                pr_ids = PRs.search([('url', '=', pr.html_url)])
                if pr_ids:
                    PRs.browse(pr_ids[0]).write({'modified_addons': '\n'.join(modified_addons)})
