import logging
import os
import stackless
from functools import partial
from tempfile import NamedTemporaryFile

from HavokMud.externalhandler import ExternalHandler

logger = logging.getLogger(__name__)


class Editor(object):
    """
    This class is used to use an editor over the connection, and then return the edited file contents.  The
    files are temporary files, and are deleted when we've finished with them, and the editors are run in a
    restricted mode so they can only edit that file.

    To use:
    callback = self.handle_this_edited_value   # signature of void callback(str)
    editor can be "vim" or "nano", default of "nano"
    editorObj = Editor(connection, editor, callback)
    editorObj.launch(initial_contents)

    The calling tasklet can then yield as the user input loop will trigger the original handler on further input
    after the callback has been called to set the value of whatever variable being edited.
    """
    editors = {
        "nano": ["nano", "-R"],
        "vim": ["vim", "-Z"],
    }

    def __init__(self, connection, editor, callback=None):
        from HavokMud.startup import server_instance
        self.connection = connection
        self.server = server_instance
        self.editor = editor
        self.channel = stackless.channel()
        self.callback_channel = stackless.channel()
        self.file_ = None
        self.editor_callback = partial(self.editor_callback_wrapper, callback)

    def launch(self, initial_contents=None):
        command = self.editors.get(self.editor, None)
        if not command:
            raise NotImplementedError("Editor %s is not configured" % self.editor)
        self.file_ = NamedTemporaryFile("w+", delete=False)
        if initial_contents:
            self.file_.write(initial_contents)
            self.file_.flush()
            self.file_.seek(0)
        command += self.file_.name
        self.connection.handler = ExternalHandler(self.connection, command, self.channel,
                                                  self.handler_callback, self.editor_callback)

    def handler_callback(self):
        self.channel.receive()
        self.file_.seek(0)
        contents = self.file_.read()
        filename = self.file_.name
        self.file_.close()
        os.unlink(filename)
        self.callback_channel.send(contents)

    def default_editor_callback(self):
        contents = self.callback_channel.receive()
        return contents

    def editor_callback_wrapper(self, callback):
        if callback and hasattr(callback, "__call__"):
            callback(self.default_editor_callback())
