import urllib
import time

i = 0

while True:
	u = urllib.urlopen('http://localhost:8080/?url=http://tinyurl.com/b')
	if u.getcode() == 200:
		out = "================"
	else:
		out = ""
		
	print i, u.getcode(), out
	i += 1
	time.sleep(1)