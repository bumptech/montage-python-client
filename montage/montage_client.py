import time
import uuid
import sys
import simplejson

from diesel import first
from diesel.util.pool import ConnectionPool
from diesel.protocols.zeromq import DieselZMQSocket, zctx, zmq

import montage_palm as proto

packet_to_id = {proto.MontageGet: proto.MONTAGE_GET,
                proto.MontageGetMany: proto.MONTAGE_GET_MANY,
                proto.MontageGetReference: proto.MONTAGE_GET_REFERENCE,
                proto.MontageGetResponse: proto.MONTAGE_GET_RESPONSE,
                proto.MontagePut: proto.MONTAGE_PUT,
                proto.MontagePutMany: proto.MONTAGE_PUT_MANY,
                proto.MontagePutResponse: proto.MONTAGE_PUT_RESPONSE,
                proto.MontagePutManyResponse: proto.MONTAGE_PUT_MANY_RESPONSE,
                proto.MontageCommand: proto.MONTAGE_COMMAND,
                proto.MontageCommandResponse: proto.MONTAGE_COMMAND_RESPONSE,
                proto.MontageDelete: proto.MONTAGE_DELETE,
                proto.MontageDeleteResponse: proto.MONTAGE_DELETE_RESPONSE,
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

    def new_montage_object(self, bucket, key, data, vclock=None):
        obj = proto.MontageObject(bucket=bucket, key=key)
        obj.data = data
        if vclock:
            obj.vclock = vclock
        return obj

    def _monitor_get(self, start, result):
        duration = time.time() - start
        if duration > 1:
            self.logger('DB', 'SLOW_FETCH',
                        action='MONTAGE_GET',
                        bucket=result.bucket,
                        key=result.key,
                        duration=duration,
                        length=len(result.data) if result else 0)
        if result and len(result.data) > 2097152: # two megabytes
            self.logger('DB', 'BIG_FETCH',
                        action='MONTAGE_GET',
                        bucket=result.bucket,
                        key=result.key,
                        duration=duration,
                        length=len(result.data))
        if result and result.fetch_resolutions__exists and result.fetch_resolutions > 10:
            self.logger('DB', 'MANY_SIBLINGS_FETCH',
                        action='MONTAGE_GET',
                        bucket=result.bucket,
                        key=result.key,
                        duration=duration,
                        length=len(result.data),
                        num_siblings=result.fetch_resolutions)

    def get(self, bucket, key):
        req = proto.MontageGet(bucket=bucket,key=key)

        start = time.time()
        resp = self._do_request(req, bucket, key)

        assert len(resp.status) == 1, \
               'There should only be one status response'
        assert len(resp.subs) == 0, \
               'There should not be any subqueries'

        status = resp.status[0]
        if status == proto.MISSING:
            return None
        if status == proto.EXISTS:
            self._monitor_get(start, resp.master)
            return resp.master
        else:
            raise RiakException('Error fetching from magicd (b=%s, k=%s)' % (bucket, key))

    def _get_subs(self, start, resp):
        out = []
        i = 0
        for status in resp.status:
            if status == proto.MISSING:
                out.append(None)
            if status == proto.EXISTS:
                sub = resp.subs[i]
                self._monitor_get(start, sub)
                out.append(sub)
                i += 1
        assert i == len(resp.subs), "incomplete status list"
        return out

    def get_many(self, buckets_keys):
        req = proto.MontageGetMany()
        for (b, k) in buckets_keys:
            req.gets.append(proto.MontageGet(bucket=b, key=k))

        start = time.time()
        resp = self._do_request(req)

        assert len(resp.status) == len(buckets_keys), \
            'You should receive as many status responses as you requested'

        return self._get_subs(start, resp)

    def get_by(self, bucket, key, targets):
        req = proto.MontageGetReference(bucket=bucket, key=key)
        req.target_buckets.set(targets)

        start = time.time()
        resp = self._do_request(req, bucket, key)
        return (resp.master, self._get_subs(start, resp))

    def delete(self, bucket, key):
        req = proto.MontageDelete(bucket=bucket, key=key)
        resp = self._do_request(req, bucket, key)

        assert isinstance(resp, proto.MontageDeleteResponse), \
               'Delete should always get DeleteResponse back'

    def put(self, bucket, key, data, vclock=None):
        obj = self.new_montage_object(bucket, key, data, vclock)
        req = proto.MontagePut(object=obj)
        resp = self._do_request(req)

        if resp.modified:
            return resp.object
        else:
            return None

    def put_many(self, mos):
        req = proto.MontagePutMany()
        req.objects.set(mos)
        resp = self._do_request(req)
        return [ r.object for r in resp.objects ]

    def command(self, command, argument):
        req = proto.MontageCommand(command=command,
                             argument=argument)
        resp = self._do_request(req)
        return resp

    def _do_request(self, req, bucket=None, key=None):
        try:
            return self.recv(self.send(req))
        except MontageRequestTimeout, e:
            e.riak_bucket = bucket
            e.riak_key = key
            raise

    def send(self, req):
        id = uuid.uuid4()
        out_pb = proto.MontageEnvelope(mtype=packet_to_id[type(req)],
                               msg=req.dumps(),
                               msgid=id.bytes)
        self.sock.send(out_pb.dumps())
        return id

    def recv(self, matchid=None):
        evt, frame = first(waits=[self.sock], sleep=self.timeout)
        if evt == 'sleep':
            err = "Timed out after %.2f secs waiting for zmq frame"
            raise MontageRequestTimeout(err % self.timeout)

        env = proto.MontageEnvelope(frame.bytes)
        if matchid:
            assert env.msgid == matchid.bytes, "request/response id pairs did not match!"

        if env.mtype == proto.MONTAGE_ERROR:
            raise RiakException(proto.MontageError(env.msg).error)

        return id_to_packet[env.mtype](env.msg)

def montage_pool(host, port, timeout=30, logger=default_logger, pool_size=5):
    return ConnectionPool(lambda: MontageClient(host, port,
                                                timeout=timeout,
                                                logger=logger),
                          lambda conn: conn.close(),
                          pool_size=pool_size)
