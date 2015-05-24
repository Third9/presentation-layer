#!/usr/bin/env python3.4
# -*- coding: utf-8 -*-

import asyncio
import os
import sys
import json
import logging
import traceback

object_registry = {}
last_object_id = 0

electron_exec = os.path.join(os.path.dirname(__file__),
        'vendor/electron-v0.25.2-darwin-x64/Electron.app/Contents/MacOS/Electron')

valence_app = os.path.join(os.path.dirname(__file__), 'vendor/app')

def create_object_id():
    global last_object_id
    last_object_id += 1
    return last_object_id

def generate_remote_call(method_name, obj_id, save_id, *args, **kwargs):
    remote_call = {
        'cmd': 'call',
        'method': method_name,
        'obj': str(obj_id),
        'save': str(save_id),
        'args': []
    }
    if len(args) > 0:
        remote_call['args'] += args
    if len(kwargs.items()) > 0:
        remote_call['args'].append(kwargs)
    return remote_call

@asyncio.coroutine
def send_call(call, process):
    msg = json.dumps(call, sort_keys=True).encode('utf-8') + b'\n'
    logging.debug(msg)
    process.stdin.write(msg)
    yield from process.stdin.drain()


class RemoteObject(object):
    def __init__(self, name="RemoteObject", process=None):
        global object_registry
        self.name = name
        self.id = create_object_id()
        self.process = process
        object_registry[self.id] = self

    @asyncio.coroutine
    def new(self, *args, **kwargs):
        resulting_obj = RemoteObject('new_window', self.process)
        call = generate_remote_call('new', self.id, resulting_obj.id, **kwargs)
        yield from send_call(call, self.process)
        return resulting_obj

    def call(self, method, *args, **kwargs):
        resulting_obj = RemoteObject('{}()'.format(method), self.process)
        call = generate_remote_call(method, self.id, resulting_obj.id, *args, **kwargs)

        yield from send_call(call, self.process)
        return resulting_obj


    def __str__(self):
        return '{} [{}]'.format(self.name, self.id)

@asyncio.coroutine
def require(name, process):
    remote_obj = RemoteObject(name=name, process=process)
    remote_call = {
        "cmd" : "call",
        "method" : "require",
        "args" : [name],
        "save" : str(remote_obj.id)
    }
    yield from send_call(remote_call, process)
    return remote_obj

@asyncio.coroutine
def run_process():
    process = yield from asyncio.create_subprocess_exec(*[electron_exec, valence_app],
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT)
    try:
        yield from asyncio.sleep(1.0)
        app = yield from require('app', process)
        browser_window = yield from require('browser-window', process)
        window = yield from browser_window.new(width=1000, height=600, title='My App')
        yield from window.call('loadUrl', "data:text/html,Hello World!")

        yield from asyncio.sleep(2.0)
    finally:
        process.terminate()



@asyncio.coroutine
def test_comm():
    process = yield from asyncio.create_subprocess_exec(*['ls', '-l'],
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)
    bla =  yield from process.stdout.read()# communicate()
    logging.debug('{} / {}'.format(bla, ''))

if __name__ == '__main__':
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(run_process())



