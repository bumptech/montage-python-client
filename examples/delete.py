from diesel import quickstart, quickstop
from montageclient import MontageClient
from user_palm import UserInfo

# run with montage/examples/basic_proxy.hs

def test_delete(cl, bucket, key):
    data = UserInfo(uid=1)
    put = cl.put(bucket, key, data.dumps())

    cl.delete(bucket, key)
    gone = cl.get(bucket, key)
    assert gone == None, "value still persists after delete"
    print "\nsuccessfully did delete\n"

def main():
    cl = MontageClient('localhost', 7078)

    test_delete(cl, 'u-info', '1')
    quickstop()

quickstart(main)
