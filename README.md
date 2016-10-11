# Diffuser - Automatic cluster deployment tool for distributed filesystems in cloud infrastructures

![KOALA](images/Diffusor_logo.png)

Diffuser is an automatic cluster deployment tool for distributed filesystems in cloud infrastructures (IaaS).

It is designed to help users to deploy a bunch of virtual server instances inside AWS-compatible cloud infrastructures and connect them via popular distributed filesystems.

## Motivation for the development of Diffuser

Working with public or private cloud infrastructures (e.g. Amazon EC2, Eucalyptus, OpenNebula or Nimbus) is simple but deploying a cluster of virtual server instances that have a distributed filesystem already up and running is a complex and time-consuming task.

Diffuser is a command-line tool, written in Python, that is designed to automate this task and create an already connected cluster within minutes.

The following distributed filesystems are implemented inside Diffuser:

- NFS
- GlusterFS (with redundancy)
- GlusterFS (without redundancy)
- Ceph
- PVFS2

It's easy to implement support for more distributed filesystems.

## The way Diffuser works

Diffuser is a command-line application. Python 2.5 or newer is required. The software uses [boto](https://github.com/boto/boto), a Python interface to the [Amazon Web Services](https://aws.amazon.com) to start the virtual server instances. The deployment and configuration of the distributed filesystem is done via the SSH module [paramiko](https://github.com/paramiko/paramiko).

When running Diffuser, the user need to select one of the supported distributed filesystems. The configuration parameters can be modified inside Diffuser's configuration file.
