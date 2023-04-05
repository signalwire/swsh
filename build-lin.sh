#!/bin/bash

WORKDIR="."

# Verify pip and pyinstaller are available
PIP=$( which pip3 )
if [ -z  $PIP ]; then
  echo "python pip is not available.  Installing..."
  apt-get install python3-pip -y
  PIP=$( which pip3 )
fi

PYINSTALLER=$( which pyinstaller )
if [ -z $PYINSTALLER ]; then
  echo "python pyinstaller is not available.  Installing..."
  ${PIP} install pyinstaller
  PYINSTALLER=$( which pyinstaller )
fi

# Run setup.py
# Installs all required modules for SWiSH
${PIP} install $WORKDIR
RESULT=$?
if [ $RESULT -ne 0 ]; then
  echo "Something has gone wrong.  Error"
  exit 2
fi

# Do patches
CMD_LOC=$( $PIP show cmd2 |grep Location | awk '{print $2}' )
PYGMENTS_LOC=$( $PIP show pygments |grep Location | awk '{print $2}' )

/usr/bin/patch ${CMD_LOC}/cmd2/cmd2.py < ${WORKDIR}/swsh/patches/cmd2.patch
/usr/bin/patch ${CMD_LOC}/cmd2/cmd2.py < ${WORKDIR}/swsh/patches/do_history.patch
/usr/bin/patch ${PYGMENTS_LOC}/pygments/formatters/_mapping.py < ${WORKDIR}/swsh/patches//pygment_mapping.patch

cp ${WORKDIR}/swsh/patches/swishcolor.py ${PYGMENTS_LOC}/pygments/formatters/swishcolor.py

# Run build
${PYINSTALLER} build-swsh.py --onefile -n swsh

# Copy to /u/l/b
cp ${WORKDIR}/dist/swsh /usr/local/bin/swsh
