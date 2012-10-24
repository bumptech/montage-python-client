from setuptools import setup

def build_pb():
    import os
    print 'building protobuf modules...'
    assert os.system("palmc ./ montage/") == 0

build_pb()

VERSION = "0.1.0"

setup(name="montage",
      version=VERSION,
      author="Bump Technologies, Inc.",
      author_email="dev@bumptechnologies.com",
      packages=["montage"],
      install_requires=[
        "palm",
        "diesel",
        "simplejson",
    ],
      )
