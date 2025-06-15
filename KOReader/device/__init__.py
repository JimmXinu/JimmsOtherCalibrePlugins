"""KOReader device driver."""

import logging
logger = logging.getLogger(__name__)
loghandler=logging.StreamHandler()
loghandler.setFormatter(logging.Formatter("KR: %(levelname)s: %(asctime)s: %(filename)s(%(lineno)d): %(message)s"))
logger.addHandler(loghandler)

from calibre.constants import DEBUG
if DEBUG:
    loghandler.setLevel(logging.DEBUG)
    logger.setLevel(logging.DEBUG)
else:
    loghandler.setLevel(logging.CRITICAL)
    logger.setLevel(logging.CRITICAL)

