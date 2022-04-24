import torch
import torch.nn as nn


class Classifier(nn.Module):
    def __init__(self, D_in,dropout= 0,number_of_classes= 1,first_division = 2):
        super(Classifier, self).__init__()
        
        self.fc1 = nn.Linear(D_in, (D_in//first_division))
        self.fc2 = nn.Linear((D_in//first_division),(D_in//(first_division*2)))
        self.fc3 = nn.Linear((D_in//(first_division*2)), (D_in//(first_division*4)))
        self.fc4= nn.Linear((D_in//(first_division*4)), number_of_classes)

        # self.soft = nn.Softmax(dim=0)
        self.drop = nn.Dropout(p=dropout)
        # self.relu = nn.LeakyReLU()#nn.ReLU()
        # self.tanh = nn.Tanh()
        self.selu = nn.SELU()     
    def forward(self, x):
        x = self.selu(self.fc1(x))
        x = self.drop(x)
        x = self.selu(self.fc2(x))
        # x = self.drop(x)
        x = self.selu(self.fc3(x))
        x = self.drop(x)
        x = self.fc4(x)
        # x = self.soft(x)

        return x

class G_Model(nn.Module):
    def __init__(self, input_dim,first_division = 2):
        super(G_Model, self).__init__()
        # Encoder: affine function
        self.fc1 = nn.Linear(input_dim,input_dim//first_division)
        self.fc2 = nn.Linear(input_dim//first_division, input_dim//(first_division*2))
        self.fc3 = nn.Linear(input_dim//(first_division*2), input_dim//(first_division*4))
        # Decoder: affine function
        self.fc4 = nn.Linear( input_dim//(first_division*4),input_dim//(first_division*2))
        self.fc5 = nn.Linear( input_dim//(first_division*2),input_dim//(first_division))
        self.fc6 = nn.Linear(input_dim//first_division, input_dim)
        # self.fc1 = nn.Linear(input_dim,input_dim//16)
        # self.fc2 = nn.Linear(input_dim//16, input_dim//32)
        # # Decoder: affine function
        # self.fc3 = nn.Linear(input_dim//32, input_dim//16)
        # self.fc4 = nn.Linear(input_dim//16, input_dim)
        self.sig = nn.Sigmoid()
        self.selu = nn.SELU()

    def forward(self, a):
        x = self.selu(self.fc1(a))
        x = self.selu(self.fc2(x))
        z = self.selu(self.fc3(x))
        x = self.selu(self.fc4(z))
        x = self.selu(self.fc5(x))
        logits = self.fc6(x)
        mask = self.sig(logits)
        return mask
