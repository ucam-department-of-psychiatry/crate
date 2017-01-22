#!/usr/bin/env python

"""
A threading "daemon" thread IS NOT A PROPER DAEMON.
http://www.bogotobogo.com/python/Multithread/python_multithreading_Daemon_join_method_threads.php

The daemon threads are killed when the main process exits.
"""

import threading

def threadfunc():
    while True:
        print("In daemon thread")
        time.sleep(5)

th = threading.Thread(target=threadfunc)
th.daemon = True
print("Starting daemon thread")
th.start()
print("At end of main program")
