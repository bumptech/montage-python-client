from diesel import quickstart, quickstop
from montageclient import MontageClient
from user_palm import UserInfo

# run with montage/examples/basic_proxy.hs

def test_many(cl, bucket):
    data = UserInfo(uid=1)

    mos = [ cl.new_montage_object(bucket, str(i), data.dumps()) for i in xrange(0,2) ]
    ref = cl.put_many(mos)
    found = cl.get_many([(bucket, str(i)) for i in xrange(0,2) ])

    assert len(ref) == len(found), "Num put %d and num found %d don't match" % (len(ref), len(found))
    for (r, f) in zip(ref, found):
        assert r.data == f.data, "put data does not match found data"
    print "\nsuccessfully matched put many with get many\n"

def main():
    cl = MontageClient('localhost', 7078)

    test_many(cl, 'u-info')
    quickstop()

quickstart(main)
