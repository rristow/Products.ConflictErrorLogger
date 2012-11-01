# -*- coding: utf-8 -*-

import os
import traceback
import logging
import time
import thread
from ZODB.utils import p64, u64, tid_repr
from ZODB.Connection import Connection
from ZODB.POSException import TransactionError

MSG_OBJ_EDITING = "Start editing the object."
MSG_OBJ_CONTINUE_EDITING = "Continuing to edit the object."
MSG_OBJ_ALREADY_EDITED = "The object is already been edited."
MSG_OBJ_CONFLICT_DETECTED = "A potential conflictError was detected for this object."
MSG_OBJ_CONFLICT = "A ConflictError is been raised for the object."
TRACEBACK_SEP = "\n============\n"

class ConflictErrorPreview(TransactionError):
    """ A "possible" transaction error was detected. (One second threads start
    to edit the same object).
    """

class ConflictLogger(object):
    obj_pool = {}
    log = None
    is_active = True

    def config(self, 
                 log,
                 FIRST_CHANGE_ONLY=True, 
                 RAISE_CONFLICTERRORPREVIEW=False):

        self.log = log
        # Do not cache all changes in the object, just the first conflict detection
        self.FIRST_CHANGE_ONLY = FIRST_CHANGE_ONLY
        # Raise an exception when a conflict error is detected
        self.RAISE_CONFLICTERRORPREVIEW = RAISE_CONFLICTERRORPREVIEW

    def frm(self,msg,thread=None,connection=None, obj=None, traceback=None):
        """ Format the message to the log.
        """
        msg_h = ["time: %s"%time.strftime('%H:%M:%S')]
        if  thread:
            msg_h.append("thread: %s"%thread.get_ident())
        if  connection:
            msg_h.append("connection: %s"%connection)
        if  obj:
            oid = obj._p_oid
            oid_str = tid_repr(oid)
            msg_h.append("object._p_oid: %s"%oid_str)
            msg_h.append("object.to_string: %s"%obj)

        msg = "[%s]: %s"%(", ".join(msg_h), msg)

        if traceback:
            msg += ">>>>>>>>\n%s\n<<<<<<<<"%traceback
        return msg

    def appendLog(self, msg, level=logging.WARNING, thread=None, 
                 connection=None, obj=None, traceback=None):
        """ Append a message to the log.
        """
        msg = self.frm(msg, thread,connection, obj, traceback)
        self.log.log(level, msg)

    def get_traceback(self):
        """ Get the traceback (string)
        """
        return "".join(traceback.format_stack())

    def objpool_add(self, actual_conn, actual_obj, traceback):
        """ Add an object and connection to the pool
        """
        # Get connections pool 
        poid = actual_obj._p_oid
        if poid in self.obj_pool.keys():
            connections_pool = self.obj_pool[poid]
        else:
            connections_pool = {}
            self.appendLog("objpool_add, added: %s, %s"%(actual_obj, tid_repr(poid)), level=logging.DEBUG)
            self.obj_pool[poid] = connections_pool

        # The object is already been edit in ...
        if connections_pool.keys():

            if actual_conn in connections_pool.keys():
                # ... this connection
                if not self.FIRST_CHANGE_ONLY:
                    self.appendLog(MSG_OBJ_CONTINUE_EDITING, level=logging.DEBUG, connection=actual_conn, obj=actual_obj)
                    tb_info = self.frm(MSG_OBJ_CONTINUE_EDITING)
                    connections_pool[actual_conn] += "\n%s traceback:\n%s"%(tb_info,traceback)
                    return True
            else:
                # ... another connection
                self.appendLog(MSG_OBJ_ALREADY_EDITED, level=logging.DEBUG, connection=actual_conn, obj=actual_obj)
                tb_info = self.frm(MSG_OBJ_ALREADY_EDITED, connection=actual_conn, obj=actual_obj)
                connections_pool[actual_conn] = "%s traceback:\n%s"%(tb_info ,traceback)
                return True
        else:
            # The object start to is already been edit in ..
            self.appendLog(MSG_OBJ_EDITING, level=logging.DEBUG, connection=actual_conn, obj=actual_obj)
            tb_info = self.frm(MSG_OBJ_EDITING, connection=actual_conn, obj=actual_obj)
            connections_pool[actual_conn] = "%s traceback:\n%s"%(tb_info ,traceback)
            return True

    def search_conflicting_data(self, actual_conn, actual_obj):
        """ Search for an conflicting data (not the actual_conn) in the pool
        """
        poid = actual_obj._p_oid
        result_tb=[]

        # Check if ZODB is changing this object
        if poid in self.obj_pool.keys():
            connections_pool = self.obj_pool[poid]
        else:
            connections_pool = {}
            self.obj_pool[poid] = connections_pool

        # Get traceback pool 
        for conn in connections_pool.keys():
            # just get the data from other connections
            if conn != actual_conn:
                result_tb.append(connections_pool[conn])
        return TRACEBACK_SEP.join(result_tb)

    def sanitize_cache(self):
        """ Remove the obj_pool if no more references
        """
        # Remove connections from pool
        for poid, connections_pool in self.obj_pool.items():
            conn_todel =  []
            for conn in connections_pool:
                registered_obj_oids = [o._p_oid for o in conn._registered_objects]
                if poid not in registered_obj_oids:
                    conn_todel.append(conn)

            # Removed objects 
            for conn in conn_todel:
                self.appendLog("sanitize_cache, Removed connection: %s"%conn, level=logging.DEBUG)
                self.obj_pool[poid].pop(conn)

        # find objects with no information 
        obj_todel =  []
        for poid, connections_pool in self.obj_pool.items():
            if not connections_pool:
                obj_todel.append(poid)

        # Removed objects 
        for poid in obj_todel:
            self.appendLog("sanitize_cache, Removed object: %s"%tid_repr(poid), level=logging.DEBUG)
            self.obj_pool.pop(poid)

    def check_alreadychanged_obj(self, actual_conn, actual_obj):
        """ Check in the connection if the object is been edited
        """
        registered_obj_oids = []
        poid = actual_obj._p_oid
        # Get all objects been edited
        if poid in self.obj_pool.keys():
            connections_pool = self.obj_pool[poid]
            
            # Get traceback pool 
            for conn in connections_pool.keys():
                # just get the data from other connections
                if conn != actual_conn:
                    objs = [o._p_oid for o in conn._registered_objects]
                    registered_obj_oids += objs
        return poid in registered_obj_oids

#------------------------------------------------------------------------------
#   Notifications from ZODB

    def notify_register(self, actual_conn, actual_obj):
        """ Some objective is been edited in ZODB.
        """
        if os.environ.get('CELogger_ACTIVE', True):
            # restarting
            if not self.is_active:
                self.obj_pool = {}
            self.is_active = True
        else:
            self.is_active = False
            return

        traceback = self.get_traceback()
        raise_exception = False
        if actual_conn and self.check_alreadychanged_obj(actual_conn, actual_obj):
            self.appendLog(MSG_OBJ_CONFLICT_DETECTED, thread=thread, connection=actual_conn, obj=actual_obj)

            if self.RAISE_CONFLICTERRORPREVIEW:
                raise_exception = True

        # Remove old refs
        self.sanitize_cache()

        #tb_info = self.frm(MSG_OBJ_EDITING, thread=thread, connection=actual_conn, obj=actual_obj)
        #self.objpool_add(actual_conn, actual_obj, "%s Traceback:\n%s"%(tb_info,traceback))
        self.objpool_add(actual_conn, actual_obj, traceback)

        if raise_exception:
            raise ConflictErrorPreview("A potential conflictError was "
                                       "detected. Check log for details.")

    def notify_ConflictError(self, conflict_error_exc, message=None, 
            pobject=None, oid=None, serials=None, data=None):
        """ A ConflictError is been raised.
        """
        if not os.environ.get('CELogger_ACTIVE', True):
            return

        conflict_trace = self.search_conflicting_data(None, pobject)

        if conflict_trace:
            self.appendLog("%s This object was initially changed here (traceback):\n"%MSG_OBJ_CONFLICT, thread=thread, obj=pobject, traceback=conflict_trace)
        else:
            self.appendLog("%s There is no traceback info.\n"%MSG_OBJ_CONFLICT, thread=thread, obj=pobject)

        # If logging in another file, append also the actual traceback.
        if self.log.name == "CELogger":
            self.log.exception(conflict_error_exc)
            self.log.error(self.get_traceback())
