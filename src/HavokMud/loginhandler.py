import logging
import uuid

from HavokMud.basehandler import BaseHandler
from HavokMud.loginstatemachine import LoginStateMachine

logger = logging.getLogger(__name__)


class LoginHandler(BaseHandler):
    def __init__(self, server, connection):
        BaseHandler.__init__(self, server, connection)
        self.tokens = None
        self.state = "initial"
        self.fsm = LoginStateMachine(self)

    def send_prompt(self, prompt):
        if self.state == "initial":
            self.fsm.go_to_get_email()

    def handle_input(self, tokens):
        print(tokens)
        self.tokens = tokens
        try:
            print("before", self.state)
            self.fsm.process_input()
            print("after", self.state)
        except Exception as e:
            bug_uuid = str(uuid.uuid4())
            self.append_line("Something has gone wrong server-side.  If you wish to refer to this in a support request")
            self.append_line("please reference the event as %s" % bug_uuid)
            logger.error("Bug ID: %s" % bug_uuid)
            logger.exception("Exception!!!")
            self.append_output(None)
