#!/usr/bin/env python3
# -*- coding: utf-8

import argparse, sys, os, hashlib, requests
from functools import partial
from queue import Queue
from threading import Thread


class Grabber():
    danbooru_url = "http://donmai.us"
    page = 1    # Need 0 for gelbooru
    limit = 200
    threads = 10
    
    login = ""
    password = ""

    blacklist = "scat comic".split()

    tags = ""
    total_result = []
    total_post_count = 0
    download_count = 0
    downloaded_count = 0
    skipped_count = 0
    
    parser = argparse.ArgumentParser(description='Grabber')
    parser.add_argument("-p", "--post", action="store_true",
                        help="Post search")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="Quiet mode")
    parser.add_argument("value", help="Value to search")
    args = parser.parse_args()
    
    
    def md5sum(self, file_name):
        with open(file_name, "rb") as file_to_check:
            hasher = hashlib.md5()
            for buf in iter(partial(file_to_check.read, 128), b""):
                hasher.update(buf)
        return hasher.hexdigest()


    def download(self, file_url, file_name, md5):
        org_fn = file_url[22:]
        if os.path.exists(org_fn) and os.path.isfile(org_fn):
            local_file_md5 = self.md5sum(org_fn)
            if local_file_md5 == md5:
                self.download_count += 1
                if not self.args.quiet:
                    print ("{}/{}".format(self.download_count, self.total_post_count),
                           "({}%)".format(round(self.download_count/(self.total_post_count/100))),
                           "Rename old file {} to {}".format(org_fn, file_name))
                os.rename(org_fn, file_name)
            else:
                os.remove(org_fn)
                
                self.download(file_url, file_name, md5)
        if os.path.exists(file_name) and os.path.isfile(file_name):
            local_file_md5 = self.md5sum(file_name)
            if local_file_md5 == md5:
                self.download_count += 1
                self.skipped_count += 1
                if not self.args.quiet:
                    print ("{}/{}".format(self.download_count, self.total_post_count),
                           "({}%)".format(round(self.download_count/(self.total_post_count/100))),
                           "md5 match! Skipping download.")
            else:
                if not self.args.quiet:
                    print ("md5 mismatch!",
                           "\nLocal file md5:", local_file_md5,
                           "\nCorrect file md5:", md5,
                           "\nRestart file download.")
                os.remove(file_name)
                
                self.download(file_url, file_name, md5)
        else:
            self.download_count += 1
            self.downloaded_count += 1
            print ("{}/{}".format(self.download_count, self.total_post_count),
                   "({}%)".format(round(self.download_count/(self.total_post_count/100))),
                   "downloading", file_name)
            
            r = requests.get(file_url, stream = True)
            with open(file_name, "wb") as f:
                for chunk in r.iter_content(chunk_size = 1024):
                    if chunk:
                        f.write(chunk)
                        f.flush()
  
    
    def parse(self, post):
        file_url = self.danbooru_url + post["file_url"]
        file_name = "{} - {}.{}".format("Donmai.us", post["id"], post["file_ext"])
        md5 = post["md5"]
        
        if not post["is_blacklisted"]:
            self.download(file_url, file_name, md5)
        else:
            if os.path.exists(file_name) and os.path.isfile(file_name):
                print ("Skipped file is exists!!!")
            
          
    def worker(self):
        while True:
            post = q.get()
            self.parse(post)
            q.task_done()
            
  
    def search(self, value, method = "tag"):
        if method is "tag":
            self.tags = value.replace(" ", "+")
            url = "{}/posts.json?tags={}&page={}&limit={}".format(self.danbooru_url, self.tags, self.page, self.limit)
            if not self.args.quiet:
                print ("Please wait, loading page", self.page)
        if method is "post":
            url = "{}/posts.json?tags=id:{}&page={}&limit={}".format(self.danbooru_url, value, self.page, self.limit)
        if method is "pool":
            url = "{}/posts.json?tags=pool:{}&page={}&limit={}".format(self.danbooru_url, value, self.page, self.limit)
            
        if self.login and self.password:
            response = requests.get(url, auth = (self.login, self.password))
        else:
            response = requests.get(url)
        result = response.json()
        
        post_counter = len(result)        
        if post_counter == 0 and not self.total_result:
            print ("Not found.")
            sys.exit()
        if post_counter == self.limit:
            self.page += 1
            self.total_post_count += post_counter
            self.total_result += result
            
            return self.search(self.tags)
        else:
            self.total_post_count += post_counter
            self.total_result += result
            
            if method is "tag":
                for tag in self.tags.split("+"):
                    if tag in self.blacklist:
                        self.blacklist.remove(tag)
                print ("Before:", self.total_post_count)
                for post in self.total_result:
                    post["is_blacklisted"] = False
                    for tag in self.blacklist:
                        if tag in post["tag_string"] and not post["is_blacklisted"]:
                            post["is_blacklisted"] = True
                            self.total_post_count -= 1
            print ("Total results:", self.total_post_count)
            
            pic_dir = os.getenv("HOME") + "/Pictures"
            if not os.path.exists(pic_dir) and not os.path.isdir(pic_dir):
                os.mkdir(pic_dir)
            os.chdir(pic_dir)
            if self.tags:
                if not os.path.exists(self.tags) and not os.path.isdir(self.tags):
                    os.mkdir(self.tags)
                os.chdir(self.tags)
            
            if self.args.quiet:
                return self.total_result
            else:
                a = input("Do you want to continiue?\n")
                if "n" not in a:
                    return self.total_result
                else:
                    sys.exit()
                  
  
g = Grabber()
q = Queue()

if g.args.post:
    print ("Search post with id:", g.args.value)
    for item in g.search(g.args.value, method = "post"):
        g.parse(item)
else:
    print ("Search tag:", g.args.value)
    for item in g.search(g.args.value):
        q.put(item)
        
    for i in range(g.threads):
        t = Thread(target=g.worker)
        t.daemon = True
        t.start()
        
    q.join()
    print ("Done! TTL: {}, OK: {}, SKP: {}".format(g.total_post_count, g.downloaded_count, g.skipped_count))
 
