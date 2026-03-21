import multiprocessing

# Workers: 2 * CPU cores + 1 is the standard formula
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
threads = 1

bind = "0.0.0.0:5000"
timeout = 60
keepalive = 5

# Log to stdout so kubectl logs picks it up
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Don't log health check noise
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(Dms)sms'