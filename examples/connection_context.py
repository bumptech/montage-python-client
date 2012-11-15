import diesel

from montageclient import MontageClient


def main():
    print "entering 'with' block using MontageClient ..."
    with MontageClient('localhost', 8087) as c:
        print "  got connection", c
        assert not c.is_closed
        print "  connection.is_closed ==", c.is_closed
    assert c.is_closed
    print "... left 'with' block"
    print "connection.is_closed ==", c.is_closed
    print
    print "entering 'with' block using MontageClient ..."
    try:
        with MontageClient('localhost', 8087) as c:
            print "  got connection", c
            assert not c.is_closed
            assert 0
    except AssertionError:
        assert c.is_closed
        print "exception caught, connection closed, all is well"
    diesel.quickstop()

diesel.set_log_level(diesel.loglevels.ERROR)
diesel.quickstart(main)
