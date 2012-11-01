# -*- coding: utf-8 -*-

import unittest
import persistent
import transaction
from ZODB.POSException import ConflictError
from Products.ConflictErrorLogger.tests.base import TestBase
from Products.ConflictErrorLogger.monitor import MSG_OBJ_EDITING
from Products.ConflictErrorLogger.monitor import MSG_OBJ_ALREADY_EDITED
from Products.ConflictErrorLogger.monitor import MSG_OBJ_CONFLICT_DETECTED
from Products.ConflictErrorLogger.monitor import MSG_OBJ_CONFLICT
from Products.ConflictErrorLogger.monitor import ConflictErrorPreview

class testConflictErrorLogger(TestBase):

    def test_NoConflict(self):
        """ Test if there is no messages if no conflict.
        """
        self.configureCE( 
                    CELogger_FIRST_CHANGE_ONLY=True,
                    CELogger_RAISE_CONFLICTERRORPREVIEW=False,
                    CELogger_ACTIVE= True)

        # TEST - No conlict
        # First edit and commit A
        p_ConnA = self.conn_A.root()['p'] 
        p_ConnA.inc()
        self.assertEqual(p_ConnA.value, 1)
        self.tm_A.commit()
        
        # And than edit B and commit B
        self.tm_B.begin() #sync DB
        p_ConnB = self.conn_B.root()['p'] 
        self.assertEqual(p_ConnB.value, 1)
        p_ConnB.inc()
        self.assertEqual(p_ConnB.value, 2)
        self.tm_B.commit()
        self.assertEqual(p_ConnB.value, 2)
        # Check if no information in the logs
        assert(MSG_OBJ_CONFLICT not in self.getLog())

    def test_SimpleConflict(self):
        self.configureCE( 
                    CELogger_FIRST_CHANGE_ONLY=True,
                    CELogger_RAISE_CONFLICTERRORPREVIEW=False,
                    CELogger_ACTIVE= True)
        # First edit A 
        p_ConnA = self.conn_A.root()['p'] 
        p_ConnA.inc()

        # And than edit B
        self.tm_B.begin() #sync DB
        p_ConnB = self.conn_B.root()['p'] 
        p_ConnB.inc()

        # in this point a conflict must to be detected, because 2 connections 
        # are changing the same object at the same time
        log = self.getLog()
        self.assertTrue(MSG_OBJ_ALREADY_EDITED in log)
        # But there is no conflict yet 
        self.assertTrue(MSG_OBJ_CONFLICT not in log)

        # commit the changes
        self.tm_B.commit()
        try:
            self.tm_A.commit()
        except ConflictError:
            pass

        log = self.getLog(continue_from_here=log)
        # Now the conflict traceback is in the log
        assert(MSG_OBJ_CONFLICT in log)
        # And also the origin of this conflict (source-code) 
        assert("p_ConnA.inc()" in log)

    def test_MultipleConflict(self):
        self.configureCE( 
                    CELogger_FIRST_CHANGE_ONLY=True,
                    CELogger_RAISE_CONFLICTERRORPREVIEW=False,
                    CELogger_ACTIVE= True)
        # First edit A 

        p_ConnA = self.conn_A.root()['p'] 
        p_ConnA.inc()

        # And than edit B
        self.tm_B.begin() #sync DB
        p_ConnB = self.conn_B.root()['p'] 
        p_ConnB.inc()
        
        # also edit C
        self.tm_C.begin() #sync DB
        p_ConnC = self.conn_C.root()['p'] 
        p_ConnC.inc()

        # commit the changes
        self.tm_B.commit()
        try:
            self.tm_A.commit()
        except ConflictError:
            pass

        log = self.getLog()
        
        # Now the conflict traceback is in the log
        self.assertTrue(MSG_OBJ_CONFLICT in log)
        # And also the origin of this conflict (source-code from traceback) 
        self.assertTrue("p_ConnA.inc()" in log)

    def test_ConflictErrorPreview(self):
        self.configureCE( 
                    CELogger_FIRST_CHANGE_ONLY=False,
                    CELogger_RAISE_CONFLICTERRORPREVIEW=True,
                    CELogger_ACTIVE= True)

        # First edit A 
        p_ConnA = self.conn_A.root()['p'] 
        p_ConnA.inc()

        # And than edit B
        self.tm_B.begin() #sync DB
        p_ConnB = self.conn_B.root()['p'] 

        # in this point a conflict must to be detected, and the 
        # "CONFLICTERRORPREVIEW" will be raised
        self.assertRaises(ConflictErrorPreview, p_ConnB.inc)

    def test_Various(self):
        self.configureCE( 
                    CELogger_FIRST_CHANGE_ONLY=False,
                    CELogger_RAISE_CONFLICTERRORPREVIEW=False,
                    CELogger_ACTIVE= True)
        # First edit A 

        p_ConnA = self.conn_A.root()['p'] 
        p_ConnA.inc()

        # And than edit B
        self.tm_B.begin() #sync DB
        p_ConnB = self.conn_B.root()['p'] 
        p_ConnB.inc()
        
        # also edit C
        self.tm_C.begin() #sync DB
        p_ConnC = self.conn_C.root()['p'] 
        p_ConnC.inc()

        # commit the changes
        self.tm_B.commit()
        try:
            self.tm_A.commit()
        except ConflictError:
            pass

        log = self.getLog()
        
        # Now the conflict traceback is in the log
        self.assertTrue(MSG_OBJ_CONFLICT in log)
        # And also the origin of this conflict (source-code from traceback) 
        self.assertTrue("p_ConnA.inc()" in log)

def test_suite():
    return unittest.TestSuite((
         unittest.makeSuite(testConflictErrorLogger),
    ))
