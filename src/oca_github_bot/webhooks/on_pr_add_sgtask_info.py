# Copyright 2019 Simone Rubino - Agile Business Group
# Distributed under the MIT License (http://opensource.org/licenses/MIT).

import logging

from ..router import router
from ..tasks.add_sgtask_info import add_sgtask_info

_logger = logging.getLogger(__name__)


@router.register("pull_request", action="opened")
@router.register("pull_request", action="reopened")
async def on_pr_open_add_sgtask_info(event, *args, **kwargs):
    """
    Whenever a PR is opened, mention the Task if found.
    """
    org, repo = event.data["repository"]["full_name"].split("/")
    pr = event.data["pull_request"]["number"]
    add_sgtask_info.delay(org, repo, pr)
