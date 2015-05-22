#!/usr/bin/env python

import getpass
import logging
import optparse
import os
import sys
import time
import urllib
import urllib2
import simplejson
import time

TEST_MASTER = "http://a1228.halxg.cloudera.com:8081"

RED = "\x1b[31m"
RESET = "\x1b[m"

def generate_job_id():
  return "%s.%d.%d" % (getpass.getuser(), int(time.time()), os.getpid())

def do_watch_results(job_id):
  watch_url = TEST_MASTER + "/job?" + urllib.urlencode([("job_id", job_id)])
  logging.info("Watch your results at %s", watch_url)

  url = TEST_MASTER + "/job_status?" + urllib.urlencode([("job_id", job_id)])
  start_time = time.time()

  first = True
  while True:
    result_str = urllib2.urlopen(url).read()
    result = simplejson.loads(result_str)

    # On all but the first iteration, replace the previous line
    if not first:
      print "\x1b[F\x1b[2K",

    first = False
    run_time = time.time() - start_time
    print "%.1fs\t" % run_time,

    print "%d/%d tasks complete" % \
        (result['finished_tasks'], result['total_tasks']),

    if result['failed_tasks']:
      print RED,
      print "(%d failed)" % result['failed_tasks'],
      print RESET,
    print

    if result['finished_tasks'] == result['total_tasks']:
      break
    time.sleep(0.5)

def save_last_job_id(job_id):
  with file(os.path.expanduser("~/.dist-test-last-job"), "w") as f:
    f.write(job_id)

def load_last_job_id():
  try:
    with file(os.path.expanduser("~/.dist-test-last-job"), "r") as f:
      return f.read()
  except:
    return None

def submit_job_json(json):
  # Verify that it is proper JSON
  simplejson.loads(json)
  job_id = generate_job_id()
  form_data = urllib.urlencode({'job_id': job_id, 'job_json': json})
  result_str = urllib2.urlopen(TEST_MASTER + "/submit_job",
                               data=form_data).read()
  result = simplejson.loads(result_str)
  if result.get('status') != 'SUCCESS':
    sys.err.println("Unable to submit job: %s" % repr(result))
    sys.exit(1)

  save_last_job_id(job_id)

  logging.info("Submitted job %s", job_id)
  return job_id

def submit(argv):
  if len(argv) != 2:
    print >>sys.stderr, "usage: %s submit <job-json-path>" % os.path.basename(argv[0])
    sys.exit(1)

  job_id = submit_job_json(file(argv[1]).read())
  do_watch_results(job_id)

def get_job_id_from_args(command, args):
  if len(args) == 1:
    job_id = load_last_job_id()
    if job_id is not None:
      logging.info("Using most recently submitted job id: %s" % job_id)
      return job_id
  if len(args) != 2:
    print >>sys.stderr, "usage: %s %s <job-id>" % (os.path.basename(argv[0]), command)
    sys.exit(1)
  return args[1]

def watch(argv):
  job_id = get_job_id_from_args("watch", argv)
  do_watch_results(job_id)

def fetch_failed_tasks(job_id):
  url = TEST_MASTER + "/failed_tasks?" + urllib.urlencode([("job_id", job_id)])
  results_str = urllib2.urlopen(url).read()
  return simplejson.loads(results_str)

def safe_name(s):
  return "".join([c.isalnum() and c or "_" for c in s])

def fetch(argv):
  p = optparse.OptionParser(
      usage="usage: %prog fetch [options] <job-id>")
  p.add_option("-d", "--output-dir", dest="out_dir", type="string",
               help="directory into which to download logs", metavar="PATH",
	       default="dist-test-results")
  options, args = p.parse_args()

  if len(args) == 0:
    last_job = load_last_job_id()
    if last_job:
      args.append(last_job)

  if len(args) != 1:
    p.error("no job id specified")
  job_id = args[0]

  failed_tasks = fetch_failed_tasks(job_id)
  if len(failed_tasks) == 0:
    logging.info("No failed tasks in provided job, or job does not exist")
    return

  logging.info("Fetching %d failed task logs into %s",
               len(failed_tasks),
               options.out_dir)
  try:
    os.makedirs(options.out_dir)
  except:
    pass
  for t in failed_tasks:
    filename = safe_name(t['task_id']) + "." + safe_name(t['description'])
    path_prefix = os.path.join(options.out_dir, filename)
    if 'stdout_link' in t:
      path = path_prefix + ".stdout"
      if not os.path.exists(path):
        logging.info("Fetching stdout for task %s into %s", t['task_id'], path)
        urllib.urlretrieve(t['stdout_link'], path)
    else:
      logging.info("No stdout for task %s" % t['task_id'])
    if 'stderr_link' in t:
      path = path_prefix + ".stderr"
      if not os.path.exists(path):
        logging.info("Fetching stderr for task %s into %s", t['task_id'], path)
        urllib.urlretrieve(t['stderr_link'], path)
    else:
      logging.info("No stderr for task %s" % t['task_id'])


def usage(argv):
  print >>sys.stderr, "usage: %s <command> [<args>]" % os.path.basename(argv[0])
  print >>sys.stderr, """Commands:
    submit  Submit a JSON file listing tasks
    watch   Watch an already-submitted job ID
    fetch   Fetch failed test logs from a previous job"""
  print >>sys.stderr, "%s <command> --help may provide further info" % argv[0]

def main(argv):
  logging.basicConfig(level=logging.INFO)
  if len(argv) < 2:
    usage(argv)
    sys.exit(1)

  command = argv[1]
  del argv[1]
  if command == "submit":
    submit(argv)
  elif command == "watch":
    watch(argv)
  elif command == "fetch":
    fetch(argv)
  else:
    usage(argv)
    sys.exit(1)

if __name__ == "__main__":
  main(sys.argv)