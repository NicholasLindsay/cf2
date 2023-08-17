#!/usr/bin/env bash
# Set up the virtual environment folder `venv`

error () {
    >&2 echo "Error detected at \"${1}\" stage - aborting"
    exit 1
}

echo "This script sets up a virtual environment to run the configurator tool."
echo "This virtual environment will be created in the current working directory."
echo "IMPORTANT: If you want the \"bin/cf2\" script to find the virtual environment, you MUST run this script within the project root directory."
while true
do
    read -p "Do you want to continue (y/n)?" choice
    case "${choice}" in
        [Yy])   break
                ;;
        [Nn])   exit 0
                ;;
        *)      echo "Invalid choice. Please enter 'y' or 'n'"
                ;;
    esac
done

# Create a virtual environment in "venv"
python3 -m venv venv || error "venv creation"

# Enter the virtual environment
source venv/bin/activate || error "source venv"

# Install the dependencies
python3 -m pip install -r requirements.txt || error "install dependencies"

