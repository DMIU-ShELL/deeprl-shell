#######################################################################
# Copyright (C) 2017 Shangtong Zhang(zhangshangtong.cpp@gmail.com)    #
# Permission given to modify the code as long as you keep this        #
# declaration at the top                                              #
#######################################################################

from .network_utils import *

class NatureConvBody(nn.Module):
    def __init__(self, in_channels=4):
        super(NatureConvBody, self).__init__()
        self.feature_dim = 512
        self.conv1 = layer_init(nn.Conv2d(in_channels, 32, kernel_size=8, stride=4))
        self.conv2 = layer_init(nn.Conv2d(32, 64, kernel_size=4, stride=2))
        self.conv3 = layer_init(nn.Conv2d(64, 64, kernel_size=3, stride=1))
        self.fc4 = layer_init(nn.Linear(7 * 7 * 64, self.feature_dim))

    def forward(self, x):
        y = F.relu(self.conv1(x))
        y = F.relu(self.conv2(y))
        y = F.relu(self.conv3(y))
        y = y.view(y.size(0), -1)
        y = F.relu(self.fc4(y))
        return y

class CombinedNet(nn.Module, BaseNet):
    ''' not sure what I'm doing here (AS) need to review'''
    def __init__(self, bodyPredict):
        super(CombinedNet, self).__init__()
#        self.fc_value = layer_init(nn.Linear(body.feature_dim, 1))
#        self.fc_advantage = layer_init(nn.Linear(body.feature_dim, action_dim))
        self.bodyPredict = bodyPredict
        self.to(Config.DEVICE)

    def returnFeatures(self, x, to_numpy=False):
        phi = self.bodyPredict(tensor(x))
        if to_numpy:
            return phi.cpu().detach().numpy()
        return phi
    #        value = self.fc_value(phi)
#        advantange = self.fc_advantage(phi)
#        q = value.expand_as(advantange) + (advantange - advantange.mean(1, keepdim=True).expand_as(advantange))
#        if to_numpy:
#            return q.cpu().detach().numpy()
#        return q

class Mod1LNatureConvBody_direct(nn.Module):
    '''1 layer modulation, direct,
    simple RELU'''
    def __init__(self, in_channels=4):
        super(Mod1LNatureConvBody_direct, self).__init__()
        self.feature_dim = 512
        self.conv1 = layer_init(nn.Conv2d(in_channels, 32, kernel_size=8, stride=4))
        self.conv1_nm = layer_init(nn.Conv2d(2*in_channels, 32, kernel_size=8, stride=4))
        self.conv2 = layer_init(nn.Conv2d(32, 64, kernel_size=4, stride=2))
        self.conv3 = layer_init(nn.Conv2d(64, 64, kernel_size=3, stride=1))
        self.fc4 = layer_init(nn.Linear(7 * 7 * 64, self.feature_dim))

    def forward(self, x, x_nm):
        y = F.relu(self.conv1(x))
        y_nm = F.relu(self.conv1_nm(x_nm))
        y = y*y_nm
        y = F.relu(self.conv2(y))
        y = F.relu(self.conv3(y))
        y = y.view(y.size(0), -1)
        y = F.relu(self.fc4(y))
        return y

class Mod1LNatureConvBody_diff(nn.Module):
    '''1 layer modulation, simple RELU'''
    def __init__(self, in_channels=4):
        super(Mod1LNatureConvBody_diff, self).__init__()
        self.feature_dim = 512
        self.conv1 = layer_init(nn.Conv2d(in_channels, 32, kernel_size=8, stride=4))
        self.conv1_nm_fea = layer_init(nn.Conv2d(in_channels, 32, kernel_size=8, stride=4))
        self.conv1_nm_comb = layer_init(nn.Conv2d(32, 32, kernel_size=3, stride=1, padding=1))
        self.conv2 = layer_init(nn.Conv2d(32, 64, kernel_size=4, stride=2))
        self.conv3 = layer_init(nn.Conv2d(64, 64, kernel_size=3, stride=1))
        self.fc4 = layer_init(nn.Linear(7 * 7 * 64, self.feature_dim))

    def forward(self, x, x_nm):
        y0 = F.relu(self.conv1(x))
        y_nm = F.relu(self.conv1_nm_fea(x_nm))
        y_nm = y0 - y_nm
        y_nm = F.relu(self.conv1_nm_comb(y_nm))
        y = y0*y_nm
        y = F.relu(self.conv2(y))
        y = F.relu(self.conv3(y))
        y = y.view(y.size(0), -1)
        y = F.relu(self.fc4(y))
        return y

class Mod1LNatureConvBody_diff_sig(nn.Module):
    '''1 layer modulation, implemented by YH
    modulation through sigmoid'''
    def __init__(self, in_channels=4):
        super(Mod2LNatureConvBody_diff_sig, self).__init__()
        self.feature_dim = 512
        self.conv1 = layer_init(nn.Conv2d(in_channels, 32, kernel_size=8, stride=4))
        self.conv1_nm_fea = layer_init(nn.Conv2d(in_channels, 32, kernel_size=8, stride=4))
        self.conv1_nm_comb = layer_init(nn.Conv2d(32, 32, kernel_size=3, stride=1, padding=1))
        self.conv2 = layer_init(nn.Conv2d(32, 64, kernel_size=4, stride=2))
        self.conv3 = layer_init(nn.Conv2d(64, 64, kernel_size=3, stride=1))
        self.fc4 = layer_init(nn.Linear(7 * 7 * 64, self.feature_dim))

    def forward(self, x, x_nm):
        y0 = F.relu(self.conv1(x))
        y_nm = F.relu(self.conv1_nm_fea(x_nm))
        y_nm = y0 - y_nm
        y_nm = 2*torch.sigmoid(self.conv1_nm_comb(y_nm))
        y = y0*y_nm
        y = F.relu(self.conv2(y))
        y = F.relu(self.conv3(y))
        y = y.view(y.size(0), -1)
        y = F.relu(self.fc4(y))
        return y

class Mod2LNatureConvBody_diff_sig(nn.Module):
    ''' 2-layer modulated with modulation computed from the difference of 2 conv layers. Output of modulation through sigmoid with factor 2, thus in range [0, 1]'''
    def __init__(self, in_channels=4):
        super(Mod2LNatureConvBody_diff_sig, self).__init__()
        self.feature_dim = 512
        self.conv1 = layer_init(nn.Conv2d(in_channels, 32, kernel_size=8, stride=4))
        self.conv1_mem_features = layer_init(nn.Conv2d(in_channels, 32, kernel_size=8, stride=4))
        self.conv1_diff = layer_init(nn.Conv2d(32, 32, kernel_size=3, stride=1, padding=1))
        self.conv2 = layer_init(nn.Conv2d(32, 64, kernel_size=4, stride=2))
        self.conv2_mem_features = layer_init(nn.Conv2d(32, 64, kernel_size=4, stride=2))
        self.conv2_diff = layer_init(nn.Conv2d(64, 64, kernel_size=3, stride=1, padding=1))
        self.conv3 = layer_init(nn.Conv2d(64, 64, kernel_size=3, stride=1))
        self.fc4 = layer_init(nn.Linear(7 * 7 * 64, self.feature_dim))

    def forward(self, x, x_mem):
        y0 = F.relu(self.conv1(x))
        y_mem0 = F.relu(self.conv1_mem_features(x_mem))
        y = y0 * 2 * torch.sigmoid(self.conv1_diff(y0 - y_mem0))

        y0 = F.relu(self.conv2(y))
        y_mem1 = F.relu(self.conv2_mem_features(y_mem0))
        y_mod = 2 * torch.sigmoid(self.conv2_diff(y0 - y_mem1))
        y = y0 * y_mod

        y = F.relu(self.conv3(y))
        y = y.view(y.size(0), -1)
        y = F.relu(self.fc4(y))
        return y

class Mod2LNatureConvBody_direct_sig(nn.Module):
    '''2-layer modulated (AS), memory modulates directly layer 1 and 2 without computing the difference. TODO: this network should be 0.5 + 0.5*sigmoid, and not 1+ 0.5 sigmoid
'''
    def __init__(self, in_channels=4):
        super(Mod2LNatureConvBody_direct_sig, self).__init__()
        self.feature_dim = 512
        self.conv1 = layer_init(nn.Conv2d(in_channels, 32, kernel_size=8, stride=4))
        self.conv1_mem_features = layer_init(nn.Conv2d(in_channels, 32, kernel_size=8, stride=4))
        self.conv1_diff = layer_init(nn.Conv2d(32, 32, kernel_size=3, stride=1, padding=1))
        self.conv2 = layer_init(nn.Conv2d(32, 64, kernel_size=4, stride=2))
        self.conv2_mem_features = layer_init(nn.Conv2d(32, 64, kernel_size=4, stride=2))
        self.conv2_diff = layer_init(nn.Conv2d(64, 64, kernel_size=3, stride=1, padding=1))
        self.conv3 = layer_init(nn.Conv2d(64, 64, kernel_size=3, stride=1))
        self.fc4 = layer_init(nn.Linear(7 * 7 * 64, self.feature_dim))

    def forward(self, x, x_mem):
        y0 = F.relu(self.conv1(x))
        y_mem0 = F.relu(self.conv1_mem_features(x_mem))
        y_mod = 2 * torch.sigmoid(y_mem0)
        y = y0 * y_mod

        y1 = F.relu(self.conv2(y))
        y_mem1 = F.relu(self.conv2_mem_features(y_mem0))
        y_mod1 = 2 * torch.sigmoid(y_mem1)
        y = y1 * y_mod1

        y = F.relu(self.conv3(y))
        y = y.view(y.size(0), -1)
        y = F.relu(self.fc4(y))
        return y

#class Mod3LNatureConvBody_direct(nn.Module):
#    '''This network should also be 0.5+0.5sigmoid, otherwise we have a higher learning rate '''
#    def __init__(self, in_channels=4):
#        super(Mod3LNatureConvBody_direct, self).__init__()
#        self.feature_dim = 512
#        self.conv1 = layer_init(nn.Conv2d(in_channels, 32, kernel_size=8, stride=4))
#        self.conv1_mem_features = layer_init(nn.Conv2d(in_channels, 32, #kernel_size=8, stride=4))
#        self.conv2 = layer_init(nn.Conv2d(32, 64, kernel_size=4, stride=2))#
#        self.conv2_mem_features = layer_init(nn.Conv2d(32, 64, kernel_size=4, stride=2))
#        self.conv3 = layer_init(nn.Conv2d(64, 64, kernel_size=3, stride=1))
#        self.conv3_mem_features = layer_init(nn.Conv2d(64, 64, kernel_size=3, stride=1))

#        self.fc4 = layer_init(nn.Linear(7 * 7 * 64, self.feature_dim))

#    def forward(self, x, x_mem):
#        y0 = F.relu(self.conv1(x))
#        y_mem0 = F.relu(self.conv1_mem_features(x_mem))
#        y_mod0 = 1 + 0.5 * torch.sigmoid(y_mem0)
#        y = y0 * y_mod0

#        y1 = F.relu(self.conv2(y))
#        y_mem1 = F.relu(self.conv2_mem_features(y_mem0))
#        y_mod1 = 1 + 0.5 * torch.sigmoid(y_mem1)
#        y = y1 * y_mod1

#        y2 = F.relu(self.conv3(y))
#        y_mem2 = F.relu(self.conv3_mem_features(y_mem1))
#        y_mod2 = 1 + 0.5 * torch.sigmoid(y_mem2)
#        y = y2 * y_mod2
#
#        y = y.view(y.size(0), -1)
#        y = F.relu(self.fc4(y))
#        return y

class Mod3LNatureConvBody_direct_fix(nn.Module):
    '''Correction to the Mod3L direct: changing 1+ 0.5sig to 0.5 + 0.5sig
    19/12/18: does not work, to delete'''
    def __init__(self, in_channels=4):
        super(Mod3LNatureConvBody_direct_fix, self).__init__()
        self.feature_dim = 512
        self.conv1 = layer_init(nn.Conv2d(in_channels, 32, kernel_size=8, stride=4))
        self.conv1_mem_features = layer_init(nn.Conv2d(in_channels, 32, kernel_size=8, stride=4))
        self.conv2 = layer_init(nn.Conv2d(32, 64, kernel_size=4, stride=2))
        self.conv2_mem_features = layer_init(nn.Conv2d(32, 64, kernel_size=4, stride=2))
        self.conv3 = layer_init(nn.Conv2d(64, 64, kernel_size=3, stride=1))
        self.conv3_mem_features = layer_init(nn.Conv2d(64, 64, kernel_size=3, stride=1))

        self.fc4 = layer_init(nn.Linear(7 * 7 * 64, self.feature_dim))

    def forward(self, x, x_mem):
        y0 = F.relu(self.conv1(x))
        y_mem0 = F.relu(self.conv1_mem_features(x_mem))
        y_mod0 = 0.5 + 0.5 * torch.sigmoid(y_mem0)
        y = y0 * y_mod0

        y1 = F.relu(self.conv2(y))
        y_mem1 = F.relu(self.conv2_mem_features(y_mem0))
        y_mod1 = 0.5 + 0.5 * torch.sigmoid(y_mem1)
        y = y1 * y_mod1

        y2 = F.relu(self.conv3(y))
        y_mem2 = F.relu(self.conv3_mem_features(y_mem1))
        y_mod2 = 0.5 + 0.5 * torch.sigmoid(y_mem2)
        y = y2 * y_mod2

        y = y.view(y.size(0), -1)
        y = F.relu(self.fc4(y))
        return y

class Mod3LNatureConvBody_direct_2Sig(nn.Module):
    ''' direct modulation going through a sigmoid * 2 so that the modulation can change plasticity in the rage [0,2]'''
    def __init__(self, in_channels=4):
        super(Mod3LNatureConvBody_direct_2Sig, self).__init__()
        self.feature_dim = 512
        self.conv1 = layer_init(nn.Conv2d(in_channels, 32, kernel_size=8, stride=4))
        self.conv1_mem_features = layer_init(nn.Conv2d(in_channels, 32, kernel_size=8, stride=4))
        self.conv2 = layer_init(nn.Conv2d(32, 64, kernel_size=4, stride=2))
        self.conv2_mem_features = layer_init(nn.Conv2d(32, 64, kernel_size=4, stride=2))
        self.conv3 = layer_init(nn.Conv2d(64, 64, kernel_size=3, stride=1))
        self.conv3_mem_features = layer_init(nn.Conv2d(64, 64, kernel_size=3, stride=1))

        self.fc4 = layer_init(nn.Linear(7 * 7 * 64, self.feature_dim))

    def forward(self, x, x_mem):
        y0 = F.relu(self.conv1(x))
        y_mem0 = F.relu(self.conv1_mem_features(x_mem))
        y_mod0 = 2 * torch.sigmoid(y_mem0)
        y = y0 * y_mod0

        y1 = F.relu(self.conv2(y))
        y_mem1 = F.relu(self.conv2_mem_features(y_mem0))
        y_mod1 = 2 * torch.sigmoid(y_mem1)
        y = y1 * y_mod1

        y2 = F.relu(self.conv3(y))
        y_mem2 = F.relu(self.conv3_mem_features(y_mem1))
        y_mod2 = 2 * torch.sigmoid(y_mem2)
        y = y2 * y_mod2

        y = y.view(y.size(0), -1)
        y = F.relu(self.fc4(y))
        return y

class Mod3LNatureConvBody_direct_4Sig(nn.Module):
    ''' direct modulation going through a sigmoid * 2 so that the modulation can change plasticity in the rage [0,2]'''
    def __init__(self, in_channels=4):
        super(Mod3LNatureConvBody_direct_4Sig, self).__init__()
        self.feature_dim = 512
        self.conv1 = layer_init(nn.Conv2d(in_channels, 32, kernel_size=8, stride=4))
        self.conv1_mem_features = layer_init(nn.Conv2d(in_channels, 32, kernel_size=8, stride=4))
        self.conv2 = layer_init(nn.Conv2d(32, 64, kernel_size=4, stride=2))
        self.conv2_mem_features = layer_init(nn.Conv2d(32, 64, kernel_size=4, stride=2))
        self.conv3 = layer_init(nn.Conv2d(64, 64, kernel_size=3, stride=1))
        self.conv3_mem_features = layer_init(nn.Conv2d(64, 64, kernel_size=3, stride=1))

        self.fc4 = layer_init(nn.Linear(7 * 7 * 64, self.feature_dim))

    def forward(self, x, x_mem):
        y0 = F.relu(self.conv1(x))
        y_mem0 = F.relu(self.conv1_mem_features(x_mem))
        y_mod0 = 4 * torch.sigmoid(y_mem0)
        y = y0 * y_mod0

        y1 = F.relu(self.conv2(y))
        y_mem1 = F.relu(self.conv2_mem_features(y_mem0))
        y_mod1 = 4 * torch.sigmoid(y_mem1)
        y = y1 * y_mod1

        y2 = F.relu(self.conv3(y))
        y_mem2 = F.relu(self.conv3_mem_features(y_mem1))
        y_mod2 = 4 * torch.sigmoid(y_mem2)
        y = y2 * y_mod2

        y = y.view(y.size(0), -1)
        y = F.relu(self.fc4(y))
        return y

class Mod3LNatureConvBody_direct_2Sig_control(nn.Module):
    ''' direct modulation going through a sigmoid * 2 so that the modulation can change plasticity in the rage [0,2]'''
    def __init__(self, in_channels=4):
        super(Mod3LNatureConvBody_direct_2Sig_control, self).__init__()
        self.feature_dim = 512
        self.conv1 = layer_init(nn.Conv2d(in_channels, 32, kernel_size=8, stride=4))
        self.conv1_mem_features = layer_init(nn.Conv2d(in_channels, 32, kernel_size=8, stride=4))
        self.conv2 = layer_init(nn.Conv2d(32, 64, kernel_size=4, stride=2))
        self.conv2_mem_features = layer_init(nn.Conv2d(32, 64, kernel_size=4, stride=2))
        self.conv3 = layer_init(nn.Conv2d(64, 64, kernel_size=3, stride=1))
        self.conv3_mem_features = layer_init(nn.Conv2d(64, 64, kernel_size=3, stride=1))

        self.fc4 = layer_init(nn.Linear(7 * 7 * 64, self.feature_dim))

    def forward(self, x, x_mem):
        y0 = F.relu(self.conv1(x))
        y_mem0 = F.relu(self.conv1_mem_features(x_mem))
        y_mod0 = 2 * torch.sigmoid(y_mem0)
        y = y0 * y_mod0

        y1 = F.relu(self.conv2(y))
        y_mem1 = F.relu(self.conv2_mem_features(y_mem0))
        y_mod1 = 2 * torch.sigmoid(y_mem1)
        y = y1 * y_mod1

        y2 = F.relu(self.conv3(y))
        y_mem2 = F.relu(self.conv3_mem_features(y_mem1))
        y_mod2 = 2 * torch.sigmoid(y_mem2)
        y = y2 * y_mod2

        y = y.view(y.size(0), -1)
        y = F.relu(self.fc4(y))
        return y


class Mod3LNatureConvBody_directTH(nn.Module):
    '''direct neuromodulation with tanh so that plasticity is modulated in the range [-1,1].
    19/12/18 does not work, to delete'''
    def __init__(self, in_channels=4):
        super(Mod3LNatureConvBody_directTH, self).__init__()
        self.feature_dim = 512
        self.conv1 = layer_init(nn.Conv2d(in_channels, 32, kernel_size=8, stride=4))
        self.conv1_mem_features = layer_init(nn.Conv2d(in_channels, 32, kernel_size=8, stride=4))
        self.conv2 = layer_init(nn.Conv2d(32, 64, kernel_size=4, stride=2))
        self.conv2_mem_features = layer_init(nn.Conv2d(32, 64, kernel_size=4, stride=2))
        self.conv3 = layer_init(nn.Conv2d(64, 64, kernel_size=3, stride=1))
        self.conv3_mem_features = layer_init(nn.Conv2d(64, 64, kernel_size=3, stride=1))

        self.fc4 = layer_init(nn.Linear(7 * 7 * 64, self.feature_dim))

    def forward(self, x, x_mem):
        y0 = F.relu(self.conv1(x))
        y_mem0 = F.relu(self.conv1_mem_features(x_mem))
        y_mod0 = torch.tanh(y_mem0)
        y = y0 * y_mod0

        y1 = F.relu(self.conv2(y))
        y_mem1 = F.relu(self.conv2_mem_features(y_mem0))
        y_mod1 = torch.tanh(y_mem1)
        y = y1 * y_mod1

        y2 = F.relu(self.conv3(y))
        y_mem2 = F.relu(self.conv3_mem_features(y_mem1))
        y_mod2 = torch.tanh(y_mem2)
        y = y2 * y_mod2

        y = y.view(y.size(0), -1)
        y = F.relu(self.fc4(y))
        return y

class Mod3LNatureConvBody_diff_sig(nn.Module):
    '''3 layer modulation with mod computed with difference of the conv layers. 2*sigmoid at the end.'''
    def __init__(self, in_channels=4):
        super(Mod3LNatureConvBody_diff_sig, self).__init__()
        self.feature_dim = 512
        self.conv1 = layer_init(nn.Conv2d(in_channels, 32, kernel_size=8, stride=4))
        self.conv1_nm_fea = layer_init(nn.Conv2d(in_channels, 32, kernel_size=8, stride=4))
        self.conv1_nm_comb = layer_init(nn.Conv2d(32, 32, kernel_size=3, stride=1, padding=1))
        self.conv2 = layer_init(nn.Conv2d(32, 64, kernel_size=4, stride=2))
        self.conv2_nm_fea = layer_init(nn.Conv2d(32, 64, kernel_size=4, stride=2))
        self.conv2_nm_comb = layer_init(nn.Conv2d(64, 64, kernel_size=3, stride=1, padding=1))
        self.conv3 = layer_init(nn.Conv2d(64, 64, kernel_size=3, stride=1))
        self.conv3_nm_fea = layer_init(nn.Conv2d(64, 64, kernel_size=3, stride=1))
        self.conv3_nm_comb = layer_init(nn.Conv2d(64, 64, kernel_size=3, stride=1, padding=1))
        self.fc4 = layer_init(nn.Linear(7 * 7 * 64, self.feature_dim))

    def forward(self, x, x_nm):
        y0 = F.relu(self.conv1(x))
        y_nm0 = F.relu(self.conv1_nm_fea(x_nm))
        y_nm = y0 - y_nm0
        y_nm = 2*torch.sigmoid(self.conv1_nm_comb(y_nm))
        y = y0*y_nm

        y0 = F.relu(self.conv2(y))
        y_nm0 = F.relu(self.conv2_nm_fea(y_nm0))
        y_nm = y0 - y_nm0
        y_nm = 2*torch.sigmoid(self.conv2_nm_comb(y_nm))
        y = y0*y_nm

        y0 = F.relu(self.conv3(y))
        y_nm0 = F.relu(self.conv3_nm_fea(y_nm0))
        y_nm = y0 - y_nm0
        y_nm = 2*torch.sigmoid(self.conv3_nm_comb(y_nm))
        y = y0*y_nm

        y = y.view(y.size(0), -1)
        y = F.relu(self.fc4(y))
        return y

class ModNatureConvBody_Prediction(nn.Module):
    '''Working progress to get the latent space prediction (AS)'''
    def __init__(self, in_channels=4):
        super(ModNatureConvBodyPrediction, self).__init__()
        self.feature_dim = 512
        self.conv1 = layer_init(nn.Conv2d(in_channels, 32, kernel_size=8, stride=4))
        self.conv2 = layer_init(nn.Conv2d(32, 64, kernel_size=4, stride=2))
        self.conv3 = layer_init(nn.Conv2d(64, 64, kernel_size=3, stride=1))
        self.fc4 = layer_init(nn.Linear(7 * 7 * 64, self.feature_dim))

    def forward(self, x):
        y = F.relu(self.conv1(x))
        y = F.relu(self.conv2(y))
        y = F.relu(self.conv3(y))
        y = y.view(y.size(0), -1)
        y = F.relu(self.fc4(y))
        return y
 #3-layer modulated by AS, memory modulates directly layer 1 and 2 without computing the difference. The sigmoid is reduced in intensity

class DDPGConvBody(nn.Module):
    def __init__(self, in_channels=4):
        super(DDPGConvBody, self).__init__()
        self.feature_dim = 39 * 39 * 32
        self.conv1 = layer_init(nn.Conv2d(in_channels, 32, kernel_size=3, stride=2))
        self.conv2 = layer_init(nn.Conv2d(32, 32, kernel_size=3))

    def forward(self, x):
        y = F.elu(self.conv1(x))
        y = F.elu(self.conv2(y))
        y = y.view(y.size(0), -1)
        return y

class FCBody(nn.Module):
    def __init__(self, state_dim, hidden_units=(64, 64), gate=F.relu):
        super(FCBody, self).__init__()
        dims = (state_dim, ) + hidden_units
        self.layers = nn.ModuleList([layer_init(nn.Linear(dim_in, dim_out)) for dim_in, dim_out in zip(dims[:-1], dims[1:])])
        self.gate = gate
        self.feature_dim = dims[-1]

    def forward(self, x):
        for layer in self.layers:
            x = self.gate(layer(x))
        return x

class TwoLayerFCBodyWithAction(nn.Module):
    def __init__(self, state_dim, action_dim, hidden_units=(64, 64), gate=F.relu):
        super(TwoLayerFCBodyWithAction, self).__init__()
        hidden_size1, hidden_size2 = hidden_units
        self.fc1 = layer_init(nn.Linear(state_dim, hidden_size1))
        self.fc2 = layer_init(nn.Linear(hidden_size1 + action_dim, hidden_size2))
        self.gate = gate
        self.feature_dim = hidden_size2

    def forward(self, x, action):
        x = self.gate(self.fc1(x))
        phi = self.gate(self.fc2(torch.cat([x, action], dim=1)))
        return phi

class OneLayerFCBodyWithAction(nn.Module):
    def __init__(self, state_dim, action_dim, hidden_units, gate=F.relu):
        super(OneLayerFCBodyWithAction, self).__init__()
        self.fc_s = layer_init(nn.Linear(state_dim, hidden_units))
        self.fc_a = layer_init(nn.Linear(action_dim, hidden_units))
        self.gate = gate
        self.feature_dim = hidden_units * 2

    def forward(self, x, action):
        phi = self.gate(torch.cat([self.fc_s(x), self.fc_a(action)], dim=1))
        return phi

class DummyBody(nn.Module):
    def __init__(self, state_dim):
        super(DummyBody, self).__init__()
        self.feature_dim = state_dim

    def forward(self, x):
        return x
