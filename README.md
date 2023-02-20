# swish
SignalWire interactive SHell

A command line shell for managing and administrating SignalWire Spaces.
For any questions or assistance, please contact SignalWire Support.

---
INSTALLATION
---
Linux
Download linux version of swsh
sudo mv /path/to/swish-linux /usr/local/bin/swsh

MacOS
Downlaod macos version of swsh
sudo mv /path/to/swish-apple-silicon /usr/local/bin/swsh

Windows
Download windows exe version of swsh

---
SETUP and USAGE
---
Linux / MacOS:
1.  Open Terminal
2.  Three Environment variables need to be set on each OS in for SWiSH.  Run the following commands:
       - export PROJECT_ID=<YOUR_PROJECT_ID>
       - export SIGNALWIRE_SPACE=<YOUR_SIGNALWIRE_SPACE>
       - export REST_API_TOKEN=<YOUR_REST_API_TOKEN>
3.  Run in Interactive or Non-Interactive Mode
    Interactive:
        - Type 'swsh' in terminal and hit enter to be taken into the interactive shell environment
    Non-Interactive
        - Type 'swsh -x "command(s)"' to have SWiSH run a command and return the output.


Windows:
1.  Open CMD
2.  Three Environment variables need to be set on each OS in for SWiSH.  Run the following commands:
       - setx PROJECT_ID=<YOUR_PROJECT_ID>
       - setx SIGNALWIRE_SPACE=<YOUR_SIGNALWIRE_SPACE>
       - setx REST_API_TOKEN=<YOUR_REST_API_TOKEN>
3.  Run in Interactive or Non-Interactive Mode
    Interactive:
        - type 'swsh.exe' in the folder its located in 
    Non-Interactive
        - type 'swsh.exe -x "command(s)"' in the folder it is located in
