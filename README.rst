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

To see a basic last write wins resolution in action, throw UserInfo data at montage, at the same bucket and key destination, and ask for it back::

    from montage import MontageClient
    from user_palm import UserInfo

    # UserInfo is a constructor with one required integer field, uid

    client = MontageClient('localhost', 7078)

    bucket = 'u-info'
    key = '1'

    data_1 = UserInfo(uid=1)
    first = client.put(bucket, key, data_1.dumps())
    data_2 = UserInfo(uid=2)
    second = client.put(bucket, key, data_2.dumps())

    resolved = client.get(bucket, key)
    assert UserInfo(resolved.data) == data_2, "Failed last write wins"

The type signatures of get and put::

    # pseudo C-style
    # where vclock is optional and obj has fields 'data', 'bucket', 'key', 'vclock'
    obj put(string bucket, string key, bytestring data, bytestring vclock);

    obj get(string bucket, string key);

    # Haskell-style
    put :: String -> String -> ByteString -> Maybe ByteString -> Object
    put bucket key data vclock = obj

    get :: String -> String -> Object
    get bucket key = obj

The montage-python-client sends requests to montage over a zmq socket using diesel.  To execute the above code, wrap the above logic in a function that can be diesel quickstarted::

    from diesel import quickstart
    from montage import MontageClient
    from user_palm import UserInfo

    def resolve():
        client = MontageClient('localhost', 7078)
	...
	assert UserInfo(resolved.data) == data_2, "Failed last write wins"

    quickstart(resolve)

(Add a diesel quickstop inside of your function, after your resolution logic, to tell diesel to close its connections when finished.)
