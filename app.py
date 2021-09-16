import bottle
import redis
import settings
import logging
import json

app = application = bottle.default_app()

def rate(fn):
    def _wrap(*args, **kwargs):
        ip = bottle.request.environ.get('REMOTE_ADDR')
        try:
            r = connect(settings.ratelimit_db)
        except:
            generic_message = 'There was a problem comunicating with the database.'
            bottle.response.status = 501
            return bottle.template('error.html', generic_message=generic_message, detailed_message=False)
        try:
            atempts = r.get(ip)
            if not atempts:
                atempts = bytes([1])
        except Exception as e:
            generic_message = 'There was a problem'
            bottle.response.status = 500
            return bottle.template('error.html', generic_message=generic_message, detailed_message=False)
        atempts = bytes_to_int(atempts)
        atempts += 1
        r.setex(ip, 5, int_to_bytes(atempts))
        if atempts > 10 :
            generic_message = 'Please stop'
            bottle.response.status = 439
            return bottle.template('error.html', generic_message=generic_message, detailed_message=False)
        return fn(*args, **kwargs)
    return _wrap


def bytes_to_int(b):
    return (int.from_bytes(b, "big"))


def int_to_bytes(i):
    return (bytes([i]))


def connect(db=settings.db):
    return redis.StrictRedis(settings.redis_host, port=settings.redis_port, db=db)


def update_redis(key, message, ttl=3600):
  r = connect()
  h = r.setex(key, ttl, message)
  return h


@bottle.post('/')
def add_message():
    try:
        byte = bottle.request.body
        data = json.loads(byte.read().decode('UTF-8'))
    except:
        bottle.response.status = 400
        return {'status':400, 'message':'Wrong input parameters'}
    try:
        r = connect()
    except:
        generic_message = 'There was a problem comunicating with the database.'
        bottle.response.status = 500
        return {'status':500, 'message':generic_message}
    if update_redis(data['key'], data['message'], data['ttl']):
        generic_message = 'Message stored in database'
        bottle.response.status = 200
        return {'status':200, 'message':generic_message, 'link':f'{settings.uri}/{data["key"]}'}
    else:
        bottle.response.status = 500
        return {'status':500, 'message':generic_message}


@bottle.get('/')
@rate
def display_message():
    detailed_message = 'This message has been deleted and will not be visible again'
    try:
        r = connect()
    except:
        generic_message = 'There was a problem comunicating with the database.'
        bottle.response.status = 500
        return bottle.template('error.html', generic_message=generic_message, detailed_message=False)
    try:
        uniq_link = bottle.request.query.uniq_link
    except:
        bottle.response.status = 200
        return bottle.template('index.html')
    try:
        message = r.get(uniq_link)
        ttl = r.ttl(uniq_link)
        if not message:
            generic_message = 'Welcome'
            detailed_message = '''
This is a one time message delivery application.
Intructions and so on will be added.
But this is it for tonight.
            '''
            bottle.response.status = 200
            return bottle.template('index.html', generic_message=generic_message, detailed_message=detailed_message)
    except Exception as e:
        generic_message = 'No message found on that link'
        bottle.response.status = 200
        return bottle.template('index.html', generic_message=generic_message, detailed_message=False)
    if uniq_link in ['hello']:
        detailed_message = '^This is the message <- this is a static thing.'
    else:
        try:
            r.delete(uniq_link)
        except:
            bottle.response.status = 500
            generic_message = 'Failed to delete message'
            detailed_message = f'''
Since the message was not deleted we will not send it.
If the error persist please contact the system owner.

Time left before your message expires: {ttl}
            '''
            return bottle.template('error.html', generic_message=generic_message, detailed_message=detailed_message)
    bottle.response.status = 200
    return bottle.template('index.html', generic_message=message, detailed_message=detailed_message)


if __name__ == '__main__':
    bottle.run(host='0.0.0.0', port=8080, debug=False, reloader=True)