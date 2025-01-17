##rcan的通道注意力换为二阶注意力
from model import common

import torch.nn as nn
import torch


def make_model(args, parent=False):
    return MRCAN(args)


## Channel Attention (CA) Layer
class CALayer(nn.Module):
    def __init__(self, channel, reduction=16, a_kernel_size=13):
        super(CALayer, self).__init__()
        # global average pooling: feature --> point
        self.avg_pool1 = nn.AdaptiveAvgPool2d(1)
        # feature channel downscale and upscale --> channel weight
        self.conv_du1 = nn.Sequential(
            nn.Conv2d(channel, channel // reduction, 1, padding=0, bias=True),
            nn.ReLU(inplace=True),
            nn.Conv2d(channel // reduction, channel, 1, padding=0, bias=True),
	        nn.Sigmoid()
        )

        # feature channel downscale and upscale --> channel weight
        self.conv_du2 = nn.Sequential(
            nn.Conv2d(channel, 1, 1, padding=0, bias=True),
            nn.ReLU(inplace=True),
            nn.Conv2d(1, 1, a_kernel_size, padding=a_kernel_size//2, bias=True),
            nn.ReLU(inplace=True),
            nn.Conv2d(1, 1, a_kernel_size, padding=a_kernel_size//2, bias=True),
	        nn.Sigmoid()
        )
    def forward(self, x):
        y1 = self.avg_pool1(x)
        y1 = self.conv_du1(y1)
        y2= self.conv_du2(x)
        return x * (y1*y2)


## Residual Channel Attention Block (RCAB)
class RCAB(nn.Module):
    def __init__(
            self, conv, n_feat, kernel_size, a_kernel_size, reduction,
            bias=True, bn=False, act=nn.ReLU(True), res_scale=1):

        super(RCAB, self).__init__()
        modules_body = []
        for i in range(2):
            modules_body.append(conv(n_feat, n_feat, kernel_size, bias=bias))
            if bn: modules_body.append(nn.BatchNorm2d(n_feat))
            if i == 0: modules_body.append(act)
        # modules_body.append(CALayer(n_feat, reduction, a_kernel_size))
        self.body = nn.Sequential(*modules_body)
        self.res_scale = res_scale

    def forward(self, x):
        res = self.body(x)
        # res = self.body(x).mul(self.res_scale)
        res += x
        return res
## Residual Group (RG)
class ResidualGroup(nn.Module):
    def __init__(self, conv, n_feat, kernel_size, a_kernel_size, reduction, i, act, res_scale, n_resblocks):
        super(ResidualGroup, self).__init__()
        modules_body = []

        self.down = conv(n_feat*(i+1), n_feat, 1)
        self.atten = CALayer(n_feat, reduction, a_kernel_size)
        for _ in range(n_resblocks):
            modules_body.append(RCAB(conv, n_feat, kernel_size, a_kernel_size, reduction, bias=True, bn=False, act=nn.ReLU(True), res_scale=1))

        self.body = nn.Sequential(*modules_body)


    def forward(self, x):
        x = self.down(torch.cat(x, 1))
        x = self.atten(x)
        res = self.body(x)

        # res += x
        return res


## Residual Channel Attention Network (MCAN)
class MRCAN(nn.Module):
    def __init__(self, args, conv=common.default_conv):
        super(MRCAN, self).__init__()

        n_resgroups = 10
        n_resblocks = 20
        n_feats = 64
        kernel_size = 3
        a_kernel_size = 13
        reduction = 16
        self.n_resgroups = n_resgroups
        scale = args.scale[0]
        act = nn.ReLU(True)

        # RGB mean for DIV2K
        self.sub_mean = common.MeanShift(args.rgb_range)

        # define head module
        modules_head = [conv(args.n_colors, n_feats, kernel_size)]

        # define body module
        modules_body = []
        for i in range(n_resgroups):
            modules_body.append(ResidualGroup(conv, n_feats, kernel_size, a_kernel_size, reduction,i, act=act, res_scale=args.res_scale, n_resblocks=n_resblocks))

        modules_body.append(conv(n_feats, n_feats, kernel_size))

        # define tail module
        modules_tail = [
            common.Upsampler(conv, scale, n_feats, act=False),
            conv(n_feats, args.n_colors, kernel_size)]

        self.add_mean = common.MeanShift(args.rgb_range, sign=1)

        self.head = nn.Sequential(*modules_head)
        self.body = nn.Sequential(*modules_body)
        self.tail = nn.Sequential(*modules_tail)

    def forward(self, x):
        x = self.sub_mean(x)
        x = self.head(x)

        # res = self.body(x)
        tem = []
        tem.append(x)
        for i in range(self.n_resgroups):
            res = self.body[i](tem)
            tem.append(res)
        res += x

        x = self.tail(res)
        x = self.add_mean(x)

        return x

    def load_state_dict(self, state_dict, strict=False):
        own_state = self.state_dict()
        for name, param in state_dict.items():
            if name in own_state:
                if isinstance(param, nn.Parameter):
                    param = param.data
                try:
                    own_state[name].copy_(param)
                except Exception:
                    if name.find('tail') >= 0:
                        print('Replace pre-trained upsampler to new one...')
                    else:
                        raise RuntimeError('While copying the parameter named {}, '
                                           'whose dimensions in the model are {} and '
                                           'whose dimensions in the checkpoint are {}.'
                                           .format(name, own_state[name].size(), param.size()))
            elif strict:
                if name.find('tail') == -1:
                    raise KeyError('unexpected key "{}" in state_dict'
                                   .format(name))

        if strict:
            missing = set(own_state.keys()) - set(state_dict.keys())
            if len(missing) > 0:
                raise KeyError('missing keys in state_dict: "{}"'.format(missing))
