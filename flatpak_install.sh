#!/usr/bin/env bash
FLATPAK="org.qgis.qgis"

if [ ! $(flatpak run --command=python $FLATPAK -m pip --version | cut -d " " -f1) = "pip" ]; then
   echo "downloading get-pip.py"
   flatpak run --command=wget $FLATPAK https://bootstrap.pypa.io/get-pip.py
   echo "installing pip"
   flatpak run --command=python $FLATPAK get-pip.py --user
else
   echo "found pip"
fi
flatpak run --command=python $FLATPAK -m pip install -r ./requirements-dev.txt
flatpak run --command=python $FLATPAK -m pip install -e .
flatpak override --env=PATH="/app/bin:/usr/bin:/var/data/python/bin" $FLATPAK --user
version=$(flatpak run --command=cetk $FLATPAK --version | cut -d " " -f2)
echo "successfully installed pip and cetk ${version} into flatpak"
