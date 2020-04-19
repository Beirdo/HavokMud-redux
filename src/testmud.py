#! /usr/bin/env python

import logging

from HavokMud.startup import start_mud

logger = logging.getLogger(__name__)

exit(start_mud(looping=True))
