#!/bin/sh
SSHOPTS="-p 2222 -oStrictHostKeyChecking=no -oUserKnownHostsFile=/dev/null -oHostKeyAlgorithms=+ssh-dss"

UDID=`ssh $SSHOPTS root@localhost "./device_infos udid"`

if [ "$UDID" == "" ]; then
    exit
fi

echo "Device UDID : $UDID"

mkdir -p $UDID

DATE=`date +"%Y%m%d-%H%M"`
OUT=$UDID/data_$DATE.dmg

echo "Dumping data partition in $OUT ..."

ssh $SSHOPTS root@localhost "cat /dev/rdisk0s2s1 || cat /dev/rdisk0s1s2" > $OUT
