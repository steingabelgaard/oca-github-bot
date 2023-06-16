# Copyright 2019 Simone Rubino - Agile Business Group
# Distributed under the MIT License (http://opensource.org/licenses/MIT).

from .. import github, odoo_client
from ..config import switchable
from ..queue import getLogger, task
import re

_logger = getLogger(__name__)


@task()
@switchable("add_sgtask_info")
def add_sgtask_info(org, repo, pr, dry_run=False):
    with github.login() as gh:
        gh_pr = gh.pull_request(org, repo, pr)
        pr_branch = gh_pr.head.ref
        if 'issue' in pr_branch and gh_pr.repository.private:  # TODO: Show other (shorter) info on non private repos?
            match = re.findall(r'-issue(\d+)-', pr_branch)
            name = False
            with odoo_client.login() as odoo:
                Tasks = odoo.env['project.task']
                task_ids = Tasks.search([('code', '=', match[0])])
                for task in Tasks.browse(task_ids):
                    name = task.name
                    url = 'https://adm.steingabelgaard.dk/mail/view?model=project.task&res_id=%d' % task.id
                    code = task.code
                    break
            if name:
                task_comment = "Task [%s - %s](%s)" %(code, name, url)
                body = gh_pr.issue().body
                if not body:
                    body = ''
                if task_comment not in body:
                    body += '\n\n' + task_comment
                    body = gh_pr.issue().edit(body=body)
                # return github.gh_call(gh_pr.create_comment, task_comment)
        