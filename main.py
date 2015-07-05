#!/usr/bin/env python

import wsgiref.handlers
import urllib
import os
import re
import logging

from django.utils import simplejson
from google.appengine.api import memcache

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template

RATE_LIMIT_CYCLE = 86400 	# seconds
CYCLE_REQ_QUOTA  = 2000		# reqs/cycle


def ratelimit(IP):
	memcache_id = "ratelimit_%s" % IP
	current_hits = memcache.get(memcache_id)
	
	if current_hits >= CYCLE_REQ_QUOTA: 
		return False
	
	if current_hits is None:
		memcache.set(memcache_id, 1, time=RATE_LIMIT_CYCLE)
	else:
		memcache.incr(memcache_id)

	return True


class TheRealURL(webapp.RequestHandler):
	
	# router 
	#@ratelimit(minutes = MINUTES_IN_DAY, requests = DAILY_REQ_QUOTA)
	def get(self):
		
		# enforce rate limit
		if ratelimit(os.environ['REMOTE_ADDR']) is False:
			# logging.warning("ERROR: Daily request quota exceeded for %s" % os.environ['REMOTE_ADDR'])
			self.response.set_status(403)
			self.response.out.write("%s daily requests quota exceeded. If you're interested in a higher quota, contact niryariv@gmail.com\n" % CYCLE_REQ_QUOTA)
			return 
		
		cache_key = "response-%s" % self.request.url # GAE takes care of version namespacing internally
		
		url = 'http://' + self.request.get('url').replace('http://','') # handle 'tinyurl.com' as well as 'http://tinyurl.com'
		callback = self.request.get('callback')
		format	 = self.request.get('format')
		flush = self.request.get('flushcache')
		
		if flush == 'now':
			memcache.flush_all()
		
		if url == 'http://':
			self.homepage()
		else:
			try:
				out = memcache.get(cache_key)
				if out is None:
					if format == 'json':
						out = self.json(url, callback)
					else:
						out = self.plain(url)
					
					memcache.add(cache_key, out)
				
				self.response.headers.add_header('Access-Control-Allow-Origin', '*')
				self.response.out.write(out)
				
			except Exception, err_msg:
				logging.warning("Exception in get(): %s" % err_msg)
				self.response.set_status(404)
				self.response.out.write('error')

			
# logic

	def _conn(self, url):
		if not hasattr(self, '_c'):
			self._c = urllib.urlopen(url)
			
		return self._c
			
			
	def _real_url(self, url):
		return self._conn(url).geturl()
			
				
	def _title(self, url):
		title = ''
		if self._conn(url).info().type.find('text') != -1:  #.type == 'text/html':
			html = self._conn(url).read()
			t_rex = re.compile('<title.*?>(.*?)</title>', re.IGNORECASE | re.DOTALL)
			res = re.search(t_rex, html)
			if res is not None:
				title = res.groups()[0]

		return title


	def _headers(self, url):
		i = self._conn(url).info()
		return { 
			'content-type' : i.getheader('content-type'),
			'content-length' : i.getheader('content-length')
		}


# views

	def homepage(self):
		template_values = { 
							'sitename' : 'TheRealURL',
							'ratelimit': CYCLE_REQ_QUOTA
							}
		
		path = os.path.join(os.path.dirname(__file__), 'views/index.html')
		self.response.out.write(template.render(path, template_values))


	def plain(self, url):
		return self._real_url(url)


	def json(self, url, callback):
		out = simplejson.dumps({ 
			'url' : self._real_url(url), 
			'title' : self._title(url),
			'headers' : self._headers(url)
		}, indent=1)

		if callback != '':
			out = callback + '(' + out + ')'
		
		return out
 

 
# GAE main

def main():
	application = webapp.WSGIApplication([('/.*', TheRealURL)], debug=True)

	wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
	main()
