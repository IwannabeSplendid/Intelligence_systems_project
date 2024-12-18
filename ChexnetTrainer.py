import os
import numpy as np
import time
import sys
from tqdm import tqdm
import random

import torch
import torch.nn as nn
import torch.backends.cudnn as cudnn
from torch.utils.data import DataLoader, Subset
import torchvision
import torchvision.transforms as transforms
import torch.optim as optim
import torch.nn.functional as tfunc
from torch.optim.lr_scheduler import ReduceLROnPlateau
import torch.nn.functional as func

from sklearn.metrics import roc_auc_score

from DensenetModels import DenseNet121
from DensenetModels import DenseNet169
from DensenetModels import DenseNet201
from DatasetGenerator import DatasetGenerator
from utils import fix_state_dict_keys

#-------------------------------------------------------------------------------- 
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

class ChexnetTrainer ():

    #---- Train the densenet network 
    #---- pathDirData - path to the directory that contains images
    #---- pathFileTrain - path to the file that contains image paths and label pairs (training set)
    #---- pathFileVal - path to the file that contains image path and label pairs (validation set)
    #---- nnArchitecture - model architecture 'DENSE-NET-121', 'DENSE-NET-169' or 'DENSE-NET-201'
    #---- nnIsTrained - if True, uses pre-trained version of the network (pre-trained on imagenet)
    #---- nnClassCount - number of output classes 
    #---- trBatchSize - batch size
    #---- trMaxEpoch - number of epochs
    #---- transResize - size of the image to scale down to (not used in current implementation)
    #---- transCrop - size of the cropped image 
    #---- launchTimestamp - date/time, used to assign unique name for the checkpoint file
    #---- checkpoint - if not None loads the model and continues training
    
    def train (pathDirData, pathFileTrain, pathFileVal, nnArchitecture, nnIsTrained, nnClassCount, trBatchSize, trMaxEpoch, transResize, transCrop, launchTimestamp, checkpoint):

        #-------------------- SETTINGS: NETWORK ARCHITECTURE
        if nnArchitecture == 'DENSE-NET-121': model = DenseNet121(nnClassCount, nnIsTrained).to(device)
        elif nnArchitecture == 'DENSE-NET-169': model = DenseNet169(nnClassCount, nnIsTrained).to(device)
        elif nnArchitecture == 'DENSE-NET-201': model = DenseNet201(nnClassCount, nnIsTrained).to(device)
        
        model = torch.nn.DataParallel(model).to(device)
                
        #-------------------- SETTINGS: DATA TRANSFORMS
        normalize = transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        
        transformList = []
        transformList.append(transforms.RandomResizedCrop(transCrop))
        transformList.append(transforms.RandomHorizontalFlip())
        transformList.append(transforms.ToTensor())
        transformList.append(normalize)      
        transformSequence=transforms.Compose(transformList)

        #-------------------- SETTINGS: DATASET BUILDERS
        datasetTrain = DatasetGenerator(pathImageDirectory=pathDirData, pathDatasetFile=pathFileTrain, transform=transformSequence)
        datasetVal =   DatasetGenerator(pathImageDirectory=pathDirData, pathDatasetFile=pathFileVal, transform=transformSequence)
              
        dataLoaderTrain = DataLoader(dataset=datasetTrain, batch_size=trBatchSize, shuffle=True,  num_workers=0, pin_memory=True)
        dataLoaderVal = DataLoader(dataset=datasetVal, batch_size=trBatchSize, shuffle=False, num_workers=0, pin_memory=True)
        
        #-------------------- SETTINGS: OPTIMIZER & SCHEDULER
        optimizer = optim.Adam (model.parameters(), lr=0.0001, betas=(0.9, 0.999), eps=1e-08, weight_decay=1e-5)
        scheduler = ReduceLROnPlateau(optimizer, factor = 0.1, patience = 5, mode = 'min')
                
        #-------------------- SETTINGS: LOSS
        loss = torch.nn.BCELoss(size_average = True)
        
        #---- Load checkpoint 
        if checkpoint != None:
            modelCheckpoint = torch.load(checkpoint, map_location=torch.device(device))
            state_dict = fix_state_dict_keys(modelCheckpoint['state_dict'])
            model.load_state_dict(state_dict)
            optimizer.load_state_dict(state_dict)

        
        #---- TRAIN THE NETWORK
        
        lossMIN = 100000
        
        for epochID in range (0, trMaxEpoch):
            
            timestampTime = time.strftime("%H%M%S")
            timestampDate = time.strftime("%d%m%Y")
            timestampSTART = timestampDate + '-' + timestampTime
                         
            ChexnetTrainer.epochTrain (model, dataLoaderTrain, optimizer, scheduler, trMaxEpoch, nnClassCount, loss)
            lossVal, losstensor = ChexnetTrainer.epochVal (model, dataLoaderVal, optimizer, scheduler, trMaxEpoch, nnClassCount, loss)
            
            timestampTime = time.strftime("%H%M%S")
            timestampDate = time.strftime("%d%m%Y")
            timestampEND = timestampDate + '-' + timestampTime
            
            scheduler.step(losstensor.data[0])
            
            if lossVal < lossMIN:
                lossMIN = lossVal    
                torch.save({'epoch': epochID + 1, 'state_dict': model.state_dict(), 'best_loss': lossMIN, 'optimizer' : optimizer.state_dict()}, 'm-' + launchTimestamp + '.pth.tar')
                print ('Epoch [' + str(epochID + 1) + '] [save] [' + timestampEND + '] loss= ' + str(lossVal))
            else:
                print ('Epoch [' + str(epochID + 1) + '] [----] [' + timestampEND + '] loss= ' + str(lossVal))
                     
    #-------------------------------------------------------------------------------- 
       
    def epochTrain (model, dataLoader, optimizer, scheduler, epochMax, classCount, loss):
        
        model.train()
        
        for batchID, (input, target) in tqdm(enumerate(dataLoader), total=len(dataLoader), desc="Processing Batches in Train"):
                        
            target = target.to(device)
                 
            varInput = torch.autograd.Variable(input)
            varTarget = torch.autograd.Variable(target)         
            varOutput = model(varInput)
            
            lossvalue = loss(varOutput, varTarget)
                       
            optimizer.zero_grad()
            lossvalue.backward()
            optimizer.step()
            
    #-------------------------------------------------------------------------------- 
        
    def epochVal (model, dataLoader, optimizer, scheduler, epochMax, classCount, loss):
        
        model.eval ()
        
        lossVal = 0
        lossValNorm = 0
        
        losstensorMean = 0
        
        for i, (input, target) in tqdm(enumerate(dataLoader), total=len(dataLoader), desc="Processing Batches in Validation"):
            
            target = target.to(device)
                 
            varInput = torch.autograd.Variable(input, volatile=True)
            varTarget = torch.autograd.Variable(target, volatile=True)    
            varOutput = model(varInput)
            
            losstensor = loss(varOutput, varTarget)
            losstensorMean += losstensor
            
            lossVal += losstensor.item()
            lossValNorm += 1
            
        outLoss = lossVal / lossValNorm
        losstensorMean = losstensorMean / lossValNorm
        
        return outLoss, losstensorMean
               
    #--------------------------------------------------------------------------------     
     
    #---- Computes area under ROC curve 
    #---- dataGT - ground truth data
    #---- dataPRED - predicted data
    #---- classCount - number of classes
    
    def computeAUROC (dataGT, dataPRED, classCount):
        
        outAUROC = []
        
        datanpGT = dataGT.cpu().numpy()
        datanpPRED = dataPRED.cpu().numpy()
        
        for i in range(classCount):
            outAUROC.append(roc_auc_score(datanpGT[:, i], datanpPRED[:, i]))
            
        return outAUROC
        
        
    #--------------------------------------------------------------------------------  
    
    #---- Test the trained network 
    #---- pathDirData - path to the directory that contains images
    #---- pathFileTrain - path to the file that contains image paths and label pairs (training set)
    #---- pathFileVal - path to the file that contains image path and label pairs (validation set)
    #---- nnArchitecture - model architecture 'DENSE-NET-121', 'DENSE-NET-169' or 'DENSE-NET-201'
    #---- nnIsTrained - if True, uses pre-trained version of the network (pre-trained on imagenet)
    #---- nnClassCount - number of output classes 
    #---- trBatchSize - batch size
    #---- trMaxEpoch - number of epochs
    #---- transResize - size of the image to scale down to (not used in current implementation)
    #---- transCrop - size of the cropped image 
    #---- launchTimestamp - date/time, used to assign unique name for the checkpoint file
    #---- checkpoint - if not None loads the model and continues training
    
    def test (pathDirData, pathFileTest, pathModel, nnArchitecture, nnClassCount, nnIsTrained, trBatchSize, transResize, transCrop, launchTimeStamp):   
        
        # CLASS_NAMES = [ 'Atelectasis', 'Cardiomegaly', 'Effusion', 'Infiltration', 'Mass', 'Nodule', 'Pneumonia',
        #         'Pneumothorax', 'Consolidation', 'Edema', 'Emphysema', 'Fibrosis', 'Pleural_Thickening', 'Hernia']
        CLASS_NAMES = [
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
        
        cudnn.benchmark = True
        
        #-------------------- SETTINGS: NETWORK ARCHITECTURE, MODEL LOAD
        if nnArchitecture == 'DENSE-NET-121': model = DenseNet121(nnClassCount, nnIsTrained).to(device)
        elif nnArchitecture == 'DENSE-NET-169': model = DenseNet169(nnClassCount, nnIsTrained).to(device)
        elif nnArchitecture == 'DENSE-NET-201': model = DenseNet201(nnClassCount, nnIsTrained).to(device)
        
        model = torch.nn.DataParallel(model).to(device) 
        
        modelCheckpoint = torch.load(pathModel, map_location=torch.device(device))
        state_dict = fix_state_dict_keys(modelCheckpoint['state_dict'])
        model.load_state_dict(state_dict)

        #-------------------- SETTINGS: DATA TRANSFORMS, TEN CROPS
        normalize = transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        
        #-------------------- SETTINGS: DATASET BUILDERS
        transformList = []
        transformList.append(transforms.Resize(transResize))
        transformList.append(transforms.TenCrop(transCrop))
        transformList.append(transforms.Lambda(lambda crops: torch.stack([transforms.ToTensor()(crop) for crop in crops])))
        transformList.append(transforms.Lambda(lambda crops: torch.stack([normalize(crop) for crop in crops])))
        transformSequence=transforms.Compose(transformList)
        
        datasetTest = DatasetGenerator(pathImageDirectory=pathDirData, pathDatasetFile=pathFileTest, transform=transformSequence)
        
        subset_size = 100
        indices_test = random.sample(range(len(datasetTest)), subset_size)
        datasetTest = Subset(datasetTest, indices_test)
        
        dataLoaderTest = DataLoader(dataset=datasetTest, batch_size=trBatchSize, num_workers=0, shuffle=False, pin_memory=True)
        
        outGT = torch.FloatTensor().to(device)
        outPRED = torch.FloatTensor().to(device)
       
        model.eval()
        
        for i, (input, target) in enumerate(tqdm(dataLoaderTest, desc="Processing Batches in Test")):
            
            target = target.to(device)
            outGT = torch.cat((outGT, target), 0)
            
            bs, n_crops, c, h, w = input.size()
            
            varInput = torch.autograd.Variable(input.view(-1, c, h, w).to(device), volatile=True)
            
            out = model(varInput)
            outMean = out.view(bs, n_crops, -1).mean(1)
            
            outPRED = torch.cat((outPRED, outMean.data), 0)

        print(outGT)
        print(len(set(outPRED.flatten().tolist())))
        print(outPRED)
        if len(set(outPRED.flatten().tolist())) < 2:
            print(outGT)
            print(outPRED)
        else:
            aurocIndividual = ChexnetTrainer.computeAUROC(outGT, outPRED, nnClassCount)
            aurocMean = np.array(aurocIndividual).mean()
            
            print ('AUROC mean ', aurocMean)
            
            for i in range (0, len(aurocIndividual)):
                print (CLASS_NAMES[i], ' ', aurocIndividual[i])
        
     
        return


    #-------------------------------------------------------------------------------- 

    def fine_tune(pathModel, pathDirData, pathFileTrain, pathFileVal, nnArchitecture, nnIsTrained, nnClassCount, trBatchSize, trMaxEpoch, transResize, transCrop, launchTimestamp, checkpoint=None, learningRate=1e-4):
    
        #-------------------- SETTINGS: NETWORK ARCHITECTURE
        if nnArchitecture == 'DENSE-NET-121': model = DenseNet121(nnClassCount, nnIsTrained).to(device)
        elif nnArchitecture == 'DENSE-NET-169': model = DenseNet169(nnClassCount, nnIsTrained).to(device)
        elif nnArchitecture == 'DENSE-NET-201': model = DenseNet201(nnClassCount, nnIsTrained).to(device)
        
        model = torch.nn.DataParallel(model).to(device) 
        
        modelCheckpoint = torch.load(pathModel, map_location=torch.device(device))
        state_dict = fix_state_dict_keys(modelCheckpoint['state_dict'])
        filtered_state_dict = {k: v for k, v in state_dict.items() if 'classifier' not in k}
        model.load_state_dict(filtered_state_dict, strict=False)
        
        #-------------------- FREEZE LAYER
        for name, param in model.named_parameters():
            if 'classifier' not in name:  # Freeze all but classifier
                param.requires_grad = False

        #-------------------- SETTINGS: DATA TRANSFORMS
        normalize = transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])

        transformList = [
            transforms.RandomResizedCrop(transCrop),
            transforms.RandomHorizontalFlip(),
            transforms.ToTensor(),
            normalize
        ]
        transformSequence = transforms.Compose(transformList)

        #-------------------- SETTINGS: DATASET BUILDERS
        datasetTrain = DatasetGenerator(pathImageDirectory=pathDirData, pathDatasetFile=pathFileTrain, transform=transformSequence)
        datasetVal = DatasetGenerator(pathImageDirectory=pathDirData, pathDatasetFile=pathFileVal, transform=transformSequence)
        
        # subset_size = 10  # Adjust this number as needed

        # # Create subsets for debugging
        # indices_train = random.sample(range(len(datasetTrain)), subset_size)
        # indices_val = random.sample(range(len(datasetVal)), subset_size)

        # datasetTrain = Subset(datasetTrain, indices_train)
        # datasetVal = Subset(datasetVal, indices_val)
        
        dataLoaderTrain = DataLoader(dataset=datasetTrain, batch_size=trBatchSize, shuffle=True, num_workers=0, pin_memory=True)
        dataLoaderVal = DataLoader(dataset=datasetVal, batch_size=trBatchSize, shuffle=False, num_workers=0, pin_memory=True)
        
        #-------------------- SETTINGS: OPTIMIZER & SCHEDULER
        optimizer = optim.Adam(filter(lambda p: p.requires_grad, model.parameters()), lr=learningRate, betas=(0.9, 0.999), eps=1e-08, weight_decay=1e-5)
        scheduler = ReduceLROnPlateau(optimizer, factor=0.1, patience=5, mode='min')

        # optimizer.load_state_dict({k: v for k, v in modelCheckpoint['optimizer'].items() if 'classifier' not in k})
        
        #-------------------- SETTINGS: LOSS
        loss = torch.nn.BCELoss(size_average=True)
        
        #---- TRAIN THE NETWORK
        lossMIN = 100000
        for epochID in range(trMaxEpoch):
            timestampTime = time.strftime("%H%M%S")
            timestampDate = time.strftime("%d%m%Y")
            timestampSTART = timestampDate + '-' + timestampTime
            
            ChexnetTrainer.epochTrain(model, dataLoaderTrain, optimizer, scheduler, trMaxEpoch, nnClassCount, loss)
            lossVal, losstensor = ChexnetTrainer.epochVal(model, dataLoaderVal, optimizer, scheduler, trMaxEpoch, nnClassCount, loss)
            
            timestampTime = time.strftime("%H%M%S")
            timestampDate = time.strftime("%d%m%Y")
            timestampEND = timestampDate + '-' + timestampTime
            
            scheduler.step(losstensor.item())
            
            # model_dir = './models'
            # model_path = os.path.join(model_dir, f'm-{launchTimestamp}.pth.tar')
            
            if lossVal < lossMIN:
                lossMIN = lossVal    
                torch.save({'epoch': epochID + 1, 'state_dict': model.state_dict(), 'best_loss': lossMIN, 'optimizer': optimizer.state_dict()}, 'm-' + launchTimestamp + '.pth.tar')
                print(f'Epoch [{epochID + 1}] [save] [{timestampEND}] loss= {lossVal}')
            else:
                print(f'Epoch [{epochID + 1}] [----] [{timestampEND}] loss= {lossVal}')

#-------------------------------------------------------------------------------- 





