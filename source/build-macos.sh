#!/bin/bash
# For MacOS

WORKDIR="."

# Clean up previous build

for DIR in build dist swsh.egg-info; do
  if [ -d ${WORKDIR}/${DIR} ]; then
    rm -rf ${WORKDIR}/${DIR}
  fi
done

if [ -f ${WORKDIR}/swsh.spec ]; then
  rm -rf ${WORKDIR}/swsh.spec
fi

# Verify pip and pyinstaller are available
PIP=$( which pip )
if [ -z  $PIP ]; then
  echo "python pip is not available.  Installing..."
  # TODO: install pip
  exit 1
  PIP=$( which pip )
fi

PYINSTALLER=$( which pyinstaller )
if [ -z $PYINSTALLER ]; then
  echo "python pyinstaller is not available.  Installing..."
  ${PIP} install pyinstaller
  PYINSTALLER=$( which pyinstaller )
fi

# Readline is not available by default on mac
${PIP} show gnureadline > /dev/null
READLINE=$?
if [ ${READLINE} -ne 0 ]; then
  echo "Readline python package is not available.  Installing..."
  ${PIP} install gnureadline
fi
 
# Run setup.py
# Installs all required modules for SWiSH
pip install $WORKDIR
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
#sudo cp ${WORKDIR}/dist/swsh /usr/local/bin/swsh
