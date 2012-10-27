from diesel import quickstart, quickstop
from montageclient import MontageClient
from user_palm import UserInfo

# run with montage/examples/basic_proxy.hs

def test_resolution(cl, bucket, key):
    [data_1, data_2, data_3] = [ UserInfo(uid=i) for i in xrange(1,4) ]

    first = cl.put(bucket, key, data_1.dumps())
    second = cl.put(bucket, key, data_2.dumps())
    third = cl.put(bucket, key, data_3.dumps())

    resolved = cl.get(bucket, key)
    assert UserInfo(resolved.data) == data_3, "Failed last write wins resolution"
    print "\nsuccessfully did last write wins resolution\n"

def main():
    cl = MontageClient('localhost', 7078)

    test_resolution(cl, 'u-info', '1')
    quickstop()

quickstart(main)
