# Copyright (c) ACSONE SA/NV 2018
# Distributed under the MIT License (http://opensource.org/licenses/MIT).

import logging

from ..router import router
from ..tasks.main_branch_bot import main_branch_bot
from ..tasks.add_modified_addons_to_ogir import add_modified_addons_to_ogir
from ..version_branch import is_main_branch_bot_branch

_logger = logging.getLogger(__name__)


@router.register("push")
async def on_push_to_main_branch(event, gh, *args, **kwargs):
    """
    On push to main branches, run the main branch bot task.
    """
    org, repo = event.data["repository"]["full_name"].split("/")
    branch = event.data["ref"].split("/")[-1]

    if not is_main_branch_bot_branch(branch):
        if "pull_request" in event.data:  # Push to PR
            pr = event.data["pull_request"]["number"]
            add_modified_addons_to_ogir.delay(org, repo, pr)
        return

    main_branch_bot.delay(org, repo, branch, build_wheels=False)
