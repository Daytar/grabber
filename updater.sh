#!/bin/bash

for tag in $(ls -d Pictures/*/ | cut -f 2 -d '/')
do
    echo "----------------------"
    python grabber.py -q $tag
done