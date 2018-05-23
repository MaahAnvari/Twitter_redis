#from time import time

import redis
from datetime import time, datetime
from django.http import HttpResponse, request
from django.http import HttpResponseRedirect
from django.shortcuts import render, render_to_response
from django.views.decorators.csrf import csrf_protect, csrf_exempt
import json
import csv
from xlrd import open_workbook

# Create your views here.
from django.template import RequestContext

def index(request):
   return render(request, "index.html", {})

def register(request):
    if request.method == 'POST':
        conn = redis.StrictRedis(host='localhost', port=6379, db=0)
        id = conn.incr('user:id:')
        username = request.POST['username']
        print("username "+str(username))
        if conn.hget('usersList:', username):
            print("invalid username")
            error = "Username is invalid"
            return render(request, "register.html", {'error': error})
        password = request.POST['password']
        conn.hset('usersList:', username, id)
        conn.hmset('user:%s' % id, {
            'username': username,
            'id': id,
            'followers': 0,
            'following': 0,
            'posts': 0,
            'signup': datetime.now(),
        })
        conn.hmset('user_info:%s' % id, {
            'username': username,
            'id': id,
            'password': password,
        })
        request.session['username'] = username
        return HttpResponseRedirect("dashboard/home")
    else:
        return render(request, "register.html", {})

@csrf_protect
def login(request):

    if (request.method == "POST"):
        print("Post")
        conn = redis.StrictRedis(host='localhost', port=6379, db=0)
        username = request.POST['username']
        password = request.POST['password']
        if (conn.hget('usersList:', username)):
            print("username accepted")
            id = str(conn.hmget('usersList:', username))[3:-2]
            print(id)
            accepted_pass = str(conn.hmget('user_info:%s' % id, 'password'))[3:-2]
            if accepted_pass == str(password):
                print("password accepted")
                request.session['username'] = request.POST['username']
                return HttpResponseRedirect("dashboard/home")
            else:
                print("password refused")
                error = "Username or Password is wrong"
                return render(request, "login.html", {'error': error})
        else:
            print("username refused")
            error = "User is not registered"
            return render(request, "login.html", {'error': error})
    else:
        print("it's not post")
        return render(request, "login.html", {})

def dashboard(request):
    Result = []
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    id = str(r.hmget('usersList:', request.session['username']))[3:-2]
    for x in r.lrange('timeline:%s'%id, 0, -1):
        print(str(x)[2:-1])
        text = str(r.hget(str(x)[2:-1],'Text'))[2:-1]
        username = str(r.hget(str(x)[2:-1],'Username'))[2:-1]
        posted = str(r.hget(str(x)[2:-1],'Posted'))[2:-1]
        posted_id = str(r.hget(str(x)[2:-1],'Post_ID'))[2:-1]
        like = str(r.hget(str(x)[2:-1],'Like'))[2:-1]
        time_to_share = str(r.hget(str(x)[2:-1],'time_to_share'))[2:-1]
# 'b'Text''
        mono = {'Text' : text , 'Username':username,'Posted':posted,'Post_ID':posted_id ,'Like':like,'time_to_share':time_to_share}
       # print(mono)
        Result.append(mono)
    print(Result)
    return render(request, "dashboard.html", {'Result' : Result})


def follower(request):
    Result = []
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    if r.exists("follower:"+request.session['username']):
        for x in r.lrange("follower:"+request.session['username'],0,-1):
            Result.append(str(x)[2:-1])
        return render(request, "follower.html", {'Result' : Result})
    else:
        return render(request, "follower.html", {})

def following(request):
    Result = []
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    if r.exists("following:"+request.session['username']):
        for x in r.lrange("following:"+request.session['username'],0,-1):
            Result.append(str(x)[2:-1])
        return render(request, "following.html", {'Result' : Result})
    else:
        return render(request, "following.html", {})

@csrf_exempt
def search(request):
    Result = []
    if request.method == "POST" or request.is_ajax():
        if request.POST['Search'] is not None:
            print("post search")
            r = redis.StrictRedis(host='localhost', port=6379, db=0)
            username = request.POST['Search']
            id = str(r.hmget('usersList:', username))[3:-2]
            if (r.hexists('usersList:',username)):
                if ( not (username == request.session['username']) ):
                    follow_now = False
                    print(r.lrange("following:"+request.session['username'],0,-1))
                    for x in range (0,r.llen("following:"+request.session['username'])):
                        following_name = str(r.lindex("following:"+request.session['username'], x))[2:-1]
                        following_id = str(r.hmget('usersList:', following_name))[3:-2]
                        if id == following_id:
                            print("you are following this person now")
                            follow_now = True
                    if not follow_now :
                        print("FOLLOW NOW")
                        Result.append({"Username": username})

        if Result is not None :
            return HttpResponse(json.dumps(Result), content_type="application/json")
        else:
            return HttpResponse("No Success")
    else:
      return render(request, "search.html", {})


def followaction(request):
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    requested_username = request.GET.get('id')
    id = str(r.hmget('usersList:', request.session['username']))[3:-2]
    uid = str(r.hmget('usersList:', requested_username))[3:-2]
    print("follow action")
    print(r.hget('usersList:', requested_username))
    print(r.lrange("following:"+request.session['username'],0,-1))
    if r.hget('usersList:', requested_username):
        r.lpush("following:"+request.session['username'],requested_username)
        #r.zadd("following:" + request.session['username'], requested_username , time())
        r.lpush("follower:"+requested_username,request.session['username'])
        #r.zadd("follower:" + requested_username, request.session['username'],time())
        following = r.llen("following:" + request.session['username'])
        followers = r.llen("follower:" + requested_username)
        r.hset('user:%s' % id, 'following', following)  # Update the known size of the following
        r.hset('user:%s' % uid,'followers', followers)  # and followers list in each user’s HASH.
        r.hset('follow time:%s'%id,requested_username,datetime.now())
        available = True
        for x in  r.lrange('tweets:%s'%uid,0,-1):
            print("tweets")
            print(x)
            try:
                index_value = r.lrange('tweets:%s' %id, 0, -1).index(x)
            except ValueError:
                index_value = -1
            print("index value"+str(index_value))
            if index_value > -1:
                available = False
            if available:
                r.lpush('timeline:%s' % id, str(x)[2:-1])
            print(r.lrange('timeline:%s' % id,0,-1))
            #r.lpush('tweets:%s'%id, str(x)[2:-1])
        return HttpResponseRedirect("/dashboard/following")
    else:
        return HttpResponseRedirect("/dashboard/search")

def unfollowaction(request):
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    requested_username = request.GET.get('id')#[2:-1]
    print(requested_username)
    print(r.hgetall('usersList:'))
    if r.hget('usersList:', requested_username):
        print("oomad too unfollow")
        r.lrem("following:"+request.session['username'],0,requested_username)
        r.lrem("follower:"+requested_username,0,request.session['username'])
        id = str(r.hmget('usersList:', request.session['username']))[3:-2]
        uid = str(r.hmget('usersList:', requested_username))[3:-2]
        following = r.llen("following:" + request.session['username'])
        followers = r.llen("follower:" + requested_username)
        r.hset('user:%s' % id, 'following', following)  # Update the known size of the following
        r.hset('user:%s' % uid, 'followers', followers)  # and followers list in each user’s HASH.
        #r.zrem("following_info:"+request.session['username'],requested_username)
        #r.zrem("followers_info:" + request.session['username'],request.session['username'])
        for x in r.lrange('tweets:%s' % uid, 0, -1):
            r.lrem('timeline:%s' % id,1, str(x)[2:-1])
        return HttpResponseRedirect("/dashboard/following")
    else:
        return HttpResponseRedirect("/dashboard/following")


def addtweet(request):
   if request.method == 'POST':
       if request.POST['tweet'] is not None:
          r = redis.StrictRedis(host='localhost', port=6379, db=0)
          id = str(r.hmget('usersList:', request.session['username']))[3:-2]
          #pid = r.llen('tweets:%s'%id)
          pid = r.incr('status:id:')
          print("add PID    "+str(pid))
          r.lpush('tweets:%s'%id,"message:%s"%pid)
          r.lpush('timeline:%s'%id,"message:%s"%pid)
          posted_time = datetime.now()
          text = request.POST['tweet']
          r.hmset("message:%s"%pid,{
              'Text':text,
              'Username':request.session['username'],
              'Posted': posted_time,
              'Post_ID': pid,
              'Like': 0,
              'time_to_share':0,
          })
          r.hset("all message :",text,pid)
          #r.zadd("public page :",posted_time,pid)
          r.lpush("public :","message:%s"%pid )
          post_number = r.llen('tweets:%s'%id)
          r.hset('user:%s' % id,'posts',post_number)
          for x in range(0, r.llen("follower:"+request.session['username'])):
              follower_name = str(r.lindex("follower:" + request.session['username'], x))[2:-1]
              follower_id = str(r.hmget('usersList:', follower_name))[3:-2]
              availabe = True
              for x in r.lrange('timeline:%s'%follower_id,0,-1):
                  if "message:%s:"%pid == str(x)[2:-1]:
                      availabe = False
              if availabe:
                 r.lpush('timeline:%s'%follower_id,"message:%s"%pid)

          text = str(r.hget("message:%s" % pid, 'Text'))[2:-1]
          tag = text.split("#")
          #print(tag)
          #print("hashtags:")
          for x in range(1, len(tag)):
              #print("x :    ("+str(tag[0])+")")
              hashtag = tag[x].split()[0]
              print(hashtag)
              new = True
              for x in r.lrange("hashtag:",0,-1):
                  #print(str(x)[2:-1])
                  if str(x)[2:-1] == "hashtag:%s"%hashtag:  #used before
                      print("use befor")
                      r.hincrby("hashtag:%s"%hashtag,'time_to_use',1)
                      #r.zincrby("hashtag :","hashtag:%s"%hashtag , 1)
                      r.zrem("hashtag :", "hashtag:%s" % hashtag)
                      r.zadd("hashtag :", float(str(r.hget("hashtag:%s" % hashtag, 'time_to_use'))[2:-1]),
                             "hashtag:%s" % hashtag)
                      new = False
              if new:         # new hashtag
                print("new hashtag")
                r.hmset("hashtag:%s"%hashtag,{
                        'Text': hashtag,
                        'time_to_use':1,
                    })
                r.lpush("hashtag:","hashtag:%s"%hashtag)
                r.zadd("hashtag :", float(str(r.hget("hashtag:%s" % hashtag, 'time_to_use'))[2:-1]),
                       "hashtag:%s" % hashtag)


          print("hashtag score")
          print(r.zscore("hashtag :", "hashtag:%s" % hashtag))

          print("hashtag    ")
          print(r.zrange("hashtag :",0,-1))
          return HttpResponseRedirect("/dashboard/tweets")
   else:
       return HttpResponseRedirect("/dashboard/tweets")

def tweets(request):
    Result = []
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    #for x in r.lrange("tweet:"+request.session['username'],0,-1):
    id = str(r.hmget('usersList:', request.session['username']))[3:-2]
    print(id)
    print("teweets in tweet:    "+str(r.llen('tweets:%s'%id)))
    for x in r.lrange('tweets:%s'%id, 0, -1):
        text = str(r.hget(str(x)[2:-1], 'Text'))[2:-1]
        username = str(r.hget(str(x)[2:-1], 'Username'))[2:-1]
        posted = str(r.hget(str(x)[2:-1], 'Posted'))[2:-1]
        posted_id = str(r.hget(str(x)[2:-1], 'Post_ID'))[2:-1]
        like = str(r.hget(str(x)[2:-1], 'Like'))[2:-1]
        time_to_share = str(r.hget(str(x)[2:-1], 'time_to_share'))[2:-1]

        mono = {'Text' : text , 'Username':username,'Posted':posted,'Post_ID':posted_id ,'Like':like,'time_to_share':time_to_share}
        # print(mono)
        Result.append(mono)
    return render(request, "tweets.html", {'Result' : Result})

def deltweet(request):
    if request.GET.get('Post_ID') is not None:
        r = redis.StrictRedis(host='localhost', port=6379, db=0)
        print("in del function")
        pid = request.GET.get('Post_ID')
        id = str(r.hmget('usersList:', request.session['username']))[3:-2]
        if (str(r.hget("message:%s" % pid,'Username'))[2:-1] == request.session['username']):
            r.lrem('tweets:%s'%id,0,"message:%s"%pid)
            r.lrem('timeline:%s' % id, 0, "message:%s" % pid)
            r.lrem('shared:%s' % id, 0, pid)
            post_number = r.llen('tweets:%s' % id)
            r.hset('user:%s' % id, 'posts', post_number)
            #r.zrem("public page :",pid)
            r.lrem("public :",0, "message:%s" % pid)
            r.lrem("user_Likes:%s" %id, 0, pid)
            #r.zrem("user Likes:%s" % id, pid)
            r.hdel('like time:%s' % id, "message:%s" % pid)
            r.hdel('share time:%s' % id, "message:%s" % pid)
            for x in range(0, r.llen("follower:" + request.session['username'])):
                follower_name = str(r.lindex("follower:" + request.session['username'], x))[2:-1]
                follower_id = str(r.hmget('usersList:', follower_name))[3:-2]
                r.lrem('timeline:%s' % follower_id,1, "message:%s" % pid)
                r.lrem('tweets:%s'% follower_id, 1, "message:%s" % pid)
                r.lrem("user_Likes:%s" % follower_id,0, pid)
                #r.zrem("user Likes:%s" % follower_id, pid)
                r.lrem('shared:%s' % follower_id, 1, pid)
            r.lrem("user_Likes:%s" % id,0, pid)
            r.delete(request.session['username'] + pid)
            r.delete("message:%s" % pid)
        return HttpResponseRedirect("/dashboard/tweets")
    else:
        return HttpResponseRedirect("/dashboard/tweets")

@csrf_exempt
def like_post(request):
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    print("in like function")
    id = str(r.hmget('usersList:', request.session['username']))[3:-2]
    pid = request.GET.get('Post_ID')
    print(request)
    like = True
    print("PID  :" + str(pid))
    for x in r.lrange("user_Likes:%s" % id, 0, -1):
        p = int(str(x)[2:-1])
        if (p == int(pid)):
            r.lrem("user_Likes:%s" % id, 0, pid)
            #r.zrem("user Likes:%s" % id, pid)
            r.hdel('like time:%s' % id, "message:%s" % pid)
            like_number = int(str(r.hget("message:%s" % pid, 'Like'))[2:-1]) - 1
            print("like karde ghablan")
            like = False
    if like:
        print("like shod")
        r.lpush("user_Likes:%s" % id, pid)
        #r.zadd("user Likes:%s" % id, datetime.now(),pid)
        r.hset('like time:%s'%id,"message:%s" % pid,datetime.now())
        print("message" + str(pid))
        print(r.hgetall("message:%s" % pid))
        print(r.hgetall("all message :"))
        like_number = int(str(r.hget("message:%s" % pid, 'Like'))[2:-1]) + 1
    r.hset("message:%s" % pid, 'Like', like_number)
    print("number of like   :   " + str(like_number))
    return HttpResponseRedirect("/dashboard/likelog")        # new name like log


def share_action(request):
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    id = str(r.hmget('usersList:', request.session['username']))[3:-2]
    pid = request.GET.get('Post_ID')
    share = True
    print("PID  :" + str(pid))
    print(r.lrange('shared:%s'%id, 0, -1))
    for x in r.lrange('shared:%s'%id, 0, -1):
        s = str(x)[2:-1]
        if (s == str(pid)):
            r.lrem('shared:%s' % id, 0, pid)
            r.lrem('tweets:%s' % id,1, "message:%s" % pid)
            r.lrem('timeline:%s' % id,1, "message:%s" % pid)
            share_number = int(str(r.hget("message:%s" % pid, 'time_to_share'))[2:-1]) - 1
            for x in range(0, r.llen("follower:" + request.session['username'])):
                follower_name = str(r.lindex("following:" + request.session['username'], x))[2:-1]
                follower_id = str(r.hmget('usersList:', follower_name))[3:-2]
                r.lrem('timeline:%s' % follower_id,1, "message:%s" % pid)
            print("share karde ghablan")
            share = False
            break
    if share:
        print("share shod")
        #r.zadd('user_shared:%s'%id,datetime.now(),pid)
        r.lpush('shared:%s' % id, pid)
        r.hset('share time:%s' % id, "message:%s" % pid, datetime.now())
        share_number = int(str(r.hget("message:%s" % pid, 'time_to_share'))[2:-1]) + 1
        r.lpush('tweets:%s' % id, "message:%s" % pid)
        print("new list")
        print(r.lrange('tweets:%s' % id,0,-1))
        r.lpush('timeline:%s' % id, "message:%s" % pid)
        post_number = r.llen('tweets:%s' % id)
        r.hset('user:%s' % id, 'posts', post_number)
        for x in range(0, r.llen("follower:" + request.session['username'])):
            follower_name = str(r.lindex("following:" + request.session['username'], x))[2:-1]
            follower_id = str(r.hmget('usersList:', follower_name))[3:-2]
            r.lpush('timeline:%s' % follower_id, "message:%s" % pid)
    r.hset("message:%s" % pid, 'time_to_share', share_number)
    print("after share")
    print(r.lrange('shared:%s' % id,0,-1))
    #print(r.lrange('timeline:%s' % id,0,-1))
    #print(r.lrange('tweets:%s' % id, 0, -1))
    return HttpResponseRedirect("/dashboard/retweetlog")

@csrf_exempt
def search_hashtag(request):
    Result = []
    print("search hashtag")
    if request.method == "POST" or request.is_ajax():
        print("it is post")
        if request.POST['Search'] is not None:
            print("not none")
            print("hashtag search")
            r = redis.StrictRedis(host='localhost', port=6379, db=0)
            hashtag = request.POST['Search']
            counter = 0
            for x in r.lrange("hashtag:", 0, -1):
                if str(x)[2:-1] == "hashtag:%s" % hashtag:
                    for y in r.lrange("public :",0,-1):
                        print(r.hget(str(y)[2:-1],'Text'))
                        if str(r.hget(str(y)[2:-1],'Text'))[2:-1].find("#"+hashtag) != -1 :
                            print("find")
                            counter = counter +1
                            h =  str(y)[2:-1]
                            text = str(r.hget(h, 'Text'))[2:-1]
                            username = str(r.hget(h, 'Username'))[2:-1]
                            posted = str(r.hget(h, 'Posted'))[2:-1]
                            posted_id = str(r.hget(h, 'Post_ID'))[2:-1]
                            like = str(r.hget(h, 'Like'))[2:-1]
                            time_to_share = str(r.hget(h, 'time_to_share'))[2:-1]
                            mono = {'Text': text, 'Username': username, 'Posted': posted, 'Post_ID': posted_id,
                                    'Like': like, 'time_to_share': time_to_share}
                            # print(mono)
                            Result.append(mono)
                        if counter == 0:
                            r.lrem("hashtag:",0,"hashtag:%s" % hashtag)     #post that contain this hashtag was deleted
                            r.zrem("hashtag :", "hashtag:%s" % hashtag)
                    #r.hset("hashtag:%s" % hashtag, 'time_to_use',counter)
                    #r.zrem("hashtag :","hashtag:%s" % hashtag)
                    #r.zadd("hashtag :", "hashtag:%s" % hashtag,counter)
        print(Result)

        if Result is not None:
            return HttpResponse(json.dumps(Result), content_type="application/json")
        else:
            return HttpResponse("No Success")
    else:
        return render(request, "hashtag.html", {})

def useful_hashtag(request):
    Result = []
    print("useful hashtag")
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    for x in r.zrange("hashtag :",0, 9):
        print(x)
        print(r.hget(str(x)[2:-1], 'Text'))
        print(r.hget(str(x)[2:-1], 'time_to_use'))
        Result.append({'Text': str(r.hget(str(x)[2:-1], 'Text'))[2:-1],
                       'time_to_use': str(r.hget(str(x)[2:-1], 'time_to_use'))[2:-1]})
    print(Result)
    return render(request, "useful_hashtag.html", {'Result': Result})

def public_page(request):
    #createuser_fromfile()
    #followaction_fromfile()
    addtweet_fromfile()
    Result = []
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    for x in r.lrange("public :", 0, -1):
        text = str(r.hget(str(x)[2:-1], 'Text'))[2:-1]
        username = str(r.hget(str(x)[2:-1], 'Username'))[2:-1]
        posted = str(r.hget(str(x)[2:-1], 'Posted'))[2:-1]
        posted_id = str(r.hget(str(x)[2:-1], 'Post_ID'))[2:-1]
        like = str(r.hget(str(x)[2:-1], 'Like'))[2:-1]
        time_to_share = str(r.hget(str(x)[2:-1], 'time_to_share'))[2:-1]

        mono = {'Text': text, 'Username': username, 'Posted': posted, 'Post_ID': posted_id, 'Like': like,
                'time_to_share': time_to_share}
        # print(mono)
        Result.append(mono)
    return render(request, "public_page.html", {'Result': Result})


def createuser_fromfile():
    conn = redis.StrictRedis(host='localhost', port=6379, db=0)
    ifile = open('test.csv',"r")
    reader = csv.reader(ifile)
    Result = []
    rownum = 0
    print(reader)
    for row in reader :
        print("row")
        print(row)
        valid = True
        colnum =0
        for col in row:
            if colnum == 0:
                username = col
                colnum += 1
            else:
                password = col
        ##############################################
        if conn.hget('usersList:', username):
            print("invalid username")
            Result.append(username)
            valid = False
        if valid :
            id = conn.incr('user:id:')
            conn.hset('usersList:', username, id)
            conn.hmset('user:%s' % id, {
                'username': username,
                'id': id,
                'followers': 0,
                'following': 0,
                'posts': 0,
                'signup': datetime.now(),
                })
            conn.hmset('user_info:%s' % id, {
                'username': username,
                'id': id,
                'password': password,
                })
    return True

def addtweet_fromfile():
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    ifile = open('tweet.csv', "r")
    reader = csv.reader(ifile)
    print(reader)
    rownum =0
    for row in reader:
        print("row")
        print(row)
        colnum = 0
        for col in row:
            if colnum == 0:
                username = col
                colnum += 1
            else:
                text = col
        rownum +=1
        ##############################################
        if rownum != 1:
            id = str(r.hmget('usersList:',username))[3:-2]
            pid = r.incr('status:id:')
            r.lpush('tweets:%s' % id, "message:%s" % pid)
            r.lpush('timeline:%s' % id, "message:%s" % pid)
            posted_time = datetime.now()
            r.hmset("message:%s" % pid, {
                'Text': text,
                'Username': username,
                'Posted': posted_time,
                'Post_ID': pid,
                'Like': 0,
                'time_to_share': 0,
            })
            r.hset("all message :", text, pid)
            #r.zadd("public page :", posted_time, pid)
            r.lpush("public :", "message:%s" % pid)
            post_number = r.llen('tweets:%s' % id)
            r.hset('user:%s' % id, 'posts', post_number)
            for x in range(0, r.llen("follower:" + username)):
                follower_name = str(r.lindex("follower:" + username, x))[2:-1]
                follower_id = str(r.hmget('usersList:', follower_name))[3:-2]
                availabe = True
                for x in r.lrange('timeline:%s' % follower_id, 0, -1):
                    if "message:%s:" % pid == str(x)[2:-1]:
                        availabe = False
                if availabe:
                    r.lpush('timeline:%s' % follower_id, "message:%s" % pid)

            text = str(r.hget("message:%s" % pid, 'Text'))[2:-1]
            tag = text.split("#")
            for x in range(1, len(tag)):
                hashtag = tag[x].split()[0]
                new = True
                for x in r.lrange("hashtag:", 0, -1):
                    if str(x)[2:-1] == "hashtag:%s" % hashtag:  # used before
                        print("use befor")
                        r.hincrby("hashtag:%s" % hashtag, 'time_to_use', 1)
                        # r.zincrby("hashtag :","hashtag:%s"%hashtag , 1)
                        new = False
                if new:  # new hashtag
                    print("new hashtag")
                    r.hmset("hashtag:%s" % hashtag, {
                        'Text': hashtag,
                        'time_to_use': 1,
                    })
                    r.lpush("hashtag:", "hashtag:%s" % hashtag)
    return True

def followaction_fromfile():
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    ifile = open('follow.csv', "r")
    reader = csv.reader(ifile)
    print(reader)
    rownum = 0
    for row in reader:
        print("row")
        print(row)
        colnum = 0
        for col in row:
            if colnum == 0:
                username = col
                colnum += 1
            else:
                requested_username = col
        rownum += 1
        ##############################################
        if rownum != 1:
            id = str(r.hmget('usersList:', username))[3:-2]
            uid = str(r.hmget('usersList:', requested_username))[3:-2]
            print("follow action")
            print(r.hget('usersList:', requested_username))
            print(r.lrange("following:" + username, 0, -1))
            if r.hget('usersList:', requested_username):
                r.lpush("following:" + username, requested_username)
                # r.zadd("following:" + request.session['username'], requested_username , time())
                r.lpush("follower:" + requested_username, username)
                # r.zadd("follower:" + requested_username, request.session['username'],time())
                following = r.llen("following:" + username)
                followers = r.llen("follower:" + requested_username)
                r.hset('user:%s' % id, 'following', following)  # Update the known size of the following
                r.hset('user:%s' % uid, 'followers', followers)  # and followers list in each user’s HASH.
                r.hset('follow time:%s' % id, requested_username, datetime.now())
                available = True
                for x in r.lrange('tweets:%s' % uid, 0, -1):
                    try:
                        index_value = r.lrange('tweets:%s' % id, 0, -1).index(x)
                    except ValueError:
                        index_value = -1
                    print("index value" + str(index_value))
                    if index_value > -1:
                        available = False
                    if available:
                        r.lpush('timeline:%s' % id, str(x)[2:-1])
                    print(r.lrange('timeline:%s' % id, 0, -1))
    return True


def share_action_fromfile(request):
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    file_path = request.POST['path']
    wb = open_workbook(file_path)
    for s in wb.sheets():
        values = []
        for row in range(s.nrows):
            col_value = []
            username = (s.cell(row, 1).value)
            try:
                username = str(int(username))
            except:
                pass
            text = (s.cell(row, 1).value)
            try:
                text = str(int(text))
            except:
                pass
            like = (s.cell(row, 1).value)
            try:
               like = str(int(like))
            except:
               pass
        for x in r.lrange("public :",0,-1):
            if str(r.hget("message:%s"%x,'Text'))[3:-2] == text:
                pid = x
                break
        id = str(r.hmget('usersList:', username))[3:-2]
        pid = request.GET.get('id')
        #r.zadd('user_shared:%s' % id, datetime.now(),pid)
        r.lpush('shared:%s' % id, pid)
        r.lpush('tweets:%s' % id, "message:%s" % pid)
        r.lpush('timeline:%s' % id, "message:%s" % pid)
        post_number = r.llen('tweets:%s' % id)
        r.hset('user:%s' % id, 'posts', post_number)
        for x in range(0, r.llen("follower:" + username)):
            follower_name = str(r.lindex("following:" + username, x))[2:-1]
            follower_id = str(r.hmget('usersList:', follower_name))[3:-2]
            r.lpush('timeline:%s' % follower_id, "message:%s" % pid)

    return HttpResponseRedirect("/dashboard/tweets")            #new name

def log_page(request):
    return render(request, "log_page.html", {})

def likelog(request):
    Result = []
    print("like")
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    id = str(r.hmget('usersList:', request.session['username']))[3:-2]
    for x in r.lrange("user_Likes:%s" % id,0,-1):
        mono = {'Text': str(r.hget("message:%s"%str(x)[2:-1],'Text'))[2:-1],'Time':str(r.hget('like time:%s'%id,"message:%s"%str(x)[2:-1]))[2:-1]}
        Result.append(mono)
    print(Result)
    return render(request, "likelog.html", {'Result': Result})

def retweetlog(request):
    Result = []
    print("retweet")
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    id = str(r.hmget('usersList:', request.session['username']))[3:-2]
    for x in r.lrange("shared:%s" % id, 0, -1):
        mono = {'Text': str(r.hget("message:%s" % str(x)[2:-1], 'Text'))[2:-1],
                'Time': str(r.hget('share time:%s' % id, "message:%s" % str(x)[2:-1]))[2:-1]}
        Result.append(mono)
    print(Result)
    return render(request, "retweetlog.html", {'Result': Result})

def followlog(request):
    Result = []
    print("follow")
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    id = str(r.hmget('usersList:', request.session['username']))[3:-2]
    for x in r.lrange("following:"+request.session['username'], 0, -1):
        mono = {'Username': str(x)[2:-1] ,'Time': str(r.hget('follow time:%s' % id, str(x)[2:-1]))[2:-1]}
        Result.append(mono)
    print(Result)
    return render(request, "followlog.html", {'Result': Result})