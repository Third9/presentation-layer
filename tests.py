#!/usr/bin/env python3.4
# -*- coding: utf-8 -*-

import asyncio
import unittest
import unittest.mock
import io
import sys
import json
import logging
import valence

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)


class TestValence(unittest.TestCase):
    
    def test_create_object_id(self):
        self.assertEqual(valence.create_object_id(), 1)

    def test_require(self):
        last_id = valence.create_object_id()
        should_be = json.dumps({
            "args" : ["app"],
            "cmd" : "call",
            "method" : "require",
            "save" : str(last_id + 1)}, sort_keys=True)
        process = unittest.mock.Mock()
        process.communicate = unittest.mock.MagicMock()
        obj = valence.require('app', process)
        process.communicate.assert_called_with(should_be)
        self.assertEqual(obj.id, last_id + 1)

    def test_new(self):
        process = unittest.mock.Mock()
        process.communicate = unittest.mock.MagicMock()
        obj = valence.require('browser-window', process)
        obj.new(1000, 600, "My App")
        logging.debug( process.communicate.call_args_list[1] )
        called_with = json.loads(process.communicate.call_args_list[1][0][0])
        self.assertEqual(called_with['args'], [{
            "height": 600,
                "title": "My App",
                "width": 1000
        }])

    def test_run_process(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(valence.run_process())

    def test_generate_remote_call(self):
        result = valence.generate_remote_call('new', 1, 2)
        self.assertEqual(result['method'], 'new')
        self.assertEqual(result['obj'], '1')
        self.assertEqual(result['save'], '2')

    
if __name__ == '__main__':
    unittest.main()