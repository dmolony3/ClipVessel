### Clip Vessel
This module serves to clip or truncate a vessel based on user provider points or a pre-specified diameter. The user must provide a surface mesh as input (in either mode or segmentation format) as well as centerlines created by the VMTK module **ExtractCenterline**. 

It is recommended to preprocess the surface prior to running the algorithm.

1. Use original segmentation as input
2. Preprocess surface. (35.0k output appears to work). This is not necessary of using orginal segmentation as input


#### Preprocessing
The module requires a surface mesh as input (specified in either model or segmentation node). The mesh is typically created by segmenting images and therefore very dense, containing very high number of points. Using all the points in the centerline extraction would make the computation time very long (several minutes to tens of minutes). Preprocessing steps built into the module simplify the input mesh by replacing many small mesh elements with larger ones in regions where the curvature of the surface is low. This simplification reduces number of points and thus computation time, without significant changes in the computation result.

Preprocessing is enabled by default and it aims for reducing the number of mesh points to 5k (=5000). For larger, more complex networks, this Target point count parameter values can be increased (up to about 100k should be enough for most cases). Simplification is not performed in high-curvature areas, as it could remove significant features from the mesh and/or may introduce mesh errors (such as non-manifold edges). Aggressiveness parameter controls how much change in the mesh is acceptable during simplification. If aggressiveness value is low then all features of the mesh are preserved and no mesh errors are introduced but it may prevent the simplification method to reach the desired target point reduction. Any positive value can be used for aggressiveness, but values between 3.5-4.5 work best for typical inputs.

Subdivide can be enabled to increase the number of input points. This may make computation more robust for input meshes that has very coarse resolution

If a node is specified in Output preprocessed surface then preprocessing result is saved in that node. This is useful for quality checks: to ensure that all important details of the mesh are preserved. Saving preprocessed surface can be used to reduce computation time for repeated centerline extractions: once the preprocessed mesh is computed, choose it as input Surface and disable Preprocess input surface.
