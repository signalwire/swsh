# SWiSH
SignalWire interactive SHell

A cross-platform command line shell for managing and administrating SignalWire Spaces.

---
INSTALLATION and SETUP
---

1.  Open Terminal
2.  Run the following command (Note: using python virtual environment is recommended, but is not required):
```
pip3 install swsh
```
3.  The following variables can be set to improve startup.  They are required for running in Non-Interactive mode.  If they are not set, swsh will ask for them at startup.
    - Linux / MacOS:
      ```
      export PROJECT_ID=<YOUR_PROJECT_ID>
      export SIGNALWIRE_SPACE=<YOUR_SIGNALWIRE_SPACE>
      export REST_API_TOKEN=<YOUR_REST_API_TOKEN>
      ```
    - Windows:
      ```
      setx PROJECT_ID=<YOUR_PROJECT_ID>
      setx SIGNALWIRE_SPACE=<YOUR_SIGNALWIRE_SPACE>
      setx REST_API_TOKEN=<YOUR_REST_API_TOKEN>
      ```
4.  Run swsh in Interactive or Non-Interactive mode
    - Interactive:
      - Type 'swsh' in terminal and hit inter to be taken into the interactive shell environment
    - Non-Interactive:
      - Type 'swsh "command(s)"' to have SWiSH run a command and return the output.  (Ideal for automated tasks)



For any questions or assistance, please contact SignalWire Support: support@signalwire.com