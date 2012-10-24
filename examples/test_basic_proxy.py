from diesel import quickstart, quickstop
from montage import MontageClient
from user_palm import UserEvent, UserName, UserInfo

# run with montage/examples/basic_proxy.hs

def test_resolution(cl, bucket, key):
    mos = [ cl.newMontageObject(bucket, key, UserInfo(uid=1)) for i in xrange(0,2) ]
    ref = cl.put_many(mos)
    assert len(ref) != 0, "Nothing put in riak"

    resolved = cl.get(bucket, key)
    assert resolved != None, "Did not resolve puts to a single point"
    print "\npassed resolution"

def test_delete(cl, bucket, key):
    cl.delete(bucket, key)
    gone = cl.get(bucket, key)
    assert gone == None, "value still persists after delete"
    print "\npassed delete"

def test_many(cl, bucket):
    mos = [ cl.newMontageObject(bucket, str(i), UserInfo(uid=1)) for i in xrange(0,2) ]
    ref = cl.put_many(mos)
    found = cl.get_many([(bucket, str(i)) for i in xrange(0,2) ])

    assert len(ref) == len(found), "Num put %d and num found %d don't match" % (len(ref), len(found))
    for (r, f) in zip(ref, found):
        assert r.data == f.data, "put data does not match found data"
    print "\npassed put many and get many identity"

def main():
    cl = MontageClient('localhost', 7078)

    bucket = 'u-info'
    key = str(1)

    test_resolution(cl, bucket, key)
    test_delete(cl, bucket, key)
    test_many(cl, bucket)
    print "\npassed all tests\n"
    quickstop()

quickstart(main)
