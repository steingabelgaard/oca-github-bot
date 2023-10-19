# Copyright (c) ACSONE SA/NV 2018
# Distributed under the MIT License (http://opensource.org/licenses/MIT).

import logging

from ..router import router
from ..tasks.beta_bot import beta_bot_remove_label

_logger = logging.getLogger(__name__)


@router.register("pull_request", action="synchronize")
async def on_pr_update(event, gh, *args, **kwargs):
    """
    Whenever a PR is updated, remove beta label
    
    """
    
    org, repo = event.data["repository"]["full_name"].split("/")
    pr = event.data["pull_request"]["number"]
    _logger.info('PR sync %s', pr)
    beta_bot_remove_label.delay(org, repo, pr)
