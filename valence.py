#!/usr/bin/env python3.4
# -*- coding: utf-8 -*-

import asyncio
import os
import sys
import json
import logging
import traceback
import paho.mqtt.client as mqtt
from queue import Queue

object_registry = {}
callback_registry = {}
last_object_id = 0
last_callback_id = 0

electron_exec = os.path.join(os.path.dirname(__file__),
        'vendor/electron-v0.25.2-darwin-x64/Electron.app/Contents/MacOS/Electron')

valence_app = os.path.join(os.path.dirname(__file__), 'vendor/app')

process = None
window = None
url_q = Queue()

def mqtt_loop():
    global url_q
    # The callback for when the client receives a CONNACK response from the server.
    def on_connect(client, userdata, rc):
        print("Connected with result code "+str(rc))
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        client.subscribe("urongo/open")

    # The callback for when a PUBLISH message is received from the server.
    def on_message(client, userdata, msg):
        logging.debug(msg.topic+" "+str(msg.payload))
        url_q.put(msg.payload)

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect("c-beam", 1883, 60)

    # Blocking call that processes network traffic, dispatches callbacks and
    # handles reconnecting.
    # Other loop*() functions are available that give a threaded interface and a
    # manual interface.
    client.loop_forever()


def create_object_id():
    global last_object_id
    last_object_id += 1
    return last_object_id

def create_callback_id():
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
        self.callbacks = {}
        object_registry[self.id] = self

    @asyncio.coroutine
    def new(self, *args, **kwargs):
        resulting_obj = RemoteObject('new_window', self.process)
        call = generate_remote_call('new', self.id, resulting_obj.id, **kwargs)
        yield from send_call(call, self.process)
        return resulting_obj

    @asyncio.coroutine
    def call(self, method, *args, **kwargs):
        resulting_obj = RemoteObject('{}()'.format(method), self.process)
        call = generate_remote_call(method, self.id, resulting_obj.id, *args, **kwargs)

        yield from send_call(call, self.process)
        return resulting_obj

    @asyncio.coroutine
    def on(self, event_name, callback_func):
        resulting_obj = RemoteObject('on({})'.format(event_name), self.process)
        call = generate_remote_call('on', self.id, resulting_obj.id, 'ready', None)
        callback_id = create_callback_id()
        callback_registry[callback_id] = callback_func
        call['args_cb'] = [[1, callback_id]]
        yield from send_call(call, self.process)
        return resulting_obj

    @asyncio.coroutine
    def destroy(self):
        call = {'cmd': 'destroy', 'obj': str(self.id)}
        yield from send_call(call, self.process)

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
def read_stuff(process):
    while True:
        try:
            data = yield from process.stdout.readline()
            stuff = data.decode('utf-8').rstrip()
            logging.debug('+++ got stuff: {}'.format(stuff))
            if len(stuff) < 1:
                return
            try:
                bla = json.loads(stuff)
                logging.debug("+++ got valid json")
                if bla['cmd'] == 'cb':
                    callback_func = callback_registry[bla['cb']]
                    yield from callback_func(*bla['args'])
            except Exception as e:
                logging.debug(e)
        except:
            return

@asyncio.coroutine
def on_app_ready(args):
    global process, window
    logging.debug('App is ready')
    browser_window =  yield from require('browser-window', process)
    window = yield from browser_window.new(width=1000, height=600, title='MQTT electron shell')
    yield from window.call('loadUrl', "data:text/html,Waiting for MQTT messages ...")

@asyncio.coroutine
def url_loop():
    global window, url_q
    while True:
        url = url_q.get()
        yield from window.call('loadUrl', url.decode('utf-8'))
        yield from asyncio.sleep(5.0)

@asyncio.coroutine
def run_process():
    global process
    process = yield from asyncio.create_subprocess_exec(*[electron_exec, valence_app],
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT)
    asyncio.async(read_stuff(process))
    try:
        app = yield from require('app', process)
        cb = yield from app.on('ready', on_app_ready)
        yield from asyncio.sleep(1.0)

        yield from cb.destroy()
        yield from app.destroy()
        asyncio.async(url_loop())

    finally:
        pass 
        # process.terminate()


if __name__ == '__main__':
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

    loop = asyncio.get_event_loop()
    asyncio.async(run_process())
    loop.run_in_executor(None, mqtt_loop)
    loop.run_forever()



