#!/usr/bin/env python2
import hashlib
import socket 
import time
import threading
import SocketServer
import random
import re
import json


from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from SocketServer import ThreadingMixIn 

from StringIO import StringIO
from threading import Thread 
import logging
import math
import sys
import os
import sqlite3

#################################################################
#################################################################
logger = logging.getLogger()
logger.setLevel(logging.INFO)

logConsoleHandler = logging.StreamHandler()
formatter = logging.Formatter(u'%(levelname)s - %(asctime)s - %(message)s')
logConsoleHandler.setFormatter(formatter)
logger.addHandler(logConsoleHandler)

#################################################################
#################################################################


def populateDatabase():
    conn = sqlite3.connect('samples.db')
    c = conn.cursor()
    c.execute('''DROP TABLE IF EXISTS samples''')
    c.execute('''CREATE TABLE samples (DATETIME datetime, EQUIPMENT text, ID int, LINE text, TARGET1 real, TARGET2 real, TARGET3 real, TARGET4 real, TARGET5 real)''')
    #DATETIME,EQUIPMENT,ID,LINE,TARGET1,TARGET2,TARGET3,TARGET4,TARGET5
    #11/19/18 0:00,MACHINE50,1,LINEdA,12,2.67,15.6,1.3884,0.2

    id = 1
    for i in range(-60*60*24,60*60*24): # Range in seconds to generate the data
        samples = []
        for j in range(0, 5): # Number of samples to generate per seccond
            date    = i
            equipment = "MACHINE50"
            line    = "LINEA"
            target1 = 5+math.sin(math.pi*i*0.02)*3 + random.uniform(-1.5,1.5)
            target2 = random.random()*10-5
            target3 = random.random()*1
            target4 = random.random()*2
            target5 = random.random()*0.4-0.2
            params  = (date, equipment, id, line, target1, target2, target3, target4, target5)
            #print(params)
            samples.append(params)
            
        c.executemany("insert into samples values (?, ?, ?, ?, ?, ?, ?, ?, ?)", samples)

        
    conn.commit()
    conn.close()

if not os.path.exists('samples.db'):
    populateDatabase()
#################################################################
#################################################################


re_hour = re.compile(r'^h-(\d+)$')
re_min = re.compile(r'^m-(\d+)$')
re_sec = re.compile(r'^s-(\d+)$')

class Handler(BaseHTTPRequestHandler):

    def log(self,s):
        logging.info( "[{}] {}".format(self.thread.name,str(s)) )

    def setup(self):
        BaseHTTPRequestHandler.setup(self)
        self.thread = threading.current_thread()
        self.log("Connected {}:{}".format(self.client_address[0],self.client_address[1]))

    def do_GET(self):
        
        path = self.path
        query = ""

        if '?' in path:
            (path, query) = path.split('?')

        if path == "/api/samples":
            self.rest_samples( path, query)
        elif path == "/api/settings":
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write("""[
    {
        "name": "data1",
        "datap": "target1",
        "target": "chart1",
        "domain": 60,
        "limit": [2,7],
        "range": [0,8],
        "refresh_rate": 1
    },
    {
        "name": "data2",
        "datap": "target2",
        "target": "chart2",
        "domain": 60,
        "limit": [-4,4],
        "range": [-6,6],
        "refresh_rate": 1
    },
    {
        "name": "data3",
        "datap": "target3",
        "target": "chart3",
        "domain": 60,
        "limit": [-4,4],
        "range": [-6,6],
        "refresh_rate": 1
    }
]""")

        else:
            self.send_response(404)
            self.end_headers()
            message =  threading.currentThread().getName()

            self.wfile.write(message)
            self.wfile.write('\n')
            self.wfile.write(path)
            self.wfile.write('\n')
            self.wfile.write(query)
            self.wfile.write('\n')
        
        return

    def rest_samples(self, path, query):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()  
        
        hour_match = re_hour.match(query)
        min_match = re_min.match(query)
        sec_match = re_sec.match(query)

        time_epoch = time.time()
        time_now_s = time.gmtime(time_epoch)
        time_now = time_now_s.tm_hour*60*60+time_now_s.tm_min*60+time_now_s.tm_sec
        time_epoch_midnight = time_epoch - time_now

        time_past = time_now
        if hour_match:
            time_past = time_now - 60*60*int(hour_match.group(1))
        elif min_match:
            time_past = time_now - 60*int(min_match.group(1))
        elif sec_match:
            time_past = time_now - int(sec_match.group(1))
        
        
        
        conn = sqlite3.connect('samples.db')
        cur = conn.cursor()
        cur.execute("select DATETIME+%d, EQUIPMENT, ID, LINE, TARGET1, TARGET2, TARGET3, TARGET4, TARGET5 from samples where DATETIME <= %d and  DATETIME > %d" % (time_epoch_midnight, time_now, time_past) )
        data = cur.fetchall()
        
        data_keys = ["datetime", "equipment", "id", "line", "target1", "target2", "target3", "target4", "target5"]
        data = [dict(zip(data_keys,v)) for v in data]

        conn.commit()
        self.wfile.write(json.dumps(data))

    def finish(self):
        self.log("Disconnected")
        self.request.close()


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    address_family = socket.AF_INET #AF_INET6
    daemon_threads = True
    pass

if __name__ == "__main__":
    HOST, PORT = "0.0.0.0", 8080

    server = ThreadedHTTPServer((HOST, PORT), Handler)
    ip, port = server.server_address

    try:
        logging.info('Starting up the server')
        server.serve_forever()
    except:
        logging.info('Shutting down the server')
        server.shutdown()
        