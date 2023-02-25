# Copyright 2019 Simone Rubino - Agile Business Group
# Distributed under the MIT License (http://opensource.org/licenses/MIT).

from .. import github, odoo_client
from ..config import switchable
from ..queue import getLogger, task
import re

_logger = getLogger(__name__)


@task()
@switchable("update_pr_state")
def update_pr_state(org, repo, pr, merged, dry_run=False):
    with github.login() as gh:
        gh_pr = gh.pull_request(org, repo, pr)
        pr_number = gh_pr.number
        if pr_number
            with odoo_client.login() as odoo:
                Prs = odoo.env['project.git.pullrequest']
                pr_ids = Prs.search([('pr_number', '=', pr_number), ('url', '=', gh_pr.html_url)])
                for pr in Prs.browse(pr_ids):
                    pr.state = 'merged' if merged else 'closed'
