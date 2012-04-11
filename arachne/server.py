#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""servers."""

import logging
import traceback
from uuid import uuid4
from time import time, mktime
from functools import wraps

import gevent
from gevent.wsgi import WSGIServer, WSGIHandler
from arachne.http import HttpError, CacheHit
from arachne.conf import settings
from arachne.utils import argspec, Heap
from arachne import amqp

import traceback

class CustomHandler(WSGIHandler):
    logger = logging.getLogger("wsgi")
    def log_request(self, *args):
        self.logger.info(self.format_request())

    def log_error(self, msg, *args):
        try:
            message = msg % args
        except Exception:
            self.logger.error(traceback.format_exc())
            message = "%r %r" % (msg, args)
        self.logger.error(message)

def autospawn(func):
    @wraps(func)
    def wrapper(self, *a, **kw):
        self.greenlets.append(gevent.spawn(func, self, *a, **kw))
    return wrapper

logger = logging.getLogger(__name__)

class Server(object):
    def __init__(self, *a, **kw):
        settings.server = self
        self.proxy = None
        self.greenlets = []

    def run_method(self, method, **args):
        """Runs a method with some arguments, catching all manner of error
        conditions and logging them appropriately"""
        try:
            return method(**args)
        except TypeError, e:
            if "takes" in e.message and "arguments" in e.message:
                return "%s\nargspec: %s.%s\n" % (traceback.format_exc(), method.plugin.plugin_name, argspec(method))
            return traceback.format_exc()
        except HttpError, e:
            message = "%s Cancelled %s/%s" % (e.message, method.im_self.plugin_name, method.__name__)
            logger.warning(message)
            return message
        except CacheHit, e:
            logger.info("Cache Hit: %s" % e.message)
            return ""
        except Exception, e:
            return traceback.format_exc()

    def serve(self, port, app, block=False):
        server = WSGIServer(('', port), app)
        server.handler_class = CustomHandler
        if not block:
            self.greenlets.append(gevent.spawn(server.serve_forever))
        else:
            server.serve_forever()

class QueueServer(Server):
    def start(self):
        self.queue = amqp.Amqp()
        self.state = "initializing"
        self.serve(self.port, self.app)
        self.update_queue_status(self.queue)
        self.run()

    @autospawn
    def update_queue_status(self, queue):
        while 1:
            self.queue_status = queue.status()
            gevent.sleep(10)

    def run(self):
        """Subclass and implement a scheduler that puts jobs on self.queue."""
        self.state = "running"
        while 1: gevent.sleep(1)


class SchedulerServer(QueueServer):
    def __init__(self, port=settings.port, plugins=[], debug=False, app=None):
        super(SchedulerServer, self).__init__()
        self.port = port
        self.state = "stopped"
        self.plugins = [p() for p in plugins]
        self.app = app
        self.jobheap = Heap()


class WorkerServer(QueueServer):
    def __init__(self, port=settings.port, plugins=[], debug=False, app=None):
        super(WorkerServer, self).__init__()
        self.port = port
        self.state = "stopped"
        self.plugins = [p() for p in plugins]
        self.app = app


class InterfaceServer(Server):
    def __init__(self, port=settings.port, plugins=[], debug=False):
        super(InterfaceServer, self).__init__()
        self.plugins = [p() for p in plugins]
        self.port = port

    def start(self):
        from arachne.web import interface
        from arachne.cassandra import Cassandra
        self.datastore = Cassandra()
        self.serve(self.port, interface.app, True)

    def run_method(self, method, **args):
        """Run a method and save its results to the datastore.  Returns either
        a string (on failures) or a dict to be sent to the client."""
        user_id = args.get('site_user_id', args.get('user_id', None))
        result = super(InterfaceServer, self).run_method(method, **args)
        # XXX: is this really enough of a "success" condition?
        if user_id and isinstance(result, (dict, list)):
            uuid = uuid4().hex
            self.datastore.set(user_id, result, uuid)
            return {uuid: result}
        return result



