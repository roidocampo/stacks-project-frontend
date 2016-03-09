#!/usr/bin/env python

import os.path
import subprocess

class NodeSlave:

    _singleton = None

    @classmethod
    def get(cls):
        if cls._singleton is None:
            cls._singleton = cls()
        return cls._singleton

    def __init__(self):
        self._script = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            "katexfilter.js")
        self._command = [ "node", self._script ]
        self._proc = subprocess.Popen(self._command,
                                      stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT)

    def process(self, tex):
        tex = tex.replace("\n", " ").strip() + "\r\n"
        self._proc.stdin.write(tex)
        katex = self._proc.stdout.readline().strip()
        return katex

def process(tex):
    slave = NodeSlave.get()
    return slave.process(tex)

