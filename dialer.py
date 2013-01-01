# -*- coding: utf-8 -*-
from __future__ import print_function

import logging
import os
import traceback

from commands import getstatusoutput as gso
from tempfile import NamedTemporaryFile
from contextlib import contextmanager
from subprocess import Popen

from gevent import Greenlet, sleep

_wvdial_reconnect_wait = 10

def modem_terminal():
    status, dmesg_out = gso("dmesg")
    if status != 0:
        raise Exception('dmesg returned ' + status)

    tty_lines = [line for line in dmesg_out.split('\n')
                 if 'GSM modem' in line]

    if len(tty_lines) == 0:
        raise Exception('No lines for GSM found in dmesg!')

    return sorted([line.split(' ')[-1] for line in tty_lines if 'tty' in line])[0]

def wvdial_config_string(terminal):
    return '''
[Dialer Defaults]
Init = AT+CGDCONT=1,"IP","internet.saunalahti"
Stupid Mode = 1
Modem Type = Analog Modem
ISDN = 0
Phone = *99#
Modem = /dev/%s
Username = { }
Password = { }
Baud = 9600
''' % terminal

@contextmanager
def wvdial_config():
    with NamedTemporaryFile(delete=False) as conf:
        print(wvdial_config_string(modem_terminal()), file=conf)
    yield conf.name
    os.unlink(conf.name)


class DialLet(Greenlet):
    def __init__(self):
        Greenlet.__init__(self)
        self.process = None
        self.logger = logging.getLogger('dialer.DialLet')

    def _run(self):
        while True:
            try:
                with wvdial_config() as config:
                    self.process = Popen(["sudo", "wvdial", "-C", config])

                    self.logger.info("Entering wvdial process waiting loop")
                    while self.process.poll() is None:
                        sleep(1)

                    self.logger.warning("wvdial process returned %s" % self.process.returncode)
                self.logger.info("Waiting for %s seconds for reconnection" % _wvdial_reconnect_wait)
                sleep(_wvdial_reconnect_wait)
            except Exception, e:
                self.logger.error(traceback.format_exc())
                self.logger.error("Encountered %s" % repr(e))
