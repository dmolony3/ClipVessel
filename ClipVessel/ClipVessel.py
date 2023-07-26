import os
import unittest
import logging
import vtk, qt, ctk, slicer
import numpy as np
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
import vtkvmtkComputationalGeometryPython as vtkvmtkComputationalGeometry

"""
  CrossSectionAnalysis : renamed from CenterlineMetrics, and merged with former deprecated CrossSectionAnalysis module.
  This file was originally derived from LineProfile.py.
  Many more features have been added since.
"""

class ClipVessel(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Clip Vessel"
    self.parent.categories = ["Vascular Modeling Toolkit"]
    self.parent.dependencies = []
    self.parent.contributors = ["David Molony (NGHS)", "Andras Lasso (PerkLab)"]
    self.parent.helpText = """
This module clips a surface model given a VMTK centerline and markups indicating where the model will be clipped. The first marker indicates the inlet. Optionally, the user can cap and add flow extensions.
    <a href="https://github.com/vmtk/SlicerExtension-VMTK/">here</a>.
"""
    self.parent.acknowledgementText = """
This file was originally developed by Jean-Christophe Fillion-Robin, Kitware Inc., Andras Lasso, PerkLab,
and Steve Pieper, Isomics, Inc. and was partially funded by NIH grant 3P41RR013218-12S1.
"""  # TODO: replace with organization, grant and thanks.

#
# ClipVesselWidget
#

class ClipVesselWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent=None):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.__init__(self, parent)
    VTKObservationMixin.__init__(self)  # needed for parameter node observation
    self.logic = None
    self._parameterNode = None
    self.updatingGUIFromParameterNode = False

  def setup(self):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.setup(self)

    # Load widget from .ui file (created by Qt Designer)
    uiWidget = slicer.util.loadUI(self.resourcePath('UI/ClipVessel.ui'))
    self.layout.addWidget(uiWidget)
    self.ui = slicer.util.childWidgetVariables(uiWidget)

    self.nodeSelectors = [
        (self.ui.inputSurfaceSelector, "InputSurface"),
        (self.ui.inputCenterlinesSelector, "InputCenterlines"),        
        (self.ui.clipPointsMarkupsSelector, "ClipPoints"),
        (self.ui.outputSurfaceModelSelector, "OutputSurfaceModel"),
        (self.ui.outputPreprocessedSurfaceModelSelector, "PreprocessedSurface"),
        ]

    # Add vertical spacer
    #self.layout.addStretch(1)

    # Set scene in MRML widgets. Make sure that in Qt designer
    # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
    # "setMRMLScene(vtkMRMLScene*)" slot.
    uiWidget.setMRMLScene(slicer.mrmlScene)

    self.logic = ClipVesselLogic()
    self.ui.parameterNodeSelector.addAttribute("vtkMRMLScriptedModuleNode", "ModuleName", self.moduleName)
    self.setParameterNode(self.logic.getParameterNode())

    # Connections
    self.ui.parameterNodeSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.setParameterNode)
    self.ui.applyButton.connect('clicked(bool)', self.onApplyButton)
    self.ui.preprocessInputSurfaceModelCheckBox.connect("toggled(bool)", self.updateParameterNodeFromGUI)
    self.ui.subdivideInputSurfaceModelCheckBox.connect("toggled(bool)", self.updateParameterNodeFromGUI)
    self.ui.targetKPointCountWidget.connect('valueChanged(double)', self.updateParameterNodeFromGUI)
    self.ui.decimationAggressivenessWidget.connect('valueChanged(double)', self.updateParameterNodeFromGUI)
    self.ui.capOutputSurfaceModelCheckBox.connect("toggled(bool)", self.updateParameterNodeFromGUI)
    self.ui.clipInputSurfaceModelCheckBox.connect("toggled(bool)", self.updateParameterNodeFromGUI)
    self.ui.clipDiameterSpinBox.connect('valueChanged(double)', self.updateParameterNodeFromGUI)
    self.ui.inputSegmentSelectorWidget.connect('currentSegmentChanged(QString)', self.updateParameterNodeFromGUI)
    #self.ui.inputCenterlinesSelector.connect('currentSegmentChanged(QString)', self.updateParameterNodeFromGUI)


    # TODO: a module must not change the application-wide unit format
    # If format is not nice enough then some formatting customization must be implemented.
    # selectionNode = slicer.mrmlScene.GetNodeByID("vtkMRMLSelectionNodeSingleton")
    # unitNode = slicer.mrmlScene.GetNodeByID(selectionNode.GetUnitNodeID("length"))
    # unitNode.SetPrecision(2)
    # unitNode = slicer.mrmlScene.GetNodeByID(selectionNode.GetUnitNodeID("area"))
    # unitNode.SetPrecision(2)

    for nodeSelector, roleName in self.nodeSelectors:
      nodeSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
      
    self.updateGUIFromParameterNode()
    

  def cleanup(self):
    """
    Called when the application closes and the module widget is destroyed.
    """
    self.removeObservers()

  def setParameterNode(self, inputParameterNode):
    """
    Adds observers to the selected parameter node. Observation is needed because when the
    parameter node is changed then the GUI must be updated immediately.
    """

    if inputParameterNode:
        self.logic.setDefaultParameters(inputParameterNode)

    # Set parameter node in the parameter node selector widget
    wasBlocked = self.ui.parameterNodeSelector.blockSignals(True)
    self.ui.parameterNodeSelector.setCurrentNode(inputParameterNode)
    self.ui.parameterNodeSelector.blockSignals(wasBlocked)

    if inputParameterNode == self._parameterNode:
        # No change
        return

    # Unobserve previusly selected parameter node and add an observer to the newly selected.
    # Changes of parameter node are observed so that whenever parameters are changed by a script or any other module
    # those are reflected immediately in the GUI.
    if self._parameterNode is not None:
        self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)
    if inputParameterNode is not None:
        self.addObserver(inputParameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)
    self._parameterNode = inputParameterNode

    # Initial GUI update
    self.updateGUIFromParameterNode()

  def updateGUIFromParameterNode(self, caller=None, event=None):
    """
    This method is called whenever parameter node is changed.
    The module GUI is updated to show the current state of the parameter node.
    """
    # Disable all sections if no parameter node is selected
    parameterNode = self._parameterNode
    if not slicer.mrmlScene.IsNodePresent(parameterNode):
        parameterNode = None
    self.ui.inputsCollapsibleButton.enabled = parameterNode is not None
    self.ui.outputsCollapsibleButton.enabled = parameterNode is not None
    self.ui.advancedCollapsibleButton.enabled = parameterNode is not None
    if parameterNode is None:
        return

    if self.updatingGUIFromParameterNode:
        return

    self.updatingGUIFromParameterNode = True

    # Update each widget from parameter node
    # Need to temporarily block signals to prevent infinite recursion (MRML node update triggers
    # GUI update, which triggers MRML node update, which triggers GUI update, ...)
    for nodeSelector, roleName in self.nodeSelectors:
        nodeSelector.setCurrentNode(self._parameterNode.GetNodeReference(roleName))

    inputSurfaceNode = self._parameterNode.GetNodeReference("InputSurface")
    if inputSurfaceNode and inputSurfaceNode.IsA("vtkMRMLSegmentationNode"):
        self.ui.inputSegmentSelectorWidget.setCurrentSegmentID(self._parameterNode.GetParameter("InputSegmentID"))
        self.ui.inputSegmentSelectorWidget.setVisible(True)
    else:
        self.ui.inputSegmentSelectorWidget.setVisible(False)

    #self.ui.inputCenterlinesSelector.setVisible(True)

    self.ui.targetKPointCountWidget.value = float(self._parameterNode.GetParameter("TargetNumberOfPoints"))/1000.0

    self.ui.decimationAggressivenessWidget.value = float(self._parameterNode.GetParameter("DecimationAggressiveness"))
    
    self.ui.clipDiameterSpinBox.value = float(self._parameterNode.GetParameter("ClipDiameter"))

    # do not block signals so that related widgets are enabled/disabled according to its state
    self.ui.preprocessInputSurfaceModelCheckBox.checked = (self._parameterNode.GetParameter("PreprocessInputSurface") == "true")

    self.ui.subdivideInputSurfaceModelCheckBox.checked = (self._parameterNode.GetParameter("SubdivideInputSurface") == "true")
    self.ui.capOutputSurfaceModelCheckBox.checked = (self._parameterNode.GetParameter("CapOutputSurface") == "true")    
    self.ui.clipInputSurfaceModelCheckBox.checked = (self._parameterNode.GetParameter("ClipInputSurface") == "true")
    
    # Update buttons states and tooltips
    if self._parameterNode.GetNodeReference("InputSurface") and self._parameterNode.GetNodeReference("InputCenterlines") and self._parameterNode.GetNodeReference("OutputSurfaceModel"):
        self.ui.applyButton.toolTip = "Clip vessel"
        self.ui.applyButton.enabled = True
    else:
        self.ui.applyButton.toolTip = "Select input and output model nodes"
        self.ui.applyButton.enabled = False

    self.updatingGUIFromParameterNode = False

  def updateParameterNodeFromGUI(self, caller=None, event=None):
    """
    This method is called when the user makes any change in the GUI.
    The changes are saved into the parameter node (so that they are restored when the scene is saved and loaded).
    """

    if self._parameterNode is None:
        return

    for nodeSelector, roleName in self.nodeSelectors:
        self._parameterNode.SetNodeReferenceID(roleName, nodeSelector.currentNodeID)

    inputSurfaceNode = self._parameterNode.GetNodeReference("InputSurface")
    if inputSurfaceNode and inputSurfaceNode.IsA("vtkMRMLSegmentationNode"):
        self._parameterNode.SetParameter("InputSegmentID", self.ui.inputSegmentSelectorWidget.currentSegmentID())

    self.ui.inputSegmentSelectorWidget.setCurrentSegmentID(self._parameterNode.GetParameter("InputSegmentID"))
    self.ui.inputSegmentSelectorWidget.setVisible(inputSurfaceNode and inputSurfaceNode.IsA("vtkMRMLSegmentationNode"))

    wasModify = self._parameterNode.StartModify()
    self._parameterNode.SetParameter("TargetNumberOfPoints", str(self.ui.targetKPointCountWidget.value*1000.0))
    self._parameterNode.SetParameter("DecimationAggressiveness", str(self.ui.decimationAggressivenessWidget.value))
    self._parameterNode.SetParameter("ClipDiameter", str(self.ui.clipDiameterSpinBox.value))
    self._parameterNode.SetParameter("PreprocessInputSurface", "true" if self.ui.preprocessInputSurfaceModelCheckBox.checked else "false")
    self._parameterNode.SetParameter("SubdivideInputSurface", "true" if self.ui.subdivideInputSurfaceModelCheckBox.checked else "false")
    self._parameterNode.SetParameter("CapOutputSurface", "true" if self.ui.capOutputSurfaceModelCheckBox.checked else "false")
    self._parameterNode.SetParameter("ClipInputSurface", "true" if self.ui.clipInputSurfaceModelCheckBox.checked else "false")
    self._parameterNode.EndModify(wasModify)

  def getPreprocessedPolyData(self):
    inputSurfacePolyData = self.logic.polyDataFromNode(self._parameterNode.GetNodeReference("InputSurface"),
                                                       self._parameterNode.GetParameter("InputSegmentID"))
    if not inputSurfacePolyData or inputSurfacePolyData.GetNumberOfPoints() == 0:
        raise ValueError("Valid input surface is required")

    preprocessEnabled = (self._parameterNode.GetParameter("PreprocessInputSurface") == "true")
    if not preprocessEnabled:
        return inputSurfacePolyData
    targetNumberOfPoints = float(self._parameterNode.GetParameter("TargetNumberOfPoints"))
    decimationAggressiveness = float(self._parameterNode.GetParameter("DecimationAggressiveness"))
    subdivideInputSurface = (self._parameterNode.GetParameter("SubdivideInputSurface") == "true")
    preprocessedPolyData = self.logic.preprocess(inputSurfacePolyData, targetNumberOfPoints, decimationAggressiveness, subdivideInputSurface)
    return preprocessedPolyData

  def onApplyButton(self):
    """
    Run processing when user clicks "Apply" button.
    """
    qt.QApplication.setOverrideCursor(qt.Qt.WaitCursor)
    try:
        # Preprocessing
        slicer.util.showStatusMessage("Preprocessing...")
        slicer.app.processEvents()  # force update
        preprocessedPolyData = self.getPreprocessedPolyData()
        # Save preprocessing result to model node
        preprocessedSurfaceModelNode = self._parameterNode.GetNodeReference("PreprocessedSurface")
        if preprocessedSurfaceModelNode:
            preprocessedSurfaceModelNode.SetAndObserveMesh(preprocessedPolyData)
            if not preprocessedSurfaceModelNode.GetDisplayNode():
                preprocessedSurfaceModelNode.CreateDefaultDisplayNodes()
                preprocessedSurfaceModelNode.GetDisplayNode().SetColor(1.0, 1.0, 0.0)
                preprocessedSurfaceModelNode.GetDisplayNode().SetOpacity(0.4)
                preprocessedSurfaceModelNode.GetDisplayNode().SetLineWidth(2)


        clipPointsMarkupsNode = self._parameterNode.GetNodeReference("ClipPoints")
        inputSurfaceModelNode = self._parameterNode.GetNodeReference("InputSurface")
        centerlinesModelNode = self._parameterNode.GetNodeReference("InputCenterlines")
        outputModelNode = self._parameterNode.GetNodeReference("OutputSurfaceModel")
        clipDiameter = float(self._parameterNode.GetParameter("ClipDiameter"))
        clip = self.ui.clipInputSurfaceModelCheckBox.checked
        cap = self.ui.capOutputSurfaceModelCheckBox.checked

        if clip is False:
          clipDiameter = None

        slicer.util.showStatusMessage("Clipping model...")
        slicer.app.processEvents()  # force update

        addFlowExtensions = False
        outputPolyData = self.logic.clipVessel(preprocessedPolyData, centerlinesModelNode, clipPointsMarkupsNode, clipDiameter, cap, addFlowExtensions)
        
        outputModelNode.SetAndObserveMesh(outputPolyData)
        if not outputModelNode.GetDisplayNode():
            outputModelNode.CreateDefaultDisplayNodes()
            outputModelNode.GetDisplayNode().SetColor(0.0, 1.0, 0.0)
            outputModelNode.GetDisplayNode().SetLineWidth(3)
            inputSurfaceModelNode.GetDisplayNode().SetOpacity(0.4)

    except Exception as e:
        slicer.util.errorDisplay("Failed to compute results: "+str(e))
        import traceback
        traceback.print_exc()
    qt.QApplication.restoreOverrideCursor()
    slicer.util.showStatusMessage("Clippig vessel complete.", 3000)


#
# ClipVesselLogic
#

class ClipVesselLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """
  def __init__(self):
    ScriptedLoadableModuleLogic.__init__(self)
    self.radiusArrayName = 'Radius'
    self.blankingArrayName = 'Blanking'
    self.groupIdsArrayName = 'GroupIds'
    self.tractIdsArrayName = 'TractIds'
    self.centerlineIdsArrayName = 'CenterlineIds'
    
    self.gapLength = 1.0
    self.tolerance = 0.01
    self.clipValue = 0.0
    self.cutoffRadiusFactor = 1E16

    self.groupIds = []

    self.useRadiusInformation = 1

    self.Sigma = 1
    self.AdaptiveExtensionLength = 0
    self.AdaptiveExtensionRadius = 1
    self.AdaptiveNumberOfBoundaryPoints = 0
    self.ExtensionLength = 5
    self.ExtensionRatio = 2
    self.ExtensionRadius = 1
    self.TransitionRatio = 0.25
    self.CenterlineNormalEstimationDistanceRatio = 1.0
    self.TargetNumberOfBoundaryPoints = 50

  def setDefaultParameters(self, parameterNode):
    """
    Initialize parameter node with default settings.
    """
    # We choose a small target point number value, so that we can get fast speed
    # for smooth meshes. Actual mesh size will mainly determined by DecimationAggressiveness value.
    if not parameterNode.GetParameter("TargetNumberOfPoints"):
        parameterNode.SetParameter("TargetNumberOfPoints", "5000")
    if not parameterNode.GetParameter("DecimationAggressiveness"):
        parameterNode.SetParameter("DecimationAggressiveness", "4.0")
    if not parameterNode.GetParameter("PreprocessInputSurface"):
        parameterNode.SetParameter("PreprocessInputSurface", "true")
    if not parameterNode.GetParameter("SubdivideInputSurface"):
        parameterNode.SetParameter("SubdivideInputSurface", "false")
    if not parameterNode.GetParameter("ClipDiameter"):
        parameterNode.SetParameter("ClipDiameter", "1.5")
        
  def polyDataFromNode(self, surfaceNode, segmentId):
    if not surfaceNode:
        logging.error("Invalid input surface node")
        return None
    if surfaceNode.IsA("vtkMRMLModelNode"):
        return surfaceNode.GetPolyData()
    elif surfaceNode.IsA("vtkMRMLSegmentationNode"):
        # Segmentation node
        polyData = vtk.vtkPolyData()
        surfaceNode.CreateClosedSurfaceRepresentation()
        surfaceNode.GetClosedSurfaceRepresentation(segmentId, polyData)
        return polyData
    else:
        logging.error("Surface can only be loaded from model or segmentation node")
        return None
            
  def preprocess(self, surfacePolyData, targetNumberOfPoints, decimationAggressiveness, subdivide):
    # import the vmtk libraries
    try:
        import vtkvmtkComputationalGeometryPython as vtkvmtkComputationalGeometry
        import vtkvmtkMiscPython as vtkvmtkMisc
    except ImportError:
        raise ImportError("VMTK library is not found")

    numberOfInputPoints = surfacePolyData.GetNumberOfPoints()
    if numberOfInputPoints == 0:
        raise("Input surface model is empty")
    reductionFactor = (numberOfInputPoints-targetNumberOfPoints) / numberOfInputPoints
    if reductionFactor > 0.0:
        parameters = {}
        inputSurfaceModelNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", "tempInputSurfaceModel")
        inputSurfaceModelNode.SetAndObserveMesh(surfacePolyData)
        parameters["inputModel"] = inputSurfaceModelNode
        outputSurfaceModelNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", "tempDecimatedSurfaceModel")
        parameters["outputModel"] = outputSurfaceModelNode
        parameters["reductionFactor"] = reductionFactor
        parameters["method"] = "FastQuadric"
        parameters["aggressiveness"] = decimationAggressiveness
        decimation = slicer.modules.decimation
        cliNode = slicer.cli.runSync(decimation, None, parameters)
        surfacePolyData = outputSurfaceModelNode.GetPolyData()
        slicer.mrmlScene.RemoveNode(inputSurfaceModelNode)
        slicer.mrmlScene.RemoveNode(outputSurfaceModelNode)
        slicer.mrmlScene.RemoveNode(cliNode)

    surfaceCleaner = vtk.vtkCleanPolyData()
    surfaceCleaner.SetInputData(surfacePolyData)
    surfaceCleaner.Update()

    surfaceTriangulator = vtk.vtkTriangleFilter()
    surfaceTriangulator.SetInputData(surfaceCleaner.GetOutput())
    surfaceTriangulator.PassLinesOff()
    surfaceTriangulator.PassVertsOff()
    surfaceTriangulator.Update()

    # new steps for preparation to avoid problems because of slim models (f.e. at stenosis)
    if subdivide:
        subdiv = vtk.vtkLinearSubdivisionFilter()
        subdiv.SetInputData(surfaceTriangulator.GetOutput())
        subdiv.SetNumberOfSubdivisions(1)
        subdiv.Update()
        if subdiv.GetOutput().GetNumberOfPoints() == 0:
            logging.warning("Mesh subdivision failed. Skip subdivision step.")
            subdivide = False

    normals = vtk.vtkPolyDataNormals()
    if subdivide:
        normals.SetInputData(subdiv.GetOutput())
    else:
        normals.SetInputData(surfaceTriangulator.GetOutput())
    normals.SetAutoOrientNormals(1)
    normals.SetFlipNormals(0)
    normals.SetConsistency(1)
    normals.SplittingOff()
    normals.Update()

    return normals.GetOutput()

  # Unclear if necessary
  def extractNonManifoldEdges(self, polyData, nonManifoldEdgesPolyData=None):
    '''
    Returns non-manifold edge center positions.
    nonManifoldEdgesPolyData: optional vtk.vtkPolyData() input, if specified then a polydata is returned that contains the edges
    '''
    import vtkvmtkDifferentialGeometryPython as vtkvmtkDifferentialGeometry
    neighborhoods = vtkvmtkDifferentialGeometry.vtkvmtkNeighborhoods()
    neighborhoods.SetNeighborhoodTypeToPolyDataManifoldNeighborhood()
    neighborhoods.SetDataSet(polyData)
    neighborhoods.Build()

    polyData.BuildCells()
    polyData.BuildLinks(0)

    edgeCenterPositions = []

    neighborCellIds = vtk.vtkIdList()
    nonManifoldEdgeLines = vtk.vtkCellArray()
    points = polyData.GetPoints()
    for i in range(neighborhoods.GetNumberOfNeighborhoods()):
        neighborhood = neighborhoods.GetNeighborhood(i)
        for j in range(neighborhood.GetNumberOfPoints()):
            neighborId = neighborhood.GetPointId(j)
            if i < neighborId:
                neighborCellIds.Initialize()
                polyData.GetCellEdgeNeighbors(-1, i, neighborId, neighborCellIds)
                if neighborCellIds.GetNumberOfIds() > 2:
                    nonManifoldEdgeLines.InsertNextCell(2)
                    nonManifoldEdgeLines.InsertCellPoint(i)
                    nonManifoldEdgeLines.InsertCellPoint(neighborId)
                    p1 = points.GetPoint(i)
                    p2 = points.GetPoint(neighborId)
                    edgeCenterPositions.append([(p1[0]+p2[0])/2.0, (p1[1]+p2[1])/2.0, (p1[2]+p2[2])/2.0])

    if nonManifoldEdgesPolyData:
        if not polyData.GetPoints():
            raise ValueError("Failed to get non-manifold edges (neighborhood filter output was empty)")
        pointsCopy = vtk.vtkPoints()
        pointsCopy.DeepCopy(polyData.GetPoints())
        nonManifoldEdgesPolyData.SetPoints(pointsCopy)
        nonManifoldEdgesPolyData.SetLines(nonManifoldEdgeLines)

    return edgeCenterPositions
    
  def extractBranches(self, centerlines):  
    import vtkvmtkComputationalGeometryPython as vtkvmtkComputationalGeometry
    branchExtractor = vtkvmtkComputationalGeometry.vtkvmtkCenterlineBranchExtractor()
    branchExtractor.SetInputData(centerlines)
    branchExtractor.SetBlankingArrayName('Blanking')
    branchExtractor.SetRadiusArrayName('Radius')
    branchExtractor.SetGroupIdsArrayName('GroupIds')
    branchExtractor.SetCenterlineIdsArrayName('CenterlineIds')
    branchExtractor.SetTractIdsArrayName('TractIds')
    branchExtractor.Update()
    return branchExtractor.GetOutput()

  def mergeCenterlines(self, centerlines):
    """Merges the centerlines and resets the blanking array (removed during merge) using probefilter"""
    import vtkvmtkComputationalGeometryPython as vtkvmtkComputationalGeometry
    print("Merging centerlines")
    splitCenterlines = self.extractBranches(centerlines)
    # remove redundant points from centerlines
    mergeCenterlines = vtkvmtkComputationalGeometry.vtkvmtkMergeCenterlines()
    mergeCenterlines.SetInputData(splitCenterlines)
    mergeCenterlines.SetRadiusArrayName('Radius')
    mergeCenterlines.SetGroupIdsArrayName('GroupIds')
    mergeCenterlines.SetCenterlineIdsArrayName('CenterlineIds')
    mergeCenterlines.SetTractIdsArrayName('TractIds')
    mergeCenterlines.SetBlankingArrayName('Blanking')
    mergeCenterlines.SetResamplingStepLength(0.5)
    mergeCenterlines.SetMergeBlanked(True)
    mergeCenterlines.Update()
    prober = vtk.vtkProbeFilter()
    prober.SetInputData(0, mergeCenterlines.GetOutput())
    prober.SetInputData(1, splitCenterlines)
    prober.SetPassCellArrays(1)
    prober.Update()
    mergedCenterlines = prober.GetOutput()
    #cellToPoint = vtk.vtkCellDataToPointData()
    #cellToPoint.SetInputData(mergeCenterlines.GetOutput())
    #cellToPoint.SetProcessAllArrays(1)
    #cellToPoint.Update()
    #mergedCenterlines = mergeCenterlines.GetOutput()
    #branchClipper = vtkvmtkComputationalGeometry.vtkvmtkPolyDataCenterlineGroupsClipper()
    #branchClipper.SetCenterlineGroupIdsArrayName('CenterlineIds')
    #branchClipper.SetGroupIdsArrayName('GroupIds')
    #branchClipper.SetCenterlineRadiusArrayName('Radius')
    #branchClipper.SetBlankingArrayName('Blanking')
    #branchClipper.SetCutoffRadiusFactor(1E16)
    #branchClipper.SetClipValue(0.0)
    #branchClipper.SetUseRadiusInformation(1)
    #branchClipper.ClipAllCenterlineGroupIdsOn()
    #branchClipper.GenerateClippedOutputOn()
    #branchClipper.SetInputData(surface)
    #branchClipper.SetCenterlines(branchExtractor.GetOutput())
    #branchClipper.Update()
    return mergedCenterlines
    #mergedCenterlines, clipper = clipper1(polyData, cl.GetPolyData())
    
  def getClipPoints(self, mergedCenterlines, clipRadius, cellId=0):
    # Add current cell as a curve node
    print("Finding clip points")
    assignAttribute = vtk.vtkAssignAttribute()
    assignAttribute.SetInputData(mergedCenterlines)
    #assignAttribute.Assign(self.groupIdsArrayName, vtk.vtkDataSetAttributes.SCALARS,
    #                       vtk.vtkAssignAttribute.CELL_DATA)
    assignAttribute.Assign('GroupIds', vtk.vtkDataSetAttributes.SCALARS,
                           vtk.vtkAssignAttribute.CELL_DATA)


    # identify parent and child groups for each segment     
    numberOfCells = mergedCenterlines.GetNumberOfCells()
    childDict = {}
    parentDict = {}
    
    visited = []
    stack = []
    cellId = 0
    stack.append(cellId)
    
    cellPoints = mergedCenterlines.GetCell(cellId).GetPointIds()
    endPointIndex = cellPoints.GetId(cellPoints.GetNumberOfIds() - 1)
    while stack:
      currentCellId = stack.pop()
      visited.append(currentCellId)
      cellIds = []
      for neighborCellIndex in range(numberOfCells):
        cellPoints = mergedCenterlines.GetCell(currentCellId).GetPointIds()
        endPointIndex = cellPoints.GetId(cellPoints.GetNumberOfIds() - 1)
        if neighborCellIndex in visited:
          continue
        if endPointIndex != mergedCenterlines.GetCell(neighborCellIndex).GetPointIds().GetId(0):
          continue 
        cellIds.append(neighborCellIndex)
      stack.extend(cellIds)  
      childDict[currentCellId] = cellIds
      parentDict.update({cell:currentCellId for cell in cellIds})
    
    # add point data array containing the point id so that we can extract after thresholding
    pointIds = vtk.vtkIntArray()
    pointIds.SetName('PointIds')
    [pointIds.InsertNextTuple([i, ]) for i in range(mergedCenterlines.GetNumberOfPoints())]
    mergedCenterlines.GetPointData().AddArray(pointIds)
    
    # now we can start at end branches (empty entries in dictionary)
    thresholder = vtk.vtkThreshold()
    thresholder.SetInputConnection(assignAttribute.GetOutputPort())
    terminalIds = [parentID for parentID, childId in childDict.items() if not childId]
    visited = []
    stack = terminalIds.copy()
    pointId = []
    while stack:
      currentCellId = stack.pop()
      if currentCellId in visited:
        continue

      groupId = mergedCenterlines.GetCellData().GetArray('GroupIds').GetValue(currentCellId)
      thresholder.SetLowerThreshold(groupId - 0.5)
      thresholder.SetUpperThreshold(groupId + 0.5)
      thresholder.Update()    
      segment = thresholder.GetOutput()

      #cellToPoint = vtk.vtkCellDataToPointData()
      #cellToPoint.SetInputData(segment)
      #cellToPoint.SetProcessAllArrays(1)
      ##cellToPoint.Update()
      #segment = cellToPoint.GetOutput()

      # threshold centerline with id, check radius. 
      # set ids as point data so we can 
      num_arrays = segment.GetPointData().GetNumberOfArrays()
      blankingArrayId = [i for i in range(num_arrays) if segment.GetPointData().GetArrayName(i) == 'Blanking'][0]
      radisArrayId = [i for i in range(num_arrays) if segment.GetPointData().GetArrayName(i) == 'Radius'][0]
      pointIdArrayId = [i for i in range(num_arrays) if segment.GetPointData().GetArrayName(i) == 'PointIds'][0]

      radius = segment.GetPointData().GetArray(radisArrayId)
      length = [vtk.vtkMath().Distance2BetweenPoints(segment.GetPoint(i + 1),segment.GetPoint(i)) for i in range(segment.GetNumberOfPoints() - 1)]
      length = [sum(length[:i]) for i in range(len(length) + 1)]

      # check if last value is less than clip radius. If so then the clipping point will be the first location where the radius exceeds the clip radius
      #[radius.GetTuple(i)[0] for i in range(radius.GetNumberOfTuples())]

      if radius.GetTuple(radius.GetNumberOfTuples() - 1)[0] < clipRadius:
        for i in reversed(range(radius.GetNumberOfTuples())):
          # check that we are outside bifurcation
          #if segment.GetPointData().GetArray(blankingArrayId).GetTuple(i)[0] == 1:
          if length[i] < 2:
            print(length[i])
            pointId.append(segment.GetPointData().GetArray(pointIdArrayId).GetTuple(i)[0])
            visited.append(currentCellId)    
            while parentDict[currentCellId] != 0:
              visited.append(parentDict[currentCellId])
              currentCellId = parentDict[currentCellId]
            break            
          elif radius.GetTuple(i)[0] > clipRadius:
            pointId.append(segment.GetPointData().GetArray(pointIdArrayId).GetTuple(i)[0])
            visited.append(currentCellId)
            while parentDict[currentCellId] != 0:
              visited.append(parentDict[currentCellId])
              currentCellId = parentDict[currentCellId]
            break
          elif i == 0:
            visited.append(currentCellId)
            stack.append(parentDict[currentCellId])
      else:
        visited.append(currentCellId)      
        stack.append(parentDict[currentCellId])
      
      visited = list(set(visited))
    clipPoints = [mergedCenterlines.GetPoint(int(idx)) for idx in pointId]
    return clipPoints, mergedCenterlines
    
  def set_clipper(self, surface, splitCenterlines, groupIds):
    # if we work under the assumption that group 0 is always kept it will eliminate the use of user interaction to select which groups to keep.
    branchClipper = vtkvmtkComputationalGeometry.vtkvmtkPolyDataCenterlineGroupsClipper()
    branchClipper.SetCenterlineGroupIdsArrayName(self.groupIdsArrayName)
    branchClipper.SetGroupIdsArrayName(self.groupIdsArrayName)
    branchClipper.SetCenterlineRadiusArrayName(self.radiusArrayName)
    branchClipper.SetBlankingArrayName(self.blankingArrayName)
    branchClipper.SetCutoffRadiusFactor(self.cutoffRadiusFactor)
    branchClipper.SetClipValue(self.clipValue)
    branchClipper.SetUseRadiusInformation(self.useRadiusInformation)
    if groupIds.GetNumberOfIds() > 0:
      branchClipper.ClipAllCenterlineGroupIdsOff()
      branchClipper.SetCenterlineGroupIds(groupIds)
      branchClipper.GenerateClippedOutputOn()
    else:
      branchClipper.ClipAllCenterlineGroupIdsOn()
    branchClipper.SetInputData(surface)
    branchClipper.SetCenterlines(splitCenterlines)
    branchClipper.Update()
    return branchClipper
    
  def extendVessel(self, surfacePolyData, centerlinesPolyData, clipPoints):
    """Adds flow extensions to all boundaries"""
    # compute new centerlines for the truncated geometry
    
    extensionRatio = 2
    normalEstimationRatio = 1
    adaptiveExtensionLength = 0
    adaptiveExtensionRadius = 1
    adaptiveNumberOfBoundaryPoints = 0
    extensionLength = 1
    extensionRadius = 1
    sigma = 1
    transitionRatio = 0.25
    targetNumberOfBoundaryPoints = 50
    centerlineNormalEstimationRatio = 1.0
    extensionsFilter = vtkvmtkComputationalGeometry.vtkvmtkPolyDataFlowExtensionsFilter()
    extensionsFilter.SetInputData(surfacePolyData)
    extensionsFilter.SetCenterlines(centerlinesPolyData)
    extensionsFilter.SetSigma(self.Sigma)
    extensionsFilter.SetAdaptiveExtensionLength(self.AdaptiveExtensionLength)
    extensionsFilter.SetAdaptiveExtensionRadius(self.AdaptiveExtensionRadius)
    extensionsFilter.SetAdaptiveNumberOfBoundaryPoints(self.AdaptiveNumberOfBoundaryPoints)
    extensionsFilter.SetExtensionLength(self.ExtensionLength)
    extensionsFilter.SetExtensionRatio(self.ExtensionRatio)
    extensionsFilter.SetExtensionRadius(self.ExtensionRadius)
    extensionsFilter.SetTransitionRatio(self.TransitionRatio)
    extensionsFilter.SetCenterlineNormalEstimationDistanceRatio(self.CenterlineNormalEstimationDistanceRatio)
    extensionsFilter.SetNumberOfBoundaryPoints(self.TargetNumberOfBoundaryPoints)
    extensionsFilter.SetExtensionModeToUseNormalToBoundary()
    #extensionsFilter.SetBoundaryIds(boundaryIds)
    extensionsFilter.Update()
    return extensionsFilter.GetOutput()
    
  def clipVessel(self, surfacePolyData, centerlinesNode, clipPointsMarkupsNode, cap, clipDiameter, addFlowExtensions=False):
    """Clips the vessel.
    :param surfacePolyData:
    :param centerlinesPolyData:
    :param clipPointsMarkupsNode:
    :param addFlowExtensions: adds flow extensions:
    :return:
    """
    
    ### UPLOAD TO GITHUB. CONSIDER USING MERGED CENTERLINES TO CLIP MODEL AS THIS WILL FIX INLET PROBLEMS
    
    import vtkvmtkMiscPython as vtkvmtkMisc
    import vtkvmtkComputationalGeometryPython as vtkvmtkComputationalGeometry

    if clipDiameter and clipPointsMarkupsNode:
        raise ValueError("Both a clipping diameter and a clip point can not be used together. Choose one or the other")
        
    if not clipPointsMarkupsNode and clipDiameter is None:
        raise ValueError("Either clip points or a clipping diameter must be provided")

    if clipDiameter is None:
        if not clipPointsMarkupsNode or clipPointsMarkupsNode.GetNumberOfControlPoints() < 1:
            raise ValueError("At least one point is needed for surface clipping")

    centerlinesPolyData = centerlinesNode.GetPolyData()
    #centerlinesPolyData = self.extractBranches(centerlinesPolyData)
    # identify closest point on centerline to clipPointsMarkups
    pointLocator = vtk.vtkPointLocator()
    pointLocator.SetDataSet(centerlinesPolyData)
    pointLocator.BuildLocator()
    
    clipPoints = []
    pos = [0.0, 0.0, 0.0]
    
    if clipPointsMarkupsNode is not None:
      numberOfControlPoints = clipPointsMarkupsNode.GetNumberOfControlPoints()
      for controlPointIndex in range(numberOfControlPoints):
          clipPointsMarkupsNode.GetNthControlPointPosition(controlPointIndex, pos)
          pointId = pointLocator.FindClosestPoint(pos)
          clipPoints.append(centerlinesPolyData.GetPoint(pointId))
    else:
      mergedCenterlines = self.mergeCenterlines(centerlinesPolyData)
      clipRadius = clipDiameter/2
      initialClipPoints, _ = self.getClipPoints(mergedCenterlines, clipRadius, cellId=0)
      numberOfControlPoints = len(initialClipPoints)
      for controlPointIndex in range(numberOfControlPoints):
        pointId = pointLocator.FindClosestPoint(initialClipPoints[controlPointIndex])
        clipPoints.append(centerlinesPolyData.GetPoint(pointId))
        
    clips = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "Clips")
    [clips.AddControlPointWorld(pt[0], pt[1], pt[2]) for pt in clipPoints]
    
    # create the centerline split extractor
    pointSplitExtractor = vtkvmtkComputationalGeometry.vtkvmtkCenterlineSplitExtractor()
    pointSplitExtractor.SetInputData(centerlinesPolyData)
    pointSplitExtractor.SetRadiusArrayName(self.radiusArrayName)
    pointSplitExtractor.SetGroupIdsArrayName(self.groupIdsArrayName)
    pointSplitExtractor.SetTractIdsArrayName(self.tractIdsArrayName)
    pointSplitExtractor.SetCenterlineIdsArrayName(self.centerlineIdsArrayName)
    pointSplitExtractor.SetBlankingArrayName(self.blankingArrayName)
    pointSplitExtractor.SetGapLength(self.gapLength)
    pointSplitExtractor.SetTolerance(self.tolerance)    

    groupIds = vtk.vtkIdList()
    groupIds.InsertNextId(0)

    # split the centerlines and clip the branch
    #surfacePolyData = slicer.util.getNode("Output surface model").GetPolyData()
    surface = surfacePolyData
    #print(centerlinesPolyData)
    for controlPointIndex in range(numberOfControlPoints):
        print(clipPoints[controlPointIndex])
        pointSplitExtractor.SetSplitPoint(clipPoints[controlPointIndex]) # crashing here
        pointSplitExtractor.Update()
        splitCenterlines = pointSplitExtractor.GetOutput()
        #cl1 = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", "cl")
        #cl1.SetAndObservePolyData(splitCenterlines)
        
        branchClipper = self.set_clipper(surface, splitCenterlines, groupIds)
        
        #print(controlPointIndex, branchClipper.GetCenterlineGroupIds().GetId(0), branchClipper.GetBlankingArrayName(), branchClipper.GetClipValue(), branchClipper.GetCenterlineRadiusArrayName(), branchClipper.GetGroupIdsArrayName())
        # if user provided points the inlet must be the first point
        if clipPointsMarkupsNode:
            if controlPointIndex == 0:
                surface = branchClipper.GetClippedOutput()
            else:
                surface = branchClipper.GetOutput()  
        else:
            surface = branchClipper.GetOutput()  
            
    if not branchClipper.GetOutput():
        raise ValueError("Failed to clip vessel (no output was generated)")

    addFlowExtensions = False
    if addFlowExtensions:
        print("ADDing extensions")
        surface = self.extendVessel(surface, centerlinesPolyData, clipPoints)
        print(surface)

    # Cap all the holes that are in the mesh that are not marked as endpoints
    # Maybe this is not needed.
    if cap:
        capDisplacement = 0.0
        surfaceCapper = vtkvmtkComputationalGeometry.vtkvmtkCapPolyData()
        surfaceCapper.SetInputData(surface)
        surfaceCapper.SetDisplacement(capDisplacement)
        surfaceCapper.SetInPlaneDisplacement(capDisplacement)
        surfaceCapper.Update()
        surface = surfaceCapper.GetOutput()

    surfacePolyData = vtk.vtkPolyData()
    surfacePolyData.DeepCopy(surface)

    logging.debug("End of Clip Vessel Computation..")
    return surfacePolyData

  def decimateSurface(self, polyData):
    '''
    '''

    decimationFilter = vtk.vtkDecimatePro()
    decimationFilter.SetInputData(polyData)
    decimationFilter.SetTargetReduction(0.99)
    decimationFilter.SetBoundaryVertexDeletion(0)
    decimationFilter.PreserveTopologyOn()
    decimationFilter.Update()

    cleaner = vtk.vtkCleanPolyData()
    cleaner.SetInputData(decimationFilter.GetOutput())
    cleaner.Update()

    triangleFilter = vtk.vtkTriangleFilter()
    triangleFilter.SetInputData(cleaner.GetOutput())
    triangleFilter.Update()

    outPolyData = vtk.vtkPolyData()
    outPolyData.DeepCopy(triangleFilter.GetOutput())

    return outPolyData
        
  def run(self):
    self.resetCrossSections()
    if not self.isInputCenterlineValid():
        msg = "Input is invalid."
        slicer.util.showStatusMessage(msg, 3000)
        raise ValueError(msg)

    logging.info('Processing started')
    if self.outputTableNode:
      self.emptyOutputTableNode()
      self.updateOutputTable(self.inputCenterlineNode, self.outputTableNode)
    if self.outputPlotSeriesNode:
      self.updatePlot(self.outputPlotSeriesNode, self.outputTableNode, self.inputCenterlineNode.GetName())
    logging.info('Processing completed')


#
# ClipVesselTest
#

class ClipVesselTest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  Uses ScriptedLoadableModuleTest base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear(0)

  def runTest(self):
    """
    """