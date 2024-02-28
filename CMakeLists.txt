cmake_minimum_required(VERSION 3.12)
project(fddaqconf VERSION 1.1.2)

find_package(daq-cmake REQUIRED )

daq_setup_environment()

daq_install()
