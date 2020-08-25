# Brain-Tumour-Segmentation-Msc-Thesis-
Deep Learning for segmentation of multi-model Magnetic Resonance Images from brain tumour. Project for Msc Thesis at Leeds University.


Designed for the BRATS 2018 Training Dataset. To use:

1) Download and uUzip the BRATS 2018 Dataset
2) From the Preprocessing folder, run the Unzip pogram
3) From the Preprocessing folder, run the Data Normalisation program
4) Notebooks from the Model Executables folder can now be used, each include the code allowing for the Loading, Training, Saving of the model. Also includes the code to obtain the final Segmentation Results as "ID".nii.gz files. Simply set the right boolean variables in the code and change the string for model name to avoid overwritting previous instances. The folder also includes a Python Executable that can be used to monitor the EMA throughout training.
5) Python Executable for Model Ensembling using Segmentations is available in the Postprocessing folder.
