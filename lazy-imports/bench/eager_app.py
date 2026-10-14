import sys
import time

from common import finish

t0 = time.perf_counter()
import asyncio
import csv
import ssl
import urllib.request
import numpy
import matplotlib
import workload

t_import = time.perf_counter()

command = sys.argv[1]
if command == "help":
    answer = None
elif command == "csv":
    answer = csv.list_dialects()
elif command == "records":
    answer = workload.SUMMARY
elif command == "plot":
    answer = matplotlib.__name__
else:
    raise SystemExit(2)

finish(t0, t_import, answer, "eager", command)
