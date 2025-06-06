import sys
import os
import torch
import numpy as np
from utils.data import DvsGesture, temporal_jitter,  spatial_jitter
import lava.lib.dl.slayer as slayer
from torch.utils.data import DataLoader
from utils.argparser import args_parser
from utils.qtrain import train, qtest
from utils.train import test


### Load Args ###
args = args_parser()
if args.data_path is None: 
  print(f'Missing arg --data_path | python {sys.argv[0]} --data_path <path_to_folder>')
  quit()

# Choose model
from models.s6a0 import get_model as s6a0
from models.s5a1 import get_model as s5a1
from models.s4a2 import get_model as s4a2
from models.s3a3 import get_model as s3a3
from models.s2a4 import get_model as s2a4
from models.s1a5 import get_model as s1a5
from models.snn import get_model as snn
from models.acnn import get_model as acnn

get_model, model_desc = {
  "acnn": (acnn,"Accumulate-CNN Model"),
  "s1a5" : (s1a5, "S1A5 Hybrid Model"),
  "s2a4" : (s2a4, "S1A5 Hybrid Model"),
  "s3a3" : (s3a3, "S1A5 Hybrid Model"),
  "s4a2" : (s4a2, "S1A5 Hybrid Model"),
  "s5a1" : (s5a1, "S1A5 Hybrid Model"),
  "s6a0" : (s6a0, "S1A5 Hybrid Model"),
  "snn" : (snn, "SNN Model"),
}[args.model]

# Create Save Directory
args.save_path = os.path.join(args.save_folder, args.save_name)
args.model_path = os.path.join(args.save_path, f'{args.model}.pkl')
args.log_path = os.path.join(args.save_path, "log.txt")
args.acc_path = os.path.join(args.save_path, "acc.csv")
args.model_log_path = os.path.join(args.save_path, "model_log.txt")
args.device = "cpu"

### Load Model ###
model, optimizer, error, classer = get_model(args)
model.to(args.device)


### Load Data ###
def augment(x):
  x = temporal_jitter(x, max_shift=4, lib=np)
  x = spatial_jitter(x, max_shift=20, lib=np)
  return x

train_path = os.path.join(args.data_path,"train.npz")
print(f'Loading samples...',end="\r")
training = DvsGesture(train_path)
train_loader = DataLoader(dataset=training, batch_size=args.batch_size, shuffle=True, drop_last=True)
print(f'Found {len(training):,} training samples...') 

test_path = os.path.join(args.data_path,"test.npz")
testing = DvsGesture(test_path)
test_loader = DataLoader(dataset=testing, batch_size=args.batch_size, shuffle=True, drop_last=True)
print(f'Found {len(testing):,} testing samples...') 


if not args.no_quant:
  model.qconfig = torch.ao.quantization.get_default_qat_qconfig('x86')
  torch.ao.quantization.prepare_qat(model, inplace=True)

### Train ###
for epoch in range(args.epochs):
  model.to(args.device)
  train_acc = train(model, train_loader, optimizer, error, classer, args)
  
  if not args.no_quant:
    if epoch > 3:
      model.apply(torch.ao.quantization.disable_observer)
    
    model.to("cpu")
    qmodel = torch.ao.quantization.convert(model.eval(), inplace=False)
    qmodel.eval()
  
    test_acc = qtest(qmodel, test_loader, classer, args)
  
  else:
    test_acc = test(model, test_loader, classer, args)

  print(f'Epoch [{epoch+1}/{args.epochs}] Validation: {test_acc:.2%}')
