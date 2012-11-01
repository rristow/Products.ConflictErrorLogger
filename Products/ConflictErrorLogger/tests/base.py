# -*- coding: utf-8 -*-

import logging
import unittest
import os
import tempfile
import transaction
import ZODB
from ZODB.POSException import ConflictError
from ZODB.FileStorage import FileStorage
import transaction
from persistent import Persistent  

from Products.ConflictErrorLogger.patch import conflictLogger
from Products.ConflictErrorLogger.dumper import do_enable

def removeDirectory(wd):
    """ Remove the test directory and files
    """
    for f in os.listdir(wd):
        try:
            path = os.path.join(wd, f)
            os.remove(path)
        except OSError:
            pass
    os.rmdir(wd)

class PCounter(Persistent):
    """ Persistent test object.
    """
    _val = 0
    def inc(self):
        self._val += 1

    @property
    def value(self):
        return self._val


class TestBase(unittest.TestCase):
    loglist = []

    def setUp(self):
        """
        (based on ZODB.ConflictResolution.txt): Create the database for the 
        tests Set the databases. 
        Think of `conn_A` (connection A) as one thread, and `conn_B` 
        (connection B) as a concurrent thread.
        """

        self.testdir = tempfile.mkdtemp()
        self.storage = FileStorage(os.path.join(self.testdir,'Data.fs'))
        self.db = ZODB.DB(self.storage)

        self.tm_A = transaction.TransactionManager()
        self.conn_A = self.db.open(transaction_manager=self.tm_A)
        p_ConnA = self.conn_A.root()['p'] = PCounter()
        self.tm_A.commit()

        self.tm_B = transaction.TransactionManager()
        self.conn_B = self.db.open(transaction_manager=self.tm_B)
        p_ConnB = self.conn_B.root()['p']
        assert p_ConnA._p_oid == p_ConnB._p_oid

        self.tm_C = transaction.TransactionManager()
        self.conn_C = self.db.open(transaction_manager=self.tm_C)
        p_ConnC = self.conn_B.root()['p']
        assert p_ConnA._p_oid == p_ConnC._p_oid
 
    def tearDown(self):
        """ close and delete.
        """
        self.db.close()
        self.storage.close()
        removeDirectory(self.testdir)

    def getLog(self, continue_from_here=""):
        """ Read the log file.
        """
        self.logCE.handlers[0].flush()
        #f = open(self.logCE.handlers[0].baseFilename, "r")
        f = open(self.logfile, "r")
        text = f.read()
        f.close()
        return text[len(continue_from_here):]

    def configureCE(self, 
                    CELogger_LOGFILE='conflict_error_test.log',
                    CELogger_FIRST_CHANGE_ONLY=True,
                    CELogger_RAISE_CONFLICTERRORPREVIEW=False,
                    CELogger_ACTIVE= True):
        """ configure ClinflictErrorLooger
        """
        self.logfile = os.path.join(self.testdir,CELogger_LOGFILE)
        self.logCE = do_enable(self.logfile)
        self.logCE.level = logging.DEBUG
        conflictLogger.config(
                 log=self.logCE,
                 FIRST_CHANGE_ONLY=CELogger_FIRST_CHANGE_ONLY, 
                 RAISE_CONFLICTERRORPREVIEW=CELogger_RAISE_CONFLICTERRORPREVIEW)
