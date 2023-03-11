from .. import github, odoo_client
from ..config import switchable
from ..queue import getLogger, task

_logger = getLogger(__name__)

@task()
@switchable("task_link_bot")
def task_link_start(org, repo, pr, username, task_code=None, dry_run=False):
    with github.login() as gh:
        gh_pr = gh.pull_request(org, repo, pr)
        with odoo_client.login() as odoo:
            task_id = False
            Tasks = odoo.env['project.task']
            task_ids = Tasks.search([('code', '=', task_code)])
            for task in Tasks.browse(task_ids):
                name = task.name
                url = 'https://adm.steingabelgaard.dk/mail/view?model=project.task&res_id=%d' % task.id
                code = task.code
                task_id = task.id
                break
            if not task_ids:
                comment = "Sorry, task %s could not be found!" % task_code
            else:
                task_comment = "Task [%s - %s](%s)" %(code, name, url)
                body = gh_pr.issue().body
                if not body:
                    body = ''
                if task_comment not in body:
                    body += '\n\n' + task_comment
                    body = gh_pr.issue().edit(body=body)

            PRs = odoo.env['project.git.pullrequest']
            pr_ids = PRs.search([('url', '=', gh_pr.html_url)])
            if pr_ids and task_id:
                PRs.browse(pr_ids[0]).write({'task_id': task_id})
            if comment:
                return github.gh_call(gh_pr.create_comment, comment)
            else:
                return
