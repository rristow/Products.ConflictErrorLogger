# -*- coding: utf-8 -*-
# Based on: Products.LongRequestLogger.dumper.py
import Signals.Signals
import ZConfig.components.logger.loghandler
import ZServer.BaseLogger
import logging
import os.path

try:
    from signal import SIGUSR2
except ImportError:
    # Windows doesn't have these (but also doesn't care what the exact
    # numbers are)
    SIGUSR2 = 12

class NullHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        # for comparison purposes below
        self.baseFilename = 'null'

    def emit(self, *args, **kw):
        pass

log = logging.getLogger("CELogger")
#log.propagate = False
#handler = NullHandler()
#log.addHandler(handler)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

def do_enable(logfile):
    global handler
    # this function is not exactly thread-safe, but it shouldn't matter.
    # The worse that can happen is that a change in longrequestlogger_file
    # will stop or change the logging destination of an already running request

    rotate = None
    if logfile:
        log.propagate = False
        logfile = os.path.abspath(logfile)
        #log.removeHandler(handler)
        #handler.close()
        if os.name == 'nt':
            rotate = Signals.Signals.LogfileRotateHandler
            handler = ZConfig.components.logger.loghandler.Win32FileHandler(
                logfile)
        else:
            rotate = Signals.Signals.LogfileReopenHandler
            handler = ZConfig.components.logger.loghandler.FileHandler(
                logfile)
        handler.formatter = formatter
        log.addHandler(handler)

    # Register with Zope 2 signal handlers to support log rotation
    if rotate and Signals.Signals.SignalHandler:
        Signals.Signals.SignalHandler.registerHandler(
            SIGUSR2, rotate([handler]))
    return log # which is also True as boolean
