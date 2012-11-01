# -*- coding: utf-8 -*-

import os
import logging
import thread

from App.config import getConfiguration
from ZODB.utils import p64, u64, tid_repr
from ZODB.Connection import Connection
from ZODB.POSException import ConflictError
from Products.ConflictErrorLogger.monitor import ConflictLogger
from Products.ConflictErrorLogger.dumper import do_enable

lock = thread.allocate_lock()
_enabled = []
conflictLogger = None

def AlreadyApplied(patch):
    if patch in _enabled:
        return True
    _enabled.append(patch)
    return False

if not AlreadyApplied('ConflictLogger.__init__'):
    ACTIVE=os.environ.get('CELogger_ACTIVE', True)
    LOGFILE=os.environ.get('CELogger_LOGFILE', '')
    FIRST_CHANGE_ONLY=os.environ.get('CELogger_FIRST_CHANGE_ONLY', True)
    RAISE_CONFLICTERRORPREVIEW=os.environ.get(
                                'CELogger_RAISE_CONFLICTERRORPREVIEW', False)

    if LOGFILE:
        log = do_enable(LOGFILE)
    else:
        log = logging.getLogger("CELogger")
    config = getConfiguration()
    if not config.debug_mode:
        log.critical("Attention: You are not running in debug-mode. "
                     "Do not use Products.ConflictErrorLogger for "
                     "Productive systems!")

    if (not LOGFILE) and (log.level > logging.WARNING):
        log.critical("Set the 'LOG_LEVEL' to 'WARNING' or use the "
                     "'CELogger_LOGFILE' option in order to get the messages "
                     "properly")

    log.warning("Please, be warned that 'Products.ConflictErrorLogger' will "
                "not work properly with more than 1 instance (ZEO).")

    conflictLogger = ConflictLogger()
    conflictLogger.config(
                        log,
                        FIRST_CHANGE_ONLY=FIRST_CHANGE_ONLY,
                        RAISE_CONFLICTERRORPREVIEW=RAISE_CONFLICTERRORPREVIEW)

def doConnectionMonkeyPatch():
    if AlreadyApplied('ZODB.Connection.register'):
        return

    Connection.ORIG_register = Connection.register
    def new_register(self, obj):
        lock.acquire()
        try:
            conflictLogger.notify_register(self, obj)
            return self.ORIG_register(obj)
        finally:
            lock.release()
    Connection.register = new_register

def doConflictErrorMonkeyPatch():
    if AlreadyApplied('ZODB.POSException.ConflictError'):
        return

    ConflictError.__ORIG_init__ = ConflictError.__init__
    def __NEW_init__(self, message=None, object=None, oid=None, serials=None,
                 data=None):
        lock.acquire()
        try:
            ret = self.__ORIG_init__(message, object, oid, serials, data)
            conflictLogger.notify_ConflictError(self, message, object, oid, serials, data)
            return ret
        finally:
            lock.release()
    ConflictError.__init__ = __NEW_init__

doConnectionMonkeyPatch()
doConflictErrorMonkeyPatch()
