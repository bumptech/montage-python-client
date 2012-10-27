from setuptools import setup

def build_pb():
    import os
    print 'building protobuf modules...'
    assert os.system("palmc ./ montageclient/") == 0
    assert os.system("palmc ./examples/ ./examples/") == 0

build_pb()

VERSION = "0.1.0"

setup(name="montageclient",
      version=VERSION,
      author="Bump Technologies, Inc.",
      author_email="dev@bumptechnologies.com",
      packages=["montageclient"],
      install_requires=[
        "palm",
        "diesel",
        "simplejson",
    ],
      )
