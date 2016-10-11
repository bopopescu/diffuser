#!/usr/bin/env python

from boto.ec2.connection import *
from boto.ec2 import *
import time
import base64
import getpass
import os
import socket
import sys
import traceback
import paramiko
import ConfigParser

config = ConfigParser.RawConfigParser()
# Where is the config file
config.read('config.cfg')

# Get values from the config file
AccessKey       = config.get('CREDENTIALS', 'AccessKey')
SecretAccessKey = config.get('CREDENTIALS', 'SecretAccessKey')

AMI             = config.get('INSTANCES', 'AMI')
InstanceType    = config.get('INSTANCES', 'InstanceType')
KEY             = config.get('INSTANCES', 'KEY')
zone            = config.get('INSTANCES', 'AvailabilityZone')

EBS_Size        = config.getint('EBS', 'EBS_Size_GB')
device          = config.get('EBS', 'EBS_Device')

port            = config.getint('SSH', 'Port')
username        = config.get('SSH', 'Username')
password        = config.get('SSH', 'Password')
logfile         = config.get('SSH', 'Logfile')
paramiko.util.log_to_file(logfile)

privatekeyfile  = config.get('SSH', 'PrivateKeyFile')
key = paramiko.RSAKey.from_private_key_file(privatekeyfile)

# Connect with the Region
conn_us_east = boto.ec2.connect_to_region(zone, aws_access_key_id=AccessKey,
aws_secret_access_key=SecretAccessKey, is_secure = False)

print("Welcome to DIFFUSER")

print

print("What distributed filesystem do you want?")
print("(1) NFS")
print("(2) GlusterFS (with redundancy)")
print("(3) GlusterFS (without redundancy)")
print("(4) Ceph")
print("(5) PVFS2")

print

filesystem = input('Please enter a number: ')

if filesystem == 1:
  print "You chose NFS"
  ANZ         = config.getint('NFS', 'ANZ')
elif filesystem == 2:
  print "GlusterFS (with redundancy)" 
  ANZ         = config.getint('GlusterFS', 'ANZ')
  ANZ_Server  = config.getint('GlusterFS', 'ANZ_Server')
elif filesystem == 3:
  print "GlusterFS (without redundancy)" 
  ANZ         = config.getint('GlusterFS', 'ANZ')
  ANZ_Server  = config.getint('GlusterFS', 'ANZ_Server')
elif filesystem == 4:
  print "Ceph" 
  ANZ         = config.getint('Ceph', 'ANZ')
  ANZ_Server  = config.getint('Ceph', 'ANZ_Server')
elif filesystem == 5:
  print "PVFS2" 
  ANZ         = config.getint('PVFS2', 'ANZ')
  ANZ_Server  = config.getint('PVFS2', 'ANZ_Server')
else:
  sys.exit(1)

try:
  # Try to get a list of all regions inside this cloud infrastructure
  liste_regionen = conn_us_east.get_all_regions()
except EC2ResponseError:
  # An error occured
  print "While the system tried to get a list of all regions inside this cloud infrastructure, an error occured." 
else:
  # Number of elements inside the list
  laenge_liste_regionen = len(liste_regionen)
  print "List of Regions inside this cloud infrastructure: "   
  for i in range(laenge_liste_regionen):
    print str(liste_regionen[i].name)
    
print 

print "You have chosen: "+zone
    
print 

try:
  # Try to get a list of all zones inside this region
  liste_zonen = conn_us_east.get_all_zones()
except EC2ResponseError:
  # An error occured
  print "While the system tried to get a list of all availability zones inside this region, an error occured." 
else:
  # Number of elements inside the list
  laenge_liste_zonen = len(liste_zonen)
  print "List of availability zones inside this region: "   
  for i in range(laenge_liste_zonen):
    print str(liste_zonen[i].name)
      
print        

try:
  # Try to create the instances
  reservation = conn_us_east.run_instances(AMI, key_name=KEY, instance_type=InstanceType, min_count=ANZ, max_count=ANZ)
except EC2ResponseError:
  # An error occured
  print "While the system tried to start the instances, an error occured." 
else:
  # Number of elements inside the list
  laenge_liste_reservation_instances = len(reservation.instances)
  print str(laenge_liste_reservation_instances)+" instances were created successfully: "   
  for i in range(laenge_liste_reservation_instances):
    print str(reservation.instances[i].id)
    
print     

# Give the system some time to create the instances
time.sleep(5) 

print "Your instances are now being started."  

print     

# Wait until all instances are started
laufende_instanzen = 0
while laufende_instanzen < len(reservation.instances):
  laufende_instanzen = 0
  for inst in reservation.instances:
      if inst.update() == u'running':
          laufende_instanzen += 1
  print "Running instances:", laufende_instanzen
  time.sleep(1)

print

print "Your instances are running now."  

print   

for inst in reservation.instances:
  print "Public DNS from instance", str(inst.id), ":", str(inst.public_dns_name)

if filesystem == 1:
  # Here comes NFS
  
  # Get the first instance. It will be the server
  zone = reservation.instances[0].placement
  instance_id = reservation.instances[0].id
  
  print  
  
  try:
    # try to create the EBS volume
    neues_volume = conn_us_east.create_volume(EBS_Size, zone, snapshot=None)
  except EC2ResponseError:
    # An error occured
    print "While the system tried to create the EBS volume, an error occured." 
  else:
    print "The EBS volume "+neues_volume.id+" was created successfully." 
  
  # Give the system some time to create the volume
  time.sleep(5)
  
  print
  
  try:
    # try to attach EBS volumne with the fist instance
    neues_volume_anhaengen = conn_us_east.attach_volume(neues_volume.id, instance_id, device)
  except EC2ResponseError:
    # An error occured
    print "While the system tried to attach the EBS volume with the instance "+str(instance_id)+", an error occured." 
  else:
    print "Volume "+neues_volume.id+" was attached with the instance "+str(instance_id)+" successfully." 
  
  # Give the system some time to start the instances
  time.sleep(10)
 
  # Deploy the server
  try:
      client = paramiko.SSHClient()
      client.load_system_host_keys()
      client.set_missing_host_key_policy(paramiko.WarningPolicy)
      # auto-accept unknown keys
      client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
      print 'Connecting...'
      client.connect(reservation.instances[0].public_dns_name, port, username, password, key)
      chan = client.invoke_shell()
      print repr(client.get_transport())
      print 'The system creates the NFS server.'
      print
      stdin, stdout, stderr = client.exec_command(
            "sudo /bin/sh -c '"
            "hostname;"
            "apt-get update;"
            "apt-get -y install nfs-common nfs-kernel-server;"
            "echo y | sudo mkfs.ext3 /dev/sdc;"
            "sudo mkdir /mnt/export;"
            "mount /dev/sdc /mnt/export/;"
            "chmod o+wx /etc/exports;"
            "'")
      print stdout.readlines()
      print stderr.readlines()
      liste_der_maschinen = ""
  
      for i in range(ANZ):
        if i != 0:
          liste_der_maschinen = liste_der_maschinen + reservation.instances[i].public_dns_name+"(rw,sync,no_root_squash,no_subtree_check) "
  
      stdin, stdout, stderr = client.exec_command("sudo echo '/mnt/export  "+liste_der_maschinen+"' >> /etc/exports")
      print stdout.readlines()
      print stderr.readlines()
      stdin, stdout, stderr = client.exec_command(
            "sudo /bin/sh -c '"
            "chmod o-wx /etc/exports;"
            "exportfs -a;"
            "'")
      print stdout.readlines()
      print stderr.readlines()
      chan.close()
      client.close()
  
  except Exception, e:
      print '*** Caught exception: %s: %s' % (e.__class__, e)
      traceback.print_exc()
      try:
          client.close()
      except:
          pass
      sys.exit(1)
  
  
  # Deploy the client(s)
  for i in range(ANZ):
    if i != 0:
      try:
          client = paramiko.SSHClient()
          client.load_system_host_keys()
          client.set_missing_host_key_policy(paramiko.WarningPolicy)
          # auto-accept unknown keys
          client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
          print 'Connecting...'
          client.connect(reservation.instances[i].public_dns_name, port, username, password, key)
          chan = client.invoke_shell()
          print repr(client.get_transport())
          print 'The system creates the NFS clients.'
          print
          stdin, stdout, stderr = client.exec_command(
                "sudo /bin/sh -c '"
                "hostname;"
                "apt-get update;"
                "apt-get -y install nfs-common;"
                "mkdir /mnt/export;"
                "chmod o+wx /etc/fstab;"
                "echo "+reservation.instances[0].public_dns_name+":/mnt/export  /mnt/export  nfs  auto,rw,bg  0 0 >> /etc/fstab;"
                "chmod o-wx /etc/fstab;"
                "mount /mnt/export/;"
                "'")
          print stdout.readlines()
          print stderr.readlines()
          chan.close()
          client.close()
  
      except Exception, e:
          print '*** Caught exception: %s: %s' % (e.__class__, e)
          traceback.print_exc()
          try:
              client.close()
          except:
              pass
          sys.exit(1)
          
elif filesystem == 2:
  # Here comes GlusterFS with redundancy
  
  # Get the first two instances. They will be the server

  zone = reservation.instances[0].placement
  instance_id1 = reservation.instances[0].id
  instance_id2 = reservation.instances[1].id

  print  
    
  try:
    # try to create the EBS volume
    neues_volume1 = conn_us_east.create_volume(EBS_Size, zone, snapshot=None)
  except EC2ResponseError:
    # An error occured
    print "While the system tried to create the EBS volume, an error occured." 
  else:
    print "The EBS volume "+neues_volume1.id+" was created successfully." 
  
  # Give the system some time to create the volume
  time.sleep(5)

  print
  
  try:
    # try to attach EBS volumne with the fist instance
    neues_volume_anhaengen = conn_us_east.attach_volume(neues_volume1.id, instance_id1, device)
  except EC2ResponseError:
    # An error occured
    print "While the system tried to attach the EBS volume with the instance "+str(instance_id1)+", an error occured." 
  else:
    print "Volume "+neues_volume1.id+" was attached with the instance "+str(instance_id1)+" successfully." 
  
  print
  
  try:
    # try to create the EBS volume
    neues_volume2 = conn_us_east.create_volume(EBS_Size, zone, snapshot=None)
  except EC2ResponseError:
    # An error occured
    print "While the system tried to create the EBS volume, an error occured." 
  else:
    print "The EBS volume "+neues_volume2.id+" was created successfully." 
  
  # Give the system some time to create the volume
  time.sleep(5)

  print
  
  try:
    # try to attach EBS volumne with the fist instance
    neues_volume_anhaengen = conn_us_east.attach_volume(neues_volume2.id, instance_id2, device)
  except EC2ResponseError:
    # An error occured
    print "While the system tried to attach the EBS volume with the instance "+str(instance_id2)+", an error occured." 
  else:
    print "Volume "+neues_volume2.id+" was attached with the instance "+str(instance_id2)+" successfully." 
    
  # Give the system some time to start the instances
  time.sleep(10)
  
  

  
  # Configuration of server
  for i in range(ANZ_Server):
    if i != ANZ_Server:
      try:
        # Upload of file glusterfs-3.0.5.tar.gz to the server    
        hostname = reservation.instances[i].public_dns_name
      
        transport = paramiko.Transport((hostname, port))
        transport.connect(username = username, pkey = key)
      
        sftp = paramiko.SFTPClient.from_transport(transport)
      
        remotepath = '/tmp/glusterfs-3.0.5.tar.gz'
        localpath = 'glusterfs-3.0.5.tar.gz'
        sftp.put(localpath, remotepath)
      
        sftp.close()
        transport.close()
        
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.WarningPolicy)
        # auto-accept unknown keys
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        print 'Connecting...'
        client.connect(reservation.instances[i].public_dns_name, port, username, password, key)
        chan = client.invoke_shell()
        print repr(client.get_transport())
        print 'The system creates the GlusterFS server.'
        print
        stdin, stdout, stderr = client.exec_command("sudo hostname")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo apt-get update")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo apt-get -y install flex bison")
        print stdout.readlines()
        print stderr.readlines()
#        stdin, stdout, stderr = client.exec_command("sudo wget http://ftp.gluster.com/pub/gluster/glusterfs/3.0/LATEST/glusterfs-3.0.5.tar.gz -P /tmp/")
#        print stdout.readlines()
#        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo tar -xvzf /tmp/glusterfs-3.0.5.tar.gz -C /tmp/")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cd /tmp/glusterfs-3.0.5; ./configure --prefix='")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cd /tmp/glusterfs-3.0.5; make'")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cd /tmp/glusterfs-3.0.5; make install'")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo ldconfig")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo glusterfs --version")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'sudo echo y | mkfs.ext3 /dev/sdc'")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo chmod o+wx /etc/fstab")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo echo '/dev/sdc   /gluster   ext3   noatime   0   0' >> /etc/fstab")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo chmod o-wx /etc/fstab")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo mkdir /gluster")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo mount /gluster")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo mkdir /gluster/export")
        print stdout.readlines()
        print stderr.readlines()
  
        liste_der_maschinen = ""
  
        for i in range(ANZ_Server):
          if i != ANZ_Server:
            liste_der_maschinen = liste_der_maschinen + reservation.instances[i].public_dns_name+":/gluster/export "
  
        stdin, stdout, stderr = client.exec_command("sudo glusterfs-volgen --name repstore1 --raid 1 "+liste_der_maschinen)
        print stdout.readlines()
        print stderr.readlines()
  
        vol_datename = reservation.instances[i].public_dns_name+"-repstore1-export.vol"
        stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cp "+vol_datename+" /etc/glusterfs/glusterfsd.vol'")
        print stdout.readlines()
        print stderr.readlines()
  
        stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cp repstore1-tcp.vol /etc/glusterfs/glusterfs.vol'")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo glusterfsd -f /etc/glusterfs/glusterfsd.vol")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo ps -aux | grep gluster")
        print stdout.readlines()
        print stderr.readlines()
        chan.close()
        client.close()
  
      except Exception, e:
          print '*** Caught exception: %s: %s' % (e.__class__, e)
          traceback.print_exc()
          try:
              client.close()
          except:
              pass
          sys.exit(1)
  
  
  # Datei repstore1-tcp.vol vom 1.Server holen
  try:
    hostname = reservation.instances[0].public_dns_name
    transport = paramiko.Transport((hostname, port))
    transport.connect(username = username, pkey = key)
  
    sftp = paramiko.SFTPClient.from_transport(transport)
  
    filepath = '/home/ubuntu/repstore1-tcp.vol'
    localpath = 'repstore1-tcp.vol'
    sftp.get(filepath, localpath)
  
    sftp.close()
    transport.close()
  
  except Exception, e:
      print '*** Caught exception: %s: %s' % (e.__class__, e)
      traceback.print_exc()
      try:
          client.close()
      except:
          pass
      sys.exit(1)
  
  
  # Deploy the client(s)
  for i in range(ANZ):
    if i == (ANZ-1):
      try:
          # Upload of file glusterfs-3.0.5.tar.gz to the client    
          hostname = reservation.instances[i].public_dns_name
        
          transport = paramiko.Transport((hostname, port))
          transport.connect(username = username, pkey = key)
        
          sftp = paramiko.SFTPClient.from_transport(transport)
        
          remotepath = '/tmp/glusterfs-3.0.5.tar.gz'
          localpath = 'glusterfs-3.0.5.tar.gz'
          sftp.put(localpath, remotepath)
        
          sftp.close()
          transport.close()
        
          client = paramiko.SSHClient()
          client.load_system_host_keys()
          client.set_missing_host_key_policy(paramiko.WarningPolicy)
          # auto-accept unknown keys
          client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
          print 'Connecting...'
          client.connect(reservation.instances[i].public_dns_name, port, username, password, key)
          chan = client.invoke_shell()
          print repr(client.get_transport())
          print 'The system creates the GlusterFS clients.'
          print
          stdin, stdout, stderr = client.exec_command("sudo hostname")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo apt-get update")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo apt-get -y install flex bison")
          print stdout.readlines()
          print stderr.readlines()
#          stdin, stdout, stderr = client.exec_command("sudo wget http://ftp.gluster.com/pub/gluster/glusterfs/3.0/LATEST/glusterfs-3.0.5.tar.gz -P /tmp/")
#          print stdout.readlines()
#          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo tar -xvzf /tmp/glusterfs-3.0.5.tar.gz -C /tmp/")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cd /tmp/glusterfs-3.0.5; ./configure --prefix='")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cd /tmp/glusterfs-3.0.5; make'")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cd /tmp/glusterfs-3.0.5; make install'")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo ldconfig")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo glusterfs --version")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo modprobe fuse")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo mkdir /glusterfs")
          print stdout.readlines()
          print stderr.readlines()
  
          chan.close()
          client.close()
  
          # Datei repstore1-tcp.vol auf den Client hochladen        
          hostname = reservation.instances[i].public_dns_name
  
          transport = paramiko.Transport((hostname, port))
          transport.connect(username = username, pkey = key)
        
          sftp = paramiko.SFTPClient.from_transport(transport)
        
          remotepath = '/home/ubuntu/repstore1-tcp.vol'
          localpath = 'repstore1-tcp.vol'
          sftp.put(localpath, remotepath)
        
          sftp.close()
          transport.close()
          
  
      except Exception, e:
          print '*** Caught exception: %s: %s' % (e.__class__, e)
          traceback.print_exc()
          try:
              client.close()
          except:
              pass
          sys.exit(1)
  
  
  
  # Deploy the client(s)
  for i in range(ANZ):
    if i == (ANZ-1):
      try:
          client = paramiko.SSHClient()
          client.load_system_host_keys()
          client.set_missing_host_key_policy(paramiko.WarningPolicy)
          # auto-accept unknown keys
          client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
          print 'Connecting...'
          client.connect(reservation.instances[i].public_dns_name, port, username, password, key)
          chan = client.invoke_shell()
          print repr(client.get_transport())
          print 'The system creates the GlusterFS clients.'
          print
          stdin, stdout, stderr = client.exec_command("sudo hostname")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cp repstore1-tcp.vol /etc/glusterfs/'")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo mount -t glusterfs /etc/glusterfs/repstore1-tcp.vol /glusterfs")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo df")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo tail /var/log/glusterfs/glusterfs.log")
          print stdout.readlines()
          print stderr.readlines()
          chan.close()
          client.close()
  
      except Exception, e:
          print '*** Caught exception: %s: %s' % (e.__class__, e)
          traceback.print_exc()
          try:
              client.close()
          except:
              pass
          sys.exit(1)

elif filesystem == 3:
  # Here comes GlusterFS without redundancy

  # Get the first two instances. They will be the server
  zone = reservation.instances[0].placement
  instance_id1 = reservation.instances[0].id
  instance_id2 = reservation.instances[1].id

  print  
    
  try:
    # try to create the EBS volume
    neues_volume1 = conn_us_east.create_volume(EBS_Size, zone, snapshot=None)
  except EC2ResponseError:
    # An error occured
    print "While the system tried to create the EBS volume, an error occured." 
  else:
    print "The EBS volume "+neues_volume1.id+" was created successfully." 
  
  # Give the system some time to create the volume
  time.sleep(5)

  print
  
  try:
    # try to attach EBS volumne with the fist instance
    neues_volume_anhaengen = conn_us_east.attach_volume(neues_volume1.id, instance_id1, device)
  except EC2ResponseError:
    # An error occured
    print "While the system tried to attach the EBS volume with the instance "+str(instance_id1)+", an error occured." 
  else:
    print "Volume "+neues_volume1.id+" was attached with the instance "+str(instance_id1)+" successfully." 
  
  print
  
  try:
    # try to create the EBS volume
    neues_volume2 = conn_us_east.create_volume(EBS_Size, zone, snapshot=None)
  except EC2ResponseError:
    # An error occured
    print "While the system tried to create the EBS volume, an error occured." 
  else:
    print "The EBS volume "+neues_volume2.id+" was created successfully." 
  
  # Give the system some time to create the volume
  time.sleep(5)

  print
  
  try:
    # try to attach EBS volumne with the fist instance
    neues_volume_anhaengen = conn_us_east.attach_volume(neues_volume2.id, instance_id2, device)
  except EC2ResponseError:
    # An error occured
    print "While the system tried to attach the EBS volume with the instance "+str(instance_id2)+", an error occured." 
  else:
    print "Volume "+neues_volume2.id+" was attached with the instance "+str(instance_id2)+" successfully." 
    
  # Give the system some time to start the instances
  time.sleep(10)
  
  

  
  # Configuration of server
  for i in range(ANZ_Server):
    if i != ANZ_Server:
      try:
        # Upload of file glusterfs-3.0.5.tar.gz to the server    
        hostname = reservation.instances[i].public_dns_name
      
        transport = paramiko.Transport((hostname, port))
        transport.connect(username = username, pkey = key)
      
        sftp = paramiko.SFTPClient.from_transport(transport)
      
        remotepath = '/tmp/glusterfs-3.0.5.tar.gz'
        localpath = 'glusterfs-3.0.5.tar.gz'
        sftp.put(localpath, remotepath)
      
        sftp.close()
        transport.close()
        
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.WarningPolicy)
        # auto-accept unknown keys
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        print 'Connecting...'
        client.connect(reservation.instances[i].public_dns_name, port, username, password, key)
        chan = client.invoke_shell()
        print repr(client.get_transport())
        print 'The system creates the GlusterFS server.'
        print
        stdin, stdout, stderr = client.exec_command("sudo hostname")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo apt-get update")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo apt-get -y install flex bison")
        print stdout.readlines()
        print stderr.readlines()
#        stdin, stdout, stderr = client.exec_command("sudo wget http://ftp.gluster.com/pub/gluster/glusterfs/3.0/LATEST/glusterfs-3.0.5.tar.gz -P /tmp/")
#        print stdout.readlines()
#        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo tar -xvzf /tmp/glusterfs-3.0.5.tar.gz -C /tmp/")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cd /tmp/glusterfs-3.0.5; ./configure --prefix='")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cd /tmp/glusterfs-3.0.5; make'")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cd /tmp/glusterfs-3.0.5; make install'")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo ldconfig")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo glusterfs --version")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'sudo echo y | mkfs.ext3 /dev/sdc'")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo chmod o+wx /etc/fstab")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo echo '/dev/sdc   /gluster   ext3   noatime   0   0' >> /etc/fstab")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo chmod o-wx /etc/fstab")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo mkdir /gluster")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo mount /gluster")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo mkdir /gluster/export")
        print stdout.readlines()
        print stderr.readlines()
  
        liste_der_maschinen = ""
  
        for i in range(ANZ_Server):
          if i != ANZ_Server:
            liste_der_maschinen = liste_der_maschinen + reservation.instances[i].public_dns_name+":/gluster/export "
  
        stdin, stdout, stderr = client.exec_command("sudo glusterfs-volgen --name store1 "+liste_der_maschinen)
        print stdout.readlines()
        print stderr.readlines()
  
        vol_datename = reservation.instances[i].public_dns_name+"-store1-export.vol"
        stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cp "+vol_datename+" /etc/glusterfs/glusterfsd.vol'")
        print stdout.readlines()
        print stderr.readlines()
  
        stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cp store1-tcp.vol /etc/glusterfs/glusterfs.vol'")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo glusterfsd -f /etc/glusterfs/glusterfsd.vol")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo ps -aux | grep gluster")
        print stdout.readlines()
        print stderr.readlines()
        chan.close()
        client.close()
  
      except Exception, e:
          print '*** Caught exception: %s: %s' % (e.__class__, e)
          traceback.print_exc()
          try:
              client.close()
          except:
              pass
          sys.exit(1)
  
  
  # Datei repstore1-tcp.vol vom 1.Server holen
  try:
    hostname = reservation.instances[0].public_dns_name
    transport = paramiko.Transport((hostname, port))
    transport.connect(username = username, pkey = key)
  
    sftp = paramiko.SFTPClient.from_transport(transport)
  
    filepath = '/etc/glusterfs/glusterfs.vol'
    localpath = 'glusterfs.vol'
    sftp.get(filepath, localpath)
  
    sftp.close()
    transport.close()
  
  except Exception, e:
      print '*** Caught exception: %s: %s' % (e.__class__, e)
      traceback.print_exc()
      try:
          client.close()
      except:
          pass
      sys.exit(1)
  
  
  # Deploy the client(s)
  for i in range(ANZ):
    if i == (ANZ-1):
      try:
          # Upload of file glusterfs-3.0.5.tar.gz to the client    
          hostname = reservation.instances[i].public_dns_name
        
          transport = paramiko.Transport((hostname, port))
          transport.connect(username = username, pkey = key)
        
          sftp = paramiko.SFTPClient.from_transport(transport)
        
          remotepath = '/tmp/glusterfs-3.0.5.tar.gz'
          localpath = 'glusterfs-3.0.5.tar.gz'
          sftp.put(localpath, remotepath)
        
          sftp.close()
          transport.close()
        
          client = paramiko.SSHClient()
          client.load_system_host_keys()
          client.set_missing_host_key_policy(paramiko.WarningPolicy)
          # auto-accept unknown keys
          client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
          print 'Connecting...'
          client.connect(reservation.instances[i].public_dns_name, port, username, password, key)
          chan = client.invoke_shell()
          print repr(client.get_transport())
          print 'The system creates the GlusterFS clients.'
          print
          stdin, stdout, stderr = client.exec_command("sudo hostname")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo apt-get update")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo apt-get -y install flex bison")
          print stdout.readlines()
          print stderr.readlines()
#          stdin, stdout, stderr = client.exec_command("sudo wget http://ftp.gluster.com/pub/gluster/glusterfs/3.0/LATEST/glusterfs-3.0.5.tar.gz -P /tmp/")
#          print stdout.readlines()
#          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo tar -xvzf /tmp/glusterfs-3.0.5.tar.gz -C /tmp/")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cd /tmp/glusterfs-3.0.5; ./configure --prefix='")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cd /tmp/glusterfs-3.0.5; make'")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cd /tmp/glusterfs-3.0.5; make install'")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo ldconfig")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo glusterfs --version")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo modprobe fuse")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo mkdir /glusterfs")
          print stdout.readlines()
          print stderr.readlines()
  
          chan.close()
          client.close()
  
          # Datei repstore1-tcp.vol auf den Client hochladen        
          hostname = reservation.instances[i].public_dns_name
  
          transport = paramiko.Transport((hostname, port))
          transport.connect(username = username, pkey = key)
        
          sftp = paramiko.SFTPClient.from_transport(transport)
        
          remotepath = '/home/ubuntu/glusterfs.vol'
          localpath = 'glusterfs.vol'
          sftp.put(localpath, remotepath)
        
          sftp.close()
          transport.close()
          
  
      except Exception, e:
          print '*** Caught exception: %s: %s' % (e.__class__, e)
          traceback.print_exc()
          try:
              client.close()
          except:
              pass
          sys.exit(1)
  
  
  
  # Deploy the client(s)
  for i in range(ANZ):
    if i == (ANZ-1):
      try:
          client = paramiko.SSHClient()
          client.load_system_host_keys()
          client.set_missing_host_key_policy(paramiko.WarningPolicy)
          # auto-accept unknown keys
          client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
          print 'Connecting...'
          client.connect(reservation.instances[i].public_dns_name, port, username, password, key)
          chan = client.invoke_shell()
          print repr(client.get_transport())
          print 'The system creates the GlusterFS clients.'
          print
          stdin, stdout, stderr = client.exec_command("sudo hostname")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cp glusterfs.vol /etc/glusterfs/'")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo mount -t glusterfs /etc/glusterfs/glusterfs.vol /glusterfs")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo df")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo tail /var/log/glusterfs/glusterfs.log")
          print stdout.readlines()
          print stderr.readlines()
          chan.close()
          client.close()
  
      except Exception, e:
          print '*** Caught exception: %s: %s' % (e.__class__, e)
          traceback.print_exc()
          try:
              client.close()
          except:
              pass
          sys.exit(1)

elif filesystem == 4:
  # Here comes GlusterFS with redundancy
  
  # Get the first two instances. They will be the server

  zone = reservation.instances[0].placement
  instance_id1 = reservation.instances[0].id
  instance_id2 = reservation.instances[1].id

  print  
    
  try:
    # try to create the EBS volume
    neues_volume1 = conn_us_east.create_volume(EBS_Size, zone, snapshot=None)
  except EC2ResponseError:
    # An error occured
    print "While the system tried to create the EBS volume, an error occured." 
  else:
    print "The EBS volume "+neues_volume1.id+" was created successfully." 
  
  # Give the system some time to create the volume
  time.sleep(5)

  print
  
  try:
    # try to attach EBS volumne with the fist instance
    neues_volume_anhaengen = conn_us_east.attach_volume(neues_volume1.id, instance_id1, device)
  except EC2ResponseError:
    # An error occured
    print "While the system tried to attach the EBS volume with the instance "+str(instance_id1)+", an error occured." 
  else:
    print "Volume "+neues_volume1.id+" was attached with the instance "+str(instance_id1)+" successfully." 
  
  print
  
  try:
    # try to create the EBS volume
    neues_volume2 = conn_us_east.create_volume(EBS_Size, zone, snapshot=None)
  except EC2ResponseError:
    # An error occured
    print "While the system tried to create the EBS volume, an error occured." 
  else:
    print "The EBS volume "+neues_volume2.id+" was created successfully." 
  
  # Give the system some time to create the volume
  time.sleep(5)

  print
  
  try:
    # try to attach EBS volumne with the fist instance
    neues_volume_anhaengen = conn_us_east.attach_volume(neues_volume2.id, instance_id2, device)
  except EC2ResponseError:
    # An error occured
    print "While the system tried to attach the EBS volume with the instance "+str(instance_id2)+", an error occured." 
  else:
    print "Volume "+neues_volume2.id+" was attached with the instance "+str(instance_id2)+" successfully." 
    
  # Give the system some time to start the instances
  time.sleep(10)

  # Configuratin of server
  for i in range(ANZ_Server):
    if i != ANZ_Server:
      try:
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.WarningPolicy)
        # auto-accept unknown keys
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        print 'Connecting...'
        client.connect(reservation.instances[i].public_dns_name, port, username, password, key)
        chan = client.invoke_shell()
        print repr(client.get_transport())
        print 'The system creates the Ceph server.'
        print
        stdin, stdout, stderr = client.exec_command("sudo hostname")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo apt-get update")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo apt-get -y install git-core autoconf libtool libboost-dev libedit-dev libssl-dev libboost-all-dev")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo apt-get -y install btrfs-tools")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo apt-get -y install libfuse2 libfuse-dev gawk linux-ec2-source-2.6.32")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo apt-get -y install linux-headers-2.6.32-305-ec2 linux-image-2.6.32-305-ec2")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo tar -xvzf /usr/src/linux-ec2-source-2.6.32.tar.bz2 -C /usr/src")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo ln -s /usr/src/linux-ec2-source-2.6.32 /usr/src/linux")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo cp /boot/config-2.6.32-305-ec2 /usr/src/linux/.config")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cd /usr/src/linux; make archprepare && make scripts && make prepare && make modules_prepare'")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo cp /usr/src/linux-headers-2.6.32-305-ec2/Module.symvers /usr/src/linux/")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo wget http://ceph.newdream.net/download/ceph-0.20.tar.gz")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo wget http://ceph.newdream.net/download/ceph-kclient-0.20.tar.gz")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo tar -xvzf ceph-0.20.tar.gz")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cd ceph-0.20; ./autogen.sh'")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cd ceph-0.20; ./configure'")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cd ceph-0.20/src; make'")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cd ceph-0.20/src; make install'")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo mkdir /var/log/ceph")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo mkdir /etc/ceph")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo touch /etc/ceph/ceph.conf")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo chmod o+wx /etc/ceph/ceph.conf")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo echo '[global]' >> /etc/ceph/ceph.conf")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo echo '    pid file = /var/run/ceph/$name.pid' >> /etc/ceph/ceph.conf")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo echo '    debug ms = 1' >> /etc/ceph/ceph.conf")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo echo '[mon]' >> /etc/ceph/ceph.conf")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo echo '    mon data = /srv/ceph/mon' >> /etc/ceph/ceph.conf")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo echo '[mon0]' >> /etc/ceph/ceph.conf")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo echo '    host = "+reservation.instances[0].private_dns_name+"' >> /etc/ceph/ceph.conf")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo echo '    mon addr = "+reservation.instances[0].private_dns_name+":6789' >> /etc/ceph/ceph.conf")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo echo '[mds]' >> /etc/ceph/ceph.conf")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo echo '[mds0]' >> /etc/ceph/ceph.conf")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo echo '    host = "+reservation.instances[0].private_dns_name+"' >> /etc/ceph/ceph.conf")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo echo '[osd]' >> /etc/ceph/ceph.conf")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo echo '    sudo = true' >> /etc/ceph/ceph.conf")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo echo '    osd data = /data/osd' >> /etc/ceph/ceph.conf")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo echo '[osd0]' >> /etc/ceph/ceph.conf")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo echo '    host = "+reservation.instances[0].private_dns_name+"' >> /etc/ceph/ceph.conf")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo echo '    btrfs devs = /dev/sdc' >> /etc/ceph/ceph.conf")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo echo '[osd1]' >> /etc/ceph/ceph.conf")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo echo '    host = "+reservation.instances[1].private_dns_name+"' >> /etc/ceph/ceph.conf")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo echo '    btrfs devs = /dev/sdc' >> /etc/ceph/ceph.conf")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo cat /etc/ceph/ceph.conf")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo chmod o-wx /etc/ceph/ceph.conf")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo mkcephfs -c /etc/ceph/ceph.conf --allhosts --mkbtrfs -k ~/admin.keyring")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo cp ceph-0.20/src/init-ceph /etc/init.d/ceph")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo chmod a+x /etc/init.d/ceph")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo chmod u+w /etc/init.d/ceph")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo /etc/init.d/ceph -c /etc/ceph/ceph.conf start")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo ps -aux | grep ceph")
        print stdout.readlines()
        print stderr.readlines()
        chan.close()
        client.close()
      
      except Exception, e:
          print '*** Caught exception: %s: %s' % (e.__class__, e)
          traceback.print_exc()
          try:
              client.close()
          except:
              pass
          sys.exit(1)
  
  
  # Deploy the client(s)
  for i in range(ANZ):
    if i == (ANZ-1):
      try:
          client = paramiko.SSHClient()
          client.load_system_host_keys()
          client.set_missing_host_key_policy(paramiko.WarningPolicy)
          # auto-accept unknown keys
          client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
          print 'Connecting...'
          client.connect(reservation.instances[i].public_dns_name, port, username, password, key)
          chan = client.invoke_shell()
          print repr(client.get_transport())
          print 'The system creates the GlusterFS clients.'
          print
          stdin, stdout, stderr = client.exec_command("sudo hostname")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo apt-get update")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo apt-get -y install autoconf libtool libboost-dev libedit-dev libssl-dev libboost-all-dev")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo apt-get -y install btrfs-tools")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo apt-get -y install libfuse2 libfuse-dev gawk linux-ec2-source-2.6.32")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo apt-get -y install linux-headers-2.6.32-305-ec2 linux-image-2.6.32-305-ec2")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo tar -xvjf /usr/src/linux-ec2-source-2.6.32.tar.bz2 -C /usr/src")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo ln -s /usr/src/linux-ec2-source-2.6.32 /usr/src/linux")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo cp /boot/config-2.6.32-305-ec2 /usr/src/linux/.config")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cd /usr/src/linux; make archprepare && make scripts && make prepare && make modules_prepare'")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo cp /usr/src/linux-headers-2.6.32-305-ec2/Module.symvers /usr/src/linux/")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo wget http://ceph.newdream.net/download/ceph-kclient-0.20.tar.gz")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo tar -xvzf ceph-kclient-0.20.tar.gz")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cd ceph-kclient-0.20; make KERNELDIR=/usr/src/linux/'")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cd ceph-kclient-0.20; make modules_install'")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo depmod")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo modprobe ceph")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo lsmod | grep ceph")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo mkdir /mnt/ceph")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo mount -t ceph "+ reservation.instances[0].private_dns_name+":/ /mnt/ceph/")
          print stdout.readlines()
          print stderr.readlines()
          chan.close()
          client.close()
  
  
      except Exception, e:
          print '*** Caught exception: %s: %s' % (e.__class__, e)
          traceback.print_exc()
          try:
              client.close()
          except:
              pass
          sys.exit(1)


elif filesystem == 5:
  # Here comes PVFS2 without redundancy

  # Get the first two instances. They will be the server
  zone = reservation.instances[0].placement
  instance_id1 = reservation.instances[0].id
  instance_id2 = reservation.instances[1].id

  print  
    
  try:
    # try to create the EBS volume
    neues_volume1 = conn_us_east.create_volume(EBS_Size, zone, snapshot=None)
  except EC2ResponseError:
    # An error occured
    print "While the system tried to create the EBS volume, an error occured." 
  else:
    print "The EBS volume "+neues_volume1.id+" was created successfully." 
  
  # Give the system some time to create the volume
  time.sleep(5)

  print
  
  try:
    # try to attach EBS volumne with the fist instance
    neues_volume_anhaengen = conn_us_east.attach_volume(neues_volume1.id, instance_id1, device)
  except EC2ResponseError:
    # An error occured
    print "While the system tried to attach the EBS volume with the instance "+str(instance_id1)+", an error occured." 
  else:
    print "Volume "+neues_volume1.id+" was attached with the instance "+str(instance_id1)+" successfully." 
  
  print
  
  try:
    # try to create the EBS volume
    neues_volume2 = conn_us_east.create_volume(EBS_Size, zone, snapshot=None)
  except EC2ResponseError:
    # An error occured
    print "While the system tried to create the EBS volume, an error occured." 
  else:
    print "The EBS volume "+neues_volume2.id+" was created successfully." 
  
  # Give the system some time to create the volume
  time.sleep(5)

  print
  
  try:
    # try to attach EBS volumne with the fist instance
    neues_volume_anhaengen = conn_us_east.attach_volume(neues_volume2.id, instance_id2, device)
  except EC2ResponseError:
    # An error occured
    print "While the system tried to attach the EBS volume with the instance "+str(instance_id2)+", an error occured." 
  else:
    print "Volume "+neues_volume2.id+" was attached with the instance "+str(instance_id2)+" successfully." 
    
  # Give the system some time to start the instances
  time.sleep(10)
  
  

  
  # Configuration of PVFS2 server
  for i in range(ANZ_Server):
    if i != ANZ_Server:
      try:
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.WarningPolicy)
        # auto-accept unknown keys
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        print 'Connecting...'
        client.connect(reservation.instances[i].public_dns_name, port, username, password, key)
        chan = client.invoke_shell()
        print repr(client.get_transport())
        print 'Deploy server'
        print
        stdin, stdout, stderr = client.exec_command("sudo hostname")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'sudo echo y | mkfs.ext3 /dev/sdc'")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo mkdir /pvfs2-storage-space")
        print stdout.readlines()
        print stderr.readlines()
        #stdin, stdout, stderr = client.exec_command("sudo mkdir /mnt/pvfs2/")
        #print stdout.readlines()
        #print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo mount /dev/sdc /pvfs2-storage-space")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo apt-get update")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo apt-get -y install joe bonnie++ gcc-4.4 g++ db4.8-util libdb4.8 libdb4.8-dev libdb-dev db4.8-util linux-headers-2.6.32-305-ec2 linux-image-2.6.32-305-ec2")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo wget ftp://ftp.parl.clemson.edu/pub/pvfs2/pvfs-2.8.2.tar.gz -P /usr/src/")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo tar -xvzf /usr/src/pvfs-2.8.2.tar.gz -C /usr/src")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo ln -s /usr/src/pvfs-2.8.2 /usr/src/pvfs2")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cd /usr/src/pvfs2; ./configure --with-kernel=/lib/modules/`uname -r`/build'")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cd /usr/src/pvfs2; make'")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cd /usr/src/pvfs2; make install'")
        print stdout.readlines()
        print stderr.readlines()
        
        instance0_hostname = str(reservation.instances[0].private_dns_name).replace('.ec2.internal', '')
        instance1_hostname = str(reservation.instances[1].private_dns_name).replace('.ec2.internal', '')
        print "Hostname 0:", str(instance0_hostname)
        print "Hostname 1:", str(instance1_hostname)
        
        stdin, stdout, stderr = client.exec_command("sudo pvfs2-genconfig --protocol tcp --tcpport 3334 --storage /pvfs2-storage-space --logfile /tmp/pvfs2-server.log --ioservers "+instance0_hostname+","+instance1_hostname+" --metaservers "+instance0_hostname+","+instance1_hostname+" /etc/pvfs2-fs.conf --quiet")
        print stdout.readlines()
        print stderr.readlines()
  
  
        if i == 0:
          # Datei pvfs2-fs.conf vom 1.Server holen
          hostname = reservation.instances[0].public_dns_name
          transport = paramiko.Transport((hostname, port))
          transport.connect(username = username, pkey = key)
        
          sftp = paramiko.SFTPClient.from_transport(transport)
        
          filepath = '/etc/pvfs2-fs.conf'
          localpath = 'pvfs2-fs.conf'
          sftp.get(filepath, localpath)
        
          sftp.close()
          transport.close()
        else:
          # Datei pvfs2-fs.conf auf die anderen Server hochladen        
          hostname = reservation.instances[i].public_dns_name
          transport = paramiko.Transport((hostname, port))
          transport.connect(username = username, pkey = key)
        
          sftp = paramiko.SFTPClient.from_transport(transport)
        
          remotepath = '/home/ubuntu/pvfs2-fs.conf'
          localpath = 'pvfs2-fs.conf'
          sftp.put(localpath, remotepath)
        
          sftp.close()
          transport.close()
  
        if i != 0:
          stdin, stdout, stderr = client.exec_command("sudo mv /home/ubuntu/pvfs2-fs.conf /etc/pvfs2-fs.conf")
          print stdout.readlines()
          print stderr.readlines()
  
        stdin, stdout, stderr = client.exec_command("sudo pvfs2-server /etc/pvfs2-fs.conf -f")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo pvfs2-server /etc/pvfs2-fs.conf")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo mkdir /mnt/pvfs2")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo chmod o+wx /etc/fstab")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo echo 'tcp://"+instance0_hostname+":3334/pvfs2-fs /mnt/pvfs2 pvfs2 defaults,noauto 0 0' >> /etc/fstab ")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo chmod o-wx /etc/fstab")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo touch /etc/pvfs2tab")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo chmod a+r /etc/pvfs2tab")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo chmod o+wx /etc/pvfs2tab")
        print stdout.readlines()
        print stderr.readlines()
        stdin, stdout, stderr = client.exec_command("sudo echo 'tcp://"+instance0_hostname+":3334/pvfs2-fs /mnt/pvfs2 pvfs2 defaults,noauto 0 0' >> /etc/pvfs2tab ")
        stdin, stdout, stderr = client.exec_command("sudo chmod o-wx /etc/pvfs2tab")
        print stdout.readlines()
        print stderr.readlines()
        chan.close()
        client.close()
  
  
      except Exception, e:
          print '*** Caught exception: %s: %s' % (e.__class__, e)
          traceback.print_exc()
          try:
              client.close()
          except:
              pass
          sys.exit(1)
        
  # Deploy PVFS2 Client(s)
  for i in range(ANZ):
    if i == (ANZ-1):
      try:
          client = paramiko.SSHClient()
          client.load_system_host_keys()
          client.set_missing_host_key_policy(paramiko.WarningPolicy)
          # auto-accept unknown keys
          client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
          print 'Connecting...'
          client.connect(reservation.instances[i].public_dns_name, port, username, password, key)
          chan = client.invoke_shell()
          print repr(client.get_transport())
          print 'Deploy PVFS2 client(s)'
          print
          stdin, stdout, stderr = client.exec_command("sudo hostname")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo apt-get update")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo apt-get -y install joe bonnie++ gcc-4.4 g++ db4.8-util libdb4.8 libdb4.8-dev libdb-dev db4.8-util linux-headers-2.6.32-305-ec2 linux-image-2.6.32-305-ec2 gawk linux-ec2-source-2.6.32")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo wget http://archive.ubuntu.com/ubuntu/pool/multiverse/i/iozone3/iozone3_308-1ubuntu0.1_i386.deb")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo dpkg -i iozone3_308-1ubuntu0.1_i386.deb")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo wget ftp://ftp.parl.clemson.edu/pub/pvfs2/pvfs-2.8.2.tar.gz -P /usr/src/")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo tar -xvzf /usr/src/pvfs-2.8.2.tar.gz -C /usr/src")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo ln -s /usr/src/pvfs-2.8.2 /usr/src/pvfs2")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cd /usr/src/pvfs2; ./configure --with-kernel=/lib/modules/`uname -r`/build'")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cd /usr/src/pvfs2; make'")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cd /usr/src/pvfs2; make install'")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo mkdir /mnt/pvfs2/")
          print stdout.readlines()
          print stderr.readlines()
          #stdin, stdout, stderr = client.exec_command("sudo touch /etc/pvfs2tab")
          #print stdout.readlines()
          #print stderr.readlines()
          #stdin, stdout, stderr = client.exec_command("sudo chmod a+r /etc/pvfs2tab")
          #print stdout.readlines()
          #print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo tar -xvjf /usr/src/linux-ec2-source-2.6.32.tar.bz2 -C /usr/src")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo ln -s /usr/src/linux-ec2-source-2.6.32 /usr/src/linux")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo cp /boot/config-2.6.32-305-ec2 /usr/src/linux/.config")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cd /usr/src/linux/; make archprepare && make scripts && make prepare && make modules_prepare'")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo cp /usr/src/linux-headers-2.6.32-305-ec2/Module.symvers /usr/src/linux/")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cd /usr/src/pvfs2/; ./configure --with-kernel=/usr/src/linux/'")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cd /usr/src/pvfs2/; make kmod'")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cd /usr/src/pvfs2/; make kmod_install'")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo insmod /usr/src/pvfs2/src/kernel/linux-2.6/pvfs2.ko")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo lsmod")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo /bin/sh -c 'cd /usr/src/pvfs2/src/apps/kernel/linux/; ./pvfs2-client -p ./pvfs2-client-core'")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo mount -t pvfs2 tcp://"+instance0_hostname+":3334/pvfs2-fs /mnt/pvfs2")
          print stdout.readlines()
          print stderr.readlines()
          stdin, stdout, stderr = client.exec_command("sudo mount | grep pvfs2")
          print stdout.readlines()
          print stderr.readlines()
          chan.close()
          client.close()
  
  
      except Exception, e:
          print '*** Caught exception: %s: %s' % (e.__class__, e)
          traceback.print_exc()
          try:
              client.close()
          except:
              pass
          sys.exit(1) 
        
 

else:
  sys.exit(1)
  