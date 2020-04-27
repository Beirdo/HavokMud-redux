import logging
import uuid

from HavokMud.basehandler import BaseHandler
from HavokMud.logging_support import AccountLogMessage
from HavokMud.loginstatemachine import LoginStateMachine

logger = logging.getLogger(__name__)


class LoginHandler(BaseHandler):
    def __init__(self, connection):
        BaseHandler.__init__(self, connection)
        self.tokens = None
        self.state = "initial"
        self.fsm = LoginStateMachine(self)

    def send_prompt(self, prompt):
        if self.state == "initial":
            self.fsm.go_to_get_email()

    def handle_input(self, tokens):
        self.tokens = tokens
        try:
            logger.debug(AccountLogMessage(self.account, "before state: %s" % self.state))
            self.fsm.process_input()
            logger.debug(AccountLogMessage(self.account, "after state: %s" % self.state))
        except Exception as e:
            bug_uuid = str(uuid.uuid4())
            self.append_line("Something has gone wrong server-side.  If you wish to refer to this in a support request")
            self.append_line("please reference the event as %s" % bug_uuid)
            logger.error(AccountLogMessage(self.account, "Bug ID: %s" % bug_uuid))
            logger.exception(AccountLogMessage(self.account, "Exception!!!"))
            self.append_output(None)
