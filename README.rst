========================
Python Client for Montage
========================

Install
=======

Recommended Python 2.7

From montage-python-client/ execute::

    python setup.py install

To setup montage itself, see github.com/bumptech/montage

===========
Examples
===========
To setup the examples execute::

    cd examples && ./build_test_protos.sh

You must have montage installed to run the basic proxy which the examples talk with.  In your montage/ directory::

    cd examples && runhaskell basic_proxy.hs

See github.com/bumptech/montage for more on the montage haskell setup.

A Basic Resolution
===========

The montage/examples/basic_proxy defines resolutions for three simple protocol-buffers: UserInfo, UserEvent, and UserName (view them in montage-python-client/examples/user.proto).

To see a basic last write wins resolution in action, throw UserInfo data at montage, at the same bucket and key destination, and query that bucket and key pair::

    from montage import MontageClient
    from user_palm import UserInfo

    # UserInfo is a constructor with one required integer field, uid

    client = MontageClient('localhost', 7078)

    bucket = 'u-info'
    key = '1'

    data_1 = UserInfo(uid=4393)
    first = client.put(bucket, key, data_1.dumps())
    data_2 = UserInfo(uid=4920)
    second = client.put(bucket, key, data_2.dumps())

    resolved = client.get(bucket, key)
    assert UserInfo(resolved.data) == data_2, "Failed last write wins"

The type signatures of get and put::

    # Haskell-style
    # where vclock is optional and obj has fields 'data', 'bucket', 'key', 'vclock'

    put :: String -> String -> ByteString -> Maybe ByteString -> Object
    put bucket key data vclock = obj

    get :: String -> String -> Object
    get bucket key = obj

'put' returns the data stored in riak, which comes equipped with an assigned vclock (obj.vclock).

The montage-python-client sends requests to montage over a zmq socket using diesel.  To execute the above code, wrap the above logic in a function that can be diesel quickstarted::

    from diesel import quickstart
    from montage import MontageClient
    from user_palm import UserInfo

    def resolve():
        client = MontageClient('localhost', 7078)
	...
	assert UserInfo(resolved.data) == data_2, "Failed last write wins"

    quickstart(resolve)

Delete
===========

To delete the data you just resolved (above)::

    from montage import MontageClient

    client = MontageClient('localhost', 7078)

    bucket = 'u-info'
    key = '1'
    client.delete(bucket, key)

Batches
===========

Montage supports batch commands, which means getting from many destinations, or putting data in many destinations.  The put many interface requires the building of a newMontageObject::

    from montage import MontageClient
    from user_palm import UserInfo, UserEvent

    client = MontageClient('localhost', 7078)

    bucket = 'u-info'
    key = '2'
    data = UserInfo(uid=3244)
    mo_ui = client.newMontageObject(bucket, key, data.dumps())

    bucket = 'u-event'
    key = '1'
    data = UserEvent(eid=1301)
    mo_ue = client.newMontageObject(bucket, key, data.dumps())

    what_was_put = client.put_many([mo_ui, mo_ue])

Likewise, if you desire to get from many destination, you may do so by ordering your requests as (bucket, key) pairs in a list::

    found = client.get_many([('u-info', '2'), ('u-event', '1')])

    assert found[0].data == mo_ui.data
    assert found[1].data == mo_ue.data

    found = client.get_many([('u-info', '2'), ('u-whatever', '1')])

    assert found[1] == None

The response is a list the same length of the request: the (bucket, key) pairs are exactly replaced with either a value found or None.

Reference Gets
===========

A reference get request is two chained get requests, where the first lookup produces a value that is used as the key for the second lookup.

If we've defined a way to transform a datatype to a bytestring key (as we've done for UserInfo in basic_proxy), we first deposit data that can be chained::

    # basic_proxy defines a transformation from UserInfo's uid -> key

    from montage import MontageClient
    from user_palm import UserInfo, UserEvent

    client = MontageClient('localhost', 7078)

    refdata = UserInfo(uid=2) # key for targets
    reference = cl.put('u-info', str(1), refdata.dumps())

    target1data = UserEvent(eid=3)
    target1 = client.put('u-event', str(2), target1data.dumps())

    target2data = UserName(name="montage")
    target2 = client.put('u-name', str(2), target2data.dumps())

Then to make the reference get requests::

    (referenceFound, valuesFound) = client.get_by_('u-info', str(1), ['u-event', 'u-name'])

    assert UserInfo(referenceFound.data) == reference
    assert len(valuesFound) == 2
    assert (valuesFound[0] is not None) and (valuesFound[1] is not None)
    assert UserEvent(valuesFound[0].data) == target1data
    assert UserName(valuesFound[1].data) == target2data

The values returned by a reference get request will be ordered to match the buckets given.  If the reference get failed to return one of the values, it will be None in the valuesFound list.

There is also a client.get_by method which only returns valuesFound in the case that you don't care about the intermediate (referenceFound) lookup object.  This object, though, can be useful if you need to do another lookup conditionally on referenceFound.
