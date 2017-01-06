#!/usr/bin/env python2
#
# Copyright 2012-2013 Janis Jansons (janis.jansons@janhouse.lv)
#

import argparse
import gzip
import socket
import sys
import time
import urllib
import urllib2
from StringIO import StringIO
from math import radians, cos, sin, asin, sqrt
from multiprocessing import Process, Pipe, Manager

from lxml import etree

from SocksiPy import socks

args = argparse.Namespace()
args.suppress = None
args.store = None


# Magic!
def getaddrinfo(*args):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (args[0], args[1]))]


socket.getaddrinfo = getaddrinfo

socket.setdefaulttimeout(None)


# Using StringIO with callback to measure upload progress
class CallbackStringIO(StringIO):
    def __init__(self, num, th, d, buf=''):
        # Force self.buf to be a string or unicode
        if not isinstance(buf, basestring):
            buf = str(buf)
        self.buf = buf
        self.len = len(buf)
        self.buflist = []
        self.pos = 0
        self.closed = False
        self.softspace = 0
        self.th = th
        self.num = num
        self.d = d
        self.total = self.len * self.th

    def read(self, n=10240):
        next_read = StringIO.read(self, n)
        # if 'done' in self.d:
        #    return

        self.d[self.num] = self.pos
        down = 0
        for i in range(self.th):
            down = down + self.d.get(i, 0)
        if self.num == 0:
            percent = float(down) / self.total
            percent = round(percent * 100, 2)
            print_debug("Uploaded %d of %d bytes (%0.2f%%) in %d threads\r" %
                        (down, self.total, percent, self.th))

        # if down >= self.total:
        #    print_debug('\n')
        #    self.d['done']=1

        return next_read

    def __len__(self):
        return self.len


class TeSpeed:
    def __init__(self, server="", num_top=0, server_count=3, store=False, suppress=False, unit=False, chunk_size=10240,
                 download_tests=15, upload_tests=10, server_list_file=False):

        self.headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:11.0) Gecko/20100101 Firefox/11.0',
            'Accept-Language': 'en-us,en;q=0.5',
            'Connection': 'keep-alive',
            'Accept-Encoding': 'gzip, deflate',
            # 'Referer' : 'http://c.speedtest.net/flash/speedtest.swf?v=301256',
        }

        self.num_servers = server_count
        self.servers = []
        if server != "":
            self.servers = [server]

        self.server = server
        self.down_speed = -1
        self.up_speed = -1
        self.latency_count = 10
        self.bestServers = 5
        self.server_list = None
        self.config = None

        self.units = "Mbit"
        self.unit = 0

        self.chunk_size = chunk_size

        self.download_tests = download_tests
        self.upload_tests = upload_tests

        self.local_server_list = server_list_file

        if unit:
            self.units = "MiB"
            self.unit = 1

        self.store = store
        self.suppress = suppress
        if store:
            print_debug("Printing CSV formatted results to STDOUT.\n")
        self.numTop = int(num_top)
        # ~ self.downList=['350x350', '500x500', '750x750', '1000x1000',
        # ~ '1500x1500', '2000x2000', '2000x2000', '2500x2500', '3000x3000',
        # ~ '3500x3500', '4000x4000', '4000x4000', '4000x4000', '4000x4000']
        # ~ self.upSizes=[1024*256, 1024*256, 1024*512, 1024*512,
        # ~ 1024*1024, 1024*1024, 1024*1024*2, 1024*1024*2,
        # ~ 1024*1024*2, 1024*1024*2]

        self.downList = [
            '350x350', '350x350', '500x500', '500x500', '750x750', '750x750', '1000x1000', '1500x1500', '2000x2000',
            '2500x2500',

            '3000x3000', '3500x3500', '4000x4000', '1000x1000', '1000x1000', '1000x1000', '1000x1000', '1000x1000',
            '1000x1000', '1000x1000',
            '1000x1000', '1000x1000', '1000x1000', '1000x1000', '1000x1000', '1000x1000', '1000x1000', '1000x1000',
            '1000x1000', '1000x1000',

            '2000x2000', '2000x2000', '2000x2000', '2000x2000', '2000x2000', '2000x2000', '2000x2000', '2000x2000',
            '2000x2000', '2000x2000',
            '2000x2000', '2000x2000', '2000x2000', '2000x2000', '2000x2000', '2000x2000', '2000x2000', '2000x2000',
            '2000x2000', '2000x2000',

            '4000x4000', '4000x4000', '4000x4000', '4000x4000', '4000x4000'
        ]

        # '350x350', '500x500', '750x750', '1000x1000',
        #            '1500x1500', '2000x2000', '2000x2000', '2500x2500', '3000x3000',
        #            '3500x3500', '4000x4000', '4000x4000', '4000x4000', '4000x4000'
        # ]
        self.upSizes = [

            1024 * 256, 1024 * 256, 1024 * 512, 1024 * 512, 1024 * 1024, 1024 * 1024, 1024 * 1024 * 2, 1024 * 1024 * 2,
            1024 * 1024 * 2, 1024 * 512,
            1024 * 256, 1024 * 256, 1024 * 256, 1024 * 256, 1024 * 256, 1024 * 256, 1024 * 256, 1024 * 256, 1024 * 256,
            1024 * 256,

            1024 * 512, 1024 * 512, 1024 * 512, 1024 * 512, 1024 * 512, 1024 * 512, 1024 * 512, 1024 * 512, 1024 * 512,
            1024 * 512,
            1024 * 512, 1024 * 512, 1024 * 512, 1024 * 512, 1024 * 512, 1024 * 512, 1024 * 512, 1024 * 512, 1024 * 512,
            1024 * 512,

            1024 * 256, 1024 * 256, 1024 * 256, 1024 * 256, 1024 * 256, 1024 * 256, 1024 * 256, 1024 * 256, 1024 * 256,
            1024 * 256,
            1024 * 512, 1024 * 512, 1024 * 512, 1024 * 512, 1024 * 512, 1024 * 512, 1024 * 512, 1024 * 512, 1024 * 512,
            1024 * 512,

            1024 * 1024 * 2, 1024 * 1024 * 2, 1024 * 1024 * 2, 1024 * 1024 * 2, 1024 * 1024 * 2, 1024 * 1024 * 2,
            1024 * 1024 * 2, 1024 * 1024 * 2, 1024 * 1024 * 2, 1024 * 1024 * 2,
            1024 * 1024 * 2, 1024 * 1024 * 2, 1024 * 1024 * 2, 1024 * 1024 * 2, 1024 * 1024 * 2, 1024 * 1024 * 2,
            1024 * 1024 * 2, 1024 * 1024 * 2, 1024 * 1024 * 2, 1024 * 1024 * 2,
            #            1024*1024, 1024*1024, 1024*1024*2, 1024*1024*2,
            #            1024*1024*2, 1024*1024*2]
        ]

        self.postData = ""
        self.TestSpeed()

    @staticmethod
    def calc_distance(one, two):
        # Calculate the great circle distance between two points
        # on the earth specified in decimal degrees (haversine formula)
        # (http://stackoverflow.com/posts/4913653/revisions)
        # convert decimal degrees to radians

        lon1, lat1, lon2, lat2 = map(radians, [one[0], one[1], two[0], two[1]])
        # haversine formula 
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))
        km = 6367 * c
        return km

    def find_closest(self, center, points, num=5):
        # Returns object that is closest to center
        closest = {}
        for p in range(len(points)):
            now = self.calc_distance(center, [points[p]['lat'], points[p]['lon']])
            points[p]['distance'] = now
            while True:
                if now in closest:
                    now += 00.1
                else:
                    break
            closest[now] = points[p]
        n = 0
        ret = []
        for key in sorted(closest):
            ret.append(closest[key])
            n += 1
            if n >= num != 0:
                break
        return ret

    def test_latency(self, servers):
        # Finding servers with lowest latency
        print_debug("Testing latency...\n")
        po = []
        for server in servers:
            now = self.test_single_latency(server['url'] + "latency.txt?x=" + str(time.time())) * 1000
            now /= 2  # Evil hack or just pure stupidity? Nobody knows...
            if now == -1 or now == 0:
                continue
            print_debug("%0.0f ms latency for %s (%s, %s, %s) [%0.2f km]\n" %
                        (now, server['url'], server['sponsor'], server['name'], server['country'], server['distance']))

            server['latency'] = now

            # Pick specified amount of servers with best latency for testing
            if int(len(po)) < int(self.num_servers):
                po.append(server)
            else:
                largest = -1

                for x in range(len(po)):
                    if largest < 0:
                        if now < po[x]['latency']:
                            largest = x
                    elif po[largest]['latency'] < po[x]['latency']:
                        largest = x
                        # if cur['latency']

                if largest >= 0:
                    po[largest] = server

        return po

    def test_single_latency(self, dest_addr):
        # Checking latency for single server
        # Does that by loading latency.txt (empty page)
        request = self.get_request(dest_addr)

        average_time = 0
        total = 0
        for i in range(self.latency_count):
            error = 0
            start_time = time.time()
            try:
                response = urllib2.urlopen(request, timeout=5)
            except (urllib2.URLError, socket.timeout), e:
                error = 1

            if error == 0:
                average_time = average_time + (time.time() - start_time)
                total += 1

            if total == 0:
                return False

        return average_time / total

    def get_request(self, uri):
        # Generates a GET request to be used with urlopen
        req = urllib2.Request(uri, headers=self.headers)
        return req

    def post_request(self, uri, stream):
        # Generate a POST request to be used with urlopen
        req = urllib2.Request(uri, stream, headers=self.headers)
        return req

    @staticmethod
    def report_chunk(bytes_so_far, chunk_size, total_size, num, th, d, w):
        # Receiving status update from download thread

        if w == 1:
            return
        d[num] = bytes_so_far
        down = 0
        for i in range(th):
            down = down + d.get(i, 0)

        if num == 0 or down >= total_size * th:
            percent = float(down) / (total_size * th)
            percent = round(percent * 100, 2)

            print_debug("Downloaded %d of %d bytes (%0.2f%%) in %d threads\r" %
                        (down, total_size * th, percent, th))

            # if down >= total_size*th:
            #   print_debug('\n')

    def read_chunk(self, response, num, th, d, w=0, chunk_size=False, report_hook=None):
        # print_debug("Thread num %d %d %d starting to report\n" % (th, num, d))

        if not chunk_size:
            chunk_size = self.chunk_size

        if w == 1:
            return [0, 0, 0]

        total_size = response.info().getheader('Content-Length').strip()
        total_size = int(total_size)
        bytes_so_far = 0

        start = 0
        while 1:
            chunk = 0
            if start == 0:
                # print_debug("Started receiving data\n")
                chunk = response.read(1)
                start = time.time()

            else:
                chunk = response.read(chunk_size)
            if not chunk:
                break
            bytes_so_far += len(chunk)
            if report_hook:
                report_hook(bytes_so_far, chunk_size, total_size, num, th, d, w)
        end = time.time()

        return [bytes_so_far, start, end]

    def get_async(self, conn, uri, num, th, d):
        request = self.get_request(uri)
        try:
            response = urllib2.urlopen(request, timeout=30)
            size, start, end = self.read_chunk(response, num, th, d, report_hook=self.report_chunk)
        # except urllib2.URLError, e:
        #    print_debug("Failed downloading.\n")
        except:
            print_debug('                                                                                           \r')
            print_debug("Failed downloading.\n")
            conn.send([0, 0, False])
            conn.close()
            return

        conn.send([size, start, end])
        conn.close()

    def post_async(self, conn, uri, num, th, d):
        post_length = len(self.postData)
        stream = CallbackStringIO(num, th, d, self.postData)
        request = self.post_request(uri, stream)

        try:
            response = urllib2.urlopen(request, timeout=30)
            size, start, end = self.read_chunk(response, num, th, d, 1, report_hook=self.report_chunk)
        # except urllib2.URLError, e:
        #    print_debug("Failed uploading.\n")
        except:
            print_debug('                                                                                           \r')
            print_debug("Failed uploading.\n")
            conn.send([0, 0, False])
            conn.close()
            return

        conn.send([post_length, start, end])
        conn.close()

    def load_config(self):
        # Load the configuration file
        print_debug("Loading speedtest configuration...\n")
        uri = "http://speedtest.net/speedtest-config.php?x=" + str(time.time())
        request = self.get_request(uri)
        response = None
        try:
            response = urllib2.urlopen(request, timeout=5)
        except (urllib2.URLError, socket.timeout), e:
            print_debug("Failed to get Speedtest.net config file.\n")
            print_result("%0.2f,%0.2f,\"%s\",\"%s\"\n" % (self.down_speed, self.up_speed, self.units, self.servers))
            sys.exit(1)

        # Load etree from XML data
        config = etree.fromstring(self.decompress_response(response))

        ip = config.find("client").attrib['ip']
        isp = config.find("client").attrib['isp']
        lat = float(config.find("client").attrib['lat'])
        lon = float(config.find("client").attrib['lon'])

        print_debug("IP: %s; Lat: %f; Lon: %f; ISP: %s\n" % (ip, lat, lon, isp))

        return {'ip': ip, 'lat': lat, 'lon': lon, 'isp': isp}

    def download_server_list(self):
        print_debug("Loading server list...\n")
        uri = "http://speedtest.net/speedtest-servers.php?x=" + str(time.time())
        request = self.get_request(uri)
        response = None
        try:
            response = urllib2.urlopen(request);
        except (urllib2.URLError, socket.timeout), e:
            print_debug("Failed to get Speedtest.net server list.\n")
            print_result("%0.2f,%0.2f,\"%s\",\"%s\"\n" % (self.down_speed, self.up_speed, self.units, self.servers))
            sys.exit(1)

        # Load etree from XML data
        servers_xml = etree.fromstring(self.decompress_response(response))
        return servers_xml
        pass

    @staticmethod
    def load_local_server_list(file_path):
        with open(file_path, 'r') as file:
            return file.read()
        pass

    @staticmethod
    def parse_server_list(servers_xml):
        servers = servers_xml.find("servers").findall("server")
        server_list = []

        for server in servers:
            server_list.append({
                'lat': float(server.attrib['lat']),
                'lon': float(server.attrib['lon']),
                'url': server.attrib['url'].rsplit('/', 1)[0] + '/',
                # 'url2': server.attrib['url2'].rsplit('/', 1)[0] + '/',
                'name': server.attrib['name'],
                'country': server.attrib['country'],
                'sponsor': server.attrib['sponsor'],
                'id': server.attrib['id'],
            })
        return server_list

    def load_server_list(self):
        if not self.local_server_list:
            server_xml = self.download_server_list()
        else:
            server_xml = self.load_local_server_list(self.local_server_list)
        return self.parse_server_list(server_xml)

    def decompress_response(self, response):
        # Decompress gzipped response
        data = StringIO(response.read())
        gzipper = gzip.GzipFile(fileobj=data)
        try:
            return gzipper.read()
        except IOError as e:
            # Response isn't gzipped, therefore return the data.
            return data.getvalue()

    def find_best_server(self):
        print_debug("Looking for closest and best server...\n")
        best = self.test_latency(
            self.find_closest([self.config['lat'], self.config['lon']], self.server_list, self.bestServers))
        for server in best:
            self.servers.append(server['url'])

    def async_request(self, url, num, upload=0):
        connections = []
        d = Manager().dict()
        start = time.time()
        for i in range(num):
            full_url = self.servers[i % len(self.servers)] + url
            # print full_url
            connection = {}
            connection['parent'], connection['child'] = Pipe()
            if upload == 1:
                connection['connection'] = Process(target=self.post_async,
                                                   args=(connection['child'], full_url, i, num, d))
            else:
                connection['connection'] = Process(target=self.get_async,
                                                   args=(connection['child'], full_url, i, num, d))
            connection['connection'].start()
            connections.append(connection)

        for c in range(num):
            connections[c]['size'], connections[c]['start'], connections[c]['end'] = connections[c]['parent'].recv()
            connections[c]['connection'].join()

        end = time.time()

        print_debug('                                                                                           \r')

        sizes = 0
        # tspeed=0
        for c in range(num):
            if connections[c]['end'] is not False:
                # tspeed=tspeed+(connections[c]['size']/(connections[c]['end']-connections[c]['start']))
                sizes = sizes + connections[c]['size']

                # Using more precise times for downloads
                if upload == 0:
                    if c == 0:
                        start = connections[c]['start']
                        end = connections[c]['end']
                    else:
                        if connections[c]['start'] < start:
                            start = connections[c]['start']
                        if connections[c]['end'] > end:
                            end = connections[c]['end']

        took = end - start

        return [sizes, took]

    def test_upload(self):
        # Testing upload speed
        url = "upload.php?x=" + str(time.time())

        counter = 0
        failures = 0
        data = ""
        for i in range(0, len(self.upSizes)):
            if len(data) == 0 or self.upSizes[i] != self.upSizes[i - 1]:
                # print_debug("Generating new string to upload. Length: %d\n" % (self.upSizes[i]))
                data = ''.join("1" for x in xrange(self.upSizes[i]))
            self.postData = urllib.urlencode({'upload6': data})

            if i < 2:
                thread_count = 1
            elif i < 5:
                thread_count = 2
            elif i < 7:
                thread_count = 2
            elif i < 10:
                thread_count = 3
            elif i < 25:
                thread_count = 6
            elif i < 45:
                thread_count = 4
            elif i < 65:
                thread_count = 3
            else:
                thread_count = 2

            sizes, took = self.async_request(url, thread_count, 1)
            # sizes, took=self.AsyncRequest(url, (i<4 and 1 or (i<6 and 2 or (i<6 and 4 or 8))), 1)

            # Stop testing if too many failures            
            counter += 1
            if sizes == 0:
                failures += 1
                if failures > 2:
                    break
                continue

            size = self.convert_speed(sizes)
            speed = size / took
            print_debug("Upload size: %0.2f MiB; Uploaded in %0.2f s\n" %
                        (size, took))
            print_debug("\033[92mUpload speed: %0.2f %s/s\033[0m\n" %
                        (speed, self.units))

            if self.up_speed < speed:
                self.up_speed = speed

            if took > 5 or counter >= self.upload_tests:
                break

                # print_debug("Upload size: %0.2f MiB; Uploaded in %0.2f s\n" % (self.SpeedConversion(sizes), took))
                # print_debug("Upload speed: %0.2f MiB/s\n" % (self.SpeedConversion(sizes)/took))

    def convert_speed(self, data):
        if self.unit == 1:
            result = (float(data) / 1024 / 1024)
        else:
            result = (float(data) / 1024 / 1024) * 1.048576 * 8
        return result

    def test_download(self):
        # Testing download speed
        counter = 0
        failures = 0
        for i in range(0, len(self.downList)):
            url = "random" + self.downList[i] + ".jpg?x=" + str(time.time()) + "&y=3"

            if i < 2:
                thread_count = 1
            elif i < 5:
                thread_count = 2
            elif i < 11:
                thread_count = 2
            elif i < 13:
                thread_count = 4
            elif i < 25:
                thread_count = 2
            elif i < 45:
                thread_count = 3
            elif i < 65:
                thread_count = 2
            else:
                thread_count = 2

            sizes, took = self.async_request(url, thread_count)
            # sizes, took=self.AsyncRequest(url, (i<1 and 2 or (i<6 and 4 or (i<10 and 6 or 8))) )

            # Stop testing if too many failures            
            counter += 1
            if sizes == 0:
                failures += 1
                if failures > 2:
                    break
                continue

            size = self.convert_speed(sizes)
            speed = size / took
            print_debug("Download size: %0.2f MiB; Downloaded in %0.2f s\n" %
                        (size, took))
            print_debug("\033[91mDownload speed: %0.2f %s/s\033[0m\n" %
                        (speed, self.units))

            if self.down_speed < speed:
                self.down_speed = speed

            if took > 5 or counter >= self.download_tests:
                break

                # print_debug("Download size: %0.2f MiB; Downloaded in %0.2f s\n" % (self.SpeedConversion(sizes), took))
                # print_debug("Download speed: %0.2f %s/s\n" % (self.SpeedConversion(sizes)/took, self.units))

    def TestSpeed(self):

        if self.server == 'list-servers':
            self.config = self.load_config()
            self.server_list = self.load_server_list()
            self.ListServers(self.numTop)
            return

        if self.server == '':
            self.config = self.load_config()
            self.server_list = self.load_server_list()
            self.find_best_server()

        self.test_download()
        self.test_upload()

        print_result("%0.2f,%0.2f,\"%s\",\"%s\"\n" % (self.down_speed, self.up_speed, self.units, self.servers))

    def ListServers(self, num=0):

        allSorted = self.find_closest([self.config['lat'], self.config['lon']], self.server_list, num)

        for i in range(0, len(allSorted)):
            print_result("%s. %s (%s, %s, %s) [%0.2f km]\n" %
                         (i + 1, allSorted[i]['url'], allSorted[i]['sponsor'], allSorted[i]['name'],
                          allSorted[i]['country'], allSorted[i]['distance']))


def print_debug(string):
    if not args.suppress:
        sys.stderr.write(string.encode('utf8'))
        # return


def print_result(string):
    if args.store:
        sys.stdout.write(string.encode('utf8'))
        # return


# Thx to Ryan Sears for http://bit.ly/17HhSli
def set_proxy(typ=socks.PROXY_TYPE_SOCKS4, host="127.0.0.1", port=9050):
    socks.setdefaultproxy(typ, host, port)
    socket.socket = socks.socksocket


def main(args):
    if args.version:
        print_debug(
            "Tespeed v1.1\nNetwork speedtest using speedtest.net infrastructure - https://github.com/Janhouse/tespeed\n")
        sys.exit(0)

    if args.use_proxy:
        if args.use_proxy == 5:
            set_proxy(typ=socks.PROXY_TYPE_SOCKS5, host=args.proxy_host, port=args.proxy_port)
        else:
            set_proxy(typ=socks.PROXY_TYPE_SOCKS4, host=args.proxy_host, port=args.proxy_port)

    if args.listservers:
        args.store = True

    if args.listservers != True and args.server == '' and args.store != True:
        print_debug("Getting ready. Use parameter -h or --help to see available features.\n")
    else:
        print_debug("Getting ready\n")
    try:
        t = TeSpeed(
            args.listservers and 'list-servers' or args.server,
            args.listservers, args.servercount,
            args.store and True or False,
            args.suppress and True or False,
            args.unit and True or False,
            chunk_size=args.chunksize,
            download_tests=args.downloadtests,
            upload_tests=args.uploadtests,
            server_list_file=args.serverlist and True or False
        )
    except (KeyboardInterrupt, SystemExit):
        print_debug("\nTesting stopped.\n")
        # raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='TeSpeed, CLI SpeedTest.net')

    parser.add_argument('server', nargs='?', type=str, default='',
                        help='Use the specified server for testing (skip checking for location and closest server).')
    parser.add_argument('-ls', '--list-servers', dest='listservers', nargs='?', default=0, const=10,
                        help='List the servers sorted by distance, nearest first. Optionally specify number of '
                             'servers to show.')
    parser.add_argument('-w', '--csv', dest='store', action='store_const', const=True,
                        help='Print CSV formated output to STDOUT.')
    parser.add_argument('-s', '--suppress', dest='suppress', action='store_const', const=True,
                        help='Suppress debugging (STDERR) output.')
    parser.add_argument('-mib', '--mebibit', dest='unit', action='store_const', const=True,
                        help='Show results in mebibits.')
    parser.add_argument('-n', '--server-count', dest='servercount', nargs='?', default=1, const=1,
                        help='Specify how many different servers should be used in paralel. (Default: 1) (Increase it '
                             'for >100Mbit testing.)')
    parser.add_argument('-sl', '--server-list', dest='serverlist', nargs='?', type=str,
                        help='Specify local server list')

    parser.add_argument('-p', '--proxy', dest='use_proxy', type=int, nargs='?', const=4,
                        help='Specify 4 or 5 to use SOCKS4 or SOCKS5 proxy.')
    parser.add_argument('-ph', '--proxy-host', dest='proxy_host', type=str, nargs='?', default='127.0.0.1',
                        help='Specify socks proxy host. (Default: 127.0.0.1)')
    parser.add_argument('-pp', '--proxy-port', dest='proxy_port', type=int, nargs='?', default=9050,
                        help='Specify socks proxy port. (Default: 9050)')

    parser.add_argument('-cs', '--chunk-size', dest='chunksize', nargs='?', type=int, default=10240,
                        help='Specify chunk size after wich tespeed calculates speed. Increase this number 4 or 5 '
                             'times if you use weak hardware like RaspberryPi. (Default: 10240)')
    parser.add_argument('-dt', '--max-download-tests', dest='downloadtests', nargs='?', type=int, default=15,
                        help='Specify maximum number of download tests to be performed. (Default: 15)')
    parser.add_argument('-ut', '--max-upload-tests', dest='uploadtests', nargs='?', type=int, default=10,
                        help='Specify maximum number of upload tests to be performed. (Default: 10)')

    # parser.add_argument('-i', '--interface', dest='interface', nargs='?',
    #                     help='If specified, measures speed from data for the whole network interface.')

    parser.add_argument('-v', '--version', dest='version', nargs='?', const=True, help='Show Tespeed version.')

    args = parser.parse_args()
    main(args)
