from diesel import quickstart, quickstop
from montageclient import MontageClient
from user_palm import UserEvent, UserName, UserInfo

# run with montage/examples/basic_proxy.hs

def main():
    cl = MontageClient('localhost', 7078)

    refdata = UserInfo(uid=2)
    ref = cl.put('u-info', str(1), refdata.dumps())

    target1data = UserEvent(eid=3)
    target1 = cl.put('u-event', str(2), target1data.dumps())

    target2data = UserName(name="montage")
    target2 = cl.put('u-name', str(2), target2data.dumps())

    (refObj, values) = cl.get_by('u-info', str(1), ['u-event', 'u-name'])
    assert UserInfo(refObj.data) == refdata, "reference key found did not match"
    assert len(values) == 2, "incorrect num values"
    assert values[0] is not None, "Could not retrieve u-event data, nothing found"
    assert values[1] is not None, "Could not retrieve u-name data, nothing found"
    assert UserEvent(values[0].data) == target1data, "value 1 found did not match"
    assert UserName(values[1].data) == target2data, "value 2 found did not match"
    print "\npassed reference get identity\n"
    quickstop()

quickstart(main)
