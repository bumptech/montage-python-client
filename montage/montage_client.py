import time
import uuid
import sys

from diesel import first
from diesel.util.pool import ConnectionPool
from diesel.protocols.zeromq import DieselZMQSocket, zctx, zmq

from montage_palm import *

packet_to_id = {MontageGet: MONTAGE_GET,
                MontageGetReference: MONTAGE_GET_REFERENCE,
                MontageGetResponse: MONTAGE_GET_RESPONSE,
                MontagePut:MONTAGE_PUT,
                MontagePutResponse: MONTAGE_PUT_RESPONSE,
                MontageCommand: MONTAGE_COMMAND,
                MontageCommandResponse: MONTAGE_COMMAND_RESPONSE,
                MontageDelete: MONTAGE_DELETE,
                MontageDeleteResponse: MONTAGE_DELETE_RESPONSE,
                }
id_to_packet = dict((v, k) for k, v in packet_to_id.iteritems())

def default_logger(system, event, **kw):
    params = simplejson.dumps(kw)
    sys.stderr.write("%s: %s timestamp=%f, params=%s" %
                     (system, event, time.time(), params))

class RiakException(Exception):
    pass

class MontageRequestTimeout(Exception):
    def __init__(self, msg):
        super(MontageRequestTimeout, self).__init__(msg)
        self.riak_key = None
        self.riak_bucket = None

    def __str__(self):
        exception_msg = super(MontageRequestTimeout, self).__str__()
        bucket = self.riak_bucket if self.riak_bucket is not None else "unknown"
        return "%s (bucket=%r)" % (exception_msg, bucket)

class MontageClient(object):
    # __init__ :: string -> int -> (int) -> (f(start, result)) -> client
    def __init__(self, host, port, timeout=30, logger=default_logger):
        self._sock = DieselZMQSocket(zctx.socket(zmq.REQ), connect="tcp://%s:%d" % (host, port))
        self.timeout = timeout
        self.logger = logger
        self.is_closed = False

    def close(self):
        self.is_closed = True
        self._sock.__exit__()
        self._sock = None

    @property
    def sock(self):
        assert self._sock is not None, 'The socket has already been closed'
        return self._sock

    def _monitor_get(self, start, result):
        duration = time.time() - start
        if duration > 1:
            self.logger('DB', 'SLOW_FETCH',
                        action='MONTAGE_GET',
                        bucket=bucket,
                        key=key,
                        duration=duration,
                        length=len(result.data) if result else 0)
        if result and len(result.data) > 2097152: # two megabytes
            self.logger('DB', 'BIG_FETCH',
                        action='MONTAGE_GET',
                        bucket=bucket,
                        key=key,
                        duration=duration,
                        length=len(result.data))
        if result and result.fetch_resolutions__exists and result.fetch_resolutions > 10:
            self.logger('DB', 'MANY_SIBLINGS_FETCH',
                        action='MONTAGE_GET',
                        bucket=bucket,
                        key=key,
                        duration=duration,
                        length=len(result.data),
                        num_siblings=result.fetch_resolutions)

    # get :: bucket -> key -> MontageObject
    def get(self, bucket, key):
        req = MontageGet(bucket=bucket,key=key)

        start = time.time()
        resp = self._do_request(bucket, key, req)

        assert len(resp.status) == 1, \
               'There should only be one status response'
        assert len(resp.subs) == 0, \
               'There should not be any subqueries'

        status = resp.status[0]
        if status == MISSING:
            return None
        if status == EXISTS:
            self._monitor_get(start, resp.master)
            return resp.master
        else:
            raise RiakException('Error fetching from magicd (b=%s, k=%s)' % (bucket, key))

    def _get_subs(self, start, resp):
        out = []
        i = 0
        for status in resp.status:
            if status == MISSING:
                out.append(None)
            if status == EXISTS:
                sub = resp.subs[i]
                self._monitor_get(start, sub)
                out.append(sub)
                i += 1
        assert i == len(resp.subs), "incomplete status list"
        return out

    # get_many :: [(bucket, key)] -> [MontageObject]
    def get_many(self, buckets_keys):
        req = MontageGetMany()
        req.gets.set(buckets_keys)

        assert len(resp.status) == len(buckets_keys), \
            'You should receive as many status responses as you requested'

        start = time.time()
        resp = self._do_request(bucket, key, req)
        return self._get_subs(start, resp)

    # get_by :: bucket -> key -> [target_bucket] -> [MontageObject]
    def get_by(self, bucket, key, targets):
        return self.get_by_(bucket=bucket, key=key, targets=targets)[1]

    # returns ref key (as MontageObject) along with values
    # get_by_ :: bucket -> key -> [target_bucket] -> (MontageObject, [MontageObject])
    def get_by_(self, bucket, key, targets):
        req = MontageGetReference(bucket=bucket, key=key)
        req.target_buckets.set(targets)

        start = time.time()
        resp = self._do_request(bucket, key, req)
        return (resp.master, self._get_subs(start, resp))

    # delete :: bucket -> key -> ()
    def delete(self, bucket, key):
        req = MontageDelete(bucket=bucket, key=key)
        resp = self._do_request(bucket, key, req)

        assert isinstance(resp, MontageDeleteResponse), \
               'Delete should always get DeleteResponse back'

    # put :: bucket -> key -> data -> (vclock) -> obj
    def put(self, bucket, key, data, vclock=None):
        obj = MontageObject(bucket=bucket, key=key)
        obj.data = data # can't be part of the constructor because of a palm bug
        if vclock:
            obj.vclock = vclock
        req = MontagePut(object=obj)

        resp = self._do_request(bucket, key, req)

        if resp.modified:
            return resp.object
        else:
            return None

    # put_many :: bucket -> key -> [data] -> (vclock) -> [obj]
    def put_many(self, bucket, key, datas, vclock=None):
        obj = MontageObject(bucket=bucket, key=key)
        objs = []
        for data in datas:
            obj_ = obj.copy()
            obj_.data = data
            if vclock:
                obj_.vclock = vclock
            objs.append(obj_)
        req = MontagePutMany()
        req.objects.set(objs)
        resp = self._do_request(bucket, key, req)
        return resp.object

    def command(self, command, argument):
        req = MontageCommand(command=command,
                             argument=argument)
        resp = self._do_request(None, None, req)
        return resp

    def _do_request(self, bucket, key, req):
        try:
            return self.recv(self.send(req))
        except MontageRequestTimeout, e:
            e.riak_bucket = bucket
            e.riak_key = key
            raise

    def send(self, req):
        id = uuid.uuid4()
        out_pb = MontageEnvelope(mtype=packet_to_id[type(req)],
                               msg=req.dumps(),
                               msgid=id.bytes)
        self.sock.send(out_pb.dumps())
        return id

    def recv(self, matchid=None):
        evt, frame = first(waits=[self.sock], sleep=self.timeout)
        if evt == 'sleep':
            err = "Timed out after %.2f secs waiting for zmq frame"
            raise MontageRequestTimeout(err % self.timeout)

        env = MontageEnvelope(frame.bytes)
        if matchid:
            assert env.msgid == matchid.bytes, "request/response id pairs did not match!"

        if env.mtype == MONTAGE_ERROR:
            raise RiakException(MontageError(env.msg).error)

        return id_to_packet[env.mtype](env.msg)

# montage_pool :: string -> int -> (int) -> (int) -> pool
def montage_pool(host, port, timeout=30, logger=default_logger, pool_size=5):
    return ConnectionPool(lambda: MontageClient(host, port,
                                                timeout=timeout,
                                                logger=logger),
                          lambda conn: conn.close(),
                          pool_size=pool_size)

"""
    # only one status, in a list, corresponding to master
    # what would happen if this wasn't there?
    def __get(self, bucket, key, req):
        resp = self._do_request(bucket, key, req)

        assert len(resp.status) == 1, \
               'There should only be one status response'
        assert len(resp.subs) == 0, \
               'There should not be any subqueries'

        status = resp.status[0]
        if status == MISSING:
            return None
        elif status == EXISTS:
            return resp.master
        else:
            raise RiakException('Error fetching from magicd (b=%s, k=%s)' % (bucket, key))
"""
