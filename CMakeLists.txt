cmake_minimum_required(VERSION 3.16.3...3.19.7 FATAL_ERROR)

project(ClipVessel)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://www.slicer.org/wiki/Documentation/Nightly/Extensions/ClipVessel")
set(EXTENSION_CATEGORY "Vascular Modeling Toolkit")
set(EXTENSION_CONTRIBUTORS "David Molony (Georgia Heart Institute)")
set(EXTENSION_DESCRIPTION "This module clips a surface model given a VMTK centerline and markups indicating where the model will be clipped. The first marker indicates the inlet. Optionally, the user can cap and add flow extensions.")
set(EXTENSION_ICONURL "https://www.example.com/Slicer/Extensions/ClipVessel.png")
set(EXTENSION_SCREENSHOTURLS "https://www.example.com/Slicer/Extensions/ClipVessel/Screenshots/1.png")
set(EXTENSION_DEPENDS "NA") # Specified as a list or "NA" if no dependencies

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(ClipVessel)
## NEXT_MODULE

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})
