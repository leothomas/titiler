import docker
import os


def make_pkg():
    file_dir = os.path.dirname(os.path.abspath(__file__))
    client = docker.from_env()
    
    client.images.build(
        path=os.path.join(file_dir, "..", "lambda"),
        dockerfile="Dockerfile",
        tag="lambda:latest"
    )
    
    lambda_container = client.containers.run(
        name="lambda",
        image="lambda:latest",
        command='/bin/sh -c "cp /tmp/package.zip /mnt/output/package.zip"',
        volumes={
            "lambda": {"bind": "/mnt/output", "mode": "rw"},
        }
    )


make_pkg()