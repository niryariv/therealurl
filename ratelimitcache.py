
# UNUSED - replaced by ratelimit(IP) in main.py, to reduce CPU usage

from datetime import datetime, timedelta
import functools, hashlib

import os 
import logging 

# from django.http import HttpResponseForbidden
from google.appengine.api import memcache


class ratelimit(object):
	"""
	A memcached backed rate limiting decorator for Django on Google App Engine.
	"""
	minutes = 2 # The time period
	requests = 20 # Number of allowed requests in that time period
	prefix = 'rl-' # Prefix for memcache key
	expire_after = (minutes + 1) * 60
	
	def __init__(self, **options):
		for key, value in options.items():
			setattr(self, key, value)
	
	def __call__(self, fn):
		def wrapper(request, *args, **kwargs):
			return self.view_wrapper(request, fn, *args, **kwargs)
		functools.update_wrapper(wrapper, fn)
		return wrapper
	
	def view_wrapper(self, request, fn, *args, **kwargs):
		# Pass if not ratelimited
		if not self.should_ratelimit(request):
			return fn(request, *args, **kwargs)
		# Rate limit if exceeded 
		if self._get_sum_of_requests(request) >= self.requests:
			return self.disallowed(request)
		# Count successful request
		self._count_request(request)
		# Pass
		return fn(request, *args, **kwargs)
	
	def should_ratelimit(self, request):
		"""
		Returns a boolean. Over-ride this method if you need only certain types
		of requests to rate limit.
		The default behavior is to rate limit every request.
		"""
		return True
	
	def disallowed(self, request):
		"""
		Returns a HttpResponseForbidden (HTTP Code 403) instance. Over-ride
		this method if you want to log incidents.
		"""
		logging.warning("ERROR: Daily request quota exceeded for %s" % os.environ['REMOTE_ADDR'])
        
		request.response.set_status(403)
		return request.response.out.write("Daily request quota exceeded. If you'd like a higher quota, please contact niryariv@gmail.com\n")
		# return HttpResponseForbidden('Rate limit exceeded')
		
	def key_extra(self, request):
		"""
		Returns the key extra that filters the request. Over-ride this method
		if you want to use a different extra than the remote IP address.
		"""
		# return request.META.get('REMOTE_ADDR', '')
		return os.environ['REMOTE_ADDR']
	
	def _increase_cache(self, key):
		"""
		Increases a cache value, creates the key on demand.
		"""
		added = memcache.add(key, 1, time=self.expire_after)
		if not added:
			memcache.incr(key)
	
	def _get_current_key(self, request):
		"""
		Returns the current key name.
		"""
		return '%s%s-%s' % (self.prefix, self.key_extra(request),
			datetime.utcnow().strftime('%Y%m%d%H%M'))
	
	def _count_request(self, request):
		"""
		Counts the request in the cache.
		"""
		self._increase_cache(self._get_current_key(request))
	
	def _keys_to_check(self, request):
		"""
		Returns a list of keys to check.
		"""
		extra = self.key_extra(request)
		now = datetime.utcnow()
		return [
			'%s%s-%s' % (
				self.prefix,
				extra,
				(now - timedelta(minutes = minute)).strftime('%Y%m%d%H%M')
			) for minute in range(self.minutes + 1)
		]
	
	def _get_counters(self, request):
		"""
		Returns a list of counters to check.
		"""
		return memcache.get_multi(self._keys_to_check(request))
	
	def _get_sum_of_requests(self, request):
		"""
		Returns the sum of the former requests.
		"""
		return sum(self._get_counters(request).values())
		
		
# class ratelimit_post(ratelimit):
# 	"""
# 	Rate limit POSTs - can be used to protect a login form.
# 	"""
# 	key_field = None # If provided, this POST var will affect the rate limit
# 	
# 	def should_ratelimit(self, request):
# 		return request.method == 'POST'
# 	
# 	def key_extra(self, request):
# 		# IP address and key_field (if it is set)
# 		extra = super(ratelimit_post, self).key_extra(request)
# 		if self.key_field:
# 			m = hashlib.sha1()
# 			m.update(request.POST.get(self.key_field, ''))
# 			digest = m.hexdigest()
# 			extra += '-' + digest
# 		return extra