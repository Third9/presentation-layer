#!/usr/bin/env python3.4
# -*- coding: utf-8 -*-
import os
import logging
import pythrust
import asyncio
import json
import paho.mqtt.client as paho
import websockets
import queue

mqtt_server = "c-beam.cbrp3.c-base.org"

logging.basicConfig(level=logging.DEBUG)

loop = asyncio.get_event_loop()

q = queue.Queue()
qq = asyncio.Queue()

mqtt_client_id = "urongo-luakit"
mqtt_client_name = "urongo"
mqtt_client_password = ""
mqtt_server_tls = False

window = None

def mqtt_connect(client):
    try:
        client.username_pw_set(mqtt_client_name, password=mqtt_client_password)
        if mqtt_server_tls:
            print(client.tls_set(config.mqtt_server_cert, cert_reqs=ssl.CERT_OPTIONAL))
            print(client.connect(mqtt_server, port=1884))
        else:
            print( client.connect(mqtt_server) )
        client.subscribe("+/+", 1)
        client.on_message = on_message
    except Exception as e: print(e)

def on_message(m, obj, msg):
    global last_change
    if msg.topic == "{}/open".format(mqtt_client_name):
        # last_change = datetime.now()
        print('luakit {}'.format(msg.payload))
        q.put(msg.payload)
    if msg.topic == 'user/boarding':
        # last_change = datetime.now()
        try:
            data = json.loads(msg.payload)
            print('luakit https://c-beam.cbrp3.c-base.org/welcome/{}'.format(data['user']))
        except:
            pass
    else:
        if window is not None:
           asyncio.async(window.remote(msg.payload))
        # print('message in {}: {}'.format(msg.topic, msg.payload))
    
@asyncio.coroutine
def mqtt_loop():
    global last_change
    client = paho.Client(mqtt_client_id)
    mqtt_connect(client)
    while True:
        result = client.loop(1)
        if result != 0:
            mqtt_connect(client)
        yield from asyncio.sleep(1)
        
        
@asyncio.coroutine
def produce():
    while True:
        yield from asyncio.sleep(1)
        if not q.empty():
            yield from qq.put(q.get())

@asyncio.coroutine
def hello(websocket, path):
    print("CONNECTED ###########################")
    yield from websocket.send("Hallo!")
    while True:
        url = yield from qq.get()
        print("got url {} ###########################".format(url))
        yield from websocket.send('{}'.format(url.decode('utf-8')))
    
def on_close(event):
    print("MainWindow closed.")
    loop.stop()
    loop.close()

def main():
    api = pythrust.API(loop)

    asyncio.async(api.spawn())

    ROOT_FOLDER = os.path.abspath(os.path.dirname(__file__))
    window = api.window({'root_url': 'file://%s/index.html' % ROOT_FOLDER})   
    window.on('closed', on_close)
    asyncio.async(window.set_kiosk(True))
    # asyncio.async(window.open_devtools())
    asyncio.async(window.show())
    asyncio.async(window.focus())
    asyncio.async(mqtt_loop())
    asyncio.async(window.set_fullscreen(True))
    loop.run_until_complete(websockets.serve(hello, 'localhost', 8765))
    asyncio.Task(produce())
    loop.run_forever()

if __name__ == '__main__':
    main()
