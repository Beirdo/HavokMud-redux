#
# Stackless compatible socket module (for Python 3.0+):
#
# Author: Richard Tew <richard.m.tew@gmail.com>
#
# This code was written to serve as an example of Stackless Python usage.
# Feel free to email me with any questions, comments, or suggestions for
# improvement.
#
# This wraps the asyncore module and the dispatcher class it provides in order
# write a socket module replacement that uses channels to allow calls to it to
# block until a delayed event occurs.
#
# Not all aspects of the socket module are provided by this file.  Examples of
# it in use can be seen at the bottom of this file.
#
# NOTE: Versions of the asyncore module from Python 2.4 or later include bug
#       fixes and earlier versions will not guarantee correct behaviour.
#       Specifically, it monitors for errors on sockets where the version in
#       Python 2.3.3 does not.
#

# Possible improvements:
# - More correct error handling.  When there is an error on a socket found by
#   poll, there is no idea what it actually is.
# - Launching each bit of incoming data in its own tasklet on the recvChannel
#   send is a little over the top.  It should be possible to add it to the
#   rest of the queued data
import asyncore
import logging
import socket as stdsocket  # We need the "socket" name for the function we export.
import stackless

logger = logging.getLogger(__name__)

# Cache socket module entries we may monkeypatch.
from _socket import SOCK_DGRAM, error, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR

_old_socket = stdsocket.socket
_old_SocketIO = stdsocket.SocketIO
_old_realsocket = stdsocket._realsocket


def install():
    if stdsocket.socket is _new_socket:
        raise RuntimeError("Still installed")
    stdsocket._realsocket = _old_realsocket
    stdsocket.socket = _new_socket
    stdsocket.SocketIO = _new_SocketIO
    stdsocket.SocketType = _new_socket
    stdsocket._socketobject = _new_socket


def uninstall():
    stdsocket._realsocket = _old_realsocket
    stdsocket.socket = _old_socket
    stdsocket.SocketIO = _old_SocketIO
    stdsocket.SocketType = _old_socket
    stdsocket._socketobject = _old_socket


class _new_SocketIO(_old_SocketIO):
    def __init__(self, sock, mode):
        if not isinstance(sock, _fakesocket):
            raise RuntimeError("Bad socket '%s'" % sock.__class__.__name__)
        _old_SocketIO.__init__(self, sock, mode)


# If we are to masquerade as the socket module, we need to provide the constants.
for k in stdsocket.__all__:
    globals()[k] = stdsocket.__dict__[k]

stringEncoding = "utf-8"

# Someone needs to invoke asyncore.poll() regularly to keep the socket
# data moving.  The "ManageSockets" function here is a simple example
# of such a function.  It is started by StartManager(), which uses the
# global "managerRunning" to ensure that no more than one copy is
# running.
#
# If you think you can do this better, register an alternative to
# StartManager using stacklesssocket_manager().  Your function will be
# called every time a new socket is created; it's your responsibility
# to ensure it doesn't start multiple copies of itself unnecessarily.
#

managerRunning = False


def ManageSockets():
    global managerRunning

    t = stackless.getcurrent()
    while len(asyncore.socket_map):
        # Check the sockets for activity.
        t.block_trap = False
        asyncore.poll(0.01)
        t.block_trap = True
        # Yield to give other tasklets a chance to be scheduled.
        stackless.schedule()

    managerRunning = False


def StartManager():
    global managerRunning
    if not managerRunning:
        managerRunning = True
        stackless.tasklet(ManageSockets)()


_manage_sockets_func = StartManager


def stacklesssocket_manager(mgr):
    global _manage_sockets_func
    _manage_sockets_func = mgr


def socket(*args, **kwargs):
    import sys
    if "socket" in sys.modules and sys.modules["socket"] is not stdsocket:
        raise RuntimeError("Use 'stacklesssocket.install' instead of replacing the 'socket' module")


class _new_socket(object):
    _old_socket.__doc__

    def __init__(self, family=AF_INET, type=SOCK_STREAM, proto=0, fileno=None):
        sock = _old_socket(family, type, proto, fileno)
        _manage_sockets_func()
        self.__dict__["dispatcher"] = _fakesocket(sock)

    def __getattr__(self, attrName):
        # Forward nearly everything to the dispatcher
        if not attrName.startswith("__"):
            # I don't like forwarding __repr__
            return getattr(self.dispatcher, attrName)

    def __setattr__(self, attrName, attrValue):
        setattr(self.dispatcher, attrName, attrValue)

    def __del__(self):
        if not hasattr(self, "dispatcher"):
            return
        # Close dispatcher if it isn't already closed
        if self.dispatcher._fileno is not None:
            try:
                self.dispatcher.close()
            finally:
                self.dispatcher = None

    def makefile(self, *args, **kwargs):
        return _old_socket.makefile(self.dispatcher, *args, **kwargs)


class _fakesocket(asyncore.dispatcher):
    connect_channel = None
    accept_channel = None
    recv_channel = None
    was_connected = False

    def __init__(self, realSocket):
        # This is worth doing.  I was passing in an invalid socket which
        # was an instance of _fakesocket and it was causing tasklet death.
        if not isinstance(realSocket, _old_socket):
            raise RuntimeError("An invalid socket (class '%s') passed to _fakesocket" % realSocket.__class__.__name__)

        # This will register the real socket in the internal socket map.
        asyncore.dispatcher.__init__(self, realSocket)
        self.socket = realSocket

        self.recv_channel = stackless.channel()
        self.recv_channel.preference = 0
        self.read_bytes = bytearray()
        self.read_index = 0

        self.send_buffer = bytearray()
        self.send_to_buffers = []

    def __del__(self):
        # There are no more users (sockets or files) of this fake socket, we
        # are safe to close it fully.  If we don't, asyncore will choke on
        # the weakref failures.
        self.close()

    # The asyncore version of this function depends on socket being set
    # which is not the case when this fake socket has been closed.
    def __getattr__(self, attr):
        if not hasattr(self, "socket"):
            raise AttributeError("socket attribute unset on '" + attr + "' lookup")
        return getattr(self.socket, attr)

    def add_channel(self, map=None):
        if map is None:
            map = self._map
        # map[self._fileno] = weakref.proxy(self)
        # if we leave in a weakref, then our listen socket gets reaped during gc
        # even though it still should be running as this weakref somehow ends up
        # being the only ref (?)
        map[self._fileno] = self

    def del_channel(self, map=None):
        fd = self._fileno
        if map is None:
            map = self._map
        if fd in map:
            logger.debug("closing channel %s:%s" % (fd, self))
            del map[fd]
        self._fileno = None

    def writable(self):
        if self.socket.type != SOCK_DGRAM and not self.connected:
            return True
        return len(self.send_buffer) or len(self.send_to_buffers)

    def accept(self):
        if not self.accept_channel:
            self.accept_channel = stackless.channel()
        return self.accept_channel.receive()

    def connect(self, address):
        asyncore.dispatcher.connect(self, address)

        # UDP sockets do not connect.
        if self.socket.type != SOCK_DGRAM and not self.connected:
            if not self.connect_channel:
                self.connect_channel = stackless.channel()
                # Prefer the sender.  Do not block when sending, given that
                # there is a tasklet known to be waiting, this will happen.
                self.connect_channel.preference = 1
            self.connect_channel.receive()

    def send(self, data, flags=0):
        if not self.connected:
            # The socket was never connected.
            if not self.was_connected:
                raise error(10057, "Socket is not connected")

            # The socket has been closed already.
            raise error(stdsocket.EBADF, 'Bad file descriptor')

        self.send_buffer.extend(data)
        stackless.schedule()
        return len(data)

    def sendall(self, data, flags=0):
        if not self.connected:
            # The socket was never connected.
            if not self.was_connected:
                raise error(10057, "Socket is not connected")

            # The socket has been closed already.
            raise error(stdsocket.EBADF, 'Bad file descriptor')

        # WARNING: this will busy wait until all data is sent
        # It should be possible to do away with the busy wait with
        # the use of a channel.
        self.send_buffer.extend(data)
        while self.send_buffer:
            stackless.schedule()
        return len(data)

    def sendto(self, send_data, flags, send_address):
        wait_channel = None
        for idx, (data, address, channel, sent_bytes) in enumerate(self.send_to_buffers):
            if address == send_address:
                self.send_to_buffers[idx] = (data + send_data, address, channel, sent_bytes)
                wait_channel = channel
                break
        if wait_channel is None:
            wait_channel = stackless.channel()
            self.send_to_buffers.append((send_data, send_address, wait_channel, 0))
        return wait_channel.receive()

    # Read at most byteCount bytes.
    def recv(self, byte_count, flags=0):
        b = bytearray()
        self.recv_into(b, byte_count, flags)
        return b

    def recvfrom(self, byte_count, flags=0):
        if self.socket.type == SOCK_STREAM:
            return self.recv(byte_count), None

        # recvfrom() must not concatenate two or more packets.
        # Each call should return the first 'byteCount' part of the packet.
        (data, address) = self.recv_channel.receive()
        return data[:byte_count], address

    def recv_into(self, buffer, nbytes=0, flags=0):
        logger.debug("recv_into: buflen: %s, nbytes: %s" % (len(buffer), nbytes))
        if len(buffer):
            nbytes = min(len(buffer), nbytes)

        # recv() must not concatenate two or more data fragments sent with
        # send() on the remote side. Single fragment sent with single send()
        # call should be split into strings of length less than or equal
        # to 'byteCount', and returned by one or more recv() calls.

        remaining_bytes = self.read_index != len(self.read_bytes)
        # TODO: Verify this connectivity behaviour.

        if not self.connected:
            # Sockets which have never been connected do this.
            if not self.was_connected:
                raise error(10057, 'Socket is not connected')

            # Sockets which were connected, but no longer are, use
            # up the remaining input.  Observed this with urllib.urlopen
            # where it closes the socket and then allows the caller to
            # use a file to access the body of the web page.
        elif not remaining_bytes:
            self.read_bytes = self.recv_channel.receive()
            self.read_index = 0
            remaining_bytes = len(self.read_bytes)

        if nbytes == 0:
            nbytes = len(self.read_bytes)
            if len(buffer):
                nbytes = min(len(buffer), nbytes)
            if nbytes == 0:
                return 0

        if nbytes == 1 and remaining_bytes:
            buffer[:1] = self.read_bytes[self.read_index]
            self.read_index += 1
            return 1

        if self.read_index == 0 and nbytes >= len(self.read_bytes):
            nbytes = len(self.read_bytes)
            buffer[:nbytes] = self.read_bytes
            self.read_bytes = bytearray()
            return nbytes

        idx = self.read_index + nbytes
        buffer[:] = self.read_bytes[self.read_index:idx]
        self.read_bytes = self.read_bytes[idx:]
        self.read_index = 0
        return nbytes

    def close(self):
        logger.debug("Closing %s (%s)" % (self._fileno, self.fileno()))
        if self._fileno is None:
            return

        asyncore.dispatcher.close(self)

        self.connected = False
        self.accepting = False
        self.send_buffer = None  # breaks the loop in sendall

        # Clear out all the channels with relevant errors.
        while self.accept_channel and self.accept_channel.balance < 0:
            self.accept_channel.send_exception(error, 9, 'Bad file descriptor')
        while self.connect_channel and self.connect_channel.balance < 0:
            self.connect_channel.send_exception(error, 10061, 'Connection refused')
        while self.recv_channel and self.recv_channel.balance < 0:
            # The closing of a socket is indicted by receiving nothing.  The
            # exception would have been sent if the server was killed, rather
            # than closed down gracefully.
            self.recv_channel.send(bytearray())
            # self.recv_channel.send_exception(error, 10054, 'Connection reset by peer')

    # asyncore doesn't support this.  Why not?
    def fileno(self):
        return self.socket.fileno()

    def handle_accept(self):
        if self.accept_channel and self.accept_channel.balance < 0:
            t = asyncore.dispatcher.accept(self)
            if t is None:
                return
            (current_socket, client_address) = t
            current_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
            current_socket.wasConnected = True
            stackless.tasklet(self.accept_channel.send)((current_socket, client_address))

    # Inform the blocked connect call that the connection has been made.
    def handle_connect(self):
        if self.socket.type != SOCK_DGRAM:
            if not self.connect_channel:
                self.connect_channel = stackless.channel()
                self.connect_channel.preference = 1

            self.was_connected = True
            stackless.tasklet(self.connect_channel.send)(None)

    # Asyncore says its done but self.readBuffer may be non-empty
    # so can't close yet.  Do nothing and let 'recv' trigger the close.
    def handle_close(self):
        pass

    # Some error, just close the channel and let that raise errors to
    # blocked calls.
    def handle_expt(self):
        self.close()

    def handle_read(self):
        try:
            if self.socket.type == SOCK_DGRAM:
                ret = self.socket.recvfrom(20000)
            else:
                ret = asyncore.dispatcher.recv(self, 20000)
                # Not sure this is correct, but it seems to give the
                # right behaviour.  Namely removing the socket from
                # asyncore.
                if not ret:
                    self.close()

            # Do not block.
            if self.recv_channel.balance < 0:
                # The channel prefers the sender.  This means if there are waiting
                # receivers, the first will be scheduled with the given data.
                self.recv_channel.send(ret)
            else:
                # No waiting receivers.  The send needs to block in a tasklet.
                stackless.tasklet(self.recv_channel.send)(ret)
        except stdsocket.error as err:
            # If there's a read error assume the connection is
            # broken and drop any pending output
            if self.send_buffer:
                self.send_buffer = bytearray()
            self.recv_channel.send_exception(stdsocket.error, err)

    def handle_write(self):
        if len(self.send_buffer):
            sent_bytes = asyncore.dispatcher.send(self, self.send_buffer[:512])
            self.send_buffer = self.send_buffer[sent_bytes:]
        elif len(self.send_to_buffers):
            (data, address, channel, old_sent_bytes) = self.send_to_buffers[0]
            sent_bytes = self.socket.sendto(data, 0, address)
            total_sent_bytes = old_sent_bytes + sent_bytes
            if len(data) > sent_bytes:
                self.send_to_buffers[0] = data[sent_bytes:], address, channel, total_sent_bytes
            else:
                del self.send_to_buffers[0]
                stackless.tasklet(channel.send)(total_sent_bytes)
