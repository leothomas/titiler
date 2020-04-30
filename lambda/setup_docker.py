# coding=utf-8

"""
Testing docker setup using docker-py
"""

import docker
import os


def make_pkg():
    """ Testing docker setup using docker-py"""
    # file_dir = os.path.dirname(os.path.abspath(__file__))
    client = docker.from_env()
    code_dir = "./lambda"
    client.images.build(path=code_dir, dockerfile="Dockerfile", tag="lambda:latest")
    client.containers.run(
        image="lambda:latest",
        command="/bin/sh -c 'cp /tmp/package.zip /local/package.zip'",
        remove=True,
        volumes={os.path.abspath(code_dir): {"bind": "/local/", "mode": "rw"}},
        user=0,
    )


make_pkg()
