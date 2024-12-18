import os
import numpy as np
import time
import sys

from ChexnetTrainer import ChexnetTrainer

#-------------------------------------------------------------------------------- 

def main ():
    
    # runTest()
    # runTrain()
    runFineTune()
  
#--------------------------------------------------------------------------------   

def runTrain():
    
    DENSENET121 = 'DENSE-NET-121'
    DENSENET169 = 'DENSE-NET-169'
    DENSENET201 = 'DENSE-NET-201'
    
    timestampTime = time.strftime("%H%M%S")
    timestampDate = time.strftime("%d%m%Y")
    timestampLaunch = timestampDate + '-' + timestampTime
    
    #---- Path to the directory with images
    pathDirData = './database'
    
    #---- Paths to the files with training, validation and testing sets.
    #---- Each file should contains pairs [path to image, output vector]
    #---- Example: images_011/00027736_001.png 0 0 0 0 0 0 0 0 0 0 0 0 0 0
    pathFileTrain = './dataset/train_1.txt'
    pathFileVal = './dataset/val_1.txt'
    pathFileTest = './dataset/test_1.txt'
    
    #---- Neural network parameters: type of the network, is it pre-trained 
    #---- on imagenet, number of classes
    nnArchitecture = DENSENET121
    nnIsTrained = True
    nnClassCount = 14
    
    #---- Training settings: batch size, maximum number of epochs
    trBatchSize = 8
    trMaxEpoch = 100
    
    #---- Parameters related to image transforms: size of the down-scaled image, cropped image
    imgtransResize = 256
    imgtransCrop = 224
        
    pathModel = 'm-' + timestampLaunch + '.pth.tar'
    
    print ('Training NN architecture = ', nnArchitecture)
    ChexnetTrainer.train(pathDirData, pathFileTrain, pathFileVal, nnArchitecture, nnIsTrained, nnClassCount, trBatchSize, trMaxEpoch, imgtransResize, imgtransCrop, timestampLaunch, None)
    
    print ('Testing the trained model')
    ChexnetTrainer.test(pathDirData, pathFileTest, pathModel, nnArchitecture, nnClassCount, nnIsTrained, trBatchSize, imgtransResize, imgtransCrop, timestampLaunch)

#-------------------------------------------------------------------------------- 

def runTest():
    
    pathDirData = './database'
    pathFileTest = './dataset/test_b.txt'
    nnArchitecture = 'DENSE-NET-121'
    nnIsTrained = True
    nnClassCount = 34
    trBatchSize = 8
    imgtransResize = 256
    imgtransCrop = 224
    
    pathModel = './models/m-25012024-123527.pth.tar'
    
    timestampLaunch = ''
    
    ChexnetTrainer.test(pathDirData, pathFileTest, pathModel, nnArchitecture, nnClassCount, nnIsTrained, trBatchSize, imgtransResize, imgtransCrop, timestampLaunch)

#-------------------------------------------------------------------------------- 


def runFineTune():
    pathDirData = './database'
    pathFileTrain = './dataset/train_b.txt'
    pathFileVal = './dataset/val_b.txt'
    pathFileTest = './dataset/test_b.txt'
    
    nnArchitecture = 'DENSE-NET-121'
    classes = [
        'Atelectasis', 'Cardiomegaly', 'Pleural effusion', 'Pericardial effusion', 
        'Infiltrates', 'Alveolar pattern', 'Interstitial pattern', 
        'Reticular interstitial pattern', 'Pulmonary mass', 'Soft tissue mass', 
        'Nodule', 'Pseudonodule', 'Pneumonia', 'Consolidation', 
        'Pulmonary edema', 'Emphysema', 'Pulmonary fibrosis', 
        'Apical pleural thickening', 'Hiatal hernia', 'Pulmonary hypertension', 
        'Granuloma', 'Respiratory distress', 'Heart insufficiency', 'Tuberculosis', 
        'COPD signs', 'Bullas', 'Kyphosis', 'Scoliosis', 'Goiter', 'Vertebral fracture', 
        'Vertebral degenerative changes', 'Laminar atelectasis', 'Pulmonary artery enlargement', 'Normal'
    ]
    nnIsTrained = True
    nnClassCount = len(classes)
    trBatchSize = 8
    trMaxEpoch = 100
    
    imgtransResize = 256
    imgtransCrop = 224
    
    pathModel = './models/m-25012018-123527.pth.tar'
    
    timestampLaunch = '25012018-123527'
    
    ChexnetTrainer.fine_tune(pathModel, pathDirData, pathFileTrain, pathFileVal, nnArchitecture, nnIsTrained, nnClassCount, trBatchSize, trMaxEpoch, imgtransResize, imgtransCrop, timestampLaunch)


if __name__ == '__main__':
    main()





